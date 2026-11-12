"""Real allowlisted native header probes plus bounded subprocess supervision."""
import asyncio
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch
import zlib

from PIL import Image

from foundry_mcp_server import image_preview_limits as limits
from foundry_mcp_server import image_preview_process as process
from foundry_mcp_server.image_preview_worker import PreviewFailure


class ProbeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root/'original'

    def fixture(self, fmt='PNG', orientation=None):
        options = {}
        if orientation is not None:
            exif=Image.Exif()
            exif[274]=orientation
            options['exif']=exif
        Image.new('RGB',(19,11),(20,50,100)).save(self.path,format=fmt,**options)
        self.path.chmod(0o600)
        return self.path

    async def test_real_formats_and_misleading_extensions_are_detected_from_bytes(self):
        for fmt,mime in [('PNG','image/png'),('JPEG','image/jpeg'),('WEBP','image/webp')]:
            with self.subTest(format=fmt):
                self.fixture(fmt)
                result=await process.probe_image(self.path)
                self.assertEqual(result.model_dump(),dict(width=19,height=11,mime_type=mime,
                    size_bytes=self.path.stat().st_size,frame_policy='still'))
        self.fixture()
        disguised=self.path.with_name('looks-like-pdf.pdf')
        self.path.rename(disguised)
        self.assertEqual((await process.probe_image(disguised)).mime_type,'image/png')

    async def test_all_eight_exif_orientation_display_dimensions(self):
        for orientation in range(1,9):
            self.fixture('JPEG',orientation)
            result=await process.probe_image(self.path)
            self.assertEqual((result.width,result.height),(11,19) if orientation>=5 else (19,11),orientation)

    def png_header(self,width,height):
        self.fixture()
        data=bytearray(self.path.read_bytes())
        data[16:24]=struct.pack('>II',width,height)
        data[29:33]=struct.pack('>I',zlib.crc32(data[12:29]))
        self.path.write_bytes(data)

    async def test_header_only_exact_dimension_area_limits_and_known_oversize(self):
        # Raster bodies intentionally remain small: probing must not allocate
        # the claimed raster just to reject a header or report valid dimensions.
        for width,height,accepted in [(32768,1,True),(16000,8000,True),(32769,1,False),(16001,8000,False)]:
            with self.subTest(width=width,height=height):
                self.png_header(width,height)
                if accepted:
                    result=await process.probe_image(self.path)
                    self.assertEqual((result.width,result.height),(width,height))
                else:
                    with self.assertRaises(PreviewFailure) as caught:await process.probe_image(self.path)
                    self.assertEqual(caught.exception.code,'ImageTooLarge')
                    self.assertEqual((caught.exception.width,caught.exception.height),(width,height))

    async def test_exact_compressed_limit_and_overflow_use_sparse_files(self):
        self.fixture()
        with self.path.open('r+b') as stream:stream.truncate(limits.SOURCE_MAX_BYTES)
        self.assertEqual((await process.probe_image(self.path)).size_bytes,limits.SOURCE_MAX_BYTES)
        with self.path.open('r+b') as stream:stream.truncate(limits.SOURCE_MAX_BYTES+1)
        with self.assertRaises(PreviewFailure) as caught:await process.probe_image(self.path)
        self.assertEqual(caught.exception.code,'ImageTooLarge')

    async def test_malformed_unsupported_unsafe_and_symlink_inputs_fail_without_native_details(self):
        for data in [b'',b'\x89PNG\r\n\x1a\n',b'\xff\xd8\xff',b'RIFFxxxxWEBPbad',b'%PDF-private',
                b'<svg><image href="https://private.example/?signature=secret"/></svg>',b'P3 1 1 255 1 2 3']:
            self.path.write_bytes(data)
            with self.assertRaises(PreviewFailure) as caught:await process.probe_image(self.path)
            self.assertEqual(caught.exception.code,'UnsupportedImage')
            self.assertNotIn('private',str(caught.exception))
        self.fixture()
        link=self.root/'symlink'
        link.symlink_to(self.path)
        with self.assertRaises(PreviewFailure):await process.probe_image(link)


class FakeProcess:
    def __init__(self, output=None, stalled=False):
        self.stdin=Mock(drain=AsyncMock())
        self.returncode=None
        self.killed=False
        self.waited=0
        self.entered=asyncio.Event()
        if stalled:
            async def read(_):
                self.entered.set()
                await asyncio.Event().wait()
            self.stdout=Mock(read=read)
        else:
            self.stdout=asyncio.StreamReader()
            self.stdout.feed_data(output)
            self.stdout.feed_eof()

    def kill(self):
        self.killed=True
        self.returncode=-9

    async def wait(self):
        self.waited+=1
        if self.returncode is None:self.returncode=0
        return self.returncode


class ProcessBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'original'
        self.path.write_bytes(b'fixture')

    async def test_parent_rejects_oversized_output_invalid_metadata_and_unknown_error_fields(self):
        for output in [b'x'*4097,b'not-json',json.dumps({'metadata':dict(width=True,height=1,mime_type='image/png',size_bytes=7,frame_policy='still')}).encode(),
                b'{"error_code":"private-url-secret"}',b'{"error_code":"UnsupportedImage","extra":"private"}']:
            child=FakeProcess(output)
            with patch.object(process.asyncio,'create_subprocess_exec',AsyncMock(return_value=child)):
                with self.assertRaises(PreviewFailure) as caught:await process.probe_image(self.path)
            self.assertEqual(caught.exception.code,'ImageProcessingFailed')
            self.assertNotIn('private',str(caught.exception))
            self.assertGreaterEqual(child.waited,1)
            if len(output)>4096:self.assertTrue(child.killed)

    async def test_timeout_and_cancellation_kill_reap_and_remove_private_scratch(self):
        for cancel in (False,True):
            child=FakeProcess(stalled=True)
            spawn=AsyncMock(return_value=child)
            with patch.object(process.asyncio,'create_subprocess_exec',spawn):
                task=asyncio.create_task(process.probe_image(self.path,timeout=1 if cancel else 0.02))
                await child.entered.wait()
                scratch=Path(spawn.await_args.kwargs['env']['TMPDIR'])
                self.assertTrue(scratch.exists())
                self.assertNotEqual(scratch,self.path.parent)
                self.assertEqual(spawn.await_args.kwargs['stderr'],asyncio.subprocess.DEVNULL)
                self.assertFalse(any(key.startswith(('FOUNDRY_MCP_','AUTH0_','AWS_')) for key in spawn.await_args.kwargs['env']))
                if cancel:
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):await task
                else:
                    with self.assertRaises(PreviewFailure) as caught:await task
                    self.assertEqual(caught.exception.code,'ImageProcessingTimeout')
            self.assertTrue(child.killed)
            self.assertGreaterEqual(child.waited,1)
            self.assertFalse(scratch.exists())

    async def test_spawn_errors_are_fixed_categories_not_native_paths(self):
        with patch.object(process.asyncio,'create_subprocess_exec',AsyncMock(side_effect=OSError('private-path-secret'))):
            with self.assertRaises(PreviewFailure) as caught:await process.probe_image(self.path)
        self.assertEqual(caught.exception.code,'ImageProcessingFailed')
        self.assertNotIn('private',str(caught.exception))
