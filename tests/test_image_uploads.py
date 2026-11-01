"""Actual MCP contracts, image worker isolation, and safe retrieval boundaries."""
import asyncio
import base64
import hashlib
import io
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from PIL import Image
from fastmcp import Client
from fastmcp.exceptions import ToolError
from foundry_mcp_server import image_worker as W
from foundry_mcp_server.mcp_server import image_uploads as U
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from foundry_mcp_server.evaluation import arguments_for_log
from foundry_mcp_server.ws.connection import RpcError


def png(fmt='PNG'):
    buffer = io.BytesIO()
    Image.new('RGB', (16, 12), (20, 50, 100)).save(buffer, format=fmt)
    return buffer.getvalue()


class ImageUploadTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.socket = object()
        self.manager = Mock(websockets={'gm': self.socket}, call=AsyncMock())
        register_foundry_manager(self.manager)
        self.data = png()
        self.meta = U.ImageMetadata(mime_type='image/png', width=16, height=12, size_bytes=len(self.data), sha256=hashlib.sha256(self.data).hexdigest())
        self.preflight = dict(world_id='test', user_id='gm', location=dict(source='data', directory='assets'),
                              capabilities=dict(can_upload=True, can_create_directory=True, reasons=[]))
        self.receipt = dict(status='uploaded', world_id='test', user_id='gm', filename='Goblin.png', overwritten=False,
                            image=dict(source='data', directory='assets', src='assets/Goblin.png'), **self.meta.model_dump())
        self.request = dict(directory='assets', filename='Goblin', file=dict(download_url='https://example.org/signed?secret=hidden', file_id='file-secret'))
        self.manager.call.side_effect = [self.preflight, self.receipt]

    async def retrieve(self, url, path):
        path.write_bytes(self.data)
        return self.meta, 'png'

    async def test_actual_discovery_file_contract_and_upload_receipt(self):
        with patch.object(U, 'retrieve_image', self.retrieve):
            async with Client(mcp) as client:
                tool = next(t for t in await client.list_tools() if t.name == 'upload_image')
                self.assertEqual(tool.meta['openai/fileParams'], ['file'])
                self.assertTrue(tool.annotations.destructive_hint)
                self.assertFalse(tool.annotations.read_only_hint)
                file = tool.input_schema['$defs']['OpenAIFile']
                self.assertEqual(file['required'], ['download_url', 'file_id'])
                self.assertEqual(set(file['properties']), {'download_url','file_id','mime_type','file_name'})
                self.assertTrue(all(p['type'] == 'string' for p in file['properties'].values()))
                self.assertFalse(file['additionalProperties'])
                self.assertIn('PERMANENTLY', tool.description)
                result = (await client.call_tool('upload_image', self.request)).structured_content
                self.assertEqual(result, self.receipt)
                self.assertLess(len(json.dumps(result).encode()), 8000)
        sent = self.manager.call.await_args.args[2]
        self.assertEqual(base64.b64decode(sent['content']), self.data)
        self.assertFalse(sent['overwrite'])
        self.assertNotIn('download_url', sent)
        self.assertNotIn('hidden', json.dumps(arguments_for_log('upload_image', self.request)))

    async def test_invalid_inputs_fail_before_network_or_rpc(self):
        with patch.object(U, 'retrieve_image', new_callable=AsyncMock) as retrieve:
            async with Client(mcp) as client:
                for change in [dict(filename='x.png'), dict(filename='../x'), dict(filename='x/y'), dict(filename='x%2fy'),
                               dict(directory='../x'), dict(directory='x//y'), dict(overwrite='true'), dict(source='public'),
                               dict(file={'download_url':'https://example.org','file_id':'x','unexpected':1}),
                               dict(file={'download_url':'https://example.org','file_id':'x','mime_type':None})]:
                    result = await client.call_tool('upload_image', {**self.request, **change}, raise_on_error=False)
                    self.assertTrue(result.is_error, change)
            retrieve.assert_not_awaited(); self.manager.call.assert_not_awaited()

    async def test_collision_error_is_actionable_and_does_not_echo_private_browser_errors(self):
        self.manager.call.side_effect = [self.preflight, RpcError({'code':'FileExists','message':'private-browser-secret'})]
        with patch.object(U, 'retrieve_image', self.retrieve):
            async with Client(mcp) as client:
                result = await client.call_tool('upload_image', self.request, raise_on_error=False)
                self.assertTrue(result.is_error)
                self.assertIn('overwrite=true', str(result.content)); self.assertNotIn('private-browser-secret', str(result.content))

    async def test_timeout_and_malformed_receipt_are_unknown_never_success_or_retry(self):
        for last in [TimeoutError(), {**self.receipt, 'sha256':'0'*64}, {**self.receipt, 'overwritten':True}]:
            self.manager.call.reset_mock(); self.manager.call.side_effect = [self.preflight, last]
            with patch.object(U, 'retrieve_image', self.retrieve):
                result = await U.upload_image(U.UploadRequest.model_validate(self.request))
            self.assertEqual(result['status'], 'upload_outcome_unknown')
            self.assertEqual(result['candidate_path'], 'assets/Goblin.png')
            self.assertEqual(self.manager.call.await_count, 2)

    async def test_socket_change_after_download_never_routes_to_new_gm(self):
        async def change(url, path):
            result = await self.retrieve(url, path)
            self.manager.websockets['gm'] = object()
            return result
        with patch.object(U, 'retrieve_image', change):
            result = await U.upload_image(U.UploadRequest.model_validate(self.request))
        self.assertEqual(result['status'], 'upload_outcome_unknown')
        self.assertEqual(self.manager.call.await_count, 1)

    async def test_explicit_overwrite_and_folder_contract(self):
        self.manager.call.side_effect = [self.preflight, {**self.receipt, 'overwritten': True}]
        with patch.object(U, 'retrieve_image', self.retrieve):
            async with Client(mcp) as client:
                result = (await client.call_tool('upload_image', {**self.request, 'overwrite': True})).structured_content
                self.assertTrue(result['overwritten'])
                folder = dict(status='created', world_id='test', user_id='gm', location=dict(source='data',directory='assets/Portraits'),
                              capabilities=self.preflight['capabilities'], next_call=dict(tool='browse_journal_images',arguments=dict(source='data',directory='assets/Portraits')))
                self.manager.call.side_effect = None; self.manager.call.return_value = folder
                self.assertEqual((await client.call_tool('create_image_directory', dict(directory='assets',name='Portraits'))).structured_content, folder)

    async def test_encoded_foundry_selector_is_preserved(self):
        receipt={**self.receipt,'filename':'α portrait.png','image':dict(source='data',directory='assets',src='assets/%CE%B1%20portrait.png')}
        self.manager.call.side_effect=[self.preflight,receipt]
        with patch.object(U,'retrieve_image',self.retrieve):
            async with Client(mcp) as client:
                result=(await client.call_tool('upload_image',{**self.request,'filename':'α portrait'})).structured_content
        self.assertEqual(result,receipt)

    async def test_busy_rejected_without_work(self):
        async with U._operation_lock:
            with self.assertRaisesRegex(ToolError, 'Busy'):
                await U.upload_image(U.UploadRequest.model_validate(self.request))
        self.manager.call.assert_not_awaited()

    async def test_decoder_subprocess_real_formats_and_rejections(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'image'
            for fmt, mime in [('JPEG','image/jpeg'), ('PNG','image/png'), ('WEBP','image/webp')]:
                data = png(fmt); path.write_bytes(data)
                result = await U.worker('validate', path, timeout=10)
                self.assertEqual(result['mime_type'], mime)
                self.assertEqual(result['sha256'], hashlib.sha256(data).hexdigest())
            for data in [b'<html>not an image</html>', png()[:40], png('GIF')]:
                path.write_bytes(data)
                with self.assertRaises(ToolError): await U.worker('validate', path, timeout=10)
            first = Image.new('RGB',(16,16),'red'); second=Image.new('RGB',(16,16),'blue')
            first.save(path,format='PNG',save_all=True,append_images=[second],duration=100,loop=0)
            with self.assertRaisesRegex(ToolError,'AnimatedImageUnsupported'): await U.worker('validate',path,timeout=10)
            Image.new('RGB',(8193,1)).save(path,format='PNG')
            with self.assertRaisesRegex(ToolError,'ImageDimensionsExceeded'): await U.worker('validate',path,timeout=10)

    async def test_worker_timeout_kills_and_reaps(self):
        process = Mock(returncode=None, kill=Mock(), wait=AsyncMock())
        async def stall(payload): await asyncio.sleep(5)
        process.communicate = stall
        with patch.object(asyncio,'create_subprocess_exec',AsyncMock(return_value=process)):
            with self.assertRaisesRegex(ToolError,'ImageProcessingTimeout'):
                await U.worker('download',Path('/unused'),timeout=.01)
        process.kill.assert_called_once(); process.wait.assert_awaited_once()


class RetrievalTests(unittest.TestCase):
    def address(self, ip):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip,443))]

    def test_public_address_and_dns_rebinding_boundary(self):
        for ip in ['127.0.0.1','10.0.0.1','169.254.169.254','::1','::ffff:8.8.8.8','224.0.0.1','192.0.2.1']:
            self.assertFalse(W.public_address(ip), ip)
        with patch.object(socket,'getaddrinfo',return_value=self.address('8.8.8.8')) as dns:
            parsed, host, address = W.destination('https://example.org/a?signature=secret')
            self.assertEqual(host,'example.org'); self.assertEqual(address[4][0],'8.8.8.8')
            dns.assert_called_once()
            conn = W.PinnedHTTPS(host,address)
            raw = Mock(); wrapped=Mock()
            with patch.object(socket,'socket',return_value=raw), patch.object(conn._context,'wrap_socket',return_value=wrapped) as tls:
                conn.connect()
                raw.connect.assert_called_once_with(('8.8.8.8',443))
                tls.assert_called_once_with(raw,server_hostname='example.org')
            dns.assert_called_once()  # connect does not re-resolve the hostname
        with patch.object(socket,'getaddrinfo',return_value=self.address('8.8.8.8')+self.address('127.0.0.1')):
            with self.assertRaises(W.ImageError): W.destination('https://example.org/')

    def test_invalid_urls_and_safe_redirect_handling(self):
        for url in ['http://example.org','https://user:pass@example.org/','file:///etc/passwd','https://example.org:8080','https://example.org/#x','https://example.org/\nsecret']:
            with self.assertRaises(W.ImageError): W.destination(url)
        response = Mock(status=302)
        response.getheader.return_value = 'http://127.0.0.1/secret'
        connection = Mock(getresponse=Mock(return_value=response))
        with patch.object(socket,'getaddrinfo',return_value=self.address('8.8.8.8')), patch.object(W,'PinnedHTTPS',return_value=connection):
            with self.assertRaises(W.ImageError): W.download('https://example.org/',Path('/unused'))
        connection.close.assert_called_once()

    def test_stream_limits_http_errors_and_no_credentials(self):
        response = Mock(status=200)
        response.getheader.side_effect = lambda name, default=None: 'identity' if name=='Content-Encoding' else None
        response.read.side_effect = [b'x'*5,b'x'*5,b'']
        connection=Mock(getresponse=Mock(return_value=response))
        with tempfile.TemporaryDirectory() as temp, patch.object(socket,'getaddrinfo',return_value=self.address('8.8.8.8')), patch.object(W,'PinnedHTTPS',return_value=connection):
            with patch.object(W,'MAX_BYTES',8), self.assertRaisesRegex(W.ImageError,'ImageTooLarge'):
                W.download('https://example.org/a',Path(temp)/'download')
            response.status=403
            result=W.download('https://example.org/a',Path(temp)/'download')
            self.assertEqual(result,dict(error_code='DownloadRejected',http_status=403))
        headers=connection.request.call_args.kwargs['headers']
        self.assertNotIn('Authorization',headers); self.assertNotIn('Cookie',headers)
