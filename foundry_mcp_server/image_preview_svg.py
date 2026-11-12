"""Bounded static SVG subset; only reconstructed admitted XML reaches librsvg.

No image/text/font/style-sheet/foreign elements or external resources. Inline
presentation styles and same-document fragment references are supported.
https://www.libvips.org/API/current/ctor.Image.svgload.html (8.18, dpi=96).
"""
from decimal import Decimal,InvalidOperation,ROUND_CEILING
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .image_preview_failure import PreviewFailure

SVG = 'http://www.w3.org/2000/svg'
XLINK = 'http://www.w3.org/1999/xlink'
MAX_XML_BYTES = 10_000_000
MAX_ELEMENTS = 10_000
MAX_DEPTH = 64
MAX_EXPANSION = 100_000
ELEMENTS = frozenset(('svg','g','defs','path','rect','circle','ellipse','line','polyline','polygon',
    'linearGradient','radialGradient','stop','clipPath','mask','use','symbol','title','desc'))
PRESENTATION = frozenset(('fill','stroke','stroke-width','stroke-linecap','stroke-linejoin',
    'stroke-miterlimit','stroke-dasharray','stroke-dashoffset','fill-rule','clip-rule',
    'opacity','fill-opacity','stroke-opacity','stop-color','stop-opacity','color',
    'clip-path','mask','display','visibility','vector-effect','paint-order'))
ATTRIBUTES = PRESENTATION | frozenset(('id','version','x','y','x1','y1','x2','y2','width','height',
    'cx','cy','r','rx','ry','fx','fy','d','points','transform','viewBox','preserveAspectRatio',
    'gradientUnits','gradientTransform','spreadMethod','offset','clipPathUnits',
    'maskUnits','maskContentUnits','href','style'))
IDENTIFIER = re.compile(r'[A-Za-z_][A-Za-z0-9_.:-]{0,255}\Z')
NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
LENGTH = re.compile(rf'({NUMBER})(px|in|cm|mm|pt|pc|q)?\Z')
LOCAL_URL = re.compile(r'''url\(\s*(['"]?)(#[A-Za-z_][A-Za-z0-9_.:-]{0,255})\1\s*\)\Z''',re.I)
UNITS = {'':Decimal(1),'px':Decimal(1),'in':Decimal(96),'cm':Decimal(96)/Decimal('2.54'),
    'mm':Decimal(96)/Decimal('25.4'),'pt':Decimal(4)/Decimal(3),'pc':Decimal(16),'q':Decimal(96)/Decimal('101.6')}


def reject():
    raise PreviewFailure('UnsupportedImage')


class BoundedTree(ET.TreeBuilder):
    """Parser callbacks reject declarations and bound structure during parsing."""
    def __init__(self):
        super().__init__()
        self.depth = self.count = 0

    def start(self,tag,attrs):
        self.depth += 1
        self.count += 1
        if self.depth>MAX_DEPTH or self.count>MAX_ELEMENTS or len(attrs)>64:reject()
        return super().start(tag,attrs)

    def end(self,tag):
        self.depth -= 1
        return super().end(tag)

    def doctype(self,*args):reject()
    def pi(self,*args):reject()


def scalar(value):
    if len(value)>64:reject()
    number = Decimal(value)
    if not number.is_finite() or abs(number)>Decimal('1e12') or (number and abs(number)<Decimal('1e-12')):reject()
    return number


def length(value):
    if value is None:return None
    if value.strip().endswith('%'):
        if not re.fullmatch(rf'{NUMBER}%',value.strip()) or scalar(value.strip()[:-1])<=0:reject()
        return None
    match = LENGTH.fullmatch(value.strip())
    if not match:reject()
    result = scalar(match[1])*UNITS[match[2] or '']
    if result<=0:reject()
    return result


def viewport(root):
    box = root.get('viewBox')
    if box is not None:
        parts = re.split(r'[\s,]+',box.strip())
        if len(parts)!=4 or any(not re.fullmatch(NUMBER,p) for p in parts):reject()
        box = tuple(scalar(p) for p in parts)
        if box[2]<=0 or box[3]<=0:reject()
    width,height = length(root.get('width')),length(root.get('height'))
    if width is None and height is None:
        if box is None:reject()
        width,height = box[2:]
    elif width is None:
        if box is None:reject()
        width = height*box[2]/box[3]
    elif height is None:
        if box is None:reject()
        height = width*box[3]/box[2]
    width,height = (int(n.to_integral_value(rounding=ROUND_CEILING)) for n in (width,height))
    if width>2**53-1 or height>2**53-1:
        raise PreviewFailure('ImageTooLarge')
    from .image_preview_worker import dimensions
    dimensions(width,height)
    return width,height


