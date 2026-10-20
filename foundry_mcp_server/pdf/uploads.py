"""Connection-bound, independently authorized stop-and-wait upload protocol v1."""
import asyncio
import base64
import binascii
import hashlib
import os
import secrets
import shutil
import time
import uuid
from .library import LibraryError, safe_name

CHUNK_BYTES = 32768

class Uploads:
    def __init__(self, library, send):
        self.library, self.config, self.send = library, library.config, send
        self.authorized = {}
        self.sessions = {}
        self.lock = asyncio.Lock()
        self.timer = None

    def start(self): self.timer = asyncio.create_task(self.reap())

    async def close(self):
        if self.timer:
            self.timer.cancel()
            await asyncio.gather(self.timer,return_exceptions=True)
        for ws in list(self.sessions): await self.disconnect(ws)

    async def reap(self):
        while True:
            await asyncio.sleep(min(self.config.idle,10))
            async with self.lock:
                for ws,s in list(self.sessions.items()):
                    if time.monotonic()-s['touched']>self.config.idle:
                        self.remove(ws)

    def remove(self,ws):
        session=self.sessions.pop(ws,None)
        self.library.reservations.pop(ws,None)
        if session:
            try: session['stream'].close()
            except OSError: pass
            try: session['path'].unlink(missing_ok=True)
            except OSError: pass  # Startup retries orphan cleanup after storage is repaired.

    async def disconnect(self,ws):
        async with self.lock:
            self.authorized.pop(ws,None)
            self.remove(ws)

    def check(self,ws):
        # Recheck capability fingerprint on every operation: config/token rotation revokes leases.
        if not self.config.uploads or (self.authorized.get(ws,('',0))[0]!=self.config.token or self.authorized.get(ws,('',0))[1]<time.monotonic()):
            self.remove(ws)
            raise LibraryError('Upload authorization expired or absent; authorize again')

    async def handle(self, ws, message, transport_secure):
        kind=message.get('type','')
        request=message.get('request_id')
        if not isinstance(request,str) or not 1<=len(request)<=80: request=None
        async def reply(type_,**data):
            await self.send(ws,dict(type=type_,request_id=request,protocol=1,**data))
        async with self.lock:
            try:
                if not self.config.uploads or not transport_secure: raise LibraryError('PDF uploads disabled or secure authenticated transport unavailable')
                if request is None or message.get('protocol')!=1: raise LibraryError('Protocol 1 and a bounded request_id are required')
                if kind=='pdf.upload.authorize':
                    self.authorized.pop(ws,None)
                    self.remove(ws)
                    token=message.get('token')
                    if message.get('protocol')!=1 or not isinstance(token,str) or len(token)>4096 or not secrets.compare_digest(token.encode(), self.config.token.encode()):
                        raise LibraryError('PDF upload authorization denied')
                    self.authorized[ws]=(self.config.token,time.monotonic()+3600)
                    await reply('pdf.upload.authorize_ack',chunk_bytes=CHUNK_BYTES)
                    return
                self.check(ws)
                if kind=='pdf.upload.list':
                    offset=message.get('offset',0)
                    if type(offset) is not int or not 0<=offset<=100000: raise LibraryError('Invalid list offset')
                    await reply('pdf.upload.list_ack',**self.library.documents(offset,20)); return
                if kind=='pdf.upload.index_status':
                    identifier=message.get('document_id')
                    if not isinstance(identifier,str) or len(identifier)!=32: raise LibraryError('Invalid document_id')
                    await reply('pdf.upload.index_status',**self.library.status(identifier)); return
                if kind=='pdf.upload.begin':
                    if ws in self.sessions: raise LibraryError('Cancel the existing upload first')
                    name=safe_name(message.get('name'))
                    size=message.get('size_bytes')
                    if type(size) is not int or not 0<size<=self.config.max_bytes: raise LibraryError('PDF size exceeds upload limit or is empty')
                    if len(self.sessions)>=self.config.concurrent: raise LibraryError('Too many active uploads; retry later')
                    reserved=sum(s['size']-s['accepted'] for s in self.sessions.values())
                    used=await asyncio.to_thread(self.library.usage)
                    free=await asyncio.to_thread(lambda: min(shutil.disk_usage(self.config.library).free,shutil.disk_usage(self.config.state).free))
                    if used+reserved+size>self.config.quota or free<reserved+size+268435456:
                        raise LibraryError('Insufficient PDF quota or free disk space')
                    identifier=uuid.uuid4().hex
                    path=self.config.state/'staging'/identifier
                    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                    self.library.reservations[ws]=size
                    self.sessions[ws]=dict(id=identifier,path=path,stream=os.fdopen(fd,'wb'),size=size,name=name,
                        accepted=0,seq=0,hash=hashlib.sha256(),touched=time.monotonic())
                    await reply('pdf.upload.begin_ack',upload_id=identifier,chunk_bytes=CHUNK_BYTES,accepted_bytes=0); return
                session=self.sessions.get(ws)
                if not session or message.get('upload_id')!=session['id']: raise LibraryError('Upload does not belong to this connection')
                session['touched']=time.monotonic()
                if kind=='pdf.upload.cancel':
                    self.remove(ws)
                    await reply('pdf.upload.cancel_ack'); return
                if kind=='pdf.upload.chunk':
                    encoded=message.get('data_base64')
                    if type(message.get('seq')) is not int or message['seq']!=session['seq']: raise LibraryError('Invalid chunk sequence; retry the upload')
                    if not isinstance(encoded,str) or len(encoded)>43692: raise LibraryError('Chunk exceeds limit')
                    try: data=base64.b64decode(encoded,validate=True)
                    except (ValueError,binascii.Error): raise LibraryError('Invalid base64 chunk') from None
                    if not 0<len(data)<=CHUNK_BYTES or session['accepted']+len(data)>session['size']: raise LibraryError('Chunk length exceeds declared size')
                    await asyncio.to_thread(session['stream'].write,data)
                    await asyncio.to_thread(session['stream'].flush)
                    session['hash'].update(data)
                    session['accepted']+=len(data); session['seq']+=1
                    self.library.reservations[ws]=session['size']-session['accepted']
                    await reply('pdf.upload.ack',upload_id=session['id'],accepted_bytes=session['accepted'],next_seq=session['seq']); return
                if kind=='pdf.upload.finish':
                    if session['accepted']!=session['size']: raise LibraryError('Incomplete transfer; exact declared length required')
                    await asyncio.to_thread(os.fsync,session['stream'].fileno())
                    session['stream'].close()
                    with session['path'].open('rb') as file:
                        if not file.read(8).startswith(b'%PDF-'): raise LibraryError('Content is not a PDF')
                    identifier,duplicate=await asyncio.to_thread(self.library.accept,session['path'],session['name'],session['hash'].hexdigest(),session['size'])
                    self.sessions.pop(ws)
                    self.library.reservations.pop(ws,None)
                    if not duplicate: self.library.enqueue(identifier)
                    # Completed bytes are durable in private pending storage. Not yet a validated/readable PDF.
                    await reply('pdf.upload.index_status',document_id=identifier,index_job_id=identifier,status=self.library.status(identifier)['status'],duplicate=duplicate); return
                raise LibraryError('Unknown PDF upload operation')
            except (LibraryError,OSError,ValueError,TypeError) as error:
                self.remove(ws)
                # Deliberately fixed diagnostic: parser/disk exceptions may contain private paths.
                await reply('pdf.upload.error',code='upload_rejected',message=str(error) if isinstance(error,LibraryError) else 'PDF storage operation failed; check writable private storage and free space, then retry.')
