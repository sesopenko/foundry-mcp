"""Bounded baseline JPEG container checks; pixel decoding stays in the worker.

Only the encoder's single interleaved 8-bit RGB scan with 4:4:4 sampling is
admitted. APP0 may hold a fixed 96-DPI JFIF header; EXIF/ICC/XMP/comments,
thumbnails, progressive/multiscan images and trailing bytes are rejected.
Marker/segment layout: ITU-T T.81 Annex B; JFIF 1.02 section 4.
"""


def inspect_jpeg(data):
    if data[:2]!=b'\xff\xd8':raise ValueError
    offset=2
    dimensions=None
    quantization=set()
    huffman=set()
    frame_tables=[]
    jfif=False
    while offset<len(data):
        if data[offset:offset+1]!=b'\xff':raise ValueError
        offset+=1
        marker=data[offset]
        offset+=1
        size=int.from_bytes(data[offset:offset+2],'big')
        end=offset+size
        if size<2 or end>len(data):raise ValueError
        payload=data[offset+2:end]
        offset=end
        if marker==0xe0:
            if jfif or dimensions is not None or payload not in (
                    b'JFIF\0\x01\x01\x01\x00\x60\x00\x60\0\0',
                    b'JFIF\0\x01\x02\x01\x00\x60\x00\x60\0\0'):
                raise ValueError
            jfif=True
        elif marker==0xdb:
            cursor=0
            while cursor<len(payload):
                table=payload[cursor]
                if table>3 or cursor+65>len(payload) or not all(payload[cursor+1:cursor+65]):raise ValueError
                quantization.add(table)
                cursor+=65
            if cursor==0:raise ValueError
        elif marker==0xc0:
            if dimensions is not None or len(payload)!=15 or payload[0]!=8 or payload[5]!=3:raise ValueError
            height,width=int.from_bytes(payload[1:3],'big'),int.from_bytes(payload[3:5],'big')
            if [payload[i] for i in (6,9,12)]!=[1,2,3]:raise ValueError
            if any(payload[i]!=0x11 for i in (7,10,13)):raise ValueError
            frame_tables=[payload[i] for i in (8,11,14)]
            dimensions=width,height
        elif marker==0xc4:
            cursor=0
            while cursor<len(payload):
                if cursor+17>len(payload):raise ValueError
                table=payload[cursor]
                count=sum(payload[cursor+1:cursor+17])
                if table not in (0,1,2,3,16,17,18,19) or not 1<=count<=256 or cursor+17+count>len(payload):raise ValueError
                huffman.add(table)
                cursor+=17+count
            if cursor==0:raise ValueError
        elif marker==0xda:
            if (dimensions is None or not set(frame_tables)<=quantization or len(payload)!=10
                    or payload[0]!=3 or [payload[i] for i in (1,3,5)]!=[1,2,3]
                    or payload[7:]!=b'\0\x3f\0'):
                raise ValueError
            for selector in (payload[2],payload[4],payload[6]):
                if selector>>4 not in huffman or (16+(selector&15)) not in huffman:raise ValueError
            # Single entropy scan: only byte stuffing is allowed before EOI.
            start=offset
            while offset<len(data):
                found=data.find(b'\xff',offset)
                if found<0 or found+1>=len(data):raise ValueError
                following=data[found+1]
                if following==0:
                    offset=found+2
                    continue
                if following==0xd9 and found>start and found+2==len(data):
                    return 'image/jpeg',*dimensions
                raise ValueError
            raise ValueError
        else:
            raise ValueError
    raise ValueError
