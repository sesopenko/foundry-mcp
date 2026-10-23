# Recorded feat selections — PF2e8.6.1

The [persisted source flag schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/system.ts)
permits `rulesSelections` values that are strings, numbers or arbitrary objects.
The selected-source reader admits only exact string and finite-number leaves.
Opaque map keys, including empty keys, retain JSON Pointer escaping. Missing or
undefined maps and empty maps remain distinct; no defaults are reconstructed.

The map bound is12000 keys. Malformed root maps return ReadFailed. Unsupported
object, array, boolean, null and other values are withheld, without recursively
reading their contents or inventing absent source rows. The source section is
partial with reason `unsupported_selection_values` whenever such values exist.
Supported scalar rows are `feat_recorded_selection` with mapping
`pf2e.feat.source.v1` and limitation `feat_source_not_effective_benefit`.
The root missing/empty marker uses `feat_selection_entries`.

Recorded values never establish acquisition, eligibility, selected active benefits
or UUID identity. No arbitrary flags or rule execution are authorized by this
allowlist. Integrated acquired-document joins are provided separately by the
[character Build view](build-contract.md).
Deterministic tests cover malformed/unsupported values, provenance, escaped keys,
source pagination and privacy. Existing compendium fixtures cover missing maps;
populated owned scalar selections were subsequently checked through actual MCP
in the [Build verification](build-verification.md).
