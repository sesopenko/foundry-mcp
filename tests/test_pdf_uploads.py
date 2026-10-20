import asyncio
import base64
from dataclasses import replace
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from foundry_mcp_server.pdf.config import PDFConfig
from foundry_mcp_server.pdf.library import Library
from foundry_mcp_server.pdf.uploads import Uploads
from test_pdf_library import pdf

class UploadTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory(); root=Path(self.tmp.name)
        self.library=Library(PDFConfig(True,root/'books',root/'state',True,'private',max_bytes=200000))
        await self.library.start()
        self.messages=[]
        async def send(ws,data): self.messages.append((ws,data))
        self.uploads=Uploads(self.library,send)
        self.ws=object();self.seq=0
    async def asyncTearDown(self):
        await self.uploads.close(); await self.library.close();self.tmp.cleanup()
    async def request(self,kind,ws=None,secure=True,**data):
        self.seq+=1
        await self.uploads.handle(ws or self.ws,dict(type='pdf.upload.'+kind,request_id=str(self.seq),protocol=1,**data),secure)
        return self.messages[-1][1]
    async def auth(self): return await self.request('authorize',token='private')
    async def test_authorization_denials_and_cross_socket(self):
        for fields in ({},{'token':'bridge'},{'token':'private','isGM':True}):
            response=await self.request('authorize',secure=False,**fields)
            self.assertEqual(response['type'],'pdf.upload.error')
        self.assertEqual((await self.request('list',isGM=True))['type'],'pdf.upload.error')
        await self.auth()
        begin=await self.request('begin',name='Book.pdf',size_bytes=10)
        self.assertEqual((await self.request('chunk',ws=object(),upload_id=begin['upload_id'],seq=0,data_base64='YQ=='))['type'],'pdf.upload.error')
        self.assertIn(self.ws,self.uploads.sessions)
        self.uploads.config=replace(self.uploads.config,token='rotated')
        self.assertEqual((await self.request('list'))['type'],'pdf.upload.error')
        self.assertFalse(self.uploads.sessions)
    async def test_multichunk_integrity_index_and_duplicate(self):
        source=Path(self.tmp.name)/'fixture.pdf'; pdf(source)
        # Padding after EOF is permitted in ordinary PDF readers; exercises multiple chunks.
        data=source.read_bytes()+b'\n'*70000
        for attempt in range(2):
            await self.auth()
            begin=await self.request('begin',name='Book.pdf',size_bytes=len(data))
            accepted=0
            for seq,start in enumerate(range(0,len(data),32768)):
                chunk=data[start:start+32768]
                ack=await self.request('chunk',upload_id=begin['upload_id'],seq=seq,data_base64=base64.b64encode(chunk).decode())
                accepted+=len(chunk)
                self.assertEqual(ack['accepted_bytes'],accepted)
                self.assertEqual(ack['next_seq'],seq+1)
            finish=await self.request('finish',upload_id=begin['upload_id'])
            self.assertEqual(finish['duplicate'],bool(attempt))
            await asyncio.gather(*self.library.tasks)
            status=await self.request('index_status',document_id=finish['document_id'])
            self.assertEqual(status['status'],'ready')
            saved=self.library.config.library/(hashlib.sha256(data).hexdigest()+'.pdf')
            self.assertEqual(saved.read_bytes(),data)
        self.assertEqual(len(self.library.documents()['documents']),1)
    async def test_bad_sequence_base64_lengths_names_and_disk_cleanup(self):
        for name,size in [('../bad.pdf',4),('x.pdf',200001),('x.pdf',True),('bad\x00.pdf',10)]:
            await self.auth()
            self.assertEqual((await self.request('begin',name=name,size_bytes=size))['type'],'pdf.upload.error')
        for seq,encoded in [(1,'YQ=='),(0,'%%%'),(0,base64.b64encode(b'x'*32769).decode()),(True,'YQ==')]:
            await self.auth(); begin=await self.request('begin',name='ok.pdf',size_bytes=40000)
            self.assertEqual((await self.request('chunk',upload_id=begin['upload_id'],seq=seq,data_base64=encoded))['type'],'pdf.upload.error')
            self.assertEqual(list((self.library.config.state/'staging').iterdir()),[])
        await self.auth();begin=await self.request('begin',name='ok.pdf',size_bytes=4)
        self.assertEqual((await self.request('finish',upload_id=begin['upload_id']))['type'],'pdf.upload.error')
        await self.auth()
        with patch('foundry_mcp_server.pdf.uploads.os.open',side_effect=OSError('secret host path')):
            result=await self.request('begin',name='ok.pdf',size_bytes=4)
        self.assertNotIn('secret',str(result))
    async def test_cancel_disconnect_orphan_cleanup_and_recover_completed(self):
        await self.auth();begin=await self.request('begin',name='ok.pdf',size_bytes=4)
        await self.request('cancel',upload_id=begin['upload_id'])
        self.assertFalse(self.uploads.sessions)
        begin=await self.request('begin',name='ok.pdf',size_bytes=4)
        await self.uploads.disconnect(self.ws)
        self.assertFalse(self.uploads.sessions);self.assertFalse(self.uploads.authorized)
        path=self.library.config.state/'staging'/('a'*32);path.write_bytes(b'incomplete')
        new=Library(self.library.config);await new.start();self.assertFalse(path.exists());await new.close()
    async def test_expiration_idle_timeout_quota_and_exact_limit(self):
        await self.auth()
        self.uploads.authorized[self.ws]=('private',0)
        self.assertEqual((await self.request('list'))['type'],'pdf.upload.error')
        await self.auth()
        with patch('foundry_mcp_server.pdf.uploads.shutil.disk_usage') as disk:
            disk.return_value.free=1
            self.assertEqual((await self.request('begin',name='x.pdf',size_bytes=1))['type'],'pdf.upload.error')
        begin=await self.request('begin',name='x.pdf',size_bytes=self.library.config.max_bytes)
        self.assertEqual(begin['type'],'pdf.upload.begin_ack')
        self.uploads.sessions[self.ws]['touched']=0
        self.uploads.config=replace(self.uploads.config,idle=1)
        self.uploads.start()
        await asyncio.sleep(1.05)
        self.assertFalse(self.uploads.sessions)
