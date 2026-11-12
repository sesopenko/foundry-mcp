"""Pure deterministic label placement; no native renderer or Foundry dependency."""
from dataclasses import dataclass
import math

from .image_preview_failure import PreviewFailure
from .image_preview_geometry import output_dimensions
from .map_note_glyphs import validate_keys,MAX_GLYPH_WIDTH,MAX_INK_HEIGHT

GAP=4
PIN_RADIUS=2
DIRECTIONS=('NE','NW','SE','SW','E','W','N','S')


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    width: int
    height: int

    def overlaps(self,other):
        return self.x<other.x+other.width and other.x<self.x+self.width and self.y<other.y+other.height and other.y<self.y+self.height

    def inside(self,width,height):
        return self.x>=0 and self.y>=0 and self.x+self.width<=width and self.y+self.height<=height


@dataclass(frozen=True)
class Placement:
    key: str
    pin: tuple[int,int]
    label: Box
    footprint: Box
    leader_end: tuple[int,int]
    direction: str


@dataclass(frozen=True)
class NoteLayout:
    placements: tuple[Placement,...]
    total_in_region: int
    omission_reasons: tuple[tuple[str,int],...]

    def metadata(self):
        count=len(self.placements)
        return dict(total_in_region=self.total_in_region,rendered_count=count,
            omitted_count=self.total_in_region-count,complete=count==self.total_in_region,
            keys=[p.key for p in self.placements],omission_reasons=dict(self.omission_reasons))


def validate_pins(pins,total,region):
    """No private identities or out-of-crop positions enter native annotation."""
    if (not isinstance(pins,(list,tuple)) or len(pins)>100 or type(total) is not int
            or not len(pins)<=total<=2**53-1):raise PreviewFailure('InvalidOperation')
    if not pins:
        if total:raise PreviewFailure('InvalidOperation')
        return ()
    if any(not isinstance(p,(list,tuple)) or len(p)!=3 for p in pins):raise PreviewFailure('InvalidOperation')
    validate_keys([p[0] for p in pins])
    for key,x,y in pins:
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in (x,y)):
            raise PreviewFailure('InvalidOperation')
        if not region['x']<=x<region['x']+region['width'] or not region['y']<=y<region['y']+region['height']:
            raise PreviewFailure('InvalidOperation')
    return tuple(sorted((tuple(pin) for pin in pins),key=lambda p:int(p[0][1:])))


def candidates(px,py,w,h):
    """Outlined box placements and their complete conservative mark footprint."""
    east=px+PIN_RADIUS+1+GAP;west=px-PIN_RADIUS-GAP-w
    north=py-PIN_RADIUS-GAP-h;south=py+PIN_RADIUS+1+GAP
    positions=((east,north),(west,north),(east,south),(west,south),
        (east,py-h//2),(west,py-h//2),(px-w//2,north),(px-w//2,south))
    for direction,(x,y) in zip(DIRECTIONS,positions):
        left=min(x,px-PIN_RADIUS);top=min(y,py-PIN_RADIUS)
        right=max(x+w,px+PIN_RADIUS+1);bottom=max(y+h,py+PIN_RADIUS+1)
        end=(max(x,min(px,x+w-1)),max(y,min(py,y+h-1)))
        yield direction,Box(x,y,w,h),Box(left,top,right-left,bottom-top),end


def layout_notes(pins,total,region,width,height,glyph_sizes):
    """At most100 fixed-size keys, whole footprints disjoint, label area<=5%."""
    if (type(width) is not int or type(height) is not int or output_dimensions(width,height)!=(width,height)
            or width>region['width'] or height>region['height']):raise PreviewFailure('InvalidOperation')
    pins=validate_pins(pins,total,region)
    if set(glyph_sizes)!={p[0] for p in pins}:raise PreviewFailure('InvalidOperation')
    placed=[];reasons={};area=0
    if total>len(pins):reasons['limit']=total-len(pins)
    for key,sx,sy in pins:
        w,h=glyph_sizes[key]
        if type(w) is not int or type(h) is not int or not 1<=w<=MAX_GLYPH_WIDTH or not 1<=h<=MAX_INK_HEIGHT:
            raise PreviewFailure('InvalidOperation')
        px=math.floor((sx-region['x'])*width/region['width']);py=math.floor((sy-region['y'])*height/region['height'])
        if w>width or h>height:reason='tiny_image'
        elif (area+w*h)*20>width*height:reason='density'
        else:
            reason='edge';bounded=False
            for direction,label,footprint,end in candidates(px,py,w,h):
                if not footprint.inside(width,height):continue
                bounded=True
                if any(footprint.overlaps(p.footprint) for p in placed):continue
                placed.append(Placement(key,(px,py),label,footprint,end,direction));area+=w*h
                break
            else:
                reason='collision' if bounded else 'edge'
                reasons[reason]=reasons.get(reason,0)+1
                continue
            continue
        reasons[reason]=reasons.get(reason,0)+1
    return NoteLayout(tuple(placed),total,tuple(reasons.items()))
