import { BUILD_INFO } from "./buildInfo.js";

const versionPattern = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/;
const reported = new Set();

export function validBuildInfo(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  if (value.build_kind === "unknown") return value.version === null && value.release_tag === null && value.revision === null;
  if (typeof value.version !== "string" || value.version.length > 64 || !versionPattern.test(value.version)) return false;
  if (value.revision !== null && (typeof value.revision !== "string" || !/^[0-9a-f]{40}$/.test(value.revision))) return false;
  return value.build_kind === "release" ? value.release_tag === `v${value.version}`
    : ["source", "unreleased"].includes(value.build_kind) && value.release_tag === null;
}

export function getModuleBuildInfo() { return { ...BUILD_INFO }; }

/** Compare loaded JavaScript identity, never a manifest fetched after installation. */
export function reportServerBuild(server, module = BUILD_INFO) {
  const unknown = { version: null, release_tag: null, revision: null, build_kind: "unknown" };
  server = validBuildInfo(server) ? server : unknown;
  module = validBuildInfo(module) ? module : unknown;
  const verified = server.build_kind === "release" && module.build_kind === "release";
  const comparison = verified ? (server.version === module.version ? "match" : "mismatch") : "unverified";
  if (comparison === "match") return comparison;
  const key = JSON.stringify([server, module]);
  if (reported.has(key)) return comparison;
  reported.add(key);
  const label = info => `${info.version ?? "unknown"} (${info.build_kind})`;
  if (comparison === "mismatch") {
    const parts = value => value.split(".").map(BigInt);
    const a = parts(server.version), b = parts(module.version);
    const index = a.findIndex((n, i) => n !== b[i]);
    const older = a[index] < b[index] ? "MCP server/container" : "Foundry module";
    globalThis.ui?.notifications?.warn(`Foundry MCP — Version mismatch: server ${server.release_tag}; module ${module.release_tag}. Update the older ${older}, then reload the GM browser and reconnect. Normal tools remain available.`, { permanent: true });
  } else {
    globalThis.ui?.notifications?.info(`Foundry MCP — Release comparison unverified: server ${label(server)}; module ${label(module)}. Use get_bridge_versions for details.`);
  }
  return comparison;
}
