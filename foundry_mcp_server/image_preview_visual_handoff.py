"""Private visual challenges and reports; local pixels never prove client acceptance."""
import io
import json
from pathlib import Path
import re
import secrets
from typing import Literal
from urllib.parse import urlsplit
from uuid import uuid4

from PIL import Image,ImageDraw,ImageFont
from pydantic import Field

from .image_preview_live_support import MARKER,PREVIEW_PATH,require
from .map_note_glyphs import verified_font
from .mcp_server.selective_models import Model

REGION=dict(x=720,y=500,width=240,height=200)
COLORS={'red':(210,35,45),'blue':(25,65,200),'green':(20,130,65),'purple':(135,35,170)}


def challenge():
    """Random answers exist only in pixels/private expected data, never metadata."""
    label='Q'+''.join(secrets.choice('GHJKLMNPQRSTUVWXYZ23456789') for _ in range(5))
    first,second=secrets.SystemRandom().sample(list(COLORS),2)
    symbol=secrets.choice(('circle','square','triangle'))
    image=Image.new('RGB',(1024,768),(225,225,225));draw=ImageDraw.Draw(image)
    x,y=REGION['x'],REGION['y']
    font=ImageFont.truetype(str(verified_font()),36)
    draw.text((x+16,y+18),label,font=font,fill=COLORS[first])
    box=(x+90,y+90,x+150,y+150)
    if symbol=='circle':draw.ellipse(box,fill=COLORS[second])
    elif symbol=='square':draw.rectangle(box,fill=COLORS[second])
    else:draw.polygon(((x+120,y+90),(x+90,y+150),(x+150,y+150)),fill=COLORS[second])
    stream=io.BytesIO();image.save(stream,format='PNG')
    return stream.getvalue(),dict(label=label,colors=[first,second],symbol=symbol,region=REGION.copy(),width=1024,height=768)


def prompts(page_uuid='<journal page UUID returned by fixture preparation>',map_name='<map name>',ancestry='<named folder ancestry>',level_name='<level name>'):
    """Independent fresh contexts keep key metadata out of the pixel-answer test."""
    return dict(hidden_workflow=(f'Read journal page {page_uuid}. Inspect its image region with original top-left coordinates '
        '720,500 and extent240,200. Read the short label, its color and the neighboring symbol color from image pixels. '
        'Use image information and an exact crop, then fetch the returned image URL.'),
        exact_link_trial='In a new context, inspect <exact crop URL from the observed workflow>. Read the short label, its color and the neighboring symbol color from pixels.',
        query_link_trial='In an equivalent separate new context, inspect <the same exact crop URL with only ?probe=1 appended>. Read the short label, its color and the neighboring symbol color from pixels.',
        map_workflow=(f'Browse the map named {map_name} under {ancestry}. Use discovered folder/map next calls to choose level {level_name} and its explicit background. '
            'Request an annotated crop with map_notes=true. Fetch the image, identify a visible compact note key from pixels, '
            'then follow its exact revision-bound legend to the linked journal/page. Report any annotation omissions and request a tighter crop when necessary.'))


def create_bundle(directory):
    directory=Path(directory);directory.mkdir(mode=0o700)
    try:
        marker=uuid4().hex;pixels,expected=challenge();filename=uuid4().hex+'.png'
        require(expected['label'].lower() not in filename)
        files={'.owner':marker.encode(),filename:pixels,
            'expected.json':json.dumps(expected).encode(),'prompts.json':json.dumps(prompts(),indent=2).encode(),
            'fixture.json':json.dumps(dict(marker=marker,filename=filename,ready=False)).encode()}
        for name,data in files.items():
            path=directory/name;path.write_bytes(data);path.chmod(0o600)
    except BaseException:
        for path in directory.iterdir():path.unlink()
        directory.rmdir();raise
    return public_report(directory)


def load_bundle(directory):
    directory=Path(directory);require(directory.is_dir() and not directory.is_symlink())
    def read(name):
        path=directory/name;require(path.is_file() and not path.is_symlink() and path.stat().st_size<=2097152)
        return path.read_text()
    marker=read('.owner');require(MARKER.fullmatch(marker) is not None)
    expected=json.loads(read('expected.json'))
    state=json.loads(read('fixture.json'));require(state['marker']==marker)
    require(re.fullmatch(r'[a-f0-9]{32}\.png',state['filename']) is not None)
    for name in ('.owner','expected.json','fixture.json','prompts.json',state['filename']):
        path=directory/name;require(path.is_file() and not path.is_symlink() and path.stat().st_size<=2097152)
    return expected,state


