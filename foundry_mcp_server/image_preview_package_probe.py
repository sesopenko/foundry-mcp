"""Fixed private packaged-image checks; no MCP tool and no game-world access."""
import asyncio
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

from PIL import Image

from .image_preview_failure import PreviewFailure
from .image_preview_process import probe_image,render_preview
from .image_preview_store import PreviewStore
from .map_note_glyph_probe import probe_glyphs
from .map_note_render import render_annotated


def check(condition):
    if not condition:raise ValueError('PackageVerificationFailed')


async def seed(directory):
    """Generate small fixtures, render through shipped workers, persist one crop."""
    check(os.getuid()==10001)
    rows=[]
    with tempfile.TemporaryDirectory(prefix='preview-package-') as workspace:
        original=Path(workspace)/'source'
        for fmt,mime in [('JPEG','image/jpeg'),('PNG','image/png'),('WEBP','image/webp'),
                         ('AVIF','image/avif'),('BMP','image/bmp'),('GIF','image/gif'),('TIFF','image/tiff')]:
            options=dict(quality=100,max_threads=2) if fmt=='AVIF' else {}
            Image.new('RGB',(80,60),(40,80,120)).save(original,format=fmt,**options)
            metadata=await probe_image(original)
            rendered=await render_preview(original,dict(x=10,y=10,width=40,height=30))
            check((metadata.width,metadata.height,metadata.mime_type)==(80,60,mime))
            with Image.open(io.BytesIO(rendered.data)) as decoded:
                check(decoded.size==(40,30))
                check(max(abs(a-b) for a,b in zip(decoded.convert('RGB').getpixel((0,0)),(40,80,120)))<=4)
            rows.append(fmt)
        # Exercise the animated PNG policy in the shipped decoder too.
        first=Image.new('RGB',(80,60),(40,80,120));second=Image.new('RGB',(80,60),(200,20,40))
        first.save(original,format='PNG',save_all=True,append_images=[second],duration=100)
        check((await probe_image(original)).frame_policy=='first_frame')
        check((await render_preview(original)).geometry.width==80)
        rows.append('APNG')
        original.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 60"><rect width="80" height="60" fill="#285078"/></svg>')
        check((await probe_image(original)).mime_type=='image/svg+xml')
        check((await render_preview(original)).geometry.width==80)
        rows.append('SVG')
        original.write_text('<svg xmlns="http://www.w3.org/2000/svg"><image href="https://invalid.example/private.png"/></svg>')
        try:await render_preview(original)
        except PreviewFailure as error:check(error.code=='UnsupportedImage')
        else:raise ValueError('UnsafeSvgAccepted')
        first.resize((500,500)).save(original,format='PNG')
        atlas=await probe_glyphs(['N1','N12','N100'])
        check(atlas.sizes==((22,14),(32,14),(43,14)))
        annotated=await render_annotated(original,None,[('N1',250,250)],1)
        repeated=await render_annotated(original,None,[('N1',250,250)],1)
        check(repeated.data==annotated.data and repeated.notes==annotated.notes)
        check(annotated.notes.keys==['N1'] and annotated.notes.complete)
        with Image.open(io.BytesIO(annotated.data)) as decoded:
            check(decoded.convert('RGB').getpixel((250,250))==(255,255,255))
        store=PreviewStore(directory)
        try:receipt=store.publish(annotated.data,annotated.geometry.mime_type)
        finally:store.close()
        state=dict(token=receipt.token,extension=receipt.extension,sha256=hashlib.sha256(annotated.data).hexdigest(),
            size_bytes=len(annotated.data),mime_type=receipt.mime_type)
        path=Path(directory)/'package-receipt.json'
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(descriptor,'w') as stream:json.dump(state,stream)
        check(stat.S_IMODE(Path(directory).stat().st_mode)==0o700)
        check(stat.S_IMODE((Path(directory)/'previews.sqlite3').stat().st_mode)==0o600)
    import PIL,pyvips
    return dict(passed=True,uid=os.getuid(),formats=rows,unsafe_svg_rejected=True,
        glyph_sizes=atlas.sizes,rendered_keys=1,private_permissions=True,
        pillow=PIL.__version__,pyvips=pyvips.__version__,libvips='.'.join(str(pyvips.version(i)) for i in range(3)),
        sha256=state['sha256'],size_bytes=state['size_bytes'])


def fetch(directory):
    """Read the private receipt and check the real listener without credentials."""
    state=json.loads((Path(directory)/'package-receipt.json').read_text())
    path='/image-previews/'+state['token']+'.'+state['extension']
    connection=http.client.HTTPConnection('127.0.0.1',8000,timeout=10)
    try:
        for method,suffix in [('GET',''),('GET','?probe=1'),('HEAD','')]:
            connection.request(method,path+suffix)
            response=connection.getresponse();data=response.read(2097153)
            check(response.status==200)
            check(response.getheader('Content-Type')==state['mime_type'])
            check(response.getheader('Content-Length')==str(state['size_bytes']))
            check(response.getheader('Cache-Control')=='private, no-store')
            check(response.getheader('X-Content-Type-Options')=='nosniff')
            check(response.getheader('Location') is None and response.getheader('Set-Cookie') is None)
            check(not data if method=='HEAD' else hashlib.sha256(data).hexdigest()==state['sha256'])
    finally:connection.close()
    return dict(passed=True,uid=os.getuid(),anonymous_requests=3,sha256=state['sha256'],size_bytes=state['size_bytes'])


def main():
    if sys.argv[1:] not in (['seed'],['fetch']):return 2
    try:
        directory='/data/image-previews'
        report=asyncio.run(seed(directory)) if sys.argv[1]=='seed' else fetch(directory)
    except Exception as error:report=dict(passed=False,error_type=type(error).__name__)
    print(json.dumps(report,sort_keys=True));return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
