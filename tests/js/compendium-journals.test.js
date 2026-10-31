import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture} from './helpers/compendiumFixture.js';
import {listCompendiums,searchCompendiumJournals,getCompendiumJournalContents,readCompendiumJournalPage,resolveCompendiumJournalReference} from '../../foundry-module/scripts/compendiumJournals.js';
import {getJournalContents} from '../../foundry-module/scripts/journals.js';
import {handleRpcMessage} from '../../foundry-module/scripts/foundryBridge.js';

test('pack discovery and entry-name search load only indexes, with explicit capabilities',async()=>{
  const f=fixture();const list=await listCompendiums();
  assert.deepEqual(list.nodes[0].searchable_fields,['entry_name','page_name','text']);
  const r=await searchCompendiumJournals({pack_id:f.pack.collection,query:'duplicate',field:'entry_name',limit:1});
  assert.equal(r.matches.length,1);assert.equal(r.complete,false);assert.equal(r.batch_match_count,12);
  assert.equal(f.counts().loads,0);
  assert.equal(r.matches[0].page_uuid,null);
});

test('page-title scans paginate matches and work without losing duplicate identities',async()=>{
  const f=fixture(),args={pack_id:f.pack.collection,query:'dCs BY leV',max_entries:2,limit:1};
  let cursor=null;const found=[];let calls=0;
  do{const before=f.counts().loads,r=await searchCompendiumJournals({...args,cursor});
    assert.ok(f.counts().loads-before<=2);assert.equal(r.scanned_text_pages,6);
    assert.ok(Buffer.byteLength(JSON.stringify(r))<=8000);assert.ok(r.matches.every(m=>!('excerpt'in m)));
    found.push(...r.matches.map(m=>m.page_uuid));cursor=r.next_cursor;calls++;assert.ok(calls<=12);
  }while(cursor);
  assert.equal(found.length,12);assert.equal(new Set(found).size,12);
});

test('batch revisions, index changes, selection/bounds and malformed cursors are rejected',async()=>{
  const f=fixture(),args={pack_id:f.pack.collection,query:'dc',max_entries:2,limit:1};
  const first=await searchCompendiumJournals(args);
  for(const changed of [{select:{excerpts:true}},{query:'other'},{limit:2},{max_entries:1},{max_bytes:9000}])
    await assert.rejects(searchCompendiumJournals({...args,...changed,cursor:first.next_cursor}),/inputs/);
  await assert.rejects(searchCompendiumJournals({...args,cursor:'!'}),/next_cursor/);
  f.entries[0].pages.contents[0].name='Changed';
  await assert.rejects(searchCompendiumJournals({...args,cursor:first.next_cursor}),/batch changed/);
  f.entries[0].name='Index changed';
  await assert.rejects(searchCompendiumJournals({...args,cursor:first.next_cursor}),/index changed/);
});

test('exact source survives small chunks, Unicode, HTML tables and selected evidence',async()=>{
  const f=fixture(),page=f.entries[0].pages.contents[0],args={pack_id:f.pack.collection,page_uuid:page.uuid,max_chars:77,select:{references:true,source_metadata:true}};
  let cursor=null,content='',calls=0;
  do{const r=await readCompendiumJournalPage({...args,cursor});assert.equal(r.offset,content.length);
    assert.ok(!/[\uD800-\uDBFF]$/.test(r.content));assert.ok(Buffer.byteLength(JSON.stringify(r))<=8000);
    content+=r.content;cursor=r.next_cursor;calls++;assert.ok(calls<100);
  }while(cursor);
  assert.equal(content,page.text.content);
  const first=await readCompendiumJournalPage(args);page.text.content+='edit';
  await assert.rejects(readCompendiumJournalPage({...args,cursor:first.next_cursor}),/changed/);
  await assert.rejects(readCompendiumJournalPage({...args,page_uuid:page.uuid+'#anchor'}),/without anchor/);
  await assert.rejects(readCompendiumJournalPage({...args,source:'markdown'}),/not stored/);
});

test('contents share ordered navigation and scoped headings, without opening world selectors',async()=>{
  const f=fixture();const r=await getCompendiumJournalContents({pack_id:f.pack.collection,journal_id:f.entries[0].id,limit:1});
  assert.equal(r.pages[0].page_uuid,f.entries[0].pages.contents[0].uuid);assert.equal(r.pages[0].name,'DCs by Level');
  assert.ok(!('heading_outline'in r.pages[0]));assert.ok(r.next_cursor);
  await assert.rejects(getJournalContents({journal_id:f.entries[0].id}),/not found/);
  const other={...f.pack,collection:'other.rules'};game.packs.set(other.collection,other);
  await assert.rejects(readCompendiumJournalPage({pack_id:other.collection,page_uuid:r.pages[0].page_uuid}),/selected pack/);
});

