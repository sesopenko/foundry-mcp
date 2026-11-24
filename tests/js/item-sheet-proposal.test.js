import test from 'node:test';
import assert from 'node:assert/strict';
import {world} from './fixtures/item-sheet-world.js';
import {proposal,variant} from '../../foundry-module/scripts/itemSheetProposal.js';
import {sheetTarget} from '../../foundry-module/scripts/itemSheetTarget.js';
import {PHYSICAL_TYPES} from '../../foundry-module/scripts/actorPhysical.js';

async function setup(){
  const fixture=world();
  const target=await sheetTarget({item_uuid:fixture.item.uuid});
  const evaluate=changes=>proposal({target,source:fixture.source,current:fixture.item.toObject(false),variant:variant(target)},changes);
  return {...fixture,target,evaluate};
}
test('P8 common authoring for each physical type and independent mystification',async()=>{
  const {item,source,evaluate}=await setup();
  for(const type of PHYSICAL_TYPES){
    item.type=type;
    const p=await evaluate({header:{name:'True Blade'},description:{text:'Steel < cold'},
      mystification:{unidentified_name:'Chipped Blade',unidentified_description:'It gleams & hums'}});
    assert.equal(p.patch.name,'True Blade');
    assert.equal(p.after.system.description.value,'Steel &lt; cold');
    assert.deepEqual(p.after.system.identification,{status:'identified',unidentified:{name:'Chipped Blade',img:'',
      data:{description:{value:'It gleams &amp; hums'}}}});
    if(type==='backpack')await assert.rejects(()=>evaluate({weapon_summary:{quantity:2}}),/Backpack/);
    else assert.equal((await evaluate({weapon_summary:{quantity:2}})).after.system.quantity,2);
  }
  source.system.identification.unidentified={img:'icons/keep.webp',name:'Old',data:{description:{value:'Old'}}};
  const p=await evaluate({mystification:{unidentified_description:'',identification_status:'unidentified'}});
  assert.deepEqual(p.after.system.identification.unidentified,{img:'icons/keep.webp',name:'Old',data:{description:{value:''}}});
  assert.equal(source.system.identification.status,'identified');
  for(const changes of [{header:{name:'x'.repeat(257)}},{description:{text:'[[1d20]]'}},{weapon_summary:{quantity:-1}},
    {mystification:{identification_status:'unknown'}},{mystification:{unidentified_name:' '}},
    {mystification:{unidentified_description:'@Check[will]'}}])
    await assert.rejects(()=>evaluate(changes));
});
test('P8 weapon header, image membership and sidebar price basis',async()=>{
  const {evaluate,source}=await setup();
  class Picker{
    sources={data:{}};
    static async browse(){return {target:'icons',files:['icons/new.webp'],dirs:[]};}
  }
  foundry.applications={apps:{FilePicker:{implementation:Picker}}};
  const image={source:'data',directory:'icons',src:'icons/new.webp'};
  const p=await evaluate({header:{image,level:5,rarity:'common',traits:['finesse']},
    weapon_summary:{hands:'held-in-two-hands',size:'lg',bulk:0,price:{gp:3}}});
  assert.equal(p.after.img,'icons/new.webp');assert.equal(p.after.system.usage.value,'held-in-two-hands');
  assert.deepEqual(p.after.system.price,{value:{sp:1,gp:3},per:2});
  assert.equal(p.after.system.level.value,5);assert.equal(p.after.system.bulk.value,0);
  assert.deepEqual(source.system.traits.value,['agile']);
  for(const changes of [{header:{image:{...image,src:'icons/missing.webp'}}},{header:{level:-1}},{header:{rarity:'epic'}},
    {header:{traits:['bogus']}},{weapon_summary:{bulk:0.3}},{weapon_summary:{size:'sm'}},
    {weapon_summary:{hands:1}},{weapon_summary:{price:{gp:-2}}}])await assert.rejects(()=>evaluate(changes));
});

test('P9 final classification/range, Other Tags, publication and historical code preservation',async()=>{
  const {evaluate,source}=await setup();
  source.system.traits.otherTags=['historical'];
  const p=await evaluate({publication:{title:'Guide',authors:'A and B',license:'OGL',remaster:false},
    details:{group:'bow',category:'simple',base:null,range:60}});
  assert.equal(p.after.system.group,'bow');assert.equal(p.after.system.baseItem,null);
  assert.deepEqual(p.after.system.publication,{title:'Guide',authors:'A and B',license:'OGL',remaster:false});
  assert.deepEqual(p.after.system.traits.otherTags,['historical']);
  assert.deepEqual((await evaluate({other_tags:{tags:['implement']}})).after.system.traits.otherTags,['implement']);
  for(const changes of [{details:{category:'bogus'}},{details:{base:'bogus'}},{details:{group:'bow'}},{details:{range:55}},
    {details:{group:'future'}},{publication:{title:1}},{publication:{authors:[]}},{publication:{license:'CC0'}},
    {publication:{remaster:'false'}},{other_tags:{tags:['historical']}},{weapon_summary:{hands:'held-in-two-hands'},other_tags:{tags:['implement']}},
    {publication:{title:'Valid',rules:[{key:'RollOption'}]}}])await assert.rejects(()=>evaluate(changes));
});

