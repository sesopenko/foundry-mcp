// Synthetic chapter. Setup and cleanup use exact per-run flags; the sweep uses public MCP tools.
const key='itemChapterFixture';
const flags={'foundry-mcp':{[key]:run}};
const marked=doc=>doc?.getFlag('foundry-mcp',key)===run;
const roots=()=>[...game.journal.filter(marked),...game.scenes.filter(marked),...game.actors.filter(marked)];
const stateMap=(globalThis.__itemChapterChecks??=new Map());
const state=stateMap.get(run)??{pending:false,closed:false};stateMap.set(run,state);
const guard=()=>{
  if(state.closed||!game.ready||game.world.id!=='test'||!game.user.isGM||location.origin!=='http://localhost:30000')throw Error('Chapter guard');
};
const checked=doc=>{
  if(!marked(doc))throw Error('Foreign root');
  const [collection,limit]=doc.documentName==='Actor'?[doc.items,9]:doc.documentName==='Scene'?[doc.tokens,3]:[doc.pages,3];
  if(doc.documentName==='Scene'&&doc.active || collection.size>limit || [...collection.values()].some(d=>!marked(d)))throw Error('Foreign child');
};
if(args.action==='cleanup'){
  state.closed=true;
  for(let n=0;state.pending&&n<100;n++)await new Promise(r=>setTimeout(r,100));
  const docs=roots();
  if(state.pending||docs.length>4)throw Error('Ambiguous chapter cleanup');
  docs.forEach(checked);
  for(const doc of docs){checked(doc);await doc.delete();}
  stateMap.delete(run);return JSON.stringify({remaining:roots().length});
}
if(args.action!=='create'||roots().length||state.pending||state.closed)throw Error('Unexpected chapter operation');
state.pending=true;
try{
  const blade=await foundry.utils.fromUuid('Compendium.pf2e.equipment-srd.Item.olwngGXM3hpgoLEP');
  const stone=await foundry.utils.fromUuid('Compendium.pf2e.equipment-srd.Item.fo6Yhq5mbQXsnZs0');
  if(blade?.type!=='weapon'||stone?.name!=='Wounding')throw Error('Expected public references');
  const patterns=['Copper pin','Ivory bead','Ashwood grip','Split guard','Horn pommel','Twisted wire','Brass collar'];
  const makeWeapon=(motif,magic)=>({name:motif+' Dogslicer',type:'weapon',img:blade.img,flags,system:{...blade.toObject(true).system,
    runes:{potency:magic?1:0,striking:0,property:magic?['wounding']:[]},
    description:{value:'Workshop mark: '+motif+'. Model @UUID['+blade.uuid+'].'}}});
  const makeActor=async(type,name,items)=>{
    guard();const actor=await Actor.implementation.create({type,name,flags,items});checked(actor);return actor;
  };
  const rune={name:'Engraved keepsake',type:'equipment',img:stone.img,flags,system:{...stone.toObject(true).system,
    description:{value:'A dark crescent on smooth slate. Workshop record @UUID['+stone.uuid+'].'}}};
  const loot=await makeActor('loot','Armory cabinet',[...patterns.map(p=>makeWeapon(p,true)),rune,makeWeapon('Practice',false)]);
  const npc=await makeActor('npc','Vault warden',[...patterns.slice(0,6).map(p=>makeWeapon(p,true)),makeWeapon('Practice',false)]);
  guard();const scene=await Scene.implementation.create({name:'Chapter workshop '+run,active:false,navigation:false,
    width:1000,height:1000,padding:0,flags});checked(scene);
  const specs=[];
  for(const [index,[actor,name,link]] of [[loot,'Cabinet',true],[npc,'Warden',true],[npc,'Gallery guard',false]].entries()){
    const prototype=await actor.getTokenDocument({name,actorLink:link,x:100+index*200,y:100},{parent:scene});
    const data=prototype.toObject(true);delete data._id;data.flags={...data.flags,...flags};specs.push(data);
  }
  guard();const tokens=await scene.createEmbeddedDocuments('Token',specs);checked(scene);
  const placement=(actor,linked)=>{
    const matches=tokens.filter(t=>marked(t) && t.baseActor?.uuid===actor.uuid && t.isLinked===linked);
    if(matches.length!==1)throw Error('Ambiguous chapter placement');
    return matches[0];
  };
  const cabinet=placement(loot,true), warden=placement(npc,true), copy=placement(npc,false);
  const link=t=>'@UUID['+t.uuid+']{'+t.name+'}';
  const phrase='Chapter workshop '+run;
  const pages=[
    ['Armory',phrase+'. '+link(scene)+'. The wall cabinet opens here: '+link(cabinet)+'. The warden stands watch: '+link(warden)+'.'],
    ['Gallery',phrase+'. '+link(scene)+'. A hatch opens onto the same cabinet: '+link(cabinet)+'. The guard on this side: '+link(copy)+'.'],
    ['Sealed stair',phrase+'. The freight ledger mentions a parcel but gives no custodian or inventory location.'],
  ].map(([name,value])=>({name,type:'text',flags,text:{format:1,content:'<p>'+value+'</p>'}}));
  guard();const journal=await JournalEntry.implementation.create({name:phrase,flags,pages});checked(journal);
  return JSON.stringify({journal:journal.id,scene:scene.uuid,owners:[loot.uuid,npc.uuid,copy.actor.uuid]});
}finally{state.pending=false;}
