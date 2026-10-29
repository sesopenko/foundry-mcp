"""Offline typed journal-flow proof, forged responses and read-only witness guards."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('actor_journal_live',ROOT/'scripts/actor-journal-live-check.py')
HARNESS=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(HARNESS)
PAGE='JournalEntry.j.JournalEntryPage.p'
ACTOR='Actor.actual'
ITEM=ACTOR+'.Item.owned'
PROSE='<p>Exact 😀 action requirements.</p>'


def utf16(value):
    return len(value.encode('utf-16-le'))//2


def response(value):
    return SimpleNamespace(structured_content=value)


class FlowClient:
    def __init__(self,failure=None,item_type='action'):
        self.failure,self.item_type=failure,item_type
        self.calls=[];self.fingerprints=0;self.journal_reads=0
        self.reference=dict(target=ACTOR,resolve_next_call=dict(tool='resolve_journal_reference',arguments=dict(page_uuid=PAGE,source='html',target=ACTOR)))
        self.journal_parts=['<p>@UUID[Actor.actual]{Creature} 😀</p>','<p>Original ending.</p>']

    async def list_tools(self):
        self.calls.append(('list_tools',{}))
        if self.failure=='discovery_transport':raise RuntimeError('PRIVATE_FAILURE_SOURCE')
        return [SimpleNamespace(name=name,annotations=SimpleNamespace(readOnlyHint=True)) for name in
                ('search_journals','read_journal_page','resolve_journal_reference','read_actor','list_actor_items','read_item')]

    async def call_tool(self,name,args):
        self.calls.append((name,args))
        if self.failure=='transport':raise RuntimeError('PRIVATE_FAILURE_SOURCE')
        if name=='search_journals':
            assert args['query']=='Zantus' and args['limit']==2
            second=args.get('cursor')=='search-returned'
            matches=[dict(page_name='The Violated Grave',page_uuid=PAGE)] if second else []
            return response(dict(revision='search',matches=matches,next_cursor=None if second else 'search-returned',complete=second))
        if name=='read_journal_page':
            assert args['page_uuid']==PAGE and args['source']=='html' and args['max_chars']==20000
            index=1 if args.get('cursor')=='journal-returned' else 0
            self.journal_reads+=1
            content=self.journal_parts[index]
            if self.failure=='journal_changed' and self.journal_reads>2:content+='changed'
            offset=utf16(self.journal_parts[0]) if index else 0
            value=dict(revision='journal',offset=offset,end_offset=offset+utf16(content),content=content,
                       references=[self.reference] if index==0 else [],references_complete=True,
                       next_cursor=None if index else 'journal-returned',complete=bool(index),
                       total_chars=sum(map(utf16,self.journal_parts)))
            if self.failure=='journal_revision' and index:value['revision']='changed'
            if self.failure=='journal_repeated_cursor':value.update(next_cursor='journal-returned',complete=False)
            if self.failure=='journal_oversize':value['unselected']='x'*48001
            return response(value)
        if name=='resolve_journal_reference':
            assert args==self.reference['resolve_next_call']['arguments']
            return response(dict(status='resolved',identity=dict(document_name='Actor',uuid=ACTOR),next_call=dict(tool='read_actor',arguments=dict(actor_uuid=ACTOR))))
        if name=='read_actor':
            assert args==dict(actor_uuid=ACTOR,sections=['identity'])
            return response(dict(identity=dict(uuid=ACTOR,source_kind='world')))
        if name=='list_actor_items':
            assert args==dict(actor_uuid=ACTOR,types=['action','spell'],limit=1,max_bytes=8000)
            node=dict(identity=dict(uuid=ITEM,type=self.item_type,actor=dict(uuid=ACTOR)),next_call=dict(tool='read_item',arguments=dict(item_uuid=ITEM)))
            if self.failure=='wrong_type':node['identity']['type']='equipment'
            if self.failure=='wrong_owner':node['identity']['actor']['uuid']='Actor.other'
            return response(dict(nodes=[] if self.failure=='no_owned' else [node]))
        if name=='execute_javascript':
            assert json.dumps(ACTOR) in args['code'] and json.dumps(ITEM) in args['code']
            self.fingerprints+=1
            value=dict(source_hash='source',description_hash=hashlib.sha256(PROSE.encode()).hexdigest(),description_length=utf16(PROSE),type=self.item_type)
            if self.failure=='fingerprint_changed' and self.fingerprints>1:value['source_hash']='changed'
            return response(dict(value=json.dumps(value)))
        if name=='read_item':
            assert args['item_uuid']==ITEM and args['sections']==['source','description'] and args['limit']==7 and args['max_bytes']==48000
            raw=dict(document_uuid=ITEM,path='/name',present=True,value='Owned',basis='source')
            source=dict(key='source:/name',section='source',kind='field',raw=[raw])
            pieces=[PROSE[:10],PROSE[10:]]
            rows=[source]
            start=0
            for i,piece in enumerate(pieces):
                end=start+utf16(piece)
                rows.append(dict(key='description:'+str(i),section='description',kind='text',raw=[dict(document_uuid=ITEM,path='/system/description/value',present=True,value=piece,basis='source')],text=dict(path='/system/description/value',start=start,end=end,total=utf16(PROSE),complete=i==1)))
                start=end
            if self.failure=='missing_source':rows=rows[1:]
            if self.failure=='missing_prose':rows=[source]
            if self.failure=='forged_prose':rows[-1]['raw'][0]['value']='forged'
            index=int(args.get('cursor','0'))
            selected=rows[index:index+1]
            cursor=str(index+1) if index+1<len(rows) else None
            if self.failure=='item_repeated_cursor':cursor='1'
            value=dict(identity=dict(uuid=ITEM,type=self.item_type,actor=dict(uuid=ACTOR)),revision='item',records=selected,
                       sections=[dict(name=name,status='partial' if cursor else 'complete') for name in ('source','description')],pagination=dict(next_cursor=cursor))
            if self.failure=='child_wrong_owner':value['identity']['actor']['uuid']='Actor.other'
            if self.failure=='item_revision' and index:value['revision']='changed'
            if self.failure=='item_oversize':value['unselected']='x'*48001
            return response(value)
        raise AssertionError('Unexpected or mutating call: '+name)


class JournalFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_returned_selectors_and_cursors_reach_typed_owned_exact_prose(self):
        for item_type in ('action','spell'):
            client=FlowClient(item_type=item_type)
            report=await HARNESS.verify(client)
            self.assertTrue(report['passed'],report)
            self.assertEqual(report['selected_item_type'],item_type)
            self.assertEqual(report['item_pages'],3)
            self.assertEqual(report['description_fragments'],2)
            self.assertEqual(report['journal_pages'],2)
            self.assertTrue(report['exact_prose_verified'] and report['source_fingerprints_unchanged'] and report['journal_unchanged'])
            self.assertEqual(report['requested_calls'],len(client.calls))
            self.assertEqual(report['completed_calls'],len(client.calls))
            self.assertEqual(client.fingerprints,2)

    async def test_wrong_types_owners_missing_sources_and_prose_do_not_establish_workflow(self):
        stages={'wrong_type':'typed_owned_item','wrong_owner':'typed_owned_item','no_owned':'typed_owned_item',
                'child_wrong_owner':'item_source_description','missing_source':'exact_owned_prose',
                'missing_prose':'exact_owned_prose','forged_prose':'exact_owned_prose'}
        for failure,stage in stages.items():
            with self.subTest(failure=failure):
                report=await HARNESS.verify(FlowClient(failure))
                self.assertFalse(report['passed'],report)
                self.assertEqual(report['failure_stage'],stage)

    async def test_changed_journal_fingerprints_revisions_repeated_cursors_and_byte_bounds_fail(self):
        for failure in ('journal_changed','journal_revision','journal_repeated_cursor','journal_oversize','fingerprint_changed','item_revision','item_repeated_cursor','item_oversize'):
            with self.subTest(failure=failure):
                report=await HARNESS.verify(FlowClient(failure))
                self.assertFalse(report['passed'],report)

    async def test_transport_failures_have_exact_counts_and_no_private_diagnostics(self):
        for failure,counts in [('transport',(2,1)),('discovery_transport',(1,0))]:
            client=FlowClient(failure)
            report=await HARNESS.verify(client)
            self.assertFalse(report['passed'])
            self.assertEqual((report['requested_calls'],report['completed_calls']),counts)
            self.assertNotIn('PRIVATE_FAILURE_SOURCE',json.dumps(report))

    async def test_main_has_bounded_client_and_safe_initialization_failure(self):
        class Session:
            async def __aenter__(self):raise RuntimeError('PRIVATE_FAILURE_SOURCE')
            async def __aexit__(self,*args):return False
        output=io.StringIO()
        with patch.object(HARNESS.Path,'read_text',return_value='FOUNDRY_MCP_CALLER_TOKEN=LOCAL_TEST_TOKEN'),patch.object(HARNESS,'StreamableHttpTransport',return_value=object()),patch.object(HARNESS,'Client',return_value=Session()) as client,contextlib.redirect_stdout(output):
            self.assertEqual(await HARNESS.main(),1)
        self.assertEqual(client.call_args.kwargs,dict(timeout=30,init_timeout=10))
        self.assertEqual(HARNESS.SESSION_TIMEOUT_SECONDS,180)
        self.assertNotIn('PRIVATE_FAILURE_SOURCE',output.getvalue())
        self.assertNotIn('LOCAL_TEST_TOKEN',output.getvalue())

    def test_actual_browser_fingerprint_enforces_world_type_and_owner_before_source(self):
        script=r"""
