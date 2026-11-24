"""PF2e-specific 8.7.0 weapon Details and nine physical Item source edits.

The browser validates the final Item against its world choices. Authored
changes never write adjusted values. See docs/item-sheet-controls.md and
https://github.com/foundryvtt/pf2e/blob/52dfeee703b887237f5e454747bcae45b136f9af/src/module/item/weapon/data.ts
"""
import re
from typing import Annotated, ClassVar, Literal

from fastmcp.exceptions import ToolError
from pydantic import AfterValidator, ConfigDict, Field, JsonValue, RootModel, model_validator
from starlette.websockets import WebSocketDisconnect
from typing_extensions import TypedDict

from . import selective_models as M
from .journal_image_models import ImageSelector
from foundry_mcp_server.ws.connection import RpcError


def prose(value):
    if re.search(r'\[\[|@[\w.:-]+\s*\[|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', value):
        raise ValueError('Use plain prose without inline notation or control characters')
    return value


Name = Annotated[str, Field(min_length=1, max_length=256), AfterValidator(prose)]
ShortText = Annotated[str, Field(max_length=256), AfterValidator(prose)]
Prose = Annotated[str, Field(max_length=2000), AfterValidator(prose)]
Code = Annotated[str, Field(min_length=1, max_length=128)]
Codes = Annotated[list[Code], Field(max_length=100)]
Tier = Annotated[int, Field(ge=0, le=4)]
Ordinal = Annotated[int, Field(ge=1, le=5)]
Amount = Annotated[int, Field(ge=0, le=999999)]
Die = Literal['d4','d6','d8','d10','d12']
Group = Literal['header','weapon_summary','details','material_and_runes','damage','other_tags','publication','description','mystification']


class Header(TypedDict, total=False):
    image: ImageSelector
    name: Name
    level: Annotated[int, Field(ge=0, le=30)]
    rarity: Literal['common','uncommon','rare','unique']
    traits: Codes


class Coins(TypedDict, total=False):
    pp: Amount
    gp: Amount
    sp: Amount
    cp: Amount


class Summary(TypedDict, total=False):
    quantity: Annotated[int, Field(ge=1, le=999999)]
    hands: Literal['worngloves','held-in-one-hand','held-in-one-plus-hands','held-in-two-hands']
    bulk: Literal[0.1] | Annotated[int, Field(ge=0, le=50)]
    size: Literal['tiny','med','lg','huge','grg']
    price: Coins


class Details(TypedDict, total=False):
    category: Literal['unarmed','simple','martial','advanced']
    group: Code | None
    base: Code | None
    range: Literal[10,15,20,30,40,50,60,70,80,90,100,110,120,140,150,180,200,240,300] | None


class Material(TypedDict, total=False):
    type: Code
    grade: Literal['low','standard','high']


class Slot(TypedDict):
    slot: Ordinal
    value: Code | None


class Runes(TypedDict, total=False):
    precious_material: Material | None
    potency_rune: Tier
    striking_rune: Tier
    property_runes: Annotated[list[Slot], Field(min_length=1, max_length=5)]
    specific_magic_weapon: bool


def base_damage_type(value):
    """PF2e-specific 8.7.0 weapon base damage excludes bleed; world choices are checked by the GM."""
    if value == 'bleed':
        raise ValueError('Bleed applies to persistent damage')
    return value


class BaseDamage(TypedDict, total=False):
    dice: Annotated[int, Field(ge=0, le=14)]
    die: Die | None
    type: Annotated[Code, AfterValidator(base_damage_type)]


class Persistent(TypedDict, total=False):
    amount: Annotated[int, Field(ge=1, le=999999)]
    faces: Literal[4,6,8,10,12] | None
    type: Code


class Damage(TypedDict, total=False):
    base: BaseDamage
    splash: Amount
    persistent: Persistent | None


class Tags(TypedDict, total=False):
    tags: Codes


class Publication(TypedDict, total=False):
    title: ShortText
    authors: ShortText
    license: Literal['OGL','ORC']
    remaster: bool


class Description(TypedDict, total=False):
    text: Prose


class Mystification(TypedDict, total=False):
    identification_status: Literal['identified','unidentified']
    unidentified_name: Name
    unidentified_description: Prose


class Changes(TypedDict, total=False):
    header: Header
    weapon_summary: Summary
    details: Details
    material_and_runes: Runes
    damage: Damage
    other_tags: Tags
    publication: Publication
    description: Description
    mystification: Mystification


CONTROLS = {f'{group}.{field}' for group, model in Changes.__annotations__.items()
            for field in model.__annotations__} | {'header.display_name'}
LEAVES = {f'{field}.{leaf}' for field, model in [
    ('damage.base', BaseDamage), ('damage.persistent', Persistent),
    ('material_and_runes.precious_material', Material), ('weapon_summary.price', Coins)
] for leaf in model.__annotations__}


def known_field(field):
    if field not in CONTROLS | LEAVES:
        raise ValueError('Unknown sheet field. Read the applicable sheet groups for field IDs.')
    return field


