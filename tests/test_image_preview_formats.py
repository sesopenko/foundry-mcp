"""Real raster codecs through the supervised production worker, independent pixels."""
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import unittest
import struct
from unittest.mock import patch

from PIL import Image,ImageOps

from foundry_mcp_server import image_preview_process as process
from foundry_mcp_server.image_preview_failure import PreviewFailure


class FormatTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'misleading.extension'

    def test_packaged_loader_inventory(self):
        import PIL
        from foundry_mcp_server.image_preview_worker import initialise
        native = initialise()
        loaders = ('jpegload','pngload','webpload','gifload','tiffload','heifload')
        self.assertTrue(all(native.type_find('VipsOperation',name) for name in loaders))
        print('RASTER_CODECS '+json.dumps(dict(uid=os.getuid(),pillow=PIL.__version__,
            pyvips=native.__version__,libvips='.'.join(str(native.version(i)) for i in range(3)),
            loaders=loaders),sort_keys=True))

    def save(self, fmt, *, animated=False, default=False):
        first = Image.new('RGBA' if fmt in ('PNG','WEBP','AVIF') else 'RGB', (23,17), (210,40,70))
        options = {}
        if fmt == 'JPEG': options.update(quality=100,subsampling=0)
        if fmt == 'WEBP': options['lossless'] = True
        if fmt == 'AVIF': options.update(quality=100,subsampling='4:4:4',max_threads=2)
        if animated:
            other = Image.new(first.mode,first.size,(30,190,80))
            options.update(save_all=True,append_images=[other],duration=100)
            if default:
                options.update(default_image=True,append_images=[first,other])
                first = Image.new(first.mode,first.size,(0,0,250))
        first.save(self.path,format=fmt,**options)

    async def check(self, mime, policy='still', tolerance=0):
        metadata = await process.probe_image(self.path)
        self.assertEqual((metadata.width,metadata.height,metadata.mime_type,metadata.frame_policy),
            (23,17,mime,policy))
        result = await process.render_preview(self.path,dict(x=2,y=3,width=11,height=9))
        self.assertEqual(result.geometry.source,metadata)
        self.assertEqual(result.geometry.mime_type,'image/png')
        with Image.open(BytesIO(result.data)) as output:
            self.assertEqual(output.size,(11,9))
            for pixel in output.convert('RGB').get_flattened_data():
                self.assertLessEqual(max(abs(a-b) for a,b in zip(pixel,(210,40,70))),tolerance)

    async def test_all_advertised_still_rasters_from_bytes(self):
        for fmt,mime,tolerance in [('JPEG','image/jpeg',2),('PNG','image/png',0),
                ('WEBP','image/webp',0),('AVIF','image/avif',3),('BMP','image/bmp',0),
                ('GIF','image/gif',0),('TIFF','image/tiff',0)]:
            with self.subTest(format=fmt):
                self.save(fmt)
                await self.check(mime,tolerance=tolerance)

    async def test_first_frame_and_page_without_vertical_stacks(self):
        for fmt,mime,tolerance in [('PNG','image/png',0),('WEBP','image/webp',0),
                ('GIF','image/gif',0),('TIFF','image/tiff',0),('AVIF','image/avif',3)]:
            with self.subTest(format=fmt):
                self.save(fmt,animated=True)
                await self.check(mime,'first_frame',tolerance)

    async def test_apng_with_separate_fallback_selects_first_animation_frame(self):
        self.save('PNG',animated=True,default=True)
        await self.check('image/png','first_frame')

    async def test_malformed_new_headers_and_unrelated_loaders_are_rejected(self):
        for data in (b'GIF89a',b'BMbad',b'II*\0bad',b'MM\0*bad',
                b'\0\0\0\x18ftypavif\0\0\0\0avifmif1',b'P6\n1 1\n255\nabc',
                b'<svg xmlns="http://www.w3.org/2000/svg"/>',b'%PDF-1.7'):
            self.path.write_bytes(data)
            with self.assertRaises(PreviewFailure) as caught:
                await process.render_preview(self.path)
            self.assertEqual(caught.exception.code,'UnsupportedImage')

    async def test_new_codec_alpha_is_preserved(self):
        for fmt in ('AVIF','TIFF','GIF'):
            with self.subTest(format=fmt):
                image = Image.new('RGBA',(23,17),(210,40,70,0))
                image.putpixel((10,10),(30,190,80,255))
                options = dict(quality=100,subsampling='4:4:4',max_threads=2) if fmt=='AVIF' else {}
                image.save(self.path,format=fmt,**options)
                result = await process.render_preview(self.path)
                with Image.open(BytesIO(result.data)) as output:
                    alpha = output.convert('RGBA').getchannel('A')
                    self.assertEqual(alpha.getpixel((0,0)),0)
                    self.assertEqual(alpha.getpixel((10,10)),255)

    async def test_tiff_and_avif_orientation_matches_independent_display_pixels(self):
        image = Image.new('RGB',(23,17),(210,40,70))
        for x in range(10):
            for y in range(8): image.putpixel((x,y),(30,190,80))
        for fmt in ('TIFF','AVIF'):
            for orientation in range(1,9):
                with self.subTest(format=fmt,orientation=orientation):
                    exif = Image.Exif()
                    exif[274] = orientation
                    options = dict(quality=100,subsampling='4:4:4',max_threads=2) if fmt=='AVIF' else {}
                    image.save(self.path,format=fmt,exif=exif,**options)
                    with Image.open(self.path) as source:
                        expected = ImageOps.exif_transpose(source).convert('RGB')
                    metadata = await process.probe_image(self.path)
                    self.assertEqual((metadata.width,metadata.height),expected.size)
                    result = await process.render_preview(self.path)
                    with Image.open(BytesIO(result.data)) as output:
                        self.assertEqual(output.size,expected.size)
                        self.assertLessEqual(max(abs(a-b) for actual,want in zip(
                            output.convert('RGB').get_flattened_data(),expected.get_flattened_data())
                            for a,b in zip(actual,want)),3 if fmt=='AVIF' else 0)

    async def test_bitmap_limits_are_checked_from_header_without_pixel_decode(self):
        self.save('BMP')
        original = self.path.read_bytes()
        for width,height,accepted in ((32768,1,True),(16000,8000,True),(32769,1,False),(16001,8000,False)):
            data = bytearray(original)
            data[18:26] = struct.pack('<ii',width,height)
            self.path.write_bytes(data)
            if accepted:
                result = await process.probe_image(self.path)
                self.assertEqual((result.width,result.height),(width,height))
            else:
                with self.assertRaises(PreviewFailure) as caught:await process.probe_image(self.path)
                self.assertEqual((caught.exception.code,caught.exception.width,caught.exception.height),
                    ('ImageTooLarge',width,height))

    def test_compatibility_probe_never_normalizes_pixels(self):
        from foundry_mcp_server.image_preview_worker import probe
        for fmt,animated,default in (('BMP',False,False),('PNG',True,True),('AVIF',True,False)):
            self.save(fmt,animated=animated,default=default)
            with patch('foundry_mcp_server.image_preview_raster.normalize',side_effect=AssertionError('pixel decode')):
                self.assertEqual(probe(self.path)['width'],23)

    async def test_corrupt_raster_bodies_fail_render_even_when_header_is_readable(self):
        for fmt in ('BMP','GIF','TIFF','AVIF'):
            with self.subTest(format=fmt):
                self.save(fmt)
                data = self.path.read_bytes()
                self.path.write_bytes(data[:-max(16,len(data)//3)])
                with self.assertRaises(PreviewFailure) as caught:await process.render_preview(self.path)
                self.assertEqual(caught.exception.code,'UnsupportedImage')

    def test_avif_adapter_sets_and_restores_pinned_decoder_thread_budget(self):
        from PIL import AvifImagePlugin
        from foundry_mcp_server.image_preview_raster import avif_frames
        self.save('AVIF',animated=True)
        old = AvifImagePlugin.DEFAULT_MAX_THREADS
        real_open = Image.open
        def admitted_open(*args,**kwargs):
            self.assertEqual(AvifImagePlugin.DEFAULT_MAX_THREADS,2)
            self.assertEqual(kwargs['formats'],['AVIF'])
            return real_open(*args,**kwargs)
        with patch('PIL.Image.open',side_effect=admitted_open):
            self.assertEqual(avif_frames(self.path,None,header_only=True),(None,2))
        self.assertEqual(AvifImagePlugin.DEFAULT_MAX_THREADS,old)
