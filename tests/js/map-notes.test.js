import test from 'node:test';
import assert from 'node:assert/strict';
import {projectMapNotes} from '../../foundry-module/scripts/mapNotes.js';

function fixture(){
  globalThis.game={user:{id:'gm',isGM:true}};
  const scene={id:'scene',uuid:'Scene.scene'},level={id:'floor',uuid:'Scene.scene.Level.floor',parent:scene};
  const other={id:'other',uuid:'Scene.scene.Level.other',parent:scene};
  const collection={contents:[],invalidDocumentIds:new Set()};scene.getEmbeddedCollection=type=>{assert.equal(type,'Note');return collection;};
  const entry={id:'entry',uuid:'JournalEntry.entry',name:'Journal',testUserPermission:()=>true};
  Object.defineProperty(entry,'content',{get(){throw Error('Journal body must not be read');}});
  const page={id:'page',uuid:'JournalEntry.entry.JournalEntryPage.page',parent:entry,name:'Page',testUserPermission:()=>true};
  Object.defineProperty(page,'text',{get(){throw Error('Page body must not be read');}});
  const state={scene,level,other,entry,page,collection,labels:0,sources:0,queries:0};
  state.note=(id,options={})=>{
    const source={x:100,y:200,levels:[],entryId:'entry',pageId:null,text:'',...options.source};
    const note={id,uuid:scene.uuid+'.Note.'+id,parent:scene,allowed:options.allowed!==false,
      testUserPermission(){return note.allowed;},
      toObject(){assert.ok(note.allowed);state.sources++;return structuredClone(source);},
      includedInLevel(selected){assert.ok(selected===level||selected===other);state.queries++;return options.applicable?options.applicable.includes(selected.id):true;},
      get entry(){return options.entry===undefined?entry:options.entry;},
      get page(){return options.page===undefined?(source.pageId?page:null):options.page;},
      get label(){state.labels++;if(options.label) return options.label();return source.text||note.page?.name||note.entry?.name||'';}};
    collection.contents.push(note);return note;
  };
  state.read=()=>projectMapNotes(scene,[level,other]);return state;
}

test('authorized level notes receive stable UUID-order aliases with distinct duplicate target pins',()=>{
  const f=fixture();f.note('z');f.note('a');f.note('b',{applicable:['other']});
  const result=f.read(),floor=result.by_level[0].entries,other=result.by_level[1].entries;
  assert.deepEqual(floor.map(n=>[n.key,n.note_uuid]),[['N1','Scene.scene.Note.a'],['N2','Scene.scene.Note.z']]);
  assert.deepEqual(other.map(n=>n.key),['N1','N2','N3']);
  assert.equal(floor[0].journal.journal_uuid,floor[1].journal.journal_uuid);
  assert.equal(floor[0].label,'Journal');assert.equal(floor[0].target_status,'linked_entry');
  assert.equal(f.queries,6);assert.equal(f.sources,3);assert.equal(result.partial,false);
});

test('entry/page permissions precede label getters and denied target names are never read',()=>{
  const f=fixture();
  const deniedEntry={id:'entry',uuid:'JournalEntry.entry',testUserPermission:()=>false,
    get name(){throw Error('Denied entry name read');}};
  const deniedPage={id:'page',parent:f.entry,testUserPermission:()=>false,
    get name(){throw Error('Denied page name read');}};
  f.note('a',{entry:deniedEntry,label:()=>{throw Error('Denied fallback label read');}});
  f.note('b',{source:{pageId:'page'},page:deniedPage,label:()=>{throw Error('Denied page fallback read');}});
  const result=f.read(),rows=result.by_level[0].entries;
  assert.deepEqual(rows.map(n=>n.target_status),['denied_entry','denied_page']);
  assert.ok(rows.every(n=>n.label===null&&n.page===null));assert.equal(rows[0].journal,null);
  assert.equal(result.partial,true);assert.equal(f.labels,0);
});

test('unlinked/missing entries/pages stay explicit and permitted label override/fallback remain separate',()=>{
  const f=fixture();f.note('a',{source:{entryId:null,text:'Own label'},entry:null});
  f.note('b',{entry:null});f.note('c',{source:{pageId:'page'},page:null});
  f.note('d',{source:{pageId:'page'}});f.note('e',{source:{text:'Override'}});
  const rows=f.read().by_level[0].entries;
  assert.deepEqual(rows.map(n=>n.target_status),['unlinked','missing_entry','missing_page','linked_page','linked_entry']);
  assert.equal(rows[0].label,'Own label');assert.equal(rows[3].label,'Page');assert.equal(rows[4].label,'Override');
  assert.equal(rows[3].page.page_uuid,'JournalEntry.entry.JournalEntryPage.page');
});

test('long malicious labels are untrusted plain data with explicit clipping; private witness stays full',()=>{
  const f=fixture();const label='<script>unsafe data</script>'+ 'α'.repeat(300);f.note('a',{source:{text:label}});
  const result=f.read(),row=result.by_level[0].entries[0];
  assert.equal(Array.from(row.label).length,256);assert.equal(row.label_truncated,true);
  assert.ok(JSON.stringify(result.private_witness).includes(label));assert.equal(row.note_uuid,'Scene.scene.Note.a');
});

test('denied/invalid Note documents expose only aggregate scope and never read source or labels',()=>{
  const f=fixture();f.note('hidden',{allowed:false,label:()=>{throw Error('Denied label');}});
  f.collection.invalidDocumentIds.add('private-invalid');
  const result=f.read();assert.equal(result.partial,true);assert.equal(f.sources,0);assert.equal(f.labels,0);
  assert.deepEqual(result.by_level[0].entries,[]);
});

test('public applicability is queried on owning Level objects and unavailable API fails explicitly',()=>{
  const f=fixture();const note=f.note('a');note.includedInLevel=undefined;
  assert.throws(f.read,e=>e.rpcError?.code==='UnsupportedCapability');
  note.includedInLevel=()=>null;assert.throws(f.read,e=>e.rpcError?.code==='MapDataUnavailable');
});
