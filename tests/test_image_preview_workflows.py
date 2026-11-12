"""Full synthetic JS dispatch -> real RPC/auth MCP -> native pixels -> HTTP."""
import asyncio
import base64
from io import BytesIO
import json
import random
import unittest
from unittest.mock import patch

from PIL import Image,ImageOps

from image_preview_workflow_harness import workflow,NodeSocket,Workflow
from foundry_mcp_server.image_preview_failure import PreviewFailure
from foundry_mcp_server.mcp_server import image_previews


def fixture(orientation=None):
    image=Image.frombytes('RGBA',(192,128),random.Random(724).randbytes(192*128*4))
    output=BytesIO()
    options={}
    if orientation:
        exif=Image.Exif();exif[274]=orientation;options['exif']=exif
    image.save(output,format='PNG',**options)
    return output.getvalue()


class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_call_and_time_limits_fail_before_reading_and_cleanup_removes_private_roots(self):
        meter=Workflow(None,None,None,None,None)
        meter.calls=40
        with self.assertRaisesRegex(RuntimeError,'BudgetExceeded'):await meter.request('tools/list',{})
        meter.calls=0;meter.started-=601
        with self.assertRaisesRegex(RuntimeError,'BudgetExceeded'):await meter.request('tools/list',{})
        async with workflow(fixture()) as f:
            await f.call('get_foundry_image_info',{'request':{'src':'assets/%CE%B1%20maps/opaque%20file.png'}})
            root=f.source.cache.directory
            store=f.delivery.store.directory
            self.assertTrue(root.exists())
        self.assertFalse(root.exists())
        self.assertFalse(store.exists())

    async def test_fragmented_journal_browse_multichunk_info_repeated_crops_and_anonymous_pixels(self):
        data=fixture()
        self.assertGreater(len(data),65536)
        async with workflow(data,prefix='/table') as f:
            catalog=await f.discovery()
            self.assertTrue({'get_foundry_image_info','get_foundry_image_url','read_journal_page','browse_journal_images'}<=catalog['names'])
            src,fragments=await f.read_src()
            self.assertGreater(fragments,2)
            bare=await f.call('get_foundry_image_url',{'request':{'src':src}})
            browse=await f.call('browse_journal_images',{'directory':'assets/%CE%B1%20maps'})
            image=browse['entries'][0]['image']
            canonical=await f.call('get_foundry_image_url',{'request':{'image':image}})
            for result in (bare,canonical):
                with Image.open(BytesIO(await f.fetch(result['url']))) as actual,Image.open(BytesIO(data)) as original:
                    self.assertEqual(actual.convert('RGBA').tobytes(),original.tobytes())
            info=await f.call('get_foundry_image_info',{'request':{'image':image}})
            before=(await f.stats())['fetches']
            urls=[bare['url'],canonical['url']]
            for region in (dict(x=160,y=101,width=32,height=27),dict(x=191,y=127,width=1,height=1)):
                result=await f.call('get_foundry_image_url',{'request':{'source_id':info['source_id'],'crop':region}})
                self.assertEqual(result['region'],region)
                urls.append(result['url'])
                with Image.open(BytesIO(await f.fetch(result['url']))) as actual,Image.open(BytesIO(data)) as original:
                    oracle=original.crop((region['x'],region['y'],region['x']+region['width'],region['y']+region['height']))
                    self.assertEqual(actual.convert('RGBA').tobytes(),oracle.tobytes())
            stats=await f.stats()
            self.assertEqual(stats['fetches'],before)
            self.assertEqual(before,3)
            self.assertGreater(stats['chunks'],3)
            self.assertEqual(stats['finished'][:4],[3,2,1,0])
            self.assertFalse(stats['busy'])
            self.assertEqual(len(set(urls)),4)
            self.assertFalse(f.manager.pending)
            self.assertTrue(all(r.leases==0 for r in f.source.cache._entries.values()))
            report=f.report();report.update(fragments=fragments,transfers=stats['fetches'],chunks=stats['chunks'],complete=True)
            print('PREVIEW_WORKFLOW '+json.dumps(report,sort_keys=True))

    async def test_mirrored_rotated_transparent_native_regions_through_full_dispatch(self):
        for orientation in (2,6):
            data=fixture(orientation)
            async with workflow(data) as f:
                src,_=await f.read_src()
                info=await f.call('get_foundry_image_info',{'request':{'src':src}})
                with Image.open(BytesIO(data)) as raw:
                    original=ImageOps.exif_transpose(raw).convert('RGBA')
                    self.assertEqual((info['width'],info['height']),original.size)
                    crop=dict(x=original.width-17,y=original.height-13,width=17,height=13)
                    result=await f.call('get_foundry_image_url',{'request':{'source_id':info['source_id'],'crop':crop}})
                    with Image.open(BytesIO(await f.fetch(result['url']))) as actual:
                        self.assertEqual(actual.convert('RGBA').tobytes(),original.crop((crop['x'],crop['y'],original.width,original.height)).tobytes())
                self.assertEqual((await f.stats())['fetches'],1)

    async def test_short_chunk_and_missing_reply_fail_then_recover_without_partial_cache(self):
        async with workflow(fixture()) as f:
            src,_=await f.read_src()
            for fault,code in (('short','InvalidFoundryResponse'),('missing','ImageTransferTimeout')):
                await f.change(fault=fault)
                original_call=f.manager.call
                async def bounded(client,method,params=None,timeout=10):
                    return await original_call(client,method,params,timeout=min(timeout,.05) if method=='readImagePreviewChunk' else timeout)
                with patch.object(f.manager,'call',side_effect=bounded):
                    failed=await f.call('get_foundry_image_info',{'request':{'src':src}},error=True)
                self.assertTrue(failed.get('isError'))
                self.assertIn(code,str(failed['content']))
                self.assertEqual(f.source.cache.used_bytes,0)
                self.assertEqual(list(f.source.cache.directory.iterdir()),[])
                self.assertFalse(f.manager.pending)
                self.assertFalse((await f.stats())['busy'])
                await f.change(fault=None)
                await f.call('get_foundry_image_info',{'request':{'src':src}})
                f.clock[0]+=1800
                await f.source.cache.prune()

    async def test_replacement_expiry_permission_resource_failure_and_quota_isolate_links(self):
        async with workflow(fixture()) as f:
            src,_=await f.read_src()
            info=await f.call('get_foundry_image_info',{'request':{'src':src}})
            first=await f.call('get_foundry_image_url',{'request':{'source_id':info['source_id']}})
            expected=await f.fetch(first['url'])
            replacement=BytesIO();Image.new('RGB',(11,7),'red').save(replacement,format='PNG')
            await f.change(data_base64=base64.b64encode(replacement.getvalue()).decode())
            old=await f.call('get_foundry_image_url',{'request':{'source_id':info['source_id']}})
            self.assertEqual(await f.fetch(old['url']),expected)
            fresh=await f.call('get_foundry_image_info',{'request':{'src':src}})
            self.assertEqual((fresh['width'],fresh['height']),(11,7))
            with patch.object(image_previews,'render_preview',side_effect=PreviewFailure('ImageMemoryLimit')):
                failed=await f.call('get_foundry_image_url',{'request':{'source_id':fresh['source_id']}},error=True)
                self.assertIn('ImageMemoryLimit',str(failed['content']))
            f.delivery.store.max_rows=2
            failed=await f.call('get_foundry_image_url',{'request':{'source_id':fresh['source_id']}},error=True)
            self.assertIn('PreviewQuotaExceeded',str(failed['content']))
            self.assertEqual(await f.fetch(first['url']),expected)
            await f.change(denied=True)
            failed=await f.call('get_foundry_image_url',{'request':{'source_id':info['source_id']}},error=True)
            self.assertIn('SourceContextLost',str(failed['content']))
            await f.change(denied=False)
            f.clock[0]+=1800
            failed=await f.call('get_foundry_image_url',{'request':{'source_id':info['source_id']}},error=True)
            self.assertIn('SourceUnavailable',str(failed['content']))
            self.assertEqual(await f.fetch(first['url']),expected)
            self.assertFalse(f.manager.pending)

    async def test_cancelled_transfer_and_new_socket_revalidate_pinned_handle(self):
        data=fixture()
        async with workflow(data) as f:
            src,_=await f.read_src()
            await f.change(fault='missing')
            operation=asyncio.create_task(f.call('get_foundry_image_info',{'request':{'src':src}}))
            try:
                async with asyncio.timeout(3):
                    while not f.source.cache.used_bytes:await asyncio.sleep(.005)
                operation.cancel()
                with self.assertRaises(asyncio.CancelledError):await operation
            finally:
                if not operation.done():operation.cancel();await asyncio.gather(operation,return_exceptions=True)
            self.assertEqual(f.source.cache.used_bytes,0)
            self.assertFalse(f.manager.pending)
            self.assertFalse((await f.stats())['busy'])
            await f.change(fault=None)
            info=await f.call('get_foundry_image_info',{'request':{'src':src}})
            old_socket=f.manager.websockets['gm']
            await old_socket.close()
            # Same authorized world/GM, genuinely new socket and JS process.
            fresh=await NodeSocket().start(f.manager)
            try:
                await f.manager.call('gm','fixture.init',{'image':dict(source='data',directory='assets/%CE%B1%20maps',src=src),
                    'html':'<img src="'+src+'">','data_base64':base64.b64encode(data).decode()},timeout=5)
                result=await f.call('get_foundry_image_url',{'request':{'source_id':info['source_id'],'crop':dict(x=0,y=0,width=1,height=1)}})
                self.assertEqual((await f.stats())['fetches'],0)
                self.assertEqual(result['source_id'],info['source_id'])
                with Image.open(BytesIO(await f.fetch(result['url']))) as actual,Image.open(BytesIO(data)) as source:
                    self.assertEqual(actual.convert('RGBA').getpixel((0,0)),source.getpixel((0,0)))
                await f.change(world='other')
                denied=await f.call('get_foundry_image_url',{'request':{'source_id':info['source_id']}},error=True)
                self.assertIn('SourceContextLost',str(denied['content']))
            finally:await fresh.close()

    async def test_real_decoder_failure_and_non_gm_never_leave_private_handles(self):
        async with workflow(b'broken compressed source') as f:
            src,_=await f.read_src()
            failed=await f.call('get_foundry_image_info',{'request':{'src':src}},error=True)
            self.assertIn('UnsupportedImage',str(failed['content']))
            self.assertEqual(f.source.cache.used_bytes,0)
            self.assertEqual(list(f.source.cache.directory.iterdir()),[])
            self.assertFalse((await f.stats())['busy'])
            await f.change(isGM=False)
            failed=await f.call('get_foundry_image_info',{'request':{'src':src}},error=True)
            self.assertIn('PermissionDenied',str(failed['content']))
            self.assertFalse(f.manager.pending)

    async def test_browser_transport_eof_fails_pending_transfer_promptly(self):
        async with workflow(fixture()) as f:
            src,_=await f.read_src()
            await f.change(fault='missing')
            operation=asyncio.create_task(f.call('get_foundry_image_info',{'request':{'src':src}},error=True))
            async with asyncio.timeout(3):
                while not f.source.cache.used_bytes:await asyncio.sleep(.005)
            socket=f.manager.websockets['gm']
            socket.process.stdin.close()
            await socket.process.stdin.wait_closed()
            await socket.process.wait()
            result=await asyncio.wait_for(operation,2)
            self.assertTrue(result.get('isError'))
            self.assertIn('BridgeUnavailable',str(result['content']))
            self.assertFalse(f.manager.pending)
            self.assertEqual(f.source.cache.used_bytes,0)
