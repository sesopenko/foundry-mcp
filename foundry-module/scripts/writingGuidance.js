/** GM-authored HTML guidance, core14 world settings; no system-specific APIs.
 * Public ClientSettings.register/get/set/registerMenu and DialogV2:
 * https://foundryvtt.com/api/v14/classes/foundry.helpers.ClientSettings.html
 * Public HTMLProseMirrorElement.create/save/value (no editor internals):
 * https://foundryvtt.com/api/v14/classes/foundry.applications.elements.HTMLProseMirrorElement.html
 */
import {fail, validateParams} from './actorReadUtils.js';

const MODULE = 'foundry-mcp', KEY = 'writingGuidance', MAX_HTML_BYTES = 12000;
let saves = Promise.resolve();

function gmOnly() {
  if (!game.user?.isGM) fail('PermissionDenied', 'Writing guidance requires the connected GM.');
}
function ready() {
  if (!globalThis.game?.ready || !game.settings || !game.world?.id) fail('NotReady', 'Wait for the existing world to finish loading.');
  gmOnly();
  if (!String(game.version).startsWith('14.')) fail('UnsupportedVersion', 'Writing guidance requires Foundry14.');
}
function htmlValid(value) {
  return typeof value === 'string' && new TextEncoder().encode(value).length <= MAX_HTML_BYTES;
}
function savedAtValid(value) {
  return typeof value === 'string' && Number.isFinite(Date.parse(value)) && new Date(value).toISOString() === value;
}

/** Register shared world data without reconnecting the bridge on each edit.
 * Config is hidden; the GM-only menu provides the rich-text configuration UI.
 * World settings are readable by player clients, not a confidential store.
 */
export function registerWritingGuidanceSettings() {
  game.settings.register(MODULE, KEY, {scope: 'world', config: false, type: Object,
    default: {html: null, saved_at: null}});
}

/** GM-only read RPC. Null/null is never configured; an empty string is a saved
 * empty guide. Invalid/missing settings fail instead of silently dropping rules.
 */
export function getWritingGuidance(params = {}) {
  validateParams(params, []); ready();
  const value = game.settings.get(MODULE, KEY);
  if (!value || typeof value !== 'object' || Object.keys(value).sort().join(',') !== 'html,saved_at'
      || !(value.html === null && value.saved_at === null || htmlValid(value.html) && savedAtValid(value.saved_at))) {
    fail('ReadFailed', 'The stored writing guidance is invalid.', 'Have the GM inspect the module writing-guidance setting; do not treat unavailable rules as empty.');
  }
  return {world_id: game.world.id, html: value.html, saved_at: value.saved_at};
}

/** Configuration-only save, never exposed as an LLM RPC. Serialize saves in this
 * browser, advance timestamps on same-clock saves, and reject a stale UI snapshot.
 * ClientSettings has no distributed compare-and-swap; simultaneous GM clients
 * still follow Foundry's world-setting persistence semantics.
 */
export async function saveWritingGuidance(html, expected) {
  ready();
  if (!htmlValid(html)) fail('InvalidRequest', 'Writing guidance must be HTML text within 12000 UTF-8 bytes.');
  const context = {world: game.world.id, user: game.user, settings: game.settings};
  const save = saves.then(async () => {
    ready();
    if (game.world.id !== context.world || game.user !== context.user || game.settings !== context.settings) fail('ContextChanged', 'World or GM changed before saving; reopen writing guidance.');
    const previous = getWritingGuidance();
    if (expected !== undefined && JSON.stringify(previous) !== JSON.stringify(expected)) fail('ContentChanged', 'Writing guidance changed while this editor was open.', 'Close and reopen the editor before applying your changes.');
    const milliseconds = Math.max(Date.now(), previous.saved_at === null ? 0 : Date.parse(previous.saved_at) + 1);
    await game.settings.set(MODULE, KEY, {html, saved_at: new Date(milliseconds).toISOString()});
    ready();
    if (game.world.id !== context.world || game.user !== context.user) fail('ContextChanged', 'World or GM changed while saving; verify the saved setting in its original world.');
    return getWritingGuidance();
  });
  saves = save.catch(() => {});
  return save;
}

/** Register a public settings submenu using only our own content's DOM.
 * Constructor/render/save all check GM access; no Foundry sheet DOM is queried.
 */
export function registerWritingGuidanceMenu() {
  gmOnly();
  class WritingGuidanceConfig extends foundry.applications.api.DialogV2 {
    constructor(options = {}) {
      const initial = getWritingGuidance();
      super({...options, window: {title: 'LLM writing guidance (GM)'}, content:
        '<section data-writing-guidance><p>Set instructions the LLM must follow, including official adventure folders it must not edit without your permission. This world setting is not confidential from player clients.</p>' +
        '<div data-guidance-editor></div><p data-guidance-status role="status"></p><button type="button" data-guidance-save>Save writing guidance</button></section>',
        buttons: [{action: 'close', label: 'Close'}]});
      this.guidanceSnapshot = initial;
    }
  }
  Hooks.on('renderWritingGuidanceConfig', (application, element) => {
    ready();
    const root = element.querySelector('[data-writing-guidance]');
    if (!root) return;
    const editor = foundry.applications.elements.HTMLProseMirrorElement.create({name: 'guidance', value: application.guidanceSnapshot.html ?? '',
      collaborate: false, documentUUID: '', toggled: false, height: 320});
    root.querySelector('[data-guidance-editor]').replaceChildren(editor);
    const status = root.querySelector('[data-guidance-status]'), button = root.querySelector('[data-guidance-save]');
    status.textContent = application.guidanceSnapshot.saved_at ? 'Last saved: ' + application.guidanceSnapshot.saved_at : 'No guidance has been saved.';
    button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        ready(); editor.save();
        application.guidanceSnapshot = await saveWritingGuidance(editor.value, application.guidanceSnapshot);
        status.textContent = 'Saved: ' + application.guidanceSnapshot.saved_at;
      } catch (error) {status.textContent = error.message;}
      finally {button.disabled = false;}
    });
  });
  game.settings.registerMenu(MODULE, KEY, {name: 'LLM writing guidance', label: 'Edit writing guidance',
    hint: 'Set persistent GM instructions for LLM content authoring, including protected official journals.',
    icon: 'fas fa-pen', type: WritingGuidanceConfig, restricted: true});
}
