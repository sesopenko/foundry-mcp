"""Build identity embedded at packaging time, not inferred from runtime Git/env."""
import argparse
import json
from pathlib import Path
import re

PATH = Path(__file__).with_name('build-info.json')
UNKNOWN = dict(version=None, release_tag=None, revision=None, build_kind='unknown')
VERSION = r'(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)'


def validate_build_info(value):
    if not isinstance(value, dict):
        raise ValueError('Build identity must be an object')
    result = {key: value.get(key) for key in UNKNOWN}
    version, tag, revision, kind = (result[key] for key in UNKNOWN)
    if kind == 'unknown' and all(x is None for x in (version, tag, revision)):
        return result
    if not isinstance(version, str) or len(version) > 64 or not re.fullmatch(VERSION, version):
        raise ValueError('Invalid build version')
    if revision is not None and (not isinstance(revision, str) or not re.fullmatch(r'[0-9a-f]{40}', revision)):
        raise ValueError('Invalid build revision')
    if kind == 'release':
        if tag != 'v' + version:
            raise ValueError('Release tag and version must agree')
    elif not isinstance(kind, str) or kind not in {'source', 'unreleased'} or tag is not None:
        raise ValueError('Invalid build kind or release tag')
    return result


def make_build_info(version, release_tag=None, revision=None):
    return validate_build_info(dict(version=version, release_tag=release_tag or None,
        revision=None if revision in (None, '', 'unknown') else revision,
        build_kind='release' if release_tag else 'unreleased'))


def load_build_info(path=PATH):
    try:
        if path.stat().st_size > 4096:
            return dict(UNKNOWN)
        return validate_build_info(json.loads(path.read_text()))
    except (OSError, ValueError, TypeError, RecursionError):
        return dict(UNKNOWN)


SERVER_BUILD = load_build_info()


def compare_builds(server, module):
    if server['build_kind'] != 'release' or module['build_kind'] != 'release':
        return 'unverified'
    return 'match' if server['version'] == module['version'] else 'mismatch'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    parser.add_argument('--release-tag', default='')
    parser.add_argument('--revision', default='')
    args = parser.parse_args()
    info = make_build_info(args.version, args.release_tag, args.revision)
    PATH.write_text(json.dumps(info, sort_keys=True) + '\n')
