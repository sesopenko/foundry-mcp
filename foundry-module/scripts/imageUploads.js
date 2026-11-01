/** User Data image mutations through public core14 FilePicker APIs only.
 * https://foundryvtt.com/api/v14/classes/foundry.applications.apps.FilePicker.html
 * Public implementation, sources, activeSource, canUpload/canCreateFolder,
 * browse/createDirectory/upload; browser File/Blob/fetch/crypto/Image APIs.
 * No PF2e dependencies. API/source checked on core14.369; no private members.
 */
import {fail, validateParams} from './actorReadUtils.js';
import {validImageDirectory, imageDirectoryCapabilities} from './journalImages.js';

const MAX_BYTES = 10 * 1024 * 1024;
const FORMATS = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp'};
let busy = false;

function connected(isCurrent) {
  if (!isCurrent()) fail('ContextChanged', 'The originating GM socket disconnected; inspect the destination before retrying.');
}

function context(world) {
  if (!globalThis.game?.ready || !game.world?.id) fail('NotReady', 'Connect the ready GM world.');
  if (!game.user?.isGM) fail('PermissionDenied', 'Image mutations require the connected GM.');
  if (!String(game.version).startsWith('14.')) fail('UnsupportedVersion', 'Image uploads require Foundry14.');
  if (world !== undefined && world !== game.world.id) fail('ContextChanged', 'World changed; browse the destination again.');
  return {world_id: game.world.id, user_id: game.user.id};
}

function directory(value) {
  if (!validImageDirectory(value) || value.includes('//') || value.endsWith('/')) fail('InvalidRequest', 'Use the exact User Data directory from browsing.');
}

export function validateImageName(value, stem = false) {
  if (typeof value !== 'string' || !value || value !== value.trim() || [...value].length > 200 || new TextEncoder().encode(value).length > 240 ||
      /[\\/\x00-\x1f\x7f<>:"|?*%#]/.test(value) || ['.', '..'].includes(value) || value.endsWith('.') ||
      (stem && /\.(?:jpe?g|png|webp)$/i.test(value))) fail('InvalidRequest', 'Use one name up to200 characters, without paths, controls, reserved characters or an image extension.');
}

function picker() {
  const cls = globalThis.foundry?.applications?.apps?.FilePicker?.implementation;
  if (!cls?.browse || !cls?.upload || !cls?.createDirectory) fail('UnsupportedCapability', 'Update the module and check the public FilePicker APIs.');
  return cls;
}

async function listing(target) {
  let raw;
  try {raw = await picker().browse('data', target, {wildcard: false});}
  catch {fail('BrowseFailed', 'Destination is missing, denied or unavailable; browse an existing parent.');}
  if (!raw || !validImageDirectory(raw.target) || matchingPath([raw.target], target) === undefined || !Array.isArray(raw.dirs) || !Array.isArray(raw.files)) fail('BrowseFailed', 'Exact destination could not be verified; browse again.');
  if (raw.dirs.length + raw.files.length > 10000 || new TextEncoder().encode(JSON.stringify(raw)).length > 2097152)
    fail('DirectoryTooLarge', 'Choose a directory below10000 entries/2MiB of listing data.');
  if (![...raw.dirs, ...raw.files].every(path => typeof path === 'string')) fail('ReadFailed', 'Invalid FilePicker listing.');
  return raw;
}

function requireCapability(target, key) {
  if (!imageDirectoryCapabilities('data', target)[key]) fail('PermissionDenied', 'FilePicker does not permit this operation in this User Data directory.');
}

/** FilePicker returns URI-encoded file paths on core14.369. Compare the
 * decoded spelling, but always return and fetch the exact observed selector.
 */
function matchingPath(paths, target) {
  const matches = paths.filter(path => {
    try {return decodeURIComponent(path) === decodeURIComponent(target);} catch {return false;}
  });
  if (matches.length > 1) fail('ReadFailed', 'Ambiguous native path listing; inspect the directory.');
  return matches[0];
}

async function exclusive(operation) {
  if (busy) fail('Busy', 'Another image operation is active; retry after it completes.');
  busy = true;
  try {return await operation();} finally {busy = false;}
}

/** Read-only preflight. No image bytes or URLs are supplied to Foundry. */
export async function prepareImageUpload(params, isCurrent = () => true) {
  validateParams(params, ['directory']); directory(params.directory);
  connected(isCurrent);
  const identity = context(), user = game.user;
  const raw = await listing(params.directory);
  connected(isCurrent);
  context(identity.world_id);
  if (game.user !== user) fail('ContextChanged', 'GM changed; browse again.');
  requireCapability(raw.target, 'can_upload');
  return {...identity, location: {source: 'data', directory: raw.target}, capabilities: imageDirectoryCapabilities('data', raw.target)};
}

/** Create exactly one User Data child; never recursively create parents. */
export async function createImageDirectory(params, isCurrent = () => true) {
  validateParams(params, ['directory', 'name']); directory(params.directory); validateImageName(params.name);
  return exclusive(async () => {
    connected(isCurrent);
    const identity = context(), user = game.user, target = [params.directory, params.name].filter(Boolean).join('/');
    directory(target);
    const raw = await listing(params.directory);
    connected(isCurrent);
    context(identity.world_id);
    if (game.user !== user) fail('ContextChanged', 'GM changed; browse again.');
    requireCapability(params.directory, 'can_create_directory');
    let status = 'already_exists';
    if (!matchingPath(raw.dirs, target)) {
      if (matchingPath(raw.files, target)) fail('FileExists', 'A file already has this folder name; choose another name.');
      try {await picker().createDirectory('data', target);}
      catch {fail('CreateDirectoryFailed', 'Folder creation failed; browse the parent before retrying.');}
      status = 'created';
    }
    context(identity.world_id);
    if (game.user !== user) fail('ContextChanged', 'GM changed; inspect the parent before retrying.');
    connected(isCurrent);
    const verified = await listing(target);
    connected(isCurrent);
    context(identity.world_id);
    if (game.user !== user) fail('ContextChanged', 'GM changed; inspect the parent before retrying.');
    return {status, ...identity, location: {source: 'data', directory: verified.target}, capabilities: imageDirectoryCapabilities('data', verified.target),
      next_call: {tool: 'browse_journal_images', arguments: {source: 'data', directory: verified.target}}};
  });
}

const sha256 = async bytes => [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(v => v.toString(16).padStart(2, '0')).join('');

async function verifyStored(src, expected, signal) {
  const response = await fetch(src, {cache: 'no-store', signal});
  if (!response.ok) throw Error('Unavailable');
  const reader = response.body.getReader(), chunks = []; let length = 0;
  try {
    for (;;) {
      const {done, value} = await reader.read(); if (done) break;
      length += value.length;
      if (length > expected.size_bytes || length > MAX_BYTES) throw Error('Too large');
      chunks.push(value);
    }
  } finally {await reader.cancel();}
  const saved = new Uint8Array(length); let offset = 0;
  for (const chunk of chunks) {saved.set(chunk, offset); offset += chunk.length;}
  if (length !== expected.size_bytes || await sha256(saved) !== expected.sha256) throw Error('Changed');
  const url = URL.createObjectURL(new Blob([saved], {type: expected.mime_type}));
  try {
    const image = new Image();
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => {image.src = ''; reject(Error('Timeout'));}, 5000);
      image.onload = () => {clearTimeout(timer); resolve();};
      image.onerror = () => {clearTimeout(timer); reject(Error('Broken'));};
      image.src = url;
    });
    if (image.naturalWidth !== expected.width || image.naturalHeight !== expected.height) throw Error('Wrong dimensions');
  } finally {URL.revokeObjectURL(url);}
}

