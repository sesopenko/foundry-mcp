"""PF2e-specific party source membership on core14.369/PF2e8.6.1.

Only party system.details.members[].uuid establishes membership; no player role,
stash, wealth or Bulk calculations. Browser uses public world Actor documents.
https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/party/data.ts
"""
from typing import Annotated, Literal

from fastmcp.exceptions import ToolError
from pydantic import Field, model_validator

from .selective_models import Model, PageRequest, Pagination, Runtime

WorldActorUuid = Annotated[str, Field(max_length=512, pattern=r'^Actor\.[^.\s#]+$')]


class PartyRequest(PageRequest):
    party_uuid: WorldActorUuid | None = Field(default=None, description='World party Actor UUID from this tool; omit to auto-select the sole readable party or list candidates. Never a name, local ID, token or pack UUID.')


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


class PartyResult(Model):
    contract_version: Literal[2]
    runtime: Runtime
    revision: Annotated[str, Field(min_length=1, max_length=128)]
    mode: Literal['parties', 'members']
    party: PartyIdentity | None
    scope_status: Literal['complete', 'partial'] = Field(description='Whether the selected roster/candidate scope is fully readable; independent of pagination.complete.')
    reasons: list[Literal['parties_denied', 'duplicate_member_references', 'member_missing', 'member_denied', 'member_unsupported']]
    entries: list[Annotated[PartyCandidate | PartyMember, Field(discriminator='kind')]]
    pagination: Pagination

    @model_validator(mode='after')
    def coherent_scope(self):
        if self.runtime != Runtime(core_version='14.369', system_id='pf2e', system_version='8.6.1'):
            raise ValueError('Unverified runtime')
        if len(set(self.reasons)) != len(self.reasons) or (self.scope_status == 'complete') != (not self.reasons):
            raise ValueError('Scope status must agree with reasons')
        if self.pagination.returned != len(self.entries) or self.pagination.complete != (self.pagination.next_cursor is None):
            raise ValueError('Inconsistent pagination')
        if not self.pagination.complete and not self.entries:
            raise ValueError('Incomplete page must make progress')
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
        identities = [e.identity.uuid for e in self.entries if e.identity is not None]
        if len(identities) != len(set(identities)):
            raise ValueError('Repeated Actor identity')
        return self


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
"""
