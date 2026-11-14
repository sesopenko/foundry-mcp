"""JPEG policy, real worker pixels, strict containers and isolated v1 migration."""
import io
import os
from pathlib import Path
import random
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock,patch

from PIL import Image,PngImagePlugin

from foundry_mcp_server.config import Settings
from foundry_mcp_server.image_preview_artifact import inspect_artifact
from foundry_mcp_server.image_preview_encode import encode_region
from foundry_mcp_server.image_preview_failure import PreviewFailure
from foundry_mcp_server.image_preview_process import render_preview
from foundry_mcp_server.image_preview_store import PreviewStore,token_digest,StoreFailure
from foundry_mcp_server.map_note_render import render_annotated


def jpeg_bytes(**options):
    stream=io.BytesIO()
    Image.new('RGB',(24,16),(40,80,120)).save(stream,format='JPEG',quality=80,
        subsampling=0,dpi=(96,96),**options)
    return stream.getvalue()


class JpegConfigurationTests(unittest.TestCase):
    def test_default_and_strict_boolean_values_without_reflecting_input(self):
        self.assertTrue(Settings().image_preview_jpeg)
        for value,expected in ((None,True),('true',True),('false',False)):
            env={} if value is None else {'FOUNDRY_MCP_IMAGE_PREVIEW_JPEG':value}
            with self.subTest(value=value),patch.dict(os.environ,env,clear=True):
                self.assertIs(Settings.from_env().image_preview_jpeg,expected)
        for value in ('','TRUE','False','1','0',' true','secret-sentinel'):
            with self.subTest(value=value),patch.dict(os.environ,{'FOUNDRY_MCP_IMAGE_PREVIEW_JPEG':value},clear=True):
                with self.assertRaisesRegex(ValueError,'FOUNDRY_MCP_IMAGE_PREVIEW_JPEG') as caught:
                    Settings.from_env()
                self.assertNotIn('secret-sentinel',str(caught.exception))

    def test_jpeg80_reduces_dimensions_without_changing_quality_or_format(self):
        region=Mock(width=100,height=80)
        region.resample.side_effect=lambda w,h:(w,h)
        calls=[]
        def write(image,path,mime,quality):
            calls.append((*image,mime,quality))
            path.write_bytes(b'x'*(11 if len(calls)<3 else 10))
        def verify(path,w,h,mime):return dict(width=w,height=h,mime_type=mime,size_bytes=path.stat().st_size)
        with tempfile.TemporaryDirectory() as directory:
            result=encode_region(region,directory,jpeg=True,max_bytes=10,writer=write,verify=verify)
        self.assertEqual(calls,[(100,80,'image/jpeg',80),(85,68,'image/jpeg',80),(72,57,'image/jpeg',80)])
        self.assertEqual((result['width'],result['height']),(72,57))


class JpegContainerTests(unittest.TestCase):
    def test_baseline_jpeg_and_malformed_or_metadata_bearing_artifacts(self):
        good=jpeg_bytes()
        self.assertEqual(inspect_artifact(good),dict(width=24,height=16,mime_type='image/jpeg',size_bytes=len(good)))
        exif=Image.Exif();exif[315]='private-author'
        corrupt=[good[:-1],good+b'junk',b'\xff\xd8',good[:30],jpeg_bytes(progressive=True),jpeg_bytes(exif=exif)]
        for marker in (b'\xff\xe1',b'\xff\xe2',b'\xff\xfe'):
            corrupt.append(good[:2]+marker+b'\0\x08secret'+good[2:])
        corrupt.extend([good.replace(b'\xff\xc0\0\x11\x08',b'\xff\xc0\0\x11\x0c',1),
                        good.replace(b'JFIF\0',b'JFXX\0',1)])
        for data in corrupt:
            with self.subTest(length=len(data)),self.assertRaises(PreviewFailure):inspect_artifact(data)
        # A MIME-sized header alone is insufficient; an entropy scan and EOI
        # must both be present, with no appended image or extra scan.
        scan=good.index(b'\xff\xda')
        for data in (good[:scan]+b'\xff\xd9',good+good):
            with self.assertRaises(PreviewFailure):inspect_artifact(data)


class JpegWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_original_formats_crop_alpha_metadata_and_legacy_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source'
            source=Image.new('RGBA',(64,48),(200,0,0,0))
            source.paste((0,80,160,128),(24,0,64,48))
            metadata=PngImagePlugin.PngInfo();metadata.add_text('Private','source-sentinel')
            source.save(path,format='PNG',pnginfo=metadata)
            for fmt in ('PNG','WEBP','JPEG'):
                if fmt=='WEBP':source.save(path,format=fmt,lossless=True)
                if fmt=='JPEG':source.convert('RGB').save(path,format=fmt)
                result=await render_preview(path,dict(x=4,y=4,width=56,height=40),jpeg=True)
                self.assertEqual(result.geometry.mime_type,'image/jpeg')
                self.assertEqual(result.geometry.source.mime_type,{'PNG':'image/png','WEBP':'image/webp','JPEG':'image/jpeg'}[fmt])
                with Image.open(io.BytesIO(result.data)) as decoded:
                    decoded.load()
                    self.assertEqual((decoded.format,decoded.mode,decoded.size),('JPEG','RGB',(56,40)))
                    self.assertEqual(decoded.layer[0][1:3],(1,1))
                    self.assertNotIn('progressive',decoded.info)
                    self.assertFalse(set(decoded.info)&{'exif','icc_profile','xmp','comment','Private'})
                    self.assertAlmostEqual(decoded.info['dpi'][0],96,delta=0.02)
                    if fmt!='JPEG':
                        self.assertTrue(all(v>=250 for v in decoded.getpixel((4,20))))
                        self.assertLess(max(abs(a-b) for a,b in zip(decoded.getpixel((44,20)),(127,167,207))),5)
            source.save(path,format='PNG')
            legacy=await render_preview(path,jpeg=False)
            self.assertEqual(legacy.geometry.mime_type,'image/png')
            with Image.open(io.BytesIO(legacy.data)) as decoded:self.assertEqual(decoded.tobytes(),source.tobytes())

    async def test_real_jpeg_budget_reduction_and_annotation_are_decodable(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source'
            source=Image.frombytes('RGB',(1536,1536),random.Random(81).randbytes(1536**2*3))
            source.save(path,format='PNG')
            rendered=await render_preview(path,jpeg=True)
            self.assertEqual(rendered.geometry.mime_type,'image/jpeg')
            self.assertLess(rendered.geometry.width,1536)
            self.assertLessEqual(len(rendered.data),2*1024*1024)
            source=Image.new('RGBA',(500,500),(40,80,120,255));source.save(path,format='PNG')
            annotated=await render_annotated(path,None,[('N1',250,250)],1,jpeg=True)
            self.assertEqual(annotated.geometry.mime_type,'image/jpeg')
            self.assertEqual(annotated.notes.keys,['N1'])
            self.assertTrue(annotated.notes.complete)
            with Image.open(io.BytesIO(annotated.data)) as decoded:
                decoded.load()
                self.assertEqual(decoded.size,(500,500))
                self.assertGreater(min(decoded.getpixel((250,250))),230)


class JpegMigrationTests(unittest.TestCase):
    def legacy_store(self,directory):
        """Real v1 constraint and known live PNG/WebP capabilities, no production DB."""
        path=Path(directory)/'previews.sqlite3'
        rows=[]
        for fmt,mime,token in [('PNG','image/png','00000000-0000-4000-8000-000000000001'),
                               ('WEBP','image/webp','00000000-0000-4000-8000-000000000002')]:
            stream=io.BytesIO();Image.new('RGB',(24,16),(40,80,120)).save(stream,format=fmt)
            data=stream.getvalue();rows.append((token_digest(token),mime,len(data),data,1000.,605800.))
        with sqlite3.connect(path) as db:
            db.execute("""CREATE TABLE previews(digest BLOB PRIMARY KEY CHECK(length(digest)=32),
                mime_type TEXT NOT NULL CHECK(mime_type IN ('image/png','image/webp')),
                size_bytes INTEGER NOT NULL CHECK(size_bytes>0 AND size_bytes<=2097152),
                pixels BLOB NOT NULL CHECK(length(pixels)=size_bytes),
                published_at REAL NOT NULL,expires_at REAL NOT NULL,CHECK(expires_at=published_at+604800))""")
            db.execute('CREATE INDEX preview_expiry ON previews(expires_at)')
            db.executemany('INSERT INTO previews VALUES(?,?,?,?,?,?)',rows)
            db.execute('PRAGMA user_version=1')
        return path,rows

    def test_migration_preserves_issued_rows_and_jpeg_survives_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path,rows=self.legacy_store(directory)
            store=PreviewStore(directory,clock=lambda:2000)
            with store.connection() as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],2)
                self.assertEqual(db.execute('SELECT * FROM previews ORDER BY mime_type').fetchall(),rows)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='preview_expiry'").fetchone()[0],1)
            for suffix,num,row in [('png',1,rows[0]),('webp',2,rows[1])]:
                token=f'00000000-0000-4000-8000-{num:012d}'
                self.assertEqual(store.lookup(token,suffix).data,row[3])
            jpeg=jpeg_bytes();receipt=store.publish(jpeg,'image/jpeg')
            self.assertEqual(receipt.extension,'jpg')
            self.assertIsNone(store.lookup(receipt.token,'png'))
            self.assertIsNone(store.lookup(receipt.token,'jpeg'))
            store.close()
            reopened=PreviewStore(directory,clock=lambda:2000)
            self.assertEqual(reopened.lookup(receipt.token,'jpg').data,jpeg)
            reopened.close()

    def test_failed_migration_rolls_back_ddl_and_existing_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path,rows=self.legacy_store(directory)
            connection=sqlite3.connect
            class FailingConnection(sqlite3.Connection):
                def execute(self,sql,*args):
                    if sql.startswith('INSERT INTO previews SELECT'):raise sqlite3.OperationalError('controlled failure')
                    return super().execute(sql,*args)
            with patch('foundry_mcp_server.image_preview_store.sqlite3.connect',
                       side_effect=lambda *args,**kwargs:connection(*args,**kwargs,factory=FailingConnection)):
                with self.assertRaises(StoreFailure):PreviewStore(directory,clock=lambda:2000)
            with connection(path) as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],1)
                self.assertEqual(db.execute('SELECT * FROM previews ORDER BY mime_type').fetchall(),rows)
