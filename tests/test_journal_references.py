"""Selected lazy reference boundary and actual MCP discovery contracts."""
import asyncio
import copy
import unittest
from unittest.mock import AsyncMock

from fastmcp import Client
from fastmcp.exceptions import ToolError

from foundry_mcp_server.mcp_server.journals import resolve_journal_reference
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from foundry_mcp_server.ws.connection import RpcError


class JournalReferenceTests(unittest.IsolatedAsyncioTestCase):
    page = "JournalEntry.j.JournalEntryPage.p"
    target = "Actor.a#heading#suffix"

    async def asyncSetUp(self):
        self.manager = AsyncMock()
        register_foundry_manager(self.manager)

    def response(self, document="Actor", token=False):
        identity = dict(document_name=document, id="a", uuid="Actor.a", name="A",
                        type="npc" if document == "Actor" else "action",
                        source_kind="token" if token else "world", folder=None,
                        pack=None, actor=None, instance=None)
        if document == "Item":
            identity["uuid"] = "Actor.a.Item.i"
        if token:
            identity["instance"] = dict(scene_uuid="Scene.s", scene_name="S",
                token_uuid="Scene.s.Token.t", token_name="T", actor_link=False, base_actor=None)
        arguments = {"actor_uuid" if document == "Actor" else "item_uuid": identity["uuid"]}
        if token:
            if document == "Actor":
                arguments = {}
            arguments["token_uuid"] = "Scene.s.Token.t"
        return dict(foundry_version="14.369", page_uuid=self.page, source="html",
                    target=self.target, anchor="heading#suffix", status="resolved",
                    identity=identity, next_call=dict(tool="read_actor" if document == "Actor" else "read_item", arguments=arguments))

    async def invoke(self, result):
        self.manager.call.return_value = result
        return await resolve_journal_reference(page_uuid=self.page, target=self.target)

    async def test_world_pack_item_and_token_selectors(self):
        for document in ("Actor", "Item"):
            for token in (False, True):
                with self.subTest(document=document, token=token):
                    result = self.response(document, token)
                    self.assertEqual(await self.invoke(result), result)
        result = self.response()
        result["identity"].update(source_kind="compendium", uuid="Compendium.p.a.Actor.a", pack={"id": "p.a", "title": "Pack"})
        result["next_call"]["arguments"] = {"actor_uuid": "Compendium.p.a.Actor.a"}
        self.assertEqual(await self.invoke(result), result)
        self.manager.call.assert_awaited_with("gm", "resolveJournalReference", dict(page_uuid=self.page, source="html", target=self.target), timeout=15.0)

    async def test_explicit_unresolved_statuses(self):
        for status in ("missing", "denied", "unsupported", "outside_scope", "unverified"):
            result = self.response()
            result.update(status=status, identity=None, next_call=None)
            self.assertEqual(await self.invoke(result), result)

    async def test_rejects_malformed_forged_and_unsupported_results(self):
        changes = [dict(extra=1), dict(page_uuid="other"), dict(source="markdown"),
                   dict(target="Actor.other"), dict(anchor="heading"), dict(status="unknown"),
                   dict(identity=None), dict(next_call={"tool": "read_actor", "arguments": {"actor_uuid": "Actor.other"}}),
                   dict(status="denied"), dict(foundry_version=float("nan"))]
        for change in changes:
            result = self.response()
            result.update(change)
            with self.subTest(change=change), self.assertRaisesRegex(ToolError, "InvalidFoundryResponse"):
                await self.invoke(result)
        for kind in ("hazard", "vehicle", "unknown"):
            result = self.response()
            result["identity"]["type"] = kind
            with self.assertRaises(ToolError):
                await self.invoke(result)
        oversized = self.response()
        oversized["identity"]["name"] = "x" * 49000
        with self.assertRaises(ToolError):
            await self.invoke(oversized)
        for result in (None, [], {}, {**self.response(), "identity": {"name": "x" * 49000}}):
            with self.assertRaises(ToolError):
                await self.invoke(result)
        result = copy.deepcopy(self.response("Item"))
        result["identity"]["type"] = "affliction"
        with self.assertRaises(ToolError):
            await self.invoke(result)
        result = self.response()
        result["identity"]["document_name"] = "JournalEntry"
        with self.assertRaises(ToolError):
            await self.invoke(result)

    async def test_anchor_and_markdown_echo(self):
        for target, anchor in (("Actor.a", None), ("Actor.a#", None)):
            result = self.response()
            result.update(target=target, anchor=anchor, source="markdown")
            self.manager.call.return_value = result
            self.assertEqual(await resolve_journal_reference(
                page_uuid=self.page, target=target, source="markdown"), result)

    async def test_transport_and_origin_errors(self):
        for error, expected in [(asyncio.TimeoutError(), "FoundryTimeout"),
                (ConnectionError(), "FoundryDisconnected"), (RuntimeError(), "NoConnectedGM"),
                (RpcError({"type": "ReferenceChanged", "message": "Reread origin"}), "ReferenceChanged: Reread origin")]:
            self.manager.call.side_effect = error
            with self.assertRaisesRegex(ToolError, expected):
                await resolve_journal_reference(page_uuid=self.page, target=self.target)

    async def test_discovery_and_schema(self):
        async with Client(mcp) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            tool = tools["resolve_journal_reference"]
            self.assertTrue(tool.annotations.readOnlyHint)
            self.assertFalse(tool.annotations.destructiveHint)
            self.assertEqual(tool.inputSchema["required"], ["page_uuid", "target"])
            self.assertEqual(tool.inputSchema["properties"]["source"]["default"], "html")
            self.assertEqual(tool.inputSchema["properties"]["source"]["enum"], ["html", "markdown"])
            for name in ("page_uuid", "target"):
                self.assertEqual(tool.inputSchema["properties"][name]["maxLength"], 512)
            for word in ("GM", "ReferenceChanged", "outside_scope", "read_actor", "read_item", "PF2e-specific", "next_call"):
                self.assertIn(word, tool.description)
            self.assertIn("resolve_next_call", tools["read_journal_page"].description)
            self.manager.call.return_value = self.response()
            self.assertFalse((await client.call_tool("resolve_journal_reference", dict(page_uuid=self.page, target=self.target))).is_error)
            for arguments in (dict(page_uuid=self.page, target=""), dict(page_uuid=self.page, target="x" * 513), dict(page_uuid=self.page, target=self.target, source="pdf")):
                self.assertTrue((await client.call_tool("resolve_journal_reference", arguments, raise_on_error=False)).is_error)
