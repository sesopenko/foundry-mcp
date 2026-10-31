"""Regression for PF2e chat's persisted deferred-roll HTML transformation."""
import importlib.util
from pathlib import Path
import unittest

SPEC=importlib.util.spec_from_file_location('chat_live_check',Path(__file__).resolve().parents[1]/'scripts/chat-live-check.py')
MODULE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ChatLiveCheckTests(unittest.TestCase):
    def test_persisted_link_is_valid_without_literal_roll_notation(self):
        # Public ChatMessage.content observed on14.369/PF2e8.6.1; no private
        # system method/class/attribute is required to recognize an HTML link.
        content='<p style="font-size:18px">Test <a data-formula="1"><i></i>1</a> @Check[reflex|dc:20|basic]</p>'
        MODULE.assert_stored_markup(content)