test('P10 source material grade, prospective slots and snapshot transitions',async()=>{
  const {evaluate,source}=await setup();
  const runes=async value=>(await evaluate({material_and_runes:value})).after.system;
  const result=await runes({specific_magic_weapon:true,property_runes:[{slot:2,value:'flaming'}],
    precious_material:{type:'orichalcum',grade:'high'},striking_rune:2});
  assert.deepEqual(result.runes,{potency:1,striking:2,property:['wounding','flaming']});
  assert.deepEqual(result.specific,{material:result.material,runes:result.runes});
  source.system.specific=structuredClone(result.specific);
  await assert.rejects(()=>runes({property_runes:[{slot:1,value:'flaming'}]}),/Specific/);
  assert.equal((await runes({specific_magic_weapon:false,striking_rune:2})).specific,null);
  source.system.specific=null;
  for(const value of [{potency_rune:5},{striking_rune:-1},{precious_material:{type:'bogus',grade:'high'}},
    {precious_material:{type:'orichalcum',grade:'low'}},{property_runes:[{slot:1,value:'fortification'}]},
    {potency_rune:0},{property_runes:[{slot:2,value:'flaming'}]},
    {potency_rune:3,property_runes:[{slot:3,value:'flaming'}]},{specific_magic_weapon:'false'}])
    await assert.rejects(()=>runes(value));
  assert.deepEqual((await runes({property_runes:[{slot:1,value:null}],potency_rune:0})).runes.property,[]);
  game.settings.get=()=> 'ABPRulesAsWritten';
  assert.deepEqual((await runes({property_runes:[{slot:2,value:'flaming'}]})).runes.property,['wounding','flaming']);
  await assert.rejects(()=>runes({potency_rune:3}),/Automatic Bonus Progression/);
});

test('specific fundamental upgrades preserve baseline and material type; browser rejects illegal partial clears',async()=>{
  const {source,evaluate}=await setup();
  source.system.material={type:'silver',grade:'low'};
  source.system.specific={material:{...source.system.material},runes:structuredClone(source.system.runes)};
  const after=(await evaluate({material_and_runes:{striking_rune:2,precious_material:{grade:'standard'}}})).after.system;
  assert.equal(after.runes.striking,2);assert.equal(after.specific.runes.striking,1);
  assert.deepEqual(after.material,{type:'silver',grade:'standard'});assert.equal(after.specific.material.grade,'low');
  await assert.rejects(()=>evaluate({material_and_runes:{precious_material:{type:'adamantine',grade:'high'}}}));
  source.system.specific=null;
  for(const material of [{type:null},{grade:null},{type:null,grade:null}]){
    await assert.rejects(()=>evaluate({material_and_runes:{precious_material:material}}));
  }
});

test('P11 base, splash and persistent damage are independent of runes and preserve siblings',async()=>{
  const {evaluate,source}=await setup();
  const damage=async value=>(await evaluate({damage:value})).after.system;
  const p=await damage({base:{die:'d8',type:'fire',dice:2},splash:0,persistent:{amount:2,faces:null,type:'bleed'}});
  assert.deepEqual(p.damage,{dice:2,die:'d8',damageType:'fire',modifier:3,persistent:{number:2,faces:null,type:'bleed'}});
  assert.deepEqual(p.runes,source.system.runes);assert.equal(p.splashDamage.value,0);
  source.system.damage.persistent=p.damage.persistent;
  assert.deepEqual((await damage({persistent:{faces:6}})).damage.persistent,{number:2,faces:6,type:'bleed'});
  assert.equal((await damage({persistent:null})).damage.persistent,null);
  for(const value of [{base:{dice:15}},{base:{die:'d20'}},{base:{type:'bleed'}},{base:{type:'bogus'}},
    {splash:-1},{persistent:{amount:0}},{persistent:{type:'bogus'}},{persistent:{faces:5}}])
    await assert.rejects(()=>damage(value));
  source.system.damage.persistent=null;
  await assert.rejects(()=>damage({persistent:{amount:1}}),/tuple|amount/);
});

test('a classification change cannot silently discard out-of-scope stored ammunition data',async()=>{
  const {evaluate,source}=await setup();
  Object.assign(source.system,{group:'bow',range:60,ammo:{builtIn:false,baseType:'arrows',capacity:2},expend:2,reload:{value:'1'}});
  await assert.rejects(()=>evaluate({details:{group:'sword',range:null}}),/ammunition/);
  const safe=await evaluate({publication:{title:'Preserved'}});
  assert.deepEqual(safe.after.system.ammo,source.system.ammo);
});
