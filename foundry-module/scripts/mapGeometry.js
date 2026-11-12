/** Pure display-oriented mapping; default-placement admission is separate.
 * Public contracts/evidence: docs/plans/image-viewing/map-context.md.
 */
function fail(){const e=new Error('Annotation requires a verified default background mapping; use an ordinary preview for unsupported placement.');e.rpcError={code:'UnsupportedMapMapping',type:'UnsupportedMapMapping',message:e.message};throw e;}
function valid(rect,source){
  if(!rect||!source||!['sceneX','sceneY','sceneWidth','sceneHeight'].every(k=>typeof rect[k]==='number'&&Number.isFinite(rect[k]))
    ||rect.sceneWidth<=0||rect.sceneHeight<=0||!Number.isInteger(source.width)||!Number.isInteger(source.height)
    ||source.width<1||source.height<1||source.width>32768||source.height>32768||source.width*source.height>128000000)fail();
}
export function mapNoteToSource(rect,source,x,y){
  valid(rect,source);
  if(typeof x!=='number'||typeof y!=='number'||!Number.isFinite(x)||!Number.isFinite(y))fail();
  const source_x=(x-rect.sceneX)*source.width/rect.sceneWidth,source_y=(y-rect.sceneY)*source.height/rect.sceneHeight;
  if(!Number.isFinite(source_x)||!Number.isFinite(source_y))fail();
  return{source_x,source_y};
}
export function validateMapCrop(rect,source,crop){
  valid(rect,source);
  if(!crop||!['x','y','width','height'].every(k=>Number.isInteger(crop[k]))||crop.x<0||crop.y<0||crop.width<1||crop.height<1
      ||crop.x+crop.width>source.width||crop.y+crop.height>source.height)fail();
}
export function mapRegionNotes(notes,rect,source,crop){
  validateMapCrop(rect,source,crop);
  return notes.map(n=>({key:n.key,note_uuid:n.note_uuid,x:n.x,y:n.y,...mapNoteToSource(rect,source,n.x,n.y)}))
    .filter(n=>crop.x<=n.source_x&&n.source_x<crop.x+crop.width&&crop.y<=n.source_y&&n.source_y<crop.y+crop.height)
    .sort((a,b)=>Number(a.key.slice(1))-Number(b.key.slice(1)));
}
