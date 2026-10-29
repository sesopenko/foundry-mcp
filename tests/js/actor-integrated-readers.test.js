import test from 'node:test';
import assert from 'node:assert/strict';
import {readActor,readItem} from '../../foundry-module/scripts/actors.js';
import {integratedFixture,integratedPages} from './fixtures/actor-integrated.js';

const witness=(rows,section,path)=>rows.flatMap(row=>row.section===section?row.raw:[]).find(raw=>raw.path===path);

test('combined character NPC and familiar sections paginate coherently with exact contributors and separate source/current values',async()=>{
 for(const type of ['character','npc','familiar']){
  const result=await integratedPages(type),{pages,sections,actor_uuid,item_uuids}=result,rows=pages.flatMap(page=>page.records);
  assert.ok(pages.length>1);assert.equal(new Set(rows.map(row=>row.key)).size,rows.length);
  const allowed=new Set([actor_uuid,result.master_uuid,...Object.values(item_uuids)]);
  for(const [index,page]of pages.entries()){
   assert.equal(page.identity.uuid,actor_uuid);assert.equal(page.identity.type,type);assert.deepEqual(page.sections.map(section=>section.name),sections);
   assert.equal(page.revision,pages[0].revision);assert.equal(page.pagination.returned,page.records.length);
   assert.equal(page.pagination.complete,index===pages.length-1);assert.equal(page.pagination.next_cursor===null,index===pages.length-1);
   for(const section of page.sections)if(['partial','unsupported'].includes(section.status))assert.ok(section.reasons.length>0);
  }
  assert.ok(pages.at(-1).sections.every(section=>!section.reasons.includes('pagination')));
  for(const row of rows){
   assert.ok(sections.includes(row.section));assert.deepEqual(row.provenance.contributors,row.raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})));
   for(const raw of row.raw){assert.ok(allowed.has(raw.document_uuid),'Contributors must be actual selected Actor/Items or recorded master');assert.ok(['source','transformed'].includes(raw.basis));}
  }
  const stored=witness(rows,'source','/system/attributes/hp/value'),current=witness(rows,'statistics','/system/attributes/hp/value');
  assert.equal(stored.value,7);assert.equal(stored.basis,'source');assert.equal(current.value,5);assert.equal(current.basis,'transformed');
  assert.equal(stored.document_uuid,actor_uuid);assert.equal(current.document_uuid,actor_uuid);
  const lore=rows.find(row=>row.section==='skills'&&row.mapped.concept==='lore_specialty');assert.equal(lore.mapped.value.target_uuid,item_uuids.lore);
  const loreSource=await readItem({item_uuid:item_uuids.lore,sections:['source'],limit:100,max_bytes:48000});
  const rank=loreSource.records.flatMap(row=>row.raw).find(raw=>raw.path==='/system/proficient/value');assert.equal(rank.value,1);assert.equal(rank.basis,'source');assert.equal(rank.document_uuid,item_uuids.lore);
  if(type!=='familiar'){
   const joined=rows.find(row=>row.mapped.concept==='current_skill_lore_reference');assert.equal(joined.mapped.value.target_uuid,item_uuids.lore);
   const total=witness(rows,'skills','/system/skills/terrain-lore/totalModifier');assert.equal(total.value,11);assert.equal(total.basis,'transformed');assert.equal(total.document_uuid,actor_uuid);assert.notEqual(rank.value,total.value);
  }
  const casting=rows.filter(row=>row.mapped.concept==='casting_contextual_option');assert.equal(casting.length,2);
  assert.deepEqual(casting.map(row=>row.mapped.value.expended),[false,true]);
  assert.ok(casting.every(row=>row.mapped.value.spell.target_uuid===item_uuids.spell&&row.mapped.value.entry.target_uuid===item_uuids.entry&&row.mapped.value.availability==='not_evaluated'));
  assert.ok(rows.some(row=>row.section==='inventory'&&row.mapped.concept==='inventory_item'&&row.mapped.value.target_uuid===item_uuids.weapon));
  assert.equal(rows.filter(row=>row.section==='state'&&row.mapped.concept==='state_item').length,2);
  assert.ok(rows.filter(row=>row.section==='state'&&row.mapped.concept==='state_item').every(row=>row.mapped.value.application==='unknown'));
  const expiry=rows.find(row=>row.provenance.mapping==='pf2e.effect.current.v1');assert.equal(expiry.raw[0].document_uuid,item_uuids.effect);assert.equal(expiry.raw[0].value,false);assert.equal(expiry.raw[0].basis,'transformed');
  assert.equal(pages.at(-1).sections.find(section=>section.name==='effective').status,'unsupported');
  if(type==='familiar'){
   const master=rows.find(row=>row.section==='identity'&&row.mapped.concept==='familiar_master');assert.equal(master.mapped.value.target_uuid,result.master_uuid);
   const actions=rows.filter(row=>row.section==='abilities');assert.equal(actions.length,1);assert.equal(actions[0].mapped.value.target_uuid,item_uuids.action);
   assert.equal(rows.filter(row=>row.section==='strikes').length,0);assert.equal(pages.at(-1).sections.find(section=>section.name==='strikes').status,'unsupported');
   assert.ok(rows.some(row=>row.section==='description'&&row.raw[0]?.value?.includes('Familiar original creature')));
   const skill=witness(rows,'statistics','/system/skills/acrobatics/totalModifier');assert.equal(skill.value,9);assert.equal(skill.basis,'transformed');
  }else{
   assert.ok(rows.some(row=>row.provenance.mapping==='pf2e.actor.strike-current.v1'&&row.mapped.concept==='current_strike_attack_modifier'&&row.mapped.value===11));
   const abilities=rows.filter(row=>row.section==='abilities');assert.equal(abilities.length,type==='character'?2:1);
   if(type==='character')assert.ok(rows.some(row=>row.section==='build'&&row.mapped.concept==='build_item'));
   if(type==='npc')assert.ok(rows.some(row=>row.section==='strikes'&&row.mapped.concept==='npc_attack_item'&&row.mapped.value.target_uuid===item_uuids.melee));
  }
 }
});

