// Executed only by the fixed test-world runner after its GM/runtime admission.
const marker = 'itemEditingFixture';
const flags = {'foundry-mcp':{[marker]:run}};
const marked = doc => doc?.getFlag('foundry-mcp',marker) === run;
const roots = () => [...game.scenes.filter(marked),...game.items.filter(marked),...game.actors.filter(marked),...game.users.filter(marked)];
const state = (globalThis.__itemEditingChecks ??= new Map());
const lifecycle = state.get(run) ?? {pending:0,closed:false};
state.set(run,lifecycle);
const guard = () => {
  if (game.world.id !== 'test' || !game.ready || !game.user.isGM || location.origin !== 'http://localhost:30000') throw Error('World guard');
};
const checkRoot = doc => {
  guard();
  if (!marked(doc) || !['Item','Actor','User','Scene'].includes(doc.documentName)) throw Error('Foreign root');
  if (doc.documentName==='Actor' && (doc.type!=='loot' || doc.items.size>1 || [...doc.items.values()].some(i=>!marked(i)))) throw Error('Foreign inventory');
  if (doc.documentName==='Scene' && (doc.active || doc.tokens.size>3 || [...doc.tokens.values()].some(t=>!marked(t)))) throw Error('Foreign scene');
  if (doc.documentName==='User' && (doc.role!==CONST.USER_ROLES.PLAYER || doc.name!=='Item reader '+run)) throw Error('Foreign user');
};
const encoded = result => {
  const text = JSON.stringify(result);
  if (text.length>16000) throw Error('Fixture result budget');
  return Array.from({length:Math.ceil(text.length/800)},(_,i)=>text.slice(i*800,(i+1)*800));
};
if(args.action==='cleanup'){
  lifecycle.closed=true;
  for(let i=0;lifecycle.pending && i<100;i++)await new Promise(resolve=>setTimeout(resolve,100));
  const docs=roots();
  if(lifecycle.pending || docs.length>3 || new Set(docs.map(d=>d.documentName)).size!==docs.length)throw Error('Ambiguous cleanup');
  for(const d of docs)checkRoot(d);
  for(const d of docs){checkRoot(d);await d.delete();}
  state.delete(run);
  return encoded({remaining:roots().length});
}
if(args.action==='create'||args.action==='createPlayer'){
  if(lifecycle.closed || lifecycle.pending || roots().length)throw Error('Run active');
  lifecycle.pending++;
  try{
    const reference=await foundry.utils.fromUuid('Compendium.pf2e.equipment-srd.Item.olwngGXM3hpgoLEP');
    if(reference?.type!=='weapon')throw Error('Missing Dogslicer');
    const base = reference.toObject(true);
    const weapon = {type:'weapon',name:'Dogslicer',img:base.img,flags,system:{...base.system,
      runes:{potency:1,striking:1,property:['wounding']},description:{value:'A chipped blade.'},
      identification:{status:'identified',unidentified:{name:'Jagged Goblin Blade',img:base.img,data:{description:{value:'A notched edge.'}}}}}};
    if(args.action==='createPlayer'){
      guard();const player=await User.implementation.create({name:'Item reader '+run,role:CONST.USER_ROLES.PLAYER,password:args.password,flags});
      checkRoot(player);
      guard();const owner=await Actor.implementation.create({type:'loot',name:'MCP temporary relics',flags,
        ownership:{default:0,[player.id]:CONST.DOCUMENT_OWNERSHIP_LEVELS.OBSERVER},items:[weapon]});checkRoot(owner);
      guard();const scene=await Scene.implementation.create({name:'MCP temporary relic chamber',flags,
        active:false,navigation:false,width:1000,height:1000,padding:0});checkRoot(scene);
      const specs=[];
      for(let i=0;i<3;i++){
        const t=await owner.getTokenDocument({actorLink:i===2,name:'Fixture '+i,x:i*180,y:100},{parent:scene});
        const data=t.toObject(true);delete data._id;data.flags={...data.flags,...flags};specs.push(data);
      }
      guard();const tokens=await scene.createEmbeddedDocuments('Token',specs);checkRoot(scene);
      const item=owner.items.find(marked);
      const copies=tokens.filter(t=>!t.isLinked),shared=tokens.filter(t=>t.isLinked);
      if(copies.length!==2 || shared.length!==1 || tokens.some(t=>t.baseActor?.uuid!==owner.uuid))throw Error('Unexpected token fixture');
      return encoded({player:player.id,actor:owner.uuid,item_id:item.id,base:{item_uuid:item.uuid},
        copies:[...copies,...shared].map(t=>({item_uuid:t.actor.items.get(item.id).uuid,token_uuid:t.uuid}))});
    }
    guard();const solo=await Item.implementation.create(weapon);checkRoot(solo);
    if(lifecycle.closed)throw Error('Run closed');
    guard();const owner=await Actor.implementation.create({type:'loot',name:'MCP Item editing fixture',flags,items:[weapon]});
    checkRoot(owner);
    const owned=owner.items.find(marked);
    if(!owned || !marked(solo) || lifecycle.closed)throw Error('Missing fixture');
    return encoded({solo:solo.uuid,owned:owned.uuid});
  }finally{lifecycle.pending--;}
}
const item=await foundry.utils.fromUuid(args.uuid);
if(!marked(item)||item.documentName!=='Item'||item.type!=='weapon'||lifecycle.closed)throw Error('Wrong fixture Item');
if(item.parent)checkRoot(item.parent);
if(args.action==='invariants'){
  const s=item.toObject(true);
  return encoded({rules:s.system.rules,altImage:s.system.identification.unidentified?.img,
    modifier:s.system.damage.modifier??null,per:s.system.price.per??null,ownerSize:item.parent?.items.size??null,
    specific:s.system.specific,runes:s.system.runes,material:s.system.material});
}
if(args.action==='sheet'){
  const app=item.sheet;
  app.render(true);
  let node;
  for(let i=0;i<120;i++){
    await new Promise(resolve=>setTimeout(resolve,50));
    node=document.getElementById(app.id);
    if(node?.querySelector('[data-property="system.damage.dice"]'))break;
  }
  try{
    if(!node)throw Error('Fixture sheet missing');
    const control = path => {
      const el=node.querySelector('[data-property="'+path+'"],[name="'+path+'"]');
      if(!el)throw Error('Sheet control '+path);
      return el;
    };
    const value = path => {
      const el=control(path);
      return el.type==='checkbox'?el.checked:el.value;
    };
    const menu = el => ({editable:!el.disabled && !el.classList.contains('readonly'),
      codes:Array.from(el.options,o=>o.value)});
    const menus=Object.fromEntries(['system.range','system.material','system.runes.potency',
      'system.runes.striking','system.publication.license'].map(path=>[path,menu(control(path))]));
    const slots=[...node.querySelectorAll('select[name^="system.runes.property."]')];
    const text=path=>node.querySelector('[data-edit="'+path+'"]')?.textContent.trim();
    const shown = {
      name:value('name'),image:node.querySelector('[data-edit="img"]').getAttribute('src'),title:app.title,
      level:value('system.level.value'),rarity:value('system.traits.rarity'),
      traits:JSON.parse(node.querySelector('[name="system.traits.value"]').getAttribute('value')).map(tag=>tag.id),
      quantity:value('system.quantity'),hands:value('system.usage.value'),bulk:value('system.bulk.value'),size:value('system.size'),
      price:value('system.price.value'),category:value('system.category'),group:value('system.group'),base:value('system.baseItem'),
      range:value('system.range'),material:value('system.material'),potency:value('system.runes.potency'),striking:value('system.runes.striking'),
      runes:slots.map(el=>el.value),slotEditors:slots.map(el=>!el.disabled && !el.classList.contains('readonly')),
      menus:{...menus,...(slots.length?{'system.runes.property':menu(slots[0])}:{})},
      specific:value('system.specific'),dice:value('system.damage.dice'),die:value('system.damage.die'),type:value('system.damage.damageType'),
      splash:value('system.splashDamage.value'),persistent:[...node.querySelectorAll('[data-persistent-field]')].map(el=>el.value),
      tags:[...node.querySelector('[data-property="system.traits.otherTags"]').closest('.form-group').querySelectorAll('li.tag')].map(el=>el.textContent.trim()),
      publication:['title','authors','license','remaster'].map(k=>value('system.publication.'+k)),
      status:value('system.identification.status'),unidentified:value('system.identification.unidentified.name'),
      description:text('system.description.value'),alternate:text('system.identification.unidentified.data.description.value'),
    };
    return encoded(shown);
  }finally{await app.close();}
}
throw Error('Unknown fixture step');
