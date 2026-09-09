from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import hashlib
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import data_contract
import qa


class QATests(unittest.TestCase):
    def test_passing_playtests_do_not_close_pending_core_bridges(self):
        import material_registry
        import playtest_report
        import check_duplicates
        import build_frameworks
        snapshot = {"errors": [], "summary": {"core_pool_dispositions": {"BRIDGE_REQUIRED": 1}}}
        with patch.object(material_registry, "audit", return_value=snapshot), \
                patch.object(material_registry, "load_registry", return_value={}), \
                patch.object(material_registry, "units", return_value=[]), \
                patch.object(qa, "core_review_errors", return_value=[]), \
                patch.object(build_frameworks, "aggregate", return_value={"frameworks": {}, "reviewed_frameworks": {}}), \
                patch.object(check_duplicates, "audit", return_value={"unresolved_candidates": 0}), \
                patch.object(playtest_report, "audit", return_value={"errors": []}):
            self.assertEqual(["CORE_BRIDGE_GATE: 1 core materials still require semantic closure"], qa.release_errors())

    def test_unregistered_files_fail_instead_of_silent_omission(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "new.yaml").write_text("{}", encoding="ascii")
            errors = data_contract.validate_files(root, {"files": {"required.yaml": {}}})
            self.assertIn("UNREGISTERED_DATA_FILE: new.yaml", errors)
            self.assertIn("MISSING_DATA_FILE: required.yaml", errors)

    def test_closure_includes_dependencies_and_reverse_consumers(self):
        manifest = {"files": {"a": {"depends_on": []}, "b": {"depends_on": ["a"]},
                              "c": {"depends_on": ["b"]}, "unrelated": {"depends_on": []}}}
        self.assertEqual(["a", "b", "c"], data_contract.dependency_closure(["b"], manifest))
        with self.assertRaises(ValueError):
            data_contract.dependency_closure(["unknown"], manifest)

    def test_diff_includes_committed_worktree_and_untracked_paths(self):
        with patch.object(qa, "git", side_effect=[b"abc\n", b"scripts/x.py\0authoring/a.yaml\0", b"tests/new.py\0"] ) as git:
            self.assertEqual(["authoring/a.yaml", "scripts/x.py", "tests/new.py"], qa.changed_paths("origin/main"))
            self.assertEqual(("diff", "--name-only", "-z", "abc"), git.call_args_list[1].args)

    def test_authoring_selects_only_affected_framework(self):
        index = {"frameworks": [{"id": "mat-one", "name": "One"}, {"id": "mat-two", "name": "Two"}]}
        selected = qa.scope(["authoring/frameworks/mat-one.yaml"], {"files": {}}, index)
        self.assertEqual(["One"], selected["frameworks"])
        self.assertFalse(selected["full"])
        selected = qa.scope(["authoring/frameworks/deleted.yaml"], {"files": {}}, index)
        self.assertTrue(selected["full"])

    def test_shared_runtime_change_expands_to_full_regression(self):
        self.assertTrue(qa.scope(["scripts/_common.py"])["full"])

    def test_generated_companions_do_not_force_all_framework_samples(self):
        index = {"frameworks": [{"id": "mat-one", "name": "One"}]}
        paths = ["authoring/frameworks/mat-one.yaml", "scripts/data/world_frameworks.yaml",
                 "references/material_registry.yaml", "maintenance/content_fingerprint.txt"]
        selected = qa.scope(paths, {"files": {}}, index)
        self.assertFalse(selected["full"])
        self.assertEqual(["One"], selected["frameworks"])

    def test_readme_only_selects_document_contract_tests(self):
        selected = qa.scope(["README.md"])
        self.assertFalse(selected["full"])
        self.assertEqual(["tests/test_doc_consistency.py"], selected["tests"])

    def test_review_dependency_change_invalidates_unchanged_pool_label(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "maintenance").mkdir()
            (root / "maintenance/core_review_decisions.yaml").write_text("[]", encoding="ascii")
            self.assertEqual(["CORE_REVIEW_DEPENDENCIES_MISSING"], data_contract.core_review_errors(root))
            target = root / "consumer.py"
            target.write_bytes(b"old consumer")
            document = {"version": 1, "files": {"consumer.py": hashlib.sha256(target.read_bytes()).hexdigest()}}
            (root / "maintenance/core_review_dependencies.yaml").write_text(yaml.safe_dump(document), encoding="ascii")
            self.assertEqual([], data_contract.core_review_errors(root))
            target.write_bytes(b"new consumer")
            self.assertEqual(["CORE_REVIEW_DEPENDENCY_STALE: consumer.py"], data_contract.core_review_errors(root))


if __name__ == "__main__":
    unittest.main()
