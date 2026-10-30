import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastmcp import Client, FastMCP
from fastmcp.server.middleware import MiddlewareContext
from fastmcp.tools import ToolResult
from mcp.types import CallToolRequestParams

from foundry_mcp_server.config import Settings
from foundry_mcp_server.evaluation import EvaluationMiddleware, TraceRecorder
from foundry_mcp_server.evaluation_stats import summarize


class EvaluationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "trace.jsonl"
        self.recorder = TraceRecorder(self.path)
        self.middleware = EvaluationMiddleware(self.recorder)

    def records(self):
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    async def test_discovery_real_calls_tags_validation_and_unknown_tools(self):
        server = FastMCP("evaluation-test")
        server.add_middleware(self.middleware)

        @server.tool
        def search_journals(query: str, limit: int = 20):
            return {"matches": [], "total": 0, "complete": False, "next_cursor": "cursor", "foundry_version": "14.369"}

        meta = {"evaluation": {"run_id": "baseline", "task_id": "lookup", "attempt_id": "1"}}
        async with Client(server) as client:
            await client.list_tools()
            result = await client.call_tool("search_journals", {"query": "Ripnugget"}, meta=meta)
            self.assertFalse(result.is_error)
            bad = await client.call_tool("search_journals", {"query": "x", "limit": "invalid"}, meta=meta, raise_on_error=False)
            self.assertTrue(bad.is_error)
            missing = await client.call_tool("missing", {}, meta=meta, raise_on_error=False)
            self.assertTrue(missing.is_error)
        records = self.records()
        discovery = next(r for r in records if r["event"] == "discovery")
        self.assertEqual(discovery["tools"][0]["name"], "search_journals")
        starts = [r for r in records if r["event"] == "call_started"]
        ends = [r for r in records if r["event"] == "call_finished"]
        self.assertEqual(len(starts), 3)
        self.assertEqual(len(ends), 3)
        self.assertEqual(starts[0]["task_id"], "lookup")
        self.assertEqual(starts[0]["arguments"]["query"], "Ripnugget")
        self.assertIsNotNone(starts[0]["client_session_sha256"])
        self.assertEqual(ends[0]["foundry_version"], "14.369")
        self.assertEqual(ends[0]["returned_matches"], 0)
        self.assertEqual(ends[0]["has_next_cursor"], True)
        self.assertGreater(ends[0]["response_payload_bytes"], ends[0]["structured_bytes"])
        self.assertEqual([r["outcome"] for r in ends], ["success", "error", "error"])
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)

    async def test_header_tags_and_redaction_do_not_change_results(self):
        context = MiddlewareContext(message=CallToolRequestParams(name="execute_javascript", arguments={
            "code": "private source body", "password": "credential", "token": "credential"}))
        result = ToolResult(structured_content={"content": "private journal body 😀", "complete": True})

        async def next_call(ctx):
            return result

        with patch("foundry_mcp_server.evaluation.get_http_headers", return_value={
            "authorization": "Bearer secret", "x-foundry-eval-run": "candidate", "x-foundry-eval-task": "case-1"}):
            self.assertIs(await self.middleware.on_call_tool(context, next_call), result)
        raw = self.path.read_text()
        for secret in ["private source body", "private journal body", "credential", "Bearer secret"]:
            self.assertNotIn(secret, raw)
        self.assertEqual(self.records()[-1]["source_utf16_units"], 23)
        self.assertEqual(self.records()[-1]["run_id"], "candidate")

    async def test_concurrency_cancellation_and_summary_counts(self):
        async def slow(ctx):
            await asyncio.sleep(0.005)
            return ToolResult(structured_content={"complete": True, "content": "abc"})

        context = MiddlewareContext(message=CallToolRequestParams(name="read_journal_page", arguments={"page_uuid": "JournalEntry.j.JournalEntryPage.p"}))
        await asyncio.gather(*(self.middleware.on_call_tool(context, slow) for _ in range(2)))
        task = asyncio.create_task(self.middleware.on_call_tool(context, slow))
        await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        report = summarize(self.records(), include_calls=True)["runs"][0]
        self.assertEqual(report["started_calls"], 3)
        self.assertEqual(report["finished_calls"], 3)
        self.assertEqual(report["repeated_argument_calls"], 2)
        self.assertEqual(report["outcomes"], {"success": 2, "cancelled": 1})
        self.assertEqual(len(report["calls"]), 3)
        incomplete = summarize(self.records()[:-1])
        self.assertEqual(incomplete["runs"][0]["incomplete_calls"], 1)
        self.assertEqual(summarize(self.records() * 2)["runs"][0]["started_calls"], 3)

    async def test_write_failure_does_not_change_tool_result_and_is_reported(self):
        context = MiddlewareContext(message=CallToolRequestParams(name="get_journal_tree", arguments={}))
        result = ToolResult(structured_content={"children": [], "complete": True})

        async def next_call(ctx):
            return result

        with patch.object(self.recorder, "_append", side_effect=OSError("private filesystem details")), self.assertLogs("foundry_mcp.evaluation", level="ERROR") as logs:
            self.assertIs(await self.middleware.on_call_tool(context, next_call), result)
        self.assertEqual(self.recorder.write_failures, 2)
        self.assertNotIn("private filesystem details", " ".join(logs.output))
        self.recorder.emit({"event": "test"})
        self.assertTrue(summarize(self.records())["warnings"])

    def test_default_disabled_configuration_and_rotation(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(Settings.from_env().trace_path)
            os.environ["FOUNDRY_MCP_TRACE_PATH"] = str(self.path)
            self.assertEqual(Settings.from_env().trace_path, str(self.path))
        self.recorder.max_bytes = 600
        for i in range(5):
            self.recorder.emit({"event": "test", "value": "x" * 100})
        self.assertTrue(Path(str(self.path) + ".1").exists())
        self.assertTrue(Path(str(self.path) + ".2").exists())
        self.assertTrue(summarize(self.records())["warnings"])
