"""Bounded localhost test-world acceptance for PF2e Item editing. Print aggregates only."""
import argparse
import asyncio
import json
from pathlib import Path
import re
import secrets
from tempfile import NamedTemporaryFile
from collections import defaultdict
from uuid import uuid4

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

ROOT = Path(__file__).resolve().parents[1]
DOGSLICER = 'Compendium.pf2e.equipment-srd.Item.olwngGXM3hpgoLEP'
GUARD = """
if(location.origin!=='http://localhost:30000'||game.world.id!=='test'||!game.ready||!game.user.isGM||
   game.version!=='14.370'||game.system.id!=='pf2e'||game.system.version!=='8.7.0'||
   game.settings.get('pf2e','worldSchemaVersion')!==0.961||game.settings.get('pf2e','worldSystemVersion')!=='8.7.0')
  throw Error('Expected migrated test world and ready GM');
"""


def size(data):
    return len(json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode())


class Check:
    def __init__(self, client, marker):
        if not re.fullmatch(r'[0-9a-f]{32}', marker):
            raise ValueError('Expected an exact per-run marker')
        self.client = client
        self.marker = marker
        self.calls = 0
        self.stage = 'setup'

    async def call(self, name, args):
        self.calls += 1
        if self.calls > 140:
            raise RuntimeError('Fixture call budget exceeded')
        result = await self.client.call_tool(name, args)
        return result.structured_content if result.structured_content is not None else json.loads(result.content[0].text)

    async def js(self, body, **params):
        # These scripts are fixed verification code. All variable input is serialized data.
        code = GUARD + 'const run=' + json.dumps(self.marker) + ', args=' + json.dumps(params) + ';\n' + body
        data = (await self.call('execute_javascript', {'code': code}))['value']
        if isinstance(data, dict) and data.get('$type') == 'Array' and not data['truncated']:
            data = ''.join(data['values'])
        return json.loads(data)

    async def pages(self, name, **args):
        rows, total, pages = [], 0, 0
        for _ in range(32):
            data = await self.call(name,args)
            if any(s['status']!='searched' for s in data.get('scopes',[])) or data.get('unsupported_count',0):
                raise RuntimeError('Incomplete inventory or Scene discovery')
            total += size(data)
            pages += 1
            rows.extend(data.get('records', data.get('entries', data.get('nodes', []))))
            if data['pagination']['complete']:
                return rows, [pages,total]
            args['cursor'] = data['pagination']['next_cursor']
        raise RuntimeError('Page budget exceeded')

    async def edit(self, target, changes):
        args = dict(**target,changes=changes)
        preview = await self.call('edit_item',args)
        assert preview['status']=='preview'
        applied = await self.call('edit_item',dict(args,mode='apply',expected_revision=preview['revision']))
        assert applied['status'] in ('applied','unchanged')
        rows,_ = await self.pages('read_item',**applied['next_call']['arguments'])
        return rows


async def baseline(check):
    check.stage = 'catalog'
    catalog = await check.client.list_tools()
    item = next(t for t in catalog if t.name=='read_item')
    report = dict(tools=len(catalog),catalog=size([t.model_dump(mode='json') for t in catalog]),
                  read_item=size(item.model_dump(mode='json')))
    for key,extra in [('identity',{}),('damage',dict(select={'details':['source.damage']})),
                      ('evidence',dict(select={'details':['source.damage'],'evidence':True},max_bytes=48000)),
                      ('source',dict(select={'details':['source']},limit=3,max_bytes=48000)),
                      ('description',dict(select={'details':['description']},limit=1))]:
        check.stage=key
        _,report[key]=await check.pages('read_item',item_uuid=DOGSLICER,**extra)
    return report


GROUPS = ['header','weapon_summary','details','material_and_runes','damage','other_tags','publication','description','mystification']
FIXTURE = (ROOT/'scripts/fixtures/item-editing-live.js').read_text()


async def refresh(check):
    runner = await asyncio.create_subprocess_exec(str(ROOT/'scripts/actor-tools.sh'),'refresh',
                                                 stdout=asyncio.subprocess.DEVNULL)
    if await runner.wait() != 0:
        raise RuntimeError('Development tab refresh failed')
    await asyncio.sleep(2)
    for _ in range(25):
        try:
            if await check.js('return JSON.stringify(game.ready);'):
                return
        except Exception:
            pass
        await asyncio.sleep(1)
    raise RuntimeError('GM did not reconnect after refresh')


