"""Small deterministic generator/oracle/report checks; full maps are separate."""
from io import BytesIO
from pathlib import Path
import tempfile
import json
import unittest
from unittest.mock import patch

from PIL import Image

from image_preview_measurement_harness import generate_map,region_oracle,ResourceEvidence,measure_maps,verify_delivery
from foundry_mcp_server.image_preview_resources import WorkerMetrics
from foundry_mcp_server.image_preview_failure import PreviewFailure
from foundry_mcp_server.mcp_server import image_previews


class MeasurementTests(unittest.TestCase):
    def test_delivery_oracle_checks_actual_decoding_fields_and_byte_budget(self):
        stream=BytesIO()
        Image.new('RGB',(5,3),'red').save(stream,format='PNG')
        data=stream.getvalue()
        expected=dict(width=5,height=3,mime_type='image/png',size_bytes=len(data))
        verify_delivery(data,expected)
        for change in (dict(width=6),dict(height=4),dict(mime_type='image/webp'),dict(size_bytes=len(data)+1)):
            with self.assertRaises(RuntimeError):verify_delivery(data,{**expected,**change})
    def test_streamed_map_matches_independent_decoder_and_scalar_oracle(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'opaque'
            result=generate_map(path,79,63,117)
            self.assertEqual(result['cached_row_bytes'],16*79*3)
            self.assertEqual(result['size_bytes'],path.stat().st_size)
            with Image.open(path) as image:
                self.assertEqual(image.size,(79,63))
                self.assertEqual(image.tobytes(),region_oracle(79,63,117,dict(x=0,y=0,width=79,height=63)))
                for x,y in ((0,0),(7,7),(39,31),(71,55),(78,62)):
                    self.assertEqual(image.crop((x,y,x+1,y+1)).tobytes(),region_oracle(79,63,117,dict(x=x,y=y,width=1,height=1)))

    def test_bounds_reject_before_creating_files_or_giant_oracles(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'opaque'
            for width,height,seed in ((True,100,0),(31,100,0),(32769,100,0),(20000,20000,0),(64,64,256)):
                with self.assertRaises(ValueError):generate_map(path,width,height,seed)
            self.assertFalse(path.exists())
        with self.assertRaises(ValueError):region_oracle(10000,10000,0,dict(x=0,y=0,width=10000,height=10000))

    def test_resource_summary_requires_real_positive_bounded_observations(self):
        evidence=ResourceEvidence()
        with self.assertRaises(RuntimeError):evidence.summary()
        for metrics in (WorkerMetrics(),WorkerMetrics(1073741825,0,1,1),WorkerMetrics(1,2147483649,1,1),WorkerMetrics(1,0,91,1)):
            with self.assertRaises(RuntimeError):evidence.add(metrics)
        evidence.add(WorkerMetrics(40000000,2000,.2,3))
        evidence.add(WorkerMetrics(60000000,1000,.1,2))
        summary=evidence.summary()
        self.assertEqual(summary['operations'],2)
        self.assertEqual(summary['peak_rss_bytes'],60000000)
        self.assertEqual(summary['peak_scratch_bytes'],2000)
        self.assertAlmostEqual(summary['total_elapsed_seconds'],.3)
        self.assertEqual(evidence.summary(1)['operations'],1)
        self.assertEqual(evidence.summary(1)['max_elapsed_seconds'],.1)


class SmallMeasurementWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_measurement_still_reports_actual_dispatched_call_count(self):
        with patch.object(image_previews,'probe_image',side_effect=PreviewFailure('UnsupportedImage')):
            report=await measure_maps(((64,64),))
        self.assertFalse(report['passed'])
        self.assertEqual(report['calls'],2)  # actual discovery plus failed info
        self.assertEqual(report['maps'],[])

    async def test_small_real_workflow_checks_measurement_logic_and_cleanup(self):
        report=await measure_maps(((64,64),(96,64)))
        self.assertTrue(report['passed'],report)
        self.assertEqual(len(report['maps']),2)
        self.assertLessEqual(report['calls'],80)
        self.assertTrue(all(m['transfers']==1 for m in report['maps']))
        self.assertGreater(report['resources']['operations'],0)
        def private_fields(value):
            if isinstance(value,dict):
                self.assertFalse({'url','source_id','path','seed'}&value.keys())
                for item in value.values():private_fields(item)
            elif isinstance(value,list):
                for item in value:private_fields(item)
        private_fields(report)
        self.assertNotIn('https://',json.dumps(report))
