import test from 'node:test';
import assert from 'node:assert/strict';
import {normalizeTextHTML} from '../../foundry-module/scripts/textHtml.js';
import {normalizeChatHTML} from '../../foundry-module/scripts/chat.js';

function parsed(tag, attributes = []) {
  globalThis.DOMParser = class {parseFromString() {return {
    querySelectorAll: () => [{tagName: tag, attributes: attributes.map(([name, value]) => ({name, value}))}],
    body: {innerHTML: '<p>normalized</p>', textContent: 'Text'}
  };}};
}
const invalid = error => error.rpcError?.code === 'InvalidHTML';

test('journal accepts publisher heading and read-aloud classes independently', () => {
  for (const [tag, value] of [['H2', 'no-toc'], ['P', 'read-aloud']]) {
    parsed(tag, [['class', value]]);
    assert.equal(normalizeTextHTML('input', {links: true}), '<p>normalized</p>');
  }
});

test('publisher classes do not admit executable attributes or chat markup', () => {
  for (const [tag, value] of [['H2', 'no-toc'], ['P', 'read-aloud']]) {
    parsed(tag, [['class', value]]);
    assert.throws(() => normalizeChatHTML('input'), invalid);
    for (const extra of [['onclick', 'run()'], ['data-action', 'run']]) {
      parsed(tag, [['class', value], extra]);
      assert.throws(() => normalizeTextHTML('input', {links: true}), invalid);
    }
  }
  for (const [tag, value] of [['P', 'bad<class'], ['P', 'bad\\class'], ['SCRIPT', 'read-aloud']]) {
    parsed(tag, [['class', value]]);
    assert.throws(() => normalizeTextHTML('input', {links: true}), invalid);
  }
});

// Structural witnesses from the read-only 18-page Seven Dooms sample; no
// adventure prose/assets are needed to reproduce the policy mismatch.
for (const [tag, attributes] of [
  ['H2', [['class', 'split no-toc no-toc']]],
  ['DIV', [['class', 'read-aloud']]],
  ['SECTION', [['class', 'encounter']]],
  ['ASIDE', [['class', 'sidebar float-right']]],
  ['SECTION', [['class', 'handout handout1']]],
  ['UL', [['class', 'traits']]], ['LI', [['class', 'trait rare']]],
  ['P', [['class', 'no-indent']]], ['SPAN', [['class', 'pf2-icon']]],
  ['H2', [['data-split-here', 'Standard Backgrounds']]],
  ['IMG', [['class', 'float-right'], ['src', 'modules/example/assets/Room Art.webp'], ['alt', 'Room'], ['title', 'Room'],
    ['style', "shape-outside:url('modules/example/assets/Room Art.webp')"]]],
  ['IMG', [['src', 'modules/example/logo.svg'], ['style', 'transform: scale(1.5)']]],
  ['IMG', [['src', 'modules/example/logo.webp'], ['style', "shape-outside:url('modules/example/logo.webp');position:absolute;top:280px;left:15%;width:70%"]]],
]) {
  test('journal publisher structure: ' + tag + ' ' + JSON.stringify(attributes), () => {
    parsed(tag, attributes);
    assert.equal(normalizeTextHTML('input', {links: true}), '<p>normalized</p>');
    assert.throws(() => normalizeChatHTML('input'), invalid);
  });
}

