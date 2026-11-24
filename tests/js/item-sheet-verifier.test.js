import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const body=readFileSync(new URL('../../scripts/fixtures/item-editing-live.js',import.meta.url),'utf8');
const execute=Object.getPrototypeOf(async function(){}).constructor('args','run',body);

test('GM oracle includes read-only tags shown alongside editable tag picker values',async()=>{
  const tags=[{id:'agile',readonly:false},{id:'magical',readonly:true}];
  const traitElement={value:['agile'],getAttribute:k=>k==='value'?JSON.stringify(tags):null};
  const stub={getAttribute:()=>'',value:'',textContent:'',options:[],classList:{contains:()=>false},closest:()=>({querySelectorAll:()=>[]})};
  const sheet={querySelector:s=>s.includes('"system.traits.value"')?traitElement:stub,querySelectorAll:()=>[]};
  const item={type:'weapon',documentName:'Item',getFlag:()=> 'test-marker',sheet:{id:'sheet',title:'Test',render(){},close(){}}};
  globalThis.document={getElementById:()=>sheet};
  globalThis.foundry={utils:{fromUuid:async()=>item}};
  const result=JSON.parse((await execute({uuid:'Item.test',action:'sheet'},'test-marker')).join(''));
  assert.deepEqual(result.traits,['agile','magical']);
});

test('player cleanup rejects foreign contents before deleting any marked root',async()=>{
  const marker='test-marker';let deleted=0;
  const scene={documentName:'Scene',active:false,tokens:new Map([['f',{getFlag:()=>null}]]),
    getFlag:()=>marker,delete:async()=>deleted++};
  const collection=items=>({filter:predicate=>items.filter(predicate)});
  globalThis.location={origin:'http://localhost:30000'};
  globalThis.game={ready:true,world:{id:'test'},user:{isGM:true},scenes:collection([scene]),items:collection([]),
    actors:collection([]),users:collection([])};
  await assert.rejects(()=>execute({action:'cleanup'},marker),/Foreign scene/);
  assert.equal(deleted,0);
});

test('chapter setup identifies placements even when Foundry returns tokens out of creation order',async()=>{
  const run='chapter-order-test';
  const collection=()=>({size:0,values:()=>[],filter:()=>[]});
  const document=(docName,name,extra={})=>({uuid:docName+'.'+name,documentName:docName,name,getFlag:()=>run,...extra});
  const reference=(name,type)=>({uuid:'Compendium.Item.'+name,name,type,img:'icon',toObject:()=>({system:{}})});
  globalThis.foundry={utils:{fromUuid:async id=>id.endsWith('olwngGXM3hpgoLEP')?reference('Dogslicer','weapon'):reference('Wounding','equipment')}};
  globalThis.location={origin:'http://localhost:30000'};
  globalThis.game={ready:true,user:{isGM:true},world:{id:'test'},journal:collection(),actors:collection(),scenes:collection()};
  const owners=new Map();
  globalThis.Actor={implementation:{create:async data=>{
    const actor=document('Actor',data.name,{id:data.name,items:collection(),getTokenDocument:async spec=>({toObject:()=>({...spec,actorId:data.name})})});
    owners.set(actor.id,actor);return actor;
  }}};
  const scene=document('Scene','marked',{active:false,tokens:collection(),createEmbeddedDocuments:async(_type,data)=>
    data.map((s,i)=>document('Token',s.name,{uuid:'Scene.marked.Token.'+i,isLinked:s.actorLink,actorId:s.actorId,
      baseActor:owners.get(s.actorId),actor:s.actorLink?owners.get(s.actorId):{uuid:'Scene.marked.Token.'+i+'.Actor.copy'}})).reverse()});
  globalThis.Scene={implementation:{create:async()=>scene}};
  let pages;
  globalThis.JournalEntry={implementation:{create:async data=>{pages=data.pages;return document('JournalEntry','ledger',{pages:collection()});}}};
  const chapterBody=readFileSync(new URL('../../scripts/fixtures/item-chapter-live.js',import.meta.url),'utf8');
  const chapter=Object.getPrototypeOf(async function(){}).constructor('args','run',chapterBody);
  const result=JSON.parse(await chapter({action:'create'},run));
  assert.deepEqual(new Set(result.owners),new Set(['Actor.Armory cabinet','Actor.Vault warden','Scene.marked.Token.2.Actor.copy']));
  assert.match(pages[0].text.content,/wall cabinet opens here: @UUID\[Scene.marked.Token.0\]/);
});
