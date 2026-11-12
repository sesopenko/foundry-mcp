"""Core map discovery contracts and bounded private baseline measurement."""
import json
import asyncio
import base64
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock,patch

import httpx2 as httpx
from fastmcp import Client,FastMCP

from foundry_mcp_server import main
from foundry_mcp_server.auth.principal import Principal,current_principal
from foundry_mcp_server.auth.metadata import OAuthToolMetadata
from foundry_mcp_server.config import Settings
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server import maps,tools
from foundry_mcp_server.mcp_server.map_models import BrowseMapsResult
from foundry_mcp_server.ws.connection import RpcError
from test_image_preview_identity import call

from foundry_mcp_server.map_browse_audit import measure,verify_browse


class MapBaselineTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_verifier_follows_next_calls_and_aggregates_without_names_or_ids(self):
        class FakeClient:
            async def list_tools(self,**_):return [SimpleNamespace(model_dump=lambda **_:dict(name='browse_maps'))]
            async def call_tool(self,name,args,**_):
                if name=='execute_javascript':data={'value':'private-active-id'}
                else:
                    folder=args.get('folder_uuid')
                    entries=([dict(kind='folder',folder_uuid='Folder.one',parent_uuid=None,name='Private folder',
                        next_call=dict(tool='browse_maps',arguments=dict(folder_uuid='Folder.one')))] if folder is None else
                        [dict(kind='map',scene_uuid='Scene.'+str(i),parent_uuid=folder,name='Private duplicate') for i in range(2)])
                    data=dict(location=dict(folder_uuid=folder),entries=entries,total=len(entries),complete=True,
                        next_cursor=None,scope_status='complete')
                return SimpleNamespace(structured_content=data,content=[],is_error=False,meta=None)
        report=await verify_browse(FakeClient())
        self.assertTrue(report['passed'])
        self.assertEqual((report['folders'],report['scenes'],report['duplicate_map_names']),(1,2,1))
        self.assertTrue(report['active_unchanged'])
        self.assertEqual(report['calls'],7)
        self.assertNotIn('Private',json.dumps(report));self.assertNotIn('private-active-id',json.dumps(report))

    async def test_live_verifier_enforces_thirty_call_cap_before_dispatch(self):
        class Endless:
            def __init__(self):self.actual=0
            async def list_tools(self,**_):
                self.actual+=1
                return [SimpleNamespace(model_dump=lambda **_:dict(name='browse_maps'))]
            async def call_tool(self,name,args,**_):
                self.actual+=1
                if name=='execute_javascript':data={'value':None}
                else:
                    parent=args.get('folder_uuid');next_id='Folder.'+str(self.actual)
                    data=dict(location=dict(folder_uuid=parent),entries=[dict(kind='folder',folder_uuid=next_id,
                        parent_uuid=parent,name='private',next_call=dict(tool='browse_maps',arguments=dict(folder_uuid=next_id)))],
                        total=1,complete=True,next_cursor=None,scope_status='complete')
                return SimpleNamespace(structured_content=data,content=[],is_error=False,meta=None)
        client=Endless();report=await verify_browse(client)
        self.assertFalse(report['passed']);self.assertEqual(report['calls'],30);self.assertEqual(client.actual,30)
        self.assertNotIn('private',json.dumps(report))

    async def test_actual_sdk_shape_counts_completion_and_only_allowlisted_aggregates(self):
        client=AsyncMock()
        client.list_tools.return_value=[SimpleNamespace(model_dump=lambda **_:dict(name='example'))]
        raw=dict(version='14.369',folders=18,scenes=50,source_fields_match=True,active_unchanged=True,
            private='never report',rows=[dict(label='root_default',entries=10,total=12,complete=False,json_bytes=2000),
                dict(label='folder_default',entries=0,total=0,complete=True,json_bytes=40)])
        client.call_tool.return_value=SimpleNamespace(structured_content={'value':json.dumps(raw)})
        report=await measure(client)
        self.assertTrue(report['passed'])
        self.assertEqual(report['calls'],2)
        self.assertEqual((report['folders'],report['scenes']),(18,50))
        self.assertFalse(report['rows'][0]['complete'])
        self.assertNotIn('never report',json.dumps(report))
        self.assertEqual(client.list_tools.await_count,1)
        self.assertEqual(client.call_tool.await_count,1)

    async def test_failures_invalid_counts_or_runtime_never_print_private_diagnostics(self):
        client=AsyncMock()
        client.list_tools.side_effect=RuntimeError('https://private.example/secret')
        report=await measure(client)
        self.assertFalse(report['passed'])
        self.assertEqual(report['calls'],1)
        self.assertNotIn('secret',json.dumps(report))
        client.list_tools.side_effect=None
        client.list_tools.return_value=[]
        for data in (dict(version='13'),dict(version='14.369',source_fields_match=False,active_unchanged=True),
                dict(version='14.369',source_fields_match=True,active_unchanged=True,rows=[dict(label='root_default',entries=True,total=1,complete=True)])):
            client.call_tool.return_value=SimpleNamespace(structured_content={'value':json.dumps(data)})
            self.assertFalse((await measure(client))['passed'])


class MapBrowseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folders=[dict(id='chapter',name='Chapter'),dict(id='bonus1',name='Bonus Flip Mats',folder='chapter'),
            dict(id='bonus2',name='Bonus Flip Mats',folder='chapter'),dict(id='empty',name='Empty')]
        self.scenes=[dict(id='one',name='Same map',folder='bonus1'),dict(id='two',name='Same map',folder='bonus1'),
            dict(id='noimage',name='No image')]
        self.manager=SimpleNamespace(websockets={'gm':object()},call=AsyncMock(side_effect=self.node))
        self.identity=Principal('basic','','gm','configured-account')
        self.enterContext(patch.object(tools,'_foundry_manager',self.manager))
        self.enterContext(patch.object(maps,'current_principal',lambda:self.identity))

    async def node(self,client_id,method,params,timeout):
        self.assertEqual((client_id,method),('gm','browseMaps'))
        process=await asyncio.create_subprocess_exec('node',str(Path(__file__).parent/'js/fixtures/map-browse-rpc.js'),
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
        try:
            output,_=await asyncio.wait_for(process.communicate(json.dumps(dict(params=params,folders=self.folders,scenes=self.scenes)).encode()),5)
        except BaseException:
            if process.returncode is None:process.kill()
            await process.wait()
            raise
        self.assertEqual(process.returncode,0,'Map test runtime failed')
        reply=json.loads(output)
        if reply.get('error'):raise RpcError(reply['error'])
        return reply['result']

    async def invoke(self,args):
        async with Client(mcp) as client:
            return await client.call_tool('browse_maps',args,raise_on_error=False)

    async def test_actual_mcp_js_navigation_duplicate_identities_empty_and_non_pf2e(self):
        root=await self.invoke({})
        self.assertFalse(root.is_error)
        page=BrowseMapsResult.model_validate(root.structured_content)
        self.assertEqual(page.location.folder_uuid,None)
        folder=next(e for e in page.entries if e.name=='Chapter')
        chapter=await self.invoke(folder.next_call.arguments.model_dump())
        self.assertFalse(chapter.is_error)
        entries=chapter.structured_content['entries']
        self.assertEqual([e['name'] for e in entries],['Bonus Flip Mats','Bonus Flip Mats'])
        self.assertNotEqual(entries[0]['folder_uuid'],entries[1]['folder_uuid'])
        maps_page=await self.invoke(entries[0]['next_call']['arguments'])
        self.assertFalse(maps_page.is_error)
        self.assertEqual([e['scene_uuid'] for e in maps_page.structured_content['entries']],['Scene.one','Scene.two'])
        self.assertEqual(maps_page.structured_content['entries'][0]['ancestry'][0]['name'],'Chapter')
        empty=await self.invoke({'folder_uuid':'Folder.empty'})
        self.assertEqual(empty.structured_content['entries'],[])
        self.assertTrue(empty.structured_content['complete'])
        self.assertTrue(all(call.args[2]['caller_key']==self.manager.call.await_args.args[2]['caller_key'] for call in self.manager.call.await_args_list))

    async def test_actual_discovery_schemas_flat_defaults_bounds_guidance_and_oauth(self):
        async with Client(mcp) as client:
            tool=next(t for t in await client.list_tools() if t.name=='browse_maps')
        self.assertFalse(tool.input_schema['additionalProperties'])
        self.assertEqual(set(tool.input_schema['properties']),{'folder_uuid','name_contains','limit','max_bytes','cursor'})
        self.assertEqual(tool.input_schema['properties']['limit']['default'],10)
        self.assertEqual(tool.input_schema['properties']['max_bytes']['minimum'],1024)
        self.assertEqual(set(tool.output_schema['properties']),set(BrowseMapsResult.model_fields))
        self.assertFalse(tool.output_schema['additionalProperties'])
        self.assertTrue(tool.annotations.read_only_hint)
        for term in ('get_map_info','not_checked','partial','name_truncated','ContentChanged','PF2e'):
            self.assertIn(term,tool.description)
        server=FastMCP('map-oauth-discovery');server.add_middleware(OAuthToolMetadata())
        server.add_tool(await mcp.get_tool('browse_maps'))
        async with Client(server) as client:
            self.assertEqual((await client.list_tools())[0].meta['securitySchemes'][0]['scopes'],['foundry:gm'])
        print('MAP_BROWSE_DISCOVERY_BYTES',len(json.dumps(tool.model_dump(by_alias=True),ensure_ascii=False,separators=(',',':')).encode()))

    async def test_invalid_inputs_and_untrusted_caller_context_fail_before_document_reads(self):
        for args in ({'folder_uuid':'Chapter'},{'folder_uuid':'Scene.one'},{'limit':True},{'max_bytes':1000},
                {'caller_key':'forged'},{'unknown':True},{'name_contains':False},{'cursor':'not-base64'}):
            self.assertTrue((await self.invoke(args)).is_error)
        self.manager.call.assert_not_awaited()
        with patch.object(maps,'current_principal',current_principal):
            self.assertTrue((await self.invoke({})).is_error)
        self.manager.call.assert_not_awaited()
        self.manager.websockets.clear()
        result=await self.invoke({})
        self.assertIn('BridgeUnavailable',str(result.content))

    async def test_real_pagination_binds_principal_filter_and_revision_with_bounds_changes(self):
        first=await self.invoke({'limit':1})
        self.assertFalse(first.is_error)
        cursor=first.structured_content['next_cursor']
        rest=await self.invoke({'limit':100,'max_bytes':48000,'cursor':cursor})
        self.assertTrue(rest.structured_content['complete'])
        self.identity=Principal('basic','','other','configured-account')
        other=await self.invoke({'cursor':cursor})
        self.assertIn('InvalidCursor',str(other.content))
        self.identity=Principal('basic','','gm','configured-account')
        filtered=await self.invoke({'cursor':cursor,'name_contains':'Empty'})
        self.assertIn('InvalidCursor',str(filtered.content))
        self.scenes[0]['name']='Changed'
        stale=await self.invoke({'cursor':cursor})
        self.assertIn('ContentChanged',str(stale.content))

    async def test_denied_partial_scope_and_browser_errors_are_sanitized(self):
        self.scenes[2]['allowed']=False
        page=await self.invoke({})
        self.assertFalse(page.is_error)
        self.assertEqual(page.structured_content['scope_status'],'partial')
        self.assertNotIn('No image',json.dumps(page.structured_content))
        self.manager.call.side_effect=RpcError({'code':'PermissionDenied','message':'private diagnostic sentinel'})
        denied=await self.invoke({})
        self.assertIn('PermissionDenied',str(denied.content))
        self.assertNotIn('private diagnostic sentinel',str(denied.content))

    async def test_adapter_rejects_forged_response_fields_context_counts_and_followups(self):
        valid=(await self.invoke({})).structured_content
        corruptions=[{**valid,'private':'never leak'},{**valid,'total':100},{**valid,'complete':False},
            {**valid,'location':{**valid['location'],'folder_uuid':'Folder.other'}},
            {**valid,'entries':[{**valid['entries'][0],'parent_uuid':'Folder.other'},*valid['entries'][1:]]},
            {**valid,'entries':[{**valid['entries'][0],'next_call':{'tool':'browse_maps','arguments':{'folder_uuid':'Folder.wrong'}}},*valid['entries'][1:]]},
            {**valid,'entries':[{**valid['entries'][0],'ancestry':[{'folder_uuid':'Folder.wrong','name':'Wrong','name_truncated':False}]},*valid['entries'][1:]]}]
        self.manager.call.side_effect=None
        for broken in corruptions:
            self.manager.call.return_value=broken
            result=await self.invoke({})
            self.assertTrue(result.is_error)
            self.assertIn('InvalidFoundryResponse',str(result.content))
            self.assertNotIn('never leak',str(result.content))

    async def test_socket_replacement_during_rpc_never_publishes_metadata(self):
        real=self.node
        async def changed(*args,**kwargs):
            data=await real(*args,**kwargs);self.manager.websockets['gm']=object();return data
        self.manager.call.side_effect=changed
        result=await self.invoke({})
        self.assertTrue(result.is_error)
        self.assertIn('ContextChanged',str(result.content))

    async def test_production_http_basic_authority_and_plain_none_boundary(self):
        for config,credential,allowed in ((Settings(auth_mode='basic',basic_username='gm',basic_password='password',bridge_token='browser'),
                'Basic Z206cGFzc3dvcmQ=',True),(Settings(),None,False)):
            with patch.object(main,'settings',config),patch.object(maps,'current_principal',lambda:current_principal(config)):
                async with main.app.router.lifespan_context(main.app),httpx.AsyncClient(transport=httpx.ASGITransport(
                        app=main.app,client=('127.0.0.1',1234)),base_url='https://mcp.example.com') as client:
                    response=await call(client,'browse_maps',{},credential)
                    self.assertEqual(response.status_code,200)
                    result=response.json()['result']
                    self.assertEqual(not result.get('isError',False),allowed)
                    if allowed:
                        BrowseMapsResult.model_validate(result['structuredContent'])
                        before=self.manager.call.await_count
                        self.assertEqual((await call(client,'browse_maps')).status_code,401)
                        self.assertEqual(self.manager.call.await_count,before)
                    else:self.assertIn('AuthenticatedContextRequired',response.text)
