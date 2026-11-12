/** Core14 selected-map metadata; public API evidence in map-info.md.
 * Detached source projections only, no PF2e, canvas activation or media fetch.
 */
import {mapContext,mapHash,mapNamed,mapBytes,mapCursor,mapOffset} from './mapBrowse.js';

const ID=/^[A-Za-z0-9_-]{1,128}$/;
function fail(code,message){const error=new Error(message);error.rpcError={code,type:code,message};throw error;}
const unavailable=()=>fail('MapDataUnavailable','Public map configuration is malformed; repair the Scene and retry get_map_info.');
function pick(source,keys){
  if(!source||typeof source!=='object'||Array.isArray(source))unavailable();
  return Object.fromEntries(keys.filter(k=>Object.hasOwn(source,k)&&source[k]!==undefined).map(k=>[k,source[k]]));
}
function source(doc){
  if(typeof doc?.testUserPermission!=='function'||typeof doc.toObject!=='function')fail('UnsupportedCapability','Required public document APIs are unavailable.');
  if(!doc.testUserPermission(game.user,'OBSERVER'))return null;
  return doc.toObject(true);
}
function ancestry(parent,witness){
  const result=[],seen=new Set();
  while(parent!==null){
    if(typeof parent!=='string'||!ID.test(parent)||seen.has(parent))fail('InvalidHierarchy','Missing or cyclic Scene-folder relationships; repair folders and retry.');
    seen.add(parent);
    const folder=game.folders.get(parent);
    if(!folder||folder.type!=='Scene')fail('InvalidHierarchy','Missing or invalid Scene parent folder; repair folders and retry.');
    const data=source(folder);
    if(!data)fail('PermissionDenied','Scene ancestry is unavailable; select a readable map.');
    if(typeof data.name!=='string')unavailable();
    witness.push([folder.uuid,data.name,data.folder??null]);
    result.unshift({folder_uuid:'Folder.'+parent,...mapNamed(data.name)});
    parent=data.folder??null;
  }
  return result;
}

