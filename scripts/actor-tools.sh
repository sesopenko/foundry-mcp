#!/usr/bin/env bash
# Fixed commands for dependency tracking and offline Actor/Item verification.
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$repo_root"
if (($# > 1)); then
    echo 'actor-tools: expected one fixed command, without extra arguments.' >&2
    exit 2
fi
case "${1:-status}" in
  status|check) exec .venv/bin/python scripts/actor-story-map.py "${1:-status}" ;;
  focused)
    .venv/bin/python -m unittest discover -s tests -p 'test_actor*.py' -v
    shopt -s nullglob
    actor_tests=(tests/js/actor*.test.js)
    if ((${#actor_tests[@]})); then node --test "${actor_tests[@]}"; fi
    ;;
  full) exec ./scripts/test.sh ;;
  browser) exec .venv/bin/python scripts/actor-live-check.py --browser ;;
  live) exec .venv/bin/python scripts/actor-live-check.py ;;
  *) echo 'Usage: ./scripts/actor-tools.sh [status|check|focused|full|live|browser]' >&2; exit 2 ;;
esac
