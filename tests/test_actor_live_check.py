"""Live runner must consume protocol JSON, not generated client model classes."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

spec=importlib.util.spec_from_file_location('actor_live_check',Path(__file__).resolve().parents[1]/'scripts/actor-live-check.py')
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class LivePayloadTests(unittest.TestCase):
    def test_generated_client_models_do_not_replace_protocol_json(self):
        result=SimpleNamespace(data=object(),structured_content={'module_status':'connected'})
        self.assertEqual(runner.payload(result),{'module_status':'connected'})

    def test_text_only_tools_remain_usable(self):
        result=SimpleNamespace(data=object(),structured_content=None,
                               content=[SimpleNamespace(type='text',text='{"value":"ok"}')])
        self.assertEqual(runner.payload(result),{'value':'ok'})

    def test_long_probe_json_uses_bounded_chunks_and_rejects_truncation(self):
        expected={'selectors':['x'*100 for _ in range(20)]}
        encoded=json.dumps(expected)
        chunks=[encoded[i:i+800] for i in range(0,len(encoded),800)]
        self.assertEqual(runner.probe({'value':{'$type':'Array','values':chunks,'truncated':False}}),expected)
        with self.assertRaises(ValueError):runner.probe({'value':{'$type':'Array','values':chunks[:1],'truncated':True}})
        with self.assertRaises(ValueError):runner.probe({'value':encoded[:1000]})
