"""PF2e-specific party membership and physical stash on core14.369/PF2e8.6.1.

Only party system.details.members[].uuid establishes membership; no player role,
or wealth/Bulk calculations. Stash uses actual physical embedded Item source,
not member inventories. Browser uses public world Actor/Item documents.
https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/party/data.ts
"""
from typing import Annotated, Literal

from fastmcp.exceptions import ToolError
from pydantic import Field, model_validator

from .selective_models import Model, PageRequest, Pagination, Runtime

WorldActorUuid = Annotated[str, Field(max_length=512, pattern=r'^Actor\.[^.\s#]+$')]


class PartyRequest(PageRequest):
    party_uuid: WorldActorUuid | None = Field(default=None, description='World party Actor UUID from this tool; omit to auto-select the sole readable party or list candidates. Never a name, local ID, token or pack UUID.')


class StashSelect(Model):
    quantity: bool = Field(default=True, description='Stored physical Item stock, with explicit present/value. Not currency value or wealth.')
    container: bool = Field(default=False, description='Stored containerId: a same-owner local Item-ID claim, not a UUID or verified containment tree.')
    follow_up: bool = Field(default=True, description='Include read_item next_call for source details and exact description.')


class StashRequest(PartyRequest):
    select: StashSelect = Field(default_factory=StashSelect, description='Select summary values before pagination. Identity always included; read_item expands source/description/evidence.')


class PartyIdentity(Model):
    uuid: WorldActorUuid
    name: Annotated[str, Field(max_length=256)]
    name_truncated: bool
    type: Annotated[str, Field(min_length=1, max_length=100)]


class PartyArguments(Model):
    party_uuid: WorldActorUuid


class ActorArguments(Model):
    actor_uuid: WorldActorUuid


class PartyFollowUp(Model):
    tool: Literal['get_party_members']
    arguments: PartyArguments


class ActorFollowUp(Model):
    tool: Literal['read_actor']
    arguments: ActorArguments


class PartyCandidate(Model):
    kind: Literal['party']
    identity: PartyIdentity
    next_call: PartyFollowUp

    @model_validator(mode='after')
    def matching_target(self):
        if self.identity.type != 'party' or self.next_call.arguments.party_uuid != self.identity.uuid:
            raise ValueError('Party follow-up must identify the same party')
        return self


class PartyMember(Model):
    kind: Literal['member']
    index: Annotated[int, Field(ge=0, le=199, description='First zero-based position in stored membership; not an Actor ID.')]
    status: Literal['resolved', 'missing', 'denied', 'unsupported']
    identity: PartyIdentity | None
    next_call: ActorFollowUp | None

    @model_validator(mode='after')
    def matching_target(self):
        if self.status == 'resolved':
            if (self.identity is None or self.identity.type not in ('character', 'npc', 'familiar')
                    or self.next_call is None or self.next_call.arguments.actor_uuid != self.identity.uuid):
                raise ValueError('Resolved member needs a supported Actor and matching follow-up')
        elif self.next_call is not None or self.status in ('missing', 'denied') and self.identity is not None:
            raise ValueError('Unavailable member must not expose a follow-up or denied identity')
        elif self.identity is not None and self.identity.type in ('character', 'npc', 'familiar'):
            raise ValueError('Supported member cannot be labelled unsupported')
        return self


class PartyPage(Model):
    """Shared PF2e-specific8.6.1 party scope/page invariants, no calculations."""
    contract_version: Literal[2]
    runtime: Runtime
    revision: Annotated[str, Field(min_length=1, max_length=128)]
    party: PartyIdentity | None
    scope_status: Literal['complete', 'partial'] = Field(description='Whether the selected party scope is fully readable/supported; independent of pagination.complete.')
    pagination: Pagination

    @model_validator(mode='after')
    def coherent_page(self):
        if self.runtime != Runtime(core_version='14.369', system_id='pf2e', system_version='8.6.1'):
            raise ValueError('Unverified runtime')
        if len(set(self.reasons)) != len(self.reasons) or (self.scope_status == 'complete') != (not self.reasons):
            raise ValueError('Scope status must agree with reasons')
        if self.pagination.returned != len(self.entries) or self.pagination.complete != (self.pagination.next_cursor is None):
            raise ValueError('Inconsistent pagination')
        if not self.pagination.complete and not self.entries:
            raise ValueError('Incomplete page must make progress')
        identities = [e.identity.uuid for e in self.entries if e.identity is not None]
        if len(identities) != len(set(identities)):
            raise ValueError('Repeated document identity')
        return self


