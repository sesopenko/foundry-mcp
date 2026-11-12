"""Controlled real subprocess for private preview-supervisor resource tests.

Never selected by production code or MCP input. Only tiny injected test budgets.
"""
import json
import os
from pathlib import Path
import sys
import time

sys.stdin.buffer.read(8193)
mode = sys.argv[1]
scratch = Path(os.environ['TMPDIR'])
if mode == 'rss':
    allocation = bytearray(48*1024*1024)
    time.sleep(10)
elif mode in ('scratch','unlinked'):
    files = []
    for index in range(2):
        path = scratch/str(index)
        stream = path.open('w+b')
        stream.write(b'x'*24576)
        stream.flush()
        files.append(stream)
        if mode == 'unlinked':
            path.unlink()
    time.sleep(10)
elif mode == 'stall':
    time.sleep(10)
elif mode == 'overflow':
    sys.stdout.write('x'*4097)
    sys.stdout.flush()
    time.sleep(10)
elif mode == 'flood':
    sys.stdout.buffer.write(b'x'*(8*1024*1024))
    sys.stdout.flush()
    time.sleep(10)
elif mode == 'exit':
    sys.stderr.write('private-native-error-secret')
    sys.exit(2)
else:
    time.sleep(0.1)
    print(json.dumps({'ok':True}))
