import test from 'node:test';
import assert from 'node:assert/strict';
import {world} from './fixtures/item-sheet-world.js';
import {getItemFieldOptions} from '../../foundry-module/scripts/itemSheet.js';

test('actual config, localized labels, literal case-insensitive filtering and empty matches',async()=>{
  world();
  CONFIG.PF2E.damageTypes.homebrew='CUSTOM';
  game.i18n.has=k=>k==='CUSTOM';game.i18n.localize=()=> 'Verdant';
  const get=(field,query)=>getItemFieldOptions({item_uuid:'Item.blade',field,query});
  assert.deepEqual((await get('damage.base.type','DANT')).records,[{value:'homebrew',label:'Verdant',available:true}]);
  assert.deepEqual((await get('damage.base.type','bleed')).records,[]);
  assert.equal((await get('damage.persistent.type','bleed')).records[0].value,'bleed');
  assert.equal((await get('details.range','Melee')).records[0].value,null);
  assert.equal((await get('publication.license')).records.length,2);
  assert.equal((await get('material_and_runes.precious_material','orichalcum')).records.length,1);
});
test('prospective ordered slots and revision/locale/query bound continuation',async()=>{
  const {source}=world();
  const args={item_uuid:'Item.blade',field:'material_and_runes.property_runes',slot:2,limit:3};
  assert.equal((await getItemFieldOptions(args)).available,false);
  args.proposed_changes={material_and_runes:{potency_rune:2}};
  const first=await getItemFieldOptions(args);
  assert.equal(first.available,true);assert.equal(first.records.length,3);
  const cursor=first.pagination.next_cursor;
  assert.equal((await getItemFieldOptions({...args,cursor})).records.length,3);
  await assert.rejects(()=>getItemFieldOptions({...args,cursor,query:'wound'}),/inputs differ/);
  source.name='Changed';await assert.rejects(()=>getItemFieldOptions({...args,cursor}),/data changed/);
  game.i18n.lang='de';await assert.rejects(()=>getItemFieldOptions({...args,cursor}),/inputs differ/);
});

test('availability matches adjacent occupied slots, mandatory melee range and specific-weapon upgrade controls',async()=>{
  const {source}=world();
  const sys=source.system;
  sys.runes.potency=2;sys.runes.property=['wounding','flaming'];
  const options=(field,extra={})=>getItemFieldOptions({item_uuid:'Item.blade',field,...extra});
  assert.equal((await options('material_and_runes.property_runes',{slot:1,query:'flaming'})).records[0].available,false);
  sys.traits.value.push('thrown-10');
  assert.equal((await options('details.range')).available,false);
  sys.material={type:'silver',grade:'low'};sys.specific={material:structuredClone(sys.material),runes:structuredClone(sys.runes)};
  assert.equal((await options('material_and_runes.striking_rune')).available,true);
  assert.equal((await options('material_and_runes.precious_material',{query:'orichalcum'})).records.length,0);
  assert.equal((await options('material_and_runes.precious_material',{query:'silver'})).records.length,3);
});

test('potency reduction availability accounts for occupied slots and explicit prospective clears',async()=>{
  const {source}=world();
  source.system.runes={potency:2,striking:0,property:['flaming','wounding']};
  const args={item_uuid:'Item.blade',field:'material_and_runes.potency_rune'};
  assert.equal((await getItemFieldOptions(args)).records.find(r=>r.value===1).available,false);
  args.proposed_changes={material_and_runes:{property_runes:[{slot:2,value:null}]}};
  assert.equal((await getItemFieldOptions(args)).records.find(r=>r.value===1).available,true);
});

test('classification menu evaluates the same final range, traits and ammunition as preview',async()=>{
  const {source}=world();
  const groups={item_uuid:'Item.blade',field:'details.group',query:'bow'};
  assert.equal((await getItemFieldOptions(groups)).records[0].available,false);
  assert.equal((await getItemFieldOptions({...groups,proposed_changes:{details:{range:60}}})).records[0].available,true);
  Object.assign(source.system,{group:'sword',range:60,reload:{value:'1'},ammo:{baseType:'arrows'},expend:1});
  const melee=await getItemFieldOptions({item_uuid:'Item.blade',field:'details.range',query:'Melee'});
  assert.equal(melee.records[0].available,false);
  CONFIG.PF2E.weaponTraits.tech='Tech';
  const tech=await getItemFieldOptions({item_uuid:'Item.blade',field:'header.traits',query:'tech'});
  assert.equal(tech.records[0].available,false);
});