test('publisher support rejects active tags, unsafe images, CSS and unknown data attributes', () => {
  for (const tag of ['SCRIPT', 'IFRAME', 'OBJECT', 'EMBED', 'SVG', 'MATH', 'STYLE', 'LINK', 'FORM', 'INPUT']) {
    parsed(tag); assert.throws(() => normalizeTextHTML('input', {links: true}), invalid);
  }
  for (const src of ['javascript:alert(1)', 'data:image/svg+xml,test', 'file:///tmp/a.png', 'blob:https://example.org/x', 'java\nscript:run()']) {
    parsed('IMG', [['src', src]]); assert.throws(() => normalizeTextHTML('input', {links: true}), invalid);
  }
  for (const style of ['shape-outside:url(javascript:run())', 'shape-outside:url("data:image/svg+xml,test")',
    'shape-outside:url("ok.webp") url("other.webp")', 'transform:expression(run())',
    'background-image:url(https://example.org/x)', 'position:absolute;behavior:url(x)',
    'width:var(--x)', 'width:e\\78pression(x)', 'width:1px!important', 'width:/*x*/1px']) {
    parsed('IMG', [['style', style]]); assert.throws(() => normalizeTextHTML('input', {links: true}), invalid);
  }
  for (const attr of [['onerror', 'run()'], ['srcset', 'javascript:run()'], ['data-action', 'run'], ['data-command', 'run'], ['xmlns', 'x']]) {
    parsed('IMG', [attr]); assert.throws(() => normalizeTextHTML('input', {links: true}), invalid);
  }
});

test('journal link support preserves chat exclusions', () => {
  for (const href of ['https://example.org/path', 'http://example.org', 'mailto:gm@example.org', '#chapter', '/journals/handout']) {
    parsed('A', [['href', href], ['title', 'A reference']]);
    assert.equal(normalizeTextHTML('input', {links: true}), '<p>normalized</p>');
    assert.throws(() => normalizeChatHTML('input'), invalid);
  }
});

test('links reject executable URLs, control characters and unknown attributes', () => {
  for (const href of ['javascript:alert(1)', 'data:text/html,test', 'vbscript:test', 'java\tscript:alert(1)']) {
    parsed('A', [['href', href]]); assert.throws(() => normalizeTextHTML('input', {links: true}), invalid);
  }
  parsed('A', [['onclick', 'run()']]); assert.throws(() => normalizeTextHTML('input', {links: true}), invalid);
});

test('journal styling permits Unicode font names and ordinary formatting; chat profile remains stable', () => {
  parsed('SPAN', [['style', 'font-family:文字;font-size:18pt;color:#254c84']]);
  assert.equal(normalizeTextHTML('input', {links: true}), '<p>normalized</p>');
  assert.throws(() => normalizeChatHTML('input'), invalid);
  for (const tag of ['UL', 'OL', 'LI', 'HR', 'H2', 'TABLE', 'STRONG']) {
    parsed(tag); assert.equal(normalizeTextHTML('input', {links: true}), '<p>normalized</p>');
  }
  for (const style of ['background-image:url(x)', 'color:expression(x)', '--custom:1', 'font-size:var(--size)']) {
    parsed('P', [['style', style]]); assert.throws(() => normalizeTextHTML('input', {links: true}), invalid);
  }
});

test('chat excludes images and both profiles exclude immediate roll evaluation', () => {
  parsed('IMG', [['src', 'images/test.png']]); assert.throws(() => normalizeChatHTML('input'), invalid);
  globalThis.DOMParser = class {parseFromString() {return {querySelectorAll: () => [], body: {innerHTML: '[[1d6]]', textContent: '[[1d6]]'}};}};
  assert.throws(() => normalizeTextHTML('[[1d6]]', {links: true}), invalid);
});

test('raw journal HTML cannot bypass the bounded custom point size contract', () => {
  for (const size of ['0pt', '-1pt', '201pt', '1000000px', 'Infinitypt']) {
    parsed('SPAN', [['style', 'font-size:' + size]]);
    assert.throws(() => normalizeTextHTML('input', {links: true}), invalid);
  }
  for (const size of ['1pt', '14.5pt', '200pt']) {
    parsed('SPAN', [['style', 'font-size:' + size]]);
    assert.equal(normalizeTextHTML('input', {links: true}), '<p>normalized</p>');
  }
  parsed('SPAN', [['style', 'font-size:300px']]);
  assert.equal(normalizeChatHTML('input'), '<p>normalized</p>');
});
