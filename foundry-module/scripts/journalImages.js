/** Core14 image browsing via the configured public FilePicker implementation.
 * https://foundryvtt.com/api/v14/classes/foundry.applications.apps.FilePicker.html
 * Public sources, implementation and browse(source,target,{bucket,extensions,
 * wildcard}) only. No upload, filesystem access, crawling or private members.
 * Response dirs/files/target checked on Foundry14.369; other fields ignored.
 */
import {fail, validateParams, integer, digest} from './actorReadUtils.js';

// Matches the public image picker's loaded extension set on core14.369.
const EXTENSIONS = ['apng', 'avif', 'bmp', 'gif', 'jpeg', 'jpg', 'png', 'svg', 'tiff', 'webp'];
const encoder = new TextEncoder();
const bytes = value => encoder.encode(JSON.stringify(value)).length;

function ready() {
  if (!globalThis.game?.ready || !game.world?.id) fail('NotReady', 'Connect the existing ready GM world.');
  if (!game.user?.isGM) fail('PermissionDenied', 'Image discovery requires the connected GM.');
  if (!String(game.version).startsWith('14.')) fail('UnsupportedVersion', 'Image discovery requires Foundry14.');
}

/** Directory selectors are source-relative paths, not host paths or globs. */
export function validImageDirectory(value) {
  if (typeof value !== 'string' || value.length > 2048 || /[\\\x00-\x1f\x7f*?#]/.test(value) || value.startsWith('/') || /^[a-zA-Z][\w+.-]*:/.test(value)) return false;
  try {
    const decoded = decodeURIComponent(value);
    return !/[\\\x00-\x1f\x7f]/.test(decoded) && !decoded.split('/').some(part => part === '..' || part === '.');
  } catch {return false;}
}

function api() {
  const cls = globalThis.foundry?.applications?.apps?.FilePicker?.implementation;
  if (typeof cls?.browse !== 'function') fail('UnsupportedCapability', 'The public FilePicker browse API is unavailable.');
  return cls;
}

/** Core14 public FilePicker permissions at a source-relative directory.
 * Public source state and getters only; advisory User Data-only policy.
 * Server permissions are rechecked on writes. Tested on core14.369.
 */
export function imageDirectoryCapabilities(source, directory) {
  if (source !== 'data') return {can_upload: false, can_create_directory: false, reasons: ['Mutations support User Data only.']};
  const picker = new (api())({type: 'image'});
  if (!picker.sources.data) fail('UnsupportedSource', 'User Data is unavailable.');
  picker.activeSource = 'data';
  picker.sources.data.target = directory;
  const can_upload = picker.canUpload === true, can_create_directory = picker.canCreateFolder === true;
  return {can_upload, can_create_directory, reasons: can_upload && can_create_directory ? [] : ['FilePicker restricts this operation at this directory.']};
}

function sourceAvailable(cls, source, bucket) {
  const sources = new cls({type: 'image'}).sources;
  if (!sources?.[source]) fail('UnsupportedSource', 'This file source is not configured; use a source returned by browse_journal_images.');
  if (source === 's3' && Array.isArray(sources.s3.buckets) && !sources.s3.buckets.includes(bucket)) fail('UnsupportedSource', 'Selected S3 bucket is not configured for this GM.');
  if (Array.isArray(sources.s3?.buckets) && sources.s3.buckets.length > 100) fail('SourceTooLarge', 'Configured S3 source metadata exceeds100 buckets; use the native browser to reconcile configuration.');
  return Object.entries(sources).filter(([key,value]) => ['data','public','s3'].includes(key) && value).map(([source, value]) => ({source,
    ...(source === 's3' ? {buckets: Array.isArray(value.buckets) ? value.buckets.filter(bucket => typeof bucket === 'string') : []} : {})}));
}

function imagePath(value) {
  if (typeof value !== 'string' || !value || value.length > 4096 || /[\x00-\x1f\x7f\\]/.test(value)) return false;
  try {
    const url = new URL(value, 'https://foundry.invalid/');
    return ['http:', 'https:'].includes(url.protocol) && EXTENSIONS.some(ext => url.pathname.toLowerCase().endsWith('.' + ext));
  } catch {return false;}
}

function validateLocation(source, directory, bucket) {
  if (!['data','public','s3'].includes(source) || !validImageDirectory(directory)) fail('InvalidRequest', 'Use a published source and source-relative directory, without traversal/globs/host paths.');
  if (source === 's3' ? typeof bucket !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9.-]{1,254}$/.test(bucket) : bucket !== undefined) fail('InvalidRequest', 'S3 requires a bucket; other sources forbid bucket.');
}

/** Validate the entire canonical image record; no arbitrary URL-only writes. */
export function validateJournalImageSelector(image) {
  validateParams(image, ['source', 'directory', 'bucket', 'src']);
  validateLocation(image.source, image.directory, image.bucket);
  if (!imagePath(image.src)) fail('InvalidRequest', 'Use an exact image selector returned by browse_journal_images or upload_image.');
}

/** Recheck membership through the same bounded public listing used by browsing.
 * This proves current GM file discovery, not player asset access or file identity.
 */
export async function resolveJournalImage(image) {
  validateJournalImageSelector(image); ready();
  const world = game.world.id, user = game.user, cls = api();
  sourceAvailable(cls, image.source, image.bucket);
  const full = await listing(cls, image.source, image.directory, image.bucket);
  ready();
  if (world !== game.world.id || user !== game.user) fail('ContextChanged', 'World or GM changed while checking the image.');
  const match = full.entries.find(entry => entry.kind === 'image' && entry.image.src === image.src);
  if (!match || full.directory !== image.directory) fail('ImageNotFound', 'Image is no longer in the selected directory; browse_journal_images again.');
  return match.image;
}

/** Strict segment comparison for preview hints, without decoding separators.
 * Decode exactly once per segment; percent literals remain literal. Reject dot
 * segments before URL normalization, which would otherwise erase traversal.
 */
function previewPath(path) {
  if (typeof path !== 'string' || /[\\\x00-\x1f\x7f]/.test(path) || /%(?![0-9a-f]{2})/i.test(path)) fail('InvalidRequest', 'Invalid image reference; use an exact returned image selector.');
  const parts = path.split('/');
  try {
    return parts.map(part => {
      const decoded = decodeURIComponent(part);
      if (decoded === '.' || decoded === '..' || /[/\\\x00-\x1f\x7f]/.test(decoded)) throw Error();
      return decoded;
    });
  } catch {fail('InvalidRequest', 'Image reference contains traversal, encoded separators or malformed escaping.');}
}

/** Only harmless local cache hints are ignored; source credentials are not hints. */
function localPreviewQuery(query) {
  for (const [key, value] of new URLSearchParams(query)) {
    if (!['v','version','t','cache','cb','cacheBust','_'].includes(key) || !/^[A-Za-z0-9_.~-]{0,128}$/.test(value)) {
      fail('InvalidRequest', 'Local image references accept only harmless cache-busting suffixes.');
    }
  }
}

/** Browser-only preview selection through core14 public APIs, tested14.369.
 * https://foundryvtt.com/api/v14/classes/foundry.applications.apps.FilePicker.html
 * https://foundryvtt.com/api/v14/functions/foundry.utils.getRoute.html
 * Uses configured sources, getRoute, and fresh browse/resolveJournalImage only.
 * Input is exactly one image or src. Returns PRIVATE canonical image, fetch_url,
 * credentials, world_id and user_id; never expose this record through MCP/logs.
 * No fetch, crawling, game-system semantics or prepared UI state. Bare hints
 * inspect only their parent in configured sources/buckets (<=100 buckets), then
 * recheck exact membership. isCurrent binds the initiating socket across awaits.
 */
export async function resolvePreviewSource(params, isCurrent = () => true) {
  validateParams(params, ['image', 'src']);
  if (Object.keys(params).length !== 1 || (params.image === undefined && params.src === undefined)) fail('InvalidRequest', 'Provide exactly one image or src.');
  ready();
  const world = game.world.id, user = game.user;
  const guard = () => {
    ready();
    if (!isCurrent() || world !== game.world.id || user !== game.user) fail('ContextChanged', 'GM, world or socket changed; resolve the image again.');
  };
  guard();
  const cls = api();
  const configured = new cls({type: 'image'}).sources;
  if (!globalThis.location?.origin || typeof globalThis.foundry?.utils?.getRoute !== 'function') fail('UnsupportedCapability', 'Public route resolution is unavailable; check matching core14/module versions.');
  const origin = location.origin;
  const route = foundry.utils.getRoute('');
  if (typeof route !== 'string' || !route.startsWith('/') || route.startsWith('//')) fail('UnsupportedCapability', 'Unsupported public route prefix.');
  const prefix = route.replace(/\/$/, '');

  const parse = value => {
    if (!imagePath(value) || value.startsWith('//') || value.includes('#')) fail('InvalidRequest', 'Use a supported image reference in configured Foundry sources.');
    // Inspect the raw spelling before the URL parser removes dot segments.
    const absolute = /^[A-Za-z][\w+.-]*:/.test(value);
    const rawPath = (absolute ? value.replace(/^https?:\/\/[^/]*(?=\/|$)/i, '') : value).split('?')[0];
    previewPath(rawPath);
    let url;
    try {url = new URL(value, origin + prefix + '/');}
    catch {fail('InvalidRequest', 'Invalid image reference; browse_journal_images for an exact selector.');}
    if (url.username || url.password || !['http:','https:'].includes(url.protocol)) fail('InvalidRequest', 'Credential-bearing references are unsupported.');
    const path = previewPath(url.pathname).join('/');
    return {url, path};
  };
  const localPath = parsed => {
    if (parsed.url.origin !== origin) return null;
    localPreviewQuery(parsed.url.search);
    if (prefix && !parsed.url.pathname.startsWith(prefix + '/')) return null;
    return previewPath(parsed.url.pathname.slice(prefix.length + 1)).join('/');
  };
  const resolved = async image => {
    const selected = await resolveJournalImage(image); guard();
    const parsed = parse(selected.src);
    if (selected.source !== 's3' && localPath(parsed) === null) fail('InvalidRequest', 'Local picker object must stay on the configured Foundry origin/route.');
    return {image: selected, fetch_url: parsed.url.href, credentials: selected.source === 's3' ? 'omit' : 'same-origin', world_id: world, user_id: user.id};
  };
  if (params.image !== undefined) return resolved(params.image);
  const hint = parse(params.src), local = localPath(hint);
  const buckets = configured?.s3?.buckets ?? [];
  if (!Array.isArray(buckets) || buckets.length > 100) fail('SourceTooLarge', 'Configured S3 metadata exceeds the supported100 buckets; select an exact image through browse_journal_images.');
  const candidates = [];
  if (local !== null) {
    const directory = hint.url.pathname.slice(prefix.length + 1).split('/').slice(0,-1).join('/');
    for (const source of ['data','public']) if (configured?.[source]) candidates.push({source, directory});
  }
  // An absolute S3 URL is a hint only. Picker membership, including its exact
  // host and path, is authoritative. Path-style bucket prefixes are removed
  // only when they exactly name the configured bucket.
  if (hint.url.origin !== origin && /^https?:\/\//i.test(params.src)) {
    for (const bucket of buckets) {
      validateLocation('s3', '', bucket);
      const parts = hint.url.pathname.slice(1).split('/');
      if (parts[0] === bucket) parts.shift();
      candidates.push({source: 's3', bucket, directory: parts.slice(0,-1).join('/')});
    }
  }
  if (!candidates.length) fail('UnsupportedSource', 'Reference does not identify a configured Foundry source; use browse_journal_images.');
  const matches = [];
  let unavailable = false;
  for (const location of candidates) {
    validateLocation(location.source, location.directory, location.bucket);
    let full;
    try {full = await listing(cls, location.source, location.directory, location.bucket);}
    catch (error) {
      guard();
      if (error.rpcError?.code !== 'BrowseFailed') throw error;
      unavailable = true; continue;
    }
    guard();
    for (const entry of full.entries) {
      if (entry.kind !== 'image') continue;
      const selected = parse(entry.image.src);
      const same = location.source === 's3'
        ? selected.url.origin === hint.url.origin && selected.path === hint.path
        : localPath(selected) === local;
      if (same) matches.push(entry.image);
    }
  }
  // Match only positively authorized picker objects, never an arbitrary first
  // match or an inferred file from a failed listing. Keep unavailable-source
  // coverage distinct from an empty successful search.
  if (!matches.length) {
    if (unavailable) fail('BrowseFailed', 'Referenced parent is missing, denied or unavailable; no absence established. Use browse_journal_images and pass an exact image record.');
    fail('ImageNotFound', 'No image in the referenced parent matches; browse_journal_images and select an exact image record.');
  }
  if (matches.length > 1) {
    const {source, directory, bucket} = matches[0];
    const recovery = JSON.stringify({tool: 'browse_journal_images', arguments: {source, directory, ...(bucket ? {bucket} : {}), limit: 10, max_bytes: 8000}});
    fail('AmbiguousSource', 'Reference matches multiple sources. Select one exact image record via ' + recovery);
  }
  const result = await resolved(matches[0]);
  if (unavailable) Object.assign(result, {scope_status: 'partial', limitations: ['Some configured source parents were unavailable. Selection identifies the sole verified readable match, not absence in unavailable sources.']});
  return result;
}

/** Load one native directory, never recurse. Native API has no server paging;
 * reject >10000 returned paths or >2MiB listing JSON before projecting output.
 */
async function listing(cls, source, target, bucket) {
  let raw;
  try {raw = await cls.browse(source, target, {extensions: EXTENSIONS.map(ext => '.' + ext), wildcard: false, ...(bucket ? {bucket} : {})});}
  catch {fail('BrowseFailed', 'Directory is missing, denied or unavailable; choose a returned parent/source and retry. No absence is established.');}
  if (!raw || !Array.isArray(raw.dirs) || !Array.isArray(raw.files) || !validImageDirectory(raw.target)) fail('ReadFailed', 'Unsupported FilePicker response; check server/module and core versions.');
  if (raw.dirs.length + raw.files.length > 10000 || bytes({dirs: raw.dirs, files: raw.files}) > 2097152) fail('DirectoryTooLarge', 'Native listing exceeds10000 paths/2MiB; choose a narrower known directory. Foundry loads one complete native listing before this check.');
  const seen = new Set(), entries = [];
  for (const [kind, paths] of [['directory', raw.dirs], ['image', raw.files]]) {
    for (const path of paths) {
      if (kind === 'directory' ? !validImageDirectory(path) || !path : !imagePath(path)) fail('ReadFailed', 'FilePicker returned an invalid directory/image path; no partial list returned.');
      const key = kind + ':' + path;
      if (seen.has(key)) continue;
      seen.add(key);
      const tail = path.split('/').at(-1);
      let name;
      try {name = decodeURIComponent(tail);} catch {name = tail;}
      const common = {kind, name: [...name].slice(0,256).join(''), name_truncated: [...name].length > 256};
      entries.push(kind === 'directory' ? {...common, directory: path,
        next_call: {tool: 'browse_journal_images', arguments: {source, directory: path, ...(bucket ? {bucket} : {})}}}
        : {...common, image: {source, directory: raw.target, ...(bucket ? {bucket} : {}), src: path}});
    }
  }
  entries.sort((a,b) => a.kind.localeCompare(b.kind) || (a.directory ?? a.image.src).localeCompare(b.directory ?? b.image.src));
  return {directory: raw.target, entries};
}

/** Bounded read-only navigation of existing image paths, not journal folders. */
export async function browseJournalImages(params = {}) {
  validateParams(params, ['source', 'directory', 'bucket', 'name_contains', 'limit', 'cursor', 'max_bytes']);
  const source = params.source ?? 'data', target = params.directory ?? '', filter = params.name_contains ?? '';
  validateLocation(source, target, params.bucket);
  if (typeof filter !== 'string' || filter.length > 256) fail('InvalidRequest', 'name_contains is a literal substring up to256 characters.');
  const limit = integer(params.limit, 10, 1, 100, 'limit'), max = integer(params.max_bytes, 8000, 8000, 48000, 'max_bytes');
  if (params.cursor != null) {
    validateParams(params.cursor, ['offset', 'revision']);
    integer(params.cursor.offset, undefined, 0, 10000, 'cursor.offset');
    if (typeof params.cursor.revision !== 'string') fail('InvalidCursor', 'Return the complete next_cursor unchanged.');
  }
  ready();
  const world = game.world.id, user = game.user, cls = api(), sources = sourceAvailable(cls, source, params.bucket);
  const full = await listing(cls, source, target, params.bucket);
  ready();
  if (world !== game.world.id || user !== game.user) fail('ContextChanged', 'World or GM changed during browsing; restart.');
  const capabilities = imageDirectoryCapabilities(source, full.directory);
  for (const entry of full.entries) if (entry.kind === 'directory') entry.capabilities = imageDirectoryCapabilities(source, entry.directory);
  const selection = [world, source, target, params.bucket ?? null, filter, full, capabilities];
  const revision = await digest(selection);
  ready();
  if (world !== game.world.id || user !== game.user) fail('ContextChanged', 'World or GM changed during browsing; restart.');
  if (params.cursor && params.cursor.revision !== revision) fail('ContentChanged', 'Directory/selection changed; discard earlier pages and restart.');
  const entries = full.entries.filter(entry => {
    const tail = (entry.directory ?? entry.image.src).split('/').at(-1);
    let name;
    try {name = decodeURIComponent(tail);} catch {name = tail;}
    return name.toLocaleLowerCase().includes(filter.toLocaleLowerCase());
  });
  const offset = params.cursor?.offset ?? 0;
  if (offset > entries.length) fail('InvalidCursor', 'Offset exceeds current selection; restart.');
  const result = {location: {source, directory: full.directory, ...(params.bucket ? {bucket: params.bucket} : {})},
    sources, capabilities, revision, entries: [], total: entries.length, unfiltered_total: full.entries.length,
    complete: false, next_cursor: null,
    limitations: ['One directory only; name matching is literal, not semantic or recursive.',
      'Paths do not establish image contents, suitability or player access. Native FilePicker loads a complete directory before output pagination.']};
  for (const entry of entries.slice(offset, offset + limit)) {
    const next = offset + result.entries.length + 1;
    const candidate = {...result, entries: [...result.entries, entry], complete: next === entries.length,
      next_cursor: next === entries.length ? null : {offset: next, revision}};
    if (bytes(candidate) > max) break;
    Object.assign(result, candidate);
  }
  if (!result.entries.length) {
    if (offset < entries.length) fail('ResponseTooLarge', 'Raise max_bytes for the next named path; it is never truncated.');
    result.complete = true;
  }
  if (bytes(result) > max) fail('ResponseTooLarge', 'Raise max_bytes for source metadata.');
  return result;
}
