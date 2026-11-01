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

test('text profiles exclude image authoring and immediate roll evaluation', () => {
  parsed('IMG', [['src', 'images/test.png']]); assert.throws(() => normalizeTextHTML('input', {links: true}), invalid);
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
