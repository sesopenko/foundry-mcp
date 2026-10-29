#!/usr/bin/env python3
"""Bounded read-only local WISH-003 comparison; prints counts, never game content.

Uses the private baseline produced during planning (rows: label/tool/arguments).
Only localhost MCP is accepted; credentials stay in .env.mcp. No model calls,
document mutations or automatic continuation loops. At most 40 calls and 300s.
The report contains aggregate sizes/errors only, not response payloads.
"""
import argparse
import asyncio
import json
from pathlib import Path
import time

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())


async def audit(baseline):
    cached = json.loads(Path(baseline).read_text())
    token = next(line.partition('=')[2].strip() for line in Path('.env.mcp').read_text().splitlines()
                 if line.partition('=')[0].strip() == 'FOUNDRY_MCP_CALLER_TOKEN')
    transport = StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp', headers={'Authorization': 'Bearer ' + token})
    allowed={'get_actor_types','get_actor_tree','list_actor_compendiums','get_journal_tree','list_pdf_documents','read_actor','list_actor_items','read_item','get_journal_contents','read_journal_page','search_journals','search_pdf_documents'}
    rows = [r for r in cached['rows'] if r['tool'] in allowed]
    caster = cached['census']['caster']['u']
    rows += [dict(label='selected_ac', tool='read_actor', arguments=dict(actor_uuid=caster, select=dict(details=['statistics.armor_class']))),
             dict(label='prepared', tool='read_actor', arguments=dict(actor_uuid=caster, select=dict(details=['spellcasting.prepared']))),
             dict(label='actor_identity', tool='read_actor', arguments=dict(actor_uuid=caster)),
             dict(label='capability_selected', tool='get_actor_types', arguments=dict(select=dict(actor_types=['npc'], actor_sections=['statistics'])))]
    originals={r['label']:r for r in cached['rows']}
    for label, selection in [
        ('item_melee_default',{'details':['source.attack','source.damage']}),
        ('owned_items_default',{'context':True,'relationships':True,'follow_up':True}),
        ('actor_packs_default',{'context':True,'follow_up':True,'limitations':True}),
        ('journal_contents_default',{'headings':True,'categories':True,'presentation':True,'folder_path':True}),
        ('journal_search_default',{'excerpts':True,'counts':True,'folder_path':True}),
        ('journal_page_default',{'references':True,'source_metadata':True,'folder_path':True}),
        ('pdf_search_default',{'snippet':True,'entries':True,'context':True}),
    ]:
        original=originals[label]
        rows.append(dict(label=label+'_expanded',tool=original['tool'],arguments=dict(original['arguments'],select=selection,max_bytes=48000)))
    rows.append(dict(label='ac_evidence',tool='read_actor',arguments=dict(actor_uuid=caster,select=dict(details=['statistics.armor_class'],evidence=True),max_bytes=48000)))
    assert len(rows) <= 40
    started = time.monotonic()
    report = []; calls=0; item_page=None
    async with asyncio.timeout(300), Client(transport, timeout=25, init_timeout=10) as client:
        catalog = await client.list_tools()
        for row in rows:
            result = await client.call_tool(row['tool'], row['arguments'], raise_on_error=False)
            calls+=1
            data = result.structured_content
            if row['label']=='owned_items_default' and not result.is_error:item_page=data
            text = ''.join(c.text for c in result.content if hasattr(c, 'text'))
            summary = dict(label=row['label'], tool=row['tool'], bytes=size(data) if data else len(text.encode()), error=result.is_error)
            if result.is_error: summary['message'] = text[:350]
            elif isinstance(data, dict):
                summary['complete'] = data.get('pagination', {}).get('complete', data.get('complete'))
                summary['entries'] = len(data.get('entries', data.get('nodes', data.get('matches', data.get('candidates', [])))))
            if 'structured_bytes' in row: summary['baseline_bytes'] = row['structured_bytes']
            report.append(summary)
        traversal={'complete':False,'pages':0,'entries':0,'bytes':0}
        if item_page:
            page=item_page
            for _ in range(6):
                traversal['pages']+=1;traversal['entries']+=len(page['nodes']);traversal['bytes']+=size(page)
                cursor=page['pagination']['next_cursor']
                if cursor is None:traversal['complete']=True;break
                if calls>=40:break
                response=await client.call_tool('list_actor_items',dict(originals['owned_items_default']['arguments'],cursor=cursor))
                calls+=1;page=response.structured_content
        return dict(calls=calls, discovery_calls=1, seconds=round(time.monotonic()-started, 3),
                    catalog_bytes=size([t.model_dump(mode='json') for t in catalog]), owned_item_traversal=traversal, rows=report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', help='Private planning audit JSON; never commit it.')
    args = parser.parse_args()
    print(json.dumps(asyncio.run(audit(args.baseline)), indent=2))
