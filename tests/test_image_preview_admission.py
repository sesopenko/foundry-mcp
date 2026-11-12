"""Admission policy without child processes, image operations or scratch."""
import asyncio
import unittest

from foundry_mcp_server.image_preview_admission import PreviewAdmission
from foundry_mcp_server.image_preview_worker import PreviewFailure


class AdmissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_serial_fifo_and_permit_recovery_after_exception(self):
        admission=PreviewAdmission()
        entered=[]
        async def request(index):
            async with admission.permit():
                entered.append(index)
                await asyncio.sleep(0)
        async with admission.permit():
            tasks=[asyncio.create_task(request(index)) for index in range(3)]
            await asyncio.sleep(0)
            self.assertEqual(admission.queued,3)
            self.assertEqual(entered,[])
        await asyncio.gather(*tasks)
        self.assertEqual(entered,[0,1,2])
        with self.assertRaisesRegex(ValueError,'operation failed'):
            async with admission.permit():raise ValueError('operation failed')
        async with admission.permit():self.assertEqual(admission.queued,0)

    async def test_queue_bound_and_cancel_do_not_release_owner(self):
        admission=PreviewAdmission(max_queued=1)
        async def waiter():
            async with admission.permit():self.fail('cancelled waiter entered')
        async with admission.permit():
            queued=asyncio.create_task(waiter())
            await asyncio.sleep(0)
            with self.assertRaises(PreviewFailure) as caught:
                async with admission.permit():self.fail('overflow entered')
            self.assertEqual(caught.exception.code,'ImageProcessingBusy')
            queued.cancel()
            with self.assertRaises(asyncio.CancelledError):await queued
            self.assertEqual(admission.queued,0)
            replacement=asyncio.create_task(waiter())
            await asyncio.sleep(0)
            self.assertFalse(replacement.done())
            replacement.cancel()
            with self.assertRaises(asyncio.CancelledError):await replacement

    async def test_queue_timeout_leaves_owner_and_future_admission_intact(self):
        admission=PreviewAdmission(queue_timeout=0.01)
        async with admission.permit():
            with self.assertRaises(PreviewFailure) as caught:
                async with admission.permit():self.fail('timed out waiter entered')
            self.assertEqual(caught.exception.code,'ImageProcessingBusy')
            self.assertEqual(admission.queued,0)
        async with admission.permit():pass

    async def test_cancel_active_request_releases_permit(self):
        admission=PreviewAdmission()
        entered=asyncio.Event()
        async def request():
            async with admission.permit():
                entered.set()
                await asyncio.Event().wait()
        task=asyncio.create_task(request())
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        async with admission.permit():pass
