import test from 'node:test';
import assert from 'node:assert/strict';
import {PDFUpload} from '../../foundry-module/scripts/pdfUpload.js';
import {pdfRequest,setPdfSocket,handlePdfMessage} from '../../foundry-module/scripts/pdfChannel.js';

function gm() { globalThis.game={user:{isGM:true},settings:{get:()=> 'private'}}; }
test('PDF upload uses bounded slices and acknowledged bytes with one request in flight',async()=>{
 gm(); let accepted=0,seq=0,inflight=0,max=0;const progress=[],slices=[];
 const request=async(type,data)=>{
  inflight++;max=Math.max(max,inflight);await Promise.resolve();inflight--;
  if(type.endsWith('authorize')) return {type:'pdf.upload.authorize_ack'};
  if(type.endsWith('begin')) return {upload_id:'opaque',chunk_bytes:32768,accepted_bytes:0};
  if(type.endsWith('chunk')) {
   assert.equal(data.seq,seq++);accepted+=atob(data.data_base64).length;
   assert.equal(progress.at(-1).accepted,accepted-atob(data.data_base64).length);
   return {type:'pdf.upload.ack',upload_id:'opaque',next_seq:seq,accepted_bytes:accepted};
  }
  return {document_id:'doc',status:'queued'};
 };
 const bytes=new Uint8Array(70000);
 const file={name:'Book.pdf',size:bytes.length,slice(start,end){slices.push(end-start);return new Blob([bytes.slice(start,end)]);},arrayBuffer(){throw Error('must not read entire file');}};
 await new PDFUpload(request).upload(file,p=>progress.push(p));
 assert.equal(max,1);assert.ok(slices.every(n=>n<=32768));
 assert.deepEqual(progress.map(p=>p.accepted),[0,32768,65536,70000,70000]);
 assert.equal(progress.at(-1).stage,'queued');
});
test('player helpers fail, forged acknowledgments fail, role loss stops subsequent chunks',async()=>{
 gm();game.user.isGM=false;let called=false;
 await assert.rejects(new PDFUpload(async()=>{called=true;}).upload({name:'x.pdf',size:1}),/GM-only/);assert.equal(called,false);
 gm();let chunks=0;
 const request=async type=>{
  if(type.endsWith('begin'))return {upload_id:'id',chunk_bytes:32768,accepted_bytes:0};
  if(type.endsWith('chunk')) {chunks++;return {type:'pdf.upload.ack',upload_id:'id',next_seq:1,accepted_bytes:999999};}
  return {};
 };
 await assert.rejects(new PDFUpload(request).upload(new File([new Uint8Array(5)],'a.pdf')),/acknowledgment/);
 assert.equal(chunks,1);
});
test('PDF channel requires ready socket, correlates requests, rejects on disconnect and checks roles',async()=>{
 gm();setPdfSocket(null);await assert.rejects(pdfRequest('pdf.upload.list'),/authenticated/);
 let sent;setPdfSocket({readyState:1,send(v){sent=JSON.parse(v);}});
 const pending=pdfRequest('pdf.upload.list');
 assert.equal(handlePdfMessage({id:'ordinary',result:1}),false);
 handlePdfMessage({type:'pdf.upload.list_ack',request_id:sent.request_id,documents:[]});
 assert.deepEqual((await pending).documents,[]);
 const old=pdfRequest('pdf.upload.list');setPdfSocket(null);await assert.rejects(old,/disconnected/);
 game.user.isGM=false;assert.throws(()=>pdfRequest('pdf.upload.list'),/GM-only/);
});
