/** Basic text HTML validation shared by authoring destinations. Standard browser
 * DOMParser/URL only; no enrichment, rolls or private Foundry editor APIs.
 * Foundry HTMLField may further sanitize persisted document content.
 */
import {fail} from './actorReadUtils.js';

const TAGS = new Set(['P','BR','H1','H2','H3','H4','H5','H6','DIV','SPAN','STRONG','B','EM','I','U','S','SUB','SUP','BLOCKQUOTE','PRE','CODE','UL','OL','LI','TABLE','CAPTION','COLGROUP','COL','THEAD','TBODY','TFOOT','TR','TH','TD','HR']);
const CHAT_STYLE = /^\s*(text-align|font-size|font-family|font-weight|font-style|text-decoration|color|background-color)\s*:\s*[a-zA-Z0-9 #.,%()"'-]+$/;
const JOURNAL_STYLE = /^\s*(text-align|font-size|font-family|font-weight|font-style|text-decoration|color|background-color)\s*:\s*[\p{L}\p{N} _#.,%()"'-]+$/u;

function journalStyle(part) {
  if (!JOURNAL_STYLE.test(part)) return false;
  const [property, value] = part.split(':').map(value => value.trim());
  if (property !== 'font-size') return true;
  const match = /^(\d+(?:\.\d+)?)pt$/.exec(value);
  return match !== null && Number(match[1]) >= 1 && Number(match[1]) <= 200;
}

function safeLink(value) {
  if (/[\x00-\x20\x7f]/.test(value) || value.length > 2048) return false;
  try {return ['http:', 'https:', 'mailto:'].includes(new URL(value, 'https://example.invalid/').protocol);}
  catch {return false;}
}

/** Normalize the common text subset. links=true is the journal profile;
 * default retains chat's existing tag/style restrictions. Images remain outside
 * both profiles until the separate image-authoring feature is implemented.
 */
export function normalizeTextHTML(content, {links = false} = {}) {
  const doc = new DOMParser().parseFromString(content, 'text/html');
  for (const el of doc.querySelectorAll('*')) {
    const wrapper = ['HTML', 'HEAD', 'BODY'].includes(el.tagName);
    if (!wrapper && !TAGS.has(el.tagName) && !(links && el.tagName === 'A')) fail('InvalidHTML', 'Use supported text HTML; this destination excludes images and executable HTML.');
    for (const attribute of el.attributes) {
      const {name, value} = attribute;
      const span = ['TH', 'TD'].includes(el.tagName) && ['colspan', 'rowspan'].includes(name) && /^(?:[1-9]|[1-9]\d|100)$/.test(value);
      const style = name === 'style' && value.split(';').every(part => !part.trim()
        || (links ? journalStyle(part) : CHAT_STYLE.test(part)) && !/url|expression|var\(/i.test(part));
      const link = links && el.tagName === 'A' && (name === 'href' && safeLink(value) || name === 'title' && value.length <= 512);
      if (wrapper || !(span || style || link)) fail('InvalidHTML', 'Unsupported text attribute, link or style; no event/class/data attributes.');
    }
  }
  if (/\[\[(?!\/(?:r|gmr|br|sr)\s)/.test(doc.body.textContent ?? '')) fail('InvalidHTML', 'Only deferred inline rolls from create_pf2e_inline_roll are accepted; immediate rolls can evaluate while rendering.');
  return doc.body.innerHTML;
}
