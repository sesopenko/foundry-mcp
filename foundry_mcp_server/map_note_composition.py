"""Worker-only final-size annotation composition and bounded encoding."""
from pathlib import Path

from .image_preview_encode import encode_region
from .image_preview_geometry import prepare_region
from .image_preview_worker import open_original,initialise
from .map_note_glyphs import rasterize_keys
from .map_note_layout import layout_notes,validate_pins


def compose_notes(image,pins,total,region,glyphs):
    """Draw bounded leaders/pins and white outlined keys, never opaque boxes."""
    vips=initialise()
    layout=layout_notes(pins,total,region,image.width,image.height,{key:(g.width,g.height) for key,g in glyphs.items()})
    overlay=vips.Image.black(image.width,image.height,bands=4).copy(interpretation='srgb')
    for p in layout.placements:
        x,y=p.pin;ex,ey=p.leader_end
        overlay=overlay.draw_line([24,24,24,255],x,y,ex,ey)
        overlay=overlay.draw_circle([24,24,24,255],x,y,2,fill=True)
        overlay=overlay.draw_circle([255,255,255,255],x,y,1,fill=True)
        overlay=overlay.composite2(glyphs[p.key].image,'over',x=p.label.x,y=p.label.y,compositing_space='srgb')
    return image.composite2(overlay,'over',compositing_space='srgb').cast('uchar'),layout.metadata()


def render_annotated(path,crop,pins,total,scratch,**encoding):
    """Recompose from unannotated source pixels on every encoding attempt."""
    image,metadata=open_original(path)
    region=prepare_region(image,metadata,crop)
    pins=validate_pins(pins,total,region.bounds)
    glyphs={g.key:g for g in rasterize_keys([p[0] for p in pins])} if pins else {}
    def compose(image):return compose_notes(image,pins,total,region.bounds,glyphs)
    artifact=encode_region(region,Path(scratch),compose=compose,**encoding)
    return dict(source=metadata,region=region.bounds,**artifact)
