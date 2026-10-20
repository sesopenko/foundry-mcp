import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, AsyncMock
from fastmcp import Client
from foundry_mcp_server.mcp_server.tools import mcp
from foundry_mcp_server.pdf.config import PDFConfig
from foundry_mcp_server.pdf.library import Library, hash_file
from foundry_mcp_server.pdf import runtime
from foundry_mcp_server import main
from foundry_mcp_server.config import Settings
from fastapi import WebSocketDisconnect
from test_pdf_library import pdf

class ToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_fresh_discovery_grounded_read_and_disabled_denial(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);library=Library(PDFConfig(True,root/'books',root/'state'))
            await library.start();pdf(root/'books'/'Rules.pdf')
            with patch.object(runtime,'library',library):
                async with Client(mcp) as client:
                    catalog={t.name:t for t in await client.list_tools()}
                    for name in ('list_pdf_documents','locate_pdf_entry','search_pdf_documents','read_pdf_pages','refresh_pdf_index'):
                        self.assertGreater(len(catalog[name].description),500)
                        self.assertEqual(catalog[name].inputSchema['type'],'object')
                    result=await client.call_tool('refresh_pdf_index',{})
                    await asyncio.gather(*library.tasks)
                    docs=(await client.call_tool('list_pdf_documents',{})).data
                    identifier=docs['documents'][0]['document_id']
                    candidates=(await client.call_tool('locate_pdf_entry',{'name':'Sure Strike'})).data
                    self.assertEqual(candidates['candidates'][0]['document_id'],identifier)
                    page=(await client.call_tool('read_pdf_pages',{'document_id':identifier,'physical_page':1})).data
                    self.assertIn('Roll twice',page['text']);self.assertEqual(page['name'],'Rules.pdf')
                    invalid=await client.call_tool('read_pdf_pages',{'document_id':'../../secret','physical_page':1},raise_on_error=False)
                    self.assertTrue(invalid.is_error)
                with patch.object(runtime,'library',None):
                    async with Client(mcp) as client:
                        result=await client.call_tool('list_pdf_documents',{},raise_on_error=False)
                        self.assertTrue(result.is_error)
            await library.close()

    async def test_typed_upload_dispatch_and_rpc_are_separate_and_disconnect_cleans(self):
        socket=AsyncMock();manager=AsyncMock();uploads=AsyncMock()
        socket.client.host='127.0.0.1';socket.scope={'scheme':'ws'}
        socket.receive_text.side_effect=[json.dumps({'type':'pdf.upload.authorize','request_id':'1','token':'private'}),json.dumps({'id':'ordinary','result':[]}),WebSocketDisconnect()]
        with patch.object(main,'settings',Settings(development=True,browser_token='browser')),patch.object(main,'foundry_manager',manager),patch.object(main,'pdf_uploads',uploads):
            socket.receive_json.return_value={'token':'browser'}
            await main.foundry_ws(socket)
        uploads.handle.assert_awaited_once()
        manager.handle_incoming.assert_awaited_once_with(json.dumps({'id':'ordinary','result':[]}),socket)
        uploads.disconnect.assert_awaited_once_with(socket)

class ConfigTests(unittest.TestCase):
    def test_requires_authenticated_gm_policy_and_separate_capability(self):
        base={'FOUNDRY_MCP_PDF_ENABLED':'true','FOUNDRY_MCP_PDF_LIBRARY_DIR':'/tmp/books','FOUNDRY_MCP_PDF_INDEX_DIR':'/tmp/state'}
        with patch.dict(os.environ,base,clear=True):
            with self.assertRaises(ValueError): PDFConfig.from_env()
            with patch('foundry_mcp_server.pdf.config.settings',Settings(auth_mode='basic',bridge_token='world')):
                with self.assertRaises(ValueError):PDFConfig.from_env()
                os.environ['FOUNDRY_MCP_PDF_TRUSTED_GM_MCP']='true'
                self.assertTrue(PDFConfig.from_env().enabled)
                os.environ['FOUNDRY_MCP_PDF_UPLOAD_ENABLED']='true'
                os.environ['FOUNDRY_MCP_PDF_UPLOAD_TOKEN']='world'
                with self.assertRaises(ValueError):PDFConfig.from_env()
                os.environ['FOUNDRY_MCP_PDF_UPLOAD_TOKEN']='private'
                self.assertTrue(PDFConfig.from_env().uploads)
