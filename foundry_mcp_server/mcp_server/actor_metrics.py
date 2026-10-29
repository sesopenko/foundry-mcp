"""PF2e-specific character runtime metric validation, PF2e8.6.1/core14.369.

Scoped API-evidence exception, 2026-10-28; current getter values, never source.
Upstream: https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/inventory
"""
REASONS = {'missing_api', 'invalid_value', 'getter_failed', 'items_denied',
           'item_limit', 'dependency_unavailable', 'inconsistent_value'}
FIELDS = {
    'wealth': {'total_currency': 'cp', 'total_wealth': 'cp', 'non_currency_value': 'cp'},
    'bulk': {'carried_bulk': 'light_bulk', 'encumbered_after': 'bulk',
             'maximum_bulk': 'bulk', 'is_encumbered': None, 'is_over_max': None,
             'until_encumbered': 'light_bulk'},
}


def metric_record(row, identity):
    """Validate PF2e-specific detached getter witnesses, including absence."""
    if identity['document_name'] != 'Actor' or identity['type'] != 'character': return False
    if set(row) != {'key','section','kind','raw','mapped','provenance'} or row['kind'] != 'field' or row['raw'] != []: return False
    if row['provenance'] != dict(contributors=[], mapping='pf2e.actor.inventory-metrics.v1', limitations=['version_specific_guarded_runtime_getters']): return False
    mapped=row['mapped']
    if type(mapped) is not dict or set(mapped) != {'concept','value','unit'}: return False
    concept=mapped['concept']; section=row['section']; key=row['key']
    if key.startswith(section+':summary:'):
        fields=FIELDS[section]
        if key != section+':summary:'+concept: return False
    elif key == section+':items:item_count':
        fields={'item_count':None}
    elif key.startswith(section+':item:'):
        item_uuid=key[len(section+':item:'):].rsplit(':',1)[0]
        if not item_uuid.startswith(identity['uuid']+'.Item.') or not item_uuid[len(identity['uuid']+'.Item.'):].isalnum(): return False
        fields={'item_uuid':None, 'item_name':None, 'quantity':None, **({'asset_value':'cp'} if section=='wealth' else {'item_bulk':'light_bulk'})}
        if key != section+':item:'+item_uuid+':'+concept: return False
    else: return False
    if concept not in fields or mapped['unit'] != fields[concept]: return False
    reading=mapped['value']
    if type(reading) is not dict: return False
    if reading.get('availability')=='potentially_missing':
        return set(reading)=={'availability','value','reason'} and reading['value'] is None and reading['reason'] in REASONS
    if set(reading)!={'availability','value'} or reading['availability']!='available': return False
    value=reading['value']
    if concept in ('is_encumbered','is_over_max'): return type(value) is bool
    if concept=='item_name': return type(value) is str and len(value)<=256
    if concept=='item_uuid': return value==item_uuid
    return type(value) is int and 0<=value<=9007199254740991


def metric_section(records, section, identity):
    """PF2e-specific missing values cannot advertise a complete section."""
    rows=[r for r in records if r['section']==section['name']]
    if identity['type']!='character': return not rows and section==dict(name=section['name'],status='unsupported',reasons=['character_only'])
    if not set(section['reasons']) <= {'pagination','potentially_missing'}: return False
    if section['status'] != ('partial' if section['reasons'] else 'complete'): return False
    return not any(r['mapped']['value']['availability']=='potentially_missing' for r in rows) or 'potentially_missing' in section['reasons']