class ReviewedTrial(Model):
    """Operator-reviewed actual target trace, not a model's self-reported steps.

    Shape validation cannot authenticate the provenance of a human-supplied
    record. Keep the original client trace privately and review it before use.
    """
    provenance: Literal['reviewed_target_client_trace']
    client: Literal['ChatGPT']
    context_id: str=Field(min_length=1,max_length=128)
    trace_sha256: str=Field(pattern=r'^[a-f0-9]{64}$')
    fetched_url: str=Field(min_length=1,max_length=4096)
    client_fetch_observed: bool
    answer: str=Field(max_length=2000)
    info_call_observed: bool=False
    requested_region: dict[str,int]|None=None
    browse_observed: bool=False
    level_selection_observed: bool=False
    map_notes_requested: bool=False
    key_read_from_pixels: bool=False
    legend_matches_rendered_key: bool=False
    journal_page_followed: bool=False
    annotation_omitted_count: int=Field(default=0,ge=0)
    omissions_reported: bool=False


def valid_url(value):
    parsed=urlsplit(value)
    return bool(parsed.scheme=='https' and parsed.hostname and not parsed.username and not parsed.password
        and not parsed.fragment and PREVIEW_PATH.fullmatch(parsed.path))


def evaluate(expected,observations=None):
    """Pending by default; trusted reviewed observations are evaluated separately."""
    names=('hidden_workflow','exact_link_trial','query_link_trial','map_workflow')
    statuses={name:'pending' for name in names}
    if observations is None:return statuses
    require(set(observations)<=set(names))
    trials={name:ReviewedTrial.model_validate(value) for name,value in observations.items()}
    for name,trial in trials.items():
        read=trial.client_fetch_observed and valid_url(trial.fetched_url)
        if name!='query_link_trial':read=read and not urlsplit(trial.fetched_url).query
        if name=='map_workflow':
            passed=read and all((trial.browse_observed,trial.level_selection_observed,trial.map_notes_requested,
                trial.key_read_from_pixels,trial.legend_matches_rendered_key,trial.journal_page_followed))
            passed=passed and (trial.annotation_omitted_count==0 or trial.omissions_reported)
        else:
            answer=trial.answer.casefold()
            passed=read and all(re.search(r'\b'+re.escape(word.casefold())+r'\b',answer) for word in [expected['label'],*expected['colors']])
            if name=='hidden_workflow':passed=passed and trial.info_call_observed and trial.requested_region==expected['region']
        statuses[name]='passed' if passed else 'failed'
    if 'exact_link_trial' in trials and 'query_link_trial' in trials:
        exact,query=trials['exact_link_trial'],trials['query_link_trial'];a,b=urlsplit(exact.fetched_url),urlsplit(query.fetched_url)
        equivalent=(a._replace(query='')==b._replace(query='') and a.query=='' and b.query=='probe=1'
            and exact.context_id!=query.context_id and exact.trace_sha256!=query.trace_sha256)
        if 'hidden_workflow' in trials:
            hidden=trials['hidden_workflow']
            equivalent=equivalent and hidden.fetched_url==exact.fetched_url and hidden.context_id not in (exact.context_id,query.context_id)
        if not equivalent:statuses['exact_link_trial']=statuses['query_link_trial']='failed'
    for name,trial in trials.items():
        if any(other!=name and (value.context_id==trial.context_id or value.trace_sha256==trial.trace_sha256) for other,value in trials.items()):
            statuses[name]='failed'
    return statuses


def public_report(directory,observations=None):
    expected,state=load_bundle(directory)
    statuses=evaluate(expected,observations)
    return dict(implementation='complete',local_pixel_fixture='generated',fixture_ready=state['ready'],
        visual_acceptance='passed' if all(value=='passed' for value in statuses.values()) else 'failed' if 'failed' in statuses.values() else 'pending',
        scenarios=statuses,expected_answers_public=False,
        prerequisites=['Actual target ChatGPT with refreshed tools and authorized GM bridge to the same test world.',
            'Operator-provided publicly reachable trusted HTTPS preview origin on authenticated Basic/OAuth MCP; loopback development mode is not a public deployment.',
            'Prepare the marked fixture, use private concrete prompts in separate contexts, and retain reviewed actual-client traces.',
            'Run delegated exact-marker fixture cleanup after the external trials.'])
