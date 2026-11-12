"""Pure display-oriented Scene-to-image geometry, independent of Foundry state."""
from dataclasses import dataclass
import math

from fastmcp.exceptions import ToolError

from . import image_preview_limits as limits
from .mcp_server.image_preview_models import Crop


def unsupported_mapping():
    return ToolError('UnsupportedMapMapping: annotation requires a verified default background mapping on the supported Foundry build. Choose its background/level or request an ordinary preview without map_notes.')


def finite(value):
    return type(value) in (int,float) and math.isfinite(value)


@dataclass(frozen=True)
class SceneImageMapping:
    """Public Scene rectangle already contains padding/shift; source is oriented.

    Do not subtract shift twice or interpret Scene dimensions as image pixels.
    Background/default-placement admission belongs to the browser context reader.
    """
    scene_x: float
    scene_y: float
    scene_width: float
    scene_height: float
    source_width: int
    source_height: int

    def __post_init__(self):
        if (not all(finite(v) for v in (self.scene_x,self.scene_y,self.scene_width,self.scene_height))
                or self.scene_width<=0 or self.scene_height<=0
                or type(self.source_width) is not int or type(self.source_height) is not int
                or not 1<=self.source_width<=limits.SOURCE_MAX_EDGE or not 1<=self.source_height<=limits.SOURCE_MAX_EDGE
                or self.source_width*self.source_height>limits.SOURCE_MAX_PIXELS):raise unsupported_mapping()

    def source_point(self,x,y):
        if not finite(x) or not finite(y):raise unsupported_mapping()
        point=((x-self.scene_x)*self.source_width/self.scene_width,
            (y-self.scene_y)*self.source_height/self.scene_height)
        if not all(finite(v) for v in point):raise unsupported_mapping()
        return point

    def contains(self,x,y,region:Crop):
        region.check_containment(self.source_width,self.source_height)
        u,v=self.source_point(x,y)
        return region.x<=u<region.x+region.width and region.y<=v<region.y+region.height

    def output_point(self,x,y,region:Crop,width:int,height:int):
        """Map one in-region pin to delivered pixels, preserving its source key."""
        region.check_containment(self.source_width,self.source_height)
        if (type(width) is not int or type(height) is not int or width<1 or height<1
                or width>region.width or height>region.height or width>limits.OUTPUT_MAX_EDGE
                or height>limits.OUTPUT_MAX_EDGE or width*height>limits.OUTPUT_MAX_PIXELS):raise unsupported_mapping()
        u,v=self.source_point(x,y)
        if not self.contains(x,y,region):raise unsupported_mapping()
        return((u-region.x)*width/region.width,(v-region.y)*height/region.height)
