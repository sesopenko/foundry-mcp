import test from 'node:test';
import assert from 'node:assert/strict';
import {readItem,getActorTypes} from '../../foundry-module/scripts/actors.js';
function fixture(context='world'){
 const source={name:'Faith',type:'deity',system:{category:'philosophy',sanctification:null,skill:null,domains:{primary:['truth'],alternate:[]},font:[],attribute:['wis'],weapons:['staff'],spells:{'a/~':'Item.spell',duplicate:'Item.spell'},description:{value:'Exact doctrine.'},rules:[{private:'deity_private_sentinel'}]}};
 const owner=context==='token'?{documentName:'Actor',uuid:'Scene.s.Token.t.Actor.a',id:'a',name:'Owner',type:'character',items:new Map(),testUserPermission:()=>true}:null;
 const pack=context==='pack'?{collection:'test.faiths',title:'Faiths',testUserPermission:()=>true}:null;
 const item={documentName:'Item',id:'faith',uuid:owner?owner.uuid+'.Item.faith':pack?'Compendium.test.faiths.Item.faith':'Item.faith',name:'Faith',type:'deity',parent:owner,compendium:pack,folder:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
 const spell={documentName:'Item',id:'spell',uuid:'Item.spell',name:'Spell',type:'spell',parent:null,compendium:null,folder:null,testUserPermission:()=>true,toObject:()=>{throw Error('Target source must not be read');}};
 const docs=new Map([[item.uuid,item],[spell.uuid,spell]]),lookups=[];let token=null;
 if(owner){const scene={documentName:'Scene',uuid:'Scene.s',name:'Scene',testUserPermission:()=>true};token={documentName:'Token',uuid:'Scene.s.Token.t',name:'Token',parent:scene,actor:owner,baseActor:null,isLinked:false,testUserPermission:()=>true};owner.token=token;owner.items.set('faith',item);docs.set(token.uuid,token);}
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>{lookups.push(uuid);return docs.get(uuid);}}};
 return {source,item,spell,docs,lookups,args:{item_uuid:item.uuid,...(token?{token_uuid:token.uuid}:{})}};
}
async function all(f,sections,limit=3){let cursor,rows=[],last;do{last=await readItem({...f.args,sections,limit,max_bytes:8000,...(cursor?{cursor}:{})});rows.push(...last.records);cursor=last.pagination.next_cursor;}while(cursor);return {rows,last};}
test('deity source options preserve philosophy identity and never acquire listed spells',async()=>{
 const f=fixture(),before=JSON.stringify(f.source),{rows,last}=await all(f,['source','description','effective']);
 for(const [path,value]of [['/system/category','philosophy'],['/system/sanctification',null],['/system/skill',null],['/system/spells/a~1~0','Item.spell'],['/system/description/value','Exact doctrine.']])assert.deepEqual(rows.find(r=>r.raw[0]?.path===path).raw[0].value,value);
 assert.ok(!f.lookups.includes('Item.spell'));assert.ok(!JSON.stringify(rows).includes('deity_private_sentinel'));assert.equal(last.sections[0].status,'complete');assert.equal(last.sections[2].status,'unsupported');assert.equal(JSON.stringify(f.source),before);
});
test('deity references distinguish wrong-type missing denied and empty targets',async()=>{
 const f=fixture();let result=await all(f,['relationships']);assert.equal(result.rows.length,2);assert.ok(result.rows.every(r=>r.mapped.value.type==='spell'));assert.equal(new Set(result.rows.map(r=>r.key)).size,2);
 f.spell.type='feat';assert.ok((await all(f,['relationships'])).rows.every(r=>r.mapped.value.status==='unsupported'));f.spell.type='spell';f.spell.testUserPermission=()=>false;assert.ok((await all(f,['relationships'])).rows.every(r=>r.mapped.value.status==='denied'));f.docs.delete('Item.spell');assert.ok((await all(f,['relationships'])).rows.every(r=>r.mapped.value.status==='missing'));
 f.source.system.spells={};assert.equal((await all(f,['relationships'])).rows[0].mapped.value.status,'empty');delete f.source.system.spells;assert.equal((await all(f,['relationships'])).rows[0].mapped.value.status,'missing');
});
test('deity relationship continuations revalidate source target names and permissions',async()=>{
 for(const change of ['source','name','permission']){const f=fixture(),page=await readItem({...f.args,sections:['relationships'],limit:1});if(change==='source')f.source.system.spells.extra='Item.spell';if(change==='name')f.spell.name='Changed';if(change==='permission')f.spell.testUserPermission=()=>false;await assert.rejects(readItem({...f.args,sections:['relationships'],limit:1,cursor:page.pagination.next_cursor}),e=>e.rpcError.code==='ContentChanged');}
});
test('deity explicit references are bounded and discovery reports verified source scope',async()=>{
 const f=fixture();f.source.system.spells=Object.fromEntries(Array.from({length:201},(_,i)=>[String(i),'Item.spell']));await assert.rejects(readItem({...f.args,sections:['relationships']}),e=>e.rpcError.code==='ReadFailed');assert.ok((await readItem({...f.args,sections:['source'],limit:1})).pagination.next_cursor);
 const row=(await getActorTypes()).item_types.find(r=>r.type==='deity');assert.equal(row.mapped_supported,true);assert.equal(row.verification.live.status,'passed');game.system.id='other';await assert.rejects(readItem({...f.args,sections:['source']}),e=>e.rpcError.code==='UnsupportedSystem');
});

test('deity source and explicit spell links preserve compendium and synthetic ownership identity',async()=>{
 for(const context of ['pack','token']){const f=fixture(context),{rows,last}=await all(f,['source','description','relationships']);assert.equal(last.identity.uuid,f.item.uuid);assert.equal(last.identity.type,'deity');assert.equal(last.sections[0].status,'complete');assert.ok(rows.filter(r=>r.section==='relationships').every(r=>r.raw[0].document_uuid===f.item.uuid&&r.mapped.value.target_uuid==='Item.spell'));}
});

test('deity pantheon category remains source without creature conversion',async()=>{const f=fixture();f.source.system.category='pantheon';const {rows,last}=await all(f,['source']);assert.equal(last.identity.type,'deity');assert.equal(rows.find(r=>r.raw[0]?.path==='/system/category').mapped.value,'pantheon');});
