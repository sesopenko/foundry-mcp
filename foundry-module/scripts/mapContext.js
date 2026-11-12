/** Private map image context and bounded region candidates; never public MCP DTOs.
 * Uses declared source/schema APIs and project snapshot/resolver interfaces only.
 */
import {mapContext,mapHash,mapBytes,mapCursor,mapOffset} from './mapBrowse.js';
import {readMapSnapshot,selectedMapRevision} from './mapInfo.js';
import {resolvePreviewSource} from './journalImages.js';
import {mapRegionNotes,validateMapCrop} from './mapGeometry.js';

const ID=/^[A-Za-z0-9_-]{1,128}$/;
function fail(code,message){const e=new Error(message);e.rpcError={code,type:code,message};throw e;}
function params(value,keys){
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(k=>!keys.includes(k)))fail('InvalidRequest','Use the private map context contract.');
}
function validate(input,extra=[]){
  params(input,['map','caller_key','expected_revision','expected_reference_digest','max_bytes',...extra]);
  params(input.map,['scene_uuid','level_id','role']);
  const {map,caller_key,expected_revision=null,expected_reference_digest=null,max_bytes=48000}=input;
  if(typeof map.scene_uuid!=='string'||!/^Scene\.[A-Za-z0-9_-]{1,128}$/.test(map.scene_uuid)
    ||typeof map.level_id!=='string'||!ID.test(map.level_id)||!['background','foreground'].includes(map.role)
    ||typeof caller_key!=='string'||!/^[0-9a-f]{64}$/.test(caller_key)
    ||(expected_revision!==null&&(typeof expected_revision!=='string'||expected_revision.length>128))
    ||(expected_reference_digest!==null&&(typeof expected_reference_digest!=='string'||!expected_reference_digest.length||expected_reference_digest.length>128))
    ||!Number.isInteger(max_bytes)||max_bytes<1024||max_bytes>48000)fail('InvalidRequest','Use exact Scene/level/role, trusted caller and bounded private response.');
  return{map,caller_key,expected_revision,expected_reference_digest,max_bytes};
}
function canonical(value){
  return JSON.stringify(value,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)
    ?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v);
}
function mapping(scene,level,source,map,rect){
  if(map.role!=='background')return{status:'unsupported',reason:'foreground_role'};
  if(game.version!=='14.369')return{status:'unsupported',reason:'unverified_build'};
  if(!['sceneX','sceneY','sceneWidth','sceneHeight'].every(k=>typeof rect[k]==='number'&&Number.isFinite(rect[k]))
      ||rect.sceneWidth<=0||rect.sceneHeight<=0)return{status:'unsupported',reason:'invalid_rectangle'};
  const field=globalThis.foundry?.documents?.Level?.schema?.getField?.('textures');
  if(typeof field?.clean!=='function')return{status:'unsupported',reason:'default_schema_unavailable'};
  let initial;
  try{initial=field.clean(undefined,{source});}catch{return{status:'unsupported',reason:'default_schema_unavailable'};}
  if(!source.textures||typeof source.textures!=='object'||Array.isArray(source.textures)
      ||!initial||typeof initial!=='object'||Array.isArray(initial)||canonical(source.textures)!==canonical(initial))
    return{status:'unsupported',reason:'nondefault_placement'};
  return{status:'supported',reason:null};
}
async function capture(input,isCurrent){
  const owner=mapContext(isCurrent),data=readMapSnapshot(input.map.scene_uuid);
  const selected=data.assets.find(l=>l.level_id===input.map.level_id);
  if(!selected)fail(data.unavailable[0].includes(input.map.level_id)?'PermissionDenied':'LevelNotFound','Choose a readable owning Level from get_map_info assets.');
  const scene=game.scenes.get(input.map.scene_uuid.slice(6));
  const level=scene.getEmbeddedCollection('Level').get(input.map.level_id);
  if(!level||level.parent!==scene)fail('MapContextChanged','Selected level changed; refresh map/image info.');
  const source=level.toObject(true),src=source[input.map.role]?.src;
  if(typeof src!=='string'||!src)fail('ImageNotFound','Selected level role has no image; choose a returned usable asset.');
  const revision=await selectedMapRevision(owner,data,input.map.level_id);
  if(input.expected_revision!==null&&input.expected_revision!==revision)fail('MapContextChanged','Map metadata/notes changed; refresh get_map_info and image info.');
  const reference_digest=await mapHash(src);
  if(input.expected_reference_digest!==null&&input.expected_reference_digest!==reference_digest)
    fail('MapContextChanged','Selected map asset reference changed; refresh map/image info.');
  const resolved=await resolvePreviewSource({src},isCurrent);
  if(resolved.world_id!==owner[0]||resolved.user_id!==owner[1])fail('MapContextChanged','Map source belongs to another world/GM; refresh map info.');
  const notes=data.notes.by_level.find(l=>l.level_id===input.map.level_id).entries;
  const alias_digest=await mapHash(notes.map(n=>[n.key,n.note_uuid]));
  const support=mapping(scene,level,source,input.map,data.geometry.scene_rect);
  const placement_digest=await mapHash([game.version,data.geometry.scene_rect,source.textures,support]);
  if(JSON.stringify(mapContext(isCurrent))!==JSON.stringify(owner)||JSON.stringify(readMapSnapshot(input.map.scene_uuid))!==JSON.stringify(data))
    fail('MapContextChanged','Map owner, configuration or notes changed; refresh map/image info.');
  const partial=data.notes.partial||data.unavailable.some(ids=>ids.length);
  return{notes,witness:data,owner,context:{protocol:'map_context.v1',world_id:owner[0],user_id:owner[1],map:input.map,level_uuid:selected.level_uuid,
    image:resolved.image,reference_digest,revision,alias_digest,alias_total:notes.length,rectangle:data.geometry.scene_rect,
    mapping:support,placement_digest,core_version:game.version,scope_status:partial?'partial':'complete',
    source_scope_status:resolved.scope_status==='partial'?'partial':'complete',limitations:partial
      ?['Some selected-map Note/document scope is unavailable; complete candidate streams do not prove exhaustive availability.']:[]}};
}

