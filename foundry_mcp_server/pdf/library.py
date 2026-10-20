"""Private immutable PDF sources and transactional page/entry FTS index."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import uuid
from contextlib import contextmanager

class LibraryError(ValueError): pass

class Library:
    def __init__(self, config):
        self.config = config
        self.lock = asyncio.Lock()
        self.tasks = set()
        self.jobs = {}
        self.started = False
        self.scan_lock = asyncio.Lock()
        self.reservations = {}

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.config.state / 'library.sqlite3', timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def setup(self):
        for root in (self.config.library, self.config.state):
            root.mkdir(mode=0o700, parents=True, exist_ok=True)
            if root.is_symlink() or root.resolve()!=root or not root.is_dir(): raise LibraryError('Private storage unavailable')
            root.chmod(0o700)
        incoming=self.config.library/'.incoming'
        incoming.mkdir(mode=0o700,exist_ok=True)
        if incoming.is_symlink(): raise LibraryError('Private storage unavailable')
        for p in incoming.iterdir():
            if re.fullmatch(r'[a-f0-9]{32}',p.name) and not p.is_dir(): p.unlink()
        for name in ('staging', 'pending', 'results'):
            p = self.config.state / name
            p.mkdir(mode=0o700, exist_ok=True)
            if p.is_symlink(): raise LibraryError('Private storage unavailable')
        if (self.config.state/'library.sqlite3').is_symlink(): raise LibraryError('Private storage unavailable')
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, name TEXT, sha256 TEXT UNIQUE, size_bytes INTEGER,
              status TEXT, revision TEXT, page_count INTEGER DEFAULT 0, error TEXT);
            CREATE TABLE IF NOT EXISTS pages(document_id TEXT, page INTEGER, label TEXT, text TEXT, warnings TEXT,
              PRIMARY KEY(document_id,page));
            CREATE TABLE IF NOT EXISTS entries(document_id TEXT, page INTEGER, title TEXT, context TEXT, provenance TEXT);
            CREATE VIRTUAL TABLE IF NOT EXISTS page_fts USING fts5(document_id UNINDEXED,page UNINDEXED,text);
            CREATE INDEX IF NOT EXISTS entries_document ON entries(document_id);
            ''')
        # Only our server-owned opaque names; never follow user-created symlinks.
        for directory in ('staging', 'results'):
            for p in (self.config.state / directory).iterdir():
                if re.fullmatch(r'[a-f0-9]{32}(?:\.json)?', p.name) and not p.is_dir(): p.unlink()
        (self.config.state/'library.sqlite3').chmod(0o600)
        with self.db() as db:
            known={r['id'] for r in db.execute('SELECT id FROM documents')}
        for p in (self.config.state/'pending').iterdir():
            if re.fullmatch(r'[a-f0-9]{32}',p.name) and p.name not in known and not p.is_dir(): p.unlink()
        self.started = True

    async def start(self):
        await asyncio.to_thread(self.setup)
        with self.db() as db:
            rows = db.execute("SELECT id FROM documents WHERE status IN ('queued','validating','indexing')").fetchall()
        for r in rows: self.enqueue(r['id'])

    async def close(self):
        for task in list(self.tasks): task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    def enqueue(self, document_id):
        if document_id in self.jobs: return
        task = asyncio.create_task(self.index(document_id))
        self.tasks.add(task)
        self.jobs[document_id]=task
        task.add_done_callback(self.tasks.discard)
        task.add_done_callback(lambda _: self.jobs.pop(document_id,None))

    def documents(self, offset=0, limit=20):
        with self.db() as db:
            rows = db.execute('SELECT id AS document_id,name,sha256,size_bytes,status,revision,page_count,error FROM documents ORDER BY name,id LIMIT ? OFFSET ?', (limit+1,offset)).fetchall()
        documents=[]
        with self.db() as db:
            for r in rows[:limit]:
                item=dict(r)
                item['warnings']=['reading_order_unverified','table_structure_unverified','untrusted_source_content'] if r['status']=='ready' else []
                if db.execute("SELECT 1 FROM pages WHERE document_id=? AND warnings LIKE '%sparse_text_no_ocr%' LIMIT 1",(r['document_id'],)).fetchone():
                    item['warnings'].append('sparse_text_no_ocr')
                documents.append(item)
        return dict(documents=documents, next_offset=offset+limit if len(rows)>limit else None)

    def status(self, document_id):
        with self.db() as db:
            row = db.execute('SELECT id AS document_id,name,status,revision,page_count,error FROM documents WHERE id=?',(document_id,)).fetchone()
        if row is None: raise LibraryError('Unknown document_id; use list_pdf_documents')
        return dict(row)

    def usage(self):
        return sum(p.stat().st_size for root in (self.config.library,self.config.state)
                   for p in root.rglob('*') if p.is_file() and not p.is_symlink())

    def accept(self, path, name, digest, size):
        with self.db() as db:
            existing = db.execute('SELECT id,status FROM documents WHERE sha256=?',(digest,)).fetchone()
            if existing:
                path.unlink(missing_ok=True)
                if existing['status']=='failed':
                    # A failed parser result is deterministic until explicit refresh retries it.
                    return existing['id'], True
                return existing['id'], True
            identifier = uuid.uuid4().hex
            destination = self.config.state/'pending'/identifier
            os.replace(path, destination)
            try:
                db.execute('INSERT INTO documents(id,name,sha256,size_bytes,status,revision) VALUES(?,?,?,?,?,?)',
                           (identifier,name,digest,size,'queued',digest))
            except BaseException:
                destination.unlink(missing_ok=True)
                raise
        return identifier, False

    async def index(self, identifier):
        async with self.lock:
            output = self.config.state/'results'/(uuid.uuid4().hex+'.json')
            process = None
            try:
                with self.db() as db:
                    row = db.execute('SELECT * FROM documents WHERE id=?',(identifier,)).fetchone()
                    db.execute("UPDATE documents SET status='validating',error=NULL WHERE id=?",(identifier,))
                source = self.config.state/'pending'/identifier
                final = self.config.library/(row['sha256']+'.pdf')
                if not source.exists(): source = final
                if source.is_symlink() or final.is_symlink() or not source.is_file(): raise LibraryError('missing')
                if await asyncio.to_thread(hash_file, source) != row['sha256']: raise LibraryError('source_changed')
                process = await asyncio.create_subprocess_exec(sys.executable,'-m','foundry_mcp_server.pdf.worker',str(source),str(output),
                    stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
                await asyncio.wait_for(process.wait(),120)
                if process.returncode or not output.is_file() or output.stat().st_size>33554432: raise LibraryError('parse')
                data = await asyncio.to_thread(lambda: json.loads(output.read_text()))
                text_bytes=sum(len(p['text'].encode()) for p in data['pages'])
                if self.usage()+sum(self.reservations.values())+text_bytes*5>self.config.quota: raise LibraryError('index_quota')
                if source != final:
                    # State and source storage can be different Docker filesystems.
                    # Promote only inside the destination filesystem after a durable copy.
                    def promote():
                        temporary=self.config.library/'.incoming'/uuid.uuid4().hex
                        try:
                            fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                            with os.fdopen(fd,'wb') as target, source.open('rb') as original:
                                shutil.copyfileobj(original,target,65536)
                                target.flush();os.fsync(target.fileno())
                            os.replace(temporary,final)
                            directory=os.open(self.config.library,os.O_RDONLY|os.O_DIRECTORY)
                            try: os.fsync(directory)
                            finally: os.close(directory)
                        finally: temporary.unlink(missing_ok=True)
                    await asyncio.to_thread(promote)
                def commit():
                    with self.db() as db:
                        db.execute("UPDATE documents SET status='indexing' WHERE id=?",(identifier,))
                        db.execute('DELETE FROM pages WHERE document_id=?',(identifier,))
                        db.execute('DELETE FROM entries WHERE document_id=?',(identifier,))
                        db.execute('DELETE FROM page_fts WHERE document_id=?',(identifier,))
                        for p in data['pages']:
                            db.execute('INSERT INTO pages VALUES(?,?,?,?,?)',(identifier,p['page'],p['label'],p['text'],json.dumps(p['warnings'])))
                            db.execute('INSERT INTO page_fts VALUES(?,?,?)',(identifier,p['page'],' '.join(p['text'].split())))
                        for e in data['entries']:
                            db.execute('INSERT INTO entries VALUES(?,?,?,?,?)',(identifier,e['page'],e['title'],json.dumps(e['context']),e['provenance']))
                        db.execute("UPDATE documents SET status='ready',page_count=?,error=NULL WHERE id=?",(len(data['pages']),identifier))
                await asyncio.to_thread(commit)
                if source != final: source.unlink(missing_ok=True)
            except asyncio.CancelledError:
                raise
            except Exception:
                with self.db() as db:
                    db.execute("UPDATE documents SET status='failed',error='PDF unavailable, encrypted, invalid, or parsing/resource limit exceeded; inspect storage and retry refresh' WHERE id=?",(identifier,))
            finally:
                if process and process.returncode is None:
                    process.kill()
                    await process.wait()
                try: output.unlink(missing_ok=True)
                except OSError: pass  # Startup retries cleanup; never log private source paths.

    async def scan(self):
        async with self.scan_lock:
            return await self._scan()

    async def _scan(self):
        # Only top-level regular files in the configured root; names never supplied by an LLM.
        added = []
        with self.db() as db:
            retry=[r['id'] for r in db.execute("SELECT id FROM documents WHERE status='failed'")]
        for identifier in retry: self.enqueue(identifier)
        for path in sorted(self.config.library.glob('*.pdf')):
            if path.is_symlink() or not path.is_file() or path.stat().st_size>self.config.max_bytes: continue
            digest = await asyncio.to_thread(hash_file,path)
            with self.db() as db:
                row = db.execute('SELECT id,status FROM documents WHERE sha256=?',(digest,)).fetchone()
            if row:
                if row['status']=='failed': self.enqueue(row['id'])
                continue
            size = path.stat().st_size
            if self.usage()+sum(self.reservations.values())+size > self.config.quota: raise LibraryError('PDF storage quota exceeded')
            staging = self.config.state/'staging'/uuid.uuid4().hex
            await asyncio.to_thread(shutil.copyfile,path,staging)
            staging.chmod(0o600)
            if await asyncio.to_thread(hash_file, staging) != digest:
                staging.unlink(missing_ok=True)
                raise LibraryError('Source changed during scan; retry')
            identifier,_ = self.accept(staging,safe_name(path.name),digest,size)
            self.enqueue(identifier)
            added.append(identifier)
        return dict(queued_document_ids=added, message='Poll list_pdf_documents until ready; failed sources require repair. Existing ready content is immutable by SHA-256.')

    def read(self, identifier, page, revision=None, offset=0, max_chars=8000):
        state = self.status(identifier)
        if state['status']!='ready': raise LibraryError('Document is not ready; use list_pdf_documents')
        if revision is not None and revision!=state['revision']: raise LibraryError('Stale revision; rediscover document and restart reading')
        with self.db() as db:
            row = db.execute('SELECT * FROM pages WHERE document_id=? AND page=?',(identifier,page)).fetchone()
        if row is None: raise LibraryError('Physical page out of range; consult page_count')
        if offset>len(row['text']): raise LibraryError('Offset outside source text')
        text = row['text'][offset:offset+max_chars]
        return dict(document_id=identifier,name=state['name'],revision=state['revision'],physical_page=page,
                    page_label=row['label'],text=text,warnings=json.loads(row['warnings']),
                    next_offset=offset+len(text) if offset+len(text)<len(row['text']) else None,
                    total_characters=len(row['text']))

    def search(self, query, identifier=None, offset=0, limit=10, locate=False):
        words = re.findall(r'\w+',query, re.UNICODE)
        if not words or len(query)>300 or len(words)>30: raise LibraryError('Use a nonempty query of at most 300 characters and 30 words')
        if identifier: self.status(identifier)
        match = ' AND '.join('"'+w+'"' for w in words)
        with self.db() as db:
            rows = db.execute('''SELECT f.document_id,f.page,d.name,d.revision,p.label,p.warnings,
                 snippet(page_fts,2,'','', ' … ',30) AS snippet,bm25(page_fts) AS rank
                 FROM page_fts f JOIN documents d ON d.id=f.document_id
                 JOIN pages p ON p.document_id=f.document_id AND p.page=f.page
                 WHERE page_fts MATCH ? AND d.status='ready' AND (? IS NULL OR d.id=?)
                 ORDER BY rank,d.id,f.page LIMIT 2000''',(match,identifier,identifier)).fetchall()
            results = []
            for r in rows:
                entries = [dict(e) for e in db.execute('SELECT title,context,provenance FROM entries WHERE document_id=? AND page=?',(r['document_id'],r['page']))]
                exact = [e for e in entries if normalized(e['title'])==normalized(query)]
                chosen = exact or entries[:5]
                for e in chosen:
                    e['context']=json.loads(e['context'])
                    e['optional_variant_evidence']=any('variant' in s.casefold() for s in e['context'])
                results.append(dict(document_id=r['document_id'],name=r['name'],revision=r['revision'],physical_page=r['page'],page_label=r['label'],
                    snippet=r['snippet'],entries=chosen,warnings=json.loads(r['warnings']),exact_heading_candidate=bool(exact)))
            if locate:
                # Exact headings/bookmarks can exist even when extracted page text is empty.
                for e in db.execute('''SELECT e.*,d.name,d.revision,p.label,p.warnings FROM entries e JOIN documents d ON d.id=e.document_id
                    JOIN pages p ON p.document_id=e.document_id AND p.page=e.page
                    WHERE d.status='ready' AND (? IS NULL OR d.id=?) LIMIT 20000''',(identifier,identifier)):
                    if normalized(e['title'])!=normalized(query): continue
                    if any(r['document_id']==e['document_id'] and r['physical_page']==e['page'] for r in results): continue
                    context=json.loads(e['context'])
                    results.append(dict(document_id=e['document_id'],name=e['name'],revision=e['revision'],physical_page=e['page'],page_label=e['label'],snippet='',
                        entries=[dict(title=e['title'],context=context,provenance=e['provenance'],optional_variant_evidence=any('variant' in s.casefold() for s in context))],
                        warnings=json.loads(e['warnings']),exact_heading_candidate=True))
                results.sort(key=lambda r:not r['exact_heading_candidate'])
        return dict(candidates=results[offset:offset+limit],next_offset=offset+limit if offset+limit<len(results) else None,
                    candidate_cap_reached=len(rows)==2000,message='Candidates are not proof. Read physical pages with read_pdf_pages before mechanical claims. Tables and heading roles require verification; no similarity confidence is reported.')

def normalized(value): return ' '.join(value.casefold().split())

def hash_file(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        while chunk:=stream.read(65536): digest.update(chunk)
    return digest.hexdigest()

def safe_name(value):
    if not isinstance(value,str) or not 1<=len(value)<=180 or value in {'.','..'} or any(ord(c)<32 or ord(c)==127 or c in '/\\:' for c in value):
        raise LibraryError('Use a plain PDF filename without paths or control characters')
    if not value.casefold().endswith('.pdf'): raise LibraryError('Select a PDF file')
    return value
