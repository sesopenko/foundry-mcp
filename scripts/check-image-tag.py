#!/usr/bin/env python3
"""Fail closed before replacing a release tag; suppress private image references."""
import os
import argparse
import re
import subprocess
import sys


def image_exists(image):
    result = subprocess.run(['docker', 'buildx', 'imagetools', 'inspect', image],
                            capture_output=True, text=True, timeout=30)
    if result.returncode == 0:
        return True
    if not re.search(r'(?im)(manifest[_ ]unknown|: not found\s*$)', result.stderr):
        raise ValueError('Could not establish that release image tag is absent; check private registry access')
    return False


def check(image):
    if image_exists(image):
        raise ValueError('Release image tag already exists; increment the synchronized version')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-existing', action='store_true', help='Emit a safe push output for immutable commit tags')
    args = parser.parse_args()
    try:
        if args.skip_existing:
            push = not image_exists(os.environ['RELEASE_IMAGE'])
            with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
                print('push=' + str(push).lower(), file=output)
        else:
            check(os.environ['RELEASE_IMAGE'])
    except (ValueError, KeyError, OSError, subprocess.TimeoutExpired) as exc:
        # Subprocess errors may include the private hostname; never print them.
        print(str(exc) if isinstance(exc, ValueError) else 'Release tag check failed', file=sys.stderr)
        raise SystemExit(1)
