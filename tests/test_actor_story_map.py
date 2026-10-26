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

    def test_deferred_story_remains_recorded_without_delivery_credit_or_ready_work(self):
        tasks={}
        for index in range(39):
            key=f'ITEM-test{index}'
            tasks[key]=tracker.Task(key,2,set(),'Complete' if index<32 else 'Not started',key)
        tasks['ITEM-test38'].status='Deferred'
        self.assertFalse(tasks['ITEM-test38'].delivered)
        report=tracker.report(tasks)
        self.assertIn('delivery stories: 38; recorded stories: 39;',report)
        self.assertIn('complete: 32;',report)
        self.assertIn('progress: 84.2%',report)
        ready,incomplete=report.split('Incomplete work and remaining prerequisites:',1)
        self.assertNotIn('- ITEM-test38:',ready)
        active,deferred=incomplete.split('Deferred backlog (outside current delivery scope):',1)
        self.assertNotIn('- ITEM-test38:',active)
        self.assertIn('- ITEM-test38: Deferred',deferred)

    def test_deferred_status_is_valid_and_active_hard_dependencies_are_rejected(self):
        path=self.directory/'stories/ITEM-affliction.md'
        path.write_text(path.read_text().replace('| Implementation status | Not started |','| Implementation status | Deferred |'))
        state_path=self.directory/'stories/CORE-state.md'
        # Make the dependency explicit in both inventories regardless of the
        # current approved delivery graph, to exercise the validation rule.
        state_text=state_path.read_text()
        lines=state_text.splitlines()
        lines=[line[:-2]+' ITEM-affliction |' if line.startswith('| Prerequisites |') and 'ITEM-affliction' not in line else line for line in lines]
        state_path.write_text('\n'.join(lines)+'\n')
        index=self.directory/'index.md'
        index_lines=index.read_text().splitlines()
        for position,line in enumerate(index_lines):
            if line.startswith('| [CORE-state:') and 'ITEM-affliction' not in line:
                cells=line.split('|');cells[4]+=' ITEM-affliction ';index_lines[position]='|'.join(cells)
        if not any('ITEM_affliction --> CORE_state' in line for line in index_lines):
            position=index_lines.index('```',next(i for i,line in enumerate(index_lines) if line=='```mermaid')+1)
            index_lines.insert(position,'  ITEM_affliction --> CORE_state')
        index.write_text('\n'.join(index_lines)+'\n')
        with self.assertRaisesRegex(ValueError,'active.*deferred|deferred.*dependency'):
            tracker.load_map(self.directory)
        # The deferred story remains valid after its active hard edge is removed
        # consistently from the story, index row and Mermaid graph.
        lines=state_path.read_text().splitlines()
        lines=['| Prerequisites | ITEM-condition ITEM-effect |' if line.startswith('| Prerequisites |') else line for line in lines]
        state_path.write_text('\n'.join(lines)+'\n')
        index_lines=index.read_text().splitlines()
        for position,line in enumerate(index_lines):
            if line.startswith('| [CORE-state:'):
                cells=line.split('|');cells[4]=' ITEM-condition ITEM-effect ';index_lines[position]='|'.join(cells)
        index.write_text('\n'.join(line for line in index_lines if 'ITEM_affliction --> CORE_state' not in line)+'\n')
        tasks=tracker.load_map(self.directory)
        self.assertEqual(len(tasks),42)
        self.assertEqual(tasks['ITEM-affliction'].status,'Deferred')
