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
    async def test_match_explanations_are_validated_at_mcp_output_boundary(self):
        candidate = dict(document_id='a'*32,name='Synthetic.pdf',revision='r',physical_page=1,
                         page_label='1',warnings=[],match_details={'matched_fields':['invented_field'], 'body_matches_all_terms':False})
        packet = dict(candidates=[candidate],next_offset=None,candidate_cap_reached=False,message='Candidates require verification')
        with patch('foundry_mcp_server.mcp_server.selective.pdfs.run',new=AsyncMock(return_value=packet)):
            async with Client(mcp) as client:
                result = await client.call_tool('search_pdf_documents',{'query':'checkpoint','select':{'match_details':True}},raise_on_error=False)
                self.assertTrue(result.is_error)
                self.assertIn('InvalidFoundryResponse',str(result.content))

    async def test_fresh_discovery_grounded_read_and_disabled_denial(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);library=Library(PDFConfig(True,root/'books',root/'state'))
            await library.start();pdf(root/'books'/'Rules.pdf')
            with patch.object(runtime,'library',library):
                async with Client(mcp) as client:
                    catalog={t.name:t for t in await client.list_tools()}
                    for name in ('list_pdf_documents','locate_pdf_entry','search_pdf_documents','read_pdf_pages','refresh_pdf_index'):
                        self.assertGreater(len(catalog[name].description),500)
                        self.assertEqual(catalog[name].input_schema['type'],'object')
                    result=await client.call_tool('refresh_pdf_index',{})
                    await asyncio.gather(*library.tasks)
                    docs=(await client.call_tool('list_pdf_documents',{})).data
                    identifier=docs['documents'][0]['document_id']
                    schema = catalog['search_pdf_documents'].input_schema
                    self.assertEqual(schema['properties']['search_mode']['enum'], ['contextual','text'])
                    self.assertIn('match_details', schema['$defs']['PdfSearchSelect']['properties'])
                    query = {'query':'Variant Roll', 'document_id': identifier}
                    contextual = (await client.call_tool('search_pdf_documents', query)).structured_content
                    self.assertEqual(contextual['contract_version'], 2)
                    self.assertEqual(len(contextual['candidates']), 1)
                    self.assertNotIn('match_details', contextual['candidates'][0])
                    self.assertEqual((await client.call_tool('search_pdf_documents', dict(query, search_mode='text'))).structured_content['candidates'], [])
                    details = (await client.call_tool('search_pdf_documents', dict(query, select={'match_details':True,'snippet':True}))).structured_content
                    self.assertEqual(details['candidates'][0]['match_details']['matched_fields'], ['body','bookmark_titles'])
                    self.assertNotIn('metadata_excerpt_derived', contextual['candidates'][0])
                    for invalid_args in (dict(query, search_mode='semantic'), dict(query, select={'unknown':True}),
                                         dict(query, select={'context':True}), dict(query, extra=True)):
                        invalid = await client.call_tool('search_pdf_documents', invalid_args, raise_on_error=False)
                        self.assertTrue(invalid.is_error)
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
