#!/usr/bin/env python3
"""Validate deployment/document Compose examples with synthetic environment only."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
VALUES=dict(FOUNDRY_MCP_IMAGE='local:verification',FOUNDRY_MCP_LAN_ADDRESS='192.0.2.10',
    FOUNDRY_MCP_BASIC_USERNAME='fixture',FOUNDRY_MCP_BASIC_PASSWORD='synthetic-password',
    FOUNDRY_MCP_BRIDGE_TOKEN='synthetic-browser',FOUNDRY_MCP_PUBLIC_URL='https://mcp.example.com',
    FOUNDRY_MCP_OAUTH_ISSUER='https://fixture.auth0.com/',FOUNDRY_MCP_OAUTH_ALLOWED_SUBJECTS='auth0|fixture',
    FOUNDRY_MCP_OAUTH_ALLOWED_CLIENT_IDS='fixture-client')


def examples(root=ROOT):
    rows=[(name,(root/name).read_text()) for name in ('deploy/compose.yaml','deploy/compose.oauth.yaml')]
    for name in ('README.md','docs/docker-repository-overview.md'):
        for index,body in enumerate(re.findall(r'```yaml\n(.*?)```',(root/name).read_text(),re.S)):
            if body.startswith('services:\n'):rows.append((name+':'+str(index),body))
    return rows


def verify(*,root=ROOT,execute=subprocess.run):
    checked=0
    # Do not interpolate the operator's private deployment environment or .env.
    base={key:os.environ[key] for key in ('PATH','HOME') if key in os.environ}
    try:
        with tempfile.TemporaryDirectory(prefix='preview-compose-') as directory:
            path=Path(directory)/'compose.yaml'
            for name,body in examples(root):
                path.write_text(body)
                for origin in ('','https://previews.example.com'):
                    result=execute(['docker','compose','--env-file','/dev/null','-f',str(path),'config','--format','json'],
                        env={**base,**VALUES,'FOUNDRY_MCP_IMAGE_PREVIEW_ORIGIN':origin},
                        capture_output=True,text=True,timeout=20)
                    if result.returncode or len(result.stdout)>65536:raise ValueError('Invalid compose example')
                    value=json.loads(result.stdout);service=value['services']['foundry-mcp'];environment=service['environment']
                    if environment['FOUNDRY_MCP_IMAGE_PREVIEW_ORIGIN']!=origin:raise ValueError('Wrong preview origin')
                    if environment['FOUNDRY_MCP_IMAGE_PREVIEW_DATA_DIR']!='/data/image-previews':raise ValueError('Wrong private store')
                    if not any(v.get('type')=='volume' and v.get('source')=='image-previews' and v.get('target')=='/data/image-previews' for v in service['volumes']):raise ValueError('Missing persistent preview volume')
                    if environment['FOUNDRY_MCP_AUTH_MODE']=='oauth' and any(key.startswith('FOUNDRY_MCP_BASIC_') for key in environment):raise ValueError('Mixed authentication')
                    checked+=1
        return dict(passed=True,configurations=checked)
    except Exception as error:return dict(passed=False,configurations=checked,error_type=type(error).__name__)


if __name__=='__main__':
    report=verify();print(json.dumps(report,sort_keys=True));raise SystemExit(0 if report['passed'] else 1)
