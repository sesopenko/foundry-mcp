"""Private challenge isolation and reviewed-evidence state; no real-client proof."""
import copy
import io
import json
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest

from PIL import Image,ImageChops
from foundry_mcp_server import image_preview_visual_handoff as handoff
from foundry_mcp_server import image_preview_visual_fixture as fixture
import test_image_preview_live_check as live_helpers


def observed(expected):
    url='https://preview.example/image-previews/00000000-0000-4000-8000-000000000000.png'
    result={}
    for index,name in enumerate(('hidden_workflow','exact_link_trial','query_link_trial','map_workflow')):
        result[name]=dict(provenance='reviewed_target_client_trace',client='ChatGPT',context_id='context'+str(index),
            trace_sha256='abcd'[index]*64,fetched_url=url+('?probe=1' if name=='query_link_trial' else ''),client_fetch_observed=True,
            answer=expected['label']+' '+','.join(expected['colors']),info_call_observed=True,requested_region=expected['region'],
            browse_observed=True,level_selection_observed=True,map_notes_requested=True,key_read_from_pixels=True,
            legend_matches_rendered_key=True,journal_page_followed=True)
    return result


class HandoffTests(unittest.TestCase):
    def test_random_answer_is_only_in_selected_pixels_and_private_expected_data(self):
        pixels,expected=handoff.challenge()
        self.assertTrue(expected['label'].startswith('Q'));self.assertNotEqual(*expected['colors'])
        with Image.open(io.BytesIO(pixels)) as decoded:
            self.assertEqual(decoded.size,(1024,768));self.assertFalse(decoded.info)
            delta=ImageChops.difference(decoded,Image.new('RGB',decoded.size,(225,225,225)))
            left,top,right,bottom=delta.getbbox();region=expected['region']
            self.assertGreaterEqual(left,region['x']);self.assertGreaterEqual(top,region['y'])
            self.assertLessEqual(right,region['x']+region['width']);self.assertLessEqual(bottom,region['y']+region['height'])
            self.assertEqual(decoded.getpixel((region['x']+120,region['y']+120)),handoff.COLORS[expected['colors'][1]])
        self.assertRegex(expected['label'],r'^Q[GHJKLMNPQRSTUVWXYZ23456789]{5}$')

    def test_private_bundle_permissions_opaque_name_and_nonrevealing_prompts(self):
        with tempfile.TemporaryDirectory() as parent:
            directory=Path(parent)/'handoff';report=handoff.create_bundle(directory)
            expected,state=handoff.load_bundle(directory)
            self.assertEqual(directory.stat().st_mode&0o777,0o700)
            for path in directory.iterdir():self.assertEqual(path.stat().st_mode&0o777,0o600)
            self.assertRegex(state['filename'],r'^[a-f0-9]{32}\.png$')
            public=json.dumps(report)+str((directory/'prompts.json').read_text())+state['filename']
            self.assertNotIn(expected['label'].casefold(),public.casefold())
            for color in expected['colors']:self.assertIsNone(re.search(r'\b'+color+r'\b',public,re.I))
            self.assertEqual(report['visual_acceptance'],'pending');self.assertFalse(report['fixture_ready'])
            self.assertEqual(set(report['scenarios'].values()),{'pending'})
            with self.assertRaises(FileExistsError):handoff.create_bundle(directory)

    def test_only_complete_reviewed_target_evidence_can_produce_pass(self):
        _,expected=handoff.challenge();evidence=observed(expected)
        self.assertEqual(set(handoff.evaluate(expected,evidence).values()),{'passed'})
        for field,value in [('provenance','model_self_report'),('client','Codex'),('trace_sha256','no-trace')]:
            broken=copy.deepcopy(evidence);broken['hidden_workflow'][field]=value
            with self.assertRaises(ValueError):handoff.evaluate(expected,broken)
        broken=copy.deepcopy(evidence);broken['hidden_workflow']['info_call_observed']=False
        self.assertEqual(handoff.evaluate(expected,broken)['hidden_workflow'],'failed')
        broken=copy.deepcopy(evidence);broken['hidden_workflow']['requested_region']={**expected['region'],'x':0}
        self.assertEqual(handoff.evaluate(expected,broken)['hidden_workflow'],'failed')
        broken=copy.deepcopy(evidence);broken['hidden_workflow']['answer']='No pixel answer'
        self.assertEqual(handoff.evaluate(expected,broken)['hidden_workflow'],'failed')

    def test_exact_and_query_trials_require_same_capability_only_probe_and_fresh_contexts(self):
        _,expected=handoff.challenge();evidence=observed(expected)
        for field,value in [('context_id','context1'),('trace_sha256','b'*64),
                ('fetched_url',evidence['query_link_trial']['fetched_url'].replace('probe=1','probe=2')),
                ('fetched_url',evidence['query_link_trial']['fetched_url'].replace('00000000-0000','10000000-0000'))]:
            broken=copy.deepcopy(evidence);broken['query_link_trial'][field]=value
            self.assertEqual(handoff.evaluate(expected,broken)['query_link_trial'],'failed')

    def test_map_pixel_key_legend_and_omission_evidence_are_independent(self):
        _,expected=handoff.challenge();evidence=observed(expected)
        for field in ('browse_observed','level_selection_observed','map_notes_requested','key_read_from_pixels','legend_matches_rendered_key','journal_page_followed'):
            broken=copy.deepcopy(evidence);broken['map_workflow'][field]=False
            self.assertEqual(handoff.evaluate(expected,broken)['map_workflow'],'failed')
        evidence['map_workflow']['annotation_omitted_count']=3
        self.assertEqual(handoff.evaluate(expected,evidence)['map_workflow'],'failed')
        evidence['map_workflow']['omissions_reported']=True
        self.assertEqual(handoff.evaluate(expected,evidence)['map_workflow'],'passed')

    def test_report_never_echoes_private_answers_urls_or_trace_content(self):
        with tempfile.TemporaryDirectory() as parent:
            directory=Path(parent)/'handoff';handoff.create_bundle(directory);expected,_=handoff.load_bundle(directory)
            report=handoff.public_report(directory,observed(expected))
            self.assertEqual(report['visual_acceptance'],'passed')
            for private in (expected['label'],'image-previews/','context0','a'*64):self.assertNotIn(private,json.dumps(report))

    def test_symlinked_private_expected_file_is_rejected_before_read(self):
        with tempfile.TemporaryDirectory() as parent:
            directory=Path(parent)/'handoff';handoff.create_bundle(directory)
            path=directory/'expected.json';path.unlink();path.symlink_to('/etc/hosts')
            with self.assertRaises(ValueError):handoff.load_bundle(directory)


