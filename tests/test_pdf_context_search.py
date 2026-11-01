"""Synthetic source/metadata boundaries; no private book content."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from dataclasses import replace

from foundry_mcp_server.pdf.config import PDFConfig
from foundry_mcp_server.pdf.library import Library, LibraryError
from foundry_mcp_server.pdf import search_context


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.library = Library(PDFConfig(True, root/'books', root/'state'))
        self.library.setup()
        self.identifier = 'a'*32
        with self.library.db() as db:
            db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)',
                       (self.identifier, 'Synthetic.pdf', 'b'*64, 1, 'ready', 'b'*64, 1, None))
            db.execute('INSERT INTO pages VALUES(?,?,?,?,?)',
                       (self.identifier, 1, 'i', 'A checkpoint requires a careful approach.', '["sparse_text_no_ocr"]'))
            db.execute('INSERT INTO page_fts VALUES(?,?,?)',
                       (self.identifier, 1, 'A checkpoint requires a careful approach.'))
            db.execute('INSERT INTO entries VALUES(?,?,?,?,?)',
                       (self.identifier, 1, 'Infiltration', json.dumps(['Subsystems']), 'bookmark'))
        self.library.setup()

    def test_cross_field_retrieval_preserves_source(self):
        result = self.library.search('Infiltration checkpoint')['candidates']
        self.assertEqual([r['physical_page'] for r in result], [1])
        self.assertEqual(self.library.search('Infiltration checkpoint', search_mode='text')['candidates'], [])
        self.assertEqual(self.library.search('Infiltration checkpoint nonexistent')['candidates'], [])
        self.assertEqual(self.library.read(self.identifier, 1)['text'], 'A checkpoint requires a careful approach.')

    def test_explanation_selection_and_ancestor_boundary(self):
        compact = self.library.search('Subsystems checkpoint', select={})['candidates']
        detailed = self.library.search('Subsystems checkpoint', select={'match_details': True, 'snippet': True})['candidates']
        self.assertEqual([r['physical_page'] for r in compact], [r['physical_page'] for r in detailed])
        self.assertNotIn('match_details', compact[0])
        self.assertEqual(detailed[0]['match_details'], dict(matched_fields=['body', 'bookmark_ancestors'],
                         body_matches_all_terms=False, metadata_excerpt='Subsystems', metadata_excerpt_derived=True))
        self.assertNotIn('Subsystems', detailed[0]['snippet'])
        text = self.library.search('checkpoint', search_mode='text', select={'match_details': True})['candidates'][0]
        self.assertEqual(text['match_details'], dict(matched_fields=['body'], body_matches_all_terms=True))
        with self.library.db() as db:
            db.execute('INSERT INTO entries VALUES(?,?,?,?,?)',
                       (self.identifier, 1, 'Heuristic', '["Fabricated"]', 'heading_candidate'))
        self.library.setup()
        self.assertEqual(self.library.search('Fabricated checkpoint')['candidates'], [])
        self.assertEqual(len(self.library.search('Heuristic checkpoint')['candidates']), 1)

    def test_bookmark_only_empty_snippet_and_exact_locate(self):
        with self.library.db() as db:
            db.execute('UPDATE pages SET text=""')
            db.execute('UPDATE page_fts SET text=""')
        self.library.setup()
        result = self.library.search('Infiltration', select={'snippet': True, 'match_details': True})['candidates'][0]
        self.assertEqual(result['snippet'], '')
        self.assertIn('sparse_text_no_ocr', result['warnings'])
        self.assertFalse(result['match_details']['body_matches_all_terms'])
        for mode in ('text', 'contextual'):
            result = self.library.search('  INFILTRATION  ', locate=True, search_mode=mode)['candidates'][0]
            self.assertTrue(result['exact_heading_candidate'])

    def test_locate_selection_does_not_change_exact_promotion(self):
        full = self.library.search('Infiltration', locate=True)['candidates']
        compact = self.library.search('Infiltration', locate=True, select={})['candidates']
        self.assertEqual([r['physical_page'] for r in full], [r['physical_page'] for r in compact])
        self.assertNotIn('entries', compact[0])

    def test_query_bounds_unicode_and_operators(self):
        for query in ('', '!!!', 'x'*301, ' '.join(['x']*31)):
            with self.assertRaises(LibraryError): self.library.search(query)
        for query in ('"checkpoint"', 'checkpoint OR absent', 'checkpoint_approach', 'chéckpoint'):
            for mode in ('text', 'contextual'):
                self.library.search(query, search_mode=mode)
        self.assertEqual(len(self.library.search('chéckpoint')['candidates']), 1)
        with self.assertRaises(LibraryError): self.library.search('checkpoint', search_mode='semantic')
        with self.assertRaises(LibraryError): self.library.search('checkpoint', 'c'*32)

    def test_pagination_budgets_and_ties(self):
        with self.library.db() as db:
            for n in range(2, 13):
                db.execute('INSERT INTO pages SELECT document_id,?,label,text,warnings FROM pages WHERE page=1', (n,))
                db.execute('INSERT INTO page_fts SELECT document_id,?,text FROM page_fts WHERE page=1', (n,))
                db.execute('INSERT INTO entries SELECT document_id,?,title,context,provenance FROM entries WHERE page=1', (n,))
        self.library.setup()
        for mode in ('text', 'contextual'):
            ids, offset = [], 0
            while offset is not None:
                result = self.library.search('checkpoint', offset=offset, limit=3, select={}, search_mode=mode)
                ids.extend(r['physical_page'] for r in result['candidates'])
                offset = result['next_offset']
            self.assertEqual(ids, list(range(1, 13)))
            limited = self.library.search('checkpoint', select={}, max_bytes=1024, search_mode=mode)
            self.assertLess(len(limited['candidates']), 10)
            self.assertEqual(limited['next_offset'], len(limited['candidates']))
            with self.assertRaisesRegex(LibraryError, 'ResponseTooLarge'):
                self.library.search('checkpoint', select={}, max_bytes=1, search_mode=mode)

    def test_migration_restart_fingerprint_and_exact_page_keys(self):
        before = self.library.read(self.identifier, 1)
        with self.library.db() as db:
            db.execute('DROP TABLE page_context_fts')
            db.execute('DROP TABLE pdf_context_index_state')
        with patch.object(self.library, 'index', side_effect=AssertionError('must not parse')):
            self.library.setup()
        self.assertEqual(before, self.library.read(self.identifier, 1))
        with patch.object(search_context, 'write_context', side_effect=AssertionError('unchanged')):
            self.library.setup()
        # Matching row counts cannot establish matching page coverage.
        with self.library.db() as db:
            db.execute('UPDATE page_context_fts SET page=99')
        self.library.setup()
        self.assertEqual(len(self.library.search('Infiltration checkpoint')['candidates']), 1)
        with self.library.db() as db:
            db.execute('UPDATE entries SET title="Stealth"')
        self.library.setup()
        self.assertEqual(self.library.search('Infiltration checkpoint')['candidates'], [])
        self.assertEqual(len(self.library.search('Stealth checkpoint')['candidates']), 1)
        with self.library.db() as db:
            db.execute('INSERT INTO page_context_fts SELECT * FROM page_context_fts')
            db.execute('INSERT INTO page_context_fts VALUES(?,?,?,?,?,?,?)', ('orphan',1,'secret','','','','[]'))
            db.execute('INSERT INTO pdf_context_index_state VALUES(?,?,?,?,?)', ('orphan','r',1,'x',1))
        self.library.setup()
        with self.library.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM page_context_fts').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT count(*) FROM pdf_context_index_state').fetchone()[0], 1)

    def test_failed_migration_rolls_back_and_preserves_sources(self):
        before = self.library.read(self.identifier, 1)
        with self.library.db() as db:
            db.execute('UPDATE pdf_context_index_state SET build_version=0')
        original = search_context.write_context
        def interrupted(*args):
            original(*args)
            raise OSError('private extracted text must not escape')
        with patch.object(search_context, 'write_context', side_effect=interrupted):
            with self.assertRaisesRegex(LibraryError, '^Contextual PDF index upgrade failed;') as error:
                self.library.setup()
        self.assertNotIn('private extracted', str(error.exception))
        with self.library.db() as db:
            self.assertEqual(db.execute('SELECT build_version FROM pdf_context_index_state').fetchone()[0], 0)
        self.assertEqual(self.library.read(self.identifier, 1), before)
        tiny = Library(replace(self.library.config, quota=1))
        with self.assertRaises(LibraryError): tiny.setup()
        self.assertEqual(self.library.status(self.identifier)['status'], 'ready')
        self.library.setup()
        self.assertEqual(self.library.read(self.identifier, 1), before)
        with self.library.db() as db:
            db.execute('UPDATE entries SET context="malformed"')
        with self.assertRaises(LibraryError): self.library.setup()
        self.assertEqual(self.library.read(self.identifier, 1), before)

    def test_page_and_book_boundaries_and_truncation_warning(self):
        with self.library.db() as db:
            db.execute('INSERT INTO pages VALUES(?,?,?,?,?)', (self.identifier,2,'2','Different prose','[]'))
            db.execute('INSERT INTO entries VALUES(?,?,?,?,?)', (self.identifier,2,'Elsewhere','[]','bookmark'))
            db.execute('INSERT INTO entries VALUES(?,?,?,?,?)', (self.identifier,1,'é'*5000,'[]','bookmark'))
            db.execute('INSERT INTO documents SELECT ?,name,sha256,size_bytes,status,revision,page_count,error FROM documents', ('c'*32,))
            db.execute('INSERT INTO pages VALUES(?,?,?,?,?)', ('c'*32,1,'1','Only other volume','[]'))
            db.execute('INSERT INTO entries VALUES(?,?,?,?,?)', ('c'*32,1,'DifferentBook','[]','bookmark'))
        self.library.setup()
        for query in ('Elsewhere checkpoint','DifferentBook checkpoint','Infiltration Different'):
            self.assertEqual(self.library.search(query)['candidates'], [])
        candidate = self.library.search('Infiltration checkpoint')['candidates'][0]
        self.assertIn('search_context_truncated', candidate['warnings'])

    def test_lexical_cap_does_not_drop_exact_bookmark(self):
        with self.library.db() as db:
            for n in range(2, 2002):
                db.execute('INSERT INTO pages VALUES(?,?,?,?,?)', (self.identifier,n,str(n),'checkpoint','[]'))
                db.execute('INSERT INTO page_fts VALUES(?,?,?)', (self.identifier,n,'checkpoint'))
            db.execute('INSERT INTO pages VALUES(?,?,?,?,?)', (self.identifier,2002,'2002','','["sparse_text_no_ocr"]'))
            db.execute('INSERT INTO page_fts VALUES(?,?,?)', (self.identifier,2002,''))
            db.execute('INSERT INTO entries VALUES(?,?,?,?,?)', (self.identifier,2002,'checkpoint','[]','bookmark'))
        self.library.setup()
        for mode in ('text','contextual'):
            result = self.library.search('checkpoint', locate=True, search_mode=mode)
            self.assertTrue(result['candidate_cap_reached'])
            self.assertEqual(result['candidates'][0]['physical_page'],2002)


class ProjectionTests(unittest.TestCase):
    def test_provenance_deduplication_order_bounds_and_fingerprint(self):
        pages = [dict(page=1, text=' Canonical\n body '), dict(page=2, text='')]
        entries = [dict(page=1, title=' Alpha ', context=['Parent'], provenance='bookmark'),
                   dict(page=1, title='alpha', context=['False ancestry'], provenance='heading_candidate'),
                   dict(page=1, title='é'*5000, context=[], provenance='bookmark')]
        rows, fingerprint = search_context.project(pages, entries)
        self.assertEqual(search_context.project(pages[::-1], entries[::-1]), (rows, fingerprint))
        self.assertEqual(rows[0][1:5], ('Canonical body', 'Alpha', 'Parent', ''))
        self.assertEqual(json.loads(rows[0][-1]), ['search_context_truncated'])
        self.assertEqual(rows[1][1:5], ('', '', '', ''))
        self.assertNotEqual(search_context.project(pages, entries[:1])[1], fingerprint)
        for context in (None, {}, [1], 'invalid json'):
            with self.assertRaises((ValueError, TypeError)):
                search_context.project(pages, [dict(page=1, title='x', context=context, provenance='bookmark')])
