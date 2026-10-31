"""Bounded read-only WISH-009 audit of existing localhost test world.

Baseline: existing catalog and Actor/Item lookup/read defaults and expansions.
Candidate: same scenarios plus compendium page discovery, complete source
reconstruction, related-source follow-up and preparation. No model calls,
imports, mutations, rolls, chat, enrichment or credential output. 60 calls/300s
maximum per phase; individual gameplay paths have 8-call/120-second targets.
"""
import argparse
import asyncio
import json
from pathlib import Path
import time
import hashlib
import subprocess

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

ROOT = Path(__file__).resolve().parents[1]


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())


async def audit(client, candidate):
    calls = 0
    rows = []
    started = time.monotonic()

    async def call(tool, args, label):
        nonlocal calls
        assert calls < 60, 'Call cap'
        calls += 1
        t = time.monotonic()
        response = await client.call_tool(tool, args, meta={'evaluation': {'run_id': 'wish009-candidate' if candidate else 'wish009-baseline', 'task_id': label, 'attempt_id': 'deterministic'}})
        data = response.structured_content
        rows.append(dict(label=label, tool=tool, bytes=size(data), mcp_bytes=size({'content': [b.model_dump(mode='json') for b in response.content], 'structuredContent': data}), seconds=round(time.monotonic()-t, 3), complete=data.get('pagination', {}).get('complete', data.get('complete'))))
        return data

    catalog = await client.list_tools(); calls += 1
    catalog_bytes = size([t.model_dump(mode='json') for t in catalog])
    before = await call('execute_javascript', {'code': """
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369'||game.system.id!=='pf2e'||game.system.version!=='8.6.1')throw Error('Wrong runtime');
return JSON.stringify({core:game.version,system:game.system.version,messages:game.messages.size,journals:game.journal.size,items:game.items.size,actors:game.actors.size});
"""}, 'setup')
    before = json.loads(before['value'])
    identities = {}
    source_checks = {}
    paths = []
    for kind, term, pack_query, types in [('Item', 'Treat Wounds', 'Actions', ['action']), ('Item', 'Fireball', 'Spells', ['spell']), ('Actor', 'Goblin Warrior', 'Monster Core', ['npc'])]:
        path_start, path_calls = time.monotonic(), calls
        listed = await call('list_actor_compendiums', {'document_type': kind, 'query': pack_query}, term)
        assert listed['nodes'] and listed['pagination']['complete']
        found = await call('search_compendium_actors', {'pack_ids': [p['id'] for p in listed['nodes']][:10], 'query': term, 'document_type': kind, 'types': types}, term)
        match = next(n for n in found['nodes'] if n['identity']['name'].lower() == term.lower())
        identities[term] = match['identity']['uuid']
        reader, selector = ('read_actor', 'actor_uuid') if kind == 'Actor' else ('read_item', 'item_uuid')
        await call(reader, {selector: identities[term]}, term + '-identity')
        args = {selector: identities[term], 'select': {'details': ['source', 'description'] if kind == 'Item' else ['statistics', 'abilities']}, 'max_bytes': 48000, 'limit': 100}
        result = await call(reader, args, term + '-rules')
        values = []
        for _ in range(5):
            values.extend(v for e in result['entries'] for v in e['values'])
            if result['pagination']['complete']:
                break
            result = await call(reader, dict(args, cursor=result['pagination']['next_cursor']), term + '-rules')
        assert result['pagination']['complete']
        if term == 'Fireball':
            concepts = {v['concept']: v['value'] for v in values}
            assert concepts['spell_range_text'] == '500 feet'
            assert concepts['spell_base_rank'] == 3
            source_checks['fireball_range_rank'] = True
        elif term == 'Treat Wounds':
            content = ''.join(v['value'] for v in values if isinstance(v['value'], str) and v.get('text'))
            assert '10 minutes' in content and 'wounded' in content.lower() and 'hour' in content.lower()
            source_checks['treat_wounds_complete_prose'] = True
        paths.append(dict(task=term, calls=calls-path_calls, seconds=round(time.monotonic()-path_start, 3), complete=True))

    if candidate:
        path_start, path_calls = time.monotonic(), calls
        packs = await call('list_compendiums', {'document_type': 'JournalEntry', 'query': 'journals'}, 'DCs by Level')
        assert packs['pagination']['complete']
        # Select by advertised title; no hard-coded pack/document IDs.
        assert len(packs['nodes']) == 1
        selected = packs['nodes'][0]
        pack_id = selected['id']
        results = await call('search_compendium_journals', {'pack_id': pack_id, 'query': 'DCs by Level'}, 'DCs by Level')
        assert results['complete'] and not results['failures']
        match = next(m for m in results['matches'] if m['page_name'] == 'DCs by Level')

        async def page(match, label, **extra):
            args = {'pack_id': pack_id, 'page_uuid': match['page_uuid'], **extra}
            pieces = []; end = 0
            for _ in range(10):
                data = await call('read_compendium_journal_page', args, label)
                assert data['offset'] == end
                end = data['end_offset']; pieces.append(data['content'])
                if data['complete']:
                    assert end == data['total_chars']
                    return ''.join(pieces), data
                args['cursor'] = data['next_cursor']
            raise AssertionError('Page continuation cap')

        html, data = await page(match, 'DCs by Level')
        assert '<table' in html and '>5<' in html and '>20<' in html
        assert '<th>Spell Rank*</th>' in html
        assert '* If a spell is uncommon or rare, adjust its difficulty accordingly.' in html
        source_checks['dc_level_tables_footnote'] = True
        paths.append(dict(task='DCs by Level', calls=calls-path_calls, seconds=round(time.monotonic()-path_start, 3), complete=True))
        # Reused identity with small fragments verifies full reconstruction.
        again, _ = await page(match, 'preparation-fragments', max_chars=600)
        assert again == html
        adjustment = await call('search_compendium_journals', {'pack_id': pack_id, 'journal_id': match['journal_id'], 'query': 'DC Adjustments'}, 'preparation-follow-up')
        adjust = next(m for m in adjustment['matches'] if m['page_name'] == 'DC Adjustments')
        adjustment_html, _ = await page(adjust, 'preparation-follow-up')
        assert 'Hard' in adjustment_html and '+2' in adjustment_html
        source_checks['separate_hard_adjustment'] = True
        contents_args = {'pack_id': pack_id, 'journal_id': match['journal_id']}
        contents = await call('get_compendium_journal_contents', contents_args, 'contents-default')
        page_ids = [p['page_uuid'] for p in contents['pages']]
        for _ in range(9):
            if contents['complete']:
                break
            contents = await call('get_compendium_journal_contents', dict(contents_args, cursor=contents['next_cursor']), 'contents-default-continuation')
            page_ids.extend(p['page_uuid'] for p in contents['pages'])
        assert contents['complete'] and len(set(page_ids)) == len(page_ids) == contents['total']
        source_checks['complete_entry_navigation'] = True
        await call('get_compendium_journal_contents', {'pack_id': pack_id, 'journal_id': match['journal_id'], 'select': {'headings': True, 'categories': True, 'presentation': True}, 'max_bytes': 48000}, 'contents-expanded')
        await page(match, 'page-expanded', select={'references': True, 'source_metadata': True}, max_bytes=48000)
        body = await call('search_compendium_journals', {'pack_id': pack_id, 'journal_id': match['journal_id'], 'query': 'difficulty', 'field': 'text', 'select': {'excerpts': True}}, 'body-selected')
        assert body['scanned_entries'] == 1 and body['scanned_text_pages'] > 0
        await call('read_item', {'item_uuid': identities['Fireball'], 'select': {'details': ['source.attack'], 'evidence': True}, 'max_bytes': 48000}, 'range-evidence')
    after = await call('execute_javascript', {'code': "return JSON.stringify({core:game.version,system:game.system.version,messages:game.messages.size,journals:game.journal.size,items:game.items.size,actors:game.actors.size});"}, 'setup')
    assert json.loads(after['value']) == before
    return dict(passed=True, phase='candidate' if candidate else 'baseline', calls=calls, discovery_calls=1, call_cap=60, seconds=round(time.monotonic()-started,3), time_cap=300,
                catalog_bytes=catalog_bytes, catalog_tools=len(catalog), paths=paths, checks=source_checks, document_counts_unchanged=True, measurements=rows, tokens=None)


