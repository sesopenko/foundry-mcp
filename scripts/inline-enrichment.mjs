/** Inspect detached enrichment results only, never Foundry sheet/UI DOM. */
export function isInlineEnrichment(source, container) {
  if (['@Check[', '@Damage[', '@Embed[', '[[/'].some(marker => container.innerHTML.includes(marker))) return false;
  return !!container.querySelector(source.startsWith('@Embed[') ? 'document-embed' : 'a');
}
