"""Coordinator contracts plus real composition; component internals tested separately."""
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import AsyncMock,Mock

from foundry_mcp_server import image_preview_limits as limits
from foundry_mcp_server.image_preview_child import PreviewChild
from foundry_mcp_server.image_preview_process import probe_image
from foundry_mcp_server.image_preview_resources import MONITOR_INTERVAL,ResourceMonitor,WorkerMetrics
from foundry_mcp_server.image_preview_supervisor import PreviewSupervisor
from foundry_mcp_server.image_preview_workspace import PreviewWorkspace
from foundry_mcp_server.image_preview_worker import PreviewFailure
from image_preview_fixtures import FixtureChildren


class ExitedChild:
    """Owned real unreaped child; deterministic completion/monitor handoff fixture."""
    def __init__(self, environment):
        self.environment=environment
        self.wait_confirmations=0

    async def start(self):
        self.process=subprocess.Popen([sys.executable,
            str(Path(__file__).parent/'fixtures'/'preview_resource_child.py'),'good'],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            env=self.environment)
        self.pid=self.process.pid
        os.waitid(os.P_PID,self.pid,os.WEXITED|os.WNOWAIT)
        self.fd_owner=Path(f'/proc/{self.pid}/fd').stat().st_uid
        self.state=Path(f'/proc/{self.pid}/stat').read_text().split(') ',1)[1][0]

    def exchange(self,payload):
        async def read():return self.process.stdout.read()
        self.output=asyncio.create_task(read())
        return self.output

    async def wait_finished(self,timeout):
        self.wait_confirmations+=1
        self.process.wait(timeout=timeout)
        return True

    async def close(self):
        self.process.wait(timeout=2)
        self.process.stdout.close()
        if hasattr(self,'output'):
            self.output.cancel()
            await asyncio.gather(self.output,return_exceptions=True)