async def compare_sheet(check, uuid):
    rows,_=await check.pages('read_item',item_uuid=uuid,sheet={'groups':GROUPS},limit=100,max_bytes=48000)
    fields={r['field']:r for r in rows}
    ui=await check.js(FIXTURE,action='sheet',uuid=uuid)
    compare={
        'header.name':'name','header.level':'level','header.rarity':'rarity','weapon_summary.quantity':'quantity',
        'weapon_summary.hands':'hands','weapon_summary.bulk':'bulk','weapon_summary.size':'size','details.category':'category',
        'details.group':'group','details.base':'base','details.range':'range','material_and_runes.potency_rune':'potency',
        'material_and_runes.striking_rune':'striking','damage.splash':'splash','mystification.identification_status':'status',
    }
    for id,key in compare.items():
        check.stage='compare '+id
        value=fields[id]['display']
        assert str(value if value is not None else '')==ui[key]
    check.stage='sheet compound controls'
    assert fields['header.image']['source']==ui['image']
    assert fields['header.display_name']['display'] in ui['title']
    assert all(t in ui['traits'] for t in fields['header.traits']['display'])
    price=fields['weapon_summary.price']['display']
    assert all(str(value) in ui['price'] for code,value in price.items() if code!='per' and value)
    material=fields['material_and_runes.precious_material']['display']
    if material['type']:
        assert json.loads(ui['material'])==material
    else:
        assert not ui['material'] or json.loads(ui['material'])['type'] is None
    assert [r.get('display') or '' for r in rows if r.get('slot')]==ui['runes']
    assert [r['editable'] for r in rows if r.get('slot')]==ui['slotEditors']
    menu_fields={'system.range':'details.range','system.material':'material_and_runes.precious_material',
                 'system.runes.property':'material_and_runes.property_runes','system.runes.potency':'material_and_runes.potency_rune',
                 'system.runes.striking':'material_and_runes.striking_rune','system.publication.license':'publication.license'}
    for path,menu in ui['menus'].items():
        field=menu_fields[path]
        check.stage='menu '+field
        args={'slot':1} if path=='system.runes.property' else {}
        choices,_=await check.pages('get_item_field_options',item_uuid=uuid,field=field,limit=100,max_bytes=48000,**args)
        codes=[option['value'] for option in choices]
        if path=='system.material':
            expected=[json.loads(code) if code else None for code in menu['codes']]
            expected=[entry if entry and entry['type'] else None for entry in expected]
            assert {json.dumps(v,sort_keys=True) for v in codes}=={json.dumps(v,sort_keys=True) for v in expected},field
        else:
            assert {'' if v is None else str(v) for v in codes}==set(menu['codes']),field
        field_row=next(r for r in rows if r['field']==field)
        assert field_row['editable']==menu['editable'],field
    assert fields['material_and_runes.specific_magic_weapon']['display']==ui['specific']
    damage=fields['damage.base']['display']
    assert [str(damage['dice']),damage['die'],damage['type']]==[ui['dice'],ui['die'],ui['type']]
    persistent=fields['damage.persistent']['display']
    assert ui['persistent']==([str(persistent['amount']),str(persistent['faces'] or ''),persistent['type']] if persistent else ['0','',''])
    assert len(fields['other_tags.tags']['display'])==len(ui['tags'])
    assert [fields['publication.'+k].get('display','') for k in ['title','authors','license','remaster']]==ui['publication']
    assert fields['mystification.unidentified_name']['display']==ui['unidentified']
    for id,key in [('description.text','description'),('mystification.unidentified_description','alternate')]:
        assert fields[id]['display']==ui[key]
    return len(fields)


