"""Capture actual diagnostics without printing fixture capabilities on failure."""
from io import StringIO
import asyncio
import json
import logging
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch
import uuid

from fastmcp.server.middleware import MiddlewareContext
from fastmcp.tools import ToolResult
from mcp.types import CallToolRequestParams
from uvicorn.logging import AccessFormatter

from foundry_mcp_server import main
from foundry_mcp_server.evaluation import EvaluationMiddleware,TraceRecorder
from foundry_mcp_server.config import Settings
from foundry_mcp_server.image_preview_runtime import PreviewRuntime
from foundry_mcp_server.image_preview_store import StoreFailure


class LogPrivacyTests(unittest.TestCase):
    def test_encoded_paths_signed_urls_and_idempotent_installation(self):
        from foundry_mcp_server.image_preview_privacy import scrub_text,install_capability_filters,CapabilityFilter
        nonce = str(uuid.uuid4())
        for value in ('/image%2Dpreviews/'+nonce+'.png','https%3A%2F%2Fhost%2Fimage-previews%2F'+nonce+'.png',
                '/image-previews/'+nonce+'.png?signature=private',
                'https://bucket.example/object?X-Amz-Signature='+nonce):
            self.assertFalse(nonce in scrub_text(value))
        install_capability_filters()
        install_capability_filters()
        for name in ('uvicorn.access','foundry_mcp.image_previews'):
            self.assertEqual(sum(isinstance(f,CapabilityFilter) for f in logging.getLogger(name).filters),1)

    def test_malformed_encoded_url_does_not_break_logging(self):
        from foundry_mcp_server.image_preview_privacy import scrub_text
        self.assertIsInstance(scrub_text('http%3A%2F%2F%5B'),str)

    def test_trace_redaction_supports_json_strings_with_unpaired_surrogates(self):
        from foundry_mcp_server.image_preview_privacy import private_record
        result = private_record('/image-previews/fixture'+chr(0xd800))
        self.assertTrue(result['redacted'])

    def test_actual_access_formatter_preserves_status_without_capability_or_query(self):
        nonce = str(uuid.uuid4())
        output = StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(AccessFormatter('%(client_addr)s - "%(request_line)s" %(status_code)s',use_colors=False))
        logger = logging.getLogger('uvicorn.access')
        with patch.object(logger,'handlers',[handler]),patch.object(logger,'propagate',False),patch.object(logger,'level',logging.INFO):
            for status in (200,404,503):
                logger.info('%s - "%s %s HTTP/%s" %d','127.0.0.1:1','GET',
                    '/image-previews/'+nonce+'.png?probe=1&private=value','1.1',status)
            logger.info('%s - "%s %s HTTP/%s" %d','127.0.0.1:1','GET','/health','1.1',200)
        text = output.getvalue()
        self.assertFalse(nonce in text)
        self.assertFalse('private=value' in text)
        for value in ('200','404','503','/health','GET'):self.assertIn(value,text)

    def test_application_exception_and_interpolated_url_do_not_emit_capability(self):
        nonce = str(uuid.uuid4())
        capability = 'https://previews.example.com/image-previews/'+nonce+'.webp?probe=1'
        output = StringIO()
        handler = logging.StreamHandler(output)
        logger = logging.getLogger('foundry_mcp.image_previews')
        with patch.object(logger,'handlers',[handler]),patch.object(logger,'propagate',False),patch.object(logger,'level',logging.INFO):
            logger.info('preview request %s status=200',capability)
            try:raise ValueError('fixture failure '+capability)
            except ValueError:logger.exception('preview status=503')
        text = output.getvalue()
        self.assertFalse(nonce in text)
        self.assertIn('status=200',text)
        self.assertIn('status=503',text)
        self.assertIn('ValueError',text)


