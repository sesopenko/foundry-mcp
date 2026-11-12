"""Native typography/pixels and real supervised atlas lifecycle contracts."""
import hashlib
import io
import json
import os
import struct
import unittest
from unittest.mock import patch

from PIL import Image

from foundry_mcp_server import map_note_glyphs as glyphs
from foundry_mcp_server.image_preview_failure import PreviewFailure
from foundry_mcp_server.image_preview_resources import WorkerMetrics
from foundry_mcp_server.image_preview_supervisor import PreviewSupervisor
from foundry_mcp_server.image_preview_workspace import PreviewWorkspace
from foundry_mcp_server.image_preview_worker import initialise
from foundry_mcp_server.map_note_glyph_probe import probe_glyphs,MAX_ATLAS_BYTES,AtlasReply


class NativeGlyphTests(unittest.TestCase):
    def setUp(self):
        self.workspace=PreviewWorkspace();self.workspace.__enter__()
        self.environment=patch.dict(os.environ,self.workspace.environment());self.environment.start()

    def tearDown(self):
        self.environment.stop();self.workspace.__exit__(None,None,None)

    def test_worker_json_geometry_is_accepted_without_losing_strict_validation(self):
        value={'glyphs':{'sizes':[[21,14],[31,14]],'width':31,'height':28,'size_bytes':100}}
        reply=AtlasReply.model_validate(json.loads(json.dumps(value)))
        self.assertEqual(reply.model_dump(),value)
        for sizes in ([[21,True]],[[21,14,7]],[[21.0,14]],[[193,14]]):
            with self.subTest(sizes=sizes),self.assertRaises(ValueError):
                AtlasReply.model_validate({'glyphs':{**value['glyphs'],'sizes':sizes}})

    def test_private_atlas_uses_generated_96dpi_container_contract(self):
        glyphs.glyph_atlas(['N1'],self.workspace.path)
        data=(self.workspace.path/'glyphs.png').read_bytes()
        offset=data.index(b'pHYs')+4
        self.assertEqual(struct.unpack('>IIB',data[offset:offset+9]),(3780,3780,1))

    def test_native_metrics_rgba_antialias_and_contrast(self):
        keys=['N1','N12','N100','N999999999999999']
        result=glyphs.rasterize_keys(keys)
        self.assertEqual([g.key for g in result],keys)
        self.assertLess(result[0].width,result[1].width)
        self.assertLess(result[1].width,result[2].width)
        for glyph in result:
            self.assertLessEqual(glyph.width,192);self.assertLessEqual(glyph.height,20)
            self.assertEqual((glyph.image.bands,glyph.image.format),(4,'uchar'))
            rgba=Image.frombytes('RGBA',(glyph.width,glyph.height),glyph.image.write_to_memory())
            pixels=list(rgba.get_flattened_data())
            self.assertIn((255,255,255,255),pixels)
            self.assertTrue(any(r==g==b==24 and a>0 for r,g,b,a in pixels))
            self.assertTrue(any(0<a<255 for r,g,b,a in pixels))
            self.assertEqual(rgba.getbbox(),(0,0,glyph.width,glyph.height))
            # Fixed white fill and dark outline remain visible on both extremes.
            for color in ('white','black'):
                rendered=Image.alpha_composite(Image.new('RGBA',rgba.size,color),rgba).convert('L')
                self.assertGreater(max(rendered.get_flattened_data())-min(rendered.get_flattened_data()),200)

    def test_outline_is_exact_one_pixel_dilation_with_no_resizing(self):
        vips=initialise()
        values=bytes([0,0,0,0,0,0,255,128,0,0,0,0,0,0,0])
        mask=vips.Image.new_from_memory(values,5,3,1,'uchar')
        with patch.object(vips.Image,'text',return_value=mask) as text:
            glyph=glyphs.rasterize_keys(['N1'])[0]
        self.assertEqual((glyph.width,glyph.height),(7,5))
        text.assert_called_once_with('N1',font='DejaVu Sans 12',fontfile=str(glyphs.FONT_FILE),dpi=96,wrap='none')
        rgba=Image.frombytes('RGBA',(7,5),glyph.image.write_to_memory())
        # Independent scalar maximum filter plus source-over equation.
        def fill(x,y):return values[(y-1)*5+x-1] if 1<=x<6 and 1<=y<4 else 0
        for y in range(5):
            for x in range(7):
                a=fill(x,y);b=max(fill(xx,yy) for yy in range(y-1,y+2) for xx in range(x-1,x+2))
                expected=a+b*(1-a/255)
                self.assertLessEqual(abs(rgba.getpixel((x,y))[3]-expected),1)
                if a==255:self.assertEqual(rgba.getpixel((x,y)),(255,255,255,255))
                if a==0 and b>0:self.assertEqual(rgba.getpixel((x,y))[:3],(24,24,24))

    def test_invalid_keys_never_reach_native_markup_or_fonts(self):
        invalid=[[],['N0'],['N01'],['N-1'],['N1\n'],['N１'],['N1<span>'],['<b>N1</b>'],['N'+'9'*16],
            ['JournalEntry.private'],[True],['N1','N1'],['N1']*101,None,'N1']
        with patch.object(glyphs,'verified_font') as font:
            for keys in invalid:
                with self.subTest(keys=keys),self.assertRaises(PreviewFailure) as caught:glyphs.rasterize_keys(keys)
                self.assertEqual(caught.exception.code,'InvalidOperation')
            font.assert_not_called()

    def test_missing_corrupt_or_symlink_font_cannot_fall_back_to_host(self):
        path=self.workspace.path/'missing.ttf'
        with patch.object(glyphs,'FONT_FILE',path):
            with self.assertRaises(PreviewFailure) as caught:glyphs.rasterize_keys(['N1'])
            self.assertEqual(caught.exception.code,'ImageProcessingFailed')
        path.write_bytes(b'x'*759720)
        with patch.object(glyphs,'FONT_FILE',path):
            with self.assertRaises(PreviewFailure):glyphs.rasterize_keys(['N1'])
        path.unlink();path.symlink_to(glyphs.FONT_FILE)
        with patch.object(glyphs,'FONT_FILE',path):
            with self.assertRaises(PreviewFailure):glyphs.rasterize_keys(['N1'])
        self.assertEqual(hashlib.sha256(glyphs.FONT_FILE.read_bytes()).hexdigest(),glyphs.FONT_SHA256)

    def test_overheight_native_output_fails_instead_of_shrinking(self):
        vips=initialise();mask=vips.Image.black(20,19)
        with patch.object(vips.Image,'text',return_value=mask):
            with self.assertRaises(PreviewFailure) as caught:glyphs.rasterize_keys(['N1'])
        self.assertEqual(caught.exception.code,'ImageProcessingFailed')

    def test_isolated_font_config_and_license_ship_inside_package(self):
        from xml.etree import ElementTree
        root=ElementTree.parse(glyphs.FONT_DIR/'fonts.conf').getroot()
        self.assertEqual(root.tag,'fontconfig')
        self.assertEqual(root.findall('.//dir')+root.findall('.//include'),[])
        self.assertEqual(self.workspace.environment()['FONTCONFIG_FILE'],str(glyphs.FONT_DIR/'fonts.conf'))
        license=(glyphs.FONT_DIR/'LICENSE.txt').read_text()
        self.assertIn('Copyright (c) 2003 by Bitstream',license)
        self.assertIn('Copyright (c) 2006 by Tavmjong Bah',license)