test('empty, denied, missing, media, work bounds, unsupported packs and non-PF2e journals',async()=>{
  const f=fixture(),args={pack_id:f.pack.collection,query:'DC',max_entries:1};
  f.entries[0].pages.contents[0].testUserPermission=()=>false;
  f.entries[0].pages.contents[1].type='image';
  const r=await searchCompendiumJournals(args);assert.equal(r.unsupported_pages,1);assert.equal(r.failures[0].status,'PermissionDenied');assert.equal(r.coverage_complete,false);
  assert.ok(!r.matches.some(m=>m.page_id==='p0'||m.page_id==='p1'));
  const deniedPage=f.entries[0].pages.contents[0];Object.defineProperty(deniedPage,'name',{get(){throw Error('DENIED_READ');}});
  await searchCompendiumJournals(args);
  await assert.rejects(readCompendiumJournalPage({pack_id:f.pack.collection,page_uuid:deniedPage.uuid}),/readable/);
  f.pack.testUserPermission=()=>false;
  assert.equal((await listCompendiums()).denied_packs,1);
  await assert.rejects(searchCompendiumJournals(args),/OBSERVER/);
  f.pack.testUserPermission=()=>true;f.pack.documentName='Macro';
  await assert.rejects(searchCompendiumJournals(args),/JournalEntry/);
  await assert.rejects(searchCompendiumJournals({...args,pack_id:'missing'}),/Relist/);
  fixture();game.system={id:'other'};
  assert.equal((await searchCompendiumJournals({pack_id:'test.rules',query:'no match'})).matches.length,0);
  game.user.isGM=false;await assert.rejects(listCompendiums(),/GM/);
});

test('body search is explicit, excerpts selective and entry loading failures remain gaps',async()=>{
  const f=fixture(),args={pack_id:f.pack.collection,query:'20',field:'text',max_entries:1,select:{excerpts:true}};
  const r=await searchCompendiumJournals(args);assert.equal(r.matches.length,3);assert.equal(r.matches[0].excerpt_derived,true);
  f.pack.getDocument=async()=>{throw Error('loading failure');};
  const failed=await searchCompendiumJournals(args);assert.equal(failed.coverage_complete,false);assert.ok(failed.failures.length);
});

test('lazy relative journal links keep named canonical destination and source membership',async()=>{
  const f=fixture(),page=f.entries[0].pages.contents[0],args={pack_id:f.pack.collection,page_uuid:page.uuid,target:'.p1'};
  page.parent.pages.contents[1].documentName='JournalEntryPage';
  const r=await resolveCompendiumJournalReference(args);assert.equal(r.status,'resolved');assert.equal(r.next_call.tool,'read_compendium_journal_page');
  assert.equal(r.next_call.arguments.pack_id,f.pack.collection);
  page.text.content='changed';await assert.rejects(resolveCompendiumJournalReference(args),/absent/);
});

test('RPC exposes only fixed read handlers, rejects mutation/unknown parameters',async()=>{
  fixture();const r=await handleRpcMessage({id:1,method:'listCompendiums',params:{}});assert.equal(r.result.nodes.length,1);
  const unknown=await handleRpcMessage({id:2,method:'searchCompendiumJournals',params:{pack_id:'test.rules',query:'dc',update:{}}});assert.ok(unknown.error);
  const mutation=await handleRpcMessage({id:3,method:'updateCompendium',params:{}});assert.ok(mutation.error);
});

test('an earlier page losing permission while later entries load is never disclosed',async()=>{
  const f=fixture(),original=f.pack.getDocument;
  f.pack.getDocument=async id=>{const value=await original(id);if(id==='j01')f.entries[0].pages.contents[0].testUserPermission=()=>false;return value;};
  await assert.rejects(searchCompendiumJournals({pack_id:f.pack.collection,query:'DC',max_entries:2}),/changed during loading/);
});

test('work bound, missing/unsupported pages and pack permissions after awaits',async()=>{
  const f=fixture(),args={pack_id:f.pack.collection,query:'DC',max_entries:1};
  f.entries[0].pages.size=10001;
  await assert.rejects(searchCompendiumJournals(args),/10000/);
  f.entries[0].pages.size=3;f.entries[0].pages.contents[0].type='image';
  await assert.rejects(readCompendiumJournalPage({pack_id:f.pack.collection,page_uuid:f.entries[0].pages.contents[0].uuid}),/Only text pages/);
  await assert.rejects(readCompendiumJournalPage({pack_id:f.pack.collection,page_uuid:f.entries[0].uuid+'.JournalEntryPage.missing'}),/Refresh/);
  const getIndex=f.pack.getIndex;f.pack.getIndex=async()=>{const r=await getIndex();f.pack.testUserPermission=()=>false;return r;};
  await assert.rejects(searchCompendiumJournals(args),/access changed/);
});

test('Markdown body search uses UUID labels without matching target IDs',async()=>{
  const f=fixture();for(const page of f.entries[0].pages.contents)page.text={markdown:'@UUID[Compendium.hidden.pack.Item.secretid]{Visible label}',format:2};
  const args={pack_id:f.pack.collection,journal_id:f.entries[0].id,field:'text'};
  assert.equal((await searchCompendiumJournals({...args,query:'secretid'})).matches.length,0);
  assert.equal((await searchCompendiumJournals({...args,query:'Visible label'})).matches.length,3);
});
