#!/usr/bin/env python3
"""Prepare synchronized release versions; never commit, tag, push, or publish."""
import argparse
import json
from pathlib import Path
import re
import tomllib


def plan_bump(root, version):
    root = Path(root)
    current = tomllib.loads((root / 'pyproject.toml').read_text())['project']['version']
    pattern = r'(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)'
    if not re.fullmatch(pattern, current) or not re.fullmatch(pattern, version):
        raise ValueError('Versions must be X.Y.Z without a v prefix or prerelease suffix')
    if tuple(map(int, version.split('.'))) <= tuple(map(int, current.split('.'))):
        raise ValueError('Release version must be greater than the current project version')
    changes = {}

    def exact(name, old, new):
        text = (root / name).read_text()
        if text.count(old) != 1:
            raise ValueError(f'{name}: expected exactly one synchronized version entry; inspect before editing')
        changes[name] = text.replace(old, new, 1)

    exact('pyproject.toml', f'version = "{current}"', f'version = "{version}"')
    exact('uv.lock', f'name = "foundry-mcp"\nversion = "{current}"',
          f'name = "foundry-mcp"\nversion = "{version}"')
    exact('foundry_mcp_server/build-info.json', f'"version":"{current}"', f'"version":"{version}"')
    exact('foundry-module/scripts/buildInfo.js', f'"version":"{current}"', f'"version":"{version}"')
    exact('Dockerfile', f'ARG VERSION={current}\n', f'ARG VERSION={version}\n')
    exact('deploy/compose.local.yaml', f'VERSION: {current}\n', f'VERSION: {version}\n')

    name = 'foundry-module/module.json'
    data = json.loads((root / name).read_text())
    public = 'https://github.com/sesopenko/foundry-mcp'
    if (data.get('version') != current
        or data.get('manifest') != public + '/releases/latest/download/module.json'
        or data.get('download') != public + f'/releases/download/v{current}/foundry-mcp.zip'):
        raise ValueError('Module version or release URLs are inconsistent; inspect before editing')
    data['version'] = version
    data['download'] = public + f'/releases/download/v{version}/foundry-mcp.zip'
    changes[name] = json.dumps(data, indent=2, ensure_ascii=False) + '\n'

    name = 'tests/test_packaging.py'
    text = (root / name).read_text()
    for old in (f"tag='v{current}'", f"self.assertEqual(version, '{current}')"):
        if text.count(old) != 1:
            raise ValueError('Packaging test version expectations changed; inspect before editing')
    changes[name] = text.replace(f"tag='v{current}'", f"tag='v{version}'").replace(
        f"self.assertEqual(version, '{current}')", f"self.assertEqual(version, '{version}')")

    # These are current-use examples, not historical verification records.
    for name in ('README.md', 'deploy/.env.example', 'docs/operations.md',
                 'docs/docker-repository-overview.md'):
        text = (root / name).read_text()
        updated = re.sub(r'(?<![\d.])' + re.escape(current) + r'(?![\d.])', version, text)
        if updated != text:
            changes[name] = updated
    return current, changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument('--version', required=True, help='LLM-selected X.Y.Z release version, without v')
    parser.add_argument('--dry-run', action='store_true', help='Print the proposed files without editing')
    args = parser.parse_args()
    version = args.version
    try:
        current, changes = plan_bump(args.root, version)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f'{current} -> {version}')
    for name, content in changes.items():
        print(name)
        if not args.dry_run:
            (args.root / name).write_text(content)


if __name__ == '__main__':
    main()
