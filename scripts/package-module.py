#!/usr/bin/env python3
"""Build validated versioned module assets; never copy the repository wholesale."""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from foundry_mcp_server.build_info import make_build_info

PUBLIC = 'https://github.com/sesopenko/foundry-mcp'
RUNTIME_SCRIPTS = ('main.js', 'foundryBridge.js', 'connectionConfig.js', 'exploration.js', 'journals.js', 'actorReadUtils.js', 'actorDocuments.js', 'actors.js', 'actorPhysical.js', 'actorWeapon.js', 'actorAmmo.js', 'actorArmor.js', 'actorShield.js', 'actorWeaponRelationships.js', 'actorAction.js', 'actorMelee.js', 'actorLore.js', 'actorNpc.js', 'actorEffect.js', 'actorCondition.js', 'actorConditionRelationships.js', 'actorEffectRelationships.js', 'actorWorld.js', 'actorScenes.js', 'actorPacks.js', 'buildInfo.js', 'versionStatus.js', 'pdfChannel.js', 'pdfUpload.js', 'pdfManager.js')


def manifest(root=ROOT, tag=None):
    module = root / 'foundry-module'
    if module.is_symlink() or (module / 'scripts').is_symlink():
        raise ValueError('Module directories must not be symlinks')
    data = json.loads((module / 'module.json').read_text())
    version = tomllib.loads((root / 'pyproject.toml').read_text())['project']['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Release version must be X.Y.Z')
    if data.get('version') != version or (tag is not None and tag != 'v' + version):
        raise ValueError('Release tag, Python, and module versions must agree')
    for key in ('id', 'title', 'description', 'authors', 'compatibility', 'esmodules', 'url', 'manifest', 'download'):
        if not data.get(key):
            raise ValueError('Missing manifest metadata: ' + key)
    if data['id'] != 'foundry-mcp':
        raise ValueError('Module id must match installation directory foundry-mcp')
    if data['url'] != PUBLIC or data['manifest'] != PUBLIC + '/releases/latest/download/module.json':
        raise ValueError('Incorrect repository or stable manifest URL')
    if data['download'] != PUBLIC + f'/releases/download/v{version}/foundry-mcp.zip':
        raise ValueError('Download must be pinned to matching release')
    scripts = [module / 'scripts' / name for name in RUNTIME_SCRIPTS]
    allowed = {'module.json', 'LICENSE.txt', *(p.relative_to(module).as_posix() for p in scripts)}
    if not (module / 'LICENSE.txt').is_file() or (module / 'LICENSE.txt').is_symlink():
        raise ValueError('Module license must be a regular file')
    for path in data['esmodules']:
        if path not in allowed or not (module / path).is_file():
            raise ValueError('Missing or unsupported module entrypoint')
    # Every local ES import must be included. Remote imports are not allowed.
    for script in scripts:
        if script.is_symlink():
            raise ValueError('Module assets must not be symlinks')
        if not script.is_file():
            raise ValueError('Missing runtime script')
        for target in re.findall(r'(?:from\s+|import\s*)[\x27\"]([^\x27\"]+)[\x27\"]', script.read_text()):
            if not target.startswith('./') or 'scripts/' + target[2:] not in allowed:
                raise ValueError('Unpackaged or external module import')
    if (module / 'module.json').is_symlink():
        raise ValueError('Manifest must not be a symlink')
    return data, allowed


def package(output, root=ROOT, tag=None, revision=None):
    data, allowed = manifest(root, tag)
    output.mkdir(parents=True, exist_ok=True)
    info = make_build_info(data['version'], tag, revision)
    build_script = ('export const BUILD_INFO = Object.freeze(' + json.dumps(info, sort_keys=True) + ');\n').encode()
    encoded = (json.dumps(data, indent=2) + '\n').encode()
    (output / 'module.json').write_bytes(encoded)
    with zipfile.ZipFile(output / 'foundry-mcp.zip', 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(allowed):
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe archive path')
            info = zipfile.ZipInfo(name, date_time=(2025, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            content = encoded if name == 'module.json' else build_script if name == 'scripts/buildInfo.js' else (root / 'foundry-module' / name).read_bytes()
            archive.writestr(info, content)
    return data['version']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', help='Release tag; must equal v<version>')
    parser.add_argument('--revision', help='Build commit SHA')
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/module')
    args = parser.parse_args()
    print('Packaged module ' + package(args.output, tag=args.tag, revision=args.revision))