@unittest.skipUnless(sys.platform=='linux','Preview monitoring requires Linux procfs')
class SupervisorTests(unittest.IsolatedAsyncioTestCase):
    def supervisor(self,fixture,**options):
        return PreviewSupervisor(child_factory=lambda env:PreviewChild(env,spawn=fixture.spawn),**options)

    def assert_clean(self,fixture):
        self.assertEqual(fixture.permissions,0o700)
        self.assertTrue(all(not path.exists() for path in fixture.scratch))
        self.assertTrue(all(child.returncode is not None for child in fixture.children))

    async def test_production_defaults_real_probe_and_private_metrics(self):
        supervisor=PreviewSupervisor()
        self.assertEqual((supervisor.monitor.max_rss,supervisor.monitor.max_scratch,supervisor.timeout),(1024**3,2*1024**3,90))
        self.assertEqual(limits.WORKER_CONCURRENCY,1)
        self.assertEqual((supervisor.admission.max_queued,supervisor.admission.queue_timeout),(8,90))
        self.assertLessEqual(MONITOR_INTERVAL,0.025)
        metrics=WorkerMetrics()
        with PreviewWorkspace() as source:
            from PIL import Image
            path=source.path/'original'
            Image.new('RGB',(19,11),(20,40,60)).save(path,format='PNG')
            result=await probe_image(path,supervisor=supervisor,metrics=metrics)
            self.assertEqual((result.width,result.height),(19,11))
            self.assertTrue(path.exists())
        self.assertGreater(metrics.peak_rss_bytes,0)
        self.assertLess(metrics.peak_rss_bytes,limits.WORKER_MAX_RSS)
        self.assertGreater(metrics.elapsed_seconds,0)
        self.assertNotIn('peak_rss_bytes',result.model_dump())

    async def test_real_rss_scratch_and_unlinked_exhaustion_then_recovery(self):
        for mode,code in [('rss','ImageMemoryLimit'),('scratch','ImageScratchLimit'),('unlinked','ImageScratchLimit')]:
            with self.subTest(mode=mode):
                fixture=FixtureChildren(mode)
                supervisor=self.supervisor(fixture,max_rss=24*1024**2,max_scratch=32768,timeout=3,interval=0.01)
                metrics=WorkerMetrics()
                with self.assertRaises(PreviewFailure) as caught:await supervisor.run(b'{}',metrics=metrics)
                self.assertEqual(caught.exception.code,code)
                self.assertGreater(metrics.peak_rss_bytes if mode=='rss' else metrics.peak_scratch_bytes,
                    supervisor.monitor.max_rss if mode=='rss' else supervisor.monitor.max_scratch)
                self.assertEqual(fixture.children[0].returncode,-9)
                self.assert_clean(fixture)
                fixture.mode='good'
                self.assertEqual(json.loads(await supervisor.run(b'{}')),{'ok':True})
                self.assert_clean(fixture)

    @unittest.skipUnless(os.geteuid()!=0,'Requires nonroot procfs ownership')
    async def test_unavailable_proc_observation_of_exited_child_requires_owned_completion(self):
        children=[]
        def child_factory(environment):
            child=ExitedChild(environment)
            children.append(child)
            return child
        result=await PreviewSupervisor(child_factory=child_factory).run(b'{}')
        self.assertEqual(json.loads(result),{'ok':True})
        self.assertEqual((children[0].state,children[0].fd_owner),('Z',0))
        self.assertEqual(children[0].wait_confirmations,1)
        self.assertEqual(children[0].process.returncode,0)

    async def test_denied_running_worker_fails_closed_then_recovery_uses_new_monitor(self):
        fixture=FixtureChildren('stall')
        monitor=Mock(spec=ResourceMonitor)
        monitor.measure.side_effect=PermissionError('private')
        supervisor=self.supervisor(fixture,monitor=monitor)
        with self.assertRaises(PreviewFailure) as caught:await supervisor.run(b'{}')
        self.assertEqual(caught.exception.code,'ImageProcessingFailed')
        self.assertNotIn('private',str(caught.exception))
        self.assertEqual(fixture.children[0].returncode,-9)
        self.assert_clean(fixture)
        supervisor.monitor=ResourceMonitor()
        fixture.mode='good'
        self.assertEqual(json.loads(await supervisor.run(b'{}')),{'ok':True})

    async def test_processing_timeout_cancellation_and_final_scratch_failure_clean_all(self):
        fixture=FixtureChildren('stall')
        supervisor=self.supervisor(fixture,timeout=0.1)
        with self.assertRaises(PreviewFailure) as caught:await supervisor.run(b'{}')
        self.assertEqual(caught.exception.code,'ImageProcessingTimeout')
        self.assert_clean(fixture)
        fixture.started.clear()
        task=asyncio.create_task(supervisor.run(b'{}',timeout=3))
        await fixture.started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assert_clean(fixture)
        fixture.mode='good'
        supervisor.timeout=limits.WORKER_TIMEOUT_SECONDS
        supervisor.monitor=Mock(spec=ResourceMonitor)
        supervisor.monitor.final_scratch.side_effect=PreviewFailure('ImageScratchLimit')
        with self.assertRaises(PreviewFailure) as caught:await supervisor.run(b'{}')
        self.assertEqual(caught.exception.code,'ImageScratchLimit')
        self.assert_clean(fixture)

    async def test_queue_cancellation_creates_no_child_or_workspace(self):
        fixture=FixtureChildren('stall')
        supervisor=self.supervisor(fixture,max_queued=1)
        first=asyncio.create_task(supervisor.run(b'{}'))
        await fixture.started.wait()
        queued=asyncio.create_task(supervisor.run(b'{}'))
        await asyncio.sleep(0)
        with self.assertRaises(PreviewFailure) as caught:await supervisor.run(b'{}')
        self.assertEqual(caught.exception.code,'ImageProcessingBusy')
        queued.cancel()
        with self.assertRaises(asyncio.CancelledError):await queued
        self.assertEqual(len(fixture.children),1)
        self.assertEqual(len(fixture.scratch),1)
        first.cancel()
        with self.assertRaises(asyncio.CancelledError):await first
        self.assert_clean(fixture)

    async def test_component_unwind_order_and_upload_admission_independence(self):
        from foundry_mcp_server.mcp_server import image_uploads
        events=[]
        @asynccontextmanager
        async def permit():
            events.append('admit')
            try:yield
            finally:events.append('release')
        class Workspace:
            path=Path('/unused')
            def __enter__(self):events.append('workspace');return self
            def environment(self):return {}
            def __exit__(self,*exception):events.append('remove')
        child=Mock(spec=PreviewChild)
        child.pid=1
        child.start=AsyncMock()
        child.close=AsyncMock(side_effect=lambda:events.append('reap'))
        async def result():return b'{}'
        child.exchange.side_effect=lambda payload:asyncio.create_task(result())
        monitor=Mock(spec=ResourceMonitor)
        monitor.final_scratch.side_effect=lambda *args:events.append('final')
        supervisor=PreviewSupervisor(admission=Mock(permit=permit),workspace_factory=Workspace,
            child_factory=lambda env:child,monitor=monitor)
        async with image_uploads._operation_lock:
            self.assertEqual(await supervisor.run(b'{}'),b'{}')
        self.assertEqual(events,['admit','workspace','reap','final','remove','release'])
