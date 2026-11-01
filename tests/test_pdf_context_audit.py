"""Audit selectors must not silently substitute another book in a fixed dataset."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('pdf_context_audit', Path(__file__).parents[1]/'scripts/pdf-context-audit.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AuditTests(unittest.TestCase):
    def test_player_core_two_does_not_replace_player_core(self):
        books = [dict(id='first', name='Pathfinder 2e - Player Core Remaster.pdf'),
                 dict(id='second', name='Pathfinder Player Core 2.pdf')]
        self.assertEqual(audit.baseline_books(books), {'player':'first'})
        self.assertEqual(audit.baseline_books(books[::-1]), {'player':'first'})

    def test_duplicate_editions_require_explicit_dataset(self):
        with self.assertRaisesRegex(ValueError, 'Ambiguous baseline editions'):
            audit.baseline_books([dict(id='one',name='Player Core.pdf'), dict(id='two',name='Player Core Remaster.pdf')])
