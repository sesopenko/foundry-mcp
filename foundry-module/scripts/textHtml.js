/** Basic text HTML validation shared by authoring destinations. Standard browser
 * DOMParser/URL only; no enrichment, rolls or private Foundry editor APIs.
 * Foundry HTMLField may further sanitize persisted document content.
 */
import {fail} from './actorReadUtils.js';

const TAGS = new Set(['P','BR','H1','H2','H3','H4','H5','H6','DIV','SPAN','STRONG','B','EM','I','U','S','SUB','SUP','BLOCKQUOTE','PRE','CODE','UL','OL','LI','TABLE','CAPTION','COLGROUP','COL','THEAD','TBODY','TFOOT','TR','TH','TD','HR']);
const CHAT_STYLE = /^\s*(text-align|font-size|font-family|font-weight|font-style|text-decoration|color|background-color)\s*:\s*[a-zA-Z0-9 #.,%()"'-]+$/;
const JOURNAL_STYLE = /^\s*(text-align|font-size|font-family|font-weight|font-style|text-decoration|color|background-color)\s*:\s*[\p{L}\p{N} _#.,%()"'-]+$/u;
const JOURNAL_TAGS = new Set([...TAGS, 'A', 'IMG', 'SECTION', 'ASIDE', 'ARTICLE', 'HEADER', 'FOOTER', 'FIGURE', 'FIGCAPTION', 'DL', 'DT', 'DD', 'MARK', 'SMALL', 'ABBR']);
const LAYOUT_PROPERTIES = new Set(['position', 'top', 'right', 'bottom', 'left', 'width', 'height', 'min-width', 'max-width', 'min-height', 'max-height', 'margin', 'margin-top', 'margin-right', 'margin-bottom', 'margin-left', 'padding', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left', 'float', 'clear', 'display', 'vertical-align', 'border', 'border-width', 'border-style', 'border-color', 'border-radius', 'opacity', 'object-fit', 'text-indent', 'line-height']);

/** Passive image URL policy: HTTP(S) or relative assets, including spaces.
 * No fetch, asset-membership or existence claim is made by raw HTML authoring.
 */
function safeImageURL(value) {
  if (!value.trim() || value.length > 2048 || /[\x00-\x1f\x7f\\]/.test(value)) return false;
  try {return ['http:', 'https:'].includes(new URL(value, 'https://example.invalid/').protocol);}
  catch {return false;}
}

function journalStyle(part) {
  const colon = part.indexOf(':');
  if (colon < 0) return false;
  const property = part.slice(0, colon).trim().toLowerCase(), value = part.slice(colon + 1).trim();
  if (property === 'shape-outside') {
    const url = /^url\((?:'([^'\\]*)'|"([^"\\]*)"|([^\s'"()\\]+))\)$/i.exec(value);
    return url !== null && safeImageURL(url[1] ?? url[2] ?? url[3]);
  }
  if (property === 'transform') return /^(?:scale(?:X|Y)?\(\s*-?\d+(?:\.\d+)?(?:\s*,\s*-?\d+(?:\.\d+)?)?\s*\)\s*)+$/i.test(value);
  if (LAYOUT_PROPERTIES.has(property)) return /^[a-zA-Z0-9 #.,%+\-]+$/.test(value);
  if (!JOURNAL_STYLE.test(part) || /url|expression|var\(/i.test(part)) return false;
  if (property !== 'font-size') return true;
  const match = /^(\d+(?:\.\d+)?)pt$/.exec(value);
  return match !== null && Number(match[1]) >= 1 && Number(match[1]) <= 200;
}

/** Journal presentation attributes are independent of chat's text subset.
 * Classes are passive CSS tokens, not a publisher-specific name allowlist.
 * Only the observed split metadata is admitted; action/command data is not.
 */
function journalAttribute(tag, name, value) {
  if (name === 'class') return value.length <= 1024 && /^(?:[a-zA-Z_][\w-]*)(?:\s+[a-zA-Z_][\w-]*)*\s*$/.test(value);
  if (name === 'id') return /^[a-zA-Z_][\w:.-]{0,255}$/.test(value);
  if (name === 'title') return value.length <= 512;
  if (name === 'data-split-here') return value.length <= 256 && !/[\x00-\x1f\x7f]/.test(value);
  if (tag !== 'IMG') return false;
  if (name === 'src') return safeImageURL(value);
  if (name === 'alt') return value.length <= 1000;
  return ['width', 'height'].includes(name) && /^(?:[1-9]\d{0,3})$/.test(value) && Number(value) <= 8192;
}

function safeLink(value) {
  if (/[\x00-\x20\x7f]/.test(value) || value.length > 2048) return false;
  try {return ['http:', 'https:', 'mailto:'].includes(new URL(value, 'https://example.invalid/').protocol);}
  catch {return false;}
}

/** Normalize authoring HTML. links=true selects journal presentation HTML:
 * semantic blocks, CSS classes, passive images and bounded layout styles.
 * The default retains chat's existing tag/style/attribute restrictions.
 * Neither profile permits executable HTML or immediate inline rolls.
 */
export function normalizeTextHTML(content, {links = false} = {}) {
  const doc = new DOMParser().parseFromString(content, 'text/html');
  for (const el of doc.querySelectorAll('*')) {
    const wrapper = ['HTML', 'HEAD', 'BODY'].includes(el.tagName);
    if (!wrapper && !(links ? JOURNAL_TAGS : TAGS).has(el.tagName)) fail('InvalidHTML', 'Unsupported HTML element; scripts, active embeds and forms are not accepted. Chat also excludes images and links.');
    for (const attribute of el.attributes) {
      const {name, value} = attribute;
      const span = ['TH', 'TD'].includes(el.tagName) && ['colspan', 'rowspan'].includes(name) && /^(?:[1-9]|[1-9]\d|100)$/.test(value);
      const style = name === 'style' && value.split(';').every(part => !part.trim()
        || (links ? journalStyle(part) : CHAT_STYLE.test(part) && !/url|expression|var\(/i.test(part)));
      const link = links && el.tagName === 'A' && (name === 'href' && safeLink(value) || name === 'title' && value.length <= 512);
      const presentation = links && journalAttribute(el.tagName, name, value);
      if (wrapper || !(span || style || link || presentation)) fail('InvalidHTML', 'Unsupported HTML attribute, URL or style. Journals accept presentation classes, safe image URLs and data-split-here; event handlers and other data attributes are rejected.');
    }
  }
  if (/\[\[(?!\/(?:r|gmr|br|sr)\s)/.test(doc.body.textContent ?? '')) fail('InvalidHTML', 'Only deferred inline rolls from create_pf2e_inline_roll are accepted; immediate rolls can evaluate while rendering.');
  return doc.body.innerHTML;
}
