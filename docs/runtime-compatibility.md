# Runtime compatibility

PF2e-specific Actor/Item discovery, readers, party tools, journal target
admission, inventory metrics and inline builders accept **Foundry >=14.369,<15**
and **PF2e >=8.6.1,<9**. Any combination within those ranges is admitted.
Later minor/patch versions do not need individual allowlisting. Older releases,
other majors, malformed versions and other systems remain unsupported.

Responses retain actual runtime versions. Inline response schemas now publish
bounded strings with range validation instead of exact literals; clients must
not require the old constants. No requests, pagination defaults or capability
exclusions changed. Nullable current land speed is preserved as null for
characters, NPCs and familiars, without inventing zero.

The module's broad Foundry minimum declaration is separate from these tool
requirements. Exact tagged MCP server/module release comparison is unchanged:
mismatches warn, and normal tools remain available. Source builds still report
unverified parity. See [version diagnostics](bridge-version-diagnostics.md).

## Local testing baseline and recovery

Compose pins `felddy/foundryvtt:14.370.0` and Foundry **14.370**; the existing
local PF2e installation is **8.7.0**. Keep the private `.env` Foundry override
aligned with `.env.example`. PF2e is installed in persisted data, separately
from the Foundry container. For another checkout, install the exact
[PF2e 8.7.0 release](https://github.com/foundryvtt/pf2e/releases/tag/pf2e-8.7.0).

Stop Foundry and back up its data before package upgrades. Preserve worlds and
credentials. Launching a world can migrate its data; downgrading may require
restoring the pre-upgrade backup as well as older packages. The November 15
local upgrade retained a complete archive outside the mount and the previous
system directory under ignored `.local/`. Production and the reserved v13
packaging fixture were not changed.

## Schema audit and automated evidence

The upstream diff from PF2e 8.6.1 to
[8.7.0 revision 52dfeee](https://github.com/foundryvtt/pf2e/tree/52dfeee703b887237f5e454747bcae45b136f9af)
was reviewed for adopted contracts. `CreatureMovementData.speeds.land` became
nullable, requiring reader/validator changes. NPC melee linkage adds
`syncWeaponFeatures` and changes derived rune/material handling; source readers
do not infer those effective benefits, so no new linkage capability is claimed.
Other retained Item source allowlists and party membership schemas are
unchanged. Affliction construction remains disabled upstream. Historical
immutable 8.6.1 citations remain baseline evidence.

Unit tests cover minimums, later updates, mixed combinations, unsupported
majors, malformed versions, JavaScript/Python parity, nullable land speed and
actual in-memory FastMCP discovery/invocation with browser-generated packets.
Verifier guard/lifecycle tests remain offline and retain localhost/test-world,
GM and exact-marker cleanup restrictions.

A deterministic comparison used the original checkout and updated code, with
one discovery and seven calls each (30-call/90-second limit, no game data or
model calls). Default, selected and evidence responses stayed at 899, 2180,
3742, 993 and 2610 compact UTF-8 JSON bytes. The complete two-page workflow
remained 2420 + 2161 bytes. Both catalogs contained 42 tools. Bytes are not
billed tokens; these measurements establish unchanged equal-content payloads.
The catalog grew from 261596 to 262618 bytes as compatibility descriptions were
made explicit; the inline output schema changed from 921 to 934 bytes.

Range admission is policy, not proof that every accepted release was tested.
Historical live evidence remains for 14.369/8.6.1. Local packages were upgraded
to 14.370/8.7.0; test-world migration and browser/live compatibility checks were
deliberately deferred at the user's request. Automated tests do not establish
those runtime behaviors.
