"""Bounded local acceptance helpers; never production routes or public MCP tools."""
import contextlib
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import io
import json
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import threading
import time
from urllib.parse import urlsplit

from PIL import Image,PngImagePlugin

PREVIEW_PATH=re.compile(r'^/image-previews/[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}\.(jpg|png|webp)$')
MARKER=re.compile(r'^[a-f0-9]{32}$')


def require(condition):
    if not condition:raise ValueError('LocalPreviewAcceptanceFailed')


def compact(value):return len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())


class Budget:
    def __init__(self,limit=60,seconds=1200,*,clock=time.monotonic):
        self.limit,self.clock,self.deadline=limit,clock,clock()+seconds
        self.calls=0;self.rows=[]

    def admit(self,*,cleanup=False):
        require(self.calls<self.limit and self.clock()<self.deadline+(30 if cleanup else 0))
        self.calls+=1


class AssetFixture:
    """Only one newly created exact marker directory/file is eligible for cleanup."""
    def __init__(self,data_root,marker):
        require(MARKER.fullmatch(marker) is not None)
        self.root=Path(data_root).resolve();self.marker=marker
        self.path=self.root/('mcp-preview-verify-'+marker)
        self.filename='α '+marker+'.png';self.created=False

    def __enter__(self):
        self.path.mkdir(mode=0o700);self.created=True
        try:
            (self.path/'.preview-owner').write_text(self.marker)
            metadata=PngImagePlugin.PngInfo();metadata.add_text('Technical fixture','bounded-transfer-'*4000)
            Image.new('RGB',(512,384),(40,80,120)).save(self.path/self.filename,format='PNG',pnginfo=metadata)
        except BaseException:self.cleanup();raise
        return self

    @property
    def src(self):return self.path.name+'/'+self.filename

    def cleanup(self):
        if not self.created:return
        require(not self.path.is_symlink() and self.path.parent==self.root)
        require((self.path/'.preview-owner').read_text()==self.marker)
        require({p.name for p in self.path.iterdir()}<={'.preview-owner',self.filename})
        for path in self.path.iterdir():require(path.is_file() and not path.is_symlink())
        shutil.rmtree(self.path);self.created=False

    def __exit__(self,*_):self.cleanup()


@contextlib.contextmanager
def preview_settings(path,origin,directory):
    """Temporarily amend only private fixture configuration, with exact restoration."""
    path=Path(path);require(path.is_file() and not path.is_symlink())
    original=path.read_bytes()
    require(not any(line.split(b'=',1)[0].strip() in
        (b'FOUNDRY_MCP_IMAGE_PREVIEW_ORIGIN',b'FOUNDRY_MCP_IMAGE_PREVIEW_DATA_DIR') for line in original.splitlines()))
    require('\n' not in origin and '\n' not in str(directory) and Path(directory).is_absolute())
    amended=original+b'\nFOUNDRY_MCP_IMAGE_PREVIEW_ORIGIN='+origin.encode()+b'\nFOUNDRY_MCP_IMAGE_PREVIEW_DATA_DIR='+str(directory).encode()+b'\n'
    try:
        path.write_bytes(amended)
        yield
    finally:
        require(path.read_bytes()==amended)
        path.write_bytes(original)


class PreviewTLS:
    """Loopback-only test TLS; exact anonymous preview paths, fixed existing upstream."""
    def __init__(self,directory):self.directory=Path(directory);self.server=None

    def __enter__(self):
        certificate=self.directory/'localhost.pem';key=self.directory/'localhost.key'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
            '-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost',
            '-keyout',str(key),'-out',str(certificate)],check=True,capture_output=True,timeout=15)
        key.chmod(0o600)
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def finish(self):
                super().finish()
                # A reader waiting for HEAD's empty body must see TLS
                # close_notify, not an unclean transport EOF (curl error56).
                self.connection.settimeout(5)
                try:self.connection.unwrap().close()
                except (OSError,ssl.SSLError):pass
            def handle_preview(self):
                if not PREVIEW_PATH.fullmatch(self.path.partition('?')[0]):
                    self.send_error(404);return
                upstream=http.client.HTTPConnection('127.0.0.1',8000,timeout=10)
                try:
                    upstream.request(self.command,self.path)
                    reply=upstream.getresponse();body=reply.read(2097153)
                    if len(body)>2097152:raise ValueError('Oversized preview')
                    self.send_response(reply.status)
                    for name in ('Content-Type','Content-Length','Cache-Control','X-Content-Type-Options'):
                        if (value:=reply.getheader(name)) is not None:self.send_header(name,value)
                    self.end_headers()
                    if self.command!='HEAD':self.wfile.write(body)
                except Exception:
                    self.close_connection=True
                finally:upstream.close()
            do_GET=handle_preview
            do_HEAD=handle_preview
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.daemon_threads=True
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(certificate,key)
        self.server.socket=context.wrap_socket(self.server.socket,server_side=True)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.origin='https://localhost:'+str(self.server.server_port);self.certificate=certificate
        return self

    def __exit__(self,*_):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=5)