class PartyResult(PartyPage):
    mode: Literal['parties', 'members']
    reasons: list[Literal['parties_denied', 'duplicate_member_references', 'member_missing', 'member_denied', 'member_unsupported']]
    entries: list[Annotated[PartyCandidate | PartyMember, Field(discriminator='kind')]]

    @model_validator(mode='after')
    def coherent_scope(self):
        if self.mode == 'parties':
            if self.party is not None or any(not isinstance(e, PartyCandidate) for e in self.entries) or set(self.reasons) - {'parties_denied'}:
                raise ValueError('Invalid party candidate scope')
        else:
            if self.party is None or self.party.type != 'party' or any(not isinstance(e, PartyMember) for e in self.entries) or 'parties_denied' in self.reasons:
                raise ValueError('Invalid member scope')
            indexes = [e.index for e in self.entries]
            if indexes != sorted(set(indexes)):
                raise ValueError('Member positions must be ordered and unique')
            if any(e.status != 'resolved' and 'member_' + e.status not in self.reasons for e in self.entries):
                raise ValueError('Unavailable member lacks scope reason')
        return self


StashItemUuid = Annotated[str, Field(max_length=512, pattern=r'^Actor\.[^.\s#]+\.Item\.[^.\s#]+$')]
PhysicalType = Literal['weapon', 'armor', 'shield', 'equipment', 'consumable', 'ammo', 'backpack', 'book', 'treasure']


class StashIdentity(Model):
    uuid: StashItemUuid
    name: Annotated[str, Field(max_length=256)]
    name_truncated: bool
    type: PhysicalType


class Quantity(Model):
    present: bool
    value: Annotated[int | float, Field(ge=0, allow_inf_nan=False)] | None = None

    @model_validator(mode='after')
    def present_value(self):
        if self.present != ('value' in self.model_fields_set) or self.present and self.value is None:
            raise ValueError('Quantity presence must match its finite nonnegative value')
        return self


class Container(Model):
    present: bool
    value: Annotated[str, Field(max_length=512)] | None = None

    @model_validator(mode='after')
    def present_value(self):
        if self.present != ('value' in self.model_fields_set):
            raise ValueError('Container presence must match the source value, including null')
        return self


class StashItemArguments(Model):
    item_uuid: StashItemUuid


class StashItemFollowUp(Model):
    tool: Literal['read_item']
    arguments: StashItemArguments


class StashPartyFollowUp(Model):
    tool: Literal['get_party_stash']
    arguments: PartyArguments


class StashCandidate(PartyCandidate):
    next_call: StashPartyFollowUp


class StashItem(Model):
    kind: Literal['item']
    identity: StashIdentity
    quantity: Quantity | None = None
    container: Container | None = None
    next_call: StashItemFollowUp | None = None

    @model_validator(mode='after')
    def matching_target(self):
        if self.next_call is not None and self.next_call.arguments.item_uuid != self.identity.uuid:
            raise ValueError('Stash Item follow-up must identify the same Item')
        for field in ('quantity', 'container', 'next_call'):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError('Unselected fields must be omitted, not null')
        return self


