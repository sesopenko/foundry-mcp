import test from 'node:test';
import assert from 'node:assert/strict';
import {registerPDFManager} from '../../foundry-module/scripts/pdfManager.js';
import {setPdfSocket,handlePdfMessage} from '../../foundry-module/scripts/pdfChannel.js';

function manager() {
 const hooks=new Map();let menu;
 globalThis.document={createElement(){return {children:[],listeners:{},addEventListener(name,fn){this.listeners[name]=fn;},append(child){this.children.push(child);}};}};
 globalThis.game={user:{isGM:true},settings:{get:()=> 'test-password',registerMenu(ns,key,value){menu=value;}}};
 globalThis.Hooks={on(name,callback){hooks.set(name,callback);}};
 globalThis.foundry={applications:{api:{DialogV2:class{constructor(options){this.options=options;}}}}};
 registerPDFManager();
 const controls=new Map();
 const root={querySelector(selector){if(!controls.has(selector))controls.set(selector,{textContent:'',children:[],listeners:{},addEventListener(name,fn){this.listeners[name]=fn;},removeAttribute(name){if(name==='value')this.value=undefined;},replaceChildren(){this.children=[];},append(child){this.children.push(child);}});return controls.get(selector);}};
 const application=new menu.type();
 hooks.get('renderPDFLibraryManager')(application,{querySelector:()=>root});
 const status=root.querySelector('[data-pdf="status"]');
 status.control=name=>root.querySelector(`[data-pdf="${name}"]`);
 status.file=root.querySelector('[name="pdf-file"]');
 return status;
}

test('PDF manager checks authorization and displays a connected empty library automatically',async()=>{
 const sent=[];
 setPdfSocket({readyState:1,send(raw){const m=JSON.parse(raw);sent.push(m.type);queueMicrotask(()=>handlePdfMessage({type:m.type==='pdf.upload.authorize'?'pdf.upload.authorize_ack':'pdf.upload.list_ack',request_id:m.request_id,documents:[],next_offset:null}));}});
 const status=manager();
 assert.equal(status.textContent,'Connecting to PDF library…');
 await new Promise(resolve=>setTimeout(resolve,0));
 assert.deepEqual(sent,['pdf.upload.authorize','pdf.upload.list']);
 assert.equal(status.textContent,'Connected. No PDFs uploaded yet.');
 setPdfSocket(null);
});

test('PDF manager displays the actual connection failure instead of an assumed initial error',async()=>{
 setPdfSocket(null);
 const status=manager();
 await new Promise(resolve=>setTimeout(resolve,0));
 assert.equal(status.textContent,'Connect an authenticated GM bridge first.');
});

for (const outcome of ['ready','failed','transport_error']) {
 test(`PDF progress stops after ${outcome}`,async()=>{
  setPdfSocket({readyState:1,send(raw){
   const m=JSON.parse(raw);
   const responses={
    'pdf.upload.authorize':{type:'pdf.upload.authorize_ack'},
    'pdf.upload.list':{type:'pdf.upload.list_ack',documents:[],next_offset:null},
    'pdf.upload.begin':{type:'pdf.upload.begin_ack',upload_id:'test',chunk_bytes:32768,accepted_bytes:0},
    'pdf.upload.chunk':{type:'pdf.upload.ack',upload_id:'test',next_seq:1,accepted_bytes:5},
    'pdf.upload.finish': outcome==='transport_error'
      ? {type:'pdf.upload.error',message:'Connection lost'}
      : {type:'pdf.upload.index_status',document_id:'doc',status:outcome},
    'pdf.upload.cancel':{type:'pdf.upload.cancel_ack'}
   };
   queueMicrotask(()=>handlePdfMessage({...responses[m.type],request_id:m.request_id}));
  }});
  const status=manager();
  await new Promise(resolve=>setTimeout(resolve,0));
  status.file.files=[new File([new Uint8Array(5)],'test.pdf')];
  await status.control('upload').listeners.click();
  assert.equal(status.control('progress').value,outcome==='ready'?1:0);
  assert.equal(status.control('upload').disabled,false);
  setPdfSocket(null);
 });
}

