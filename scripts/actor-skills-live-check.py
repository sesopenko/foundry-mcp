"""Read-only PF2e-specific current Skills and owner-local Lore verification.

Foundry14.369/PF2e8.6.1 public Actor.toObject(false), Actor.items, permissions
and canonical Item identities only. No getters, fallback, preparation or writes.
https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html#toobject
https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/creature/data.ts
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

REQUEST_TIMEOUT_SECONDS = 30
INIT_TIMEOUT_SECONDS = 10
SESSION_TIMEOUT_SECONDS = 180
GUARD = """
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369'||game.system.id!=='pf2e'||game.system.version!=='8.6.1')throw Error('Wrong development runtime');
"""
CHUNKS = """
const report=JSON.stringify(result);if(new TextEncoder().encode(report).length>16000)throw Error('Metadata bound');
return Array.from({length:Math.ceil(report.length/800)},(_,i)=>report.slice(i*800,(i+1)*800));
"""
COMMON = """
const hash=async value=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(value)))),b=>b.toString(16).padStart(2,'0')).join('');
const own=(object,key)=>{if(!object||typeof object!=='object')return undefined;const d=Object.getOwnPropertyDescriptor(object,key);if(!d)return undefined;if(!Object.hasOwn(d,'value'))throw Error('Accessor prohibited');return d.value;};
const at=(object,path)=>{let value=object;for(const encoded of path.slice(1).split('/')){value=own(value,encoded.replace(/~1/g,'/').replace(/~0/g,'~'));if(value===undefined)return {present:false};}return {present:true,value};};
const escape=key=>key.replaceAll('~','~0').replaceAll('/','~1');
function snapshot(actor){
 if(!actor||!['npc','character'].includes(actor.type)||!actor.testUserPermission(game.user,'OBSERVER')||actor.items.size>12000)throw Error('Unsupported Skills actor');
 const source=actor.toObject(true),current=actor.toObject(false),skills=at(current,'/system/skills'),keys=skills.present?Object.getOwnPropertyNames(skills.value):[];
 if(keys.length>512)throw Error('Skill key bound');
 const paths=[],witnesses=[],joins=[],sources=[...actor.items.values()].filter(i=>i.type==='lore'&&i.testUserPermission(game.user,'OBSERVER'));
 let ordinary=0,numeric=0,denied=false;
 if(!skills.present||!keys.length){paths.push('/system/skills');witnesses.push({path:'/system/skills',...skills});}
 const common=['slug','label','attribute','value','totalModifier','dc','breakdown','lore','itemId'];
 for(const key of keys){
  const skill=own(skills.value,key),lore=own(skill,'lore'),id=own(skill,'itemId'),item=lore===true&&typeof id==='string'&&id?[...actor.items.values()].find(i=>i.id===id):null;
  if(item&&!item.testUserPermission(game.user,'OBSERVER')){denied=true;continue;}
  if(lore===false)ordinary++;
  for(const leaf of [...common,...(actor.type==='character'?['rank','armor']:['base','mod','visible','note'])]){
   const path='/system/skills/'+escape(key)+'/'+leaf,selected=at(current,path);paths.push(path);witnesses.push({path,...selected});
   if(['value','totalModifier'].includes(leaf)&&selected.present&&typeof selected.value==='number'&&Number.isFinite(selected.value))numeric++;
  }
  if(lore===true)joins.push({path:'/system/skills/'+escape(key),status:!item?'missing':item.type==='lore'&&item.parent===actor?'resolved':'unsupported',target_uuid:item?.type==='lore'&&item.parent===actor?item.uuid:null});
 }
 return {actor,source,current,paths,witnesses,joins,sources,ordinary,numeric,denied};
}
"""
SELECT = """
const census={npc_actors:0,npc_with_current_skills:0,npc_with_resolved_lore:0};let best=null;
for(const actor of game.actors.values()){if(actor.type!=='npc'||!actor.testUserPermission(game.user,'OBSERVER'))continue;census.npc_actors++;const s=snapshot(actor);if(s.paths.length>1)census.npc_with_current_skills++;if(s.joins.some(j=>j.status==='resolved')){census.npc_with_resolved_lore++;if(!best||s.ordinary>best.ordinary)best=s;}}
const selected=best?[best]:[],gaps=best?[]:['existing_npc_with_current_owner_local_lore'];
if(CHARACTER_UUID!==null){const actor=[...game.actors.values()].find(a=>a.uuid===CHARACTER_UUID);if(!actor||actor.type!=='character')gaps.push('requested_character_unavailable');else selected.push(snapshot(actor));}
const samples=[];for(const s of selected)samples.push({uuid:s.actor.uuid,type:s.actor.type,source_hash:await hash(s.source),current_hash:await hash(s.witnesses),paths_hash:await hash(s.paths.sort()),ordinary_skills:s.ordinary,numeric_fields:s.numeric,resolved_lore:s.joins.filter(j=>j.status==='resolved').length,source_lore:s.sources.map(i=>i.uuid),joins:s.joins});
const result={samples,census,coverage_gaps:gaps};
"""
CHECK = """
const actor=[...game.actors.values()].find(a=>a.uuid===ACTOR_UUID),s=snapshot(actor),checks=[];
for(const claim of claims){const doc=claim.document_uuid===actor.uuid?actor:[...actor.items.values()].find(i=>i.uuid===claim.document_uuid);if(!doc||!doc.testUserPermission(game.user,'OBSERVER'))throw Error('Unreadable contributor');const selected=at(claim.basis==='transformed'?s.current:JSON.parse(JSON.stringify(doc.toObject(true))),claim.path);checks.push(claim.present===selected.present&&(!selected.present||JSON.stringify(claim.value)===JSON.stringify(selected.value)));}
const result=checks;
"""
JOIN_CHECK = """
const actor=[...game.actors.values()].find(a=>a.uuid===ACTOR_UUID),s=snapshot(actor),checks=[];
for(const claim of claims){const item=[...actor.items.values()].find(i=>i.uuid===claim.target_uuid);if(!item||item.type!=='lore'||item.parent!==actor||!item.testUserPermission(game.user,'OBSERVER'))throw Error('Wrong Lore origin');if(claim.source_identity){checks.push(true);continue;}const name=[...item.name];checks.push(claim.name===name.slice(0,256).join('')&&claim.name_truncated===(name.length>256));}
const result=checks;
"""


def payload(result):
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(next(block.text for block in result.content if block.type == 'text'))


def code(body, actor_uuid=None, claims=None, character_uuid=None):
    """PF2e-specific bounded independent serialization; no source/model fallback."""
    result = GUARD + COMMON
    if claims is not None:
        result += 'const claims=' + json.dumps(claims) + ';'
    result += body.replace('ACTOR_UUID', json.dumps(actor_uuid)).replace('CHARACTER_UUID', json.dumps(character_uuid)) + CHUNKS
    assert len(result.encode()) <= 32768
    return result


async def verify(client, world_id='test', character_uuid=None, report=None):
    """PF2e-specific NPC proof plus an optional existing supplied character."""
    if world_id != 'test':
        raise ValueError('Explicit existing test world required')
    requested, completed, stage = 0, 0, 'discovery'
    result = report if report is not None else {}
    result.update(passed=False, pages=0, current_records=0, source_lore=0, resolved_lore=0)

    def counts():
        result.update(mcp_calls=completed, requested_calls=requested, completed_calls=completed)

    async def call(name, arguments):
        nonlocal requested, completed
        requested += 1
        counts()
        response = await client.call_tool(name, arguments)
        completed += 1
        counts()
        return payload(response)

    async def browser(script):
        value = (await call('execute_javascript', {'code': script}))['value']
        if isinstance(value, dict) and value.get('$type') == 'Array':
            assert value.get('truncated') is False
            value = ''.join(value['values'])
        return json.loads(value)

    try:
        requested += 1
        counts()
        tools = {tool.name: tool for tool in await client.list_tools()}
        completed += 1
        counts()
        assert tools['read_actor'].annotations.readOnlyHint
        for phrase in ('skills', 'transformed', 'itemId'):
            assert phrase in tools['read_actor'].description
        stage = 'selection'
        before = await browser(code(SELECT, character_uuid=character_uuid))
        result.update(census=before['census'], coverage_gaps=list(before['coverage_gaps']))
        assert not before['coverage_gaps'] and before['samples']
        assert len([sample for sample in before['samples'] if sample['type'] == 'npc']) == 1
        if character_uuid is not None:
            assert len([sample for sample in before['samples'] if sample['type'] == 'character' and sample['uuid'] == character_uuid]) == 1
            assert len(before['samples']) == 2
        else:
            assert len(before['samples']) == 1
        for sample in before['samples']:
            for key, reason in [('numeric_fields', 'numeric_current_skill_fields_unavailable'), ('resolved_lore', 'current_owner_local_lore_unavailable'), ('ordinary_skills', 'ordinary_current_skills_unavailable')]:
                if sample[key] <= 0:
                    result['coverage_gaps'].append(sample['type'] + '_' + reason)
        assert not result['coverage_gaps']
        for sample in before['samples']:
            stage = 'skills_read'
            rows, cursor, seen, revision = [], None, set(), None
            for _ in range(200):
                args = dict(actor_uuid=sample['uuid'], sections=['skills'], limit=10, max_bytes=8000)
                if cursor:
                    args['cursor'] = cursor
                page = await call('read_actor', args)
                assert page['identity']['uuid'] == sample['uuid'] and page['identity']['type'] == sample['type']
                assert len(json.dumps(page, ensure_ascii=False, separators=(',', ':')).encode()) <= 8000
                section = page['sections'][0]
                assert section['status'] == 'partial' and 'other_skills_pending' in section['reasons']
                revision = revision or page['revision']; assert revision == page['revision']
                rows.extend(page['records']); result['pages'] += 1
                cursor = page['pagination']['next_cursor']
                if cursor is None:
                    break
                assert cursor not in seen; seen.add(cursor)
            else:
                raise AssertionError('Skill page bound')
            assert len({row['key'] for row in rows}) == len(rows)
            current = [row for row in rows if row['provenance']['mapping'] == 'pf2e.actor.skills-current.v1']
            stage = 'current_record_contract'
            paths = sorted(row['raw'][0]['path'] for row in current)
            assert hashlib.sha256(json.dumps(paths, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest() == sample['paths_hash']
            for row in current:
                raw = row['raw'][0]
                leaf = raw['path'].rsplit('/', 1)[-1]
                result['checking_field'] = leaf if leaf in ['slug','label','attribute','value','totalModifier','dc','breakdown','lore','itemId','rank','armor','base','mod','visible','note'] else 'collection'
                assert raw['document_uuid'] == sample['uuid'] and raw['basis'] == 'transformed'
                expected = raw.get('value')
                if raw['path'].endswith('/rank') and raw['present']:
                    expected = dict(rank=raw['value'], label=['Untrained', 'Trained', 'Expert', 'Master', 'Legendary'][raw['value']])
                assert row['mapped']['value'] == expected
                assert row['provenance']['limitations'] == ['serialized_current_skill_not_target_context']
            stage = 'source_and_current_lore_membership'
            source = [row for row in rows if row['provenance']['mapping'] == 'pf2e.lore.specialty.v1' and row['mapped']['value']['status'] == 'resolved']
            assert {row['mapped']['value']['target_uuid'] for row in source} == set(sample['source_lore'])
            joins = [row for row in rows if row['provenance']['mapping'] == 'pf2e.actor.skills-lore.v1']
            assert len(joins) == len(sample['joins'])
            for expected in sample['joins']:
                row = next(row for row in joins if row['raw'][0]['path'] == expected['path'] + '/lore')
                assert row['mapped']['value']['status'] == expected['status'] and row['mapped']['value']['target_uuid'] == expected['target_uuid']
            stage = 'independent_witnesses'
            witnesses = [raw for row in rows for raw in row['raw']]
            for row in rows:
                assert row['provenance']['contributors'] == [{key: raw[key] for key in ('document_uuid', 'path', 'basis')} for raw in row['raw']]
            for offset in range(0, len(witnesses), 30):
                batch = witnesses[offset:offset + 30]
                checks = await browser(code(CHECK, sample['uuid'], batch))
                if len(checks) != len(batch) or not all(value is True for value in checks):
                    result.update(failed_check_kind='raw_source_current', expected_checks=len(batch), returned_checks=len(checks),
                                  failed_checks=sum(value is not True for value in checks),
                                  failed_field_paths=sorted({'/system/skills/*/' + raw['path'].rsplit('/',1)[-1] if raw['path'].startswith('/system/skills/') else raw['path'] for raw,value in zip(batch,checks) if value is not True}))
                assert len(checks) == len(batch) and all(value is True for value in checks)
            resolved = [{**row['mapped']['value'], 'source_identity': row in source} for row in source + joins if row['mapped']['value']['status'] == 'resolved']
            checks = await browser(code(JOIN_CHECK, sample['uuid'], resolved))
            if len(checks) != len(resolved) or not all(value is True for value in checks):
                result.update(failed_check_kind='lore_identity', expected_checks=len(resolved), returned_checks=len(checks),
                              failed_checks=sum(value is not True for value in checks))
            assert len(checks) == len(resolved) and all(value is True for value in checks)
            follow = await call('read_item', dict(item_uuid=next(row['mapped']['value']['target_uuid'] for row in joins if row['mapped']['value']['status'] == 'resolved'), sections=['identity']))
            assert follow['identity']['actor']['uuid'] == sample['uuid']
            result['current_records'] += len(current); result['source_lore'] += len(source); result['resolved_lore'] += len(joins)
        stage = 'unchanged_fingerprints'
        assert await browser(code(SELECT, character_uuid=character_uuid)) == before
        result.update(passed=True, actor_types=sorted({sample['type'] for sample in before['samples']}), fingerprint_unchanged=True,
                      target_context_evaluated=False, character_checked=character_uuid is not None)
        result.pop('checking_field', None)
    except Exception as error:
        result.update(passed=False, failure_stage=stage, exception_type=type(error).__name__)
    result.update(mcp_calls=completed, requested_calls=requested, completed_calls=completed)
    return result


async def main(world_id, character_uuid=None):
    if world_id != 'test':
        raise ValueError('Explicit existing test world required')
    result = dict(passed=False)
    try:
        token = next(line.partition('=')[2].strip() for line in (Path(__file__).resolve().parents[1] / '.env.mcp').read_text().splitlines() if line.partition('=')[0].strip() == 'FOUNDRY_MCP_CALLER_TOKEN')
        if not token:
            raise RuntimeError('Missing local caller credential')
        transport = StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp', headers={'Authorization': 'Bearer ' + token})
        async with Client(transport, timeout=REQUEST_TIMEOUT_SECONDS, init_timeout=INIT_TIMEOUT_SECONDS) as client:
            async with asyncio.timeout(SESSION_TIMEOUT_SECONDS):
                await verify(client, world_id, character_uuid, result)
    except Exception as error:
        result.update(passed=False, exception_type=type(error).__name__)
    print(json.dumps(result))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world-id', required=True, choices=['test'])
    parser.add_argument('--character-uuid', help='Optional existing character supplied by an authorized marked-fixture caller.')
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.world_id, args.character_uuid)))
