import test from 'node:test';
import assert from 'node:assert/strict';
import {readItem} from '../../foundry-module/scripts/actors.js';

function fixture() {
 const source={name:'Reaction',type:'action',system:{actionType:{value:'reaction'},actions:{value:null},deathNote:undefined,frequency:undefined,selfEffect:{uuid:'Item.effect',name:'Named effect'},traits:{value:[],otherTags:[]},description:{value:'<p>Trigger 🙂</p>'.repeat(1000)}}};
 const doc=(uuid,type,data)=>({uuid,id:uuid.split('.').at(-1),documentName:'Item',type,name:data?.name??'Effect',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(data??{name:'Effect',type})});
 const item=doc('Item.action','action',source), effect=doc('Item.effect','effect');const docs=new Map([[item.uuid,item],[effect.uuid,effect]]);let resolutions=0;
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map()};
 globalThis.foundry={utils:{fromUuid:async(uuid,options)=>{if(uuid==='Item.effect'){resolutions++;assert.equal(options.relative,item);}return docs.get(uuid);}}};
 return {source,item,effect,docs,resolutions:()=>resolutions};
}

test('source maps null-count reactions and never resolves or applies its effect',async()=>{
 const f=fixture();const before=structuredClone(f.source);
 const page=await readItem({item_uuid:f.item.uuid,limit:100});
 assert.equal(page.sections.find(s=>s.name==='source').status,'complete');
 const activation=page.records.find(r=>r.raw[0].path==='/system/actionType/value');
 assert.equal(activation.raw[0].value,'reaction');assert.equal(activation.mapped.value,'reaction');
 assert.equal(page.records.find(r=>r.raw[0].path==='/system/actions/value').raw[0].value,null);
 assert.equal(f.resolutions(),0);assert.deepEqual(f.source,before);
 assert.ok(!page.records.some(r=>r.raw[0].path.includes('description')));
});

test('explicit relationship resolves read-only and permission changes invalidate continuations',async()=>{
 const f=fixture();let page=await readItem({item_uuid:f.item.uuid,sections:['relationships']});
 assert.deepEqual(page.records[0].mapped.value,{target_uuid:f.effect.uuid,status:'resolved'});
 assert.equal(page.records[0].raw[1].value,'Named effect');assert.equal(page.records[0].provenance.mapping,'pf2e.action.self_effect.v1');
 page=await readItem({item_uuid:f.item.uuid,sections:['source','relationships'],limit:1});
 f.effect.testUserPermission=()=>false;
 await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source','relationships'],limit:1,cursor:page.pagination.next_cursor}),error=>error.rpcError.code==='ContentChanged');
 const denied=await readItem({item_uuid:f.item.uuid,sections:['relationships']});
 assert.deepEqual(denied.records[0].mapped.value,{target_uuid:null,status:'denied'});
 f.effect.testUserPermission=()=>true;f.docs.delete(f.effect.uuid);
 const missing=await readItem({item_uuid:f.item.uuid,sections:['relationships']});assert.equal(missing.records[0].mapped.value.status,'missing');
});

test('exact descriptions and unsupported effective values remain independently bounded',async()=>{
 const f=fixture();let cursor=null;const rows=[];
 do {const page=await readItem({item_uuid:f.item.uuid,sections:['description','effective'],limit:2,max_bytes:8000,cursor});
  assert.ok(Buffer.byteLength(JSON.stringify(page))<=8000);assert.equal(page.sections[1].status,'unsupported');rows.push(...page.records);cursor=page.pagination.next_cursor;
 }while(cursor);
 assert.equal(rows.map(r=>r.raw[0].value).join(''),f.source.system.description.value);assert.equal(f.resolutions(),0);
});

test('synthetic effect relationships return revalidated token context for a usable follow-up',async()=>{
 const f=fixture();const scene={uuid:'Scene.s',documentName:'Scene',name:'Inactive',testUserPermission:()=>true};
 const owner={uuid:'Scene.s.Token.t.Actor.a',id:'a',documentName:'Actor',type:'npc',name:'Current',items:new Map(),testUserPermission:()=>true};
 const token={uuid:'Scene.s.Token.t',documentName:'Token',name:'Current token',parent:scene,actor:owner,baseActor:null,isLinked:false,testUserPermission:()=>true};owner.token=token;
 f.effect.uuid='Scene.s.Token.t.Actor.a.Item.e';f.effect.parent=owner;owner.items.set('e',f.effect);f.docs.set(f.effect.uuid,f.effect);f.docs.set(token.uuid,token);f.source.system.selfEffect.uuid=f.effect.uuid;
 let page=await readItem({item_uuid:f.item.uuid,sections:['relationships']});
 assert.deepEqual(page.records[0].mapped.value,{target_uuid:f.effect.uuid,status:'resolved',token_uuid:token.uuid});
 const followed=await readItem({item_uuid:f.effect.uuid,token_uuid:token.uuid,sections:['identity']});
 assert.equal(followed.identity.instance.token_uuid,token.uuid);
 scene.testUserPermission=()=>false;page=await readItem({item_uuid:f.item.uuid,sections:['relationships']});
 assert.equal(page.records[0].mapped.value.status,'denied');assert.equal(page.records[0].mapped.value.target_uuid,null);
});

test('relationships-only reads do not validate unrelated malformed action source',async()=>{
 const f=fixture();f.source.system.frequency={max:{malformed:true}};
 const relation=await readItem({item_uuid:f.item.uuid,sections:['relationships']});
 assert.equal(relation.records[0].mapped.value.status,'resolved');
 await assert.rejects(readItem({item_uuid:f.item.uuid}),error=>error.rpcError.code==='ReadFailed');
});
