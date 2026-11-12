"""Independent Pillow pixel oracles against real supervised native region workers."""
import asyncio
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

from PIL import Image,ImageCms,ImageOps

from foundry_mcp_server.image_preview_child import PreviewChild
from foundry_mcp_server.image_preview_geometry import output_dimensions,preview_to_source
from foundry_mcp_server.image_preview_process import render_region
from foundry_mcp_server.image_preview_supervisor import PreviewSupervisor
from foundry_mcp_server.image_preview_worker import PreviewFailure


class GeometryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/'original'

    def pattern(self,mode='RGB'):
        image=Image.new(mode,(19,11))
        for y in range(11):
            for x in range(19):
                value=(x*11%256,y*19%256,(x+13*y)%256)
                image.putpixel((x,y),value+((7*x+3*y)%256,) if mode=='RGBA' else value)
        return image

    def decoded(self,result):
        image=Image.open(io.BytesIO(result.png))
        image.load()
        self.assertEqual(image.size,(result.geometry.width,result.geometry.height))
        self.assertNotIn('PNG',repr(result))
        return image

    async def test_native_full_border_and_one_pixel_crops_preserve_exact_pixels(self):
        for mode in ('RGB','RGBA'):
            image=self.pattern(mode)
            image.save(self.path,format='PNG')
            for box in (None,(18,10,19,11),(17,8,19,11),(0,0,1,1),(3,2,12,7)):
                with self.subTest(mode=mode,box=box):
                    crop=None if box is None else dict(x=box[0],y=box[1],width=box[2]-box[0],height=box[3]-box[1])
                    result=await render_region(self.path,crop)
                    expected=image if box is None else image.crop(box)
                    actual=self.decoded(result)
                    self.assertEqual(actual.mode,expected.mode)
                    self.assertEqual(actual.tobytes(),expected.tobytes())
                    self.assertEqual(result.geometry.region.model_dump(),crop or dict(x=0,y=0,width=19,height=11))

    async def test_all_eight_display_orientations_agree_with_independent_pixel_oracle(self):
        source=self.pattern()
        for orientation in range(1,9):
            with self.subTest(orientation=orientation):
                exif=Image.Exif()
                exif[274]=orientation
                source.save(self.path,format='PNG',exif=exif)
                with Image.open(self.path) as raw:expected=ImageOps.exif_transpose(raw)
                result=await render_region(self.path)
                self.assertEqual((result.geometry.source.width,result.geometry.source.height),expected.size)
                self.assertEqual(self.decoded(result).tobytes(),expected.tobytes())
                region=dict(x=expected.width-3,y=expected.height-2,width=3,height=2)
                result=await render_region(self.path,region)
                self.assertEqual(self.decoded(result).tobytes(),expected.crop((expected.width-3,expected.height-2,expected.width,expected.height)).tobytes())

    async def test_invalid_rectangles_report_original_display_dimensions_without_clipping(self):
        self.pattern().save(self.path,format='PNG')
        valid=dict(x=1,y=2,width=3,height=4)
        invalid=[[],{},dict(valid,extra=1)]
        invalid += [dict(valid,**{key:value}) for key,value in
            [('x',True),('x',1.0),('y',-1),('width',False),('width',0),('height',-1),('x',19),('y',11),('width',19),('height',11)]]
        for crop in invalid:
            with self.subTest(crop=crop):
                with self.assertRaises(PreviewFailure) as caught:await render_region(self.path,crop)
                self.assertEqual((caught.exception.code,caught.exception.width,caught.exception.height),('InvalidCrop',19,11))

    async def test_wide_square_and_thin_budget_geometry_is_real_and_never_enlarged(self):
        for size,expected in [((2500,2000),(1717,1373)),((3000,3000),(1536,1536)),((4096,4),(2048,2)),((19,11),(19,11))]:
            with self.subTest(size=size):
                Image.new('RGB',size,(40,80,120)).save(self.path,format='PNG')
                result=await render_region(self.path)
                image=self.decoded(result)
                self.assertEqual(image.size,expected)
                self.assertEqual(image.getpixel((image.width//2,image.height//2)),(40,80,120))
                self.assertLessEqual(max(image.size),2048)
                self.assertLessEqual(image.width*image.height,2359296)

    async def test_alpha_reduction_preserves_edge_color_without_transparent_color_bleed(self):
        image=Image.new('RGBA',(4096,8),(0,255,0,0))
        image.paste((255,0,0,255),(0,0,2048,8))
        image.save(self.path,format='PNG')
        result=await render_region(self.path)
        output=self.decoded(result)
        self.assertEqual(output.mode,'RGBA')
        transition=[pixel for pixel in output.get_flattened_data() if 0<pixel[3]<255]
        self.assertTrue(transition)
        self.assertTrue(all(pixel[0]>=254 and pixel[1:3]==(0,0) for pixel in transition))

    async def test_gray_16bit_gray_and_embedded_srgb_profile_convert_predictably(self):
        gray=Image.new('L',(2,1))
        gray.putdata([0,255])
        gray.save(self.path,format='PNG')
        self.assertEqual(list(self.decoded(await render_region(self.path)).get_flattened_data()),[(0,0,0),(255,255,255)])
        gray16=Image.new('I;16',(2,1))
        gray16.putdata([0,65535])
        gray16.save(self.path,format='PNG')
        self.assertEqual(list(self.decoded(await render_region(self.path)).get_flattened_data()),[(0,0,0),(255,255,255)])
        profile=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
        source=self.pattern()
        source.save(self.path,format='PNG',icc_profile=profile)
        output=self.decoded(await render_region(self.path))
        self.assertLessEqual(max(abs(a-b) for a,b in zip(output.tobytes(),source.tobytes())),1)

    async def test_repeated_resampling_uses_original_region_not_previous_candidate(self):
        image=Image.new('RGB',(257,129))
        for y in range(129):
            for x in range(257):image.putpixel((x,y),((x*y)%256,(x*11)%256,(y*7)%256))
        image.save(self.path,format='PNG')
        async def spawn(*command,**options):
            options['env']={**options['env'],'PYTHONPATH':str(Path(__file__).resolve().parent.parent)}
            return await asyncio.create_subprocess_exec(sys.executable,
                str(Path(__file__).parent/'fixtures'/'preview_geometry_child.py'),**options)
        supervisor=PreviewSupervisor(child_factory=lambda env:PreviewChild(env,spawn=spawn))
        raw=await supervisor.run(json.dumps({'source':str(self.path)}).encode())
        result=json.loads(raw)
        self.assertNotIn('error_code',result,result)
        self.assertTrue(result['repeated_matches_fresh'])

    async def test_geometry_worker_cancellation_discards_intermediate_with_owned_workspace(self):
        Image.new('RGB',(3000,3000),(20,40,60)).save(self.path,format='PNG')
        started,release=asyncio.Event(),asyncio.Event()
        owned=[]
        from foundry_mcp_server.image_preview_workspace import PreviewWorkspace
        class Workspace(PreviewWorkspace):
            def __enter__(self):
                result=super().__enter__()
                owned.append(self.path)
                return result
        async def spawn(*command,**options):
            child=await asyncio.create_subprocess_exec(*command,**options)
            started.set()
            await release.wait()
            return child
        supervisor=PreviewSupervisor(workspace_factory=Workspace,child_factory=lambda env:PreviewChild(env,spawn=spawn))
        task=asyncio.create_task(render_region(self.path,supervisor=supervisor))
        await started.wait()
        task.cancel()
        release.set()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertTrue(all(not path.exists() for path in owned))
        self.assertTrue(self.path.exists())

    async def test_parent_rejects_bad_geometry_mismatched_png_and_symlink_artifacts(self):
        image=self.pattern()
        image.save(self.path,format='PNG')
        png=self.path.read_bytes()
        from foundry_mcp_server.image_preview_workspace import PreviewWorkspace
        for case in ('bad_geometry','bad_png','wrong_dimensions','symlink','unknown_field'):
            async def run(payload,*,metrics,timeout,collect):
                geometry=dict(source=dict(width=19,height=11,mime_type='image/png',
                    size_bytes=len(png),frame_policy='still'),region=dict(x=0,y=0,width=19,height=11),width=19,height=11)
                if case=='bad_geometry':geometry['region']['x']=1
                if case=='unknown_field':geometry['extra']='forbidden'
                with PreviewWorkspace() as workspace:
                    artifact=workspace.path/'region.png'
                    if case=='symlink':artifact.symlink_to(self.path)
                    else:
                        data=bytearray(png)
                        if case=='bad_png':data[:8]=b'invalid!'
                        if case=='wrong_dimensions':data[16:20]=(18).to_bytes(4,'big')
                        artifact.write_bytes(data)
                    return collect(workspace,json.dumps({'geometry':geometry}).encode())
            with self.subTest(case=case):
                with self.assertRaises(PreviewFailure) as caught:
                    await render_region(self.path,supervisor=Mock(run=run))
                self.assertEqual(caught.exception.code,'ImageProcessingFailed')


class CoordinateTests(unittest.TestCase):
    def test_exact_output_budget_and_rounding_examples(self):
        for dimensions,expected in [((10000,10000),(1536,1536)),((10000,5000),(2048,1024)),((32768,1),(2048,1)),((1,32768),(1,2048)),((7,3),(7,3))]:
            self.assertEqual(output_dimensions(*dimensions),expected)
        for width in (1,2,1536,2048,2049,8191,32768):
            for height in (1,7,1536,2501,32768):
                w,h=output_dimensions(width,height)
                self.assertLessEqual(max(w,h),2048)
                self.assertLessEqual(w*h,2359296)
                self.assertLessEqual(w,width)
                self.assertLessEqual(h,height)

    def test_overview_and_nested_crop_mapping_use_exclusive_edges(self):
        whole=dict(x=0,y=0,width=10000,height=5000)
        detail=preview_to_source(whole,2048,1024,dict(x=1474,y=634,width=262,height=197))
        self.assertEqual(detail,dict(x=7197,y=3095,width=1280,height=963))
        nested=preview_to_source(dict(x=7200,y=3100,width=1280,height=960),640,480,dict(x=10,y=20,width=100,height=80))
        self.assertEqual(nested,dict(x=7220,y=3140,width=200,height=160))
