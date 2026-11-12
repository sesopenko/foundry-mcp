"""Exercise repeated evaluation of the production geometry pipeline in a child."""
import hashlib
import json
import sys

from foundry_mcp_server.image_preview_geometry import prepare_region
from foundry_mcp_server.image_preview_worker import open_original

try:
    request=json.loads(sys.stdin.buffer.read(8192))
    image,metadata=open_original(request['source'])
    region=prepare_region(image,metadata)
    first=region.resample(100,50).pngsave_buffer(strip=True)
    second=region.resample(60,30).pngsave_buffer(strip=True)
    fresh,metadata=open_original(request['source'])
    expected=prepare_region(fresh,metadata).resample(60,30).pngsave_buffer(strip=True)
    print(json.dumps({'first':hashlib.sha256(first).hexdigest(),
        'repeated_matches_fresh':second==expected}))
except Exception as error:
    # Fixture diagnostics classify known native behavior without paths/errors.
    print(json.dumps({'error_code':type(error).__name__,
        'sequential_read':'out of order read' in str(error).lower()}))
