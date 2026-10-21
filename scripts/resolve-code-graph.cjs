#!/usr/bin/env node
// Bypass upstream's shared-cache launcher: only this checkout's exact engine.
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const {execFileSync} = require('node:child_process');
try {
  const root = fs.realpathSync(path.join(__dirname, '..'));
  const pin = JSON.parse(fs.readFileSync(path.join(root, 'package.json'))).devDependencies['@sdsrs/code-graph'];
  if (!/^\d+\.\d+\.\d+$/.test(pin)) throw Error('Root dependency must be an exact version');
  const localRequire = createRequire(path.join(root, 'package.json'));
  const parent = localRequire.resolve('@sdsrs/code-graph/package.json');
  if (process.platform !== 'linux' || !['x64', 'arm64'].includes(process.arch)) throw Error('Requires Linux x64 or arm64 (arm64 unverified)');
  const platform = createRequire(parent).resolve(`@sdsrs/code-graph-linux-${process.arch}/package.json`);
  const binary = fs.realpathSync(path.join(path.dirname(platform), 'code-graph-mcp'));
  const prefix = path.join(root, 'node_modules') + path.sep;
  for (const file of [parent, platform, binary]) {
    if (!fs.realpathSync(file).startsWith(prefix)) throw Error('Package or executable escapes checkout node_modules');
  }
  for (const file of [parent, platform]) {
    if (JSON.parse(fs.readFileSync(file)).version !== pin) throw Error('Installed package differs from root pin');
  }
  fs.accessSync(binary, fs.constants.X_OK);
  if (execFileSync(binary, ['--version'], {encoding:'utf8', timeout:10000}).trim() !== `code-graph-mcp ${pin}`) throw Error('Native engine version mismatch');
  console.log(binary);
} catch (error) {
  console.error(`code-graph: ${error.message}. Run ./scripts/dev-setup.sh with checkout consumers stopped.`);
  process.exit(1);
}