import {webcrypto} from 'node:crypto';Object.defineProperty(globalThis,'crypto',{value:webcrypto});
const [code,scenario]=JSON.parse(process.argv[1]);let reads=0;
globalThis.location={origin:'http://localhost:30000'};
globalThis.game={ready:true,user:{isGM:true},world:{id:scenario==='world'?'campaign':'test'},version:'14.369',system:{id:'pf2e',version:'8.6.1'}};
const actor={uuid:'Actor.actual',documentName:'Actor',testUserPermission:()=>true,toObject(flag){if(flag!==true)throw Error('Wrong basis');reads++;return {name:'Actor',system:{}};}};
const item={uuid:'Actor.actual.Item.owned',documentName:'Item',type:scenario==='type'?'equipment':'action',parent:scenario==='owner'?{}:actor,testUserPermission:()=>true,toObject(flag){if(flag!==true)throw Error('Wrong basis');reads++;return {system:{description:{value:'Exact 😀 prose'}}};}};
globalThis.foundry={utils:{fromUuid:async uuid=>uuid===actor.uuid?actor:item}};
let result,rejected=false;try{result=await new Function('return (async()=>{'+code+'})()')();}catch{rejected=true;}
console.log(JSON.stringify({result,rejected,reads}));
"""
        body=HARNESS.GUARD+HARNESS.FINGERPRINT.replace('ACTOR',json.dumps(ACTOR)).replace('ITEM',json.dumps(ITEM))+'\nreturn result;'
        for scenario in ('valid','world','type','owner'):
            process=subprocess.run(['node','--input-type=module','-e',script,json.dumps([body,scenario])],cwd=ROOT,text=True,capture_output=True,check=True,timeout=10)
            result=json.loads(process.stdout)
            self.assertEqual(result['rejected'],scenario!='valid')
            self.assertEqual(result['reads'],2 if scenario=='valid' else 0)
            if scenario=='valid':self.assertEqual(result['result']['description_length'],utf16('Exact 😀 prose'))