class TracePrivacyTests(unittest.IsolatedAsyncioTestCase):
    async def test_evaluation_arguments_results_and_error_metrics_are_capability_safe(self):
        nonce = str(uuid.uuid4())
        capability = 'https://previews.example.com/image-previews/'+nonce+'.png'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'trace.jsonl'
            middleware = EvaluationMiddleware(TraceRecorder(path))
            async def reply(context):
                return ToolResult(structured_content={'url':capability,'source':capability,'complete':True})
            for tool,args in (('get_foundry_image_url',{'request':{'src':capability}}),
                    ('search_journals',{'query':capability})):
                context = MiddlewareContext(message=CallToolRequestParams(name=tool,arguments=args))
                with patch('foundry_mcp_server.evaluation.get_http_headers',return_value={}):
                    await middleware.on_call_tool(context,reply)
            text = path.read_text()
            self.assertFalse(nonce in text)
            records = [json.loads(line) for line in text.splitlines()]
            finished = [row for row in records if row['event']=='call_finished']
            self.assertEqual(len(finished),2)
            self.assertTrue(all(row['response_payload_bytes']>0 for row in finished))

    async def test_uvicorn_protocol_emits_redacted_success_query_not_found_and_error(self):
        # Exercise Uvicorn's real protocol/cycle/access logging and the production
        # ASGI app using a memory transport; no second listening server/instance.
        from uvicorn import Config
        from uvicorn.protocols.http.h11_impl import H11Protocol
        from uvicorn.server import ServerState
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            config = Settings(auth_mode='basic',basic_username='user',basic_password='pass',bridge_token='bridge',
                image_preview_origin='https://previews.example.com',image_preview_data_dir=directory)
            runtime = PreviewRuntime()
            output = StringIO()
            handler = logging.StreamHandler(output)
            handler.setFormatter(AccessFormatter('%(request_line)s %(status_code)s',use_colors=False))
            logger = logging.getLogger('uvicorn.access')
            with patch.object(main,'settings',config),patch.object(main,'preview_runtime',runtime), \
                    patch.object(logger,'handlers',[handler]),patch.object(logger,'propagate',False),patch.object(logger,'level',logging.INFO):
                async with main.app.router.lifespan_context(main.app):
                    # Use the same tiny real PNG fixture as the route tests.
                    from io import BytesIO
                    png = BytesIO()
                    Image.new('RGB',(17,11),(20,40,60)).save(png,format='PNG')
                    receipt = await runtime.publish(png.getvalue(),'image/png')
                    path = f'/image-previews/{receipt.token}.png'
                    server_state = ServerState()
                    class Transport(asyncio.Transport):
                        def __init__(self):self.done = asyncio.Event(); self.parts = []
                        def get_extra_info(self,name,default=None):
                            return {'sockname':('127.0.0.1',8000),'peername':('127.0.0.1',1234)}.get(name,default)
                        def write(self,data):self.parts.append(data)
                        def close(self):self.done.set()
                        def is_closing(self):return self.done.is_set()
                        def pause_reading(self):pass
                        def resume_reading(self):pass
                    async def request(path,status):
                        transport = Transport()
                        protocol = H11Protocol(Config(main.app,log_config=None,access_log=True),server_state,{})
                        protocol.connection_made(transport)
                        try:
                            protocol.data_received(('GET '+path+' HTTP/1.1\r\nHost: test\r\nConnection: close\r\n\r\n').encode())
                            await asyncio.wait_for(transport.done.wait(),2)
                            await asyncio.gather(*tuple(server_state.tasks))
                            self.assertTrue(b''.join(transport.parts).startswith(f'HTTP/1.1 {status}'.encode()))
                        finally:protocol.connection_lost(None)
                    await request(path,200)
                    await request(path+'?probe=1',200)
                    await request(path.replace('.png','.webp'),404)
                    with patch.object(runtime.store,'lookup',side_effect=StoreFailure()):await request(path,503)
                    await request('/health',200)
            text = output.getvalue()
            self.assertFalse(receipt.token in text)
            self.assertEqual(text.count('[redacted]'),4)
            for value in ('200','404','503','GET /health'):self.assertIn(value,text)


class AuthMatrixTests(unittest.TestCase):
    def test_fresh_actual_application_authentication_modes(self):
        from test_oauth import ENV
        reports = []
        for mode in ('basic','oauth','development','none'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as directory:
                env = {key:value for key,value in os.environ.items() if not key.startswith(('FOUNDRY_MCP_','FASTMCP_'))}
                env.update(FOUNDRY_MCP_IMAGE_PREVIEW_ORIGIN='https://previews.example.com',
                    FOUNDRY_MCP_IMAGE_PREVIEW_DATA_DIR=directory)
                if mode=='basic':env.update(FOUNDRY_MCP_AUTH_MODE='basic',FOUNDRY_MCP_BASIC_USERNAME='user',
                    FOUNDRY_MCP_BASIC_PASSWORD='pass',FOUNDRY_MCP_BRIDGE_TOKEN='bridge')
                elif mode=='oauth':env.update(ENV)
                elif mode=='development':env.update(FOUNDRY_MCP_DEV_EXECUTION='true',
                    FOUNDRY_MCP_CALLER_TOKEN='development-caller',FOUNDRY_MCP_BROWSER_TOKEN='development-browser')
                completed = subprocess.run([sys.executable,str(Path(__file__).parent/'fixtures/image_preview_auth_probe.py'),mode],
                    cwd=Path(main.__file__).resolve().parents[1],env=env,capture_output=True,text=True,timeout=30)
                report = json.loads(completed.stdout)
                self.assertEqual(completed.returncode,0,report)
                self.assertTrue(report['complete'])
                self.assertLessEqual(report['calls'],16)
                reports.append(report)
        print('PREVIEW_AUTH_MATRIX '+json.dumps(reports,sort_keys=True))
