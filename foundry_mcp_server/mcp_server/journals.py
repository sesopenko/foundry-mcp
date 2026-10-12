"""Self-documenting, read-only world-journal tools; state stays in Foundry."""
import asyncio
import json
from typing import Annotated, Any, Literal

from fastmcp.exceptions import ToolError
from pydantic import Field

from .server import mcp
from foundry_mcp_server.ws.connection import RpcError

Identifier = Annotated[str, Field(min_length=1, max_length=512)]
Cursor = Annotated[str, Field(min_length=1, max_length=4096)]
ListLimit = Annotated[int, Field(ge=1, le=50, strict=True)]


async def _call(method: str, params: dict[str, Any], field: str) -> dict[str, Any]:
    from . import tools

    try:
        result = await tools._foundry_manager.call("gm", method, params, timeout=15.0)
    except RpcError as exc:
        raise ToolError(f"{exc.error.get('type', 'FoundryError')}: {exc.error.get('message', 'Foundry call failed')}") from exc
    except asyncio.TimeoutError as exc:
        raise ToolError("FoundryTimeout: retry after the GM browser is responsive.") from exc
    except ConnectionError as exc:
        raise ToolError("FoundryDisconnected: reconnect the GM browser and retry.") from exc
    except RuntimeError as exc:
        raise ToolError("NoConnectedGM: open the world in the connected GM browser and retry.") from exc

    # Enforce the RPC contract before exposing browser output to MCP callers.
    if not isinstance(result, dict):
        raise ToolError("InvalidFoundryResponse: expected a journal result object.")
    valid = (
        isinstance(result.get("foundry_version"), str)
        and isinstance(result.get("revision"), str)
        and type(result.get("complete")) is bool
        and "next_cursor" in result
        and (result["next_cursor"] is None or isinstance(result["next_cursor"], str))
        and isinstance(result.get(field), str if field == "content" else list)
        and result["complete"] == (result["next_cursor"] is None)
    )
    if field != "content":
        valid = valid and type(result.get("total")) is int and result["total"] >= 0
        valid = valid and isinstance(result.get(field), list) and all(isinstance(row, dict) for row in result[field])
    else:
        valid = valid and all(type(result.get(key)) is int for key in ("offset", "end_offset", "total_chars"))
        if valid:
            valid = 0 <= result["offset"] <= result["end_offset"] <= result["total_chars"]
    try:
        valid = valid and len(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")) <= 48000
    except (TypeError, UnicodeError, ValueError):
        valid = False
    if not valid:
        raise ToolError("InvalidFoundryResponse: malformed or oversized journal result.")
    return result


@mcp.tool
async def get_journal_tree(
    folder_id: Identifier | None = None,
    max_depth: Annotated[int, Field(ge=0, le=8, strict=True)] = 3,
    limit: Annotated[int, Field(ge=1, le=100, strict=True)] = 50,
    cursor: Cursor | None = None,
) -> dict[str, Any]:
    """Discover world journals as nested folders, subfolders, and entry summaries.

    Requires a ready connected GM browser; includes GM-only world journals,
    excludes compendiums. Start with get_journal_tree() at the directory root,
    including unfiled entries. folder_id is an opaque ID from a returned folder
    node, not its name/path. max_depth (default 3, 0..8) controls folder expansion;
    limit (default 50, 1..100) bounds immediate children per response. Output is
    also bounded to 48,000 UTF-8 JSON bytes and 100 expanded descendant nodes.

    Returns folder_path, folder_id, children, total immediate child count,
    revision, complete, tree_complete, next_cursor, and foundry_version.
    children are nested kind=folder or kind=journal nodes with names and stable
    folder_id/journal_id selectors. Folder nodes have children, child_count,
    complete, and expand; use expand.folder_id in a NEW call without cursor to
    expand a collapsed/partial branch. Journal nodes include journal_uuid and
    text/non_text_page_count. Names longer than 256 characters are marked
    name_truncated; identifiers remain intact. Core sorting is represented;
    publisher-specific sheet styling/numbering is not reproduced.

    complete means all immediate children were returned; tree_complete also
    requires descendants to be expanded. When next_cursor is non-null, pass it
    unchanged with the same folder_id and max_depth to fetch remaining immediate
    children. An empty folder has child_count=0, not an unexpanded branch.
    Use journal_id with get_journal_contents to inspect an entry's page outline.
    For a known name/phrase, search_journals can search globally immediately.
    FolderNotFound: refresh root navigation. ContentChanged/InvalidCursor:
    restart without cursor. FoundryNotReady/NoConnectedGM: connect/wait and retry.
    """
    return await _call("getJournalTree", dict(folder_id=folder_id, max_depth=max_depth, limit=limit, cursor=cursor), "children")


@mcp.tool
async def get_journal_contents(
    journal_id: Identifier,
    page_id: Identifier | None = None,
    categories_only: Annotated[bool, Field(strict=True)] = False,
    limit: ListLimit = 20,
    cursor: Cursor | None = None,
) -> dict[str, Any]:
    """Inspect a world journal's ordered pages, categories, and heading outlines.

    Requires the connected ready GM world. Supply journal_id from get_journal_tree
    or search_journals, not a name or UUID. Normally omit page_id to list pages.
    limit defaults to 20 (1..50); responses also stop at 48,000 UTF-8 JSON bytes.

    Returns source name, journal_id/journal_uuid, folder_path, mode, revision,
    total, complete, next_cursor, foundry_version. mode=pages includes ordered
    pages and groups (category labels with page_uuids pointing to this response's
    pages). Each page has page_id/page_uuid, name, type, readable, title_level,
    title_show, category, sort, and heading_outline. Heading records include
    anchor, name, level, parent_anchor, ancestor_anchors; these are sections in
    the page, not documents or child pages. First 20 headings per page are shown;
    headings_complete and headings_next_call make omitted headings explicit.
    Use headings_next_call.journal_id/page_id in a NEW call without cursor to
    enumerate that page's headings (mode=headings, heading_outline, total).
    groups_complete/category_count flag category labels not included in this
    response; use categories_next_call in a NEW call without cursor to list
    every category, including empty ones. That call sets categories_only=true
    (mode=categories, groups with category_id/name/sort/page_count). Never combine
    categories_only with page_id. No source content is returned in any mode.

    Follow next_cursor unchanged with the same journal_id/page_id/categories_only
    until complete; complete concerns only the current mode's pagination.
    Category groups may span response pages. Media pages are listed readable=false;
    no bodies are returned. Names over 256 characters have name_truncated=true.
    An empty entry is valid. Use a text page's full page_uuid with read_journal_page.
    JournalNotFound/PageNotFound: refresh navigation. ContentChanged/InvalidCursor:
    restart without cursor. Unsupported media is never fetched or interpreted.
    """
    if categories_only and page_id is not None:
        raise ToolError("InvalidParameters: categories_only cannot be combined with page_id.")
    return await _call("getJournalContents", dict(journal_id=journal_id, page_id=page_id, categories_only=categories_only, limit=limit, cursor=cursor),
                       "groups" if categories_only else "heading_outline" if page_id is not None else "pages")


@mcp.tool
async def search_journals(
    query: Annotated[str, Field(min_length=1, max_length=512)],
    folder_id: Identifier | None = None,
    journal_id: Identifier | None = None,
    limit: ListLimit = 20,
    cursor: Cursor | None = None,
) -> dict[str, Any]:
    """Find text pages by a literal case-insensitive phrase, not a semantic question.

    Requires a connected ready GM world; includes GM-only text, excludes
    compendiums/media. Example: search_journals(query="Ripnugget") or query="E1".
    With no scope search every world journal. Supply folder_id from get_journal_tree
    to include descendants OR journal_id from navigation/search to restrict one
    entry; never both. IDs are opaque, not names/paths. Query whitespace is
    normalized; matching covers page names and derived HTML text/link labels,
    not HTML attributes, image filenames, UUID IDs, or regexes.

    Returns matches (one per page), total matching pages, searched_text_pages,
    scope, revision, complete, next_cursor, foundry_version. Each match includes
    journal_id/name, page_id/name/page_uuid, folder_path, matched_fields,
    text_match_count, up to three excerpts, excerpts_complete, excerpts_derived.
    Excerpts are derived search context, not stored HTML or source offsets.
    Names are bounded with explicit *_truncated flags. Order is stable by entry
    name and page order, not semantic relevance. limit defaults to 20 (1..50);
    output also stops at 48,000 UTF-8 JSON bytes. Follow next_cursor unchanged
    with the same query and scope to retrieve remaining matching pages.

    Read full source using each match's page_uuid with read_journal_page. Empty
    matches only mean this literal query found no text in this scope; broaden
    scope or try alternate wording before concluding facts are absent. Partial
    results cannot establish exhaustive coverage. InvalidParameters: choose one
    scope/nonblank query. ContentChanged/InvalidCursor: restart without cursor.
    Missing scope documents: refresh get_journal_tree/get_journal_contents.
    """
    if not query.strip() or (folder_id is not None and journal_id is not None):
        raise ToolError("InvalidParameters: provide a nonblank query and at most one folder_id or journal_id.")
    return await _call("searchJournals", dict(query=query, folder_id=folder_id, journal_id=journal_id, limit=limit, cursor=cursor), "matches")


@mcp.tool
async def read_journal_page(
    page_uuid: Identifier,
    source: Literal["html", "markdown"] = "html",
    max_chars: Annotated[int, Field(ge=1, le=20000, strict=True)] = 12000,
    cursor: Cursor | None = None,
) -> dict[str, Any]:
    """Read exact stored HTML or original Markdown from a world journal text page.

    Use page_uuid returned by get_journal_contents/search_journals, e.g.
    JournalEntry.<entry-id>.JournalEntryPage.<page-id>. Bare IDs, entry UUIDs,
    names, paths, heading anchors and compendium UUIDs are not accepted.
    Requires a connected ready GM browser; includes GM-only text. Images/maps,
    PDFs, video are unsupported. No content is enriched, executed, or fetched.

    source defaults to html: content is an exact substring of page.text.content,
    preserving markup, attributes, entities, whitespace and Foundry notation.
    source=markdown reads page.text.markdown when stored. available_sources tells
    which sources exist; stored_format is Foundry's editor format (1=HTML,
    2=Markdown) and differs from the selected source. Missing HTML is reported
    source_present=false with empty content, distinct from a missing document.

    Returns source names/IDs, folder_path, content, source, stored_format,
    available_sources, source_present, offset/end_offset, total_chars,
    offset_units, fragment, revision, complete, next_cursor, foundry_version.
    references lists up to 20 complete UUID references within this chunk,
    references_complete flags omitted metadata; original notation stays in content.
    For resolved world links use reference.journal_id with get_journal_contents
    or reference.page_uuid with read_journal_page. anchor is a section within
    that page, not part of the read selector. Relative links resolve against
    this source page. Unresolved and non-journal targets are marked explicitly;
    split notation may only be visible after concatenating adjacent chunks.
    max_chars defaults to 12000 (1..20000 UTF-16 units); Unicode pairs stay
    intact, so a one-unit limit may yield two units. Output also stops at 48,000
    UTF-8 JSON bytes. Fragments may contain incomplete HTML elements; nothing
    is rewritten or wrapped. Concatenate chunks to reproduce the exact source.

    Pass next_cursor unchanged with the same page_uuid/source until complete;
    positions/revision are encoded in it, so do not calculate offsets. Each
    source has its own cursor. ContentChanged/InvalidCursor: restart without
    cursor. SourceUnavailable: use source=html. Missing entry/page: refresh
    contents/search. UnsupportedPageType: select a readable text page.
    Cite journal_name/page_name when answering; IDs support subsequent calls.
    """
    return await _call("readJournalPage", dict(page_uuid=page_uuid, source=source, max_chars=max_chars, cursor=cursor), "content")
