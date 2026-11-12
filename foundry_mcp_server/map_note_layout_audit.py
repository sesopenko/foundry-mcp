"""Three bounded synthetic renders for local visual obstruction review."""
import argparse
import asyncio
from dataclasses import asdict
from pathlib import Path
import tempfile

from PIL import Image,ImageDraw

from .image_preview_resources import WorkerMetrics
from .map_note_render import render_annotated


async def audit(output):
    """No Foundry data, game writes, URLs or hidden-answer acceptance claims."""
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    results=[]
    async with asyncio.timeout(120):
        with tempfile.TemporaryDirectory(prefix='map-note-visual-') as directory:
            source=Path(directory)/'source.png'
            image=Image.new('RGB',(2000,1600),(185,180,165));draw=ImageDraw.Draw(image)
            for row in range(4):
                for col in range(5):
                    x=col*400+30;y=row*400+30
                    color=(40,45,50) if (col+row)%2 else (230,225,210)
                    draw.rectangle((x,y,x+340,y+340),fill=color,outline=(90,85,75),width=12)
                    draw.ellipse((x+140,y+140,x+200,y+200),outline=(100,120,135),width=5)
            image.save(source)
            regular=[('N'+str(i+1),col*400+200,row*400+200) for i,(row,col) in enumerate((r,c) for r in range(4) for c in range(5))]
            for name,crop,pins in [('overview',None,regular),('detail',dict(x=0,y=0,width=800,height=800),[p for p in regular if p[1]<800 and p[2]<800]),
                    ('dense',dict(x=0,y=0,width=800,height=800),[('N'+str(i+1),400+i%3,400+i%3) for i in range(100)])]:
                target=output/(name+'.png')
                if target.exists():raise ValueError('Visual output already exists')
                metrics=WorkerMetrics()
                result=await render_annotated(source,crop,pins,len(pins),metrics=metrics)
                if result.geometry.mime_type!='image/png':raise ValueError('Expected lossless synthetic fixture')
                target.write_bytes(result.data)
                results.append(dict(case=name,width=result.geometry.width,height=result.geometry.height,bytes=len(result.data),
                    notes=result.notes.model_dump(),metrics=asdict(metrics)))
    return results


if __name__=='__main__':
    import json
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    print(json.dumps(asyncio.run(audit(parser.parse_args().output)),separators=(',',':')))
