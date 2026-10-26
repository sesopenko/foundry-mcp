import test from 'node:test';
import assert from 'node:assert/strict';
import {readActor,readItem} from '../../foundry-module/scripts/actors.js';

function fixture(type='character',context='world'){
 const source={name:'Actor',type,system:{attributes:{hp:{value:7}}}},docs=new Map();
 const actor={documentName:'Actor',id:'a',uuid:'Actor.a',type,name:'Actor',system:{actions:[]},items:new Map(),folder:null,compendium:null,testUserPermission:()=>true,toObject(flag){assert.equal(flag,true);return structuredClone(source);},prepareData(){throw Error('prepare prohibited');},update(){throw Error('write prohibited');}};
 if(context==='pack'){actor.uuid='Compendium.test.actors.Actor.a';actor.compendium={collection:'test.actors',title:'Test actors',testUserPermission:()=>true};}
 let selector={actor_uuid:actor.uuid};
 if(context==='token'){const scene={documentName:'Scene',uuid:'Scene.s',name:'Scene',testUserPermission:()=>true};const base={...actor};actor.uuid='Scene.s.Token.t.Actor.a';const token={documentName:'Token',id:'t',uuid:'Scene.s.Token.t',name:'Token',parent:scene,actor,baseActor:base,isLinked:false,testUserPermission:()=>true};actor.token=token;docs.set(token.uuid,token);selector={token_uuid:token.uuid};}
 docs.set(actor.uuid,actor);
 const item=(id,owned=true)=>{const type=actor.type==='npc'?'melee':'weapon',source={name:'Persisted origin',type,system:{description:{value:'Original'}}};const value={documentName:'Item',id,uuid:actor.uuid+'.Item.'+id,type,name:'Display origin',parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject(flag){assert.equal(flag,true);return structuredClone(source);}};if(owned){actor.items.set(id,value);docs.set(value.uuid,value);}return value;};
 class CompiledStrike {get modifiers(){throw Error('modifiers getter prohibited');}}
 const strike=(origin=item('generated',false))=>Object.assign(new CompiledStrike(),{type:'strike',slug:'fist',label:'Fist',glyph:'A',description:'Strike description',ready:true,canAttack:true,totalModifier:9,breakdown:'Authored modifier breakdown',visible:true,handsAvailable:true,sourceId:'attack',attackRollType:'Attack',item:origin,options:[],domains:[],traits:[],weaponTraits:[],variants:[{penalty:0,label:'First',roll(){throw Error('roll prohibited');}}],altUsages:[],attack(){throw Error('attack prohibited');},damage(){throw Error('damage prohibited');},critical(){throw Error('critical prohibited');}});
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
 return {actor,source,selector,docs,item,strike};
}
async function all(f){const rows=[],pages=[];let cursor;do{const page=await readActor({...f.selector,sections:['strikes'],limit:4,max_bytes:8000,...(cursor?{cursor}:{})});assert.ok(Buffer.byteLength(JSON.stringify(page))<=8000);rows.push(...page.records);pages.push(page);cursor=page.pagination.next_cursor;assert.ok(pages.length<300);}while(cursor);return {rows,pages};}
const code=value=>error=>error.rpcError?.code===value;
const field=(rows,path)=>rows.find(row=>row.key==='strikes:current:'+path);

