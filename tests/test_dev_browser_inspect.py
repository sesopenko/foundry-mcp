"""Offline scope and redaction checks for dedicated development UI inspection."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/dev-browser-inspect.py"
SPEC = importlib.util.spec_from_file_location("dev_browser_inspect_under_test", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DevelopmentBrowserInspectTests(unittest.IsolatedAsyncioTestCase):
    def harness(self, tabs=None, port="9229", result=None):
        files = []

        def read_file(path, *args, **kwargs):
            files.append(path)
            if path != SCRIPT.parent.parent / ".browser-dev/chrome-profile/DevToolsActivePort":
                raise AssertionError("Inspection must not access credentials or another profile")
            return port + "\n/devtools/browser/dedicated\n"

        response = MagicMock()
        response.json.return_value = tabs if tabs is not None else [{
            "type": "page", "url": "http://localhost:30000/join",
            "webSocketDebuggerUrl": "ws://127.0.0.1:9229/devtools/page/dedicated",
        }]
        http = MagicMock()
        http.get = AsyncMock(return_value=response)
        http_context = MagicMock()
        http_context.__aenter__ = AsyncMock(return_value=http)
        http_context.__aexit__ = AsyncMock(return_value=False)
        client = MagicMock(return_value=http_context)
        summary = result if result is not None else {
            "path": "/join", "world": "test", "login_status": {
                "password_message": True, "password_required": True,
            }, "inputs": [{"tag": "INPUT", "id": "join-password", "type": "password"}],
            "buttons": [], "packages": [],
        }
        socket = MagicMock()
        socket.send = AsyncMock()
        socket.recv = AsyncMock(side_effect=[
            json.dumps({"id": 2}),
            json.dumps({"id": 1, "result": {"result": {"value": json.dumps(summary)}}}),
        ])
        socket_context = MagicMock()
        socket_context.__aenter__ = AsyncMock(return_value=socket)
        socket_context.__aexit__ = AsyncMock(return_value=False)
        connect = MagicMock(return_value=socket_context)
        return SimpleNamespace(files=files, read_file=read_file, http=http, client=client,
                               socket=socket, connect=connect)

    async def run_helper(self, harness):
        output = io.StringIO()
        with patch.object(MODULE.Path, "read_text", autospec=True, side_effect=harness.read_file), \
             patch.object(MODULE.httpx, "AsyncClient", harness.client), \
             patch.object(MODULE.websockets, "connect", harness.connect), \
             contextlib.redirect_stdout(output):
            result = await MODULE.main()
        return result, output.getvalue()

    async def test_success_reads_only_dedicated_profile_and_reports_console_categories_without_values(self):
        harness = self.harness()
        secret = "DUMMY-secret-never-print"
        events = [{"method": "Runtime.consoleAPICalled", "params": {"args": [
            {"value": "Password rejected: " + secret},
            {"value": "User already logged in: " + secret},
            {"value": "Invalid user selection: " + secret},
            {"value": {"credential": secret}},
        ]}}, {"id": 2}, {"id": 1, "result": {"result": {"value": json.dumps({
            "path": "/join", "world": "test", "inputs": [], "buttons": [],
            "packages": [], "login_status": {"password_message": True},
        })}}}]
        harness.socket.recv.side_effect = [json.dumps(event) for event in events]
        result, output = await self.run_helper(harness)
        self.assertEqual(result, 0)
        self.assertEqual(harness.files, [SCRIPT.parent.parent / ".browser-dev/chrome-profile/DevToolsActivePort"])
        harness.client.assert_called_once_with(trust_env=False)
        harness.http.get.assert_awaited_once_with("http://127.0.0.1:9229/json/list")
        harness.connect.assert_called_once_with("ws://127.0.0.1:9229/devtools/page/dedicated")
        requests = [json.loads(call.args[0]) for call in harness.socket.send.call_args_list]
        self.assertEqual([request["method"] for request in requests], ["Runtime.enable", "Runtime.evaluate"])
        expression = requests[1]["params"]["expression"]
        self.assertIn("e.type", expression)
        self.assertIn("o.value", expression)  # Select option IDs, never input values.
        for prohibited in ["e.value", "password.value", "document.cookie", "localStorage",
                           "sessionStorage", "requestSubmit", ".click(", "createWorld", "resetWorld"]:
            self.assertNotIn(prohibited, expression)
        self.assertEqual(json.loads(output)["login_console_categories"],
                         ["already_active", "password", "user_selection"])
        self.assertNotIn(secret, output)
        self.assertNotIn("credential", output)

    async def test_foreign_ordinary_ambiguous_and_wrong_debugger_endpoints_never_open_socket(self):
        valid = {"type": "page", "url": "http://localhost:30000/join",
                 "webSocketDebuggerUrl": "ws://127.0.0.1:9229/devtools/page/dedicated"}
        cases = [[], [{**valid, "url": "https://ordinary.example/join"}], [valid, valid]]
        for endpoint in ["ws://foreign.example:9229/devtools/page/other",
                         "ws://127.0.0.1:9230/devtools/page/other",
                         "ws://127.0.0.1:9229/devtools/browser/other",
                         "ws://user:pass@127.0.0.1:9229/devtools/page/other",
                         "ws://127.0.0.1:9229/devtools/page/other?secret=yes"]:
            cases.append([{**valid, "webSocketDebuggerUrl": endpoint}])
        for tabs in cases:
            with self.subTest(tabs=tabs):
                harness = self.harness(tabs=tabs)
                result, output = await self.run_helper(harness)
                self.assertEqual(result, 1)
                self.assertEqual(len(harness.files), 1)
                harness.connect.assert_not_called()
                harness.socket.send.assert_not_awaited()
                self.assertEqual(set(json.loads(output)), {"passed", "exception_type"})

    async def test_invalid_profile_port_rejects_before_any_endpoint_or_credential_access(self):
        for port in ["", "invalid", "0", "65536"]:
            with self.subTest(port=port):
                harness = self.harness(port=port)
                result, output = await self.run_helper(harness)
                self.assertEqual(result, 1)
                self.assertEqual(len(harness.files), 1)
                harness.client.assert_not_called()
                harness.connect.assert_not_called()
                self.assertEqual(json.loads(output), {"passed": False, "exception_type": "RuntimeError"})

    async def test_cdp_and_transport_errors_report_only_sanitized_exception_types(self):
        secret = "DUMMY-private-browser-error"
        for reply in [{"id": 1, "error": {"message": secret}},
                      {"id": 1, "result": {"exceptionDetails": {"text": secret}}}]:
            harness = self.harness()
            harness.socket.recv.side_effect = [json.dumps({"id": 2}), json.dumps(reply)]
            result, output = await self.run_helper(harness)
            self.assertEqual(result, 1)
            self.assertEqual(json.loads(output), {"passed": False, "exception_type": "RuntimeError"})
            self.assertNotIn(secret, output)
        harness = self.harness()
        harness.connect.side_effect = RuntimeError(secret)
        result, output = await self.run_helper(harness)
        self.assertEqual(result, 1)
        self.assertEqual(json.loads(output), {"passed": False, "exception_type": "RuntimeError"})
        self.assertNotIn(secret, output)


if __name__ == "__main__":
    unittest.main()