/** Upload validated bytes from Python, never external URLs or arbitrary files.
 * Existing destinations require explicit overwrite. No automatic retry/rollback;
 * external writers can race the public browse-then-upload API.
 */
export async function uploadImage(params, isCurrent = () => true) {
  validateParams(params, ['directory', 'filename', 'overwrite', 'world_id', 'user_id', 'mime_type', 'size_bytes', 'sha256', 'width', 'height', 'content']);
  directory(params.directory); validateImageName(params.filename, true);
  const extension = FORMATS[params.mime_type];
  if (!extension || typeof params.overwrite !== 'boolean' || !Number.isInteger(params.size_bytes) || params.size_bytes < 1 || params.size_bytes > MAX_BYTES ||
      typeof params.content !== 'string' || params.content.length > 4 * Math.ceil(MAX_BYTES / 3) || !/^[a-f0-9]{64}$/.test(params.sha256) ||
      ![params.width, params.height].every(v => Number.isInteger(v) && v >= 1 && v <= 8192) || params.width * params.height > 32000000)
    fail('InvalidRequest', 'Invalid bounded image transfer.');
  return exclusive(async () => {
    connected(isCurrent);
    const identity = context(params.world_id), user = game.user;
    if (identity.user_id !== params.user_id) fail('ContextChanged', 'GM changed since preflight.');
    const name = `${params.filename}.${extension}`, target = `${params.directory}/${name}`;
    let bytes;
    try {bytes = Uint8Array.from(atob(params.content), char => char.charCodeAt(0));}
    catch {fail('InvalidRequest', 'Invalid image transfer encoding.');}
    if (bytes.length !== params.size_bytes || await sha256(bytes) !== params.sha256) fail('InvalidRequest', 'Image transfer checksum/length mismatch.');
    const raw = await listing(params.directory);
    connected(isCurrent);
    context(params.world_id);
    if (game.user !== user) fail('ContextChanged', 'GM changed since preflight.');
    requireCapability(params.directory, 'can_upload');
    const exists = Boolean(matchingPath(raw.files, target));
    if (matchingPath(raw.dirs, target) || (exists && !params.overwrite)) fail('FileExists', 'Destination already exists. Choose another filename or explicitly set overwrite=true for permanent replacement.');
    try {
      const uploaded = await picker().upload('data', params.directory, new File([bytes], name, {type: params.mime_type}), {}, {notify: false});
      if (typeof uploaded?.path !== 'string' || !matchingPath([uploaded.path], target)) throw Error('Unconfirmed upload');
    }
    catch {return {status: 'upload_outcome_unknown', ...identity, candidate_path: target, error_code: 'UploadFailed', message: 'Upload may have stored the file; inspect the destination before retrying.'};}
    let storedPath;
    try {
      connected(isCurrent);
      context(params.world_id);
      if (game.user !== user) throw Error('Changed GM');
      const after = await listing(params.directory);
      storedPath = matchingPath(after.files, target);
      if (!storedPath) throw Error('Missing exact path');
      await verifyStored(storedPath, params, AbortSignal.timeout(10000));
      connected(isCurrent);
      context(params.world_id);
      if (game.user !== user) throw Error('Changed GM');
    } catch {return {status: 'upload_outcome_unknown', ...identity, candidate_path: target, error_code: 'VerificationFailed', message: 'The file may exist but verification failed; inspect it before retrying.'};}
    return {status: 'uploaded', ...identity, filename: name, mime_type: params.mime_type, width: params.width, height: params.height,
      size_bytes: params.size_bytes, sha256: params.sha256, overwritten: exists, image: {source: 'data', directory: params.directory, src: storedPath}};
  });
}
