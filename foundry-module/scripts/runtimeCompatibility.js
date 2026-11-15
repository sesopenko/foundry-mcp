/** PF2e-specific version admission for the existing Actor/Item and inline
 * contracts. Foundry >=14.369,<15; PF2e >=8.6.1,<9. These ranges express
 * compatibility policy, not live verification of every accepted release.
 * Source/derived assumptions remain with each reader. Schema audit and tested
 * versions: docs/runtime-compatibility.md. No Foundry runtime APIs are called.
 */
export const COMPATIBILITY = 'Foundry >=14.369,<15 and PF2e >=8.6.1,<9';

/** Compare canonical numeric release components without lexical ordering. */
function inRange(value, minimum) {
  if (typeof value !== 'string' || value.length > 64 || /[\r\n]/.test(value) || !/^(0|[1-9]\d*)(\.(0|[1-9]\d*)){1,2}$/.test(value)) return false;
  const parts = value.split('.').map(Number);
  if (parts.some(part => !Number.isSafeInteger(part))) return false;
  while (parts.length < 3) parts.push(0);
  return parts[0] === minimum[0] && (parts[1] > minimum[1] || parts[1] === minimum[1] && parts[2] >= minimum[2]);
}

/** PF2e-specific admission only; preserve actual version strings in responses. */
export function supportedRuntime(value) {
  return value?.system_id === 'pf2e' && inRange(value.core_version, [14, 369, 0]) && inRange(value.system_version, [8, 6, 1]);
}
