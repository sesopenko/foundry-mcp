/** PF2e-specific combined-reader fixture, F14.369/PF2e8.6.1, no gameplay writes. */
import assert from 'node:assert/strict';
import {readActor,getActorTypes} from '../../../foundry-module/scripts/actors.js';

export function integratedFixture(type='character',context='world'){
 const source={name:'Integrated Actor',type,system:{abilities:type==='character'?null:{},details:{level:{value:2},biography:{appearance:'<p>Character original 😀 appearance.</p>'},creature:{value:'<p>Familiar original creature.</p>'},blurb:'NPC blurb',publicNotes:'<p>NPC original public notes.</p>',privateNotes:'<p>NPC private notes.</p>'},attributes:{ac:{value:15},hp:{value:7,max:20,temp:0}},skills:{acrobatics:{rank:1,base:3}},resources:{focus:{value:1}},...(type==='familiar'?{master:{id:'master',ability:'cha'}}:{})}};
 const current={name:source.name,type,system:{abilities:Object.fromEntries(['str','dex','con','int','wis','cha'].map(key=>[key,{mod:3,base:2}])),attributes:{ac:{value:23,breakdown:'Current AC',details:''},hp:{value:5,max:30,temp:2}},saves:Object.fromEntries(['fortitude','reflex','will'].map(key=>[key,{value:9,totalModifier:10,breakdown:'Current save',rank:1}])),perception:{value:8,totalModifier:9,breakdown:'Current Perception',vision:true,rank:1},movement:{speeds:Object.fromEntries(['land','burrow','climb','fly','swim','travel'].map(mode=>[mode,['land','travel'].includes(mode)?{value:25,base:20,type:mode,source:null}:null]))},skills:{acrobatics:{slug:'acrobatics',label:'Acrobatics',value:8,totalModifier:9,dc:18,breakdown:'Current skill',lore:false,itemId:null}},resources:{focus:{value:1,max:2,cap:3}}}};
 const docs=new Map(),itemSources=new Map(),reads={source:0,current:0};
 const prohibited=()=>{throw Error('Mutation, roll, preparation or getter prohibited');};
 const actor={documentName:'Actor',id:'a',uuid:'Actor.a',name:source.name,type,system:{...current.system,actions:[]},folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject(flag){reads[flag?'source':'current']++;if(type==='familiar')assert.equal(flag,true);return structuredClone(flag?source:current);},update:prohibited,prepareData:prohibited,getRollData:prohibited,rollInitiative:prohibited};
 Object.defineProperty(actor,'master',{get:prohibited});
 if(context==='pack'){actor.uuid='Compendium.test.actors.Actor.a';actor.compendium={collection:'test.actors',title:'Actors',testUserPermission:()=>true};}
 let selector={actor_uuid:actor.uuid};
 if(context==='token'){const base={documentName:'Actor',id:'base',uuid:'Actor.base',name:'Base',type,testUserPermission:()=>true};const scene={documentName:'Scene',uuid:'Scene.s',name:'Inactive',active:false,testUserPermission:()=>true};actor.uuid='Scene.s.Token.t.Actor.a';const token={documentName:'Token',id:'t',uuid:'Scene.s.Token.t',name:'Token',parent:scene,actor,baseActor:base,isLinked:false,testUserPermission:()=>true};actor.token=token;docs.set(token.uuid,token);selector={token_uuid:token.uuid};}
 docs.set(actor.uuid,actor);
 const master={documentName:'Actor',id:'master',uuid:'Actor.master',name:'Master',type:'character',items:new Map(),folder:null,compendium:null,testUserPermission:()=>true,toObject:prohibited};docs.set(master.uuid,master);
 function add(id,itemType,system,name='Same contributor'){
  const data={name,type:itemType,system:{...system,rules:[]}};
  const item={documentName:'Item',id,uuid:actor.uuid+'.Item.'+id,name:'Displayed '+name,type:itemType,parent:actor,folder:null,compendium:null,system:itemType==='effect'?{expired:false}:{},testUserPermission:()=>true,toObject(flag){return structuredClone(flag?data:{...data,system:{...data.system,cast:{focusPoints:0}}});},update:prohibited,roll:prohibited,prepareData:prohibited};
  actor.items.set(id,item);itemSources.set(id,data);docs.set(item.uuid,item);return item;
 }
 add('action','action',{actionType:{value:'passive'},actions:{value:null},category:type==='familiar'?'familiar':null,traits:{value:[],otherTags:[]},description:{value:'<p>Exact action description.</p>'}});
 add('feat','feat',{category:'classfeature',level:{value:1,taken:1}});
 add('lore','lore',{mod:{value:4},proficient:{value:1},variants:{},traits:{otherTags:[]}},'Terrain Lore');
 if(type!=='familiar')current.system.skills['terrain-lore']={slug:'terrain-lore',label:'Terrain Lore',attribute:'int',value:10,totalModifier:11,dc:21,breakdown:'Current Lore total',lore:true,itemId:'lore',rank:1,armor:false,base:4,mod:11,visible:true,note:''};
 add('weapon','weapon',{containerId:null,quantity:1,price:{value:{gp:2},per:1}});
 add('effect','effect',{duration:{value:-1,unit:'unlimited',expiry:null,sustained:false},badge:null,context:null});
 add('condition','condition',{value:{isValued:true,value:2},persistent:null,references:{parent:null,children:[],overrides:[],overriddenBy:[]},overrides:[]});
 const entry=add('entry','spellcastingEntry',{prepared:{value:'prepared',flexible:false},slots:{slot1:{value:0,max:2,prepared:[{id:'spell',expended:false},{id:'spell',expended:true}]}},autoHeightenLevel:{value:null}});
 add('spell','spell',{level:{value:1},traits:{value:[]},location:{value:entry.id,heightenedLevel:3,autoHeightenLevel:null,signature:false},ritual:null});
 if(type==='character')add('background','background',{trainedSkills:{value:['acrobatics'],lore:['Terrain Lore']},items:{}});
 const origin=type==='npc'?add('melee','melee',{bonus:{value:12},action:'strike',attackEffects:{value:[]}}):{id:'generated',uuid:actor.uuid+'.Item.generated',documentName:'Item',type:'weapon',parent:actor,testUserPermission:()=>true};
 if(type!=='familiar')actor.system.actions=[{type:'strike',slug:'strike',label:'Generated Strike',glyph:'A',description:'Current Strike description',ready:true,canAttack:true,totalModifier:11,breakdown:'Current attack',visible:true,handsAvailable:true,sourceId:'melee',attackRollType:'Attack',item:origin,options:[],domains:[],traits:[],weaponTraits:[],variants:[{penalty:0,label:'First',roll:prohibited}],altUsages:[],attack:prohibited,damage:prohibited,critical:prohibited}];
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor],['master',master]]),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
 return {actor,master,source,current,itemSources,selector,reads,docs};
}

export async function integratedPages(type='character',context='world'){
 const f=integratedFixture(type,context),registry=await getActorTypes(),sections=registry.actor_sections.map(row=>row.name),pages=[];
 const before=JSON.stringify([f.source,f.current,[...f.itemSources]]);
 let cursor;do{const page=await readActor({...f.selector,sections,limit:7,max_bytes:48000,...(cursor?{cursor}:{})});assert.ok(Buffer.byteLength(JSON.stringify(page))<=48000);pages.push(page);cursor=page.pagination.next_cursor;assert.ok(pages.length<300);}while(cursor);
 assert.equal(JSON.stringify([f.source,f.current,[...f.itemSources]]),before,'Combined read must not mutate source/current documents');
 return {pages,sections,source:f.source,current:f.current,itemSources:[...f.itemSources],selector:f.selector,actor_uuid:f.actor.uuid,master_uuid:f.master.uuid,item_uuids:Object.fromEntries([...f.actor.items].map(([id,item])=>[id,item.uuid]))};
}