async def evaluation(client, args):
    """Instrument one fresh-agent task; bounded read-only MCP fallback client.

    Report writes are private evaluation artifacts, never Foundry mutations.
    Each catalog/describe/call counts, including failed requests. Start/finish
    records survive separate client processes; no LLM self-reported metrics.
    """
    assert args.run in ('agent1', 'agent2')
    directory = ROOT / '.eval-runs'
    directory.mkdir(mode=0o700, exist_ok=True)
    path = directory / ('wish009-' + args.run + '.json')
    now = time.time()
    if path.exists():
        state = json.loads(path.read_text())
    else:
        state = dict(started=now, calls=[], call_cap=8, seconds_cap=120, tokens=None,
                     harness='fresh Python MCP client per operation; instruction-only isolation',
                     commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                     dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True)))
    assert len(state['calls']) < 8 and now-state['started'] < 120, 'Evaluation budget exhausted'
    row = dict(operation=args.phase, tool=args.tool, started=now, complete=False)
    state['calls'].append(row)
    path.touch(mode=0o600, exist_ok=True)
    path.write_text(json.dumps(state))
    try:
        if args.phase in ('catalog', 'describe'):
            catalog = await client.list_tools()
            state['catalog_hash'] = hashlib.sha256(json.dumps([t.model_dump(mode='json') for t in catalog], sort_keys=True).encode()).hexdigest()
            if args.phase == 'catalog':
                output = [{'name': t.name, 'purpose': (t.description or '').split('\n')[0]} for t in catalog]
            else:
                output = next(t for t in catalog if t.name == args.tool).model_dump(mode='json')
        else:
            assert args.tool in {'list_compendiums', 'search_compendium_journals', 'get_compendium_journal_contents',
                                 'read_compendium_journal_page', 'resolve_compendium_journal_reference',
                                 'list_actor_compendiums', 'search_compendium_actors', 'read_item', 'read_actor'}
            response = await client.call_tool(args.tool, json.loads(args.arguments), meta={'evaluation': {'run_id': 'wish009-'+args.run, 'task_id': 'level-dc', 'attempt_id': '1'}})
            output = response.structured_content
        row.update(complete=True, bytes=size(output))
        print(json.dumps(output))
    finally:
        row['seconds'] = round(time.time()-now, 3)
        state['elapsed'] = round(time.time()-state['started'], 3)
        path.write_text(json.dumps(state))


async def main(args):
    token = next(line.partition('=')[2].strip() for line in (ROOT/'.env.mcp').read_text().splitlines() if line.partition('=')[0].strip() == 'FOUNDRY_MCP_CALLER_TOKEN')
    transport = StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp', headers={'Authorization': 'Bearer '+token})
    async with asyncio.timeout(300), Client(transport, timeout=35, init_timeout=10) as client:
        if args.phase in ('baseline', 'candidate'):
            report = await audit(client, args.phase == 'candidate')
            directory = ROOT / '.eval-runs'
            directory.mkdir(mode=0o700, exist_ok=True)
            path = directory / ('wish009-' + args.phase + '.json')
            path.touch(mode=0o600, exist_ok=True)
            path.write_text(json.dumps(report))
            print(json.dumps(report))
        else:
            await evaluation(client, args)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['baseline', 'candidate', 'catalog', 'describe', 'call'])
    parser.add_argument('--run', choices=['agent1', 'agent2'])
    parser.add_argument('--tool')
    parser.add_argument('--arguments', default='{}')
    asyncio.run(main(parser.parse_args()))
