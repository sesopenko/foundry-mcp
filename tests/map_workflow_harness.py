"""External catalog fixture plus bounded real-worker large annotation evidence."""
import asyncio
import copy
from dataclasses import asdict
from io import BytesIO
import json
from pathlib import Path
import tempfile

from PIL import Image
import test_map_image_tools as map_tools
from image_preview_measurement_harness import generate_map,region_oracle,ResourceEvidence
from foundry_mcp_server.image_preview_resources import WorkerMetrics
from foundry_mcp_server.map_note_render import render_annotated


class MapWorkflowBackend(map_tools.MapToolBackend):
    def __init__(self):
        super().__init__()
        self.folders=[dict(id='root',name='Adventure',folder=None,sorting='a',sort=0),
            dict(id='chapter',name='Chapter',folder='root',sorting='m',sort=0),
            dict(id='copy',name='Chapter',folder='root',sorting='a',sort=1)]
        self.scene.update(folder='chapter',sort=5,width=5940,height=7920,padding=.25,shiftX=0,shiftY=0,
            initialLevel='floor',grid=dict(type=1,size=180,distance=5,units='ft',style='solid',thickness=1,color='#000000',alpha=.35),
            rectangle=dict(sceneX=1620,sceneY=2160,sceneWidth=5940,sceneHeight=7920))
        self.scene['notes'][0].update(x=4590,y=6120)
        self.scene['notes'].append(dict(id='note02',x=4650,y=6200,text='Second',levels=[],entryId='journal',pageId='page'))
        self.scene['levels'].extend([dict(id='empty',name='Empty',sort=1,background={}),
            dict(id='video',name='Video',sort=2,background=dict(src='assets/a.webm'))])
        self.scene['tiles']=[dict(id='tile',name='Artwork',sort=0,levels=['floor'],x=10,y=20,width=100,height=200,
            rotation=15,texture=dict(src='assets/a.png'))]
        self.primary=self.scene;self.copy=copy.deepcopy(self.scene);self.copy.update(id='copy',folder='copy',sort=1)

    async def result(self,method,params):
        if method=='browseMaps':
            process=await asyncio.create_subprocess_exec('node',str(Path(__file__).parent/'js/fixtures/map-browse-rpc.js'),
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
            try:
                output,_=await asyncio.wait_for(process.communicate(json.dumps(dict(params=params,folders=self.folders,scenes=[self.primary,self.copy])).encode()),5)
            except BaseException:
                if process.returncode is None:process.kill()
                await process.wait();raise
            response=json.loads(output)
            if response.get('error'):raise map_tools.RpcError(response['error'])
            return response['result']
        selected=params.get('scene_uuid') or params.get('map',{}).get('scene_uuid')
        self.scene=self.copy if selected=='Scene.copy' else self.primary
        return await super().result(method,params)


async def large_annotations(width=10000,height=10000):
    """One overview and native bottom-right crop, independent unpainted pixels."""
    async with asyncio.timeout(120):
        with tempfile.TemporaryDirectory(prefix='map-annotated-large-') as directory:
            path=Path(directory)/'source';seed=73;generate_map(path,width,height,seed)
            pins=[('N1',width//2,height//2),('N2',width-80,height-80)]
            resources=ResourceEvidence();rows=[]
            for crop,selected in [(None,pins),(dict(x=width-150,y=height-150,width=150,height=150),[pins[1]])]:
                metrics=WorkerMetrics();rendered=await render_annotated(path,crop,selected,len(selected),metrics=metrics)
                resources.add(metrics)
                if rendered.notes.keys!=[pin[0] for pin in selected] or not rendered.notes.complete:raise ValueError('AnnotationMissing')
                with Image.open(BytesIO(rendered.data)) as decoded:
                    decoded.load()
                    if crop:
                        # Bottom-right24-square is far from pin/leader/label extents.
                        corner=dict(x=width-24,y=height-24,width=24,height=24)
                        actual=decoded.convert('RGB').crop((126,126,150,150)).tobytes()
                        if actual!=region_oracle(width,height,seed,corner):raise ValueError('IndependentMapPixelsDiffer')
                        if decoded.convert('RGB').getpixel((70,70))!=(255,255,255):raise ValueError('IndependentPinPositionDiffer')
                    if max(decoded.size)>2048 or decoded.width*decoded.height>2359296 or len(rendered.data)>2097152:raise ValueError('OutputBudgetExceeded')
                rows.append(dict(width=rendered.geometry.width,height=rendered.geometry.height,bytes=len(rendered.data),
                    notes=rendered.notes.model_dump(),metrics=asdict(metrics)))
            return dict(passed=True,source_width=width,source_height=height,renders=rows,resources=resources.summary())
