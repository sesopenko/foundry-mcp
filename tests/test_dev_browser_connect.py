"""Offline authorization and secret-handling checks for the dev login helper."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/dev-browser-connect.py"
SPEC = importlib.util.spec_from_file_location("dev_browser_connect_under_test", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DevelopmentBrowserConnectTests(unittest.IsolatedAsyncioTestCase):
    """Use dummy credentials, fake CDP replies and no real files or network."""

    def harness(self, path="/join", tabs=None, credential=None, reply=None):
        profile_port = "9229"
        admin_key = 'DUMMY-admin-"\\\n-key'
        password = 'DUMMY-gm-";globalThis.secret=1;//\\\n🙂'
        if credential is None:
            credential = {
                "world_id": "test", "user_name": "Gamemaster", "password": password
            }
        default_tab = {
            "type": "page", "url": "http://localhost:30000" + path,
            "webSocketDebuggerUrl": "ws://127.0.0.1:9229/devtools/page/dedicated",
        }
        tabs = [default_tab] if tabs is None else tabs
        files = []

        def read_file(selected, *args, **kwargs):
            files.append(selected)
            if selected == SCRIPT.parent.parent / ".browser-dev/chrome-profile/DevToolsActivePort":
                return profile_port + "\n/devtools/browser/dedicated\n"
            if selected == SCRIPT.parent.parent / ".local/dev-login.json":
                if isinstance(credential, Exception):
                    raise credential
                return json.dumps(credential)
            raise AssertionError("Unexpected file access")

        response = MagicMock()
        response.json.return_value = tabs
        http = MagicMock()
        http.get = AsyncMock(return_value=response)
        http_context = MagicMock()
        http_context.__aenter__ = AsyncMock(return_value=http)
        http_context.__aexit__ = AsyncMock(return_value=False)
        client = MagicMock(return_value=http_context)
        if reply is None:
            action = {
                "/join": "join_existing_test_gm", "/auth": "authenticate_admin",
                "/setup": "launch_existing_test_world",
            }.get(path, "unexpected")
            reply = {"id": 1, "result": {"result": {"value": json.dumps({
                "submitted": True, "action": action
            })}}}
        socket = MagicMock()
        socket.send = AsyncMock()
        socket.recv = AsyncMock(return_value=json.dumps(reply))
        socket_context = MagicMock()
        socket_context.__aenter__ = AsyncMock(return_value=socket)
        socket_context.__aexit__ = AsyncMock(return_value=False)
        connect = MagicMock(return_value=socket_context)
        docker = MagicMock(return_value=SimpleNamespace(stdout=admin_key + "\n", stderr=""))
        return SimpleNamespace(
            files=files, read_file=read_file, http=http, client=client, socket=socket,
            connect=connect, docker=docker, admin_key=admin_key, password=password,
        )

    async def run_helper(self, harness, **kwargs):
        output = io.StringIO()
        with patch.object(MODULE.Path, "read_text", autospec=True, side_effect=harness.read_file), \
             patch.object(MODULE.httpx, "AsyncClient", harness.client), \
             patch.object(MODULE.websockets, "connect", harness.connect), \
             patch.object(MODULE.subprocess, "run", harness.docker), \
             contextlib.redirect_stdout(output):
            result = await MODULE.main(**kwargs)
        return result, output.getvalue()

    def expression(self, harness):
        request = json.loads(harness.socket.send.call_args.args[0])
        self.assertEqual(request["method"], "Runtime.evaluate")
        self.assertTrue(request["params"]["returnByValue"])
        return request["params"]["expression"]

    def assert_no_credentials_or_socket(self, harness):
        self.assertEqual(len(harness.files), 1)
        harness.docker.assert_not_called()
        harness.connect.assert_not_called()
        harness.socket.send.assert_not_awaited()

    async def test_join_uses_only_dedicated_endpoint_and_json_quoted_configured_gm_password(self):
        harness = self.harness()
        result, output = await self.run_helper(harness, join_gm=True)
        self.assertEqual(result, 0)
        harness.client.assert_called_once_with(trust_env=False)
        harness.http.get.assert_awaited_once_with("http://127.0.0.1:9229/json/list")
        harness.connect.assert_called_once_with("ws://127.0.0.1:9229/devtools/page/dedicated")
        harness.docker.assert_not_called()
        expression = self.expression(harness)
        self.assertIn("password.value=" + json.dumps(harness.password) + ";", expression)
        self.assertIn("location.origin!=='http://localhost:30000'", expression)
        self.assertIn("location.pathname!=='/join'", expression)
        self.assertIn("globalThis.game?.world?.id!=='test'", expression)
        self.assertIn("o.textContent.trim()==='Gamemaster'", expression)
        self.assertIn("password.form!==user.form", expression)
        self.assertIn("setTimeout(()=>join.click(),0)", expression)
        self.assertEqual(json.loads(output), {"submitted": True, "action": "join_existing_test_gm"})
        self.assertNotIn(harness.password, output)
        self.assertNotIn(json.dumps(harness.password), output)

    async def test_ordinary_foreign_wrong_path_and_ambiguous_tabs_fail_before_credentials(self):
        for urls in [[], ["https://example.test/join"], ["http://localhost:30000.evil.test/join"],
                     ["http://127.0.0.1:30000/join"], ["http://localhost:30000/setup"],
                     ["http://localhost:30000/join/"], ["http://localhost:30000/join#other"],
                     ["http://localhost:30000/join", "http://localhost:30000/join"]]:
            with self.subTest(urls=urls):
                tabs = [{"type": "page", "url": url, "webSocketDebuggerUrl": "ws://invalid"}
                        for url in urls]
                harness = self.harness(tabs=tabs)
                result, output = await self.run_helper(harness, join_gm=True)
                self.assertEqual(result, 1)
                self.assertEqual(json.loads(output)["stage"], "development_tab")
                self.assert_no_credentials_or_socket(harness)

    async def test_admin_key_is_read_only_after_auth_tab_and_never_printed(self):
        invalid = self.harness(path="/setup")
        result, _ = await self.run_helper(invalid, authenticate_admin=True)
        self.assertEqual(result, 1)
        self.assert_no_credentials_or_socket(invalid)
        harness = self.harness(path="/auth")
        result, output = await self.run_helper(harness, authenticate_admin=True)
        self.assertEqual(result, 0)
        harness.docker.assert_called_once_with(
            ["docker", "compose", "exec", "-T", "foundry", "printenv", "FOUNDRY_ADMIN_KEY"],
            cwd=SCRIPT.parent.parent, capture_output=True, text=True, check=True,
        )
        self.assertEqual(len(harness.files), 1)
        self.assertIn("input.value=" + json.dumps(harness.admin_key) + ";", self.expression(harness))
        self.assertNotIn(harness.admin_key, output)
        self.assertNotIn(json.dumps(harness.admin_key), output)
        self.assertEqual(json.loads(output), {"submitted": True, "action": "authenticate_admin"})

    async def test_only_existing_test_world_launch_is_possible_without_credentials(self):
        wrong = self.harness(path="/setup")
        result, _ = await self.run_helper(wrong, launch_world="campaign")
        self.assertEqual(result, 1)
        self.assertEqual(wrong.files, [])
        wrong.client.assert_not_called()
        wrong.docker.assert_not_called()
        wrong.connect.assert_not_called()
        harness = self.harness(path="/setup")
        result, output = await self.run_helper(harness, launch_world="test")
        self.assertEqual(result, 0)
        self.assertEqual(len(harness.files), 1)
        harness.docker.assert_not_called()
        expression = self.expression(harness)
        self.assertIn("location.pathname!=='/setup'", expression)
        self.assertIn("[data-package-id=\"test\"]", expression)
        self.assertIn('[data-action="worldLaunch"]', expression)
        self.assertIn("launch_existing_test_world", output)
        for prohibited in ["createWorld", "deleteWorld", "createDocuments", "deleteDocuments",
                           "resetWorld", "Actor.create", "game.world.update", "fetch("]:
            self.assertNotIn(prohibited, expression)

    async def test_missing_mismatched_or_malformed_local_gm_credentials_never_open_socket(self):
        for credential in [FileNotFoundError("DUMMY-private-path"), {},
                           {"world_id": "campaign", "user_name": "Gamemaster", "password": "SECRET"},
                           {"world_id": "test", "user_name": "Player", "password": "SECRET"},
                           {"world_id": "test", "user_name": "Gamemaster"},
                           {"world_id": "test", "user_name": "Gamemaster", "password": False},
                           {"world_id": "test", "user_name": "Gamemaster", "password": "x" * 4097}]:
            with self.subTest(credential_type=type(credential).__name__):
                harness = self.harness(credential=credential)
                result, output = await self.run_helper(harness, join_gm=True)
                self.assertEqual(result, 1)
                self.assertEqual(json.loads(output)["stage"], "local_development_credential")
                harness.connect.assert_not_called()
                harness.socket.send.assert_not_awaited()
                harness.docker.assert_not_called()
                self.assertNotIn("SECRET", output)
                self.assertNotIn("DUMMY-private-path", output)

    async def test_browser_and_transport_errors_never_echo_detailed_secret_diagnostics(self):
        secret = "DUMMY-never-print-browser-detail"
        for reply in [{"id": 1, "error": {"message": secret}},
                      {"id": 1, "result": {"exceptionDetails": {"text": secret}}}]:
            harness = self.harness(reply=reply)
            result, output = await self.run_helper(harness, join_gm=True)
            self.assertEqual(result, 1)
            self.assertEqual(json.loads(output), {
                "passed": False, "stage": "normal_login_form", "exception_type": "RuntimeError"
            })
            self.assertNotIn(secret, output)
            self.assertNotIn(harness.password, output)
        harness = self.harness()
        harness.connect.side_effect = RuntimeError(secret)
        result, output = await self.run_helper(harness, join_gm=True)
        self.assertEqual(result, 1)
        self.assertNotIn(secret, output)

    async def test_success_shaped_browser_payload_cannot_echo_captured_admin_key(self):
        harness = self.harness(path="/auth")
        harness.socket.recv.return_value = json.dumps({
            "id": 1, "result": {"result": {"value": json.dumps({
                "submitted": True, "action": "authenticate_admin", "credential": harness.admin_key
            })}}
        })
        result, output = await self.run_helper(harness, authenticate_admin=True)
        self.assertEqual(result, 1)
        self.assertNotIn(harness.admin_key, output)
        self.assertNotIn(json.dumps(harness.admin_key), output)
        self.assertNotIn("credential", json.loads(output))

    async def test_foreign_debugger_socket_is_rejected_before_credential_access(self):
        for debugger_url in [
            "ws://ordinary-browser.example/devtools/page/not-dedicated",
            "ws://127.0.0.1:9230/devtools/page/ordinary-profile",
            "ws://127.0.0.1:9229/devtools/browser/not-a-page",
        ]:
            with self.subTest(debugger_url=debugger_url):
                harness = self.harness(tabs=[{
                    "type": "page", "url": "http://localhost:30000/join",
                    "webSocketDebuggerUrl": debugger_url,
                }])
                result, _ = await self.run_helper(harness, join_gm=True)
                self.assertEqual(result, 1)
                self.assert_no_credentials_or_socket(harness)

    async def test_no_action_direct_call_rejects_before_local_credential_lookup(self):
        harness = self.harness(path="/setup")
        result, _ = await self.run_helper(harness)
        self.assertEqual(result, 1)
        self.assertNotIn(SCRIPT.parent.parent / ".local/dev-login.json", harness.files)
        harness.docker.assert_not_called()
        harness.connect.assert_not_called()
        harness.socket.send.assert_not_awaited()

    async def test_allowlisted_launch_retry_is_preserved_without_credentials(self):
        value = {"submitted": True, "action": "decline_optional_sharing", "retry_launch": True}
        harness = self.harness(path="/setup", reply={
            "id": 1, "result": {"result": {"value": json.dumps(value)}}
        })
        result, output = await self.run_helper(harness, launch_world="test")
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output), value)
        self.assertEqual(len(harness.files), 1)
        harness.docker.assert_not_called()

    async def test_browser_success_requires_matching_action_and_literal_boolean_flags(self):
        for value in [{"submitted": True, "action": "authenticate_admin"},
                      {"submitted": 1, "action": "join_existing_test_gm"},
                      {"submitted": True, "action": "join_existing_test_gm", "retry_launch": 1}]:
            harness = self.harness(reply={
                "id": 1, "result": {"result": {"value": json.dumps(value)}}
            })
            result, output = await self.run_helper(harness, join_gm=True)
            self.assertEqual(result, 1)
            self.assertEqual(json.loads(output)["exception_type"], "RuntimeError")


if __name__ == "__main__":
    unittest.main()
