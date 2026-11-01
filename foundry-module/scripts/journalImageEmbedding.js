/** Text-page image insertion using standard browser APIs only.
 * Core14 persistence remains in journalAuthoring.js. No Foundry UI/sheet DOM.
 */
import {fail, validateParams, integer} from './actorReadUtils.js';
import {validateJournalImageSelector, resolveJournalImage} from './journalImages.js';

const TAGS = ['p','div','h1','h2','h3','h4','h5','h6','blockquote','pre','ul','ol','li','table'];
const escape = value => value.replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));

export function validateImageInsertion(action) {
  validateJournalImageSelector(action.image);
  if (typeof action.alt !== 'string' || [...action.alt].length > 1000 || /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(action.alt)) fail('InvalidRequest', 'alt is required, up to1000 Unicode characters; empty is allowed for decorative images.');
  for (const key of ['width', 'height']) if (Object.hasOwn(action, key)) integer(action[key], undefined, 1, 8192, key);
  const position = action.position ?? 'append';
  if (!['append','prepend','before','after'].includes(position)) fail('InvalidRequest', 'Choose append/prepend/before/after image position.');
  if (['before','after'].includes(position)) {
    validateParams(action.anchor, ['tag', 'text']);
    if (!TAGS.includes(action.anchor.tag) || typeof action.anchor.text !== 'string' || !action.anchor.text || [...action.anchor.text].length > 2000) fail('InvalidRequest', 'An anchored insertion requires a supported block tag and exact text up to2000 characters.');
  } else if (Object.hasOwn(action, 'anchor')) fail('InvalidRequest', 'anchor requires position=before or after.');
}

/** Confirm this browser can load the selected asset, with a5s deadline. The
 * browser may cache/load its body; no bytes are returned to the LLM. Player
 * access remains independent of this GM check and document ownership.
 */
export async function verifyJournalImage(image) {
  const selected = await resolveJournalImage(image);
  await new Promise((resolve, reject) => {
    const element = new Image();
    const finish = okay => {
      clearTimeout(timer); element.onload = element.onerror = null;
      if (!okay) element.src = '';
      okay ? resolve() : reject(Object.assign(new Error('ImageUnavailable'), {rpcError: {code: 'ImageUnavailable', message: 'The selected image could not be loaded by the GM within5 seconds; choose another accessible source.'}}));
    };
    const timer = setTimeout(() => finish(false), 5000);
    element.onload = () => finish(element.naturalWidth > 0 && element.naturalHeight > 0);
    element.onerror = () => finish(false);
    element.src = selected.src;
  });
  return selected;
}

/** Append/prepend preserves original HTML bytes. Anchored insertion uses a
 * detached DOM and serializes it, preserving content but normalizing markup.
 * No existing content is enriched, evaluated or re-sanitized here.
 */
export function insertJournalImage(source, action) {
  validateImageInsertion(action);
  const attributes = [`src="${escape(action.image.src)}"`, `alt="${escape(action.alt)}"`];
  for (const key of ['width', 'height']) if (Object.hasOwn(action, key)) attributes.push(`${key}="${action[key]}"`);
  const html = '<img ' + attributes.join(' ') + '>', position = action.position ?? 'append';
  if (position === 'append') return source + html;
  if (position === 'prepend') return html + source;
  const doc = new DOMParser().parseFromString(source, 'text/html');
  const matches = [...doc.body.querySelectorAll(action.anchor.tag)].filter(element => element.textContent === action.anchor.text);
  if (!matches.length) fail('AnchorNotFound', 'No block matches the exact tag/text; reread the page and choose a current anchor.');
  if (matches.length !== 1) fail('AmbiguousAnchor', 'Multiple blocks match; choose a unique block or append/prepend.');
  matches[0].insertAdjacentHTML(position === 'before' ? 'beforebegin' : 'afterend', html);
  return doc.body.innerHTML;
}