export async function getMapImageContext(value={},isCurrent=()=>true){
  const input=validate(value),{context}=await capture(input,isCurrent);
  if(mapBytes(context)>input.max_bytes)fail('ResponseTooLarge','Private map identity exceeds the configured frame budget.');
  return context;
}

export async function getMapRegionCandidates(value={},isCurrent=()=>true){
  const input=validate(value,['source_size','crop','source_scope','cursor','limit']);
  params(value.source_size,['width','height']);params(value.crop,['x','y','width','height']);
  const {source_size,crop,source_scope,cursor=null,limit=100}=value;
  if(input.expected_revision===null||typeof source_scope!=='string'||!/^[0-9a-f]{64}$/.test(source_scope)
      ||!Number.isInteger(limit)||limit<1||limit>100||(cursor!==null&&(typeof cursor!=='string'||!cursor.length||cursor.length>4096)))
    fail('InvalidRequest','Candidates require exact revision/source scope and bounded continuation.');
  const {context,notes,witness,owner}=await capture(input,isCurrent);
  if(context.mapping.status!=='supported')fail('UnsupportedMapMapping','Choose a verified default background, or request an ordinary preview without map_notes.');
  validateMapCrop(context.rectangle,source_size,crop);
  const entries=mapRegionNotes(notes,context.rectangle,source_size,crop);
  const scope=await mapHash([input.caller_key,input.map,source_scope,source_size,crop]);
  const offset=mapOffset(cursor,scope,context.revision,entries.length);
  if(JSON.stringify(mapContext(isCurrent))!==JSON.stringify(owner)||JSON.stringify(readMapSnapshot(input.map.scene_uuid))!==JSON.stringify(witness))
    fail('MapContextChanged','Map notes changed while selecting the crop; refresh map/image info.');
  const result={protocol:'map_candidates.v1',context,source_size,crop,entries:[],total_in_region:entries.length,
    complete:offset===entries.length,next_cursor:offset===entries.length?null:mapCursor(scope,context.revision,offset)};
  if(mapBytes(result)>input.max_bytes)fail('ResponseTooLarge','Private candidate identity exceeds the configured frame budget.');
  let end=offset;
  while(end<entries.length&&end-offset<limit){
    const next=end+1,complete=next===entries.length;
    const candidate={...result,entries:[...result.entries,entries[end]],complete,next_cursor:complete?null:mapCursor(scope,context.revision,next)};
    if(mapBytes(candidate)>input.max_bytes)break;
    Object.assign(result,candidate);end=next;
  }
  if(end===offset&&offset<entries.length)fail('ResponseTooLarge','One complete private candidate cannot fit the configured frame budget.');
  return result;
}
