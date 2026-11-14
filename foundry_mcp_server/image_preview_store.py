"""Private immutable derivative BLOBs and digest-only seven-day capabilities.

Each operation owns its SQLite connection. BEGIN IMMEDIATE serializes pruning,
quota admission and publication across threads/processes. No source identity,
original bytes, crop selectors, or bearer token is persisted here.
"""
from contextlib import contextmanager
from dataclasses import dataclass,field
import hashlib
import math
import os
from pathlib import Path
import sqlite3
import time
import uuid

from . import image_preview_limits as limits
from .image_preview_artifact import inspect_artifact
from .image_preview_failure import PreviewFailure


class StoreFailure(ValueError):
    """Fixed internal category; tool integration supplies actionable recovery."""
    def __init__(self,code='PreviewStorageUnavailable'):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PublishedPreview:
    token: str = field(repr=False)
    extension: str
    mime_type: str
    size_bytes: int
    expires_at: float


@dataclass(frozen=True)
class StoredPreview:
    data: bytes = field(repr=False)
    mime_type: str
    size_bytes: int
    expires_at: float


def token_digest(token):
    """Accept only a canonical UUID4 capability, hash its random UUID bytes."""
    if not isinstance(token,str) or len(token)!=36:return None
    try:identifier = uuid.UUID(token)
    except ValueError:return None
    if identifier.version!=4 or str(identifier)!=token:return None
    return hashlib.sha256(identifier.bytes).digest()


class PreviewStore:
    def __init__(self,directory,*,clock=time.time,max_bytes=limits.STORE_MAX_BYTES,
                 max_rows=limits.STORE_MAX_ROWS):
        if type(max_bytes) is not int or max_bytes<1 or type(max_rows) is not int or max_rows<1:
            raise ValueError('Invalid preview store limits')
        self.directory = Path(directory).absolute()
        self.path = self.directory/'previews.sqlite3'
        self.clock,self.max_bytes,self.max_rows = clock,max_bytes,max_rows
        self.closed = False
        try:
            self.directory.mkdir(mode=0o700,parents=True,exist_ok=True)
            if self.directory.is_symlink() or self.directory.resolve()!=self.directory or not self.directory.is_dir():
                raise StoreFailure()
            self.directory.chmod(0o700)
            for suffix in ('','-journal','-wal','-shm'):
                candidate = Path(str(self.path)+suffix)
                if candidate.is_symlink():raise StoreFailure()
                if candidate.exists():
                    if not candidate.is_file() or candidate.stat().st_nlink!=1:raise StoreFailure()
                    candidate.chmod(0o600)
            if not self.path.exists():
                descriptor = os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                os.close(descriptor)
            with self.connection() as db:
                version=db.execute('PRAGMA user_version').fetchone()[0]
                if version not in (0,1,2):raise StoreFailure()
                db.execute('PRAGMA journal_mode=DELETE')
                db.execute('BEGIN IMMEDIATE')
                # Recheck after acquiring the writer lock: concurrent startup
                # may already have migrated this store. Never re-encode rows.
                version=db.execute('PRAGMA user_version').fetchone()[0]
                if version not in (0,1,2):raise StoreFailure()
                if version==1:
                    db.execute('ALTER TABLE previews RENAME TO previews_v1')
                db.execute('''CREATE TABLE IF NOT EXISTS previews(
                    digest BLOB PRIMARY KEY CHECK(length(digest)=32),
                    mime_type TEXT NOT NULL CHECK(mime_type IN ('image/jpeg','image/png','image/webp')),
                    size_bytes INTEGER NOT NULL CHECK(size_bytes>0 AND size_bytes<=2097152),
                    pixels BLOB NOT NULL CHECK(length(pixels)=size_bytes),
                    published_at REAL NOT NULL, expires_at REAL NOT NULL,
                    CHECK(expires_at=published_at+604800))''')
                if version==1:
                    db.execute('INSERT INTO previews SELECT * FROM previews_v1')
                    db.execute('DROP TABLE previews_v1')
                db.execute('CREATE INDEX IF NOT EXISTS preview_expiry ON previews(expires_at)')
                db.execute('PRAGMA user_version=2')
            self.prune()
        except (OSError,sqlite3.Error):
            raise StoreFailure() from None

    @contextmanager
    def connection(self):
        if self.closed:raise StoreFailure()
        db = None
        try:
            db = sqlite3.connect(self.path,timeout=5)
            db.execute('PRAGMA trusted_schema=OFF')
            db.execute('PRAGMA synchronous=FULL')
            db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH,4*1024*1024)
            with db:yield db
        except (sqlite3.Error,OSError):
            raise StoreFailure() from None
        finally:
            if db is not None:db.close()

    def now(self):
        instant = self.clock()
        if type(instant) not in (int,float) or not math.isfinite(instant):raise StoreFailure()
        return float(instant)

    def publish(self,data,mime_type):
        """Publish an already worker-decoded derivative after bounded revalidation.

        Container validation repeats MIME/length/geometry bounds, without parent
        pixel decoding. Only trusted render results should call this interface.
        Expired-row pruning commits even when a new issuance exceeds quota.
        """
        if type(data) is not bytes:raise StoreFailure('InvalidPreviewArtifact')
        try:actual = inspect_artifact(data)
        except PreviewFailure:raise StoreFailure('InvalidPreviewArtifact') from None
        if actual['mime_type']!=mime_type:raise StoreFailure('InvalidPreviewArtifact')
        token = str(uuid.uuid4())
        digest = token_digest(token)
        size = len(data)
        admitted = False
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            now = self.now()
            expiry = now+limits.PREVIEW_TTL_SECONDS
            db.execute('DELETE FROM previews WHERE expires_at<=?',(now,))
            count,used = db.execute('SELECT COUNT(*),COALESCE(SUM(size_bytes),0) FROM previews').fetchone()
            if count+1<=self.max_rows and used+size<=self.max_bytes:
                db.execute('INSERT INTO previews VALUES(?,?,?,?,?,?)',
                    (digest,mime_type,size,data,now,expiry))
                admitted = True
        if not admitted:raise StoreFailure('PreviewQuotaExceeded')
        extension={'image/jpeg':'jpg','image/png':'png','image/webp':'webp'}[mime_type]
        return PublishedPreview(token,extension,mime_type,size,expiry)

    def lookup(self,token,extension):
        """Return only this immutable live derivative, never original/region data."""
        digest = token_digest(token)
        if digest is None or extension not in ('jpg','png','webp'):return None
        mime = 'image/jpeg' if extension=='jpg' else 'image/'+extension
        with self.connection() as db:
            row = db.execute('SELECT pixels,mime_type,size_bytes,expires_at FROM previews WHERE digest=? AND mime_type=? AND expires_at>?',
                (digest,mime,self.now())).fetchone()
        return StoredPreview(*row) if row else None

    def prune(self):
        """Safe startup/periodic cleanup; lookup expiry never depends on its run."""
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            return db.execute('DELETE FROM previews WHERE expires_at<=?',(self.now(),)).rowcount

    def close(self):
        """No persistent connections/tasks; runtime drains operations before close."""
        self.closed = True
