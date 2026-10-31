---
name: foundry-release
description: Infer the semantic release version from changes since the last tag, synchronize foundry-mcp server/image and Foundry manifest versions, validate, commit, tag, and push for GitHub Actions publication. Use when asked to bump and release this project, not for ordinary commits or deployment restarts.
---

# Release Foundry MCP

Work from the repository root. Read AGENTS.md, its required reading, and
[the release instructions](../../../docs/operations.md#module-versioning-and-releases).
The outcome is one reviewed release commit on `main` and a matching `vX.Y.Z`
tag pushed to `origin`. GitHub Actions publishes Docker Hub SHA/version/`latest`
images and the Foundry module's public manifest and ZIP.

Invoking this skill to perform a release authorizes its commit, tag and push;
do not ask for an extra confirmation already supplied by that request. Honor
explicit narrower instructions such as prepare-only or do-not-push, and normal
command-tool permission boundaries. Creating/editing this skill does not run it.
Do not manually build/push/retag registry images, replace release assets, modify
GitHub secrets, or deploy/restart any remote service as part of a release.

## Infer the semantic release version

The LLM owns version selection; do not default every release to a patch bump
or ask the user to classify changes that can be understood from Git.

1. Inspect the branch and origin, then fetch main and release tags with the
   host Git CLI. Identify the last stable `vX.Y.Z` release tag reachable from
   the release branch; inspect tag ancestry/history rather than choosing an
   unrelated branch's numerically highest tag.
2. Review commit history and actual diffs from that tag through HEAD, plus
   staged changes, unstaged changes, and release-relevant untracked files.
   Include the complete release, not only the most recent commit. Commit
   subjects and conventional-commit prefixes are clues, not evidence by
   themselves. Ignore unrelated edits excluded from the release.
3. Choose the highest semantic impact present:
   - **Major:** incompatible changes to an established consumer interface:
     MCP tool names, accepted inputs, response/continuation contracts, supported
     runtime requirements, or required configuration/authentication/protocol
     changes that break existing integrations without adaptation.
   - **Minor:** backward-compatible features, tools or optional capabilities.
   - **Patch:** backward-compatible fixes, docs, tests, packaging, CI and
     maintenance changes with no new user-facing capability or breaking contract.
   For a pre-1.0 project without another documented convention, use a minor
   increment for breaking changes or features and patch for fixes/maintenance.
   Reset lower components when incrementing minor or major.
4. State the base tag, selected version and concise rationale tied to concrete
   changes. Use a version explicitly requested by the user when supplied,
   explaining any semantic-version mismatch. If no tag exists, inspect all
   history and the project's current version before selecting the initial
   release; do not invent a previous release. If nothing changed, report that
   instead of manufacturing a release.

Compare the selected version with versions already edited in the working tree.
If the same release is partly prepared, finish synchronizing it instead of
incrementing again. Never silently downgrade an already prepared version; resolve
an actual conflict with user intent before publishing.

## Inspect release state

- Inspect status, staged changes, branch, origin URL, and recent commits. Include
  only changes belonging to the requested release. Preserve unrelated edits and
  staging; never use blanket `git add .`, stash, reset, or force-push to simplify
  release preparation. If the intended commit scope cannot be determined, ask.
- Require the release branch to be `main` and origin to be this public project.
  Confirm origin/main is
  an ancestor of the intended release commit and the proposed tag is absent
  locally and remotely. If another branch, divergent remote changes, or an
  existing tag conflicts, resolve scope with the user rather than moving tags
  or automatically merging unrelated work.

## Prepare synchronized versions

After selecting `X.Y.Z` from the release analysis, use the helper first in
dry-run mode, then apply that same explicit version:

```bash
python3 .agents/skills/foundry-release/scripts/bump-version.py --version X.Y.Z --dry-run
python3 .agents/skills/foundry-release/scripts/bump-version.py --version X.Y.Z
```

The helper intentionally has no default bump policy. It only applies the LLM's
selected version. If that version is already partly applied, inspect and finish
the existing edits rather than applying another bump.

The helper updates project/runtime/container versions, only the project entry
in `uv.lock`, module version and versioned ZIP URL, packaging expectations, and
current deployment/documentation examples. It preserves the stable manifest URL
and historical verification records. It performs no Git or network actions.
If expected source entries changed, inspect and adjust the helper or make focused
edits rather than doing a repository-wide version replacement.

Review the diff against AGENTS.md's version-bump rule. Keep
`https://github.com/sesopenko/foundry-mcp/releases/latest/download/module.json`
as the public manifest URL; its `version` and version-specific ZIP must describe
the new release. Update the Docker Hub overview for behavior changes. Do not
add `compatibility.verified` claims without supporting evidence.

## Validate, commit, tag and push

- Run `./scripts/test.sh`, then
  `.venv/bin/python scripts/package-module.py --tag vX.Y.Z` and `git diff --check`.
  Resolve relevant failures before proceeding. Routine version bumps do not need
  a new Foundry instance, another manual setup, or repeated exploratory testing.
- Inspect generated `dist/module/module.json` and the ZIP; packaging must validate
  synchronized versions, stable manifest, exact release download URL and imports.
  Keep generated archives and private files out of the commit.
- Stage explicit release paths, review `git diff --cached`, and commit a concise
  description of the released changes. Do not bypass failing commit hooks.
- Recheck the remote tag, create local `vX.Y.Z` at the release commit, then push
  the branch and exact tag together:

  ```bash
  git tag vX.Y.Z
  git push --atomic origin main refs/tags/vX.Y.Z
  ```

  Substitute the chosen version. Never force a push or move an existing tag.
  If a push fails, inspect local/remote commit and tag state before retrying;
  resume the same release instead of creating another bump or duplicate tag.

## Verify publication and report

When GitHub access is available, locate the tag-triggered `CI and releases`
run for the pushed commit (a main-triggered run is separate). Inspect `verify`,
`push-image`, and `release-module`. Check the Docker Hub tag and anonymous
GitHub release assets; the stable manifest must advertise `X.Y.Z` and its ZIP.
Use bounded status checks with progress updates. Do not confuse queued/skipped
jobs or a successful Git push with completed publication.

For unattended public liveness checks, use plain
`./scripts/release-liveness.sh <check>` invocations. Reviewed choices are `runs`
(five recent workflow runs), `release` (latest release metadata), `manifest`
(stable Foundry manifest), `module` (stable ZIP headers), and `images` (ten
Docker Hub tags). Inspect returned tag/commit/digest, not merely HTTP success.
The runner permits only fixed anonymous HTTPS GET/HEAD requests, ignores curl
configuration, and rejects extra arguments, URLs and options. Project rules in
`.codex/rules/release-liveness.rules` allow this runner rather than unrestricted
curl. Other endpoints retain normal approval requirements. Restart Codex after
rule changes; liveness permission alone never authorizes release or deployment.

If credentials or permissions block publication, report the precise job/reason
and stop publishing attempts until corrected. Required Actions secrets are
`DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` (Read/Write access); the Actions
variable `PUSH_IMAGE_ENABLED` must be `true`. Do not display secret values.
Retry only failed work when appropriate; never overwrite immutable tags/assets
or fall back to manual registry publication. If CI cannot be inspected, report
that limitation and link the Actions page instead of claiming success.

Finish with commit SHA, release tag, pushed remote, validation results, CI and
asset status, and any remaining operator action. The user applies container and
Foundry module updates separately. Link this skill when reporting its use.
