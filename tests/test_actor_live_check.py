"""Live runner must consume protocol JSON, not generated client model classes."""
import importlib.util
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
