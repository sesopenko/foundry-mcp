import test from 'node:test';
import assert from 'node:assert/strict';
import { verifyPF2eInlineRoll as roll, verifyPF2eInlineCheck as check, verifyPF2eInlineEmbed as embed } from '../../foundry-module/scripts/inline.js';

const uuid = 'Compendium.pf2e.feats-srd.Item.39CqlOzlHjEhh0E4';
function setup() {
  const validated = [];
  globalThis.game = {ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map(),packs:new Map()};
  const pack = {documentName:'Item',collection:'pf2e.feats-srd',testUserPermission:()=>true};
  game.packs.set(pack.collection, pack);
  const item = {documentName:'Item',uuid,compendium:pack,parent:null,testUserPermission:()=>true};
  globalThis.foundry = {dice:{Roll:{validate:f=>{validated.push(f);return true;}}},utils:{fromUuid:async()=>item}};
  return {pack,item,validated};
}
const packet = () => ({text:'[[/r 1d20+3]]',formulas:['1d20+3']});
function fails(fn, code) { assert.throws(fn, e=>e.rpcError?.type===code); }

test('public validation only, no evaluation or document mutation APIs supplied', async()=>{
  const {validated} = setup();
  assert.equal(roll(packet()).text, packet().text);
  assert.deepEqual(validated,['1d20+3']);
  assert.equal(check({text:'@Check[flat]',formulas:[]}).runtime.system_id,'pf2e');
  assert.equal((await embed({text:`@Embed[${uuid} inline]`,formulas:[],item_uuid:uuid})).text,`@Embed[${uuid} inline]`);
});

test('readiness, permission, system and exact version failures',()=>{
  for (const [change,code] of [
    [()=>game.ready=false,'NotReady'],[()=>game.user.isGM=false,'PermissionDenied'],
    [()=>game.system.id='other','UnsupportedSystem'],[()=>game.version='14.370','UnsupportedVersion'],
    [()=>game.system.version='8.6.2','UnsupportedVersion']]) {
    const {validated}=setup();change();fails(()=>roll(packet()),code);assert.equal(validated.length,0);
  }
});

test('invalid formulas, expression injection and source bounds',()=>{
  setup();foundry.dice.Roll.validate=()=>false;fails(()=>roll(packet()),'InvalidFormula');
  setup();for(const f of ['@actor.level','1d6*2','max(1,2)','1d6[fire]','1d6;alert(1)']) fails(()=>roll({text:'x',formulas:[f]}),'InvalidRequest');
  fails(()=>roll({text:'😀'.repeat(2001),formulas:[]}),'InvalidRequest');
});

test('missing/denied/mismatched compendium Items and post-await changes',async()=>{
  const params={text:`@Embed[${uuid} inline]`,formulas:[],item_uuid:uuid};
  for (const [change,code] of [
    [()=>game.packs.clear(),'DocumentNotFound'],
    [({pack})=>pack.testUserPermission=()=>false,'PermissionDenied'],
    [()=>foundry.utils.fromUuid=async()=>null,'DocumentNotFound'],
    [({item})=>item.testUserPermission=()=>false,'PermissionDenied'],
    [({item})=>item.uuid='Item.other','InvalidRequest'],
    [({item})=>item.documentName='Actor','InvalidRequest'],
    [({item})=>foundry.utils.fromUuid=async()=>{game.user.isGM=false;return item;},'PermissionDenied'],
    [({item})=>foundry.utils.fromUuid=async()=>{game.packs.clear();return item;},'DocumentNotFound']]) {
    const fixtures=setup();change(fixtures);
    await assert.rejects(()=>embed(params), e=>e.rpcError?.type===code);
  }
});
