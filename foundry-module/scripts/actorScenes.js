/** Scene navigation using public core14.369 Scene/TokenDocument APIs.
 * https://foundryvtt.com/api/v14/classes/foundry.documents.TokenDocument.html
 * https://foundryvtt.com/api/v14/classes/foundry.documents.collections.Scenes.html
 * PF2e-specific: filters character/npc/familiar on system8.6.1; identities only,
 * no persisted or derived statistic is interpreted. No canvas or active scene.
 */
import { fail, validateParams, integer, selector, selectSections, digest, paginate } from './actorReadUtils.js';
import { ACTOR_TYPES, ready, permitted, requirePermission, named, documentIdentity } from './actorDocuments.js';

const compare=(a,b)=>a<b?-1:a>b?1:0;

/** PF2e-specific scene/token identity navigation; see module version boundary. */
export async function listSceneActors(params={}) {
  validateParams(params,['scene_uuid','query','types','limit','max_bytes','cursor']);
  const current=ready();
  integer(params.limit,50,1,100,'limit'); integer(params.max_bytes,48000,8000,48000,'max_bytes');
  if (!game.scenes) fail('NotReady','Scene documents are not ready.','Wait for world readiness.');
  const selected=params.scene_uuid!==undefined&&params.scene_uuid!==null;
  if (!selected && (params.query!=null || params.types!=null)) fail('InvalidRequest','query/types require scene_uuid.','First list scenes, then repeat with a returned scene_uuid.');
  let query='';
  if (params.query!=null) {
    if (typeof params.query!=='string'||!params.query.trim()||[...params.query.trim()].length>200) fail('InvalidRequest','query must contain 1–200 characters after trim.');
    query=params.query.trim().toLowerCase();
  }
  const types=selectSections(params.types??undefined,ACTOR_TYPES,ACTOR_TYPES);
  if (selected) {
    selector(params.scene_uuid,'scene_uuid');
    if (!/^Scene\.[^.]+$/.test(params.scene_uuid)) fail('InvalidRequest','scene_uuid must select a world Scene.');
  }
  const build=async()=>{
    const nodes=[];const scopes=[];let unsupported_count=0;
    if (!selected) {
      for (const scene of game.scenes.values()) {
        if (!permitted(scene)) { scopes.push({id:scene.uuid,status:'denied',reason:'Scene OBSERVER permission required.'});continue; }
        scopes.push({id:scene.uuid,status:'searched',reason:null});
        nodes.push({kind:'scene',id:scene.id,uuid:scene.uuid,...named(scene),parent_uuid:null,
          next_call:{tool:'list_scene_actors',arguments:{scene_uuid:scene.uuid}}});
      }
    } else {
      const scene=[...game.scenes.values()].find(value=>value.uuid===params.scene_uuid);
      if (!scene) fail('DocumentNotFound','Selected Scene no longer exists.','List scenes again without scene_uuid.');
      requirePermission(scene);
      let incomplete=false;
      for (const token of scene.tokens.values()) {
        if (!permitted(token)) {scopes.push({id:token.uuid,status:'denied',reason:'Token OBSERVER permission required.'});incomplete=true;continue;}
        const actor=token.actor;
        if (actor&&!permitted(actor)) {scopes.push({id:token.uuid,status:'denied',reason:'Actor OBSERVER permission required.'});incomplete=true;continue;}
        if (actor&&!ACTOR_TYPES.includes(actor.type)) {unsupported_count++;continue;}
        if (actor&&!types.includes(actor.type)) continue;
        if (query&&!String(token.name).toLowerCase().includes(query)&&!String(actor?.name??'').toLowerCase().includes(query)) continue;
        const identity=actor?documentIdentity(actor,null,token):null;
        const base=token.baseActor;
        nodes.push({kind:'token',id:token.id,uuid:token.uuid,...named(token),parent_uuid:scene.uuid,
          identity,actor_link:token.isLinked,base_actor:base&&permitted(base)?{uuid:base.uuid,...named(base)}:null,
          next_call:actor?{tool:'read_actor',arguments:{token_uuid:token.uuid}}:null,
          limitations:[...(!actor?['ActorUnavailable: current token Actor is missing; base Actor cannot substitute current state.']:[]),
            ...(!base||!permitted(base)?['BaseActorUnavailable: base Actor is missing or inaccessible; current Actor identity is retained.']:[])]});
      }
      scopes.unshift({id:scene.uuid,status:incomplete?'incomplete':'searched',reason:incomplete?'Some token/Actor documents are inaccessible.':null});
    }
    nodes.sort((a,b)=>compare(a.name.toLowerCase(),b.name.toLowerCase())||compare(a.uuid,b.uuid));
    scopes.sort((a,b)=>compare(a.id,b.id));
    return {nodes,scopes,unsupported_count,runtime:ready()};
  };
  const snapshot=await build();const revision=await digest(snapshot);
  const base={contract_version:1,runtime:current,revision,scopes:snapshot.scopes,unsupported_count:snapshot.unsupported_count,limitations:['Completion covers the selected readable scene scope; no active-canvas requirement.']};
  const result=await paginate(snapshot.nodes,base,params,{tool:'list_scene_actors',scene_uuid:params.scene_uuid??null,query,types});
  if (await digest(await build())!==revision) fail('ContentChanged','Scene/token identity or scope changed.','Discard accumulated pages and restart without cursor.');
  const {records,...rest}=result;return {...rest,nodes:records};
}
