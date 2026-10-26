"""PF2e-specific read-only transformed-serialization probe on existing Actors.

No document creation, preparation calls, getters outside serialized document data,
or gameplay operations. Reports selected primitive field coverage without names
or selectors. Contract: docs/actor-item-story-map/current-statistics-contract.md.
"""
import asyncio
import argparse
import json
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


def payload(result):
    """Decode MCP structured data without displaying document values."""
    return result.structured_content if result.structured_content is not None else json.loads(
        next(block.text for block in result.content if block.type == 'text'))


def javascript_payload(result):
    value = payload(result)['value']
    if isinstance(value, dict) and value.get('$type') == 'Array':
        assert value.get('truncated') is False
        value = ''.join(value['values'])
    return json.loads(value)


async def verify(client, code):
    """PF2e-specific NPC read-only live verification, exact14.369/8.6.1 only.

    Expected primitives come independently from public transformed serialization;
    source hashes cover public source serialization before/after every page read.
    No helper import, runtime preparation or game document writes are performed.
    """
    available = {tool.name: tool for tool in await client.list_tools()}
    tool = available['read_actor']
    properties = tool.inputSchema['properties']
    assert {'actor_uuid', 'token_uuid', 'sections', 'limit', 'max_bytes', 'cursor'} <= properties.keys()
    assert 'statistics' in properties['sections']['items']['enum']
    assert properties['limit']['minimum'] <= 7 <= properties['limit']['maximum']
    assert properties['max_bytes']['minimum'] <= 8000 <= properties['max_bytes']['maximum']
    assert tool.annotations.readOnlyHint
    assert all(term.lower() in tool.description.lower() for term in ('transformed', 'partial', 'familiar', 'statistics'))
    registry = payload(await client.call_tool('get_actor_types', {}))
    statistics = next(row for row in registry['actor_sections'] if row['name'] == 'statistics')
    # Source support is the familiar master context; NPC numeric rows below
    # still require independently verified transformed provenance.
    assert statistics['source_supported'] and statistics['mapped_supported'] and statistics['effective_supported']
    assert all(term in ' '.join(statistics['limitations']).lower() for term in ('character', 'npc', 'familiar'))
    # Reuse only guarded document selection and the independent path definitions.
    setup = code.split('const samples=')[0]
    snapshot = setup + """
const samples=[];
for(const {actor,context,token} of selected){
 if(actor.type!=='npc')continue;
 const transformed=actor.toObject(false).system;
 const fields=[];
 for(const path of pathsFor(actor.type)){
  const keys=path.split('.');let value=transformed,present=true;
  for(const key of keys){if(value===null||typeof value!=='object'||!Object.hasOwn(value,key)||value[key]===undefined){present=false;break;}value=value[key];}
  if(keys.length===3&&keys[0]==='movement'){
   if(!['land','travel'].includes(keys[2])&&present&&value===null)fields.push({path:'/system/'+keys.join('/'),present:true,value:null});
   continue;
  }
  if(keys[0]==='movement'&&transformed.movement?.speeds?.[keys[2]]===null)continue;
  fields.push({path:'/system/'+keys.join('/'),present,...(present?{value}:{})});
 }
 const bytes=new TextEncoder().encode(JSON.stringify(actor.toObject(true)));
 const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
 samples.push({context,selector:token?{token_uuid:token.uuid}:{actor_uuid:actor.uuid},uuid:actor.uuid,hash,fields});
}
const report=JSON.stringify({samples});
return Array.from({length:Math.ceil(report.length/800)},(_,i)=>report.slice(i*800,(i+1)*800));
"""
    before = javascript_payload(await client.call_tool('execute_javascript', {'code': snapshot}))
    assert len(before['samples']) == 2
    assert {row['context'] for row in before['samples']} == {'world', 'synthetic'}
    summaries = []
    for sample in before['samples']:
        expected = {row['path']: row for row in sample['fields']}
        rows, cursors, cursor, pages, revision = [], set(), None, 0, None
        while True:
            arguments = dict(sample['selector'], sections=['statistics'], limit=7, max_bytes=8000)
            if cursor:
                arguments['cursor'] = cursor
            page = payload(await client.call_tool('read_actor', arguments))
            pages += 1
            assert pages <= 200
            assert page['identity']['uuid'] == sample['uuid']
            instance = page['identity']['instance']
            if sample['context'] == 'synthetic':
                assert instance['token_uuid'] == sample['selector']['token_uuid']
                assert instance['actor_link'] is False
            else:
                assert instance is None
            if revision is None:
                revision = page['revision']
            assert page['revision'] == revision
            section = next(row for row in page['sections'] if row['name'] == 'statistics')
            assert section['status'] == 'partial' and 'other_statistics_pending' in section['reasons']
            if any(not row['present'] for row in expected.values()):
                assert 'current_fields_unavailable' in section['reasons']
            rows.extend(page['records'])
            cursor = page['pagination']['next_cursor']
            if cursor is None:
                break
            assert cursor not in cursors
            cursors.add(cursor)
        actual, supplemental, seen_paths = {}, [], set()
        for row in rows:
            assert row['section'] == 'statistics' and len(row['raw']) == 1
            raw = row['raw'][0]
            assert raw['basis'] == 'transformed' and raw['document_uuid'] == sample['uuid']
            assert raw['path'] not in seen_paths
            seen_paths.add(raw['path'])
            assert row['key'] == 'statistics:' + raw['path'] and row['kind'] == 'field'
            assert row['provenance']['contributors'] == [{'document_uuid': sample['uuid'], 'path': raw['path'], 'basis': 'transformed'}]
            mapping = row['provenance']['mapping']
            assert mapping in ('pf2e.actor.current.v1', 'pf2e.actor.creature-current.v1')
            if mapping == 'pf2e.actor.current.v1':
                actual[raw['path']] = {key: raw[key] for key in ('path', 'present', 'value') if key in raw}
            else:
                assert row['provenance']['limitations'] == ['serialized_creature_details_not_target_context']
                supplemental.append(row)
                expected_mapped = raw.get('value')
                if expected_mapped == [] and not raw['path'].endswith('/definition'):
                    expected_mapped = None
                assert row['mapped']['value'] == expected_mapped
        assert actual == expected
        assert 0 < len(supplemental) <= 24000
        # Read only the returned supplementary paths, independently of the
        # production selector. Batch small requests/results to preserve the
        # development tool's bounded chunk envelope without dumping Actors.
        for offset in range(0, len(supplemental), 20):
            batch = supplemental[offset:offset + 20]
            paths = [row['raw'][0]['path'] for row in batch]
            independent = setup + 'const requested=' + json.dumps(paths) + ';const context=' + json.dumps(sample['context']) + ';' + r"""
if(requested.length>24000)throw Error('Verification path bound exceeded');
const candidate=selected.find(row=>row.context===context&&row.actor.type==='npc');
if(!candidate)throw Error('Existing selected context unavailable');
const serialized=candidate.actor.toObject(false);
const own=(object,key)=>{if(object===null||typeof object!=='object')return {present:false};const d=Object.getOwnPropertyDescriptor(object,key);if(!d||!Object.hasOwn(d,'value')||d.value===undefined)return {present:false};return {present:true,value:d.value};};
function clean(value,depth=0,budget={nodes:0}){
 if(depth>10||++budget.nodes>1024)throw Error('Verification value bound exceeded');
 if(value===null||typeof value==='string'||typeof value==='boolean'||typeof value==='number'&&Number.isFinite(value))return value;
 if(Array.isArray(value)){const result=[];for(let i=0;i<value.length;i++){const field=own(value,String(i));if(!field.present)throw Error('Unavailable array data');result.push(clean(field.value,depth+1,budget));}return result;}
 if(typeof value!=='object')throw Error('Unsupported selected data');
 const result={};for(const key of Object.getOwnPropertyNames(value)){const field=own(value,key);if(!field.present)throw Error('Unavailable object data');Object.defineProperty(result,key,{value:clean(field.value,depth+1,budget),enumerable:true});}return result;
}
const fields=[];
for(const path of requested){let value=serialized,present=true;for(const encoded of path.slice(1).split('/')){const key=encoded.replace(/~1/g,'/').replace(/~0/g,'~'),field=own(value,key);if(!field.present){present=false;break;}value=field.value;}
 if(present&&value===Infinity){if(!/^\/system\/perception\/senses\/\d+\/range$/.test(path))throw Error('Unexpected nonfinite selected field');value={'$number':'Infinity'};}
 fields.push({path,present,...(present?{value:clean(value)}:{})});
}
const report=JSON.stringify({fields});
return Array.from({length:Math.ceil(report.length/800)},(_,i)=>report.slice(i*800,(i+1)*800));
"""
            selected_fields = javascript_payload(await client.call_tool('execute_javascript', {'code': independent}))['fields']
            assert selected_fields == [{key: row['raw'][0][key] for key in ('path', 'present', 'value') if key in row['raw'][0]} for row in batch]
        summaries.append({'pages': pages, 'records': len(rows), 'core_records_checked': len(actual), 'supplement_records_checked': len(supplemental)})
    after = javascript_payload(await client.call_tool('execute_javascript', {'code': snapshot}))
    assert after == before, 'Selected source or transformed snapshot changed during verification.'
    print(json.dumps({'passed': True, 'samples': len(summaries), 'results': summaries}))


