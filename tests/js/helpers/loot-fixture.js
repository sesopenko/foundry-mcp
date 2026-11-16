/** PF2e-specific inert loot8.7.0 source fixture; no prepared Actor state. */
export function lootFixture() {
  const docs=new Map(), sources=new Map();
  const actor=uuid=>{
    const a={uuid,id:'base',documentName:'Actor',name:'Chest',type:'loot',parent:null,folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,
      toObject(){throw Error('Loot Actor source must not be read');}};
    docs.set(uuid,a);return a;
  };
  const add=(a,id,type,system={})=>{
    const source={name:id,type,system};sources.set(a.uuid+id,source);
    const item={uuid:a.uuid+'.Item.'+id,id,documentName:'Item',name:id,type,parent:a,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
    docs.set(item.uuid,item);a.items.set(id,item);return item;
  };
  const base=actor('Actor.base');add(base,'bag','backpack',{containerId:null});add(base,'coins','treasure',{quantity:0,containerId:'bag',description:{value:'<p>Exact coins.</p>'}});
  const scene={uuid:'Scene.s',id:'s',name:'Room',documentName:'Scene',tokens:new Map(),testUserPermission:()=>true};docs.set(scene.uuid,scene);
  for(const [i,quantity] of [7,19,0].entries()){
    const owner=i===2?base:actor(`Scene.s.Token.t${i}.Actor.base`);
    if(i<2){add(owner,'bag','backpack',{containerId:null});add(owner,'coins','treasure',{quantity,containerId:'bag',description:{value:`<p>Coins ${quantity}.</p>`}});}
    const token={uuid:`Scene.s.Token.t${i}`,id:`t${i}`,name:'Chest',documentName:'Token',parent:scene,actor:owner,baseActor:base,isLinked:i===2,testUserPermission:()=>true};
    scene.tokens.set(token.id,token);docs.set(token.uuid,token);
  }
  globalThis.game={ready:true,version:'14.370',system:{id:'pf2e',version:'8.7.0'},user:{isGM:true},actors:new Map([['base',base]]),items:new Map(),folders:new Map(),scenes:new Map([['s',scene]]),packs:new Map()};
  globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
  return {base,scene,add,docs,sources,actor};
}
