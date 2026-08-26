from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


def load(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILD = load("build_opening", "scripts/build_opening.py")
FILL = load("fill_opening", "scripts/fill_opening.py")
SLICE = load("live_slice", "scripts/live_slice.py")


class LiveSliceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        roll = BUILD.build_roll(7, {}, {}, False, False)
        cls.state = FILL.fill_opening(BUILD.build_skeleton(roll), roll)

    def test_slice_drops_audit_candidates_and_decision_copies(self) -> None:
        slice_ = SLICE.extract_live_slice(self.state)
        blob = str(slice_)
        self.assertNotIn("naming_audit", blob)
        self.assertNotIn("candidates", blob)
        self.assertNotIn("decision_card", blob)
        self.assertNotIn("stable_core", blob)
        self.assertNotIn("sexuality_development", blob)
        npc = slice_["npcs"][0]
        self.assertIn("goal", npc)
        self.assertIn("emotion", npc)
        self.assertIn("autonomy", npc)
        self.assertIn("sexuality_baseline", npc)

    def test_opening_brief_has_player_facing_keys(self) -> None:
        suggestions = FILL.opening_suggestions(self.state)
        brief = SLICE.opening_brief(self.state, suggestions)
        self.assertTrue(brief["player"]["name"])
        self.assertTrue(brief["npc"]["name"])
        self.assertTrue(brief["unresolved"])
        self.assertEqual(3, len(brief["suggested"]))
        self.assertIn("当场的态度", brief["safety"])

    def test_human_status_has_no_field_names(self) -> None:
        text = SLICE.human_status(self.state)
        self.assertIn("地点：", text)
        self.assertNotIn("current_node", text)
        self.assertNotIn("safety_state", text)

    def test_human_presence_follows_participants_not_main_roster(self) -> None:
        state = BUILD.load_yaml_module().safe_load(BUILD.dump_yaml(self.state))
        state["npcs"][0]["location"] = "门外走廊（正离场）"
        state["current_node"]["participants"] = ["player-001"]
        state["consent"]["participants"] = ["player-001"]
        text = SLICE.human_status(state)
        player_name = str(state["player"]["name"])
        npc_name = str(state["npcs"][0]["name"])
        presence_line = next(line for line in text.splitlines() if line.startswith("在场："))
        self.assertIn(player_name, presence_line)
        self.assertNotIn(npc_name, presence_line)

    def test_grants_line_distinguishes_non_physical_scope(self) -> None:
        state = BUILD.load_yaml_module().safe_load(BUILD.dump_yaml(self.state))
        state["consent"]["grants"] = [{
            "id": "consent-009", "scene_id": state["consent"]["scene_id"],
            "participants": list(state["current_node"]["participants"]),
            "scope": [{"type": "emotional", "permission": "可以继续聊私事"}],
            "status": "granted", "granted_turn": 1, "withdrawn_turn": None,
            "last_checked_turn": 1,
        }]
        text = SLICE.human_status(state)
        self.assertIn("情感", text)
        self.assertNotIn("身体许可（", text)

    def test_pending_events_capped_with_overflow_note(self) -> None:
        state = BUILD.load_yaml_module().safe_load(BUILD.dump_yaml(self.state))
        base = dict(state["events"][0])
        for index in range(12):
            pad = dict(base)
            pad["id"] = f"evt-pad-{index:02d}"
            pad["semantic_key"] = f"pad-{index}"
            pad["status"] = "pending"
            pad["due_at"] = None
            state["events"].append(pad)
        slice_ = SLICE.extract_live_slice(state)
        pending = slice_["pending_events"]
        total = sum(1 for e in state["events"] if isinstance(e, dict) and e.get("status") == "pending")
        self.assertEqual(10, len(pending) - 1)
        self.assertEqual(11, len(pending))
        self.assertIn(f"另有 {total - 10} 条未列出", str(pending[-1]))

    def test_knowledge_keeps_latest_entries_only(self) -> None:
        state = BUILD.load_yaml_module().safe_load(BUILD.dump_yaml(self.state))
        state["npcs"][0]["knowledge"] = [f"线索{index:02d}" for index in range(12)]
        state["player"]["knowledge"] = [f"玩家线索{index:02d}" for index in range(12)]
        slice_ = SLICE.extract_live_slice(state)
        self.assertEqual([f"线索{index:02d}" for index in range(4, 12)],
                         slice_["npcs"][0]["knowledge"])
        self.assertEqual(8, len(slice_["player"]["knowledge"]))
        self.assertNotIn("玩家线索00", str(slice_["player"]))

    def test_cli_human(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.yaml"
            yaml = BUILD.load_yaml_module()
            path.write_text(yaml.safe_dump(self.state, allow_unicode=True, sort_keys=False), encoding="utf-8")
            self.assertEqual(0, SLICE.main([str(path), "--human"]))


if __name__ == "__main__":
    unittest.main()