async def diagnose(client, code):
    """PF2e-specific read-only diagnosis of our exported helper's admission."""
    setup = code.split('const samples=')[0]
    diagnostic = setup + """
const {currentStatisticFields}=await import('/modules/foundry-mcp/scripts/actorCurrent.js');
const samples=[];
for(const {actor,context} of selected){
 if(actor.type!=='npc')continue;
 const transformed=actor.toObject(false),containers=new Map();
 for(const path of ['type',...pathsFor(actor.type).map(p=>'system.'+p)]){
  let value=transformed,prefix='';
  for(const key of path.split('.')){
   const type=value===null?'null':typeof value;
   const object=value!==null&&typeof value==='object';
   const plain=object&&[Object.prototype,null].includes(Object.getPrototypeOf(value));
   const descriptor=object?Object.getOwnPropertyDescriptor(value,key):undefined;
   containers.set(prefix+'/'+key,{path:prefix||'/',type,plain,child:key,present:!!descriptor,ownData:!!descriptor&&Object.hasOwn(descriptor,'value')});
   if(!descriptor||!Object.hasOwn(descriptor,'value'))break;
   value=descriptor.value;prefix+='/'+key;
  }
 }
 let failure=null;
 try{currentStatisticFields(transformed);}catch(error){failure=String(error.message);}
 samples.push({context,failure,containers:[...containers.values()].filter(row=>!row.plain||!row.ownData)});
}
const report=JSON.stringify({version:game.version,system:game.system.version,samples});
return Array.from({length:Math.ceil(report.length/800)},(_,i)=>report.slice(i*800,(i+1)*800));
"""
    print(json.dumps(javascript_payload(await client.call_tool('execute_javascript', {'code': diagnostic}))))


