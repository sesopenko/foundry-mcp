import test from 'node:test';
import assert from 'node:assert/strict';
import {world} from './fixtures/item-sheet-world.js';
import {readItemSheet} from '../../foundry-module/scripts/itemSheet.js';
const read=sheet=>readItemSheet({item_uuid:'Item.blade',sheet,max_bytes:48000,limit:100});

test('P6 header, summary, classification, tags and publication have source and displayed witnesses',async()=>{
  world();
  const data=await read({groups:['header','weapon_summary','details','other_tags','publication']});
  assert.equal(data.pagination.complete,true);
  const rows=Object.fromEntries(data.records.map(r=>[r.field,r]));
  const expected={'header.image':'icons/blade.webp','header.name':'Dogslicer','header.level':0,
    'header.rarity':'uncommon','header.traits':['agile'],'weapon_summary.quantity':1,'weapon_summary.hands':'held-in-one-hand',
    'weapon_summary.bulk':0.1,'weapon_summary.size':'med','weapon_summary.price':{sp:1,per:2},'details.category':'martial',
    'details.group':'sword','details.base':'dogslicer','details.range':null,'other_tags.tags':[],
    'publication.license':'ORC','publication.remaster':true};
  for(const [id,value] of Object.entries(expected)) assert.deepEqual(rows[id].source,value,id);
  for(const id of ['publication.title','publication.authors'])assert.equal(rows[id].present,false);
  assert.equal(rows['header.display_name'].display,'Jagged Goblin Blade');assert.equal(rows['header.display_name'].editable,false);
  assert.equal(rows['header.level'].display,7);assert.deepEqual(rows['header.traits'].display,['agile','magical']);
  assert.deepEqual(rows['weapon_summary.price'].display,{gp:440,per:2});
  assert.equal(rows['weapon_summary.hands'].display_label,'1');
  assert.equal(rows['weapon_summary.hands'].group_label,'Weapon Summary');
  game.i18n.has=k=>k==='PF2E.Details';
  game.i18n.localize=()=> 'Détails';
  assert.equal((await read({fields:['details.group']})).records[0].group_label,'Détails');
});

test('P7 ordered rune slots, damage tuples, mystification, exact bounded Unicode prose',async()=>{
  const {source}=world();
  source.system.runes.potency=2;
  const prose='A jagged blade. 🗡️'.repeat(220);source.system.description.value=prose;
  const page=await read({groups:['material_and_runes','damage','mystification']});
  const rows=Object.fromEntries(page.records.map(r=>[r.field,r]));
  const slots=page.records.filter(r=>r.slot);
  assert.deepEqual(slots.map(r=>[r.slot,r.present,r.source]),[[1,true,'wounding'],[2,false,undefined]]);
  assert.equal(slots[0].options.arguments.slot,1);
  assert.equal(rows['material_and_runes.specific_magic_weapon'].source,false);
  assert.deepEqual(rows['material_and_runes.precious_material'].source,{type:null,grade:null});
  assert.equal(rows['material_and_runes.striking_rune'].source,1);assert.equal(rows['material_and_runes.potency_rune'].source,2);
  assert.deepEqual(rows['damage.base'].source,{dice:1,die:'d6',type:'slashing'});
  assert.equal(rows['damage.base'].display.dice,2);assert.equal(rows['damage.splash'].source,0);
  assert.equal(rows['damage.persistent'].source,null);assert.equal(rows['mystification.identification_status'].source,'identified');
  assert.equal(rows['mystification.unidentified_name'].present,false);assert.equal(rows['mystification.unidentified_description'].present,false);
  assert.ok(!(await read({})).records.some(r=>r.field==='description.text'));
  const args={item_uuid:'Item.blade',sheet:{fields:['description.text']},limit:1};
  let exact='';
  for(let i=0;i<20;i++){
    const data=await readItemSheet(args);const row=data.records[0];
    assert.equal(row.text.start,exact.length);exact+=row.source;
    assert.ok(Buffer.byteLength(JSON.stringify(data))<=8000);
    if(data.pagination.complete)break;
    args.cursor=data.pagination.next_cursor;
  }
  assert.equal(exact,prose);
});

test('non-weapon physical forms retain common fields and scope',async()=>{
  const {item}=world();item.type='backpack';
  const page=await read({groups:['header','weapon_summary','damage','mystification']});
  assert.deepEqual(page.unsupported_groups,['damage']);
  assert.equal(page.records.find(r=>r.field==='weapon_summary.quantity').editable,false);
  assert.ok(!page.records.some(r=>r.field==='weapon_summary.hands'));
});

test('source baseline and authored, free and granted slot states stay distinct',async()=>{
  const {source,item}=world();
  source.system.runes.potency=3;
  const base=item.toObject.bind(item);
  item.toObject=stored=>{const d=base(stored);if(!stored)d.system.runes.property.push('flaming');return d;};
  const readRunes=()=>read({groups:['material_and_runes']});
  let page=await readRunes();
  assert.deepEqual(page.records.filter(r=>r.slot).map(r=>r.slot_state),['occupied','derived','free']);
  source.system.specific={material:{...source.system.material},runes:structuredClone(source.system.runes)};
  page=await readRunes();
  assert.deepEqual(page.records.find(r=>r.field.endsWith('specific_magic_weapon')).specific_baseline,source.system.specific);
  assert.equal(page.records.find(r=>r.slot===1).editable,false);
});

test('current potency supplies sheet capacity without being copied to authored runes',async()=>{
  const {item}=world();
  const serialize=item.toObject.bind(item);
  item.toObject=stored=>{const data=serialize(stored);if(!stored)data.system.runes.potency=2;return data;};
  const result=await read({groups:['material_and_runes']});
  assert.deepEqual(result.records.filter(r=>r.slot).map(r=>r.slot_state),['occupied','free']);
  assert.equal(result.records.find(r=>r.field.endsWith('potency_rune')).source,1);
});
