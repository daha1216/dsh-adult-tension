from __future__ import annotations

from contextlib import redirect_stdout
from difflib import SequenceMatcher
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("material_quality_test", ROOT / "scripts/material_quality.py")
Q = importlib.util.module_from_spec(spec)
with patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
    spec.loader.exec_module(Q)


def framework(categories=("inspect",), pair_count=2):
    return {
        "places": {"office": {}},
        "pairs": [
            {"appellations": ["Colleague"], "position": "peer",
             "npc": {"role": f"role-{i}", "resource": "shared archive key"},
             "player": {"identity": f"identity-{i}", "resources": ["shared notebook"]},
             "relationship_reason": "They maintain the same public archive."}
            for i in range(pair_count)
        ],
        "activities": {
            f"task-{i}": {"category": category, "places": ["office"], "pairs": [0],
                          "beats": {"trigger": "A page is ready.", "objective": "Check the date.",
                                    "choice": "Compare the records.", "immediate": f"Record {i} checked.",
                                    "near": f"Shelf {i} is ready."}}
            for i, category in enumerate(categories)
        },
        "pressures": {"deadline": {}},
    }


class MaterialQualityTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        read_yaml = Q.read_yaml

        def read_fixture(path):
            self.assertEqual(self.root, path.parent, "Do not read production material")
            return read_yaml(path)

        reader = patch.object(Q, "read_yaml", side_effect=read_fixture)
        reader.start()
        self.addCleanup(reader.stop)

    def write(self, name, document):
        (self.root / name).write_text(json.dumps(document), encoding="utf-8")

    def report(self):
        return Q.quality(self.root)

    def seed_framework(self, categories=("inspect",), pair_count=2):
        data = framework(categories, pair_count)
        self.write("world_frameworks.yaml", {"frameworks": {"demo/~": data}})
        self.write("action_metadata.yaml", {
            "inspect": {"function": "check"}, "compare": {"function": "check"},
            "repair": {"function": "repair"}, "depart": {"function": "leave"},
        })
        return data

    def assert_source(self, source, expected=None):
        document = json.loads((self.root / source["file"]).read_text(encoding="utf-8"))
        for encoded in source["path"].split("/")[1:]:
            key = encoded.replace("~1", "/").replace("~0", "~")
            document = document[int(key)] if isinstance(document, list) else document[key]
        if expected is not None:
            self.assertEqual(expected, document)
        return document

    def test_exact_duplicates_preserve_legacy_keys_and_original_indices(self):
        text = "The public archive opens at nine."
        self.write("one.yaml", {"a/b~": [text, {"count": 1}, text]})
        report = self.report()
        self.assertEqual(1, report["summary"]["exact_same_list_candidates"])
        candidate, = report["same_list_candidates"]
        self.assertEqual(("one.yaml", "/a~1b~0", text, 2),
                         tuple(candidate[k] for k in ("file", "path", "value", "count")))
        self.assertEqual(["/a~1b~0/0", "/a~1b~0/2"], candidate["paths"])
        self.assertTrue(candidate["candidate_only"])
        self.assertEqual([], report["near_candidates"])
        cluster, = report["prose_clusters"]
        self.assertEqual(text, cluster["text"])
        self.assertEqual(candidate["paths"], cluster["paths"])

    def test_near_duplicates_match_original_algorithm_and_source_indices(self):
        values = ["The public archive opens at nine.", None,
                  "The public archive opens at ten.", "unrelated", "",
                  "The public archive opens at nine."]
        self.write("one.yaml", {"items": values})
        expected = [(i, j, round(SequenceMatcher(None, a, b).ratio(), 3))
                    for i, a in enumerate(values) if isinstance(a, str)
                    for j, b in enumerate(values) if j > i and isinstance(b, str)
                    and a != b and SequenceMatcher(None, a, b).ratio() >= 0.83]
        candidates = self.report()["near_candidates"]
        self.assertEqual(expected, [(int(c["a_path"].split("/")[-1]),
                                    int(c["b_path"].split("/")[-1]), c["similarity"])
                                   for c in candidates])
        self.assertTrue(candidates)
        for c in candidates:
            self.assert_source({"file": c["file"], "path": c["a_path"]}, c["a"])
            self.assert_source({"file": c["file"], "path": c["b_path"]}, c["b"])

    def test_cross_file_sentence_is_not_a_same_file_duplicate_or_deletion(self):
        text = "The public archive opens at nine."
        self.write("one.yaml", {"note": text})
        self.write("two.yaml", {"note": text})
        report = self.report()
        for key in ("same_list_candidates", "near_candidates", "prose_clusters"):
            self.assertEqual([], report[key])
        c, = report["cross_file_same_candidates"]
        self.assertEqual(["one.yaml", "two.yaml"], c["files"])
        self.assertEqual(2, c["count"])
        self.assertTrue(c["candidate_only"])
        self.assertFalse(report["review_policy"]["automatic_deletion"])
        for source in c["occurrences"]:
            self.assert_source(source, text)

    def test_large_list_scans_tail_instead_of_skipping_or_truncating(self):
        values = [chr(0x400 + i) * 4 for i in range(151)]
        values += ["The archive opens at nine.", "The archive opens at ten."]
        self.write("one.yaml", {"items": values})
        report = self.report()
        self.assertEqual(1, report["summary"]["large_lists_scanned"])
        c, = report["near_candidates"]
        self.assertEqual(("/items/151", "/items/152"), (c["a_path"], c["b_path"]))

    def test_distributions_use_metadata_and_count_source_entries(self):
        self.seed_framework(("inspect", "compare"))
        self.write("action_categories.yaml", {"inspect": ["a", "b"], "compare": ["c"]})
        self.write("pools.yaml", {"玩家化身轴": {
            "称谓": ["Colleague", "Colleague", "Visitor"], "社会位置": ["peer", "guest"]}})
        report = self.report()
        d = report["distributions"]
        self.assertEqual({"check": 3}, d["action_functions"])
        self.assertEqual({"Colleague": 2, "Visitor": 1}, d["appellations"])
        self.assertEqual({"peer": 1, "guest": 1}, d["social_positions"])
        for evidence in d["action_function_evidence"]:
            self.assert_source(evidence["function_source"], "check")
        f, = report["frameworks"]
        self.assertEqual({"check": 2}, f["action_function_distribution"])
        self.assertEqual({"Colleague": {"peer": 2}}, f["appellation_social_position_distribution"])
        self.assertEqual({"peer": 2}, f["social_position_distribution"])

    def test_three_function_shortfall_is_not_three_beat_keys_or_categories(self):
        self.seed_framework(("inspect", "compare", "repair"))
        report = self.report()
        c, = report["three_function_shortfall_candidates"]
        self.assertEqual((3, 2), (c["minimum"], c["observed"]))
        self.assertEqual("/frameworks/demo~1~0/activities", c["path"])
        for source in c["evidence"]:
            self.assert_source(source, source["category"])
            self.assert_source(source["function_source"], source["function"])
        self.assertEqual("REVIEW_REQUIRED", report["frameworks"][0]["semantic_grade"])

    def test_three_functions_do_not_grant_semantic_pass(self):
        self.seed_framework(("inspect", "repair", "depart"))
        report = self.report()
        self.assertEqual([], report["three_function_shortfall_candidates"])
        f, = report["frameworks"]
        self.assertEqual("REVIEW_REQUIRED", f["semantic_grade"])
        self.assertEqual("B", f["structural_grade"])
        self.assertEqual(3, f["pressure_combinations"])
        self.assertEqual(0, f["generic_followups"])

    def test_missing_metadata_is_explicit_incomplete_evidence(self):
        self.seed_framework(("unknown",))
        report = self.report()
        c, = report["three_function_shortfall_candidates"]
        self.assertEqual(0, c["observed"])
        self.assertEqual(1, len(c["unmapped"]))
        self.assert_source(c["unmapped"][0], "unknown")

    def test_generic_followups_and_repeated_consequences_have_paths(self):
        data = self.seed_framework(("inspect", "repair"))
        generic = "The record is filed. " + "约下次继续"
        for activity in data["activities"].values():
            activity["beats"]["near"] = generic
        data["pressures"]["deadline"] = {"far_consequence": generic}
        self.write("world_frameworks.yaml", {"frameworks": {"demo/~": data}})
        report = self.report()
        self.assertEqual(3, len(report["generic_consequence_candidates"]))
        self.assertEqual(2, report["frameworks"][0]["generic_followups"])
        self.assertEqual("C", report["frameworks"][0]["structural_grade"])
        for c in report["generic_consequence_candidates"]:
            self.assert_source(c, generic)
        c, = report["consequence_reuse_candidates"]
        for source in c["occurrences"]:
            self.assert_source(source, generic)

    def test_pair_resource_and_reason_reuse_cross_frameworks_are_traceable(self):
        first = framework(pair_count=1)
        second = framework(pair_count=1)
        second["pairs"][0]["npc"]["role"] = "different role"
        second["pairs"][0]["player"]["identity"] = "different identity"
        self.write("world_frameworks.yaml", {"frameworks": {"first": first, "second": second}})
        report = self.report()
        self.assertEqual(2, len(report["pair_resource_reuse_candidates"]))
        self.assertEqual(1, len(report["pair_relationship_reason_reuse_candidates"]))
        for key in ("pair_resource_reuse_candidates", "pair_relationship_reason_reuse_candidates"):
            for c in report[key]:
                self.assertEqual({"first", "second"}, {s["framework"] for s in c["occurrences"]})
                for source in c["occurrences"]:
                    self.assert_source(source, c["value"])
            self.assertEqual(report[key], report["frameworks"][0][key])

    def test_resource_repetition_inside_one_pair_is_not_pair_reuse(self):
        data = framework(pair_count=1)
        pair = data["pairs"][0]
        pair["player"]["resources"] = [pair["npc"]["resource"]] * 2
        self.write("world_frameworks.yaml", {"frameworks": {"demo": data}})
        self.assertEqual([], self.report()["pair_resource_reuse_candidates"])

    def test_report_and_summary_are_read_only_and_deterministic(self):
        self.seed_framework()
        self.write("one.yaml", {"items": ["The archive is open."] * 2})
        def snapshot():
            return {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.iterdir()}
        before = snapshot()
        open_file = io.open
        def read_only_open(file, mode="r", *args, **kwargs):
            self.assertFalse(any(flag in mode for flag in "wax+"), "Audit attempted a write")
            return open_file(file, mode, *args, **kwargs)
        with patch("io.open", side_effect=read_only_open):
            report = self.report()
            self.assertEqual(report, self.report())
            with patch.object(Q, "quality", return_value=report):
                with patch.object(sys, "argv", ["material_quality.py", "--summary"]):
                    output = io.StringIO()
                    with redirect_stdout(output):
                        Q.main()
                    self.assertEqual(report["summary"], json.loads(output.getvalue()))
        self.assertEqual(before, snapshot())
        for key in ("frameworks", "same_list_candidates", "near_candidates", "prose_clusters"):
            self.assertIsInstance(report[key], list)

    def test_empty_directory_is_a_valid_partial_inventory(self):
        report = self.report()
        self.assertEqual([], report["frameworks"])
        self.assertEqual(0, report["summary"]["near_candidates"])
        self.assertEqual("REVIEW_REQUIRED", report["review_policy"]["semantic_grade"])


if __name__ == "__main__":
    unittest.main()
