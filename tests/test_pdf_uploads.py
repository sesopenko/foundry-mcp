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
            self.assertEqual(finish['replacing'],bool(attempt))
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
    async def test_delete_requires_exact_socket_authorization_and_revision(self):
        path=self.library.config.library/'Original.pdf';pdf(path)
        result=await self.library.scan();await asyncio.gather(*self.library.tasks)
        identifier=result['queued_document_ids'][0];revision=self.library.status(identifier)['revision']
        self.assertEqual((await self.request('delete',document_id=identifier,revision=revision))['type'],'pdf.upload.error')
        await self.auth()
        self.assertEqual((await self.request('delete',ws=object(),document_id=identifier,revision=revision))['type'],'pdf.upload.error')
        self.assertEqual((await self.request('delete',document_id=identifier,revision='stale'))['type'],'pdf.upload.error')
        self.assertEqual(self.library.status(identifier)['status'],'ready')
        response=await self.request('delete',document_id=identifier,revision=revision)
        self.assertTrue(response['deleted']);self.assertEqual(response['type'],'pdf.upload.delete_ack')
        self.assertEqual(self.library.documents()['documents'],[])
        self.assertEqual(self.library.search('Sure Strike')['candidates'],[])
        self.assertFalse((self.library.config.library/(revision+'.pdf')).exists())
        # Operator-supplied import files are preserved but must not resurrect deleted content.
        self.assertTrue(path.exists());self.assertEqual((await self.library.scan())['queued_document_ids'],[])
        self.assertTrue((await self.request('delete',document_id=identifier,revision=revision))['deleted'])
        staged=self.library.config.state/'staging'/('c'*32);staged.write_bytes(path.read_bytes())
        new_id,duplicate=self.library.accept(staged,'Replacement.pdf',revision,staged.stat().st_size)
        self.assertFalse(duplicate);self.assertNotEqual(new_id,identifier)
        self.library.enqueue(new_id);await asyncio.gather(*self.library.tasks)
        self.assertEqual(self.library.status(new_id)['status'],'ready')

    async def test_delete_processing_rejected_and_interrupted_cleanup_recovers(self):
        path=self.library.config.state/'staging'/('d'*32);pdf(path)
        from foundry_mcp_server.pdf.library import hash_file,LibraryError
        identifier,_=self.library.accept(path,'Pending.pdf',hash_file(path),path.stat().st_size)
        revision=self.library.status(identifier)['revision']
        self.library.enqueue(identifier)
        with self.assertRaisesRegex(LibraryError,'processing'):await self.library.delete(identifier,revision)
        await asyncio.gather(*self.library.tasks)
        with patch.object(self.library,'_cleanup_deleted',side_effect=OSError('private path')):
            with self.assertRaises(OSError):await self.library.delete(identifier,revision)
        self.assertEqual(self.library.documents()['documents'],[])
        restarted=Library(self.library.config);await restarted.start()
        self.assertFalse((self.library.config.library/(revision+'.pdf')).exists())
        await restarted.close()
        for value in ('../x','/tmp/x',None):
            with self.assertRaises(LibraryError):await self.library.delete(value,revision)

    async def test_replacement_keeps_old_source_until_success_and_failure_preserves_it(self):
        original=self.library.config.library/'Edition.pdf';pdf(original,'ORIGINAL RULE')
        result=await self.library.scan();await asyncio.gather(*self.library.tasks)
        old_id=result['queued_document_ids'][0]
        old_revision=self.library.status(old_id)['revision']
        new=self.library.config.state/'staging'/('e'*32);pdf(new,'UPDATED RULE')
        from foundry_mcp_server.pdf.library import hash_file,LibraryError
        new_id,replacing=await self.library.accept_upload(new,'Edition.pdf',hash_file(new),new.stat().st_size)
        self.assertTrue(replacing);self.assertNotEqual(new_id,old_id)
        self.assertIn('ORIGINAL RULE',self.library.read(old_id,1)['text'])
        self.library.enqueue(new_id);await asyncio.gather(*self.library.tasks)
        self.assertIn('UPDATED RULE',self.library.read(new_id,1)['text'])
        with self.assertRaises(LibraryError):self.library.status(old_id)
        self.assertFalse((self.library.config.library/(old_revision+'.pdf')).exists())
        bad=self.library.config.state/'staging'/('f'*32);bad.write_bytes(b'%PDF-broken')
        bad_id,replacing=await self.library.accept_upload(bad,'Edition.pdf',hash_file(bad),bad.stat().st_size)
        self.assertTrue(replacing)
        self.library.enqueue(bad_id);await asyncio.gather(*self.library.tasks)
        self.assertEqual(self.library.status(bad_id)['status'],'failed')
        self.assertIn('UPDATED RULE',self.library.read(new_id,1)['text'])
        self.assertEqual((await self.library.scan())['queued_document_ids'],[])
        await asyncio.gather(*self.library.tasks)
    async def test_legacy_hash_constraint_migration_and_pending_replacement_recovery(self):
        with self.library.db() as db:
            db.execute('DROP TABLE documents')
            db.execute('CREATE TABLE documents(id TEXT PRIMARY KEY,name TEXT,sha256 TEXT UNIQUE,size_bytes INTEGER,status TEXT,revision TEXT,page_count INTEGER DEFAULT 0,error TEXT)')
        original=self.library.config.library/'Legacy.pdf';pdf(original,'LEGACY RULE')
        result=await self.library.scan();await asyncio.gather(*self.library.tasks)
        old_id=result['queued_document_ids'][0]
        migrated=Library(self.library.config);await migrated.start()
        self.assertEqual(migrated.status(old_id)['status'],'ready')
        staged=self.library.config.state/'staging'/('1'*32);staged.write_bytes(original.read_bytes())
        from foundry_mcp_server.pdf.library import hash_file,LibraryError
        new_id,replacing=await migrated.accept_upload(staged,'Legacy.pdf',hash_file(staged),staged.stat().st_size)
        self.assertTrue(replacing)
        # Do not enqueue: startup must resume this fully received replacement itself.
        recovered=Library(self.library.config);await recovered.start();await asyncio.gather(*recovered.tasks)
        self.assertEqual(recovered.status(new_id)['status'],'ready')
        with self.assertRaises(LibraryError):recovered.status(old_id)
        self.assertEqual(len(recovered.documents()['documents']),1)
        self.assertIn('LEGACY RULE',recovered.read(new_id,1)['text'])
        await migrated.close();await recovered.close()