test('all-section token reads retain instance ownership and unsupported scopes without base substitutions',async()=>{
 for(const type of ['character','npc','familiar']){
  const result=await integratedPages(type,'token'),rows=result.pages.flatMap(page=>page.records);
  assert.ok(result.pages.every(page=>page.identity.source_kind==='token'&&page.identity.uuid===result.actor_uuid&&page.identity.instance.token_uuid===result.selector.token_uuid&&page.identity.instance.base_actor.uuid==='Actor.base'));
  for(const row of rows)for(const raw of row.raw)assert.notEqual(raw.document_uuid,'Actor.base','Base template must not supply current witnesses');
  for(const row of rows.filter(row=>['character_ability_item','npc_ability_item','familiar_ability','lore_specialty','inventory_item','state_item'].includes(row.mapped.concept)&&row.mapped.value?.status==='resolved')){
   assert.equal(row.mapped.value.token_uuid,result.selector.token_uuid);assert.ok(row.mapped.value.target_uuid.startsWith(result.actor_uuid+'.Item.'));
  }
 }
});

test('combined continuations invalidate current or owned contributor changes rather than mixing section revisions',async()=>{
 for(const mutation of ['current','source','permission']){
  const f=integratedFixture('character'),sections=['source','statistics','abilities','spellcasting','state'],params={...f.selector,sections,limit:1,max_bytes:48000},first=await readActor(params);
  assert.ok(first.pagination.next_cursor);
  if(mutation==='current')f.current.system.attributes.hp.value++;
  if(mutation==='source')f.itemSources.get('spell').system.location.heightenedLevel++;
  if(mutation==='permission')f.actor.items.get('action').testUserPermission=()=>false;
  await assert.rejects(readActor({...params,cursor:first.pagination.next_cursor}),error=>error.rpcError?.code==='ContentChanged');
 }
});
