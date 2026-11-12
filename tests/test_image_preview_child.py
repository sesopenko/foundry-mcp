"""Child ownership tests use real pipes/processes independently of monitoring."""
import asyncio
import json
import unittest
from unittest.mock import AsyncMock

from foundry_mcp_server.image_preview_child import PreviewChild
from foundry_mcp_server.image_preview_workspace import PreviewWorkspace
from foundry_mcp_server.image_preview_worker import PreviewFailure
from image_preview_fixtures import FixtureChildren


class ChildTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_exchange_and_idempotent_close(self):
        fixture=FixtureChildren()
        with PreviewWorkspace() as workspace:
            child=PreviewChild(workspace.environment(),spawn=fixture.spawn)
            await child.start()
            with self.assertRaises(PreviewFailure):await child.start()
            self.assertEqual(len(fixture.children),1)
            self.assertEqual(json.loads(await child.exchange(b'{}')),{'ok':True})
            self.assertTrue(await child.wait_finished(0))
            await child.close()
            await child.close()
            self.assertEqual(child.process.returncode,0)
            self.assertTrue(workspace.path.exists())
        self.assertFalse(workspace.path.exists())

    async def test_stdout_overflow_flood_and_nonzero_exit_are_fixed_failures(self):
        for mode in ('overflow','flood','exit'):
            with self.subTest(mode=mode),PreviewWorkspace() as workspace:
                child=PreviewChild(workspace.environment(),spawn=FixtureChildren(mode).spawn)
                await child.start()
                try:
                    with self.assertRaises(PreviewFailure) as caught:
                        await child.exchange(b'{}')
                    self.assertEqual(caught.exception.code,'ImageProcessingFailed')
                    self.assertNotIn('private',str(caught.exception))
                finally:
                    # A real flood exercises paused PIPE draining before wait.
                    await asyncio.wait_for(child.close(),1)
                self.assertIsNotNone(child.process.returncode)

    async def test_spawn_failure_and_invalid_exchange_own_no_process(self):
        child=PreviewChild({},spawn=AsyncMock(side_effect=OSError('spawn failed')))
        with self.assertRaises(OSError):await child.start()
        await child.close()
        with self.assertRaises(PreviewFailure):child.exchange(b'{}')

    async def test_cancellation_during_spawn_retains_and_reaps_child(self):
        fixture=FixtureChildren('stall')
        release=asyncio.Event()
        async def spawn(*command,**options):
            process=await fixture.spawn(*command,**options)
            await release.wait()
            return process
        with PreviewWorkspace() as workspace:
            child=PreviewChild(workspace.environment(),spawn=spawn)
            task=asyncio.create_task(child.start())
            await fixture.started.wait()
            task.cancel()
            release.set()
            with self.assertRaises(asyncio.CancelledError):await task
            await child.close()
            self.assertEqual(child.process.returncode,-9)

    async def test_wait_observation_timeout_does_not_cancel_completion(self):
        with PreviewWorkspace() as workspace:
            child=PreviewChild(workspace.environment(),spawn=FixtureChildren('stall').spawn)
            await child.start()
            child.exchange(b'{}')
            self.assertFalse(await child.wait_finished(0.01))
            self.assertFalse(child._completion.cancelled())
            await child.close()
            self.assertTrue(await child.wait_finished(0))
            self.assertEqual(child.process.returncode,-9)

    async def test_repeated_cancellation_during_close_still_finishes_reaping(self):
        with PreviewWorkspace() as workspace:
            child=PreviewChild(workspace.environment(),spawn=FixtureChildren('stall').spawn)
            await child.start()
            child.exchange(b'{}')
            entered,release=asyncio.Event(),asyncio.Event()
            original_wait=child._completion
            async def held_completion():
                entered.set()
                await release.wait()
                return await original_wait
            child._completion=asyncio.create_task(held_completion())
            task=asyncio.create_task(child.close())
            await entered.wait()
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            release.set()
            with self.assertRaises(asyncio.CancelledError):await task
            self.assertIsNotNone(child.process.returncode)
            await child.close()