test('actual compiled generated unarmed uses Actor paths without publishing ephemeral Item UUID',async()=>{
 const f=fixture(),strike=f.strike();f.actor.system.actions=[strike];const {rows,pages}=await all(f);
 assert.equal(field(rows,'/system/actions/0/totalModifier').raw[0].value,9);assert.equal(field(rows,'/system/actions/0/totalModifier').raw[0].basis,'transformed');
 assert.deepEqual(rows.find(row=>row.key==='strikes:origin:/system/actions/0').mapped.value,{status:'generated',target_uuid:null});assert.ok(!JSON.stringify(rows).includes('.Item.generated'));
 assert.ok(pages.every(page=>page.sections[0].status==='partial'&&page.sections[0].reasons.includes('current_strike_damage_unsupported')));assert.equal(f.actor.items.size,0);
});
test('world pack and token owned origins follow canonical Items while NPC authored references stay separate',async()=>{
 for(const type of ['character','npc'])for(const context of ['world','pack','token']){const f=fixture(type,context),origin=f.item('owned');f.actor.system.actions=[f.strike(origin)];const {rows}=await all(f),ref=rows.find(row=>row.key==='strikes:origin:/system/actions/0');assert.equal(ref.mapped.value.target_uuid,origin.uuid);assert.equal(ref.raw[1].document_uuid,origin.uuid);assert.equal(ref.raw[1].value,'Persisted origin');
  const args={item_uuid:origin.uuid,...(context==='token'?{token_uuid:f.selector.token_uuid}:{})};const follow=await readItem({...args,sections:['identity']});assert.equal(follow.identity.uuid,origin.uuid);if(context==='token')assert.equal(ref.mapped.value.token_uuid,f.selector.token_uuid);
  if(type==='npc')assert.ok(rows.some(row=>row.mapped.concept==='npc_attack_item'&&row.mapped.value.target_uuid===origin.uuid));
 }
});
test('denied owned origins are checked before Strike labels and source; ephemeral colliding ID stays denied',async()=>{
 for(const ephemeral of [false,true]){const f=fixture(),owned=f.item('denied');owned.testUserPermission=()=>false;owned.toObject=()=>{throw Error('denied source prohibited');};const attack=f.strike(ephemeral?f.item('denied',false):owned);for(const key of ['label','slug','description','totalModifier','traits'])Object.defineProperty(attack,key,{get(){throw Error('private label read');}});f.actor.system.actions=[attack];const {rows,pages}=await all(f);assert.ok(rows.some(row=>row.key==='strikes:current:denied'));assert.ok(pages.every(page=>page.sections[0].reasons.includes('strike_items_denied')));assert.ok(!JSON.stringify(rows).includes('Persisted origin'));assert.ok(!JSON.stringify(rows).includes('.Item.denied'));}
});
test('alternate usages retain paths and PC variant accessors become capability rows without invocation',async()=>{
 const f=fixture(),a=f.strike(),b=f.strike(a.item);a.altUsages=[b];let getters=0;Object.defineProperty(a.variants[0],'label',{get(){getters++;throw Error('PC label getter');}});Object.defineProperty(a.variants[0],'penalty',{get(){getters++;throw Error('PC penalty getter');}});f.actor.system.actions=[a,{type:'area-fire',get statistic(){throw Error('area statistic getter');}}];
 const {rows,pages}=await all(f);assert.equal(getters,0);assert.equal(field(rows,'/system/actions/0/altUsages/0/totalModifier').mapped.value,9);assert.ok(rows.some(row=>row.key==='strikes:unavailable:/system/actions/0/variants/0/label'));assert.ok(rows.some(row=>row.key==='strikes:capability:non_strike_actions'));assert.ok(pages.every(page=>page.sections[0].reasons.includes('current_strike_fields_unavailable')));
});
test('long Unicode prose fragments reconstruct exact UTF16 source and origin/current changes stale cursors',async()=>{
 const f=fixture(),origin=f.item('owned'),strike=f.strike(origin);strike.description='<p>界😀 exact &amp; prose</p>'.repeat(100);f.actor.system.actions=[strike];const {rows}=await all(f),fragments=rows.filter(row=>row.kind==='text'&&row.text.path==='/system/actions/0/description');assert.ok(fragments.length>1);assert.equal(fragments.map(row=>row.raw[0].value).join(''),strike.description);assert.equal(fragments.at(-1).text.end,strike.description.length);
 for(const mutate of [()=>strike.totalModifier++,()=>origin.testUserPermission=()=>false,()=>{origin.toObject=()=>({name:'Changed source origin',type:origin.type,system:{}});}]){origin.testUserPermission=()=>true;const params={...f.selector,sections:['strikes'],limit:1},first=await readActor(params);mutate();await assert.rejects(readActor({...params,cursor:first.pagination.next_cursor}),code('ContentChanged'));}
});
test('missing and empty actions differ, default/source never select model and other systems reject',async()=>{
 const f=fixture();delete f.actor.system.actions;let result=await all(f);assert.equal(field(result.rows,'/system/actions').raw[0].present,false);f.actor.system.actions=[];result=await all(f);assert.deepEqual(field(result.rows,'/system/actions').raw[0].value,[]);
 let getters=0;Object.defineProperty(f.actor.system,'actions',{get(){getters++;throw Error('unselected actions');}});await readActor(f.selector);await readActor({...f.selector,sections:['source']});assert.equal(getters,0);game.system.id='other';await assert.rejects(readActor({...f.selector,sections:['strikes']}),code('UnsupportedSystem'));assert.equal(getters,0);
});
