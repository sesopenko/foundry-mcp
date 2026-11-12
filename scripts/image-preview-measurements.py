"""Bounded private10000x10000/10000x5000 MCP measurement; no game instance."""
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from image_preview_measurement_harness import measure_maps

if __name__=='__main__':
    report=asyncio.run(measure_maps())
    print(json.dumps(report,sort_keys=True))
    raise SystemExit(0 if report['passed'] else 1)
