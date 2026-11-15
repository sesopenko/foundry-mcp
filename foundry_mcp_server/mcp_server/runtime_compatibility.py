"""PF2e-specific admission policy for Actor/Item and inline schema contracts.

Foundry >=14.369,<15 and PF2e >=8.6.1,<9. Admission is separate from tested
version evidence and from source/derived reader semantics. See
docs/runtime-compatibility.md for upstream schema audit and runtime evidence.
"""
import re
from collections.abc import Mapping

COMPATIBILITY = 'Foundry >=14.369,<15 and PF2e >=8.6.1,<9'


def _in_range(value, minimum):
    """Compare bounded canonical numeric releases, matching the JS boundary."""
    if type(value) is not str or len(value) > 64 or not re.fullmatch(r'(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*)){1,2}', value):
        return False
    parts = tuple(int(part) for part in value.split('.'))
    if any(part > 9007199254740991 for part in parts):
        return False
    parts += (0,) * (3 - len(parts))
    return parts[0] == minimum[0] and parts >= minimum


def supported_runtime(value):
    """PF2e-specific range check; does not validate response envelope shape."""
    return (isinstance(value, Mapping) and value.get('system_id') == 'pf2e'
            and _in_range(value.get('core_version'), (14, 369, 0))
            and _in_range(value.get('system_version'), (8, 6, 1)))
