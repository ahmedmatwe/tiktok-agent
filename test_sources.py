import importlib.util
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import sources
import state


class MultiSourceTests(unittest.TestCase):
    def test_normalization_and_sec_uid_isolation(self):
        with patch.dict(os.environ, {"TIKTOK_USERNAME": "@One", "TIKTOK_USERNAMES": "@One, TWO one", "TIKTOK_SEC_UID": "primary-id"}, clear=True):
            self.assertEqual(sources.accounts(), [("one", "primary-id", True), ("two", None, False)])

    def test_invalid_input(self):
        with patch.dict(os.environ, {"TIKTOK_USERNAMES": "https://tiktok.com/@one"}, clear=True):
            with self.assertRaises(ValueError):
                sources.accounts()

    def load_agent(self):
        tiktok = types.ModuleType("tiktok")
        captioner = types.ModuleType("captioner")
        dotenv = types.ModuleType("dotenv")
        dotenv.load_dotenv = lambda *a: None
        pubs = types.ModuleType("publishers")
        for name in ("youtube", "instagram"):
            setattr(pubs, name, types.SimpleNamespace())
        with patch.dict(sys.modules, {"tiktok": tiktok, "captioner": captioner, "dotenv": dotenv, "publishers": pubs}):
            spec = importlib.util.spec_from_file_location("agent_under_test", "agent.py")
            agent = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(agent)
        return agent

    def test_existing_account_migration_and_new_account_baseline(self):
        agent = self.load_agent()
        with tempfile.TemporaryDirectory() as tmp, patch.object(state, "STATE_FILE", tmp + "/state.json"), patch.dict(os.environ, {"TIKTOK_USERNAME": "one", "TIKTOK_USERNAMES": "one,two", "BACKFILL": "false"}, clear=True):
            state.mark("__initialized__", "done", True)
            video = lambda id: types.SimpleNamespace(id=id)
            agent.tiktok.latest_videos = lambda username, *a, **kw: [video(username + "-video")]
            processed = []
            agent.process = lambda v, cookies, targets=None: processed.append(v.id)
            agent.check_once()
            self.assertEqual(processed, ["one-video"])
            self.assertTrue(state.done("two-video", "_skipped_on_first_run"))
            self.assertTrue(state.known("__initialized__:two"))
            processed.clear()
            agent.tiktok.latest_videos = lambda username, *a, **kw: [video(username + "-new"), video(username + "-video")]
            agent.check_once()
            self.assertIn("two-new", processed)
            self.assertNotIn("two-video", processed)

    def test_one_broken_account_does_not_block_others(self):
        agent = self.load_agent()
        with tempfile.TemporaryDirectory() as tmp, patch.object(state, "STATE_FILE", tmp + "/state.json"), patch.dict(os.environ, {"TIKTOK_USERNAME": "one", "TIKTOK_USERNAMES": "one,two", "BACKFILL": "true"}, clear=True):
            def latest(username, *a, **kw):
                if username == "one":
                    raise RuntimeError("source unavailable")
                return [types.SimpleNamespace(id="two-new")]
            agent.tiktok.latest_videos = latest
            processed = []
            agent.process = lambda v, cookies, targets=None: processed.append(v.id)
            with self.assertRaises(RuntimeError):
                agent.check_once()
            self.assertEqual(processed, ["two-new"])

    def test_publish_failure_preserves_success_and_fails_run(self):
        agent = self.load_agent()
        with tempfile.TemporaryDirectory() as tmp, patch.object(state, "STATE_FILE", tmp + "/state.json"):
            state.mark("test", "_meta", {"youtube_title": "test"})
            agent.tiktok.download = lambda *a: None
            def fail(*args):
                raise RuntimeError("publisher unavailable")
            publishers = {"youtube": types.SimpleNamespace(publish=lambda *a: "yt-link"), "instagram": types.SimpleNamespace(publish=fail)}
            agent.enabled_publishers = lambda: publishers
            with self.assertRaises(RuntimeError):
                agent.process(types.SimpleNamespace(id="test", path="unused"), None)
            self.assertTrue(state.done("test", "youtube"))
            self.assertFalse(state.done("test", "instagram"))


if __name__ == "__main__":
    unittest.main()