class StashResult(PartyPage):
    mode: Literal['parties', 'stash']
    basis: Literal['source']
    reasons: list[Literal['parties_denied', 'stash_items_denied', 'stash_nonphysical_excluded']]
    entries: list[Annotated[StashCandidate | StashItem, Field(discriminator='kind')]]

    @model_validator(mode='after')
    def coherent_scope(self):
        if self.mode == 'parties':
            if self.party is not None or any(not isinstance(e, StashCandidate) for e in self.entries) or set(self.reasons) - {'parties_denied'}:
                raise ValueError('Invalid stash party candidates')
        elif (self.party is None or self.party.type != 'party' or 'parties_denied' in self.reasons
              or any(not isinstance(e, StashItem) or e.identity.uuid.rsplit('.Item.', 1)[0] != self.party.uuid for e in self.entries)):
            raise ValueError('Stash Items must belong to the selected party')
        uuids = [e.identity.uuid for e in self.entries]
        if uuids != sorted(uuids):
            raise ValueError('Stash entries must be ordered by UUID')
        return self


async def read_stash(request: StashRequest):
    """PF2e-specific8.6.1 physical party stock, never member inventories/totals.

    Uses public embedded Item source; schema/version evidence: module actorParty.js.
    """
    from .selective import rpc
    result = await rpc('getPartyStash', request.model_dump(exclude_none=True))
    try:
        validated = StashResult.model_validate(result)
        if len(validated.entries) > request.limit:
            raise ValueError('Page exceeds requested limit')
        if request.party_uuid is not None and (validated.party is None or validated.party.uuid != request.party_uuid):
            raise ValueError('Wrong party')
        if validated.mode == 'stash':
            for entry in validated.entries:
                for key, enabled in request.select.model_dump().items():
                    field = 'next_call' if key == 'follow_up' else key
                    if (field in entry.model_fields_set) != enabled:
                        raise ValueError('Stash response does not match selection')
    except (ValueError, TypeError):
        raise ToolError('InvalidFoundryResponse: party stash failed validation; check server/module compatibility.') from None
    return result


async def read_party(request: PartyRequest):
    """PF2e-specific source roster read, never inferred player roles or totals."""
    from .selective import rpc
    result = await rpc('getPartyMembers', request.model_dump(exclude_none=True))
    # Output shape is validated again at the actual FastMCP boundary.
    try:
        validated = PartyResult.model_validate(result)
        if len(validated.entries) > request.limit:
            raise ValueError('Page exceeds requested limit')
        if request.party_uuid is not None and (validated.party is None or validated.party.uuid != request.party_uuid):
            raise ValueError('Wrong party')
    except (ValueError, TypeError):
        raise ToolError('InvalidFoundryResponse: party roster failed validation; check server/module compatibility.') from None
    return result


PARTY_DOC = """PF2e-specific GM read of official party membership (core14.369/PF2e8.6.1).
Use for 'the PCs' before individual read_actor calls: take resolved character
members, not player ownership, logged-in users or every character in the world.
Reads persisted party membership, not stash, Bulk or wealth. Other systems/
versions are unsupported. Requires ready authenticated GM and OBSERVER rights.

Omit party_uuid: sole readable world party auto-selects; otherwise mode=parties
returns named candidates. Choose a candidate's next_call; never choose among
multiple parties arbitrarily. With no candidates, scope_status=complete means
no world parties, partial means inaccessible parties exist. Explicit party_uuid
is a world Actor UUID supplied here, never a name/local ID/pack/token selector.

Returns contract_version=2,runtime,revision,mode,party,scope_status,reasons,entries,
pagination. mode=members includes named party and member entries with first
zero-based source index, status, identity and next_call. Resolved character/npc/
familiar identities have uuid,name,name_truncated,type and read_actor follow-ups.
Missing/denied identities are null; unsupported references/types have no follow-up.
Only world Actor membership is resolved; pack/token references stay unsupported.
Duplicate references appear once with a reason; duplicate names stay distinct.
Names clip at 256 characters. Complete empty member entries mean an empty party.

limit defaults 10 (1–100 entries), max_bytes 8000 (8000–48000 compact UTF-8 JSON
bytes). Copy pagination.next_cursor unchanged with ALL original inputs until
pagination.complete; it covers paging, while scope_status covers missing/denied/
unsupported membership. Candidates order by UUID; members by stored position.
Recheck the selected party revision after multi-character reads; those reads
are sequential, not an atomic party snapshot. Never claim a whole-party ranking
when membership or required character values are incomplete.

ContentChanged: discard pages and restart. InvalidCursor/CursorMismatch: restart
without cursor or restore original inputs. DocumentNotFound: rediscover parties.
PermissionDenied: obtain GM/document access. UnsupportedType: choose a party.
UnsupportedSystem/Version: inspect get_actor_types. BridgeUnavailable: reconnect
the existing GM browser. ResponseTooLarge: raise max_bytes. InvalidRequest: use
published bounds; unknown inputs rejected before reads. ReadFailed: inspect
membership source; limits are 12000 world Actors, 200 parties/200 member claims.
Example: get_party_members({}), then each returned read_actor next_call.
For shared possessions, call get_party_stash with the selected party UUID.
"""

