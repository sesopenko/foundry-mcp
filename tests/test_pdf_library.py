import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from foundry_mcp_server.pdf.config import PDFConfig
from foundry_mcp_server.pdf.library import Library, safe_name, hash_file, LibraryError


def pdf(path, text='SURE STRIKE\\nSPELL 1\\nRoll twice and use the better result.'):
    writer=PdfWriter()
    page=writer.add_blank_page(600,800)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream=DecodedStreamObject()
    commands='BT /F1 12 Tf 50 750 Td '+ ' '.join('('+line+') Tj 0 -16 Td' for line in text.split('\\n'))+' ET'
    stream.set_data(commands.encode())
    page[NameObject('/Contents')]=writer._add_object(stream)
    writer.add_outline_item('Variant Rules',0)
    writer.add_outline_item('Sure Strike',0)
    writer.write(path)

class LibraryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        self.config=PDFConfig(True,root/'books',root/'state',True,'private')
        self.library=Library(self.config)
        await self.library.start()
    async def asyncTearDown(self):
        await self.library.close()
        self.tmp.cleanup()
    async def test_scan_search_and_read_without_browser_and_restart(self):
        path=self.config.library/'Book.pdf'
        pdf(path)
        result=await self.library.scan()
        await asyncio.gather(*self.library.tasks)
        identifier=result['queued_document_ids'][0]
        self.assertEqual(self.library.status(identifier)['status'],'ready')
        result=self.library.search('Sure Strike',locate=True)
        self.assertEqual(result['candidates'][0]['document_id'],identifier)
        source=self.library.read(identifier,1,max_chars=12)
        self.assertIn('table_structure_unverified',source['warnings'])
        full=source['text']; offset=source['next_offset']
        while offset is not None:
            more=self.library.read(identifier,1,source['revision'],offset,12)
            full+=more['text']; offset=more['next_offset']
        self.assertIn('Roll twice',full)
        with self.assertRaises(LibraryError): self.library.read(identifier,1,'wrong')
        other=Library(self.config); await other.start()
        self.assertEqual(other.status(identifier)['status'],'ready')
        self.assertEqual((await other.scan())['queued_document_ids'],[])
        await other.close()
    async def test_corrupt_and_encrypted_fail_without_searchable_content(self):
        path=self.config.library/'broken.pdf'; path.write_bytes(b'%PDF-broken')
        result=await self.library.scan(); await asyncio.gather(*self.library.tasks)
        self.assertEqual(self.library.status(result['queued_document_ids'][0])['status'],'failed')
        self.assertEqual(self.library.search('broken')['candidates'],[])
        writer=PdfWriter();writer.add_blank_page(100,100);writer.encrypt('secret')
        writer.write(self.config.library/'encrypted.pdf')
        result=await self.library.scan();await asyncio.gather(*self.library.tasks)
        self.assertEqual(self.library.status(result['queued_document_ids'][0])['status'],'failed')
    def test_names(self):
        for name in ('../x.pdf','/x.pdf','x\\y.pdf','x\n.pdf','x:foo.pdf','image.png'):
            with self.assertRaises(LibraryError):safe_name(name)

    async def test_completed_pending_job_survives_restart(self):
        path=self.config.state/'staging'/('b'*32);pdf(path)
        identifier,_=self.library.accept(path,'Pending.pdf',hash_file(path),path.stat().st_size)
        other=Library(self.config);await other.start();await asyncio.gather(*other.tasks)
        self.assertEqual(other.status(identifier)['status'],'ready')
        await other.close()
