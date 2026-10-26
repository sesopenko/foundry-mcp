"""PF2e-specific14.369/8.6.1 read-only same-base token acceptance check.

Uses public Scene.tokens/active, TokenDocument.actor/baseActor/isLinked and
Document.toObject/testUserPermission/fromUuid. No canvas, writes or fixtures.
https://foundryvtt.com/api/v14/classes/foundry.documents.TokenDocument.html
https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor
"""
import argparse
import asyncio
import json
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

REQUEST_TIMEOUT_SECONDS = 30
INIT_TIMEOUT_SECONDS = 10
SESSION_TIMEOUT_SECONDS = 180
GUARD="""
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369'||game.system.id!=='pf2e'||game.system.version!=='8.6.1')throw Error('Wrong development runtime');
"""
CHUNKS="""
const encoded=JSON.stringify(result);if(encoded.length>12000)throw Error('Probe metadata bound');
return Array.from({length:Math.ceil(encoded.length/800)},(_,i)=>encoded.slice(i*800,(i+1)*800));
"""
SELECT="""
const hash=async value=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(value)))),b=>b.toString(16).padStart(2,'0')).join('');
const supported=new Set(['action','melee','lore','effect','condition','weapon','armor','shield','equipment','treasure','backpack','ammo','consumable','spell','spellcastingEntry','book','kit','feat','ancestry','heritage','background','class','deity']);
const candidates=[];let scenes=0,tokens=0;
const census={readable_supported_linked:0,readable_supported_unlinked:0,with_readable_items:0,excluded_no_readable_items:0,excluded_nonfinite_hp:0,excluded_invalid_owned_membership:0,excluded_invalid_owned_uuid:0,candidate_unlinked_base_groups:0,groups_with_distinct_current_hp:0};
for(const scene of game.scenes.values()){if(++scenes>200)throw Error('Scene bound');if(!scene.testUserPermission(game.user,'OBSERVER'))continue;
for(const token of scene.tokens.values()){if(++tokens>2000)throw Error('Token bound');const actor=token.actor,base=token.baseActor;
if(!actor||!['npc','character'].includes(actor.type)||!base||!token.testUserPermission(game.user,'OBSERVER')||!actor.testUserPermission(game.user,'OBSERVER'))continue;
census[token.isLinked?'readable_supported_linked':'readable_supported_unlinked']++;
if(actor.items.size>12000)throw Error('Item bound');const items=[...actor.items.values()].filter(i=>supported.has(i.type)&&i.testUserPermission(game.user,'OBSERVER'));
if(!items.length){census.excluded_no_readable_items++;continue;}census.with_readable_items++;
if(items.some(i=>i.parent!==actor||actor.items.get(i.id)!==i)){census.excluded_invalid_owned_membership++;continue;}
if(items.some(i=>typeof i.uuid!=='string'||!i.uuid.startsWith(actor.uuid+'.Item.'))||new Set(items.map(i=>i.uuid)).size!==items.length){census.excluded_invalid_owned_uuid++;continue;}
const source=actor.toObject(true),hp=source.system?.attributes?.hp?.value,currentHP=actor.toObject(false).system?.attributes?.hp?.value;if(!Number.isFinite(hp)||!Number.isFinite(currentHP)){census.excluded_nonfinite_hp++;continue;}
const itemSources=items.map(i=>{const s=i.toObject(true);return {name:s.name,type:s.type,system:s.system};}).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b)));
candidates.push({token,actor,base,scene,hp,currentHP,itemUUIDs:items.map(i=>i.uuid),itemHash:await hash(itemSources)});}}
const groups=new Map();for(const candidate of candidates){if(candidate.token.isLinked)continue;const group=groups.get(candidate.base.uuid)??[];group.push(candidate);groups.set(candidate.base.uuid,group);}
census.candidate_unlinked_base_groups=groups.size;
census.groups_with_distinct_current_hp=[...groups.values()].filter(group=>new Set(group.map(c=>c.currentHP)).size>1).length;
let pair=null;for(let i=0;i<candidates.length&&!pair;i++)for(let j=i+1;j<candidates.length;j++){const a=candidates[i],b=candidates[j];if(!a.token.isLinked&&!b.token.isLinked&&a.base.uuid===b.base.uuid&&a.actor.uuid!==b.actor.uuid&&a.actor.uuid!==a.base.uuid&&b.actor.uuid!==b.base.uuid&&a.currentHP!==b.currentHP&&a.itemUUIDs.every(uuid=>!b.itemUUIDs.includes(uuid))){pair=[a,b];break;}}
const inactiveScene=[...game.scenes.values()].find(scene=>scene.active===false&&scene.testUserPermission(game.user,'OBSERVER'));
const linked=candidates.find(c=>c.token.isLinked);const gaps=[];if(!pair)gaps.push('same_base_unlinked_pair_with_distinct_hp_items');if(!linked)gaps.push('linked_control');if(!inactiveScene)gaps.push('inactive_scene');
const samples=[];if(!gaps.length)for(const c of [...pair,linked]){const {token,actor,base,scene}=c;
const readable=[...actor.items.values()].filter(i=>supported.has(i.type)&&i.testUserPermission(game.user,'OBSERVER'));
const other=c===pair[0]?pair[1]:c===pair[1]?pair[0]:null;
const meaningful=i=>{const s=i.toObject(true);return JSON.stringify({name:s.name,type:s.type,system:s.system});};
const otherItems=other?[...other.actor.items.values()].filter(i=>supported.has(i.type)&&i.testUserPermission(game.user,'OBSERVER')):[];
const item=readable.find(i=>other&&!otherItems.some(j=>meaningful(i)===meaningful(j)))??readable[0];
if(!item){gaps.push('readable_supported_item');break;}
samples.push({token:token.uuid,actor:actor.uuid,base:base.uuid,scene:scene.uuid,linked:token.isLinked,inactive:!scene.active,hp:c.hp,currentHP:actor.toObject(false).system?.attributes?.hp?.value,item:{uuid:item.uuid,id:item.id,type:item.type},items:[...actor.items.values()].filter(i=>supported.has(i.type)&&i.testUserPermission(game.user,'OBSERVER')).map(i=>({uuid:i.uuid,id:i.id,type:i.type})),actorHash:await hash(actor.toObject(true)),tokenHash:await hash(token.toObject(true)),itemsHash:c.itemHash});}
for(const sample of samples){const item=await foundry.utils.fromUuid(sample.item.uuid);if(!item||item.uuid!==sample.item.uuid||item.parent?.uuid!==sample.actor||item.parent.items.get(item.id)!==item)throw Error('Selected Item owner mismatch');sample.item.source_hash=await hash(item.toObject(true));}
const result={gaps,samples,census,inactive_scene:inactiveScene?.uuid??null,scenes_scanned:scenes,tokens_scanned:tokens};
"""