/** Safe source hint only. Never reveals signed queries or user-info credentials. */
export function mapMedia(value,present=true){
  let reference=null,reference_status='missing',media_kind='none';
  if(present&&value!==undefined){
    if(value===null)reference_status='null';
    else if(value===''){reference_status='empty';reference='';}
    else if(typeof value!=='string')reference_status='unsupported';
    else {
      reference_status='unsupported';media_kind='unknown';
      try{
        const url=new URL(value,'https://map-reference.invalid/');
        if(url.username||url.password||url.search){reference_status='sensitive';}
        else if(value.length<=4096&&!/[\\\x00-\x1f\x7f]/.test(value)&&!value.startsWith('//')
            &&!url.hash&&['http:','https:'].includes(url.protocol)){
          const rawPath=value.replace(/^https?:\/\/[^/]*(?=\/|$)/i,'').split(/[?#]/)[0];
          const originalParts=rawPath.split('/').map(s=>decodeURIComponent(s));
          const path=url.pathname.split('/').map(s=>decodeURIComponent(s));
          if(path.every(s=>s!=='.'&&s!=='..'&&!/[/\\\x00-\x1f\x7f]/.test(s))
              &&originalParts.every(s=>s!=='.'&&s!=='..'&&!/[/\\\x00-\x1f\x7f]/.test(s))){
            reference_status='safe';reference=value;
            const ext=path.at(-1).split('.').at(-1).toLowerCase();
            media_kind=['jpg','jpeg','png','apng','webp','avif','bmp','gif','tif','tiff','svg'].includes(ext)?'image'
              :['webm','mp4','m4v','ogv','ogg'].includes(ext)?'video':'unknown';
          }
        }
      }catch{/* Invalid source stays a fixed unsupported record, never diagnostics. */}
    }
  }
  const supported=reference_status==='safe'&&media_kind==='image';
  const args={request:{src:reference}};
  return{reference,reference_status,media_kind,support_status:supported?'reference_only':reference_status==='sensitive'?'map_context_required'
    :['missing','null','empty'].includes(reference_status)?'missing':media_kind==='video'?'unsupported_video':'unsupported_reference',
    info_next_call:supported?{tool:'get_foundry_image_info',arguments:args}:null,
    preview_next_call:supported?{tool:'get_foundry_image_url',arguments:args}:null};
}
function media(data){return mapMedia(data?.src,!!data&&Object.hasOwn(data,'src'));}
function embedded(scene,name){
  if(typeof scene.getEmbeddedCollection!=='function')fail('UnsupportedCapability','Public embedded document collections are unavailable.');
  const collection=scene.getEmbeddedCollection(name);
  if(!Array.isArray(collection?.contents)||!(collection.invalidDocumentIds instanceof Set))fail('UnsupportedCapability','Public embedded availability metadata is unavailable.');
  const rows=[],denied=[];
  for(const doc of collection.contents){
    if(typeof doc.id!=='string'||!ID.test(doc.id)||doc.parent!==scene||doc.uuid!==`${scene.uuid}.${name}.${doc.id}`)unavailable();
    const data=source(doc);
    if(data===null)denied.push(doc.id);else rows.push({doc,data});
  }
  if(new Set(collection.contents.map(d=>d.id)).size!==collection.contents.length)unavailable();
  return{rows,unavailable:denied.concat([...collection.invalidDocumentIds]).sort()};
}
function snapshot(scene_uuid){
  const scene=game.scenes.get(scene_uuid.slice(6));
  if(!scene)fail('SceneNotFound','Scene is missing; restart browse_maps and select a current Scene UUID.');
  if(scene.uuid!==scene_uuid)unavailable();
  const data=source(scene);
  if(!data)fail('PermissionDenied','Selected Scene is unavailable; use a readable map and ready GM.');
  if(typeof scene.getDimensions!=='function')fail('UnsupportedCapability','Public Scene dimensions API is unavailable.');
  if(typeof data.name!=='string')unavailable();
  const folderWitness=[],ancestors=ancestry(data.folder??null,folderWitness),dimensions=scene.getDimensions();
  const rect=pick(dimensions,['sceneX','sceneY','sceneWidth','sceneHeight']);
  if(Object.keys(rect).length!==4||Object.values(rect).some(v=>typeof v!=='number'||!Number.isFinite(v)))unavailable();
  const levels=embedded(scene,'Level'),tiles=embedded(scene,'Tile');
  const allLevelIds=new Set(scene.getEmbeddedCollection('Level').contents.map(d=>d.id));
  const assetRows=levels.rows.map(({doc,data:s})=>{
    if(typeof s.name!=='string')unavailable();
    const role=r=>({...media(s[r]),role:r,map:{scene_uuid,level_id:doc.id,role:r}});
    return{kind:'level',level_id:doc.id,level_uuid:doc.uuid,...mapNamed(s.name),sort:s.sort??null,
      ...(Object.hasOwn(s,'elevation')?{elevation:s.elevation===null?null:pick(s.elevation,['bottom','top'])}:{}),
      background:role('background'),foreground:role('foreground')};
  });
  let unknownMembership=false;
  const tileRows=tiles.rows.map(({doc,data:s})=>{
    let ids=s.levels??null;
    if(ids instanceof Set)ids=[...ids];
    if(ids!==null&&(!Array.isArray(ids)||ids.some(id=>typeof id!=='string'||!ID.test(id)||!allLevelIds.has(id))||new Set(ids).size!==ids.length))unavailable();
    const explicit=!!ids?.length;if(!explicit)unknownMembership=true;
    return{kind:'tile',tile_uuid:doc.uuid,...(s.name!==undefined?{name:s.name===null?null:mapNamed(s.name).name}:{}),
      name_truncated:typeof s.name==='string'&&Array.from(s.name).length>256,sort:s.sort??null,
      placement:{...pick(s,['x','y','width','height','rotation','elevation','anchorX','anchorY']),
        ...pick(s.texture??{},['anchorX','anchorY','scaleX','scaleY','fit'])},
      media:media(s.texture),level_membership:{declared_ids:ids,status:explicit?'explicit':'not_evaluated'}};
  });
  const order=(a,b)=>(a.sort??0)-(b.sort??0)||((a.level_uuid??a.tile_uuid)<(b.level_uuid??b.tile_uuid)?-1:1);
  assetRows.sort(order);tileRows.sort(order);
  return{scene:{scene_uuid,...mapNamed(data.name),parent_uuid:data.folder?'Folder.'+data.folder:null,ancestry:ancestors},
    // Private revision witnesses preserve changes hidden by clipping/redaction.
    // They never enter the public response or browser diagnostics.
    source_witness:{scene_name:data.name,folders:folderWitness,
      levels:levels.rows.map(({doc,data:s})=>[doc.id,pick(s,['name','background','foreground','textures','elevation','sort'])]),
      tiles:tiles.rows.map(({doc,data:s})=>[doc.id,pick(s,['name','texture','levels'])])},
    geometry:{...pick(data,['width','height','padding','shiftX','shiftY']),scene_rect:rect},grid:pick(data.grid??{},['type','size','distance','units','style','thickness','color','alpha']),
    ...(Object.hasOwn(data,'initialLevel')?{initial_level_id:data.initialLevel}:{}),assets:assetRows,tiles:tileRows,
    unavailable:[levels.unavailable,tiles.unavailable],unknownMembership,
    artwork:{levels:assetRows.length,tiles:tileRows.length,
      background_references:assetRows.filter(r=>!['missing','null','empty'].includes(r.background.reference_status)).length,
      foreground_references:assetRows.filter(r=>!['missing','null','empty'].includes(r.foreground.reference_status)).length}};
}

/** Exact Scene/optional level metadata; caller_key is injected by authenticated Python. */
export async function getMapInfo(params={},isCurrent=()=>true){
  const allowed=['scene_uuid','level_id','section','expected_revision','limit','max_bytes','cursor','caller_key'];
  if(!params||typeof params!=='object'||Array.isArray(params)||Object.keys(params).some(k=>!allowed.includes(k)))fail('InvalidRequest','Use published get_map_info fields.');
  const {scene_uuid,level_id=null,section='assets',expected_revision=null,limit=10,max_bytes=8000,cursor=null,caller_key}=params;
  if(typeof scene_uuid!=='string'||!/^Scene\.[A-Za-z0-9_-]{1,128}$/.test(scene_uuid)
    ||(level_id!==null&&(typeof level_id!=='string'||!ID.test(level_id)))||!['assets','tiles'].includes(section)
    ||!Number.isInteger(limit)||limit<1||limit>100||!Number.isInteger(max_bytes)||max_bytes<1024||max_bytes>48000
    ||(cursor!==null&&(typeof cursor!=='string'||!cursor.length||cursor.length>4096))
    ||(expected_revision!==null&&(typeof expected_revision!=='string'||expected_revision.length>128))
    ||typeof caller_key!=='string'||!/^[0-9a-f]{64}$/.test(caller_key))fail('InvalidRequest','Use exact Scene/level identities and published bounds.');
  const owner=mapContext(isCurrent),data=snapshot(scene_uuid);
  if(level_id!==null&&!data.assets.some(l=>l.level_id===level_id)){
    if(data.unavailable[0].includes(level_id))fail('PermissionDenied','Selected level is unavailable; choose a readable level.');
    fail('LevelNotFound','Level does not belong to this Scene; use get_map_info assets without level_id.');
  }
  const revision=await mapHash([owner,data]),scope=await mapHash([owner,caller_key,scene_uuid,level_id,section]);
  if(JSON.stringify(mapContext(isCurrent))!==JSON.stringify(owner)||JSON.stringify(snapshot(scene_uuid))!==JSON.stringify(data))fail('ContentChanged','Map metadata or permissions changed; restart get_map_info.');
  if(expected_revision!==null&&expected_revision!==revision)fail('ContentChanged','Expected map revision changed; discard prior pages and restart.');
  const entries=section==='assets'?data.assets.filter(l=>level_id===null||l.level_id===level_id)
    :data.tiles.filter(t=>level_id===null||t.level_membership.status==='not_evaluated'||t.level_membership.declared_ids.includes(level_id));
  const offset=mapOffset(cursor,scope,revision,entries.length);
  const partial=data.unavailable.some(ids=>ids.length>0)||(section==='tiles'&&level_id!==null&&data.unknownMembership);
  const result={scene:data.scene,geometry:data.geometry,grid:data.grid,...(Object.hasOwn(data,'initial_level_id')?{initial_level_id:data.initial_level_id}:{}),
    level_id,section,revision,entries:[],total:entries.length,complete:offset===entries.length,next_cursor:offset===entries.length?null:mapCursor(scope,revision,offset),
    scope_status:partial?'partial':'complete',artwork:data.artwork,limitations:[
      'Configured references only; no file existence checks. Scene dimensions differ from original image pixels.',
      'A background/foreground file is not a composed Scene; Tiles, fog, lights, tokens and walls are separate.',
      ...(partial?['Some embedded data or selected-level Tile applicability is unavailable; this inventory cannot establish exhaustive scope.']:[])]};
  if(mapBytes(result)>max_bytes)fail('ResponseTooLarge','Map identity exceeds max_bytes; increase up to48000.');
  let end=offset;
  while(end<entries.length&&end-offset<limit){
    const next=end+1,complete=next===entries.length;
    const candidate={...result,entries:[...result.entries,entries[end]],complete,next_cursor:complete?null:mapCursor(scope,revision,next)};
    if(mapBytes(candidate)>max_bytes)break;
    Object.assign(result,candidate);end=next;
  }
  if(end===offset&&offset<entries.length)fail('ResponseTooLarge','One complete level/Tile record cannot fit; increase max_bytes up to48000.');
  return result;
}
