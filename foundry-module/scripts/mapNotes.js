/** Authorized core14 Note identities and labels; no journal-body hydration.
 * Public includedInLevel/label/entry/page contracts: map-note-identities.md.
 */
import {mapNamed} from './mapBrowse.js';

const ID=/^[A-Za-z0-9_-]{1,128}$/;
function fail(code,message){const e=new Error(message);e.rpcError={code,type:code,message};throw e;}
const invalid=()=>fail('MapDataUnavailable','Public Note identity or metadata is malformed; repair the Scene notes.');
function permission(doc){
  if(typeof doc?.testUserPermission!=='function')fail('UnsupportedCapability','Public Note/linked document permissions are unavailable.');
  return doc.testUserPermission(game.user,'OBSERVER')===true;
}
function identity(doc,kind){
  if(typeof doc.id!=='string'||!ID.test(doc.id)||doc.uuid!==(kind==='JournalEntry'?'JournalEntry.'+doc.id:doc.parent?.uuid+'.JournalEntryPage.'+doc.id)
      ||typeof doc.name!=='string')invalid();
  return{[kind==='JournalEntry'?'journal_uuid':'page_uuid']:doc.uuid,...mapNamed(doc.name)};
}
function target(note,source){
  let status='unlinked',journal=null,page=null,denied=false,witness=[];
  if(source.entryId!==undefined&&source.entryId!==null&&source.entryId!==''){
    if(typeof source.entryId!=='string'||!ID.test(source.entryId))invalid();
    const entry=note.entry;
    if(!entry)status='missing_entry';
    else if(!permission(entry)){status='denied_entry';denied=true;}
    else {
      if(entry.id!==source.entryId)invalid();
      journal=identity(entry,'JournalEntry');witness.push(entry.uuid,entry.name);
      status='linked_entry';
      if(source.pageId!==undefined&&source.pageId!==null&&source.pageId!==''){
        if(typeof source.pageId!=='string'||!ID.test(source.pageId))invalid();
        const linked=note.page;
        if(!linked)status='missing_page';
        else if(!permission(linked)){status='denied_page';denied=true;}
        else{
          if(linked.id!==source.pageId||linked.parent!==entry)invalid();
          page=identity(linked,'JournalEntryPage');witness.push(linked.uuid,linked.name);status='linked_page';
        }
      }
    }
  }
  let label=null;
  if(!denied){label=note.label;if(typeof label!=='string')invalid();}
  return{public:{label:label===null?null:mapNamed(label).name,label_truncated:label!==null&&Array.from(label).length>256,
    target_status:status,journal,page},witness:[status,label,witness],denied};
}

/** Snapshot every authorized Note once; aliases are assigned per complete level. */
export function projectMapNotes(scene,levels){
  const collection=scene.getEmbeddedCollection('Note');
  if(!Array.isArray(collection?.contents)||!(collection.invalidDocumentIds instanceof Set))fail('UnsupportedCapability','Public Note collection availability is unavailable.');
  const notes=[],unavailable=[...collection.invalidDocumentIds].sort(),privateWitness=[];
  let partial=unavailable.length>0;
  for(const note of collection.contents){
    if(typeof note.id!=='string'||!ID.test(note.id)||note.parent!==scene||note.uuid!==scene.uuid+'.Note.'+note.id)invalid();
    if(!permission(note)){unavailable.push(note.id);partial=true;continue;}
    if(typeof note.toObject!=='function'||typeof note.includedInLevel!=='function')fail('UnsupportedCapability','Public Note serialization/level query is unavailable.');
    const source=note.toObject(true);
    if(!Number.isFinite(source.x)||!Number.isFinite(source.y))invalid();
    const applicable=[];
    for(const level of levels){const included=note.includedInLevel(level);if(typeof included!=='boolean')invalid();if(included)applicable.push(level.id);}
    const link=target(note,source);partial||=link.denied;
    notes.push({note_uuid:note.uuid,x:source.x,y:source.y,applicable,...link.public});
    privateWitness.push([note.id,source.x,source.y,source.entryId??null,source.pageId??null,source.text??null,
      source.levels instanceof Set?[...source.levels]:source.levels,applicable,link.witness]);
  }
  if(new Set(collection.contents.map(n=>n.id)).size!==collection.contents.length)invalid();
  notes.sort((a,b)=>a.note_uuid<b.note_uuid?-1:1);
  const byLevel=levels.map(level=>({level_id:level.id,entries:notes.filter(n=>n.applicable.includes(level.id)).map((n,i)=>{
    const {applicable,...entry}=n;return{kind:'note',key:'N'+(i+1),level_id:level.id,...entry};
  })}));
  return{by_level:byLevel,private_witness:privateWitness,unavailable:unavailable.sort(),partial};
}