STASH_DOC = """PF2e-specific GM read of official party stash (core14.369/PF2e8.6.1).
Use for shared possessions, not member inventories or inferred player ownership.
Requires ready authenticated GM and OBSERVER access to party and each Item.
Other systems/versions are unsupported. Read-only: no transfers, writes or rolls.

Omit party_uuid to auto-select the sole readable party or return mode=parties
with named candidates and get_party_stash next_call. Or copy a world Actor UUID
from get_party_members. Never accept names, local IDs, token or pack selectors.
Multiple parties require explicit choice; inaccessible parties are not absent.
Complete empty candidates mean no world parties; empty partial candidates with
parties_denied mean inaccessible parties exist. Generic party read_actor and
list_actor_items remain unsupported; use this tool for the stash instead.

Returns contract_version=2,runtime,revision,mode,party,basis=source,scope_status,
reasons,entries,pagination. mode=stash has the named owner and actual embedded
physical Items, ordered by UUID. identity contains uuid,name,name_truncated,type;
names clip at 256 Unicode characters, UUIDs stay intact. Default quantity has
present and, when stored, value (zero is real stock, not missing). It is NOT
currency value, wealth, Bulk or effective benefits. select.quantity=false omits
stock; select.container=true adds container {present,value?}, a stored local
Item-ID claim (null means no container), not a verified hierarchy or UUID.
select.follow_up defaults true: next_call targets read_item by returned Item
UUID, preserving party ownership. Read source.physical, other source groups,
description or evidence there on demand, using its continuations for full text.
No party campaign data, member source, prepared inventory or serialized subitems
are expanded. Denied Item identities/source are withheld; stash_items_denied
and stash_nonphysical_excluded make scope_status partial. Nonphysical campaign
Items are outside stash scope. Complete empty stash means no physical Items.

Defaults: limit=10 (1–100 entries), max_bytes=8000 (8000–48000 compact UTF-8 JSON
bytes). select precedes pagination. Pass pagination.next_cursor unchanged with
ALL original party/select/bounds inputs until pagination.complete=true. That
only completes enumeration; scope_status reports excluded/denied content.
Revisions cover selected source values, named identities and permission scope;
separate read_item calls are sequential observations, not an atomic snapshot.
ContentChanged: discard pages and restart. CursorMismatch/InvalidCursor: restore
original inputs or restart without cursor. ResponseTooLarge: raise max_bytes.
DocumentNotFound: rediscover party; PermissionDenied: restore GM/document access.
UnsupportedType: select a party. UnsupportedSystem/Version: inspect get_actor_types.
BridgeUnavailable: reconnect existing GM browser. InvalidRequest: inspect schema;
unknown fields fail before reads. ReadFailed: inspect malformed source/identities
or the 12000 world-Actor/200-party/12000 owned-Item snapshot limits.
Example: get_party_stash({party_uuid:"Actor.<returned-id>",select:{container:true}}),
then copy an Item's read_item next_call and select its desired details.
"""
