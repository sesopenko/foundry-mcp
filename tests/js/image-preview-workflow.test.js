import test from 'node:test';
import assert from 'node:assert/strict';
import {createWorkflowFixture} from './fixtures/image-preview-workflow.js';

test('workflow fixture uses real paged journal and image handlers with multichunk cleanup',async t=>{
  const image={source:'data',directory:'assets',src:'assets/opaque.png'};
  const f=createWorkflowFixture({image,data_base64:Buffer.alloc(90000,71).toString('base64'),html:'<p>prefix</p><img src="assets/opaque.png">'});
  t.after(()=>f.close());
  let id=0;
  const rpc=async(method,params={})=>(await f.rpc({id:String(++id),method,params}));
  const first=(await rpc('readJournalPage',{page_uuid:'JournalEntry.fixture.JournalEntryPage.page',max_chars:20,select:{}})).result;
  assert.equal(first.complete,false);
  assert.ok(first.next_cursor);
  let content=first.content,page=first;
  while(!page.complete){
    page=(await rpc('readJournalPage',{page_uuid:first.page_uuid,max_chars:20,select:{},cursor:page.next_cursor})).result;
    content+=page.content;
  }
  assert.equal(content,f.page.text.content);
  const browse=(await rpc('browseJournalImages',{directory:'assets'})).result;
  assert.deepEqual(browse.entries[0].image,image);
  const begin=(await rpc('beginImagePreviewTransfer',{image})).result;
  assert.equal(begin.chunk_count,3);
  for(let index=0;index<3;index++){
    const part=(await rpc('readImagePreviewChunk',{transfer_id:begin.transfer_id,index,offset:index*begin.chunk_bytes,
      length:Math.min(begin.chunk_bytes,begin.size_bytes-index*begin.chunk_bytes)})).result;
    assert.equal(Buffer.from(part.data_base64,'base64').length,part.length);
  }
  assert.equal((await rpc('fixture.stats')).result.busy,false);
});
