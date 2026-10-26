"""Sanitized casting probe diagnostics and actual SDK call accounting."""
import importlib.util
import json
from pathlib import Path
import unittest

from fastmcp.exceptions import ToolError


SPEC = importlib.util.spec_from_file_location('casting_live_check', Path(__file__).resolve().parents[1] / 'scripts/actor-casting-current-live-check.py')
HARNESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARNESS)


class CastingLiveCheckTests(unittest.IsolatedAsyncioTestCase):
    def test_only_allowlisted_structured_tool_codes_escape(self):
        secret = 'private credential and campaign prose'
        for code in ('InvalidFoundryResponse', 'ReadFailed', 'ContentChanged'):
            error = ToolError(json.dumps({'code': code, 'message': secret, 'recovery': secret, 'selector': secret}))
            self.assertEqual(HARNESS.structured_error_code(error), code)
            self.assertNotIn(secret, json.dumps({'code': HARNESS.structured_error_code(error)}))
        for error in (ToolError(secret), ToolError(json.dumps({'code': secret})), ToolError(json.dumps({'code': {'message': secret}})), ToolError('[]'), RuntimeError(json.dumps({'code': 'ReadFailed'}))):
            self.assertIsNone(HARNESS.structured_error_code(error))

    async def test_requested_and_completed_include_failed_call_separately(self):
        progress = HARNESS.CallProgress()

        async def success(value):
            return value

        async def failure():
            raise ToolError('{"code":"ReadFailed","message":"private"}')

        self.assertEqual(await progress.call(success, 7), 7)
        self.assertEqual((progress.requested, progress.completed), (1, 1))
        with self.assertRaises(ToolError):
            await progress.call(failure)
        self.assertEqual((progress.requested, progress.completed), (2, 1))

    async def test_oversize_restarts_section_without_old_rows_cursor_or_revision(self):
        calls, progress = [], HARNESS.CallProgress()

        async def request(budget, cursor, ordinal):
            calls.append((budget, cursor, ordinal))
            if budget == 8000:
                if cursor:
                    raise ToolError('{"code":"ResponseTooLarge"}')
                return {'revision': 'old', 'records': ['discarded'], 'pagination': {'next_cursor': 'old-cursor'}}
            return {'revision': 'new', 'records': ['retained'], 'pagination': {'next_cursor': None}}

        async def counted(*args):
            return await progress.call(request, *args)

        rows, pages, restarts, discarded = await HARNESS.bounded_pages(counted, lambda page: None)
        self.assertEqual((rows, pages, restarts, discarded), (['retained'], 1, 1, 1))
        self.assertEqual(calls, [(8000, None, 1), (8000, 'old-cursor', 2), (48000, None, 1)])
        self.assertEqual((progress.requested, progress.completed), (3, 2))

    async def test_large_budget_failure_and_unrelated_error_are_not_retried(self):
        for code, expected in [('ResponseTooLarge', 2), ('ReadFailed', 1)]:
            calls = []
            error = ToolError(json.dumps({'code': code, 'message': 'private'}))

            async def request(budget, cursor, ordinal):
                calls.append(budget)
                raise error

            with self.assertRaises(ToolError) as caught:
                await HARNESS.bounded_pages(request, lambda page: None)
            self.assertIs(caught.exception, error)
            self.assertEqual(len(calls), expected)

    async def test_actual_utf8_budget_and_revision_checks_remain_strict(self):
        async def oversize(budget, cursor, ordinal):
            return {'revision': 'one', 'records': ['😀' * 2100], 'pagination': {'next_cursor': None}}

        with self.assertRaises(AssertionError):
            await HARNESS.bounded_pages(oversize, lambda page: None)

        async def unstable(budget, cursor, ordinal):
            return {'revision': str(ordinal), 'records': [], 'pagination': {'next_cursor': 'next' if ordinal == 1 else None}}

        with self.assertRaises(AssertionError):
            await HARNESS.bounded_pages(unstable, lambda page: None)
