#!/usr/bin/env python3
"""Resolve CI identity from its ref, or verify the exact identity in a module ZIP."""
import argparse
import json
import os
from pathlib import Path
import sys
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from foundry_mcp_server.build_info import make_build_info


def resolve(root, ref_type, ref_name, revision):
    version = tomllib.loads((root / 'pyproject.toml').read_text())['project']['version']
    manifest = json.loads((root / 'foundry-module/module.json').read_text())
    if manifest['version'] != version:
        raise ValueError('Project and module versions must agree')
    return make_build_info(version, ref_name if ref_type == 'tag' else None, revision)


def verify_archive(archive, expected):
    with zipfile.ZipFile(archive) as package:
        script = package.read('scripts/buildInfo.js').decode()
        prefix, suffix = 'export const BUILD_INFO = Object.freeze(', ');\n'
        if not script.startswith(prefix) or not script.endswith(suffix):
            raise ValueError('Missing generated module build identity')
        actual = json.loads(script[len(prefix):-len(suffix)])
        manifest = json.loads(package.read('module.json'))
        if actual != expected or manifest['version'] != expected['version']:
            raise ValueError('Module artifact identity does not match this workflow tag/commit')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref-type', default=os.getenv('GITHUB_REF_TYPE', 'branch'))
    parser.add_argument('--ref-name', default=os.getenv('GITHUB_REF_NAME', ''))
    parser.add_argument('--revision', default=os.getenv('GITHUB_SHA', ''))
    parser.add_argument('--github-output', type=Path)
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    expected = resolve(ROOT, args.ref_type, args.ref_name, args.revision)
    if args.archive:
        verify_archive(args.archive, expected)
    if args.github_output:
        with args.github_output.open('a') as output:
            for key, value in expected.items():
                print(key + '=' + (value or ''), file=output)
    print(json.dumps(expected, sort_keys=True))


if __name__ == '__main__':
    main()
