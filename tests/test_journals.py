import asyncio
import unittest
from unittest.mock import AsyncMock

from fastmcp import Client
from fastmcp.exceptions import ToolError

from foundry_mcp_server.mcp_server.journals import (
    get_journal_tree, get_journal_contents, search_journals, read_journal_page,
)
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from foundry_mcp_server.ws.connection import RpcError


class JournalToolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager = AsyncMock()
        register_foundry_manager(self.manager)

    def response(self, field):
        result = dict(foundry_version="14.369", revision="abc", complete=True, next_cursor=None)
        if field == "content":
            result.update(content='<p class="x"> &amp; </p>', offset=0, end_offset=24, total_chars=24)
        else:
            result.update({field: [], "total": 0})
        return result

    async def test_rpc_contracts_and_exact_html_result(self):
        cases = [
            (get_journal_tree, {}, "getJournalTree", "children", dict(folder_id=None, max_depth=3, limit=50, cursor=None)),
            (get_journal_contents, {"journal_id": "j"}, "getJournalContents", "pages", dict(journal_id="j", page_id=None, categories_only=False, limit=20, cursor=None)),
            (get_journal_contents, {"journal_id": "j", "page_id": "p"}, "getJournalContents", "heading_outline", dict(journal_id="j", page_id="p", categories_only=False, limit=20, cursor=None)),
            (get_journal_contents, {"journal_id": "j", "categories_only": True}, "getJournalContents", "groups", dict(journal_id="j", page_id=None, categories_only=True, limit=20, cursor=None)),
            (search_journals, {"query": "Ripnugget"}, "searchJournals", "matches", dict(query="Ripnugget", folder_id=None, journal_id=None, limit=20, cursor=None)),
            (read_journal_page, {"page_uuid": "JournalEntry.j.JournalEntryPage.p"}, "readJournalPage", "content", dict(page_uuid="JournalEntry.j.JournalEntryPage.p", source="html", max_chars=12000, cursor=None)),
        ]
        for tool, arguments, method, field, params in cases:
            with self.subTest(method=method, arguments=arguments):
                self.manager.reset_mock()
                result = self.response(field)
                self.manager.call.return_value = result
                self.assertEqual(await tool(**arguments), result)
                self.manager.call.assert_awaited_once_with("gm", method, params, timeout=15.0)

    async def test_transport_and_browser_errors_are_actionable(self):
        for error, message in [
            (asyncio.TimeoutError(), "FoundryTimeout"),
            (ConnectionError(), "FoundryDisconnected"),
            (RuntimeError(), "NoConnectedGM"),
            (RpcError({"type": "ContentChanged", "message": "Restart without cursor"}), "ContentChanged: Restart without cursor"),
        ]:
            with self.subTest(message=message):
                self.manager.call.side_effect = error
                with self.assertRaisesRegex(ToolError, message):
                    await get_journal_tree()

    async def test_invalid_responses_and_conflicting_search_scope(self):
        for response in [None, [], {}, {**self.response("children"), "complete": "true"},
                         {**self.response("children"), "children": ["bad"]},
                         {**self.response("children"), "next_cursor": "cursor"},
                         {**self.response("children"), "extra": "x" * 50000}]:
            with self.subTest(response_type=type(response)):
                self.manager.call.return_value = response
                with self.assertRaises(ToolError):
                    await get_journal_tree()
        with self.assertRaisesRegex(ToolError, "at most one"):
            await search_journals(query="x", folder_id="f", journal_id="j")
        with self.assertRaisesRegex(ToolError, "nonblank"):
            await search_journals(query=" ")

    async def test_fresh_client_discovery_and_schema_validation(self):
        async with Client(mcp) as client:
            discovered = {tool.name: tool for tool in await client.list_tools()}
            for name in ["get_journal_tree", "get_journal_contents", "search_journals", "read_journal_page"]:
                tool = discovered[name]
                self.assertIn("cursor", tool.inputSchema["properties"])
                self.assertIn("next_cursor", tool.description)
                self.assertIn("GM", tool.description)
                self.assertIsNotNone(tool.annotations, name)
                self.assertTrue(tool.annotations.readOnlyHint, name)
                self.assertFalse(tool.annotations.destructiveHint, name)
            schema = discovered["read_journal_page"].inputSchema
            self.assertEqual(schema["required"], ["page_uuid"])
            self.assertEqual(schema["properties"]["source"]["enum"], ["html", "markdown"])
            self.assertEqual(schema["properties"]["max_chars"]["maximum"], 20000)
            self.assertEqual(discovered["get_journal_tree"].inputSchema["properties"]["max_depth"]["default"], 3)

            self.manager.call.return_value = self.response("children")
            await client.call_tool("get_journal_tree", {})
            for parameters in [{"limit": 0}, {"max_depth": 9}, {"limit": True}]:
                with self.subTest(parameters=parameters):
                    result = await client.call_tool("get_journal_tree", parameters, raise_on_error=False)
                    self.assertTrue(result.is_error)
            result = await client.call_tool("read_journal_page", {"page_uuid": "x", "source": "pdf"}, raise_on_error=False)
            self.assertTrue(result.is_error)
