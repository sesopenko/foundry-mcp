/** Core14 chat document APIs: https://foundryvtt.com/api/v14/classes/foundry.documents.ChatMessage.html
 * Uses public visible/isContentVisible, toObject, author, create and getFlag.
 * No PF2e interpretation, enrichment, roll evaluation or deletion.
 */
import { fail, validateParams } from './actorReadUtils.js';

function ready() {
  if (!globalThis.game?.ready || !game.messages) fail('NotReady', 'Wait for the existing world.');
  if (!game.user?.isGM) fail('PermissionDenied', 'Connect an authorized GM.');
  if (!String(game.version).startsWith('14.')) fail('UnsupportedVersion', 'Chat requires Foundry14.');
}
const bytes = value => new TextEncoder().encode(JSON.stringify(value)).length;
const key = m => [m.timestamp, m.id];
const compare = (a,b) => a[0]-b[0] || (a[1]<b[1]?-1:a[1]>b[1]?1:0);
const histories = new WeakMap();
/** Browser-local observation order: first batch timestamp/ID, later batches appended.
 * IDs only are retained, never message bodies or a second game-state cache.
 */
function history(messages) {
  let state=histories.get(game.messages);
  if(!state || state.world!==game.world.id || state.user!==game.user.id) {
    state={world:game.world.id,user:game.user.id,epoch:crypto.randomUUID(),ids:new Map()};
    histories.set(game.messages,state);
  }
  const fresh=messages.filter(m=>!state.ids.has(m.id)).sort((a,b)=>compare(key(a),key(b)));
  if(state.ids.size+fresh.length>50000) fail('HistoryTooLarge','Chat exceeds 50000 observed messages. Archive history in Foundry and reload; no history was silently truncated.');
  for(const m of fresh) state.ids.set(m.id,state.ids.size+1);
  return state;
}
function cursor(state,position) {
  return JSON.stringify({world:state.world,user:state.user,epoch:state.epoch,position});
}
const clip = value => value==null?null:[...String(value)].slice(0,128).join('');
function identity(m) {
  const s=m.toObject(true);
  return {id:m.id, timestamp:s.timestamp, author:{id:m.author?.id??null,name:clip(m.author?.name)},
    names_truncated:[m.author?.name,s.speaker?.alias].some(v=>v!=null&&[...String(v)].length>128),
    speaker:{actor:s.speaker?.actor??null,alias:clip(s.speaker?.alias),scene:s.speaker?.scene??null,token:s.speaker?.token??null},
    whisper:s.whisper??[],blind:s.blind===true};
}
/** Read loaded visible history in stable observation order; exclusive anchors. */
export function readChatMessages(p={}) {
  validateParams(p,['after_id','cursor','limit','max_bytes']);
  ready();
  const limit=p.limit??10, max=p.max_bytes??8000;
  if(!Number.isInteger(limit)||limit<1||limit>100||!Number.isInteger(max)||max<2000||max>48000) fail('InvalidRequest','Invalid bounds.');
  if(game.messages.size>50000) fail('HistoryTooLarge','Loaded chat exceeds 50000 messages; archive in Foundry before reading.');
  const messages=[...game.messages.values()].filter(m=>m.visible && m.isContentVisible);
  const state=history(messages);
  let boundary=0;
  if(p.after_id) {
    const anchor=messages.find(m=>m.id===p.after_id);
    if(!anchor) fail('MissingAnchor','Anchor missing or invisible; restart history or use returned cursor.');
    boundary=state.ids.get(anchor.id);
  }
  if(p.cursor) {
    if(p.after_id) fail('InvalidRequest','Use cursor or after_id.');
    let c; try { c=JSON.parse(p.cursor); } catch { fail('InvalidCursor','Restart history.'); }
    if(c?.world!==state.world || c?.user!==state.user || c?.epoch!==state.epoch || !Number.isSafeInteger(c.position) || c.position<0 || c.position>state.ids.size) fail('InvalidCursor','Cursor belongs to another browser session/world/user or is malformed. Restart history or anchor an existing message ID.');
    boundary=c.position;
  }
  const pending=messages.filter(m=>state.ids.get(m.id)>boundary).sort((a,b)=>state.ids.get(a.id)-state.ids.get(b.id));
  const result={messages:[],cursor:cursor(state,boundary),has_more:pending.length>0,scope:'loaded_visible_history'};
  for(const m of pending) {
    const row={...identity(m),content:m.content,content_available_separately:false};
    result.messages.push(row);
    const next=state.ids.get(m.id);
    const nextCursor=cursor(state,next);
    if(bytes({...result,cursor:nextCursor})>max) {
      result.messages.pop();
      if(!result.messages.length) {
        result.messages.push({...identity(m),content:null,content_available_separately:true});
        if(bytes({...result,cursor:nextCursor})>max) fail('ResponseTooLarge','Message identity exceeds max_bytes; raise it up to 48000.');
      } else break;
    }
    boundary=next;
    if(result.messages.length>=limit) break;
  }
  result.cursor=cursor(state,boundary);
  result.has_more=pending.some(m=>state.ids.get(m.id)>boundary);
  return result;
}
/** Exact UTF-16 fragments; revision prevents silently joining edited content. */
export async function readChatMessageContent(p) {
  validateParams(p,['message_id','offset','revision']);
  ready();
  const m=game.messages.get(p.message_id);
  if(!m?.visible||!m.isContentVisible) fail('DocumentNotFound','Message missing or invisible.');
  const text=m.content;
  const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text))),v=>v.toString(16).padStart(2,'0')).join('');
  ready();
  if(game.messages.get(p.message_id)!==m || !m.visible || !m.isContentVisible || m.content!==text) fail('StaleContent','Message changed during reading; restart at offset 0.');
  if(p.revision && p.revision!==digest) fail('StaleContent','Message edited; restart at offset 0 without revision.');
  const offset=p.offset??0;
  if(!Number.isInteger(offset)||offset<0||offset>text.length||offset>0&&!p.revision) fail('InvalidRequest','Use returned offset and revision.');
  if(offset>0 && /[\uDC00-\uDFFF]/.test(text[offset]) && /[\uD800-\uDBFF]/.test(text[offset-1])) fail('InvalidRequest','Offset splits a Unicode character; use returned next_offset.');
  let end=Math.min(text.length,offset+1000);
  if(end<text.length && /[\uD800-\uDBFF]/.test(text[end-1]) && /[\uDC00-\uDFFF]/.test(text[end])) end--;
  const content=text.slice(offset,end);
  return {message_id:m.id,content,revision:digest,next_offset:offset+content.length<text.length?offset+content.length:null};
}