FieldId = Annotated[str, AfterValidator(known_field)]


def populated(data):
    if isinstance(data, dict):
        if not data:
            raise ValueError('Each change object needs at least one field')
        for value in data.values():
            populated(value)
    if isinstance(data, list):
        keys = [v['slot'] if isinstance(v, dict) else v for v in data]
        if len(keys) != len(set(keys)):
            raise ValueError('Duplicate slot or code')
    return data


Proposal = Annotated[Changes, AfterValidator(populated)]


class Sheet(M.UniqueSelections):
    groups: list[Group] = Field(default_factory=list, max_length=9)
    fields: list[FieldId] = Field(default_factory=list, max_length=64,
                                 description='Qualified control or leaf IDs. Empty sheet omits long descriptions.')

    @model_validator(mode='after')
    def selected_groups(self):
        if self.groups and any(f.split('.')[0] not in self.groups for f in self.fields):
            raise ValueError('fields must belong to selected groups')
        return self


class ReadItem(M.ItemRequest):
    sheet: Sheet | None = Field(default=None, description='PF2e 8.7.0 physical Item form. Exclusive with select/sections.')

    @model_validator(mode='after')
    def exclusive(self):
        if self.sheet is not None and (self.sections is not None or self.select is not None):
            raise ValueError('Use exactly one of sheet, sections and select')
        return self


class Target(M.Model):
    item_uuid: M.Identifier = Field(description='Canonical Item UUID from read_item or inventory discovery.')
    token_uuid: M.Identifier | None = Field(default=None, description='Reuse placed token UUID for an unlinked inventory.')


class Options(M.PageRequest, Target):
    field: FieldId
    slot: Ordinal | None = None
    proposed_changes: Proposal | None = None
    query: Annotated[str, Field(min_length=1, max_length=200)] | None = None

    @model_validator(mode='after')
    def slot_field(self):
        if (self.field == 'material_and_runes.property_runes') != (self.slot is not None):
            raise ValueError('Supply slot only and always for property_runes')
        return self


class Edit(Target):
    max_bytes: ClassVar[int] = 8000
    changes: Proposal
    mode: Literal['preview','apply'] = 'preview'
    expected_revision: M.Identifier | None = None

    @model_validator(mode='after')
    def apply_revision(self):
        if (self.mode == 'apply') != (self.expected_revision is not None):
            raise ValueError('Only apply requires the revision from preview')
        return self


class LookupArgs(Target):
    field: FieldId
    slot: Ordinal | None = None


class FieldLookup(M.Model):
    tool: Literal['get_item_field_options']
    arguments: LookupArgs


class Fragment(M.Model):
    start: int
    end: int
    total: int
    complete: bool


class BaselineMaterial(TypedDict, total=False):
    type: str | None
    grade: str | None


class BaselineRunes(TypedDict, total=False):
    potency: int
    striking: int
    property: list[str]


class SpecificBaseline(TypedDict, total=False):
    material: BaselineMaterial
    runes: BaselineRunes


class Control(M.Model):
    group: Group
    group_label: str
    field: FieldId
    label: str
    present: bool
    source: JsonValue = None
    display: JsonValue = None
    display_label: str | None = None
    display_basis: Literal['transformed','source','document','unavailable']
    editable: bool
    reason: str | None = None
    display_reason: str | None = None
    slot: Ordinal | None = None
    slot_state: Literal['free','occupied','derived'] | None = None
    specific_baseline: SpecificBaseline | None = None
    text: Fragment | None = None
    display_text: Fragment | None = None
    choice_fields: list[FieldId] | None = None
    options: FieldLookup | None = None


class Page(M.Model):
    runtime: M.Runtime
    identity: M.Identity
    revision: str
    pagination: M.Pagination


class SheetResult(Page):
    contract_version: Literal[3]
    unsupported_groups: list[Group]
    records: list[Control]


class ItemResult(RootModel[Annotated[M.ReadResult | SheetResult, Field(discriminator='contract_version')]]):
    # Older negotiated MCP versions require the object type on the union itself.
    model_config = ConfigDict(json_schema_extra={'type': 'object'})


class Choice(M.Model):
    value: str | int | float | bool | Material | None
    label: str
    available: bool


class OptionResult(Page):
    field: FieldId
    label: str
    available: bool
    reason: str | None = None
    records: list[Choice]


class ChangeRow(M.Model):
    field: FieldId
    label: str
    before: JsonValue
    after: JsonValue
    present: bool
    excerpt: bool


class ReadbackArgs(Target):
    sheet: Sheet


class Readback(M.Model):
    tool: Literal['read_item']
    arguments: ReadbackArgs


class Receipt(M.Model):
    status: Literal['preview','applied','unchanged']
    identity: M.Identity
    revision: str
    changes: list[ChangeRow]
    next_call: Readback


UNKNOWN_OUTCOME = 'WriteOutcomeUnknown: read_item with the original target and sheet fields before another preview or apply.'


