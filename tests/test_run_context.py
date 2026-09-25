"""Offline regression tests for per-query run state and diagnostics."""
import json
import tempfile
import unittest
from pathlib import Path

from zotify.run_context import RunContext


class RunContextTests(unittest.TestCase):
    def test_session_replacement_is_scoped_and_recorded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original = object()
            replacement = object()
            context = RunContext("run-1", original, object(), temp_dir)

            context.replace_session(replacement)

            self.assertIs(context.session, replacement)
            self.assertEqual(context.session_generation, 1)
            event = json.loads(Path(context.events_path).read_text().splitlines()[0])
            self.assertEqual(event["run_id"], "run-1")
            self.assertEqual(event["event"], "session_renewed")
            self.assertEqual(event["generation"], 1)

    def test_events_append_without_leaking_other_runs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            context = RunContext("run-2", object(), object(), temp_dir)
            context.record("transfer_retry", uri="spotify:track:one", attempt=1)
            context.record("track_interrupted", uri="spotify:track:two")

            events = [json.loads(line) for line in Path(context.events_path).read_text().splitlines()]
            self.assertEqual([event["event"] for event in events], ["transfer_retry", "track_interrupted"])
            self.assertTrue(all(event["run_id"] == "run-2" for event in events))


if __name__ == "__main__":
    unittest.main()