const sendLedgers=new WeakMap();
/** Validate basic editor HTML without enriching inline notation or executing content.
 * Browser normalization precedes Foundry's documented HTMLField sanitization.
 */
export function normalizeChatHTML(content) {
  const doc=new DOMParser().parseFromString(content,'text/html');
  const tags=new Set(['P','BR','H1','H2','H3','H4','H5','H6','DIV','SPAN','STRONG','B','EM','I','U','S','SUB','SUP','BLOCKQUOTE','PRE','CODE','UL','OL','LI','TABLE','CAPTION','COLGROUP','COL','THEAD','TBODY','TFOOT','TR','TH','TD','HR']);
  for(const el of doc.querySelectorAll('*')) {
    const wrapper=['HTML','HEAD','BODY'].includes(el.tagName);
    if(!wrapper && !tags.has(el.tagName)) fail('InvalidHTML','Use basic text HTML; images, links and executable HTML are excluded.');
    for(const a of el.attributes) {
      const tableSpan=['TH','TD'].includes(el.tagName)&&['colspan','rowspan'].includes(a.name)&&/^(?:[1-9]|[1-9]\d|100)$/.test(a.value);
      const style=a.name==='style' && a.value.split(';').every(x=>!x.trim()||/^\s*(text-align|font-size|font-family|font-weight|font-style|text-decoration|color|background-color)\s*:\s*[a-zA-Z0-9 #.,%()"'-]+$/.test(x) && !/url|expression|var\(/i.test(x));
      if(wrapper || !(tableSpan||style)) fail('InvalidHTML','Only basic text styles and table spans (1–100) are accepted; no event/class/data attributes.');
    }
  }
  if(/\[\[(?!\/(?:r|gmr|br|sr)\s)/.test(doc.body.textContent??'')) fail('InvalidHTML','Only deferred inline rolls from create_pf2e_inline_roll are accepted; immediate rolls can evaluate while rendering.');
  return doc.body.innerHTML;
}

/** Explicit audience/speaker creation using configured public Document implementation.
 * No PF2e-specific API calls: core14 character type filtering is an explicit tool
 * restriction. Stored request flags provide deduplication while the message exists;
 * a deleted/archived message or unavailable collection cannot prove a prior send.
 */
export async function sendChatMessage(p) {
  validateParams(p,['request_id','mode','content','actor_id']);
  ready();
  if(typeof p.request_id!=='string'||!/^[a-zA-Z0-9-]{16,64}$/.test(p.request_id)) fail('InvalidRequest','Use a unique request_id of 16–64 letters/digits/hyphens.');
  if(typeof p.content!=='string'||!p.content.trim()||new TextEncoder().encode(p.content).length>16000) fail('InvalidRequest','Provide 1–16000 UTF-8 bytes of supported HTML.');
  const modes=['Public as User','private to game masters','blind to game masters','self only','public as character'];
  if(!modes.includes(p.mode)) fail('InvalidRequest','Choose a published mode.');
  const context={world:game.world.id,user:game.user,collection:game.messages};
  const fingerprint=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify([context.world,context.user.id,p.mode,p.content,p.actor_id??null])))),v=>v.toString(16).padStart(2,'0')).join('');
  ready();
  if(game.world.id!==context.world || game.user!==context.user || game.messages!==context.collection) fail('ContextChanged','World or connected user changed; verify intended world before sending.');
  let sends=sendLedgers.get(game.messages);
  if(!sends) { sends=new Map(); sendLedgers.set(game.messages,sends); }
  const previous=sends.get(p.request_id);
  if(previous) {
    if(previous.fingerprint!==fingerprint) fail('RequestConflict','Reuse request_id only with identical input.');
    return previous.promise;
  }
  const existing=[...game.messages.values()].filter(m=>m.getFlag('foundry-mcp','requestId')===p.request_id);
  if(existing.length) {
    if(existing.length!==1 || existing[0].author?.id!==game.user.id || existing[0].getFlag('foundry-mcp','requestDigest')!==fingerprint) fail('RequestConflict','Request ID already exists with different or unverifiable input; inspect chat before sending.');
    const m=existing[0];
    if(!m.visible || !m.isContentVisible) fail('PermissionDenied','Previously sent message is not visible; do not resend.');
    return {...identity(m),mode:p.mode,request_id:p.request_id};
  }
  if(sends.size>=1000) fail('SendLedgerFull','Reload only after reconciling outstanding sends.');
  const content=normalizeChatHTML(p.content);
  let speaker={alias:game.user.name};
  if(p.mode==='public as character') {
    const actor=game.actors.get(p.actor_id);
    if(!actor) fail('DocumentNotFound','Discover a world character using search_actors.');
    if(actor.type!=='character') fail('UnsupportedCharacterType','Public as character requires a world Actor with type character; discover that type or use Public as User.');
    if(!actor.testUserPermission(game.user,'OWNER')) fail('PermissionDenied','Select an owned character Actor.');
    speaker={actor:actor.id,alias:actor.name};
  } else if(p.actor_id) fail('InvalidRequest','actor_id requires public as character.');
  const whisper=p.mode==='self only'?[game.user.id]:p.mode.includes('game masters')?[...game.users.values()].filter(u=>u.isGM).map(u=>u.id):[];
  if(p.mode.includes('game masters')&&!whisper.length) fail('PermissionDenied','No GM recipients available.');
  if(whisper.length>100) fail('ResponseTooLarge','More than 100 GM recipients; no message was sent.');
  const promise=(async()=>{
    const m=await foundry.documents.ChatMessage.implementation.create({author:game.user.id,content,speaker,whisper,blind:p.mode==='blind to game masters',style:p.mode==='public as character'?CONST.CHAT_MESSAGE_STYLES.IC:CONST.CHAT_MESSAGE_STYLES.OOC,flags:{'foundry-mcp':{requestId:p.request_id,requestDigest:fingerprint}}});
    if(!m) fail('SendOutcomeUnknown','Creation returned no document; inspect chat before sending again.');
    return {...identity(m),mode:p.mode,request_id:p.request_id};
  })();
  sends.set(p.request_id,{fingerprint,promise});
  return promise;
}