def payload(result):
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(next(block.text for block in result.content if block.type == 'text'))


async def verify(client, world_id):
    """PF2e-specific existing character/NPC token proof; absent scenarios are gaps.

    Familiar/master integration retains its separate deterministic/live gates;
    this probe does not serialize familiar current data without master checks.
    """
    if world_id != 'test':
        raise ValueError('Explicit test world required')
    stage = 'discovery'
    calls = 0
    summary = dict(passed=False)
    totals = dict(pages=0, raw_witnesses=0, item_followups=0)

    async def call(name, args):
        nonlocal calls
        calls += 1
        return payload(await client.call_tool(name, args))

    async def js(code):
        result = await call('execute_javascript', dict(code=GUARD + code + CHUNKS))
        value = result['value']
        if isinstance(value, dict) and value.get('$type') == 'Array':
            assert value.get('truncated') is False
            value = ''.join(value['values'])
        return json.loads(value)

    async def pages(tool, args, key):
        rows, cursor, seen, revision = [], None, set(), None
        for _ in range(300):
            page=await call(tool,dict(args,limit=20,max_bytes=8000,**({'cursor':cursor} if cursor else {})))
            revision = revision or page['revision']
            assert page['revision'] == revision
            assert len(json.dumps(page,ensure_ascii=False,separators=(',',':')).encode())<=8000
            rows.extend(page[key])
            totals['pages'] += 1
            cursor = page['pagination']['next_cursor']
            if cursor is None:
                return rows, page
            assert cursor not in seen
            seen.add(cursor)
        raise AssertionError('Page bound')

    try:
        tools={tool.name:tool for tool in await client.list_tools()};calls+=1
        for name in ('list_scene_actors','read_actor','list_actor_items','read_item'):
            tool=tools[name];assert tool.annotations.readOnlyHint and not tool.inputSchema['additionalProperties']
            assert 'next_cursor' in tool.description
        assert 'token_uuid' in tools['read_actor'].inputSchema['properties']
        assert 'base_actor' in tools['list_scene_actors'].description
        stage = 'selection'
        before = await js(SELECT)
        if before['gaps']:
            return dict(passed=False, coverage_gaps=before['gaps'], mcp_calls=calls,
                        census=before['census'],
                        scenes_scanned=before.get('scenes_scanned'),
                        tokens_scanned=before.get('tokens_scanned'))
        samples=before['samples'];assert len(samples)==3
        assert samples[0]['base']==samples[1]['base']
        assert {i['uuid'] for i in samples[0]['items']}.isdisjoint({i['uuid'] for i in samples[1]['items']})
        assert samples[0]['currentHP'] != samples[1]['currentHP']
        assert len({samples[0]['actor'], samples[1]['actor'], samples[0]['base']}) == 3
        assert all(not s['linked'] for s in samples[:2]) and samples[2]['linked']
        assert samples[2]['actor']==samples[2]['base'] and before['inactive_scene']
        stage = 'scene_discovery'
        scene_nodes,_=await pages('list_scene_actors',{},'nodes')
        assert {s['scene'] for s in samples}<={n['uuid'] for n in scene_nodes}
        for scene in {s['scene'] for s in samples}|{before['inactive_scene']}:
            nodes,_=await pages('list_scene_actors',dict(scene_uuid=scene),'nodes')
            for sample in (s for s in samples if s['scene']==scene):
                node=next(n for n in nodes if n['uuid']==sample['token'])
                assert node['actor_link']==sample['linked'] and node['identity']['uuid']==sample['actor']
                assert node['base_actor']['uuid']==sample['base']
        for sample in samples:
            stage = 'actor_reads'
            for section,basis,expected in [('source','source',sample['hp']),('statistics','transformed',sample['currentHP'])]:
                rows,page=await pages('read_actor',dict(token_uuid=sample['token'],sections=[section]),'records')
                identity=page['identity'];assert identity['uuid']==sample['actor'] and identity['instance']['token_uuid']==sample['token']
                assert identity['instance']['base_actor']['uuid']==sample['base']
                hp=[raw for row in rows for raw in row['raw'] if raw['path']=='/system/attributes/hp/value']
                assert len(hp)==1 and hp[0]['basis']==basis and hp[0]['value']==expected
            stage = 'owned_item_discovery'
            nodes,_=await pages('list_actor_items',dict(token_uuid=sample['token']),'nodes')
            assert {n['identity']['uuid'] for n in nodes}=={i['uuid'] for i in sample['items']}
            selected=next(n for n in nodes if n['identity']['uuid']==sample['item']['uuid'])
            assert selected['next_call']['arguments']['token_uuid']==sample['token']
            stage = 'item_reads'
            for section in ('source','description'):
                rows,page=await pages('read_item',dict(item_uuid=sample['item']['uuid'],token_uuid=sample['token'],sections=[section]),'records')
                assert page['identity']['uuid']==sample['item']['uuid'] and page['identity']['actor']['uuid']==sample['actor']
                witnesses=[dict(raw,**({'fragment':row['text']} if row['kind']=='text' else {})) for row in rows for raw in row['raw']]
                assert all(raw['document_uuid']==sample['item']['uuid'] for raw in witnesses)
                paths={raw['path'] for raw in witnesses if 'fragment' in raw}
                for path in paths:
                    fragments=[raw['fragment'] for raw in witnesses if raw['path']==path and 'fragment' in raw]
                    assert fragments[0]['start']==0 and fragments[-1]['end']==fragments[-1]['total']
                    assert all(a['end']==b['start'] for a,b in zip(fragments,fragments[1:]))
                # Compare fragments in browser, returning booleans only to avoid
                # reproducing private prose or exceeding exploration string limits.
                for offset in range(0,len(witnesses),30):
                    checks=await js('const claims='+json.dumps(witnesses[offset:offset+30])+';' + """
const result=[];for(const claim of claims){const item=await foundry.utils.fromUuid(claim.document_uuid);if(!item||!item.testUserPermission(game.user,'OBSERVER'))throw Error('Missing selected Item');let value=item.toObject(true),present=true;for(const key of claim.path.slice(1).split('/').map(k=>k.replace(/~1/g,'/').replace(/~0/g,'~'))){if(value===null||typeof value!=='object'||!Object.hasOwn(value,key)){present=false;break;}value=value[key];}if(claim.fragment){const f=claim.fragment;result.push(present===claim.present&&typeof value==='string'&&value.length===f.total&&value.slice(f.start,f.end)===claim.value);}else result.push(present===claim.present&&(!present||JSON.stringify(value)===JSON.stringify(claim.value)));}
""")
                    assert len(checks) == len(witnesses[offset:offset+30])
                    for raw,check in zip(witnesses[offset:offset+30],checks):
                        assert raw['basis']=='source' and check is True
                totals['raw_witnesses']+=len(witnesses)
            totals['item_followups']+=1
        stage = 'cross_token_rejection'
        response=await client.call_tool('read_item',dict(item_uuid=samples[0]['item']['uuid'],token_uuid=samples[1]['token'],sections=['source']),raise_on_error=False);calls+=1
        assert response.is_error and 'DocumentNotFound' in ''.join(getattr(block,'text','') for block in response.content)
        stage = 'unchanged_source_fingerprints'
        assert await js(SELECT) == before
        summary.update(passed=True,source_unchanged=True,unlinked_tokens=2,linked_controls=1,inactive_scene_verified=True,coverage_gaps=[],census=before['census'],distinct_source_hp=samples[0]['hp']!=samples[1]['hp'],distinct_item_content=samples[0]['itemsHash']!=samples[1]['itemsHash'])
    except Exception as error:
        summary.update(failure_stage=stage, exception_type=type(error).__name__)
    summary.update(mcp_calls=calls,**totals)
    return summary


async def main(world_id):
    token = None
    for line in (Path(__file__).resolve().parent.parent/'.env.mcp').read_text().splitlines():
        key, separator, value = line.partition('=')
        if separator and key.strip() == 'FOUNDRY_MCP_CALLER_TOKEN':
            token = value.strip()
    if not token:
        raise RuntimeError('Missing local caller credential')
    transport=StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp',headers={'Authorization':'Bearer '+token})
    try:
        async with Client(transport,timeout=REQUEST_TIMEOUT_SECONDS,init_timeout=INIT_TIMEOUT_SECONDS) as client:
            async with asyncio.timeout(SESSION_TIMEOUT_SECONDS):
                result = await verify(client, world_id)
    except Exception as error:
        result = dict(passed=False, exception_type=type(error).__name__)
    print(json.dumps(result))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world-id', required=True, choices=['test'])
    raise SystemExit(asyncio.run(main(parser.parse_args().world_id)))
