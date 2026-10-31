import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readChatMessages,readChatMessageContent,sendChatMessage,normalizeChatHTML} from '../../foundry-module/scripts/chat.js';
import {webcrypto} from 'node:crypto';
globalThis.crypto??=webcrypto;
function setup(rows) {
  globalThis.game={ready:true,version:'14.369',world:{id:'test'},user:{id:'gm',isGM:true},messages:new Map(rows.map(([id,timestamp,content,visible=true])=>[id,{id,timestamp,content,visible,isContentVisible:visible,author:{id:'gm',name:'GM'},toObject(){return {timestamp,speaker:{},whisper:[]};}}]))};
}
test('exclusive pagination, equal timestamps, deleted anchor and later polling',()=>{
  setup([['b',1,'b'],['a',1,'a'],['c',2,'c'],['hidden',3,'secret',false]]);
  const first=readChatMessages({limit:1});
  assert.deepEqual(first.messages.map(m=>m.id),['a']);
  game.messages.delete('a');
  const rest=readChatMessages({cursor:first.cursor});
  assert.deepEqual(rest.messages.map(m=>m.id),['b','c']);
  assert.equal(rest.has_more,false);
  assert.equal(readChatMessages({cursor:rest.cursor}).messages.length,0);
  assert.throws(()=>readChatMessages({after_id:'a'}));
});
test('oversized exact fragments and edit revision',async()=>{
  setup([['a',1,'x'.repeat(9000)]]);
  assert.equal(readChatMessages({}).messages[0].content,null);
  const first=await readChatMessageContent({message_id:'a'});
  assert.equal(first.content.length,1000);
  game.messages.get('a').content='changed';
  await assert.rejects(readChatMessageContent({message_id:'a',offset:1000,revision:first.revision}));
});
test('incremental cursors include newly observed equal and older timestamps',()=>{
  setup([['z',10,'old']]);
  const end=readChatMessages({});
  const old=game.messages.get('z');
  game.messages.set('a',{...old,id:'a',content:'new equal'});
  game.messages.set('backdated',{...old,id:'backdated',timestamp:1,content:'new older'});
  const newer=readChatMessages({cursor:end.cursor});
  assert.deepEqual(newer.messages.map(m=>m.id),['backdated','a']);
  assert.equal(readChatMessages({cursor:newer.cursor}).messages.length,0);
});
test('a newly observed batch sorts equal timestamps by lexical ID, not creation order',()=>{
  setup([]);
  const cursor=readChatMessages({}).cursor;
  for(const id of ['z','a'])game.messages.set(id,{id,timestamp:10,content:id,visible:true,isContentVisible:true,toObject:()=>({timestamp:10,speaker:{}})});
  assert.deepEqual(readChatMessages({cursor}).messages.map(m=>m.id),['a','z']);
});
test('content fragments never split surrogate pairs',async()=>{
  setup([['a',1,'x'.repeat(999)+'😀'+'z']]);
  const first=await readChatMessageContent({message_id:'a'});
  assert.equal(first.content,'x'.repeat(999));
  const next=await readChatMessageContent({message_id:'a',offset:first.next_offset,revision:first.revision});
  assert.equal(next.content,'😀z');
});
test('complete pagination stays within byte bounds with exact IDs and clipped names',()=>{
  setup(Array.from({length:25},(_,i)=>[String(i).padStart(2,'0'),i,'😀'.repeat(300)]));
  game.messages.get('00').author.name='😀'.repeat(2000);
  const ids=[]; let cursor;
  for(let calls=0;calls<30;calls++) {
    const page=readChatMessages({max_bytes:2000,limit:10,...(cursor?{cursor}:{})});
    assert.ok(Buffer.byteLength(JSON.stringify(page))<=2000);
    ids.push(...page.messages.map(m=>m.id));
    if(!cursor) assert.equal(page.messages[0].names_truncated,true);
    cursor=page.cursor;
    if(!page.has_more) break;
  }
  assert.equal(ids.length,25);
  assert.equal(new Set(ids).size,25);
  const edited=game.messages.get('00'); edited.content='edit';
  assert.equal(readChatMessages({cursor}).messages.length,0);
  const newCollection=new Map(game.messages);game.messages=newCollection;
  assert.throws(()=>readChatMessages({cursor}),/Cursor belongs/);
  game.user.isGM=false;
  assert.throws(()=>readChatMessages({}),/authorized GM/);
});
test('HTML policies reject active elements, wrappers and unsupported attributes',()=>{
  for(const element of [
    {tagName:'IMG',attributes:[]}, {tagName:'SCRIPT',attributes:[]},
    {tagName:'BODY',attributes:[{name:'onload',value:'alert(1)'}]},
    {tagName:'SPAN',attributes:[{name:'class',value:'secret'}]},
    {tagName:'P',attributes:[{name:'style',value:'background-color:url(example)'}]},
    {tagName:'P',attributes:[{name:'style',value:'position:fixed'}]},
    {tagName:'TD',attributes:[{name:'colspan',value:'101'}]},
  ]) {
    globalThis.DOMParser=class {parseFromString(){return {querySelectorAll:()=>[element],body:{innerHTML:'x'}};}};
    assert.throws(()=>normalizeChatHTML('x'));
  }
  const elements=[{tagName:'H2',attributes:[{name:'style',value:'text-align:center;font-family:Arial;font-size:18px'}]},{tagName:'TD',attributes:[{name:'colspan',value:'2'}]}];
  globalThis.DOMParser=class {parseFromString(){return {querySelectorAll:()=>elements,body:{innerHTML:'normalized'}};}};
  assert.equal(normalizeChatHTML('original'),'normalized');
});
test('all five audience/speaker choices, duplicate attempts and invalid character',async()=>{
  setup([]);
  game.user.name='GM';
  game.users=new Map([['gm',{id:'gm',isGM:true}],['player',{id:'player',isGM:false}]]);
  game.actors=new Map([['pc',{id:'pc',name:'Hero',type:'character',testUserPermission:()=>true}]]);
  globalThis.DOMParser=class {parseFromString(content){return {body:{innerHTML:content},querySelectorAll:()=>[]};}};
  globalThis.CONST={CHAT_MESSAGE_STYLES:{IC:2,OOC:1}};
  const writes=[];
  globalThis.foundry={documents:{ChatMessage:{implementation:{async create(data){
    writes.push(data);
    return {id:'created',author:game.user,toObject:()=>({...data,timestamp:1})};
  }}}}};
  const modes=['Public as User','private to game masters','blind to game masters','self only','public as character'];
  for(const [i,mode] of modes.entries()) {
    const p={request_id:`test-send-request-${i}`,mode,content:'<p>Hello</p>',...(i===4?{actor_id:'pc'}:{})};
    const result=await sendChatMessage(p);
    assert.equal(result.author.id,'gm');
    assert.equal(result.speaker.actor,i===4?'pc':null);
    assert.deepEqual(result.whisper,[1,2,3].includes(i)?['gm']:[]);
    assert.equal(result.blind,i===2);
    assert.equal(writes[i].style,i===4?2:1);
    await sendChatMessage(p);
    assert.equal(writes.length,i+1);
    await assert.rejects(sendChatMessage({...p,content:'different'}));
  }
  await assert.rejects(sendChatMessage({request_id:'missing-character-test',mode:modes[4],actor_id:'missing',content:'x'}));
  assert.equal(writes.length,5);
  game.user={id:'other-gm',name:'Other',isGM:true};
  await assert.rejects(sendChatMessage({request_id:'test-send-request-0',mode:modes[0],content:'<p>Hello</p>'}),/Reuse request_id/);
});
test('concurrent retries coalesce and persisted flags reconcile a loaded send',async()=>{
  setup([]);
  game.system={id:'another-system'}; // Core chat is intentionally system-neutral.
  game.user.name='GM';game.users=new Map([['gm',game.user]]);game.actors=new Map();
  globalThis.CONST={CHAT_MESSAGE_STYLES:{IC:2,OOC:1}};
  globalThis.DOMParser=class {parseFromString(content){return {querySelectorAll:()=>[],body:{innerHTML:content,textContent:content}};}};
  let writes=0;
  globalThis.foundry={documents:{ChatMessage:{implementation:{async create(data){
    writes++;
    return {id:'new',author:game.user,toObject:()=>({...data,timestamp:1})};
  }}}}};
  const request={request_id:'concurrent-send-key',mode:'Public as User',content:'<p>Hi</p>'};
  const replies=await Promise.all([sendChatMessage(request),sendChatMessage(request)]);
  assert.equal(writes,1);assert.equal(replies[0].id,replies[1].id);
  const values=[game.world.id,game.user.id,request.mode,request.content,null];
  const fingerprint=Buffer.from(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(values)))).toString('hex');
  const m={id:'persisted',visible:true,isContentVisible:true,author:game.user,toObject:()=>({timestamp:1,speaker:{alias:'GM'}}),getFlag:(_scope,key)=>key==='requestId'?request.request_id:fingerprint};
  game.messages=new Map([['persisted',m]]); // New collection simulates a fresh ledger.
  assert.equal((await sendChatMessage(request)).id,'persisted');assert.equal(writes,1);
  await assert.rejects(sendChatMessage({...request,content:'different'}),/different or unverifiable/);
  game.actors.set('denied',{type:'character',testUserPermission:()=>false});
  await assert.rejects(sendChatMessage({...request,request_id:'denied-character-key',mode:'public as character',actor_id:'denied'}),/owned character/);
  await assert.rejects(sendChatMessage({...request,request_id:'immediate-roll-key',content:'[[1d20]]'}),/Only deferred/);
  await assert.rejects(sendChatMessage({...request,request_id:'unknown-field-key',delete:true}),/Unknown input/);
  assert.equal(writes,1);
});