class SupervisedGlyphTests(unittest.IsolatedAsyncioTestCase):
    def supervisor(self,**options):
        self.paths=[]
        def workspace():
            result=PreviewWorkspace();enter=result.__enter__
            # Record actual owned directory without replacing cleanup ownership.
            class RecordedWorkspace:
                def __enter__(inner):
                    entered=enter();self.paths.append(entered.path);return entered
                def __exit__(inner,*exc):return result.__exit__(*exc)
            return RecordedWorkspace()
        return PreviewSupervisor(workspace_factory=workspace,**options)

    async def test_real_worker_deterministic_metrics_bounds_and_cleanup(self):
        supervisor=self.supervisor();metrics=WorkerMetrics()
        keys=['N1','N12','N100','N999999999999999']
        first=await probe_glyphs(keys,supervisor=supervisor,metrics=metrics)
        second=await probe_glyphs(keys,supervisor=supervisor)
        self.assertEqual(first.png,second.png);self.assertEqual(first.sizes,second.sizes)
        self.assertEqual(first.keys,tuple(keys));self.assertLessEqual(len(first.png),MAX_ATLAS_BYTES)
        with Image.open(io.BytesIO(first.png)) as image:
            self.assertEqual(image.mode,'RGBA')
            self.assertEqual(image.size,(max(w for w,h in first.sizes),sum(h for w,h in first.sizes)))
        self.assertGreater(metrics.peak_rss_bytes,0);self.assertLess(metrics.peak_rss_bytes,1024**3)
        self.assertTrue(all(not path.exists() for path in self.paths))
        self.assertNotIn('png',repr(first))

    async def test_one_hundred_maximum_length_keys_remain_bounded(self):
        keys=['N'+str(999999999999000+i) for i in range(100)]
        supervisor=self.supervisor();atlas=await probe_glyphs(keys,supervisor=supervisor)
        self.assertEqual(len(atlas.sizes),100)
        self.assertTrue(all(w<=192 and h<=20 for w,h in atlas.sizes))
        self.assertTrue(all(not path.exists() for path in self.paths))

    async def test_real_resource_rejection_and_timeout_remove_owned_scratch(self):
        for options,code in [(dict(max_scratch=1),'ImageScratchLimit'),(dict(max_rss=1),'ImageMemoryLimit'),
                             (dict(timeout=0.000001),'ImageProcessingTimeout')]:
            supervisor=self.supervisor(**options)
            with self.subTest(code=code),self.assertRaises(PreviewFailure) as caught:
                await probe_glyphs(['N1'],supervisor=supervisor)
            self.assertEqual(caught.exception.code,code)
            self.assertTrue(all(not path.exists() for path in self.paths))

    async def test_private_worker_rejects_extra_source_or_markup_fields(self):
        supervisor=self.supervisor()
        for request in [dict(operation='glyphs',keys=['N1'],font='/etc/private'),dict(operation='glyphs',keys=['<b>N1</b>'])]:
            reply=json.loads(await supervisor.run(json.dumps(request).encode()))
            self.assertEqual(reply,{'error_code':'InvalidOperation'})
        self.assertTrue(all(not path.exists() for path in self.paths))
