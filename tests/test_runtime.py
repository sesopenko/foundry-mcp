import os
import unittest
from unittest.mock import patch

from foundry_mcp_server.config import Settings
from foundry_mcp_server import main


class RuntimeTests(unittest.TestCase):
    def test_binding_defaults_and_overrides(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual((Settings.from_env().host, Settings.from_env().port), ('127.0.0.1', 8000))
            os.environ.update(FOUNDRY_MCP_HOST='0.0.0.0', FOUNDRY_MCP_PORT='8123')
            configured = Settings.from_env()
            self.assertEqual((configured.host, configured.port), ('0.0.0.0', 8123))
            with patch.object(main, 'settings', configured), patch.object(main.uvicorn, 'run') as run:
                main.main()
            run.assert_called_once_with('foundry_mcp_server.main:app', host='0.0.0.0', port=8123,
                                        reload=False, proxy_headers=False)

    def test_invalid_bind_configuration_fails_startup(self):
        for name, values in {'FOUNDRY_MCP_HOST': ['', '  ', 'http://localhost', 'bad host', 'localhost:8000'],
                             'FOUNDRY_MCP_PORT': ['0', '-1', '65536', 'x', '1.5', '']}.items():
            for value in values:
                with self.subTest(name=name, value=value), patch.dict(os.environ, {name: value}, clear=True):
                    with self.assertRaisesRegex(ValueError, name):
                        Settings.from_env()
