"""Transactional immutable derivative publication, expiry, quotas and restart."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest
from unittest.mock import patch
import uuid

from PIL import Image

from foundry_mcp_server import image_preview_limits as limits
from foundry_mcp_server.image_preview_store import PreviewStore,StoreFailure,token_digest


def pixels(fmt='PNG',colour=(20,40,60)):
    stream = BytesIO()
    Image.new('RGB',(17,11),colour).save(stream,format=fmt)
    return stream.getvalue()


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)/'private'
        self.instant = 1794432000.25
        self.data = pixels()
        self.store = self.make_store()
        self.addCleanup(self.store.close)

    def make_store(self,**options):
        return PreviewStore(self.directory,clock=lambda:self.instant,**options)

    def test_real_png_and_webp_are_immutable_distinct_capabilities(self):
        first = self.store.publish(self.data,'image/png')
        second = self.store.publish(self.data,'image/png')
        other = self.store.publish(pixels('WEBP'),'image/webp')
        self.assertNotEqual(first.token,second.token)
        self.assertEqual(uuid.UUID(first.token).version,4)
        self.assertEqual(first.expires_at-self.instant,604800)
        self.assertEqual((first.extension,other.extension),('png','webp'))
        found = self.store.lookup(first.token,'png')
        self.assertEqual((found.data,found.mime_type,found.size_bytes),(self.data,'image/png',len(self.data)))
        with Image.open(BytesIO(found.data)) as image:self.assertEqual(image.size,(17,11))
        self.assertNotIn(first.token,repr(first))
        self.assertNotIn(repr(self.data),repr(found))

    def test_only_digest_not_bearer_or_source_fields_are_persisted(self):
        receipt = self.store.publish(self.data,'image/png')
        with sqlite3.connect(self.store.path) as db:
            row = db.execute('SELECT digest FROM previews').fetchone()
            columns = [r[1] for r in db.execute('PRAGMA table_info(previews)')]
        self.assertEqual(row,(token_digest(receipt.token),))
        self.assertEqual(len(row[0]),32)
        self.assertEqual(set(columns),{'digest','mime_type','size_bytes','pixels','published_at','expires_at'})
        self.assertNotIn(receipt.token.encode(),self.store.path.read_bytes())

    def test_lookup_binds_canonical_token_and_extension(self):
        receipt = self.store.publish(self.data,'image/png')
        for token,extension in ((receipt.token,'webp'),(str(uuid.uuid4()),'png'),
                (receipt.token.upper(),'png'),('..','png'),(str(uuid.uuid1()),'png'),
                (receipt.token,'png/../original'),(None,'png')):
            self.assertIsNone(self.store.lookup(token,extension))
        self.assertEqual(self.store.lookup(receipt.token,'png').data,self.data)

    def test_exact_expiry_is_independent_of_pruning(self):
        receipt = self.store.publish(self.data,'image/png')
        self.instant = receipt.expires_at-0.001
        self.assertIsNotNone(self.store.lookup(receipt.token,'png'))
        self.instant = receipt.expires_at
        self.assertIsNone(self.store.lookup(receipt.token,'png'))
        with sqlite3.connect(self.store.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM previews').fetchone()[0],1)
        self.assertEqual(self.store.prune(),1)
        self.assertEqual(self.store.prune(),0)

    def test_reopen_preserves_valid_links_and_startup_prunes_expired(self):
        old = self.store.publish(self.data,'image/png')
        self.instant += 100
        valid = self.store.publish(self.data,'image/png')
        self.store.close()
        self.instant = old.expires_at
        reopened = self.make_store()
        self.addCleanup(reopened.close)
        self.assertIsNone(reopened.lookup(old.token,'png'))
        self.assertEqual(reopened.lookup(valid.token,'png').data,self.data)
        with sqlite3.connect(reopened.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM previews').fetchone()[0],1)

    def test_byte_and_row_quota_boundaries_preserve_existing_links(self):
        for quota in ('rows','bytes'):
            store = self.make_store(max_rows=1 if quota=='rows' else 2,
                max_bytes=len(self.data) if quota=='bytes' else 10000)
            with self.subTest(quota=quota):
                # Each subcase uses a newly emptied private derivative table.
                with sqlite3.connect(store.path) as db:db.execute('DELETE FROM previews')
                first = store.publish(self.data,'image/png')
                with self.assertRaises(StoreFailure) as caught:store.publish(self.data,'image/png')
                self.assertEqual(caught.exception.code,'PreviewQuotaExceeded')
                self.assertEqual(store.lookup(first.token,'png').data,self.data)
            store.close()

    def test_prune_and_admit_are_one_transaction_with_expired_quota_reuse(self):
        store = self.make_store(max_rows=1,max_bytes=len(self.data))
        self.addCleanup(store.close)
        old = store.publish(self.data,'image/png')
        self.instant = old.expires_at
        new = store.publish(self.data,'image/png')
        self.assertIsNone(store.lookup(old.token,'png'))
        self.assertIsNotNone(store.lookup(new.token,'png'))

    def test_quota_rejection_still_commits_expired_pruning(self):
        expired = self.store.publish(self.data,'image/png')
        self.instant += 100
        valid = self.store.publish(self.data,'image/png')
        self.instant = expired.expires_at
        constrained = self.make_store(max_rows=1)
        self.addCleanup(constrained.close)
        # Put back one expired row after startup pruning, as if periodic cleanup
        # had been paused. A quota rejection must retain only the live row.
        with sqlite3.connect(constrained.path) as db:
            db.execute('INSERT INTO previews VALUES(?,?,?,?,?,?)',(token_digest(expired.token),
                'image/png',len(self.data),self.data,expired.expires_at-604800,expired.expires_at))
        with self.assertRaises(StoreFailure) as caught:constrained.publish(self.data,'image/png')
        self.assertEqual(caught.exception.code,'PreviewQuotaExceeded')
        self.assertIsNotNone(constrained.lookup(valid.token,'png'))
        with sqlite3.connect(constrained.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM previews').fetchone()[0],1)

    def test_competing_connections_cannot_overadmit_rows_or_bytes(self):
        stores = [self.make_store(max_rows=2,max_bytes=2*len(self.data)) for _ in range(4)]
        for store in stores:self.addCleanup(store.close)
        def issue(index):
            try:return stores[index%4].publish(self.data,'image/png')
            except StoreFailure as failure:return failure.code
        with ThreadPoolExecutor(max_workers=4) as executor:results = list(executor.map(issue,range(8)))
        accepted = [r for r in results if not isinstance(r,str)]
        self.assertEqual(len(accepted),2)
        self.assertEqual(results.count('PreviewQuotaExceeded'),6)
        with sqlite3.connect(self.store.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*),SUM(size_bytes) FROM previews').fetchone(),(2,2*len(self.data)))
        for receipt in accepted:self.assertEqual(self.store.lookup(receipt.token,'png').data,self.data)

    def test_failed_sql_transaction_publishes_nothing_and_preserves_previous(self):
        valid = self.store.publish(self.data,'image/png')
        with sqlite3.connect(self.store.path) as db:
            db.execute("CREATE TRIGGER reject_insert BEFORE INSERT ON previews BEGIN SELECT RAISE(ABORT,'private diagnostic'); END")
        with self.assertRaises(StoreFailure) as caught:self.store.publish(self.data,'image/png')
        self.assertEqual(str(caught.exception),'PreviewStorageUnavailable')
        self.assertNotIn('private',str(caught.exception))
        self.assertEqual(self.store.lookup(valid.token,'png').data,self.data)
        with sqlite3.connect(self.store.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM previews').fetchone()[0],1)

    def test_invalid_artifacts_do_not_consume_quota_or_publish(self):
        for data,mime in ((b'bad','image/png'),(self.data,'image/webp'),(self.data+b'bad','image/png'),
                (bytearray(self.data),'image/png')):
            with self.assertRaises(StoreFailure) as caught:self.store.publish(data,mime)
            self.assertEqual(caught.exception.code,'InvalidPreviewArtifact')
        self.assertIsNotNone(self.store.publish(self.data,'image/png'))

    def test_private_permissions_and_symlink_rejection_and_closed_state(self):
        self.store.publish(self.data,'image/png')
        for path in self.directory.iterdir():self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
        self.assertEqual(stat.S_IMODE(self.directory.stat().st_mode),0o700)
        link = self.directory.with_name('linked')
        link.symlink_to(self.directory,target_is_directory=True)
        with self.assertRaises(StoreFailure):PreviewStore(link)
        self.store.close()
        self.store.close()
        with self.assertRaises(StoreFailure):self.store.publish(self.data,'image/png')
        reopened = self.make_store()
        reopened.close()

    def test_active_sqlite_journal_is_private_during_publication(self):
        real_connect = sqlite3.connect
        observed = []
        case = self
        class Connection(sqlite3.Connection):
            def execute(self,sql,*args):
                result = super().execute(sql,*args)
                if sql.startswith('INSERT INTO previews'):
                    journal = Path(str(case.store.path)+'-journal')
                    case.assertTrue(journal.is_file())
                    case.assertEqual(stat.S_IMODE(journal.stat().st_mode),0o600)
                    observed.append(True)
                return result
        def connect(*args,**kwargs):return real_connect(*args,**kwargs,factory=Connection)
        with patch('foundry_mcp_server.image_preview_store.sqlite3.connect',side_effect=connect):
            self.store.publish(self.data,'image/png')
        self.assertEqual(observed,[True])

    def test_unsafe_database_sidecar_and_corruption_fail_without_native_details(self):
        link = Path(str(self.store.path)+'-journal')
        target = self.directory.with_name('outside')
        target.write_bytes(b'synthetic private content')
        link.symlink_to(target)
        with self.assertRaises(StoreFailure) as caught:self.make_store()
        self.assertEqual(str(caught.exception),'PreviewStorageUnavailable')
        link.unlink()
        self.store.close()
        self.store.path.write_bytes(b'not a private database')
        with self.assertRaises(StoreFailure) as caught:self.make_store()
        self.assertEqual(str(caught.exception),'PreviewStorageUnavailable')

    def test_production_limits_remain_independent_of_test_quotas(self):
        self.assertEqual((self.store.max_bytes,self.store.max_rows),(1024**3,4096))
        self.assertEqual(limits.PREVIEW_TTL_SECONDS,604800)