for (const confirmed of [false,true]) {
 test(`PDF deletion ${confirmed?'confirms and refreshes':'cancel leaves library unchanged'}`,async()=>{
  let deleted=false;const sent=[];
  const book={document_id:'a'.repeat(32),revision:'b'.repeat(64),name:'<book>.pdf',status:'ready',page_count:1};
  setPdfSocket({readyState:1,send(raw){const m=JSON.parse(raw);sent.push(m);
   let response;
   if(m.type==='pdf.upload.authorize')response={type:'pdf.upload.authorize_ack'};
   else if(m.type==='pdf.upload.delete'){deleted=true;response={type:'pdf.upload.delete_ack',document_id:book.document_id,deleted:true};}
   else response={type:'pdf.upload.list_ack',documents:deleted?[]:[book],next_offset:null};
   queueMicrotask(()=>handlePdfMessage({...response,request_id:m.request_id}));
  }});
  const status=manager();
  foundry.applications.api.DialogV2.confirm=async options=>{
   assert.ok(options.content.includes('&lt;book&gt;.pdf'));
   assert.ok(!options.content.includes('<book>'));
   return confirmed;
  };
  await new Promise(resolve=>setTimeout(resolve,0));
  const button=status.control('documents').children[0].children[0];
  await button.listeners.click();
  assert.equal(deleted,confirmed);
  const requests=sent.filter(m=>m.type==='pdf.upload.delete');
  assert.equal(requests.length,confirmed?1:0);
  if(confirmed){assert.equal(requests[0].revision,book.revision);assert.equal(status.control('documents').children.length,0);}
  assert.equal(status.control('upload').disabled,false);
  setPdfSocket(null);
 });
}

test('replacement uploads keep the replacement result after list refresh',async()=>{
 setPdfSocket({readyState:1,send(raw){const m=JSON.parse(raw);
  const responses={
   'pdf.upload.authorize':{type:'pdf.upload.authorize_ack'},
   'pdf.upload.list':{type:'pdf.upload.list_ack',documents:[],next_offset:null},
   'pdf.upload.begin':{type:'pdf.upload.begin_ack',upload_id:'duplicate',chunk_bytes:32768,accepted_bytes:0},
   'pdf.upload.chunk':{type:'pdf.upload.ack',upload_id:'duplicate',next_seq:1,accepted_bytes:5},
   'pdf.upload.finish':{type:'pdf.upload.index_status',document_id:'existing',status:'ready',replacing:true}
  };
  queueMicrotask(()=>handlePdfMessage({...responses[m.type],request_id:m.request_id}));
 }});
 const status=manager();await new Promise(resolve=>setTimeout(resolve,0));
 status.file.files=[new File([new Uint8Array(5)],'same.pdf')];
 await status.control('upload').listeners.click();
 assert.match(status.textContent,/Existing PDF replaced/);
 assert.equal(status.control('progress').value,1);
 setPdfSocket(null);
});

test('new upload shows processing stages, refreshes the pending list and preserves completion',async()=>{
 let uploaded=false,polls=0;const stages=[];
 setPdfSocket({readyState:1,send(raw){const m=JSON.parse(raw);let response;
  const book={document_id:'new',revision:'b'.repeat(64),name:'New.pdf',status:polls?'ready':'queued',page_count:polls?1:0};
  if(m.type==='pdf.upload.authorize')response={type:'pdf.upload.authorize_ack'};
  if(m.type==='pdf.upload.list')response={type:'pdf.upload.list_ack',documents:uploaded?[book]:[],next_offset:null};
  if(m.type==='pdf.upload.begin')response={type:'pdf.upload.begin_ack',upload_id:'new-upload',chunk_bytes:32768,accepted_bytes:0};
  if(m.type==='pdf.upload.chunk')response={type:'pdf.upload.ack',upload_id:'new-upload',next_seq:1,accepted_bytes:5};
  if(m.type==='pdf.upload.finish'){uploaded=true;response={type:'pdf.upload.index_status',document_id:'new',status:'queued',replacing:false};}
  if(m.type==='pdf.upload.index_status'){polls++;response={type:'pdf.upload.index_status',document_id:'new',status:'ready'};}
  queueMicrotask(()=>handlePdfMessage({...response,request_id:m.request_id}));
 }});
 const status=manager();await new Promise(resolve=>setTimeout(resolve,0));
 let text=status.textContent;
 Object.defineProperty(status,'textContent',{get:()=>text,set:value=>{text=value;stages.push(value);}});
 status.file.files=[new File([new Uint8Array(5)],'New.pdf')];
 const work=status.control('upload').listeners.click();
 await new Promise(resolve=>setTimeout(resolve,0));
 assert.match(status.textContent,/Waiting to process/);
 assert.equal(status.control('documents').children.length,1);
 assert.equal(status.control('progress').value,undefined); // indeterminate while server works
 await work;
 assert.match(status.textContent,/Ready \/ Searchable. PDF added/);
 assert.equal(status.control('progress').value,1);
 assert.ok(stages.some(value=>value.includes('Waiting to process')));
 setPdfSocket(null);
});
