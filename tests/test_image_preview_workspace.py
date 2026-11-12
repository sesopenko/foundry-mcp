"""Scratch lifetime and environment policy without child lifecycle mocks."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from foundry_mcp_server.image_preview_workspace import PreviewWorkspace


class WorkspaceTests(unittest.TestCase):
    def test_private_workspace_removes_only_owned_files_on_exception(self):
        with tempfile.TemporaryDirectory() as directory:
            original=Path(directory)/'original'
            original.write_bytes(b'unchanged')
            with self.assertRaises(ValueError):
                with PreviewWorkspace() as workspace:
                    scratch=workspace.path
                    self.assertEqual(scratch.stat().st_mode & 0o777,0o700)
                    (scratch/'partial').write_bytes(b'partial')
                    (scratch/'foreign').symlink_to(original)
                    raise ValueError('operation failed')
            self.assertFalse(scratch.exists())
            self.assertEqual(original.read_bytes(),b'unchanged')

    def test_environment_points_to_owned_scratch_and_excludes_credentials(self):
        with patch.dict(os.environ,{'FOUNDRY_MCP_TOKEN':'secret','AUTH0_SECRET':'secret','AWS_SECRET_ACCESS_KEY':'secret','LANG':'C.UTF-8'}):
            with PreviewWorkspace() as workspace:
                environment=workspace.environment()
                for key in ('TMPDIR','VIPS_TMPDIR','XDG_CACHE_HOME'):
                    self.assertEqual(environment[key],str(workspace.path))
                self.assertFalse(any(key.startswith(('FOUNDRY_MCP_','AUTH0_','AWS_')) for key in environment))
                self.assertEqual(environment['LANG'],'C.UTF-8')
                self.assertEqual(environment['VIPS_CONCURRENCY'],'2')
                self.assertEqual(environment['VIPS_DISC_THRESHOLD'],str(16*1024*1024))

    def test_cleanup_failure_is_visible_to_owner(self):
        with PreviewWorkspace() as workspace:
            with patch.object(workspace._directory,'__exit__',side_effect=PermissionError('denied')):
                with self.assertRaises(PermissionError):workspace.__exit__(None,None,None)
