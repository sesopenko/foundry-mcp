"""Actual MCP discovery must describe delivered scoped readers without stale gates."""
import unittest
from fastmcp import Client
from foundry_mcp_server.mcp_server.server import mcp
import foundry_mcp_server.mcp_server.actors  # Register the actual tools.


class ActorInterfaceContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovery_book_and_inventory_contracts_match_delivered_scope(self):
        async with Client(mcp) as client:
            tools={tool.name:tool for tool in await client.list_tools()}
        item=tools['read_item'].description
        actor=tools['read_actor'].description
        for stale in ('representative live book fixtures are unavailable','Source remains partial until its concrete type story is delivered'):
            self.assertNotIn(stale,item)
        self.assertIn('marked formula/spell books',item)
        self.assertIn('DocumentNotFound',item)
        self.assertNotIn('books expose common physical fields with specialty pending',actor)
        self.assertIn('read_item source/relationships',actor)
        self.assertIn('deferred outside current delivery scope',item)
