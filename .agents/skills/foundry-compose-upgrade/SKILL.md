---
name: foundry-compose-upgrade
description: Upgrade Foundry VTT in the sesopenko/foundry-mcp Docker Compose stack, verify server health, and open its browser endpoint. Use for this repository's Foundry server upgrades.
---

Work in `/home/sean/src/github.com/sesopenko/foundry-mcp`, reading its AGENTS.md and required repository guidance first. Preserve unrelated working-tree edits.

## Upgrade

- Inspect `docker-compose.yml`, `.env.example`, and only the needed nonsecret keys in `.env`. Never print the complete interpolated Compose configuration: it contains credentials.
- Check https://hub.docker.com/r/felddy/foundryvtt/tags and the image project's documentation for the requested version. The Docker image version and downloaded Foundry application version are distinct. Prefer a matching image tag when available; preserve an intentional existing image choice unless a change is needed.
- Inspect `docker compose ps -a`. Stop the Foundry service before backing up active data. The actual bind mount here is `./foundry-data:/data` (the README previously said `./data`). Back up that directory outside the mounted tree before starting the upgraded server, and report the backup location. Also retain the old version/image values for recovery. Do not use `down -v` or delete persisted data.
- Update `FOUNDRY_VERSION` in all three places: Compose's default, `.env.example`, and the local gitignored `.env`. A local `.env` value overrides the default. Keep credentials intact. Remove an obsolete top-level Compose `version` field if it causes the Compose warning.
- Run `docker compose pull foundry`, then `docker compose up -d` from the repository root. `restart` alone does not apply environment changes. Docker socket access may require sandbox escalation; request it through the command tool rather than changing socket permissions. Use `python3`, not `python`, for any local edit helpers on this host.

## Verify and finish

Check `docker compose ps -a` and bounded startup logs. Allow downloading, extraction, and health-check startup time; avoid repeatedly recreating a container while it installs. Success requires healthy status, a log identifying the requested Foundry version/build, successful license verification, a listening server, and an HTTP response from the published port. Probe `http://localhost:30000/`; a 302 redirect to `/setup` is normal. Following the redirect should return 200. Inspect new logs for actual errors and report remaining warnings accurately. Server health does not establish world/system/module compatibility; do not launch or migrate a world unless included in the user's scope.

After successful verification, open `http://localhost:30000/` in the user's browser using the available desktop opener (on this Linux host, `xdg-open http://localhost:30000/`). Include the port explicitly. GUI launch requires sandbox escalation. If the deployment host or port differs, derive the address from the actual published port and reachable host.

If startup fails, use the specific error to fix configuration, credentials, download/cache, permissions, or port conflicts within the authorized upgrade. Do not expose passwords, license keys, or signed download URLs in reports. Do not repeatedly retry an authentication failure or restore data destructively without resolving the cause. A version downgrade after data migration may require restoring the pre-upgrade backup rather than merely changing the version variable.

## Observed 14.369 upgrade (2026-10-12)

`felddy/foundryvtt:release` pulled container version `14.368.0`. Setting `FOUNDRY_VERSION=14.369` successfully downloaded and ran Foundry Version 14 Build 369 on Node 24.21.0, with a healthy container and successful license verification. The entrypoint warned that its expected application version was 14.368. This was a warning, not a startup failure; do not claim warning-free startup or silently substitute an older application version. A matching image can remove the mismatch when published. The first download also emitted `Warning: Failed to get filetime: No such file or directory`; downloading and installation completed successfully. Do not delete a working cache in response to that warning alone.
