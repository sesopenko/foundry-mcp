"""Opt-in MCP records; never invokes a model or logs source bodies/credentials."""
import asyncio
import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import Middleware
from mcp.types import CallToolResult

logger = logging.getLogger("foundry_mcp.evaluation")
SAFE_ARGUMENTS = {
    "get_journal_tree": {"folder_id", "max_depth", "limit", "cursor"},
    "get_journal_contents": {"journal_id", "page_id", "categories_only", "limit", "cursor"},
    "search_journals": {"query", "folder_id", "journal_id", "limit", "cursor"},
    "read_journal_page": {"page_uuid", "source", "max_chars", "cursor"},
}


def encoded(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True, default=str).encode()


def fingerprint(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def arguments_for_log(tool, arguments):
    result = {}
    for key, value in list((arguments or {}).items())[:64]:
        if key in SAFE_ARGUMENTS.get(tool, set()) and (value is None or type(value) in (str, int, float, bool)):
            result[key] = value if not isinstance(value, str) or len(value) <= 4096 else {
                "preview": value[:4096], "truncated": True, "sha256": fingerprint(value)}
        else:
            result[str(key)[:128]] = {"redacted": True, "sha256": fingerprint(value)}
    return result


def label(value):
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value) else None


def correlation(context):
    ctx = context.fastmcp_context
    meta = {}
    session = request_id = None
    if ctx is not None:
        try:
            request = ctx.request_context
            if request is not None:
                meta = request.meta.model_dump() if request.meta is not None else {}
                request_id = str(ctx.request_id)[:128]
                session = fingerprint(ctx.session_id)
        except RuntimeError:
            pass
    headers = get_http_headers()
    tags = meta.get("evaluation", {})
    if not isinstance(tags, dict):
        tags = {}
    return {"run_id": label(tags.get("run_id")) or label(headers.get("x-foundry-eval-run")),
            "task_id": label(tags.get("task_id")) or label(headers.get("x-foundry-eval-task")),
            "attempt_id": label(tags.get("attempt_id")) or label(headers.get("x-foundry-eval-attempt")),
            "client_session_sha256": session, "mcp_request_id": request_id}


class TraceRecorder:
    """Private JSONL; 5 MB current file and two rotated files."""
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.instance_id = str(uuid4())
        self.sequence = self.write_failures = 0
        self.max_bytes = 5_000_000
        self._append(b"")  # Explicitly enabled but unwritable: fail startup.
        self.emit({"event": "trace_started"})

    def _append(self, data):
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(self.path, flags, 0o600)
        try:
            os.fchmod(fd, 0o600)
            if os.fstat(fd).st_size + len(data) > self.max_bytes:
                os.close(fd)
                fd = None
                previous = Path(str(self.path) + ".1")
                if previous.exists():
                    os.replace(previous, str(self.path) + ".2")
                os.replace(self.path, previous)
                fd = os.open(self.path, flags, 0o600)
            view = memoryview(data)
            while view:
                written = os.write(fd, view)
                if written == 0:
                    raise OSError("Trace write made no progress")
                view = view[written:]
        finally:
            if fd is not None:
                os.close(fd)

    def emit(self, record):
        self.sequence += 1
        record = {"schema_version": 1, "instance_id": self.instance_id, "sequence": self.sequence,
                  "timestamp": datetime.now(timezone.utc).isoformat(), "write_failures": self.write_failures, **record}
        try:
            self._append(encoded(record) + b"\n")
        except OSError:
            self.write_failures += 1
            logger.error("Evaluation trace write failed; records may be incomplete (failures=%d)", self.write_failures)


def result_metrics(result):
    data = result.structured_content
    payload = CallToolResult(content=result.content, structuredContent=data, _meta=result.meta)
    size = lambda value: len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())
    metrics = {"response_payload_bytes": len(payload.model_dump_json(by_alias=True, exclude_none=True).encode()),
               "structured_bytes": size(data) if data is not None else None}
    if isinstance(data, dict):
        for key in ("foundry_version", "complete", "tree_complete", "total", "searched_text_pages",
                    "offset", "end_offset", "total_chars", "source", "source_present", "revision"):
            value = data.get(key)
            if value is not None and type(value) in (str, int, bool):
                metrics[key] = value[:128] if isinstance(value, str) else value
        metrics["has_next_cursor"] = bool(data.get("next_cursor"))
        for key in ("matches", "pages", "children", "heading_outline", "groups"):
            if isinstance(data.get(key), list):
                metrics["returned_" + key] = len(data[key])
        if isinstance(data.get("content"), str):
            metrics["source_utf16_units"] = len(data["content"].encode("utf-16-le", errors="surrogatepass")) // 2
    return metrics


class EvaluationMiddleware(Middleware):
    def __init__(self, recorder):
        self.recorder = recorder

    async def on_list_tools(self, context, call_next):
        result = await call_next(context)
        catalog = [tool.to_mcp_tool().model_dump(mode="json", by_alias=True, exclude_none=True) for tool in result]
        self.recorder.emit({"event": "discovery", **correlation(context), "catalog_sha256": fingerprint(catalog), "tools": catalog})
        return result

    async def on_call_tool(self, context, call_next):
        tool = context.message.name
        arguments = context.message.arguments or {}
        call = {"call_id": str(uuid4()), "tool": tool[:128], **correlation(context), "arguments_sha256": fingerprint(arguments)}
        self.recorder.emit({"event": "call_started", **call, "arguments": arguments_for_log(tool, arguments)})
        started = time.perf_counter()
        outcome, code, metrics = "error", None, {}
        try:
            result = await call_next(context)
            outcome = "success"
            try:
                metrics = result_metrics(result)
            except (AttributeError, TypeError, ValueError, UnicodeError):
                metrics = {"metrics_error": "ResultMetricsUnavailable"}
            return result
        except asyncio.CancelledError:
            outcome, code = "cancelled", "CancelledError"
            raise
        except Exception as exc:
            prefix = str(exc).split(":", 1)[0]
            code = prefix if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", prefix) else type(exc).__name__
            raise
        finally:
            self.recorder.emit({"event": "call_finished", **call, "outcome": outcome, "error_code": code,
                                "duration_ms": round((time.perf_counter() - started) * 1000, 3), **metrics})