async def gm_sheet(check):
    try:
        check.stage='fixture create'
        ids=await check.js(FIXTURE,action='create')
        check.stage='initial GM sheet'
        count=await compare_sheet(check,ids['solo'])
        check.stage='image discovery'
        image_result=await check.call('browse_journal_images',{'source':'data','directory':'systems/pf2e/icons/equipment/weapons','name_contains':'longsword'})
        image=next(entry['image'] for entry in image_result['entries'] if entry['kind']=='image')
        tags,_=await check.pages('get_item_field_options',item_uuid=ids['solo'],field='other_tags.tags',query='improvised')
        tag=next(entry['value'] for entry in tags if entry['available'])
        common={'header':{'name':'Notched Dogslicer','level':1,'traits':['agile','finesse'],'rarity':'rare','image':image},
                'weapon_summary':{'quantity':2,'hands':'held-in-one-hand','bulk':1,'size':'lg','price':{'gp':2}},
                'details':{'category':'simple','group':'knife','base':'dagger','range':None},
                'other_tags':{'tags':[tag]},'publication':{'title':'Fixture','authors':'GM','license':'OGL','remaster':False},
                'damage':{'base':{'dice':1,'die':'d8','type':'piercing'},'splash':1,'persistent':{'amount':1,'faces':None,'type':'bleed'}},
                'mystification':{'unidentified_name':'Notched Knife','unidentified_description':'Rust flecks its edge.'},
                'description':{'text':'A shallow groove runs down the blade.'}}
        rune={'material_and_runes':{'precious_material':{'type':'silver','grade':'low'},'potency_rune':2,'striking_rune':2,
                                    'property_runes':[{'slot':1,'value':'flaming'},{'slot':2,'value':'wounding'}]}}
        for role,uuid in ids.items():
            target={'item_uuid':uuid}
            check.stage=role+' invariants'
            before=await check.js(FIXTURE,action='invariants',uuid=uuid)
            for group,change in [('sidebar and Details',common),('runes',rune),('specific on',{'material_and_runes':{'specific_magic_weapon':True}})]:
                check.stage=role+' '+group
                await check.edit(target,change)
            specific=await check.js(FIXTURE,action='invariants',uuid=uuid)
            assert specific['specific']=={'material':specific['material'],'runes':specific['runes']}
            check.stage=role+' specific GM sheet'
            await compare_sheet(check,uuid)
            await check.edit(target,{'material_and_runes':{'striking_rune':3}})
            upgraded=await check.js(FIXTURE,action='invariants',uuid=uuid)
            assert upgraded['runes']['striking']==3 and upgraded['specific']==specific['specific']
            await check.edit(target,{'material_and_runes':{'specific_magic_weapon':False}})
            after=await check.js(FIXTURE,action='invariants',uuid=uuid)
            assert all(before[k]==after[k] for k in ['rules','altImage','per','modifier','ownerSize'])
            assert after['specific'] is None
        check.stage='reload'
        await refresh(check)
        for uuid in ids.values():
            await compare_sheet(check,uuid)
        return dict(distinct_controls=count,targets=len(ids),reloaded=True)
    finally:
        removed=await check.js(FIXTURE,action='cleanup')
        assert removed=={'remaining':0}


async def player_and_tokens(check):
    from item_editing_player import player_browser
    try:
        check.stage='marked player, loot and inactive scene'
        password=secrets.token_urlsafe(32)
        ids=await check.js(FIXTURE,action='createPlayer',password=password)
        a,b,linked=ids['copies']
        assert len({a['item_uuid'],b['item_uuid'],ids['base']['item_uuid']})==3
        assert linked['item_uuid']==ids['base']['item_uuid']
        async def selected(target,field):
            rows,_=await check.pages('read_item',**target,sheet={'fields':[field]})
            return rows[0]
        field='mystification.unidentified_name'
        original=(await selected(ids['base'],field))['source']
        assert (await selected(b,field))['source']==original
        check.stage='one unlinked copy'
        await check.edit(a,{'mystification':{'unidentified_name':'Ragged Edge'}})
        await refresh(check)
        assert (await selected(a,field))['source']=='Ragged Edge'
        assert (await selected(b,field))['source']==original
        assert (await selected(ids['base'],field))['source']==original
        check.stage='linked selector recovery'
        alias=await selected(linked,field)
        assert not alias['editable'] and ids['base']['item_uuid'] in alias['reason']
        check.stage='player login'
        async with player_browser(ROOT,ids['player'],password) as witness:
            check.stage='player alternate text'
            clue='Dark specks follow the notch in its edge.'
            await check.edit(ids['base'],{'mystification':{'unidentified_name':'Speckled Blade','unidentified_description':clue}})
            assert (await selected(ids['base'],'mystification.identification_status'))['source']=='identified'
            before=await check.js(FIXTURE,action='invariants',uuid=ids['base']['item_uuid'])
            await check.edit(ids['base'],{'mystification':{'identification_status':'unidentified'}})
            assert await witness(ids['actor'],ids['item_id'],check.marker,'Speckled Blade',clue)
            check.stage='player identification reveal'
            await check.edit(ids['base'],{'mystification':{'identification_status':'identified'}})
            display=(await selected(ids['base'],'header.display_name'))['display']
            assert display!='Speckled Blade' and await witness(ids['actor'],ids['item_id'],check.marker,display,'A chipped blade.')
            after=await check.js(FIXTURE,action='invariants',uuid=ids['base']['item_uuid'])
            assert before==after
        return dict(sibling_and_base_unchanged=True,linked_alias=True,player_unidentified=True,player_identified=True)
    finally:
        removed=await check.js(FIXTURE,action='cleanup')
        assert removed=={'remaining':0}


