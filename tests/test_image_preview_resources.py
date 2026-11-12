"""Resource observations and budget policy without admission or child cleanup."""
import builtins
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from foundry_mcp_server.image_preview_resources import ResourceMonitor,WorkerMetrics,sample_resources
from foundry_mcp_server.image_preview_worker import PreviewFailure


class ResourceTests(unittest.TestCase):
    def test_exact_limits_peak_retention_and_independent_limit_categories(self):
        monitor=ResourceMonitor(max_rss=100,max_scratch=200)
        metrics=WorkerMetrics()
        with patch('foundry_mcp_server.image_preview_resources.sample_resources',side_effect=[(100,200),(101,5),(1,201),(1,1)]):
            monitor.measure(1,'unused',metrics)
            for code in ('ImageMemoryLimit','ImageScratchLimit'):
                with self.assertRaises(PreviewFailure) as caught:monitor.measure(1,'unused',metrics)
                self.assertEqual(caught.exception.code,code)
            monitor.measure(1,'unused',metrics)
        self.assertEqual((metrics.peak_rss_bytes,metrics.peak_scratch_bytes,metrics.samples),(101,201,4))

    def test_real_rss_and_unique_open_unlinked_scratch_exclude_original_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=root/'original'
            source.write_bytes(b'x'*100000)
            scratch=root/'scratch'
            scratch.mkdir()
            (scratch/'foreign').symlink_to(source)
            with (scratch/'owned').open('w+b') as stream:
                stream.write(b'a'*5000)
                stream.flush()
                info=os.fstat(stream.fileno())
                expected=max(info.st_size,info.st_blocks*512)
                rss,usage=sample_resources(os.getpid(),scratch)
                self.assertGreater(rss,0)
                self.assertEqual(usage,expected)
                (scratch/'owned').unlink()
                self.assertEqual(sample_resources(os.getpid(),scratch)[1],expected)
            self.assertEqual(sample_resources(os.getpid(),scratch)[1],0)
            self.assertTrue(source.exists())

    def test_genuine_permission_denial_is_not_zero_usage_or_a_success(self):
        metrics=WorkerMetrics()
        with tempfile.TemporaryDirectory() as directory:
            with patch('os.scandir',side_effect=PermissionError('denied')):
                with self.assertRaises(PermissionError):ResourceMonitor().measure(os.getpid(),directory,metrics)
        self.assertEqual(metrics.samples,0)

    def test_real_resident_memory_is_compared_to_its_own_budget(self):
        metrics=WorkerMetrics()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(PreviewFailure) as caught:
                ResourceMonitor(max_rss=1).measure(os.getpid(),directory,metrics)
        self.assertEqual(caught.exception.code,'ImageMemoryLimit')
        self.assertGreater(metrics.peak_rss_bytes,1)

    def test_final_scratch_does_not_read_proc_and_checks_allocated_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'output').write_bytes(b'x'*5000)
            with patch('builtins.open',side_effect=AssertionError('must not read proc')):
                with self.assertRaises(PreviewFailure) as caught:
                    ResourceMonitor(max_scratch=4999).final_scratch(directory,WorkerMetrics())
            self.assertEqual(caught.exception.code,'ImageScratchLimit')

    def test_entry_scan_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            for index in range(3):(Path(directory)/str(index)).touch()
            with patch('foundry_mcp_server.image_preview_resources.MAX_SCRATCH_ENTRIES',2):
                with self.assertRaises(PreviewFailure) as caught:sample_resources(None,directory)
            self.assertEqual(caught.exception.code,'ImageScratchLimit')

    def test_real_process_exit_after_status_open_is_handled_without_false_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            child=subprocess.Popen([sys.executable,str(Path(__file__).parent/'fixtures'/'preview_resource_child.py'),'stall'],
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                env={**os.environ,'TMPDIR':directory})
            original_open=builtins.open
            def exit_after_open(path,*args,**kwargs):
                stream=original_open(path,*args,**kwargs)
                if path==f'/proc/{child.pid}/status':
                    child.kill()
                    child.wait(timeout=2)
                return stream
            try:
                with patch('builtins.open',exit_after_open):self.assertEqual(sample_resources(child.pid,directory),(0,0))
            finally:
                if child.poll() is None:child.kill()
                child.wait(timeout=2)

    @unittest.skipUnless(sys.platform=='linux' and os.geteuid()!=0,'Requires Linux/nonroot procfs ownership')
    def test_real_unreaped_exit_explains_proc_fd_denial(self):
        with tempfile.TemporaryDirectory() as directory:
            child=subprocess.Popen([sys.executable,str(Path(__file__).parent/'fixtures'/'preview_resource_child.py'),'good'],
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                env={**os.environ,'TMPDIR':directory})
            try:
                # Observe exit without reaping: deterministically retain the
                # exact kernel state responsible for root-owned proc fd entries.
                os.waitid(os.P_PID,child.pid,os.WEXITED|os.WNOWAIT)
                self.assertEqual(Path(f'/proc/{child.pid}/stat').read_text().split(') ',1)[1][0],'Z')
                self.assertEqual(Path(f'/proc/{child.pid}/fd').stat().st_uid,0)
                with self.assertRaises(PermissionError) as caught:
                    ResourceMonitor().measure(child.pid,directory,WorkerMetrics())
                self.assertEqual(caught.exception.errno,13)
            finally:
                child.wait(timeout=2)
