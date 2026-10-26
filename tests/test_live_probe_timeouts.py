"""Offline timeout behavior for the pinned FastMCP probe client, without HTTP."""
import asyncio
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from fastmcp import Client, FastMCP
from fastmcp.server.middleware import Middleware
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (
    'actor-current-probe.py',
    'actor-state-live-check.py',
    'actor-casting-current-live-check.py',
)


def probe(name):
    spec = importlib.util.spec_from_file_location(
        name.replace('-', '_'), ROOT / 'scripts' / name,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProbeTimeoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_scripts_configure_request_initialization_and_session_budgets(self):
        class StopProbe(Exception):
            pass

        class StopClient:
            async def __aenter__(self):
                raise StopProbe()

            async def __aexit__(self, *args):
                pass

        original_timeout = asyncio.timeout
        for name in SCRIPTS:
            module = probe(name)
            transport = object()
            with self.subTest(script=name):
                self.assertEqual(
                    (module.REQUEST_TIMEOUT_SECONDS, module.INIT_TIMEOUT_SECONDS,
                     module.SESSION_TIMEOUT_SECONDS),
                    (30, 10, 180),
                )
                with (
                    patch.object(module, 'Client', return_value=StopClient()) as client,
                    patch.object(module, 'StreamableHttpTransport', return_value=transport),
                    patch.object(Path, 'read_text', return_value='FOUNDRY_MCP_CALLER_TOKEN=offline-placeholder'),
                    patch.object(module.asyncio, 'timeout', wraps=original_timeout) as deadline,
                    redirect_stdout(io.StringIO()),
                ):
                    try:
                        await module.main()
                    except StopProbe:
                        pass
                    client.assert_called_once_with(transport, timeout=30, init_timeout=10)
                    deadline.assert_called_once_with(180)

    async def test_timeout_failures_are_sanitized_in_each_script(self):
        initialization = RuntimeError('Client failed to connect: Failed to initialize server session')
        initialization.__cause__ = RuntimeError('SECRET transport details')
        cases = (
            (TimeoutError('SECRET transport details'), 'probe_session_timeout'),
            (McpError(ErrorData(code=408, message='SECRET transport details')), 'probe_request_timeout'),
            (initialization, 'probe_initialization_timeout'),
        )
        for name in SCRIPTS:
            module = probe(name)
            for error, expected in cases:
                class FailedClient:
                    async def __aenter__(self):
                        raise error

                    async def __aexit__(self, *args):
                        pass

                output = io.StringIO()
                with (
                    self.subTest(script=name, failure=expected),
                    patch.object(module, 'Client', return_value=FailedClient()),
                    patch.object(module, 'StreamableHttpTransport', return_value=object()),
                    patch.object(Path, 'read_text', return_value='FOUNDRY_MCP_CALLER_TOKEN=offline-placeholder'),
                    redirect_stdout(output),
                ):
                    self.assertEqual(await module.main(), 1)
                    summary = json.loads(output.getvalue())
                    self.assertFalse(summary['passed'])
                    self.assertEqual(summary['failure_kind'], expected)
                    self.assertNotIn('SECRET', output.getvalue())
                    self.assertNotIn('offline-placeholder', output.getvalue())

    async def test_unrelated_initialization_errors_are_not_classified_as_timeouts(self):
        for name in SCRIPTS:
            module = probe(name)
            for message in (
                'Authentication failed',
                'Other failure: Failed to initialize server session',
                'Failed to initialize server session: unsupported protocol',
            ):
                with self.subTest(script=name, message=message):
                    self.assertIsNone(module.timeout_failure(RuntimeError(message)))

    async def test_request_timeout_reaches_never_responding_in_memory_tool(self):
        server = FastMCP('offline-request-timeout')
        entered = asyncio.Event()

        @server.tool
        async def never_responds() -> str:
            entered.set()
            await asyncio.Event().wait()
            return 'unreachable'

        # A separate outer guard makes a broken timeout fail the test promptly.
        async with asyncio.timeout(2):
            async with Client(server, timeout=0.1, init_timeout=0.5) as client:
                with self.assertRaises(McpError) as caught:
                    await client.call_tool('never_responds', {})
                self.assertTrue(entered.is_set())
                self.assertEqual(caught.exception.error.code, 408)
                self.assertEqual(
                    [tool.name for tool in await client.list_tools()], ['never_responds'],
                )

    async def test_initialization_timeout_is_distinct_from_tool_request(self):
        entered = asyncio.Event()

        class StalledInitialization(Middleware):
            async def on_initialize(self, context, call_next):
                entered.set()
                await asyncio.Event().wait()

        server = FastMCP('offline-init-timeout')
        server.add_middleware(StalledInitialization())
        async with asyncio.timeout(2):
            with self.assertRaises(RuntimeError) as caught:
                async with Client(server, timeout=0.5, init_timeout=0.1):
                    self.fail('Initialization unexpectedly completed')
        self.assertTrue(entered.is_set())
        self.assertEqual(
            str(caught.exception.__cause__), 'Failed to initialize server session',
        )

    async def test_session_deadline_bounds_successful_repeated_requests_and_cleanup(self):
        server = FastMCP('offline-session-timeout')
        completed = 0

        @server.tool
        async def responsive() -> str:
            await asyncio.sleep(0.01)
            return 'ok'

        async with asyncio.timeout(2):
            with self.assertRaises(TimeoutError):
                async with asyncio.timeout(0.15):
                    async with Client(server, timeout=0.5, init_timeout=0.5) as client:
                        for _ in range(100):
                            await client.call_tool('responsive', {})
                            completed += 1
        self.assertGreater(completed, 0)
        self.assertLess(completed, 100)