CHAPTER = (ROOT/'scripts/fixtures/item-chapter-live.js').read_text()
CLUES = {
    'Copper pin': ('Copper-Pinned Knife','A green stain circles the pin nearest the hilt.'),
    'Ivory bead': ('Beaded Knife','A pale bead clicks softly against the pommel.'),
    'Ashwood grip': ('Ash-Grip Knife','The grain curls around a dark knot beneath the thumb.'),
    'Split guard': ('Forked-Hilt Knife','One tine of the guard bends toward the edge.'),
    'Horn pommel': ('Horn-Capped Knife','A polished horn cap fits snugly against the heel of the hand.'),
    'Twisted wire': ('Wire-Wound Knife','Two strands of dull wire cross beneath the thumb.'),
    'Brass collar': ('Brass-Collared Knife','A narrow brass ring has worn a groove in the grip.'),
    'stone': ('Crescent Stone','A dark crescent catches the light on the smooth slate.'),
}


async def journal_pages(check, name, args, key):
    result=[]
    for _ in range(12):
        page=await check.call(name,args)
        result.extend(page[key])
        if page['complete']:
            return result
        args=dict(args,cursor=page['next_cursor'])
    raise RuntimeError('Journal metadata budget')


async def chapter(check):
    try:
        check.stage='create chapter fixture'
        fixture=await check.js(CHAPTER,action='create')
        catalog={t.name for t in await check.client.list_tools()}
        assert {'search_journals','get_journal_contents','read_journal_page','list_scene_actors',
                'list_actor_items','read_item','edit_item'}<=catalog
        check.stage='enumerate chapter rooms'
        hits=await journal_pages(check,'search_journals',dict(query='Chapter workshop '+check.marker,journal_id=fixture['journal'],limit=2),'matches')
        rooms=await journal_pages(check,'get_journal_contents',dict(journal_id=fixture['journal'],limit=2),'pages')
        assert {p['page_uuid'] for p in rooms}=={p['page_uuid'] for p in hits}
        locations=defaultdict(set)
        unresolved=[]
        for room in rooms:
            page=await check.call('read_journal_page',{'page_uuid':room['page_uuid'],'select':{'references':True}})
            assert page['complete'] and page['references_complete']
            refs=[r['target'] for r in page['references']]
            if refs:
                assert fixture['scene'] in refs
            tokens=[uuid for uuid in refs if uuid.startswith(fixture['scene']+'.Token.')]
            if not tokens:
                unresolved.append(room['name'])
            for token in tokens:
                locations[token].add(room['name'])
        check.stage='resolve scene token inventories'
        tokens,_=await check.pages('list_scene_actors',scene_uuid=fixture['scene'],limit=2)
        assert set(locations)=={t['uuid'] for t in tokens}
        items={}
        inventories=0
        pages_read=0
        for token in tokens:
            owner=token['identity']['uuid']
            assert owner in fixture['owners']
            args={'actor_uuid':owner} if token['actor_link'] else {'token_uuid':token['uuid']}
            nodes,stats=await check.pages('list_actor_items',**args,limit=3,select={'follow_up':True})
            pages_read+=stats[0]
            inventories+=1
            for node in nodes:
                target=node['next_call']['arguments']
                assert node['next_call']['tool']=='read_item' and target['item_uuid'].startswith(owner+'.Item.')
                entry=items.setdefault(target['item_uuid'],dict(target=target,locations=set(),
                    actor=token['identity']['name'] if token['actor_link'] else token['name'],type=node['identity']['type']))
                entry['locations'].update(locations[token['uuid']])
        check.stage='inspect actual Items and their reference definitions'
        references={}
        report=[]
        mundane=0
        for item in items.values():
            target=item['target']
            groups=['description','header','mystification']
            if item['type']=='weapon':
                groups.append('material_and_runes')
            rows,_=await check.pages('read_item',**target,sheet={'groups':groups},limit=100,max_bytes=48000)
            field={r['field']:r for r in rows}
            description=field['description.text']['source']
            reference,=re.findall(r'@UUID\[([^\]]+)\]',description)
            if reference not in references:
                assert reference.startswith('Compendium.pf2e.equipment-srd.Item.')
                source,_=await check.pages('read_item',item_uuid=reference,select={'details':['source.traits','description']},
                                           limit=100,max_bytes=48000)
                references[reference]=[v['value'] for r in source for v in r['values']]
            magic_rune=any(r['field']=='material_and_runes.property_runes' and r.get('source') for r in rows)
            fundamental=any(field.get('material_and_runes.'+key,{}).get('source',0)>0 for key in ('potency_rune','striking_rune'))
            if not (magic_rune or fundamental or 'magical' in references[reference]):
                mundane+=1
                continue
            # All fixture Items begin identified. Capture PF2e's public presentation before the edit.
            assert field['mystification.identification_status']['source']=='identified'
            if 'header.display_name' in field:
                identified=field['header.display_name']['display']
                motif=re.search(r'Workshop mark: ([^.]+)',description)[1]
            else:
                identity=await check.call('read_item',target)
                identified=identity['identity']['name']
                motif='stone'
            name,clue=CLUES[motif]
            check.stage='verify chapter edits'
            fresh=await check.edit(target,{'mystification':{'unidentified_name':name,'unidentified_description':clue,
                                                            'identification_status':'unidentified'}})
            confirmed={r['field']:r['source'] for r in fresh}
            assert confirmed=={'mystification.unidentified_name':name,'mystification.unidentified_description':clue,
                               'mystification.identification_status':'unidentified'}
            report.append([', '.join(sorted(item['locations'])),item['actor'],identified,name,clue])
        assert len(report)==20 and mundane==3 and len(items)==23 and len(references)==2
        assert unresolved==['Sealed stair'] and pages_read>inventories
        return dict(rooms=len(rooms),inventories=inventories,inventory_pages=pages_read,unique_items=len(items),
                    mundane=mundane,verified=len(report),definitions=len(references),unresolved=unresolved,rows=sorted(report))
    finally:
        removed=await check.js(CHAPTER,action='cleanup')
        assert removed=={'remaining':0}


