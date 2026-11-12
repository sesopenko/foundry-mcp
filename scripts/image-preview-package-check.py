#!/usr/bin/env python3
"""Bounded local Docker check; owns only one fresh marked container/volume."""
import argparse
import json
import subprocess
import time
import uuid


def command(*args):
    result=subprocess.run(['docker',*args],capture_output=True,text=True,timeout=150)
    if result.returncode:raise RuntimeError('PackageDockerCommandFailed')
    if len(result.stdout)>65536:raise RuntimeError('PackageDockerOutputExceeded')
    return result.stdout.strip()


def verify(image,*,run=command,sleep=time.sleep):
    marker='foundry-preview-check-'+uuid.uuid4().hex
    container=marker;volume=marker+'-data';created=False
    report={};cleanup=[]
    try:
        identity=run('image','inspect','--format','{{.Id}}',image)
        run('volume','create','--label','foundry-mcp.preview-check=true',volume);created=True
        def start():
            run('run','-d','--name',container,'--label','foundry-mcp.preview-check=true',
                '--mount','type=volume,source='+volume+',target=/data/image-previews',
                '-e','FOUNDRY_MCP_AUTH_MODE=basic','-e','FOUNDRY_MCP_BASIC_USERNAME=fixture',
                '-e','FOUNDRY_MCP_BASIC_PASSWORD=synthetic-package-password',
                '-e','FOUNDRY_MCP_BRIDGE_TOKEN=synthetic-package-bridge',
                '-e','FOUNDRY_MCP_IMAGE_PREVIEW_ORIGIN=https://preview.example.com',image)
            for _ in range(30):
                status=run('inspect','--format','{{.State.Health.Status}}',container)
                if status=='healthy':return
                if status=='unhealthy':raise RuntimeError('PackageHealthFailed')
                sleep(2)
            raise RuntimeError('PackageHealthDeadline')
        def probe(action):
            value=json.loads(run('exec',container,'python','-m','foundry_mcp_server.image_preview_package_probe',action))
            if value.get('passed') is not True or value.get('uid')!=10001:raise RuntimeError('PackageProbeFailed')
            return value
        start();seeded=probe('seed');before=probe('fetch')
        run('rm','-f',container)
        start();after=probe('fetch')
        if seeded['sha256']!=before['sha256'] or before!=after:raise RuntimeError('PackagePersistenceMismatch')
        report=dict(passed=True,image_id=identity,seed=seeded,recreated_container=True,delivery=after)
    except Exception as error:report=dict(passed=False,error_type=type(error).__name__)
    finally:
        if created:
            for args in [('rm','-f',container),('volume','rm',volume)]:
                try:run(*args)
                except Exception:cleanup.append('container' if args[0]=='rm' else 'volume')
    report['cleanup_complete']=not cleanup
    if cleanup:report.update(passed=False,cleanup_pending=cleanup,cleanup_marker=marker)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',default='foundry-mcp-image-preview-check:local')
    args=parser.parse_args()
    report=verify(args.image)
    print(json.dumps(report,sort_keys=True));return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
