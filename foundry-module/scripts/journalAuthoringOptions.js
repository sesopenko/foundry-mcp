/** Core14 public font/recipient discovery for journal authoring only.
 * FontConfig.getAvailableFonts is public (no font installation or internals):
 * https://foundryvtt.com/api/v14/classes/foundry.applications.settings.menus.FontConfig.html#getavailablefonts
 * User.id/name/isGM are public document identity; offline players are included.
 */
import {fail, validateParams, integer, digest} from './actorReadUtils.js';

export function journalPlayers() {
  return [...game.users.values()].filter(user => !user.isGM).map(user => ({user_id: user.id, name: user.name})).sort((a,b) => a.user_id.localeCompare(b.user_id));
}

export function journalFonts() {
  const api = globalThis.foundry?.applications?.settings?.menus?.FontConfig;
  if (typeof api?.getAvailableFonts !== 'function') fail('UnsupportedCapability', 'The public loaded-font API is unavailable; omit font_family.');
  const fonts = api.getAvailableFonts();
  if (!Array.isArray(fonts) || fonts.length > 10000 || fonts.some(font => typeof font !== 'string' || !font || font.length > 256)) fail('ReadFailed', 'Loaded-font API returned an unsupported list.');
  return [...new Set(fonts)].sort();
}

function ready() {
  if (!globalThis.game?.ready || !game.users || !game.world?.id) fail('NotReady', 'Connect the existing ready GM world.');
  if (!game.user?.isGM) fail('PermissionDenied', 'Journal authoring options require the GM.');
  if (!String(game.version).startsWith('14.')) fail('UnsupportedVersion', 'Journal authoring requires Foundry14.');
}

/** Bounded named recipients or fonts; continuation binds the exact world/list. */
export async function getJournalAuthoringOptions(params = {}) {
  validateParams(params, ['kind', 'limit', 'cursor', 'max_bytes']);
  if (!['players', 'fonts'].includes(params.kind)) fail('InvalidRequest', 'Choose kind=players or fonts.');
  const limit = integer(params.limit, 10, 1, 100, 'limit'), max = integer(params.max_bytes, 8000, 8000, 48000, 'max_bytes');
  if (params.cursor != null) {
    validateParams(params.cursor, ['offset', 'revision']);
    integer(params.cursor.offset, undefined, 0, 10000, 'cursor.offset');
    if (typeof params.cursor.revision !== 'string') fail('InvalidCursor', 'Return the complete next_cursor unchanged.');
  }
  ready();
  const world = game.world.id, user = game.user;
  const get = () => params.kind === 'players' ? journalPlayers() : journalFonts().map(font_family => ({font_family}));
  const entries = get();
  if (entries.length > 10000) fail('ReadFailed', 'Discovery exceeds 10000 entries.');
  const revision = await digest([world, params.kind, entries]);
  ready();
  if (world !== game.world.id || user !== game.user || JSON.stringify(entries) !== JSON.stringify(get())) fail('ContentChanged', 'Authoring options changed; restart discovery.');
  if (params.cursor && params.cursor.revision !== revision) fail('ContentChanged', 'Options changed; discard continuation and restart.');
  const offset = params.cursor?.offset ?? 0;
  if (offset > entries.length) fail('InvalidCursor', 'Continuation offset exceeds the current list; restart.');
  const result = {kind: params.kind, world_id: world, revision, entries: [], total: entries.length, complete: false, next_cursor: null};
  const bytes = value => new TextEncoder().encode(JSON.stringify(value)).length;
  for (const entry of entries.slice(offset, offset + limit)) {
    const next = offset + result.entries.length + 1;
    const candidate = {...result, entries: [...result.entries, entry], complete: next === entries.length,
      next_cursor: next === entries.length ? null : {offset: next, revision}};
    if (bytes(candidate) > max) break;
    Object.assign(result, candidate);
  }
  if (!result.entries.length) {
    if (offset < entries.length) fail('ResponseTooLarge', 'Raise max_bytes for the next option.');
    result.complete = true;
  }
  return result;
}

/** Map bounded explicit format choices to safe CSS around this fragment only. */
export function formatJournalHTML(content, format) {
  if (format === undefined) return content;
  validateParams(format, ['font_family', 'font_size', 'custom_size_pt', 'font_color']);
  const styles = [];
  if (Object.hasOwn(format, 'font_family')) {
    if (typeof format.font_family !== 'string' || !journalFonts().includes(format.font_family)) fail('InvalidRequest', 'Choose an exact loaded font_family from get_journal_authoring_options.');
    // Quoted CSS strings cannot carry arbitrary declarations or HTML attributes.
    if (!/^[\p{L}\p{N} _-]{1,256}$/u.test(format.font_family)) fail('UnsupportedFont', 'This font name is outside the supported safe CSS subset.');
    styles.push(`font-family: '${format.font_family}'`);
  }
  if (Object.hasOwn(format, 'font_size')) {
    const sizes = {small: 10, normal: 12, large: 18, huge: 24};
    const size = format.font_size === 'custom' ? format.custom_size_pt : sizes[format.font_size];
    if (typeof size !== 'number' || !Number.isFinite(size) || size < 1 || size > 200) fail('InvalidRequest', 'Choose small/normal/large/huge/custom with custom_size_pt in1–200.');
    if (format.font_size !== 'custom' && Object.hasOwn(format, 'custom_size_pt')) fail('InvalidRequest', 'custom_size_pt requires font_size=custom.');
    styles.push(`font-size: ${size}pt`);
  } else if (Object.hasOwn(format, 'custom_size_pt')) fail('InvalidRequest', 'custom_size_pt requires font_size=custom.');
  if (Object.hasOwn(format, 'font_color')) {
    if (typeof format.font_color !== 'string' || !/^#[0-9a-fA-F]{6}$/.test(format.font_color)) fail('InvalidRequest', 'font_color must be #RRGGBB.');
    styles.push(`color: ${format.font_color}`);
  }
  return styles.length ? `<div style="${styles.join('; ')}">${content}</div>` : content;
}
