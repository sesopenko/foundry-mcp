import test from 'node:test';
import assert from 'node:assert/strict';
import {getActorTypes,readActor} from '../../foundry-module/scripts/actors.js';
import {integratedFixture} from './fixtures/actor-integrated.js';

test('discovery records scoped current Skills and statistics proof without advertising complete mechanics',async()=>{
 integratedFixture();
 const registry=await getActorTypes();
 const skills=registry.actor_sections.find(row=>row.name==='skills');
 const statistics=registry.actor_sections.find(row=>row.name==='statistics');
 assert.equal(skills.verification.live.status,'passed');
 assert.equal(statistics.verification.live.status,'passed');
 assert.ok(skills.verification.live.evidence.includes('scripts/actor-skills-live-check.py'));
 assert.ok(statistics.verification.live.evidence.includes('scripts/actor-character-current-live-check.py'));
 assert.match(skills.limitations.join(' '),/world character and NPC/);
 assert.match(skills.limitations.join(' '),/target-context/);
 assert.match(statistics.limitations.join(' '),/empty sense\/IWR collections/);
 assert.match(statistics.limitations.join(' '),/populated character sense\/IWR/);
 const familiar=registry.actor_types.find(row=>row.type==='familiar');
 assert.match(familiar.limitations.join(' '),/Combined/);
 assert.match(familiar.limitations.join(' '),/application/);
 const affliction=registry.item_types.find(row=>row.type==='affliction');
 for(const flag of ['in_scope','source_supported','mapped_supported','effective_supported'])assert.equal(affliction[flag],false);
});

test('selected response limitations describe delivered views and the actual current-data boundary',async()=>{
 for(const type of ['character','npc','familiar']){
  const f=integratedFixture(type);
  const page=await readActor({...f.selector,sections:['source','statistics','state'],limit:7,max_bytes:48000});
  const text=page.limitations.join(' ');
  for(const stale of ['integrated sections remain pending','supplement live verification remains pending','Generated Strikes and full target-context behavior remain pending','serialized /system/expired','full integrated views remain unverified'])assert.ok(!text.includes(stale),stale);
  assert.match(text,/own-data \/system\/expired/);
  assert.match(text,/Application is unknown/);
  if(type!=='familiar')assert.match(text,/Select strikes separately/);
 }
});
