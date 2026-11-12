"""Encoding policy seams plus independently decoded real supervised artifacts."""
import asyncio
import io
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import Mock

from PIL import Image,PngImagePlugin

from foundry_mcp_server.image_preview_artifact import inspect_artifact
from foundry_mcp_server.image_preview_encode import encode_region,verify_candidate
from foundry_mcp_server.image_preview_failure import PreviewFailure
from foundry_mcp_server.image_preview_process import render_preview
from foundry_mcp_server.image_preview_supervisor import PreviewSupervisor
from foundry_mcp_server.image_preview_workspace import PreviewWorkspace


class PolicyTests(unittest.TestCase):
    def exercise(self,sizes,*,width=100,height=80,max_bytes=10,clock=lambda:0):
        calls,scales=[],[]
        region=Mock(width=width,height=height)
        region.resample.side_effect=lambda w,h:scales.append((w,h)) or (w,h)
        sizes=iter(sizes)
        def write(image,path,mime,quality):
            calls.append((*image,mime,quality))
            path.write_bytes(b'x'*next(sizes))
        def verify(path,w,h,mime):return dict(width=w,height=h,mime_type=mime,size_bytes=path.stat().st_size)
        return region,write,verify,calls,scales

    def test_first_compliant_format_stops_png_then_webp90_then_webp82(self):
        for sizes,expected in [([10],[('image/png',None)]),([11,10],[('image/png',None),('image/webp',90)]),
                ([11,11,10],[('image/png',None),('image/webp',90),('image/webp',82)])]:
            with self.subTest(sizes=sizes),tempfile.TemporaryDirectory() as directory:
                region,write,verify,calls,scales=self.exercise(sizes)
                result=encode_region(region,directory,max_bytes=10,writer=write,verify=verify,clock=lambda:0)
                self.assertEqual([(mime,q) for _,_,mime,q in calls],expected)
                self.assertEqual(scales,[(100,80)])
                self.assertEqual(result['size_bytes'],10)
                self.assertEqual((Path(directory)/'preview.bin').read_bytes(),b'x'*10)
                self.assertFalse((Path(directory)/'candidate.bin').exists())

    def test_reduction_restarts_choices_and_uses_original_for_every_candidate_size(self):
        with tempfile.TemporaryDirectory() as directory:
            region,write,verify,calls,scales=self.exercise([11]*6+[10])
            result=encode_region(region,directory,max_bytes=10,writer=write,verify=verify,clock=lambda:0)
            self.assertEqual(scales,[(100,80),(85,68),(72,57)])
            self.assertEqual([(w,h) for w,h,_,_ in calls],[(100,80)]*3+[(85,68)]*3+[(72,57)])
            self.assertEqual((result['width'],result['height'],result['mime_type']),(72,57,'image/png'))

    def test_progress_reaches_one_pixel_and_fails_cleanly_when_nothing_can_fit(self):
        with tempfile.TemporaryDirectory() as directory:
            region,write,verify,calls,scales=self.exercise([11]*6,width=1,height=2)
            with self.assertRaises(PreviewFailure) as caught:
                encode_region(region,directory,max_bytes=10,writer=write,verify=verify,clock=lambda:0)
            self.assertEqual(caught.exception.code,'ImageProcessingFailed')
            self.assertEqual(scales,[(1,2),(1,1)])
            self.assertEqual(len(calls),6)
            self.assertEqual(list(Path(directory).iterdir()),[])

    def test_deadline_covers_encoding_and_verification_and_removes_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            region,write,verify,calls,scales=self.exercise([5])
            time=[0]
            def delayed(*args):write(*args);time[0]=2
            with self.assertRaises(PreviewFailure) as caught:
                encode_region(region,directory,max_bytes=10,writer=delayed,verify=verify,clock=lambda:time[0],deadline=1)
            self.assertEqual(caught.exception.code,'ImageProcessingTimeout')
            self.assertEqual(len(calls),1)
            self.assertEqual(list(Path(directory).iterdir()),[])

    def test_inconsistent_verifier_result_cannot_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            region,write,_,calls,scales=self.exercise([5])
            with self.assertRaises(PreviewFailure):
                encode_region(region,directory,max_bytes=10,writer=write,verify=lambda *args:{'size_bytes':5},clock=lambda:0)
            self.assertEqual(list(Path(directory).iterdir()),[])

    def test_empty_candidate_is_an_encoder_failure_not_a_size_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            region,write,verify,calls,scales=self.exercise([0,5])
            with self.assertRaises(PreviewFailure) as caught:
                encode_region(region,directory,max_bytes=10,writer=write,verify=verify,clock=lambda:0)
            self.assertEqual(caught.exception.code,'ImageProcessingFailed')
            self.assertEqual(len(calls),1)
            self.assertEqual(list(Path(directory).iterdir()),[])

    def test_corrupt_generated_artifact_reports_processing_failure_not_source_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'candidate'
            path.write_bytes(b'incomplete-generated-image')
            with self.assertRaises(PreviewFailure) as caught:verify_candidate(path,1,1,'image/png')
            self.assertEqual(caught.exception.code,'ImageProcessingFailed')

    def test_writer_exception_cleans_partial_candidate_without_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            region,_,verify,calls,scales=self.exercise([])
            def write(image,path,mime,quality):
                path.write_bytes(b'partial')
                raise OSError('controlled encoder failure')
            with self.assertRaisesRegex(OSError,'controlled encoder failure'):
                encode_region(region,directory,writer=write,verify=verify,clock=lambda:0)
            self.assertEqual(list(Path(directory).iterdir()),[])


class RenderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/'original'

    def decode(self,result):
        image=Image.open(io.BytesIO(result.data))
        image.load()
        geometry=result.geometry
        self.assertEqual(image.size,(geometry.width,geometry.height))
        self.assertEqual(geometry.size_bytes,len(result.data))
        self.assertEqual(Image.MIME[image.format],geometry.mime_type)
        self.assertLessEqual(len(result.data),2*1024*1024)
        self.assertLessEqual(max(image.size),2048)
        self.assertLessEqual(image.width*image.height,2359296)
        print('synthetic preview:',geometry.mime_type,geometry.width,geometry.height,geometry.size_bytes)
        return image

    async def test_png_preference_lossless_native_crop_and_alpha(self):
        source=Image.new('RGBA',(192,128))
        for y in range(128):
            for x in range(192):source.putpixel((x,y),(x,y,(x+y)%256,(x*3+y)%256))
        source.save(self.path,format='PNG')
        result=await render_preview(self.path,dict(x=170,y=110,width=22,height=18))
        self.assertEqual(result.geometry.mime_type,'image/png')
        self.assertEqual(self.decode(result).tobytes(),source.crop((170,110,192,128)).tobytes())

    async def test_real_high_entropy_webp_fallback_and_lossy_tolerance(self):
        source=Image.frombytes('L',(1536,1536),random.Random(601).randbytes(1536**2)).convert('RGB')
        source.save(self.path,format='PNG')
        result=await render_preview(self.path)
        output=self.decode(result).convert('RGB')
        self.assertEqual(result.geometry.mime_type,'image/webp')
        expected=source.resize(output.size,Image.Resampling.LANCZOS)
        error=sum(abs(a-b) for a,b in zip(output.tobytes(),expected.tobytes()))/(output.width*output.height*3)
        self.assertLess(error,7)

    async def test_real_random_alpha_requires_reduction_and_retains_alpha_channel(self):
        source=Image.frombytes('RGBA',(1536,1536),random.Random(602).randbytes(1536**2*4))
        source.save(self.path,format='PNG')
        result=await render_preview(self.path)
        output=self.decode(result)
        self.assertEqual(output.mode,'RGBA')
        self.assertLess(output.width,1536)
        self.assertEqual(result.geometry.region.model_dump(),dict(x=0,y=0,width=1536,height=1536))
        expected=source.getchannel('A').resize(output.size,Image.Resampling.LANCZOS)
        actual=output.getchannel('A')
        error=sum(abs(a-b) for a,b in zip(actual.tobytes(),expected.tobytes()))/(actual.width*actual.height)
        self.assertLess(error,2)

    async def test_source_metadata_is_removed_and_resolution_is_generated(self):
        source=Image.new('RGB',(19,11),(30,60,90))
        exif=Image.Exif()
        exif[271]='FixtureCamera'
        exif[315]='FixtureAuthor'
        comments=PngImagePlugin.PngInfo()
        comments.add_text('Description','Fixture source-only comment')
        source.save(self.path,format='PNG',exif=exif,pnginfo=comments,dpi=(300,300))
        result=await render_preview(self.path)
        output=self.decode(result)
        self.assertEqual(len(output.getexif()),0)
        self.assertFalse(set(output.info)&{'exif','icc_profile','xmp','comment','Description'})
        self.assertAlmostEqual(output.info['dpi'][0],96,delta=0.02)

    async def test_parent_rejects_forged_mime_dimensions_size_and_partial_bytes(self):
        source=Image.new('RGB',(19,11),(30,60,90))
        source.save(self.path,format='PNG')
        good=await render_preview(self.path)
        for case in ('mime','dimensions','size','truncated'):
            async def run(payload,*,metrics,timeout,collect):
                metadata=good.geometry.model_dump()
                if case=='mime':metadata['mime_type']='image/webp'
                if case=='dimensions':metadata['width']=18
                if case=='size':metadata['size_bytes']+=1
                with PreviewWorkspace() as workspace:
                    (workspace.path/'preview.bin').write_bytes(good.data[:-1] if case=='truncated' else good.data)
                    return collect(workspace,json.dumps({'artifact':metadata}).encode())
            with self.subTest(case=case):
                with self.assertRaises(PreviewFailure) as caught:await render_preview(self.path,supervisor=Mock(run=run))
                self.assertEqual(caught.exception.code,'ImageProcessingFailed')

    async def test_hard_worker_deadline_removes_render_scratch_and_preserves_original(self):
        Image.new('RGB',(3000,3000),(20,40,60)).save(self.path,format='PNG')
        owned=[]
        class Workspace(PreviewWorkspace):
            def __enter__(self):
                result=super().__enter__()
                owned.append(self.path)
                return result
        supervisor=PreviewSupervisor(workspace_factory=Workspace)
        with self.assertRaises(PreviewFailure) as caught:
            await render_preview(self.path,supervisor=supervisor,timeout=0.001)
        self.assertEqual(caught.exception.code,'ImageProcessingTimeout')
        self.assertTrue(owned)
        self.assertTrue(all(not path.exists() for path in owned))
        self.assertTrue(self.path.exists())


class ContainerTests(unittest.TestCase):
    def test_independent_png_and_webp_headers_and_malformed_containers(self):
        for fmt,mode in [('PNG','RGB'),('PNG','RGBA'),('WEBP','RGB'),('WEBP','RGBA')]:
            with self.subTest(format=fmt,mode=mode):
                stream=io.BytesIO()
                Image.new(mode,(17,11),(20,40,60,100) if mode=='RGBA' else (20,40,60)).save(stream,format=fmt)
                data=stream.getvalue()
                self.assertEqual(inspect_artifact(data),dict(width=17,height=11,mime_type='image/'+fmt.lower(),size_bytes=len(data)))
                for malformed in (data[:-1],data+b'x',b'not-an-image',data[:16]+b'x'*16+data[32:]):
                    with self.assertRaises(PreviewFailure):inspect_artifact(malformed)
