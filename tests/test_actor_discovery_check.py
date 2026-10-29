"""Offline selected-tool discovery and bounded secret-free diagnostics."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SPEC=importlib.util.spec_from_file_location('actor_discovery_check',Path(__file__).resolve().parents[1]/'scripts/actor-discovery-check.py')
HARNESS=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(HARNESS)


def tool(name):
    selectors=['actor_uuid','token_uuid'] if name=='read_actor' else ['item_uuid','token_uuid']
    properties={key:{} for key in selectors+['limit','max_bytes','cursor']}
    array={'type':'array','items':{'enum':['source','description']}}
    properties['sections']=array if name=='read_actor' else {'anyOf':[array,{'type':'null'}]}
    return SimpleNamespace(name=name,inputSchema={'properties':properties},annotations=SimpleNamespace(readOnlyHint=True),description='Exact book prose; bounded source reading.')


class DiscoveryCheckTests(unittest.IsolatedAsyncioTestCase):
    async def run_probe(self,tool_name=None,failure=None):
        observed={}
        class FakeClient:
            def __init__(self,transport,**options):observed['options']=options
            async def __aenter__(self):
                if failure=='connection':raise TimeoutError('private credential')
                return self
            async def __aexit__(self,*args):return False
            async def list_tools(self):
                observed['calls']=observed.get('calls',0)+1
                if failure=='discovery':raise RuntimeError('private credential')
                rows=[tool('read_actor'),tool('read_item')]
                if failure=='selectors':rows[1].inputSchema['properties'].pop('item_uuid')
                if failure=='term':rows[1].description='Other prose'
                return rows
        output=io.StringIO()
        with patch.object(HARNESS,'Client',FakeClient),patch.object(HARNESS,'StreamableHttpTransport',lambda *args,**kwargs:object()),patch.object(Path,'read_text',return_value='FOUNDRY_MCP_CALLER_TOKEN=private credential'),contextlib.redirect_stdout(output):
            args=('source',['Exact']) if tool_name is None else ('source',['Exact'],tool_name)
            status=await HARNESS.main(*args)
        self.assertNotIn('private credential',output.getvalue())
        return status,json.loads(output.getvalue()),observed

    async def test_default_actor_and_optional_item_validate_selected_schema(self):
        for selected in (None,'read_item'):
            status,result,observed=await self.run_probe(selected)
            self.assertEqual(status,0);self.assertTrue(result['passed'])
            self.assertEqual(result['tool'],selected or 'read_actor')
            self.assertEqual((result['requested_calls'],result['completed_calls']),(1,1))
            self.assertFalse(result['runtime_checked'])
            self.assertEqual(observed['options'],dict(timeout=30,init_timeout=10))
        self.assertEqual(HARNESS.SESSION_TIMEOUT_SECONDS,180)

    async def test_failure_counts_are_precise_and_no_runtime_calls_occur(self):
        for failure,counts in [('connection',(0,0)),('discovery',(1,0)),('selectors',(1,1)),('term',(1,1))]:
            status,result,_=await self.run_probe('read_item',failure)
            self.assertEqual(status,1);self.assertFalse(result['passed'])
            self.assertEqual((result['requested_calls'],result['completed_calls']),counts)
            self.assertFalse(result['runtime_checked'])

    async def test_unknown_tool_rejected_before_client_initialization(self):
        status,result,observed=await self.run_probe('write_item')
        self.assertEqual(status,1);self.assertEqual(observed,{})
        self.assertEqual(result['requested_calls'],0)
