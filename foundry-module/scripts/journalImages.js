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
  if (!['data','public','s3'].includes(source) || !validImageDirectory(target)) fail('InvalidRequest', 'Use a published source and source-relative directory, without traversal/globs/host paths.');
  if (source === 's3' ? typeof params.bucket !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9.-]{1,254}$/.test(params.bucket) : params.bucket !== undefined) fail('InvalidRequest', 'S3 requires a bucket; other sources forbid bucket.');
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
  const selection = [world, source, target, params.bucket ?? null, filter, full];
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
    sources, revision, entries: [], total: entries.length, unfiltered_total: full.entries.length,
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