def write_report(rows,unresolved):
    """Render only the synthetic chapter, after complete readbacks and marker cleanup."""
    path=ROOT/'.local'/'item-editing-chapter-gm.md'
    columns=['Location','Actor','Identified Item Name','Unidentified Name','Description']
    def line(cells):
        return '| '+' | '.join(str(v).replace('|','\\|').replace('\n',' ') for v in cells)+' |'
    lines=['# GM chapter rehearsal','',line(columns),line(['---']*5),*(line(r) for r in rows),'',
           'Unresolved location — '+', '.join(unresolved)+'. The ledger names no custodian for its parcel.','']
    with NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as private:
        temporary=Path(private.name)
        try:
            private.write('\n'.join(lines))
            private.flush()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    return str(path)


async def main(phase):
    token=next(line.partition('=')[2].strip() for line in (ROOT/'.env.mcp').read_text().splitlines()
               if line.partition('=')[0].strip()=='FOUNDRY_MCP_CALLER_TOKEN')
    transport=StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp',headers={'Authorization':'Bearer '+token})
    async with Client(transport,timeout=25,init_timeout=10) as client:
        check=Check(client,uuid4().hex)
        try:
            async with asyncio.timeout(240):
                result=await {'baseline':baseline,'gm':gm_sheet,'player':player_and_tokens,'chapter':chapter}[phase](check)
        except Exception as exc:
            import traceback
            frame=traceback.extract_tb(exc.__traceback__)[-1]
            print(json.dumps(dict(passed=False,stage=check.stage,error=type(exc).__name__,
                                  assertion=frame.line if frame.filename==__file__ else None,calls=check.calls,
                                  detail=str(exc)[:240] if phase=='gm' else None)))
            return 1
        if phase=='chapter':
            result['report']=write_report(result.pop('rows'),result['unresolved'])
        print(json.dumps(dict(passed=True,phase=phase,calls=check.calls,result=result)))
        return 0


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['baseline','gm','player','chapter'])
    raise SystemExit(asyncio.run(main(parser.parse_args().phase)))