async def invoke(request):
    """Route PF2e-specific sheet reads/choices and source-only writes to the exact GM."""
    from .selective import read, size
    from .tools import _foundry_manager
    if isinstance(request, ReadItem) and request.sheet is None:
        return await read(M.ItemRequest.model_validate(request.model_dump(exclude={'sheet'})))
    params = request.model_dump(mode='json', exclude_unset=True)
    for name in ('token_uuid','cursor','query','expected_revision','proposed_changes','slot'):
        if params.get(name) is None:
            params.pop(name, None)
    method = {ReadItem: 'readItemSheet', Options: 'getItemFieldOptions', Edit: 'editItem'}[type(request)]
    apply = isinstance(request, Edit) and request.mode == 'apply'
    try:
        result = await _foundry_manager.call('gm', method, params, timeout=15.0)
        identity = result['identity']
        if identity['uuid'] != request.item_uuid or (identity['instance'] or {}).get('token_uuid') != request.token_uuid:
            raise ValueError()
        if isinstance(request, Edit):
            receipt = Receipt.model_validate(result)
            follow_up = receipt.next_call.arguments
            fields = sorted(f'{group}.{key}' for group, values in request.changes.items() for key in values)
            if ((receipt.status == 'preview') == apply or (apply and receipt.revision != request.expected_revision)
                    or follow_up.item_uuid != request.item_uuid or follow_up.token_uuid != request.token_uuid
                    or follow_up.sheet.groups or sorted(follow_up.sheet.fields) != fields
                    or sorted(row.field for row in receipt.changes) != fields or size(result) > request.max_bytes):
                raise ValueError('Receipt does not confirm the requested edit')
        return result
    except RpcError as exc:
        error = exc.error
        if apply and not error.get('code'):
            raise ToolError(UNKNOWN_OUTCOME) from None
        raise ToolError(f"{error.get('code','RpcError')}: {error.get('message','Item operation failed')}. {error.get('recovery','Read the Item again.')}") from None
    except (OSError, WebSocketDisconnect, RuntimeError, KeyError, TypeError, ValueError):
        if apply:
            raise ToolError(UNKNOWN_OUTCOME) from None
        raise ToolError('ItemResponseUnavailable: check the GM bridge and read_item again.') from None


READ_DOC = """GM-only PF2e Item reader (Foundry >=14.369,<15 and PF2e >=8.6.1,<9).
Default is identity. Reuse the canonical Item UUID from list_actor_items, get_party_stash,
compendium or journal discovery. Preserve token_uuid for placed instances. World/Scene loot
inventory and world-party physical Items qualify. GM source prose can reveal unidentified
treasure. Afflictions (in_scope false) are deferred outside current delivery scope. Book definitions include
marked formula/spell books. Use select.details=["source","description"] for full compendium
action/spell definitions, including requirements, activation, rank, time, range, targets,
defense, damage, heightening, traits and publication where stored. Narrow range with
source.attack. Expand evidence explicitly. Coarse sections is exclusive with select.
Version 2 returns identity/runtime/revision, semantic entries, sections, limitations and
pagination. Returned null and missing are distinct. For a concise complete definition use
limit=100,max_bytes=48000 and continue until complete. DocumentNotFound: rediscover.
PermissionDenied: check GM access. UnsupportedSystem/Version/Type: inspect get_actor_types.
PF2e 8.7.0 on Foundry 14.370: opt into the GM form with sheet={},
sheet.groups or qualified sheet.fields. Explicitly select descriptions for exact text.
records supply source presence/value, transformed display or reason, editability,
one-based rune slots and executable get_item_field_options calls. Follow pagination.next_cursor
with identical target, sheet and bounds. Restart after stale content. Compendiums are read-only."""
OPTIONS_DOC = """GM-only PF2e 8.7.0 / Foundry 14.370. Look up a choice before edit_item.
Use the field ID from read_item(sheet={}), plus one-based slot for property_runes.
proposed_changes evaluates a prospective final configuration. query matches a literal
case-insensitive substring of code or localized label. records give value, label,
availability, including null for a clear. Empty records match no choices for this
query. Free prose, integers and currency have no finite menu. Copy pagination.next_cursor
with identical arguments. On stale content restart without cursor."""
EDIT_DOC = """GM-only on Foundry 14.370 / PF2e 8.7.0. Edit one existing physical Item.
World Items, creature/loot/party inventory and individual unlinked token copies qualify.
Use read_item(sheet={}) for control IDs and get_item_field_options for current choices.
Weapons support Details. Other physical types support name, prose, identification and
quantity except backpack quantity. Plain prose only. Omission preserves siblings.
Preview returns changes, revision and next_call. Apply the same proposal with that
expected_revision. A null property slot clears it. Null persistent damage clears the record.
Re-preview on conflict. On lost acknowledgment read the target before retrying.
Compendiums, linked token aliases, attachments and generated strikes cannot be edited."""
