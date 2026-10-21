"""Dependency tracking must reject cycles, premature completion and graph drift."""
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('actor_story_map', ROOT / 'scripts/actor-story-map.py')
tracker = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tracker
spec.loader.exec_module(tracker)


class StoryMapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'map'
        shutil.copytree(ROOT / 'docs/actor-item-story-map', self.directory)
        # Tests need a stable initial state even as real stories advance.
        for path in (self.directory / 'stories').glob('*.md'):
            text = path.read_text()
            text = tracker.re.sub(r'^\| Implementation status \|.*$', '| Implementation status | Not started |', text, flags=tracker.re.M)
            text = tracker.re.sub(r'^\| Integrated status \|.*$', '| Integrated status | Not started |', text, flags=tracker.re.M)
            path.write_text(text)

    def test_real_backlog_and_ready_transition(self):
        tasks = tracker.load_map(self.directory)
        self.assertEqual(len(tasks), 42)
        self.assertEqual([t.identifier for t in tasks.values() if all(tasks[d].delivered for d in t.dependencies)], ['CORE-contract'])
        path = self.directory / 'stories/CORE-contract.md'
        path.write_text(path.read_text().replace('| Implementation status | Not started |', '| Implementation status | Complete |'))
        report = tracker.report(tracker.load_map(self.directory))
        self.assertIn('complete: 1;', report)
        self.assertIn('- CORE-extract: Not started (owner CORE-extract)', report)
        self.assertNotIn('- ITEM-action: Not started (owner', report)

    def test_premature_completion_and_unknown_status_are_rejected(self):
        path = self.directory / 'stories/CORE-extract.md'
        original = path.read_text()
        path.write_text(original.replace('| Implementation status | Not started |', '| Implementation status | Complete |'))
        with self.assertRaisesRegex(ValueError, 'before its prerequisites'):
            tracker.load_map(self.directory)
        path.write_text(original.replace('| Implementation status | Not started |', '| Implementation status | almost done |'))
        with self.assertRaisesRegex(ValueError, 'unknown status'):
            tracker.load_map(self.directory)

    def test_graph_drift_and_actor_integration_are_independent(self):
        path = self.directory / 'index.md'
        path.write_text(path.read_text().replace('  CORE_contract --> CORE_extract\n', ''))
        with self.assertRaisesRegex(ValueError, 'Mermaid edges'):
            tracker.load_map(self.directory)
        source = tracker.Task('ACT-npc', 2, set(), 'Source implemented', 'ACT-npc')
        integration = tracker.Task('M-NPC', 3, {'ACT-npc'}, 'Not started', 'ACT-npc')
        self.assertTrue(source.delivered)
        self.assertFalse(integration.delivered)
        report = tracker.report({'ACT-npc': source, 'M-NPC': integration})
        self.assertIn('complete: 0;', report)
        self.assertIn('- M-NPC: Not started (owner ACT-npc)', report)

    def test_same_stage_cycle_is_rejected(self):
        path = self.directory / 'stories/CORE-contract.md'
        path.write_text(path.read_text().replace('| Prerequisites | None; start here. |', '| Prerequisites | CORE-extract |'))
        path = self.directory / 'index.md'
        lines = path.read_text().splitlines()
        lines = [line.replace('| — |', '| CORE-extract |') if line.startswith('| [CORE-contract:') else line for line in lines]
        path.write_text('\n'.join(lines) + '\n')
        with self.assertRaisesRegex(ValueError, 'Dependency cycle'):
            tracker.load_map(self.directory)

    def test_actor_story_cannot_close_at_source_checkpoint(self):
        for identifier in ('CORE-contract', 'CORE-extract', 'ACT-npc'):
            path = self.directory / 'stories' / f'{identifier}.md'
            path.write_text(path.read_text().replace('| Implementation status | Not started |', '| Implementation status | Complete |'))
        with self.assertRaisesRegex(ValueError, 'integrated checkpoint'):
            tracker.load_map(self.directory)
