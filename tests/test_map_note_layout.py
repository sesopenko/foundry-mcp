"""Independent placement/coverage/pixel expectations and real annotated encoding."""
import asyncio
import io
import json
import random
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock

from PIL import Image,ImageChops

from foundry_mcp_server.image_preview_failure import PreviewFailure
from foundry_mcp_server.image_preview_encode import encode_region
from foundry_mcp_server.image_preview_child import PreviewChild
from foundry_mcp_server.image_preview_supervisor import PreviewSupervisor
from foundry_mcp_server.image_preview_workspace import PreviewWorkspace
from foundry_mcp_server.map_note_layout import layout_notes,candidates,Box
from foundry_mcp_server.map_note_render import render_annotated,NoteRenderSummary
from foundry_mcp_server.map_note_glyph_probe import probe_glyphs
from foundry_mcp_server.map_note_layout_audit import audit


class LayoutTests(unittest.TestCase):
    def layout(self,pins,*,width=500,height=500,region=None,sizes=None,total=None):
        region=region if region is not None else dict(x=100,y=200,width=1000,height=1000)
        sizes=sizes if sizes is not None else {key:(22,14) for key,x,y in pins}
        return layout_notes(pins,len(pins) if total is None else total,region,width,height,sizes)

    def test_independent_crop_projection_and_numeric_order(self):
        result=self.layout([('N10',600,700),('N2',300,400),('N1',900,1000)])
        self.assertEqual([p.key for p in result.placements],['N1','N2','N10'])
        # (300-100)*500/1000=100, (400-200)*500/1000=100.
        p=result.placements[1]
        self.assertEqual(p.pin,(100,100));self.assertEqual(p.direction,'NE')
        self.assertEqual(p.label,Box(107,80,22,14))
        self.assertEqual(p.footprint,Box(98,80,31,23))
        self.assertEqual(p.leader_end,(107,93))

    def test_all_directions_and_four_blank_pixel_gaps(self):
        result=list(candidates(100,100,22,14))
        self.assertEqual([p[0] for p in result],['NE','NW','SE','SW','E','W','N','S'])
        self.assertEqual([(p[1].x,p[1].y) for p in result],[(107,80),(72,80),(107,107),(72,107),(107,93),(72,93),(89,80),(89,107)])
        for direction,label,footprint,end in result:
            self.assertTrue(footprint.inside(200,200))
            self.assertTrue(footprint.x<=98 and footprint.y<=98)
            self.assertTrue(footprint.x+footprint.width>=103 and footprint.y+footprint.height>=103)

    def test_edges_corners_and_tiny_image_are_explicit_omissions(self):
        region=dict(x=0,y=0,width=500,height=500)
        for x,y in [(0,0),(499,0),(0,499),(499,499),(0,250),(499,250),(250,0),(250,499)]:
            with self.subTest(x=x,y=y):
                result=self.layout([('N1',x,y)],region=region)
                self.assertEqual(result.metadata()['omission_reasons'],{'edge':1})
        result=self.layout([('N1',100,200)],width=1,height=1)
        self.assertEqual(result.metadata()['omission_reasons'],{'tiny_image':1})
        self.assertFalse(result.metadata()['complete'])

    def test_overlap_density_limit_and_exact_coverage_ceiling(self):
        pins=[('N'+str(i+1),200+i*40,300+i*40) for i in range(10)]
        result=self.layout(pins,width=100,height=100)
        self.assertLessEqual(sum(p.label.width*p.label.height for p in result.placements)*20,10000)
        self.assertIn('density',dict(result.omission_reasons))
        same=self.layout([('N1',500,500),('N2',500,500)])
        self.assertEqual(same.metadata()['omission_reasons'],{'collision':1})
        limited=self.layout([('N1',500,500)],total=150)
        self.assertEqual(limited.metadata()['omission_reasons'],{'limit':149})
        self.assertEqual(limited.metadata()['omitted_count'],149)
        NoteRenderSummary.model_validate(limited.metadata())

    def test_footprints_are_disjoint_and_zero_notes_complete(self):
        pins=[('N'+str(i+1),130+(i%10)*90,240+(i//10)*90) for i in range(100)]
        result=self.layout(pins)
        for i,p in enumerate(result.placements):
            self.assertTrue(p.footprint.inside(500,500))
            self.assertTrue(all(not p.footprint.overlaps(q.footprint) for q in result.placements[i+1:]))
        self.assertLessEqual(sum(p.label.width*p.label.height for p in result.placements)*20,500**2)
        self.assertEqual(self.layout([]).metadata(),dict(total_in_region=0,rendered_count=0,omitted_count=0,complete=True,keys=[],omission_reasons={}))

    def test_forged_inputs_and_summary_cannot_claim_completion(self):
        for pins,total in [([('N0',500,500)],1),([('N1',True,500)],1),([('N1',1100,500)],1),([('N1',float('nan'),500)],1),([],1)]:
            with self.subTest(pins=pins),self.assertRaises(PreviewFailure):self.layout(pins,total=total)
        valid=self.layout([('N1',500,500)]).metadata()
        for change in [dict(rendered_count=2),dict(keys=['N999','N1']),dict(complete=False),dict(omission_reasons={'collision':True})]:
            with self.subTest(change=change),self.assertRaises(ValueError):NoteRenderSummary.model_validate({**valid,**change})


class NativeLayoutTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/'original'

    async def test_changed_pixels_stay_inside_predicted_mark_extents_on_dark_light_alpha(self):
        for color in [(0,0,0,255),(255,255,255,255),(40,80,120,0)]:
            source=Image.new('RGBA',(500,500),color);source.save(self.path,format='PNG')
            result=await render_annotated(self.path,None,[('N1',250,250)],1)
            output=Image.open(io.BytesIO(result.data)).convert('RGBA')
            self.assertEqual(result.notes.keys,['N1'])
            # N1 is22x14 at native final-size, complete extent from(248,230) to(279,253).
            # Ignore hidden RGB of alpha0 pixels: premultiplied visual comparison.
            background=Image.new('RGBA',source.size,'black')
            diff=ImageChops.difference(Image.alpha_composite(background,source).convert('RGB'),Image.alpha_composite(background,output).convert('RGB'))
            left,top,right,bottom=diff.getbbox()
            self.assertTrue(left>=248 and top>=230 and right<=279 and bottom<=253)
            self.assertEqual(output.getpixel((250,250)),(255,255,255,255))
            self.assertEqual(result.geometry.region.width,500)

    async def test_repeated_render_one_pixel_zero_notes_and_unchanged_source(self):
        source=Image.new('RGB',(500,500),(30,60,90));source.save(self.path,format='PNG')
        before=self.path.read_bytes()
        first=await render_annotated(self.path,None,[('N1',250,250)],1)
        second=await render_annotated(self.path,None,[('N1',250,250)],1)
        self.assertEqual(first.data,second.data)
        tiny=await render_annotated(self.path,dict(x=250,y=250,width=1,height=1),[('N1',250,250)],1)
        self.assertEqual(tiny.notes.omission_reasons,{'tiny_image':1})
        self.assertEqual(Image.open(io.BytesIO(tiny.data)).convert('RGB').getpixel((0,0)),(30,60,90))
        empty=await render_annotated(self.path,None,[],0)
        self.assertTrue(empty.notes.complete);self.assertEqual(empty.notes.rendered_count,0)
        self.assertEqual(self.path.read_bytes(),before)

    async def test_nonfinite_private_pin_reports_fixed_failure_before_serialization(self):
        Image.new('RGB',(500,500)).save(self.path,format='PNG')
        with self.assertRaises(PreviewFailure) as caught:
            await render_annotated(self.path,None,[('N1',float('nan'),250)],1)
        self.assertEqual(caught.exception.code,'InvalidOperation')

    async def test_real_alpha_noise_reduces_but_recomposes_fixed_size_keys(self):
        source=Image.frombytes('RGBA',(1536,1536),random.Random(602).randbytes(1536**2*4));source.save(self.path,format='PNG')
        result=await render_annotated(self.path,None,[('N1',768,768)],1)
        self.assertLess(result.geometry.width,1536);self.assertLessEqual(len(result.data),2*1024**2)
        self.assertEqual(result.notes.keys,['N1']);self.assertEqual(result.notes.omitted_count,0)
        output=Image.open(io.BytesIO(result.data)).convert('RGBA')
        center=result.geometry.width//2
        self.assertEqual(output.getpixel((center,center))[3],255)
        glyph=await probe_glyphs(['N1'])
        mask=Image.open(io.BytesIO(glyph.png)).convert('RGBA')
        self.assertEqual(mask.size,(22,14))
        core=[(x,y) for y in range(14) for x in range(22) if mask.getpixel((x,y))==(255,255,255,255)]
        self.assertGreater(len(core),10)
        # At final coordinates the14px glyph remains intact after real byte
        # retries. Downsampling a prior annotated candidate fails this mask.
        self.assertTrue(all(output.getpixel((center+7+x,center-20+y))[3]==255 for x,y in core))

    async def test_parent_rejects_forged_keys_counts_region_and_truncated_bytes(self):
        Image.new('RGB',(500,500),(30,60,90)).save(self.path,format='PNG')
        good=await render_annotated(self.path,None,[('N1',250,250)],1)
        for case in ('key','count','region','truncated'):
            async def run(payload,*,metrics,timeout,collect):
                artifact={**good.geometry.model_dump(),'map_notes':good.notes.model_dump()}
                if case=='key':artifact['map_notes']['keys']=['N999']
                if case=='count':artifact['map_notes']['rendered_count']=2
                if case=='region':artifact['region']['width']=499
                with PreviewWorkspace() as workspace:
                    (workspace.path/'preview.bin').write_bytes(good.data[:-1] if case=='truncated' else good.data)
                    return collect(workspace,json.dumps({'artifact':artifact}).encode())
            with self.subTest(case=case),self.assertRaises(PreviewFailure) as caught:
                await render_annotated(self.path,None,[('N1',250,250)],1,supervisor=Mock(run=run))
            self.assertEqual(caught.exception.code,'ImageProcessingFailed')

    async def test_timeout_resource_failure_and_cancellation_cleanup(self):
        Image.new('RGB',(500,500)).save(self.path,format='PNG');owned=[]
        class Workspace(PreviewWorkspace):
            def __enter__(self):
                result=super().__enter__();owned.append(self.path);return result
        for options,code in [(dict(max_scratch=1),'ImageScratchLimit'),(dict(max_rss=1),'ImageMemoryLimit'),(dict(timeout=0.000001),'ImageProcessingTimeout')]:
            with self.subTest(code=code),self.assertRaises(PreviewFailure) as caught:
                await render_annotated(self.path,None,[('N1',250,250)],1,timeout=options.get('timeout',90),supervisor=PreviewSupervisor(workspace_factory=Workspace,**options))
            self.assertEqual(caught.exception.code,code)
            self.assertTrue(all(not path.exists() for path in owned))
            self.assertTrue(self.path.exists())

    async def test_cancel_after_owned_real_child_spawn_reaps_and_cleans(self):
        Image.new('RGB',(500,500)).save(self.path,format='PNG')
        started=asyncio.Event();children=[];paths=[]
        class Child(PreviewChild):
            async def start(inner):
                await super().start();children.append(inner);started.set()
                await asyncio.Future()
        class Workspace(PreviewWorkspace):
            def __enter__(inner):
                result=super().__enter__();paths.append(inner.path);return result
        supervisor=PreviewSupervisor(child_factory=Child,workspace_factory=Workspace)
        task=asyncio.create_task(render_annotated(self.path,None,[('N1',250,250)],1,supervisor=supervisor))
        await asyncio.wait_for(started.wait(),3);task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertTrue(all(c.process.returncode is not None for c in children))
        self.assertTrue(all(not path.exists() for path in paths))
        self.assertTrue(self.path.exists())

    async def test_bounded_synthetic_visual_audit_reports_sparse_and_dense_honestly(self):
        output=Path(self.directory.name)/'visual'
        results=await audit(output)
        self.assertEqual([row['case'] for row in results],['overview','detail','dense'])
        self.assertEqual([row['notes']['rendered_count'] for row in results],[20,4,1])
        self.assertEqual(results[2]['notes']['omission_reasons'],{'collision':99})
        for row in results:
            self.assertEqual((output/(row['case']+'.png')).stat().st_size,row['bytes'])
            self.assertGreater(row['metrics']['peak_rss_bytes'],0)


class AnnotatedPolicyTests(unittest.TestCase):
    def test_each_format_attempt_recomposes_unannotated_original_and_returns_final_notes(self):
        scales=[];composed=[];written=[]
        region=Mock(width=500,height=400)
        def resample(w,h):
            base=Mock(width=w,height=h);scales.append(base);return base
        region.resample.side_effect=resample
        def compose(base):
            self.assertIn(base,scales)
            result=Mock(width=base.width,height=base.height)
            composed.append((base,result))
            return result,{'attempt':len(composed)}
        def writer(image,path,mime,quality):
            written.append((image,mime,quality))
            path.write_bytes(b'x'*(11 if len(written)<5 else 10))
        def verify(path,w,h,mime):return dict(width=w,height=h,mime_type=mime,size_bytes=path.stat().st_size)
        with tempfile.TemporaryDirectory() as directory:
            actual=encode_region(region,directory,max_bytes=10,compose=compose,writer=writer,verify=verify,clock=lambda:0)
        self.assertEqual([(base.width,base.height) for base in scales],[(500,400),(425,340)])
        self.assertEqual([base for base,result in composed],[scales[0]]*3+[scales[1]]*2)
        self.assertEqual([result for base,result in composed],[image for image,mime,q in written])
        self.assertEqual(actual['map_notes'],{'attempt':5})