class FixtureClient:
    def __init__(self,fail_page=False):self.calls=[];self.fail_page=fail_page
    async def call_tool(self,name,args,**_):
        self.calls.append((name,args))
        if name=='execute_javascript':
            value=dict(map_name='Map',ancestry='Adventure / Chapter',level_name='Floor') if 'Representative map unavailable' in args['code'] else dict(journals_remaining=0,folders_remaining=0)
            raw=dict(value=json.dumps(value))
        elif name=='get_writing_guidance':raw=dict(timestamp='2050-01-01T00:00:00Z')
        elif name=='get_journal_write_context':raw=dict(revision='a'*64)
        elif name=='write_journal':
            page=args['action']['operation']=='create_page'
            if page and self.fail_page:return SimpleNamespace(is_error=True,structured_content=None)
            raw=dict(identity=dict(page_uuid='JournalEntry.fixture.JournalEntryPage.page') if page else dict(journal_id='fixture'))
        else:raise AssertionError('Unexpected preparation tool')
        return SimpleNamespace(is_error=False,structured_content=raw)


class VisualFixtureTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_preparation_after_cleanup_uses_fresh_operation_ids_with_retained_write_receipts(self):
        class LedgerClient(FixtureClient):
            def __init__(self):super().__init__();self.alive=False;self.receipts={}
            async def call_tool(self,name,args,**kwargs):
                if name=='write_journal' and args['action']['operation']=='create_journal':
                    request_id=args['request_id']
                    if request_id in self.receipts:return self.receipts[request_id]
                    self.alive=True
                    value=await super().call_tool(name,args,**kwargs);self.receipts[request_id]=value;return value
                if name=='get_journal_write_context' and not self.alive:return SimpleNamespace(is_error=True,structured_content=None)
                if name=='execute_javascript' and 'Representative map unavailable' not in args['code']:self.alive=False
                return await super().call_tool(name,args,**kwargs)
        with tempfile.TemporaryDirectory() as parent:
            root=Path(parent);data=root/'data';data.mkdir();bundle=root/'handoff';handoff.create_bundle(bundle)
            client=LedgerClient()
            await fixture.prepare(client,bundle,data,live_helpers.live.fixture)
            await fixture.cleanup(client,bundle,data,live_helpers.live.fixture)
            second=await fixture.prepare(client,bundle,data,live_helpers.live.fixture)
            self.assertTrue(second['fixture_ready']);self.assertEqual(len(client.receipts),2)
            await fixture.cleanup(client,bundle,data,live_helpers.live.fixture)

    async def test_preparation_retains_only_marked_fixture_and_delegated_cleanup_resets_prompts(self):
        with tempfile.TemporaryDirectory() as parent:
            root=Path(parent);data=root/'data';data.mkdir();bundle=root/'handoff';handoff.create_bundle(bundle)
            client=FixtureClient();report=await fixture.prepare(client,bundle,data,live_helpers.live.fixture)
            self.assertTrue(report['fixture_ready']);self.assertEqual(report['visual_acceptance'],'pending')
            self.assertEqual(report['public_urls_issued'],0);self.assertEqual(report['calls'],5)
            expected,state=handoff.load_bundle(bundle);assets=list(data.iterdir());self.assertEqual(len(assets),1)
            self.assertEqual((assets[0]/('α '+state['marker']+'.png')).read_bytes(),(bundle/state['filename']).read_bytes())
            prompts=(bundle/'prompts.json').read_text();self.assertIn('JournalEntry.fixture.JournalEntryPage.page',prompts)
            self.assertIn('choose level Floor',prompts)
            self.assertNotIn(expected['label'],prompts)
            for name,args in client.calls:
                if name=='write_journal':self.assertNotIn(expected['label'],json.dumps(args))
            cleaned=await fixture.cleanup(client,bundle,data,live_helpers.live.fixture)
            self.assertTrue(cleaned['cleanup_complete']);self.assertEqual(list(data.iterdir()),[])
            self.assertFalse(handoff.load_bundle(bundle)[1]['ready'])
            self.assertNotIn('JournalEntry.fixture', (bundle/'prompts.json').read_text())

    async def test_failed_page_creation_delegates_exact_marker_cleanup_without_issuing_urls(self):
        with tempfile.TemporaryDirectory() as parent:
            root=Path(parent);data=root/'data';data.mkdir();bundle=root/'handoff';handoff.create_bundle(bundle)
            client=FixtureClient(fail_page=True)
            with self.assertRaises(ValueError):await fixture.prepare(client,bundle,data,live_helpers.live.fixture)
            self.assertEqual(list(data.iterdir()),[])
            self.assertFalse(handoff.load_bundle(bundle)[1]['ready'])
            self.assertEqual(client.calls[-1][0],'execute_javascript')
            self.assertNotIn('get_foundry_image_url',[name for name,_ in client.calls])
