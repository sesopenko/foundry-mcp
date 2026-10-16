import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('check_image_tag', Path(__file__).resolve().parent.parent / 'scripts/check-image-tag.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class ImagePublicationTests(unittest.TestCase):
    def test_existing_release_refused_missing_allowed_and_connectivity_fails_closed(self):
        for code, error, allowed in [(0, '', False), (1, 'ERROR: registry.example/image:v1: not found', True),
                                     (1, 'manifest unknown', True), (1, 'TLS handshake failed', False),
                                     (1, 'unauthorized', False)]:
            with self.subTest(error=error), patch.object(checker.subprocess, 'run', return_value=subprocess.CompletedProcess([], code, '', error)):
                if allowed:
                    checker.check('registry.example/image:v1')
                else:
                    with self.assertRaises(ValueError):
                        checker.check('registry.example/image:v1')
