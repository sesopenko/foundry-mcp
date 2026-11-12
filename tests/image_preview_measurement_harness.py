"""Private streamed PNG generation and independent region/resource evidence.

PNG wire format: https://www.w3.org/TR/png/ (third edition), critical chunks,
8-bit RGB/filter0/noninterlaced/zlib. At most16 source rows cached, never a full
large parent raster. Output reports technical aggregates only.
"""
import asyncio
from dataclasses import asdict
from io import BytesIO
import json
from pathlib import Path
import secrets
import struct
import tempfile
import zlib
from unittest.mock import patch
from uuid import uuid4

from PIL import Image

from image_preview_workflow_harness import workflow
from foundry_mcp_server.image_preview_resources import WorkerMetrics
from foundry_mcp_server.mcp_server import image_previews


def chunk(stream,name,data):
    stream.write(struct.pack('>I',len(data))+name+data+struct.pack('>I',zlib.crc32(name+data)))


def generate_map(path,width,height,seed):
    """Write a real complete map with center/four-edge marks, bounded row memory."""
    if (any(type(v) is not int for v in (width,height,seed)) or not 32<=width<=32768
            or not 32<=height<=32768 or width*height>128000000 or not 0<=seed<=255):
        raise ValueError('Invalid synthetic map bounds')
    rows=[]
    for band in range(16):
        row=bytearray()
        for x in range(width):row.extend(((x//37*11+band*17+seed)%256,
            (x%37*3+band*7+seed*3)%256,(x//101*5+band*13+seed*7)%256))
        rows.append(bytes(row))
    marks=((width//2,height//2),(7,7),(width-8,7),(7,height-8),(width-8,height-8))
    compressor=zlib.compressobj(6)
    pending=b''
    with Path(path).open('xb') as stream:
        stream.write(b'\x89PNG\r\n\x1a\n')
        chunk(stream,b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))
        for y in range(height):
            row=rows[y//29%16]
            for index,(cx,cy) in enumerate(marks):
                if abs(y-cy)>6:continue
                row=bytearray(row)
                colour=bytes(((seed+index*41)%256,(seed*3+index*53)%256,(seed*7+index*71)%256))
                for x in range(cx-6,cx+7):
                    if y==cy or x==cx:row[x*3:x*3+3]=colour
            pending+=compressor.compress(b'\0'+row)
            while len(pending)>=65536:
                chunk(stream,b'IDAT',pending[:65536]);pending=pending[65536:]
        pending+=compressor.flush()
        while pending:
            chunk(stream,b'IDAT',pending[:65536]);pending=pending[65536:]
        chunk(stream,b'IEND',b'')
    return dict(width=width,height=height,size_bytes=Path(path).stat().st_size,
        cached_row_bytes=sum(map(len,rows)))


def region_oracle(width,height,seed,region):
    """Independent scalar pixel oracle; allocates only the requested small region.

    Never reads/crops the generated original or calls the writer's row logic.
    """
    if region['width']*region['height']>2359296:raise ValueError('Oracle region too large')
    output=bytearray()
    centers=[(width//2,height//2),(7,7),(width-8,7),(7,height-8),(width-8,height-8)]
    for y in range(region['y'],region['y']+region['height']):
        vertical=(y//29)%16
        for x in range(region['x'],region['x']+region['width']):
            value=[(11*(x//37)+17*vertical+seed)%256,
                (3*(x%37)+7*vertical+3*seed)%256,(5*(x//101)+13*vertical+7*seed)%256]
            for i,(cx,cy) in enumerate(centers):
                if max(abs(x-cx),abs(y-cy))<=6 and (x==cx or y==cy):
                    value=[(seed+41*i)%256,(3*seed+53*i)%256,(7*seed+71*i)%256]
            output.extend(value)
    return bytes(output)


class ResourceEvidence:
    def __init__(self):self.rows=[]

    def add(self,metrics):
        row=asdict(metrics)
        if not (0<row['peak_rss_bytes']<=1073741824 and 0<=row['peak_scratch_bytes']<=2147483648
                and 0<row['elapsed_seconds']<=90 and row['samples']>0):
            raise RuntimeError('WorkerResourceEvidenceFailed')
        self.rows.append(row)

    def summary(self,start=0):
        rows=self.rows[start:]
        if not rows:raise RuntimeError('MissingWorkerEvidence')
        return dict(operations=len(rows),peak_rss_bytes=max(r['peak_rss_bytes'] for r in rows),
            peak_scratch_bytes=max(r['peak_scratch_bytes'] for r in rows),
            max_elapsed_seconds=max(r['elapsed_seconds'] for r in rows),
            total_elapsed_seconds=sum(r['elapsed_seconds'] for r in rows))


def verify_delivery(data,metadata):
    """Independently decode bounded HTTP pixels and verify reported budgets."""
    if len(data)!=metadata['size_bytes'] or not 0<len(data)<=2097152:raise RuntimeError('DeliveredByteMismatch')
    with Image.open(BytesIO(data)) as decoded:
        decoded.load()
        if decoded.size!=(metadata['width'],metadata['height']):raise RuntimeError('DeliveredDimensionMismatch')
        if Image.MIME[decoded.format]!=metadata['mime_type']:raise RuntimeError('DeliveredMimeMismatch')
        if max(decoded.size)>2048 or decoded.width*decoded.height>2359296:raise RuntimeError('DeliveredBudgetExceeded')


async def measure_maps(dimensions=((10000,10000),(10000,5000))):
    """Real MCP maps; CLI uses full dimensions, unit tests may inject small maps."""
    reports=[]
    calls=0
    active=None
    resources=ResourceEvidence()
    render=image_previews.render_preview
    async def measured(*args,**kwargs):
        metrics=WorkerMetrics()
        result=await render(*args,**kwargs,metrics=metrics)
        resources.add(metrics)
        return result
    try:
        async with asyncio.timeout(1200):
            with tempfile.TemporaryDirectory(prefix='preview-large-maps-') as directory,patch.object(image_previews,'render_preview',side_effect=measured):
                for width,height in dimensions:
                    resource_start=len(resources.rows)
                    seed=secrets.randbelow(256)
                    path=Path(directory)/uuid4().hex
                    generated=generate_map(path,width,height,seed)
                    image=dict(source='data',directory='maps',src='maps/'+uuid4().hex+'.png')
                    async with workflow(path.read_bytes(),image=image) as f:
                        active=f
                        catalog=await f.discovery()
                        if not {'get_foundry_image_info','get_foundry_image_url'}<=catalog['names']:raise RuntimeError('MissingImageTools')
                        info=await f.call('get_foundry_image_info',{'request':{'image':image}})
                        if (info['width'],info['height'])!=(width,height):raise RuntimeError('OriginalDimensionsMismatch')
                        before=(await f.stats())['fetches']
                        overview=await f.call('get_foundry_image_url',{'request':{'source_id':info['source_id']}})
                        pixels=await f.fetch(overview['url'])
                        verify_delivery(pixels,overview)
                        if width==height and width>=1536:
                            if (overview['width'],overview['height'])!=(1536,1536):raise RuntimeError('SquareOverviewMismatch')
                        if (width,height)==(10000,5000) and (overview['width'],overview['height'])!=(2048,1024):
                            raise RuntimeError('WideOverviewMismatch')
                        if len(pixels)!=overview['size_bytes'] or len(pixels)>2097152:raise RuntimeError('OverviewByteMismatch')
                        crops=[dict(x=width-32,y=height-32,width=32,height=32),dict(x=width-1,y=height-1,width=1,height=1),
                            dict(x=width//2-8,y=height//2-8,width=17,height=17)]
                        if (width,height)==(10000,5000):crops.append(dict(x=7200,y=3100,width=1280,height=960))
                        for crop in crops:
                            value=await f.call('get_foundry_image_url',{'request':{'source_id':info['source_id'],'crop':crop}})
                            if value['region']!=crop or (value['width'],value['height'])!=(crop['width'],crop['height']):
                                raise RuntimeError('NativeCropGeometryMismatch')
                            with Image.open(BytesIO(await f.fetch(value['url']))) as actual:
                                if actual.convert('RGB').tobytes()!=region_oracle(width,height,seed,crop):raise RuntimeError('IndependentPixelMismatch')
                        if width>=10000:
                            reduced=await f.call('get_foundry_image_url',{'request':{'source_id':info['source_id'],
                                'crop':dict(x=width-3000,y=height-3000,width=3000,height=3000)}})
                            verify_delivery(await f.fetch(reduced['url']),reduced)
                            if (reduced['width'],reduced['height'])!=(1536,1536):raise RuntimeError('ReducedCropMismatch')
                        invalid=await f.call('get_foundry_image_url',{'request':{'source_id':info['source_id'],
                            'crop':dict(x=width-1,y=0,width=2,height=1)}},error=True,label='invalid_crop')
                        if not invalid.get('isError') or 'InvalidCrop:' not in str(invalid['content']):raise RuntimeError('InvalidCropAccepted')
                        stats=await f.stats()
                        if before!=1 or stats['fetches']!=1 or stats['busy']:raise RuntimeError('SnapshotTransferReuseFailed')
                        calls+=f.calls
                        active=None
                        if calls>80:raise RuntimeError('MeasurementCallBudgetExceeded')
                        reports.append(dict(source={k:generated[k] for k in ('width','height','size_bytes')},
                            overview={k:overview[k] for k in ('width','height','mime_type','size_bytes')},
                            transfers=stats['fetches'],chunks=stats['chunks'],catalog_tools=catalog['tools'],
                            catalog_bytes=catalog['json_bytes'],expected_errors=1,complete=True,
                            resources=resources.summary(resource_start),overview_resources=resources.rows[resource_start],**f.report()))
        return dict(passed=True,calls=calls,maps=reports,resources=resources.summary())
    except Exception as error:
        return dict(passed=False,calls=calls+(active.calls if active is not None else 0),maps=reports,
            error_type=type(error).__name__,**({'partial':active.report()} if active is not None else {}))
