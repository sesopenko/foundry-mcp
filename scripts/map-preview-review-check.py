#!/usr/bin/env python3
"""Bounded measured glyph coverage for the two retained native review derivatives."""
import asyncio
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from foundry_mcp_server.map_note_glyph_probe import probe_glyphs
from foundry_mcp_server.image_preview_live_support import require


async def measure(keys,width,height):
    atlas=await probe_glyphs(keys)
    area=sum(w*h for w,h in atlas.sizes)
    require(area*20<=width*height)
    return dict(keys=len(keys),label_box_pixels=area,coverage_percent=round(100*area/(width*height),6),
        max_ink_height=max(h for _,h in atlas.sizes),sizes=sorted(set(atlas.sizes)))


async def main():
    root=Path(__file__).resolve().parents[1]/'.local/image-preview-map-review'
    rows=[]
    # Native report/visual review established these exact rendered aliases.
    for name,keys in [('overview',[f'N{i}' for i in range(1,26)]),('detail',['N1','N10'])]:
        paths=[p for p in (root/(name+'.png'),root/(name+'.webp')) if p.is_file()]
        require(len(paths)==1)
        with Image.open(paths[0]) as decoded:width,height=decoded.size
        rows.append(dict(case=name,width=width,height=height,**await measure(keys,width,height)))
    return dict(passed=True,cases=rows)


if __name__=='__main__':
    try:report=asyncio.run(main())
    except Exception as error:report=dict(passed=False,error_type=type(error).__name__)
    print(json.dumps(report,sort_keys=True));raise SystemExit(0 if report['passed'] else 1)
