"""Offline guard and budget checks for the fixed localhost acceptance runner."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import unittest
from unittest.mock import AsyncMock, patch

PATH = Path(__file__).resolve().parents[1]/'scripts'/'item-editing-live.py'
SPEC = importlib.util.spec_from_file_location('item_editing_live',PATH)
live = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(live)


class ItemFixtureTests(unittest.IsolatedAsyncioTestCase):
    def test_report_is_private_and_lists_unresolved_locations(self):
        with TemporaryDirectory() as root, patch.object(live,'ROOT',Path(root)):
            (Path(root)/'.local').mkdir()
            report=Path(live.write_report([['Room','Actor','Blade','Knife','Clue']],['Stair']))
            self.assertEqual(report.stat().st_mode & 0o777,0o600)
            self.assertIn('| Room | Actor | Blade | Knife | Clue |',report.read_text())
            self.assertIn('Stair',report.read_text())

    def test_marker_runtime_and_fixed_command(self):
        with self.assertRaises(ValueError):
            live.Check(None,'')
        for required in ('localhost:30000',"game.world.id!=='test'",'!game.user.isGM','worldSchemaVersion','0.961'):
            self.assertIn(required,live.GUARD)
        result=subprocess.run(['./scripts/actor-tools.sh','item-edit-baseline','other-world'],capture_output=True)
        self.assertEqual(result.returncode,2)

    async def test_page_budget_and_returned_cursor(self):
        check=live.Check(None,'a'*32)
        check.call=AsyncMock(side_effect=[
            {'records':[1],'pagination':{'complete':False,'next_cursor':'provided'}},
            {'records':[2],'pagination':{'complete':True,'next_cursor':None}}])
        rows,stats=await check.pages('read_item',item_uuid='Item.example')
        self.assertEqual(rows,[1,2])
        self.assertEqual(check.call.await_args.args[1]['cursor'],'provided')
        self.assertEqual(stats[0],2)

    async def test_gm_check_reserves_cleanup_on_failed_creation(self):
        check=live.Check(None,'b'*32)
        check.js=AsyncMock(side_effect=[RuntimeError('fixture'),{'remaining':0}])
        with self.assertRaisesRegex(RuntimeError,'fixture'):
            await live.gm_sheet(check)
        self.assertEqual(check.js.await_args.kwargs,{'action':'cleanup'})

    async def test_gm_proposal_uses_installed_other_weapon_tags(self):
        check=live.Check(None,'b'*32)
        check.js=AsyncMock(side_effect=lambda code,action,**kw:
                           {'solo':'Item.test'} if action=='create' else {'remaining':0} if action=='cleanup' else {})
        check.call=AsyncMock(return_value={'entries':[{'kind':'image','image':{}}]})
        check.pages=AsyncMock(return_value=([{'value':'improvised','available':True}], [1,500]))
        class Captured(Exception):
            pass
        async def first_proposal(target, changes):
            self.assertEqual(changes['other_tags']['tags'],['improvised'])
            raise Captured()
        check.edit=first_proposal
        with patch.object(live,'compare_sheet',AsyncMock(return_value=32)),self.assertRaises(Captured):
            await live.gm_sheet(check)

    async def test_chapter_failure_runs_exact_cleanup_before_report(self):
        check=live.Check(None,'c'*32)
        check.js=AsyncMock(side_effect=[{'journal':'j','scene':'Scene.s','owners':[]},{'remaining':0}])
        check.client=AsyncMock()
        check.client.list_tools.return_value=[]
        with self.assertRaises(AssertionError):
            await live.chapter(check)
        self.assertEqual(check.js.await_args.kwargs,{'action':'cleanup'})

    async def test_incomplete_or_denied_scope_cannot_be_counted_as_exhausted(self):
        check=live.Check(None,'d'*32)
        check.call=AsyncMock(return_value={'scopes':[{'status':'denied'}],'nodes':[]})
        with self.assertRaisesRegex(RuntimeError,'Incomplete'):
            await check.pages('list_actor_items',actor_uuid='Actor.test')