def assert_delivery(status,headers,body,expected,*,head=False):
    require(status['status']==200 and status['redirects']==0)
    require(headers.get('content-type')==expected['mime_type'])
    require(headers.get('content-length')==str(expected['size_bytes']))
    require(headers.get('cache-control')=='private, no-store')
    require(headers.get('x-content-type-options')=='nosniff')
    require('location' not in headers and 'set-cookie' not in headers)
    if head:require(body==b'' and status['downloaded']==0)
    else:
        require(len(body)==expected['size_bytes'])
        with Image.open(io.BytesIO(body)) as decoded:
            decoded.load();require(decoded.size==(expected['width'],expected['height']))
            require('image/'+decoded.format.lower()==expected['mime_type'])
    return hashlib.sha256(body).hexdigest()


def curl_delivery(url,expected,origin,certificate,directory,*,execute=subprocess.run):
    """Pass capabilities only through private stdin config, never command arguments."""
    parsed=urlsplit(url)
    require(url.startswith(origin+'/') and parsed.scheme=='https' and not parsed.query and not parsed.fragment)
    require(PREVIEW_PATH.fullmatch(parsed.path) is not None)
    directory=Path(directory);hashes=[]
    for index,(method,suffix) in enumerate((('GET',''),('GET','?probe=1'),('HEAD',''))):
        header=directory/('headers-'+str(index));body=directory/('body-'+str(index))
        configuration='url = '+json.dumps(url+suffix)+'\n'
        args=['curl','--config','-','--silent','--show-error','--noproxy','*','--proto','=https',
            '--cacert',str(certificate),'--max-time','15','--max-filesize','2097152',
            '--dump-header',str(header),'--output',str(body),'--request',method,
            '--header','Connection: close','--write-out','{"status":%{http_code},"redirects":%{num_redirects},"downloaded":%{size_download}}']
        if method=='HEAD':args.append('--ignore-content-length')
        result=execute(args,input=configuration,text=True,capture_output=True,timeout=20)
        require(result.returncode==0)
        headers={line.partition(':')[0].lower():line.partition(':')[2].strip() for line in header.read_text().splitlines() if ':' in line}
        data=body.read_bytes();require(len(data)<=2097152)
        digest=assert_delivery(json.loads(result.stdout),headers,data,expected,head=method=='HEAD')
        if method=='GET':hashes.append(digest)
    require(hashes[0]==hashes[1])
    return dict(passed=True,requests=3,status=200,redirects=0,mime_type=expected['mime_type'],
        size_bytes=expected['size_bytes'],sha256=hashes[0],head_empty=True)


def cleanup_map_review(directory):
    """Remove only bounded newly marked derivative review files, never game data."""
    directory=Path(directory)
    require(not directory.is_symlink() and directory.is_dir())
    owner=directory/'.owner';require(owner.is_file() and not owner.is_symlink())
    require(MARKER.fullmatch(owner.read_text()) is not None)
    allowed={'.owner','overview.jpg','overview.png','overview.webp','detail.jpg','detail.png','detail.webp'}
    files=list(directory.iterdir())
    require(len(files)<=3 and {p.name for p in files}<=allowed)
    require(all(p.is_file() and not p.is_symlink() and p.stat().st_size<=2097152 for p in files))
    for path in files:path.unlink()
    directory.rmdir()
    return dict(cleanup_complete=True,files=len(files)-1)
