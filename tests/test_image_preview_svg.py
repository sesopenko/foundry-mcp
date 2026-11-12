"""Guarded SVG admission plus real raster pixels and negative resource access."""
from io import BytesIO
import ctypes
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import os
from pathlib import Path
import tempfile
import unittest
from threading import Thread
from urllib.request import urlopen
from unittest.mock import patch

from PIL import Image

from foundry_mcp_server import image_preview_process as process
from foundry_mcp_server.image_preview_failure import PreviewFailure


def svg(body='',attributes='width="24" height="16"'):
    return f'<svg xmlns="http://www.w3.org/2000/svg" {attributes}>{body}</svg>'.encode()


class SvgTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'original'

    async def test_core_style_icon_transparency_and_native_crop(self):
        self.path.write_bytes(svg('<path fill="#d22846" d="M2 3h12v8H2z"/>'))
        metadata = await process.probe_image(self.path)
        self.assertEqual(metadata.model_dump(),dict(width=24,height=16,mime_type='image/svg+xml',
            size_bytes=self.path.stat().st_size,frame_policy='still'))
        result = await process.render_preview(self.path,dict(x=2,y=3,width=10,height=6))
        with Image.open(BytesIO(result.data)) as output:
            self.assertEqual(output.size,(10,6))
            self.assertTrue(all(pixel==(210,40,70,255) for pixel in output.convert('RGBA').get_flattened_data()))
        result = await process.render_preview(self.path)
        with Image.open(BytesIO(result.data)) as output:
            self.assertEqual(output.convert('RGBA').getpixel((0,0))[3],0)

    async def test_viewbox_and_physical_units_use_96_css_pixels_per_inch(self):
        for attributes,expected in [('viewBox="0 0 32 18"',(32,18)),
                ('width="1in" height="0.5in"',(96,48)),
                ('width="2.54cm" height="12.7mm"',(96,48)),
                ('width="72pt" height="3pc"',(96,48)),
                ('width="64" viewBox="0 0 32 18"',(64,36))]:
            with self.subTest(attributes=attributes):
                self.path.write_bytes(svg('<rect width="100%" height="100%" fill="red"/>',attributes))
                metadata = await process.probe_image(self.path)
                self.assertEqual((metadata.width,metadata.height),expected)
                result = await process.render_preview(self.path)
                self.assertEqual((result.geometry.width,result.geometry.height),expected)

    async def test_physical_units_inside_viewport_keep_correct_pixel_placement(self):
        self.path.write_bytes(svg('<rect x="0.5in" y="0" width="0.5in" height="0.5in" fill="red"/>',
            'width="1in" height="0.5in"'))
        result = await process.render_preview(self.path)
        with Image.open(BytesIO(result.data)) as output:
            self.assertEqual(output.convert('RGBA').getpixel((24,24))[3],0)
            self.assertEqual(output.convert('RGBA').getpixel((72,24)),(255,0,0,255))

    async def test_local_fragment_use_gradient_and_inline_presentation(self):
        body = '<defs><linearGradient id="paint"><stop offset="0" stop-color="red"/><stop offset="1" stop-color="blue"/></linearGradient><path id="shape" d="M0 0h24v16H0z"/></defs><use href="#shape" style="fill:url(#paint);stroke:none"/>'
        self.path.write_bytes(svg(body))
        result = await process.render_preview(self.path)
        with Image.open(BytesIO(result.data)) as output:
            left,right = output.convert('RGB').getpixel((1,8)),output.convert('RGB').getpixel((22,8))
            self.assertGreater(left[0],left[2])
            self.assertGreater(right[2],right[0])

    async def test_named_colour_containing_url_letters_is_not_an_external_reference(self):
        self.path.write_bytes(svg('<rect width="24" height="16" fill="burlywood"/>'))
        result = await process.render_preview(self.path)
        with Image.open(BytesIO(result.data)) as output:
            self.assertEqual(output.convert('RGB').getpixel((12,8)),(222,184,135))

    async def test_missing_invalid_and_excessive_sizes(self):
        for attributes in ('','width="0" height="1"','viewBox="0 0 -1 1"','width="NaN" height="1"'):
            self.path.write_bytes(svg(attributes=attributes))
            with self.assertRaises(PreviewFailure) as caught:await process.probe_image(self.path)
            self.assertEqual(caught.exception.code,'UnsupportedImage')
        self.path.write_bytes(svg(attributes='width="32769" height="1"'))
        with self.assertRaises(PreviewFailure) as caught:await process.probe_image(self.path)
        self.assertEqual((caught.exception.code,caught.exception.width,caught.exception.height),('ImageTooLarge',32769,1))

    async def test_large_svg_dimensions_preserve_safely_known_error_geometry(self):
        self.path.write_bytes(svg(attributes='width="10000000000" height="1"'))
        with self.assertRaises(PreviewFailure) as caught:await process.probe_image(self.path)
        self.assertEqual((caught.exception.code,caught.exception.width,caught.exception.height),
            ('ImageTooLarge',10000000000,1))

    def test_forbidden_constructs_reject_before_native_loader(self):
        from foundry_mcp_server.image_preview_svg import admit_svg
        cases = [svg('<script>alert(1)</script>'),svg('<rect onload="alert(1)"/>'),
            svg('<foreignObject/>'),svg('<image href="https://example.invalid/image"/>'),
            svg('<use href="&#104;ttps://example.invalid/file#shape"/>'),
            svg('<use xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="file:///private"/>'),
            svg('<path fill="url(https://example.invalid/image)"/>'),
            svg('<path style="fill:u\\72l(https://example.invalid/image)"/>'),
            svg('<style>@import url(https://example.invalid/style);</style>'),
            svg('<g xmlns="http://www.w3.org/1999/xhtml"><script/></g>'),
            svg('<g xml:base="file:///private"/>'),svg('<animate attributeName="href"/>'),
            b'<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///private">]>'+svg('&x;'),
            b'<?xml-stylesheet href="https://example.invalid/style"?>'+svg(),
            svg('<use href="data:image/svg+xml,private"/>'),
            svg('<use href="#missing"/>'),svg('<g id="cycle"><use href="#cycle"/></g>')]
        for data in cases:
            with self.subTest(index=cases.index(data)):
                with self.assertRaises(PreviewFailure) as caught:admit_svg(data)
                self.assertEqual(caught.exception.code,'UnsupportedImage')

    def test_rejected_document_never_initializes_native_loader(self):
        from foundry_mcp_server.image_preview_svg import open_svg
        self.path.write_bytes(svg('<use href="file:///private#shape"/>'))
        with patch('foundry_mcp_server.image_preview_worker.initialise',side_effect=AssertionError('native loader invoked')):
            with self.assertRaises(PreviewFailure):open_svg(self.path,self.path.stat().st_size)

    async def test_external_http_listener_receives_no_requests(self):
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(1)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'fixture')
            def log_message(self,*args):pass
        server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread = Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            endpoint = f'http://127.0.0.1:{server.server_port}/fixture'
            with urlopen(endpoint,timeout=2) as response:self.assertEqual(response.read(),b'fixture')
            self.assertEqual(len(requests),1)
            requests.clear()
            for body in (f'<image href="{endpoint}"/>',f'<use href="{endpoint}#shape"/>',
                    f'<path style="fill:url({endpoint})"/>',
                    f'<style>@import "{endpoint}";</style>'):
                self.path.write_bytes(svg(body))
                with self.assertRaises(PreviewFailure) as caught:await process.render_preview(self.path)
                self.assertEqual(caught.exception.code,'UnsupportedImage')
            self.assertEqual(requests,[])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)
            self.assertFalse(thread.is_alive())

    async def test_external_sentinel_is_not_opened_by_native_decoder(self):
        # Linux inotify observes native opens too, unlike a Python open mock.
        sentinel = self.path.with_name('private-sentinel')
        sentinel.write_bytes(b'private synthetic sentinel')
        native = ctypes.CDLL(None,use_errno=True)
        descriptor = native.inotify_init1(os.O_NONBLOCK|os.O_CLOEXEC)
        self.assertGreaterEqual(descriptor,0)
        try:
            watch = native.inotify_add_watch(descriptor,os.fsencode(sentinel),0x20) # IN_OPEN
            self.assertGreaterEqual(watch,0)
            sentinel.read_bytes()
            self.assertTrue(os.read(descriptor,4096)) # prove watcher works
            reference = sentinel.as_uri()
            for data in (svg(f'<image href="{reference}"/>'),svg(f'<use href="{reference}#shape"/>'),
                    f'<!DOCTYPE svg [<!ENTITY x SYSTEM "{reference}">]>'.encode()+svg('&x;')):
                self.path.write_bytes(data)
                with self.assertRaises(PreviewFailure) as caught:await process.render_preview(self.path)
                self.assertEqual(caught.exception.code,'UnsupportedImage')
            with self.assertRaises(BlockingIOError):os.read(descriptor,4096)
        finally:os.close(descriptor)

    def test_parser_bounds_cycles_and_reference_expansion(self):
        from foundry_mcp_server.image_preview_svg import admit_svg,MAX_XML_BYTES,MAX_ELEMENTS,MAX_DEPTH
        fixtures = [b' '*(MAX_XML_BYTES+1),svg('<g>'*MAX_DEPTH+'</g>'*MAX_DEPTH),
            svg('<g/>'*MAX_ELEMENTS),svg('<g id="a"/><g id="a"/>'),
            svg('<path '+ ' '.join(f'a{i}="x"' for i in range(65))+'/>'),
            svg('<path/>').decode().encode('utf-16')]
        chain = '<g id="a0"><path d="M0 0h1v1z"/></g>'
        chain += ''.join(f'<g id="a{i}"><use href="#a{i-1}"/><use href="#a{i-1}"/></g>' for i in range(1,20))
        fixtures.append(svg('<defs>'+chain+'</defs><use href="#a19"/>'))
        for index,data in enumerate(fixtures):
            with self.subTest(index=index):
                with self.assertRaises(PreviewFailure):admit_svg(data)

    async def test_svg_deadline_cleans_owned_scratch_and_preserves_original(self):
        from foundry_mcp_server.image_preview_supervisor import PreviewSupervisor
        from foundry_mcp_server.image_preview_workspace import PreviewWorkspace
        self.path.write_bytes(svg('<path fill="red" d="M0 0h24v16z"/>'))
        owned = []
        class Workspace(PreviewWorkspace):
            def __enter__(self):
                result = super().__enter__()
                owned.append(self.path)
                return result
        with self.assertRaises(PreviewFailure) as caught:
            await process.render_preview(self.path,supervisor=PreviewSupervisor(workspace_factory=Workspace),timeout=0.001)
        self.assertEqual(caught.exception.code,'ImageProcessingTimeout')
        self.assertTrue(owned)
        self.assertTrue(all(not path.exists() for path in owned))
        self.assertTrue(self.path.exists())
