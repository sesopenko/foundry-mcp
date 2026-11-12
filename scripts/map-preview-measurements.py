#!/usr/bin/env python3
"""Bounded real10000-square annotated overview/detail verification; aggregates only."""
import asyncio
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from map_workflow_harness import large_annotations

if __name__=='__main__':
    try:report=asyncio.run(large_annotations())
    except Exception as error:report=dict(passed=False,error_type=type(error).__name__)
    print(json.dumps(report,sort_keys=True));raise SystemExit(0 if report['passed'] else 1)