def value_references(value):
    """Presentation values cannot smuggle URLs through CSS escapes/functions."""
    if '\\' in value or '/*' in value or '@' in value:reject()
    if re.search(r'url\s*\(',value,re.I):
        match = LOCAL_URL.fullmatch(value.strip())
        if not match:reject()
        return [match[2][1:]]
    # Only ordinary colours, numeric values and SVG presentation keywords.
    # No strings, arbitrary functions, CSS variables or URL punctuation.
    if not re.fullmatch(r'[A-Za-z0-9#.,%+\-\s()]*',value):reject()
    if '(' in value and not re.fullmatch(r'rgba?\([0-9.,%+\-\s]+\)',value,re.I):reject()
    return []


def admit_svg(data):
    """Return reconstructed XML and integral96-DPI viewport, or fixed failure.

    Byte/node/depth/attribute/reference-expansion limits bound parser work before
    native loading; parent resource supervision also covers parsing and rendering.
    """
    if not data or len(data)>MAX_XML_BYTES:reject()
    try:
        text = data.decode('utf-8-sig')
        if '\x00' in text:reject()
        root = ET.fromstring(text,parser=ET.XMLParser(target=BoundedTree()))
        if root.tag not in ('svg',f'{{{SVG}}}svg'):reject()
        ids,refs = {},{}
        for element in root.iter():
            tag = element.tag
            if tag.startswith(f'{{{SVG}}}'):tag = tag[len(SVG)+2:]
            if tag not in ELEMENTS:reject()
            element.tag = f'{{{SVG}}}{tag}'
            if (element.text or '').strip() and tag not in ('title','desc'):reject()
            element.text = element.tail = None
            links = []
            for name,value in list(element.attrib.items()):
                if name==f'{{{XLINK}}}href':
                    # Normalize xlink to the same supported local href contract.
                    if 'href' in element.attrib:reject()
                    del element.attrib[name]
                    name = 'href'
                    element.set(name,value)
                if name not in ATTRIBUTES:reject()
                if name=='id':
                    if not IDENTIFIER.fullmatch(value) or value in ids:reject()
                    ids[value] = element
                elif name=='href':
                    if tag not in ('use','linearGradient','radialGradient') or not value.startswith('#') or not IDENTIFIER.fullmatch(value[1:]):reject()
                    links.append(value[1:])
                elif name=='style':
                    for declaration in value.split(';'):
                        if not declaration.strip():continue
                        pair = declaration.split(':',1)
                        if len(pair)!=2 or pair[0].strip() not in PRESENTATION:reject()
                        links.extend(value_references(pair[1].strip()))
                elif name in PRESENTATION:
                    links.extend(value_references(value))
                else:
                    if not re.fullmatch(r'[A-Za-z0-9.,%+\-\s()]*',value):reject()
                    for number in re.findall(NUMBER,value):scalar(number)
            refs[element] = links
        width,height = viewport(root)
        # Include containment edges and local references in an acyclic bounded
        # expansion graph. Memoization prevents exponential validator work.
        active,memo = set(),{}
        def expansion(element,depth=0):
            if element in active or depth>MAX_DEPTH:reject()
            if element in memo:return memo[element]
            active.add(element)
            total = 1
            for child in list(element)+[ids.get(key) for key in refs[element]]:
                if child is None:reject()
                total += expansion(child,depth+1)
                if total>MAX_EXPANSION:reject()
            active.remove(element)
            memo[element] = total
            return total
        expansion(root)
        root.set('width',str(width))
        root.set('height',str(height))
        return ET.tostring(root,encoding='utf-8'),width,height
    except (UnicodeError,ET.ParseError,ValueError,InvalidOperation,OverflowError):
        reject()


def open_svg(path,size):
    """Load only admitted, reconstructed, private XML; no untrusted base URI."""
    if size>MAX_XML_BYTES:reject()
    with path.open('rb') as stream:data = stream.read(MAX_XML_BYTES+1)
    clean,width,height = admit_svg(data)
    target = Path(os.environ['TMPDIR'])/'guarded.svg'
    descriptor = os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(descriptor,'wb') as stream:stream.write(clean)
    from .image_preview_worker import initialise
    native = initialise()
    try:
        # libvips8.18.7 computes total_scale = scale*dpi/72 independently
        # of librsvg's CSS DPI. Keep CSS physical units at96 while cancelling
        # that additional global enlargement; pixel viewport remains exact.
        image = native.Image.svgload(str(target),dpi=96,scale=72/96,access='random',fail_on='warning')
        if (image.width,image.height)!=(width,height):reject()
        return image,dict(width=width,height=height,mime_type='image/svg+xml',size_bytes=size,frame_policy='still')
    except native.Error:
        reject()
