"""Long-run state persistence probes, not narrative-quality certification."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_opening
import commit_turn
import fill_opening
import live_slice
import manage_saves
import roll_opening


class LongRuntimeTests(unittest.TestCase):
    def test_three_hundred_turns_daily_pressure_and_legacy(self):
        pools, tables = roll_opening.load_pools(), fill_opening.load_tables()
        framework = next(iter(pools["世界框架"]))
        for mode, selection in (("daily", framework), ("pressure", framework), ("pressure", "legacy")):
            with self.subTest(mode=mode, framework=selection), tempfile.TemporaryDirectory() as directory:
                drawn = roll_opening.build_roll(pools, 11, recent={}, opening_mode=mode, framework=selection)
                state = fill_opening.fill_opening(build_opening.build_skeleton(drawn), drawn, tables)
                initial_ids = {event["id"] for event in state["events"]}
                root = Path(directory)
                store = manage_saves.SaveStore(root)
                source = root / "working.yaml"
                for step in range(1, 301):
                    patch = {"delta_minutes": 1, "last_committed_result": f"Recorded action {step}",
                             "unresolved_action": "The player may continue or leave."}
                    if mode == "pressure" and step % 20 == 0:
                        pending = [e["id"] for e in state["events"] if e["status"] == "pending"]
                        if pending:
                            patch.update(events_resolve=[pending[0]], resolve_outcome=f"Completed action {step}")
                        patch["events_add"] = [{"kind": "near", "semantic_key": f"long-probe-{step}",
                                                "trigger": "An explicitly requested followup", "consequence": "A later reply"}]
                    state = commit_turn.commit(state, patch)
                    self.assertEqual(step + 1, state["meta"]["turn"])
                    self.assertTrue(initial_ids <= {e["id"] for e in state["events"]})
                    if mode == "daily":
                        self.assertEqual([], state["events"])
                        self.assertFalse(state["world"]["pressure_seeds"]["immediate"])
                    if step % 100 == 0:
                        manage_saves.write_atomic(source, manage_saves.yaml_text(state))
                        if step == 100:
                            manifest = store.init_slot("long-run", source)
                        else:
                            manifest = store.save_slot("long-run", source, expected_updated_at=manifest["updated_at"])
                        loaded, loaded_manifest = store.load_slot("long-run")
                        self.assertEqual(state, loaded)
                        self.assertEqual(manifest, loaded_manifest)
                sliced = live_slice.extract_live_slice(state)
                self.assertLessEqual(sum("id" in e for e in sliced["pending_events"]), live_slice.PENDING_EVENTS_LIMIT)
                for event_id in initial_ids:
                    self.assertEqual(event_id, live_slice.event_receipts(state, [event_id])[0]["id"])


if __name__ == "__main__":
    unittest.main()
