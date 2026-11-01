"""Bounded read-only publisher audit, exact source reconstruction and guards."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest


SPEC = importlib.util.spec_from_file_location('journal_html_audit', Path(__file__).resolve().parents[1] / 'scripts/journal-html-live-check.py')
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class FakeClient:
    def __init__(self, failure=None):
        self.failure, self.calls = failure, []
        self.parts = ['<p>😀', 'Source</p>']
        self.page = dict(name='Sample', page_uuid='JournalEntry.j.JournalEntryPage.p')

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        if name == 'get_journal_tree':
            if 'folder_id' not in args:
                value = dict(children=[dict(kind='folder', name='Seven Dooms for Sandpoint', folder_id='folder')])
            else:
                value = dict(complete=True, children=[dict(kind='journal', name=n, journal_id=str(i)) for i, n in enumerate(AUDIT.SAMPLE)])
        elif name == 'get_journal_contents':
            names = list(AUDIT.SAMPLE.values())[int(args['journal_id'])]
            value = dict(revision='contents', complete=True, next_cursor=None, pages=[dict(self.page, name=n) for n in names])
        elif name == 'read_journal_page':
            second = args.get('cursor') == 'returned-cursor'
            start = AUDIT.utf16(self.parts[0]) if second else 0
            content = self.parts[int(second)]
            value = dict(page_uuid=self.page['page_uuid'], source='html', source_present=True, revision='source',
                         offset_units='UTF-16 code units', offset=start, end_offset=start+AUDIT.utf16(content),
                         total_chars=sum(map(AUDIT.utf16, self.parts)), content=content,
                         complete=second, next_cursor=None if second else 'returned-cursor')
            if self.failure == 'revision' and second:
                value['revision'] = 'changed'
            if self.failure == 'offset' and second:
                value['offset'] += 1
            if self.failure == 'units':
                value['offset_units'] = 'utf16'
            if self.failure == 'repeat':
                value.update(complete=False, next_cursor='returned-cursor')
            if self.failure == 'identity':
                value['page_uuid'] = 'JournalEntry.other.JournalEntryPage.p'
            if self.failure == 'missing':
                value['source_present'] = False
            if self.failure == 'partial' and second:
                value['complete'] = False
            if self.failure == 'total' and second:
                value['total_chars'] += 1
            if self.failure == 'bytes':
                value['content'] = 'x' * 48001
        else:
            raise AssertionError('Unexpected or mutating MCP call')
        return SimpleNamespace(is_error=False, structured_content=value)


class AuditTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_offset_units_contract_and_exact_unicode_fragments(self):
        client = FakeClient()
        reader = AUDIT.Reader(client)
        result = await AUDIT.read_page(reader, client.page)
        self.assertEqual(result, dict(name='Sample', content=''.join(client.parts)))
        self.assertEqual(client.calls[1][1]['cursor'], 'returned-cursor')
        self.assertEqual(reader.calls, 2)

    async def test_changed_incomplete_forged_or_oversized_fragments_fail(self):
        for failure in ('revision', 'offset', 'units', 'repeat', 'identity', 'missing', 'partial', 'total', 'bytes'):
            with self.subTest(failure=failure):
                client = FakeClient(failure)
                with self.assertRaises(ValueError):
                    await AUDIT.read_page(AUDIT.Reader(client), client.page)

    async def test_full_sampling_uses_only_discovered_read_selectors_within_budget(self):
        client = FakeClient()
        reader = AUDIT.Reader(client)
        samples = await AUDIT.collect_samples(reader)
        self.assertEqual(len(samples), 18)
        self.assertTrue(all(s['content'] == ''.join(client.parts) for s in samples))
        self.assertEqual(reader.calls, 46)
        self.assertEqual(set(n for n, _ in client.calls), AUDIT.READ_TOOLS)

    async def test_call_budget_and_mutations_are_rejected_before_dispatch(self):
        client = FakeClient()
        reader = AUDIT.Reader(client)
        with self.assertRaises(ValueError):
            await reader.call('write_journal', {})
        reader.calls = 48
        with self.assertRaises(ValueError):
            await reader.call('read_journal_page', {})
        self.assertEqual(client.calls, [])

    def test_endpoint_rejects_other_hosts_profiles_and_credentials(self):
        AUDIT.validate_endpoint('ws://127.0.0.1:9222/devtools/page/test', 9222)
        for url in ('ws://example.org:9222/devtools/page/test', 'ws://127.0.0.1:9223/devtools/page/test',
                    'ws://user:secret@127.0.0.1:9222/devtools/page/test',
                    'ws://127.0.0.1:9222/devtools/browser/test', 'ws://127.0.0.1:9222/devtools/page/test?x=1'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                AUDIT.validate_endpoint(url, 9222)

    def test_browser_expression_uses_serialized_data_and_no_dom_insertion(self):
        samples = [dict(name='Sample', content='<p>";throw Error("not code");</p>')] * 18
        expression = AUDIT.browser_expression(samples)
        self.assertIn('const samples=' + json.dumps(samples), expression)
        self.assertIn("game.world.id!=='test'", expression)
        self.assertNotIn('document.body', expression)
        self.assertNotIn('insertAdjacentHTML', expression)
        with self.assertRaises(ValueError):
            AUDIT.browser_expression(samples[:1])


if __name__ == '__main__':
    unittest.main()
