import test from 'node:test';
import assert from 'node:assert/strict';
import { isInlineEnrichment } from '../../scripts/inline-enrichment.mjs';

// Regression fixture from public TextEditor.implementation.enrichHTML on
// Foundry14.369: an Item embed is a custom element, not an anchor/div/section.
const container = tag => ({innerHTML:`<${tag}></${tag}>`,querySelector:selectors=>selectors.split(',').includes(tag)?{}:null});
test('public detached Item embeds count as enriched markup',()=>{
  assert.equal(isInlineEnrichment('@Embed[Compendium.pf2e.feats-srd.Item.abcdefghijklmnop inline]',container('document-embed')),true);
});
test('deferred rolls/checks and unprocessed source are distinguished',()=>{
  assert.equal(isInlineEnrichment('[[/r 1d20]]',container('a')),true);
  assert.equal(isInlineEnrichment('@Check[reflex|dc:20]',container('a')),true);
  assert.equal(isInlineEnrichment('@Check[flat]',{innerHTML:'@Check[flat]',querySelector:()=>({})}),false);
});
