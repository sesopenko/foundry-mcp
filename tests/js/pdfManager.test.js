import test from 'node:test';
import assert from 'node:assert/strict';
import {registerPDFManager} from '../../foundry-module/scripts/pdfManager.js';
import {setPdfSocket,handlePdfMessage} from '../../foundry-module/scripts/pdfChannel.js';

function manager() {
 const hooks=new Map();let menu;
 globalThis.game={user:{isGM:true},settings:{get:()=> 'test-password',registerMenu(ns,key,value){menu=value;}}};
 globalThis.Hooks={on(name,callback){hooks.set(name,callback);}};
 globalThis.foundry={applications:{api:{DialogV2:class{constructor(options){this.options=options;}}}}};
 registerPDFManager();
 const controls=new Map();
 const root={querySelector(selector){if(!controls.has(selector))controls.set(selector,{textContent:'',listeners:{},addEventListener(name,fn){this.listeners[name]=fn;},removeAttribute(name){if(name==='value')this.value=undefined;},replaceChildren(){},append(){}});return controls.get(selector);}};
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