async def main(verify_mode=False, diagnose_mode=False):
    root = Path(__file__).resolve().parent.parent
    token = None
    for line in (root / '.env.mcp').read_text().splitlines():
        key, separator, value = line.partition('=')
        if separator and key.strip() == 'FOUNDRY_MCP_CALLER_TOKEN':
            token = value.strip()
    if not token:
        raise RuntimeError('Configure the local MCP caller credential first.')
    transport = StreamableHttpTransport(
        'http://127.0.0.1:8000/mcp/mcp',
        headers={'Authorization': 'Bearer ' + token},
    )
    code = """
if(!game.ready||!game.user.isGM||game.version!=='14.369'||game.system.id!=='pf2e'||game.system.version!=='8.6.1')throw Error('Unsupported development runtime');
if(location.origin!=='http://localhost:30000'||game.world.id!=='test')throw Error('Wrong development world');
const pathsFor=(type)=>[
 ...['str','dex','con','int','wis','cha'].flatMap(a=>[`abilities.${a}.mod`,...(type==='character'?[`abilities.${a}.base`]:[])]),
 ...['value','breakdown','details'].map(k=>`attributes.ac.${k}`),
 ...['value','max','temp'].map(k=>`attributes.hp.${k}`),
 ...['fortitude','reflex','will'].flatMap(s=>['value','totalModifier','breakdown',...(type==='character'?['rank']:[])].map(k=>`saves.${s}.${k}`)),
 ...['value','totalModifier','breakdown','vision','rank'].map(k=>`perception.${k}`),
 ...['land','burrow','climb','fly','swim','travel'].flatMap(m=>[`movement.speeds.${m}`,...['value','base','type','source'].map(k=>`movement.speeds.${m}.${k}`)]),
];
const selected=[];
let inspectedWorldNpcs=0,adjustedFound=false;
for(const actor of game.actors.values()){
 if(actor.type!=='npc'||!actor.testUserPermission(game.user,'OBSERVER'))continue;
 if(++inspectedWorldNpcs>200)break;
 const adjustment=actor.toObject(true).system?.attributes?.adjustment;
 if(['elite','weak'].includes(adjustment)){
  selected.push({actor,context:'world',adjustment});adjustedFound=true;break;
 }
}
for(const type of ['character','npc','familiar']){
 if(type==='npc'&&adjustedFound)continue;
 const actor=[...game.actors.values()].find(a=>a.type===type&&a.testUserPermission(game.user,'OBSERVER'));
 if(actor)selected.push({actor,context:'world'});
}
for(const scene of game.scenes.values()){
 if(!scene.testUserPermission(game.user,'OBSERVER'))continue;
 const token=scene.tokens.find(t=>!t.isLinked&&t.actor?.type==='npc'&&t.testUserPermission(game.user,'OBSERVER')&&t.actor.testUserPermission(game.user,'OBSERVER'));
 if(token){selected.push({actor:token.actor,context:'synthetic',token});break;}
}
const at=(object,path)=>{
 for(const key of path.split('.')){
  if(object===null||typeof object!=='object'||!Object.hasOwn(object,key))return {present:false};
  object=object[key];
 }
 return {present:true,type:object===null?'null':typeof object,...(typeof object==='number'&&Number.isFinite(object)||typeof object==='boolean'?{value:object}:{}),...(typeof object==='string'?{length:object.length}:{})};
};
const samples=selected.map(({actor,context,adjustment})=>{
 const source=actor.toObject(true).system,transformed=actor.toObject(false).system;
 return {type:actor.type,context,...(adjustment?{adjustment}:{}),fields:pathsFor(actor.type).map(path=>{
  const s=at(source,path),t=at(transformed,path);
  // Equality for strings is computed locally; prose, names and selectors never leave the browser.
  let sv=source,tv=transformed;
  for(const key of path.split('.')){sv=sv?.[key];tv=tv?.[key];}
  return {path,source:s,transformed:t,...(path.startsWith('movement.speeds.')&&path.endsWith('.type')&&t.present?{matchesMode:tv===path.split('.')[2]}:{}),...(s.present&&t.present&&s.type!=='object'&&t.type!=='object'?{equal:Object.is(sv,tv)}:{})};
 })};
});
const report=JSON.stringify({version:game.version,system:game.system.version,inspectedWorldNpcs:Math.min(inspectedWorldNpcs,200),adjustedFound,samples});
return Array.from({length:Math.ceil(report.length/800)},(_,i)=>report.slice(i*800,(i+1)*800));
"""
    async with Client(transport) as client:
        if diagnose_mode:
            await diagnose(client, code)
            return
        if verify_mode:
            await verify(client, code)
            return
        result = await client.call_tool('execute_javascript', {'code': code})
    value = result.structured_content
    if value is None:
        value = json.loads(next(block.text for block in result.content if block.type == 'text'))
    value = value['value']
    if isinstance(value, dict) and value.get('$type') == 'Array':
        assert value.get('truncated') is False
        value = ''.join(value['values'])
    report = json.loads(value)
    assert report['samples'], 'No readable in-scope existing Actor.'
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true', help='Verify actual paginated MCP statistics, printing counts only.')
    parser.add_argument('--diagnose', action='store_true', help='Diagnose selected serialized container admission without values.')
    arguments = parser.parse_args()
    assert not (arguments.verify and arguments.diagnose), 'Choose one probe mode.'
    asyncio.run(main(arguments.verify, arguments.diagnose))
