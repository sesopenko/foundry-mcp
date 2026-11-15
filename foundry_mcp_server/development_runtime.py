"""Source-checkout-only JavaScript admission for automated verifier packets.

Load the immutable module source once when a verifier imports this module,
separately from its later credential I/O and fixture lifecycle. Production
tools do not import this module or require the browser source on disk.
"""
from pathlib import Path

_SOURCE = (Path(__file__).resolve().parents[1] / 'foundry-module/scripts/runtimeCompatibility.js').read_text()
_SOURCE = _SOURCE.replace('export const ', 'const ').replace('export function ', 'function ')


def development_runtime_check(core_only=False):
    """PF2e-specific synchronous guard; core-only probes retain their scope."""
    system = "system_id:'pf2e',system_version:'8.6.1'" if core_only else 'system_id:game.system.id,system_version:game.system.version'
    return '(() => {' + _SOURCE + '\nreturn supportedRuntime({core_version:game.version,' + system + '});})()'
