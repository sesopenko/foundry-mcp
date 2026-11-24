export function world() {
  const system = {
    quantity:1, usage:{value:'held-in-one-hand'}, bulk:{value:0.1}, size:'med', price:{value:{sp:1},per:2},
    level:{value:0}, category:'martial', group:'sword', baseItem:'dogslicer', range:null,
    material:{type:null,grade:null}, runes:{potency:1,striking:1,property:['wounding']}, specific:null,
    damage:{dice:1,die:'d6',damageType:'slashing',modifier:3,persistent:null}, splashDamage:{value:0},
    traits:{value:['agile'],rarity:'uncommon',otherTags:[]}, publication:{license:'ORC',remaster:true},
    identification:{status:'identified',unidentified:null},description:{value:'True description'},
  };
  const source = {name:'Dogslicer',type:'weapon',img:'icons/blade.webp',system};
  const docs = new Map();
  const doc = (uuid,documentName,extra) => {
    const value = {uuid,id:uuid.split('.').at(-1),name:'Fixture',documentName,parent:null,
      testUserPermission:()=>true,canUserModify:()=>true,...extra};
    docs.set(uuid,value);
    return value;
  };
  const item = doc('Item.blade','Item',{type:'weapon',name:'Jagged Goblin Blade',toObject(stored) {
    const data=structuredClone(source);
    if (!stored) {
      data.system.level.value=7; data.system.damage.dice=2; data.system.price.value={gp:440};
      data.system.traits.value.push('magical');
    }
    return data;
  }});
  const writes=[];
  item.update=async patch => {
    writes.push(structuredClone(patch));
    for(const [path,value] of Object.entries(patch)){
      const parts=path.split('.');let node=source;
      for(const k of parts.slice(0,-1)){node[k]??={};node=node[k];}
      node[parts.at(-1)]=structuredClone(value);
    }
    return item;
  };
  globalThis.game={ready:true,version:'14.370',system:{id:'pf2e',version:'8.7.0'},
    user:{isGM:true,id:'gm'},world:{id:'test'},items:new Map([[item.id,item]]),actors:new Map(),
    scenes:new Map(),settings:{get:()=> 'noABP'},i18n:{lang:'en',has:()=>false,localize:k=>k}};
  globalThis.CONFIG={PF2E:{weaponTraits:{agile:'Agile',finesse:'Finesse',magical:'Magical'},
    rarityTraits:{common:'Common',uncommon:'Uncommon'},actorSizes:{sm:'Small',med:'Medium',lg:'Large'},
    weaponCategories:{martial:'Martial',simple:'Simple'},weaponGroups:{sword:'Sword',bow:'Bow'},
    baseWeaponTypes:{dogslicer:'Dogslicer'},otherWeaponTags:{implement:'Implement'},
    damageTypes:{slashing:'Slashing',fire:'Fire',bleed:'Bleed'}}};
  globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
  return {item,source,doc,writes};
}
