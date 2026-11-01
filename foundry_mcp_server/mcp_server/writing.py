"""GM-authoritative writing guidance from public core14 world settings.

No PF2e document interpretation. The bundled user-supplied Pathfinder passage
retains its unverified-publication attribution; GM content is never relabelled
as Paizo copy. Browser save and permission boundary: writingGuidance.js.
"""
import hashlib
from html import escape
import inspect
import json
from datetime import datetime
from typing import Annotated, Literal

from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field, model_validator

from .writing_style import STYLE_GUIDE
from .selective import SelectiveTool, rpc
from .selective_models import Model
from .server import mcp

SavedAt = Annotated[str, Field(pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$', max_length=24)]
Revision = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]


class GuidanceTimestamp(Model):
    saved_at: SavedAt | None = Field(description='GM save time in UTC, null if never configured. Revision must accompany it for reliable change checks.')
    revision: Revision = Field(description='Opaque SHA-256 change marker binding world, exact GM HTML/save time and bundled style copy. Not authorization or a document selector.')


class GuidanceRequest(Model):
    since: GuidanceTimestamp | None = Field(default=None, description='Copy the entire returned timestamp record to check for changes; omit for full guidance. A bare date cannot detect bundled-style changes.')
    max_bytes: int = Field(default=8000, ge=8000, le=48000, description='Maximum compact UTF-8 JSON bytes; raise explicitly for a long configured guide. Content is never truncated.')


class GuidanceSource(Model):
    world_id: str = Field(min_length=1, max_length=128)
    html: str | None
    saved_at: SavedAt | None

    @model_validator(mode='after')
    def valid_source(self):
        if (self.html is None) != (self.saved_at is None):
            raise ValueError('Only never-configured guidance has null HTML and timestamp')
        if self.html is not None and len(self.html.encode('utf-8')) > 12000:
            raise ValueError('GM guidance exceeds its 12000 UTF-8 byte limit')
        if self.saved_at is not None:
            datetime.fromisoformat(self.saved_at)
        return self


class GMGuidance(Model):
    source: Literal['GM-authored instructions']
    html: str | None = Field(description='Exact saved HTML; null when never configured, empty string for a deliberately empty saved guide.')
    importance: Literal['critical']


class PathfinderGuidance(Model):
    source: Literal['User-supplied Pathfinder/Paizo writing conventions']
    html: str
    attribution_status: Literal['user_supplied_publication_unverified']


class GuidanceResult(Model):
    world_id: str
    changed: bool
    timestamp: GuidanceTimestamp
    gm_status: Literal['not_configured', 'empty', 'configured']
    message: str
    gm_guidance: GMGuidance | None = None
    pathfinder_guidance: PathfinderGuidance | None = None

    @model_validator(mode='after')
    def conditional_copy(self):
        if self.changed != (self.gm_guidance is not None and self.pathfinder_guidance is not None):
            raise ValueError('Changed guidance must include both source-labelled sections')
        if not self.changed and {'gm_guidance', 'pathfinder_guidance'} & self.model_fields_set:
            raise ValueError('Unchanged guidance must omit the copy')
        return self


def guidance_revision(source):
    """Hash exact stored authoring instructions and bundled style, not rendered UI."""
    value = [source.world_id, source.html, source.saved_at, STYLE_GUIDE]
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


async def get_writing_guidance(request: GuidanceRequest):
    """Read unified GM and Pathfinder writing guidance before authoring content.

    GM instructions are critically important: follow them before choosing edit
    targets or writing. Obtain explicit GM permission before altering material
    protected by those instructions. This prose is not an automatic folder ACL.
    Requires a ready authenticated GM browser on Foundry14; other systems can
    use core guidance without PF2e semantics. BridgeUnavailable is unavailable
    guidance, never an empty guide. GM edits it under module settings → Edit
    writing guidance; LLM tools cannot change this setting. World settings are
    not a confidential secret store. Use get_journal_tree to locate a destination
    or send_chat_message for explicitly requested chat after reading this guide.

    No selector is needed. Returns world_id,changed,timestamp{saved_at,revision},
    gm_status,message. Changed/full responses additionally contain gm_guidance
    {source,html,importance=critical} and pathfinder_guidance{source,html,
    attribution_status}. GM HTML is exact; the bundled style passage is HTML
    paragraphs with user_supplied_publication_unverified attribution. The page628
    reference belongs to the original passage, not every book. Neither section
    is LLM-authored. Paizo-style prose is distinct from PF2e inline syntax;
    use create_pf2e_inline_check/roll/embed for that syntax when applicable.

    Copy the complete timestamp object into since on later calls. saved_at is
    the GM's UTC save time (null if never saved); revision also binds exact HTML,
    the world and bundled style. A bare save date cannot detect style changes.
    Matching stamps return changed=false and 'No change since supplied timestamp',
    omitting both HTML sections. Different stamps return current full guidance.
    gm_status is not_configured,empty or configured; saved empty differs from
    never configured and from errors. Recheck before later writes; these reads
    are observations, not locks. Never invent permission from unchanged status.

    Default max_bytes=8000, range8000–48000 compact UTF-8 JSON bytes. The configured
    GM guide is limited to12000 UTF-8 HTML bytes. ResponseTooLarge requires raising
    max_bytes to48000; copy is never truncated or paginated. InvalidRequest: use
    the published timestamp/bounds, no unknown inputs. InvalidFoundryResponse:
    update/reload server/module together and have the GM inspect the saved guide;
    do not continue on an assumption that malformed guidance is empty.
    PermissionDenied/NotReady: connect the existing ready GM. UnsupportedVersion:
    use Foundry14. Example: get_writing_guidance({}), then {since:result.timestamp}.
    """
    try:
        source = GuidanceSource.model_validate(await rpc('getWritingGuidance', {}))
    except (ValueError, TypeError):
        raise ToolError('InvalidFoundryResponse: invalid stored writing guidance; inspect module settings and server/module compatibility.') from None
    stamp = GuidanceTimestamp(saved_at=source.saved_at, revision=guidance_revision(source))
    changed = request.since != stamp
    result = dict(world_id=source.world_id, changed=changed, timestamp=stamp.model_dump(),
        gm_status='not_configured' if source.html is None else 'empty' if not source.html else 'configured',
        message='GM instructions are critically important; follow them and obtain required GM permission before editing protected content.' if changed else 'No change since supplied timestamp.')
    if changed:
        result['gm_guidance'] = dict(source='GM-authored instructions', html=source.html, importance='critical')
        result['pathfinder_guidance'] = dict(source='User-supplied Pathfinder/Paizo writing conventions',
            html='\n'.join('<p>' + escape(paragraph, quote=False) + '</p>' for paragraph in STYLE_GUIDE.split('\n\n')),
            attribution_status='user_supplied_publication_unverified')
    return result


mcp.add_tool(SelectiveTool(name='get_writing_guidance', description=inspect.cleandoc(get_writing_guidance.__doc__),
    parameters=GuidanceRequest.model_json_schema(), output_schema=GuidanceResult.model_json_schema(),
    request_model=GuidanceRequest, response_model=GuidanceResult, handler=get_writing_guidance,
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)))
