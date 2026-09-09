from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock
import uuid

from test_validate_state import valid_save


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMMON = load("_common")
BUILD = load("build_opening")
COMMIT = load("commit_turn")
LIVE = load("live_slice")
SAVES = load("manage_saves")


class RuntimeCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.saves = self.root / "saves"
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(BUILD, "DEFAULT_OUT_DIR", self.saves))
        self.stack.enter_context(mock.patch.object(COMMIT, "ROOT", self.root))
        self.stack.enter_context(mock.patch.object(LIVE, "ROOT", self.root))

    def write_state(self, path, state=None, crlf=False):
        text = COMMON.yaml_text(state if state is not None else valid_save())
        if crlf:
            text = text.replace("\n", "\r\n")
        COMMON.write_atomic_bytes(path, text.encode("utf-8"))
        return path

    def run_cli(self, module, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = module.main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def prepare_opening(self):
        # Isolate runtime orchestration from the concurrently edited content tables.
        self.history = mock.Mock()
        self.history.recent_signatures.return_value = []
        self.history.recent_triples.return_value = []
        self.filler = mock.Mock()
        self.filler.fill_opening.return_value = valid_save()
        self.validator = mock.Mock()
        self.validator.validate_data.return_value = []
        for name, value in (
            ("load_roll_opening", self.history), ("load_fill_opening", self.filler),
            ("load_validator", self.validator), ("resolve_roll", {"seed": 7}),
            ("build_skeleton", {}),
        ):
            self.stack.enter_context(mock.patch.object(BUILD, name, return_value=value))

    def opening(self, *args):
        code, stdout, stderr = self.run_cli(
            BUILD, ["--complete", "--opening-mode", "daily", "--seed", "7", *args])
        brief = None
        if code == 0:
            raw = stdout.split("---opening_brief---\n", 1)[1].split("---end---", 1)[0]
            brief = COMMON.load_yaml_bytes(raw.encode("utf-8"))
        return code, brief, stderr


class RuntimeTests(RuntimeCase):
    def test_default_openings_same_seed_are_separate_sessions(self):
        self.prepare_opening()
        code_a, a, _ = self.opening()
        code_b, b, _ = self.opening()
        self.assertEqual((0, 0), (code_a, code_b))
        self.assertNotEqual(a["session"], b["session"])
        self.assertNotEqual(a["state_path"], b["state_path"])
        for brief in (a, b):
            uuid.UUID(brief["session"])
            path = Path(brief["state_path"])
            self.assertEqual(self.saves / "sessions" / brief["session"] / "state.yaml", path)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), brief["state_token"])
        self.assertFalse((self.saves / "current_state.yaml").exists())
        self.assertEqual(2, self.history.append_history.call_count)

    def test_explicit_session_is_stable_and_requires_force_to_reinitialize(self):
        self.prepare_opening()
        code, brief, _ = self.opening("--session", "case-a")
        self.assertEqual(0, code)
        self.assertEqual("case-a", brief["session"])
        self.assertEqual(1, self.opening("--session", "case-a")[0])
        self.assertEqual(1, self.history.append_history.call_count)
        self.assertEqual(0, self.opening("--session", "case-a", "--force")[0])

    def test_explicit_output_and_working_paths_remain_compatible(self):
        self.prepare_opening()
        out, working = self.root / "opening.yaml", self.root / "current_state.yaml"
        code, brief, _ = self.opening("--out", str(out), "--working", str(working))
        self.assertEqual(0, code)
        self.assertEqual(out.read_bytes(), working.read_bytes())
        self.assertEqual(str(working), brief["state_path"])
        self.assertIsNone(brief["session"])
        self.assertFalse((self.saves / "sessions").exists())

    def test_explicit_out_without_working_writes_only_out(self):
        self.prepare_opening()
        out = self.root / "only.yaml"
        code, brief, _ = self.opening("--out", str(out))
        self.assertEqual(0, code)
        self.assertEqual(str(out), brief["state_path"])
        self.assertFalse((self.saves / "sessions").exists())

    def test_no_working_retains_output_artifact_without_session(self):
        self.prepare_opening()
        code, brief, _ = self.opening("--no-working")
        self.assertEqual(0, code)
        self.assertEqual(str(self.saves / "_opening_7.yaml"), brief["state_path"])
        self.assertIsNone(brief["session"])
        self.assertFalse((self.saves / "sessions").exists())

    def test_explicit_session_with_out_also_writes_session_state(self):
        self.prepare_opening()
        out = self.root / "artifact.yaml"
        code, brief, _ = self.opening("--session", "case-a", "--out", str(out))
        self.assertEqual(0, code)
        self.assertEqual("case-a", brief["session"])
        self.assertEqual(out.read_bytes(), Path(brief["state_path"]).read_bytes())

    def test_existing_output_failure_does_not_append_history(self):
        self.prepare_opening()
        out = self.write_state(self.root / "existing.yaml")
        prior = out.read_bytes()
        self.assertEqual(1, self.opening("--out", str(out))[0])
        self.assertEqual(prior, out.read_bytes())
        self.history.append_history.assert_not_called()

    def test_output_and_working_write_failures_do_not_append_history(self):
        self.prepare_opening()
        out, working = self.root / "out.yaml", self.root / "working.yaml"
        real_write = BUILD.write_atomic
        for failing in (out, working):
            with self.subTest(failing=failing):
                def fail_write(path, text):
                    if path == failing:
                        raise OSError("injected write failure")
                    real_write(path, text)
                with mock.patch.object(BUILD, "write_atomic", side_effect=fail_write):
                    code, _, error = self.opening("--out", str(out), "--working", str(working), "--force")
                self.assertEqual(1, code)
                self.assertIn("injected write failure", error)
                self.history.append_history.assert_not_called()

    def test_invalid_opening_never_writes_or_appends_history(self):
        self.prepare_opening()
        self.validator.validate_data.return_value = ["invalid synthetic state"]
        self.assertEqual(1, self.opening()[0])
        self.assertFalse(self.saves.exists())
        self.history.append_history.assert_not_called()

    def test_history_runs_after_validated_successful_write(self):
        self.prepare_opening()
        out = self.root / "out.yaml"
        observed = []
        def append(_):
            observed.append((self.validator.validate_data.call_args, COMMON.load_yaml_file(out)))
        self.history.append_history.side_effect = append
        self.assertEqual(0, self.opening("--out", str(out))[0])
        self.history.append_history.assert_called_once()
        self.assertEqual([(mock.call(valid_save(), "opening"), valid_save())], observed)

    def test_session_path_rejects_traversal_and_windows_reserved_names(self):
        for session in ("../escape", "a/b", "a\\b", "..", "NUL", "COM1", "a.", "", "x" * 81):
            with self.subTest(session=session), self.assertRaises(COMMON.CommonError):
                COMMON.session_state_path(self.saves, session)

    def test_invalid_and_conflicting_session_cli_arguments_leave_no_state(self):
        self.prepare_opening()
        for session in ("", "../escape"):
            with self.subTest(session=session):
                self.assertEqual(1, self.opening("--session", session)[0])
                self.assertEqual(1, self.run_cli(COMMIT, ["--session", session, "--expected-state-token",
                                                        "0" * 64, "--patch", "{}"])[0])
                self.assertEqual(1, self.run_cli(LIVE, ["--session", session])[0])
        self.assertEqual(1, self.opening("--session", "a", "--no-working")[0])
        self.assertEqual(1, self.opening("--session", "a", "--working", str(self.root / "other.yaml"))[0])
        self.assertFalse(self.saves.exists())

    def test_roll_error_from_fresh_module_is_a_clean_cli_failure(self):
        roll = mock.Mock()
        class AnchorError(RuntimeError):
            pass
        roll.AnchorError = AnchorError
        roll.build_roll.side_effect = AnchorError("no approved frameworks")
        with mock.patch.object(BUILD, "load_roll_opening", return_value=roll):
            code, _, error = self.run_cli(BUILD, ["--complete", "--opening-mode", "daily", "--seed", "7"])
        self.assertEqual(1, code)
        self.assertIn("no approved frameworks", error)
        self.assertFalse(self.saves.exists())

    def test_commit_requires_explicit_state_or_session(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            COMMIT.main(["--patch", "{}"])
        self.assertEqual(2, error.exception.code)
        self.assertFalse(self.saves.exists())

    def test_session_commit_requires_token_before_writing(self):
        state = self.write_state(COMMON.session_state_path(self.saves, "case-a"))
        prior = state.read_bytes()
        code, _, error = self.run_cli(COMMIT, ["--session", "case-a", "--patch", "{}"])
        self.assertEqual(1, code)
        self.assertIn("--expected-state-token", error)
        self.assertEqual(prior, state.read_bytes())

    def test_explicit_legacy_state_path_without_token_remains_compatible(self):
        state = self.write_state(self.saves / "current_state.yaml")
        code, stdout, error = self.run_cli(COMMIT, ["--state", str(state), "--patch", "{}", "--format", "json"])
        self.assertEqual(0, code, error)
        payload = json.loads(stdout)
        self.assertEqual(6, payload["turn"])
        self.assertIsNone(payload["session"])
        self.assertEqual(str(state), payload["state_path"])
        self.assertEqual(hashlib.sha256(state.read_bytes()).hexdigest(), payload["state_token"])

    def test_session_stale_patch_is_rejected_and_other_session_unchanged(self):
        a = self.write_state(COMMON.session_state_path(self.saves, "a"))
        b = self.write_state(COMMON.session_state_path(self.saves, "b"))
        prior_b = b.read_bytes()
        token = hashlib.sha256(a.read_bytes()).hexdigest()
        args = ["--session", "a", "--expected-state-token", token, "--patch", "{}", "--format", "json"]
        code, stdout, error = self.run_cli(COMMIT, args)
        self.assertEqual(0, code, error)
        current = a.read_bytes()
        self.assertEqual("a", json.loads(stdout)["session"])
        self.assertEqual(hashlib.sha256(current).hexdigest(), json.loads(stdout)["state_token"])
        code, stdout, error = self.run_cli(COMMIT, args)
        self.assertEqual(1, code)
        self.assertIn("stale state token", error)
        self.assertEqual("", stdout)
        self.assertEqual(current, a.read_bytes())
        self.assertEqual(prior_b, b.read_bytes())

    def test_explicit_state_token_hashes_exact_crlf_bytes(self):
        state = self.write_state(self.root / "state.yaml", crlf=True)
        token = hashlib.sha256(state.read_bytes()).hexdigest()
        code, stdout, _ = self.run_cli(LIVE, [str(state), "--format", "json"])
        self.assertEqual(0, code)
        self.assertEqual(token, json.loads(stdout)["state_token"])
        normalized = hashlib.sha256(state.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        code, _, error = self.run_cli(COMMIT, ["--state", str(state), "--expected-state-token", normalized,
                                             "--patch", "{}"])
        self.assertEqual(1, code)
        self.assertIn("stale state token", error)
        self.assertEqual(0, self.run_cli(COMMIT, ["--state", str(state), "--expected-state-token", token,
                                                "--patch", "{}"])[0])

    def test_concurrent_session_writers_only_one_commits(self):
        path = self.write_state(COMMON.session_state_path(self.saves, "shared"))
        token = hashlib.sha256(path.read_bytes()).hexdigest()
        barrier = threading.Barrier(2)
        results, failures = [], []
        def run():
            try:
                barrier.wait(timeout=5)
                results.append(COMMIT.main(["--session", "shared", "--expected-state-token", token,
                                            "--patch", "{}", "--format", "json"]))
            except Exception as exc:
                failures.append(exc)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            threads = [threading.Thread(target=run) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=15)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual([], failures)
        self.assertEqual([0, 1], sorted(results))
        self.assertEqual(6, COMMON.load_yaml_file(path)["meta"]["turn"])

    def test_commit_write_failure_preserves_state_and_emits_no_receipt(self):
        path = self.write_state(COMMON.session_state_path(self.saves, "a"))
        prior = path.read_bytes()
        with mock.patch.object(COMMIT, "load_saves", return_value=SAVES), \
                mock.patch.object(SAVES, "write_atomic", side_effect=OSError("injected write failure")):
            code, stdout, error = self.run_cli(COMMIT, ["--session", "a", "--expected-state-token",
                                                       hashlib.sha256(prior).hexdigest(), "--patch", "{}"])
        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertIn("injected write failure", error)
        self.assertEqual(prior, path.read_bytes())

    def test_commit_out_binds_destination_not_source(self):
        source = self.write_state(COMMON.session_state_path(self.saves, "source"))
        prior = source.read_bytes()
        out = self.root / "branch.yaml"
        code, stdout, error = self.run_cli(COMMIT, ["--state", str(source), "--out", str(out),
                                                   "--patch", "{}", "--format", "json"])
        self.assertEqual(0, code, error)
        payload = json.loads(stdout)
        self.assertIsNone(payload["session"])
        self.assertEqual(str(out), payload["state_path"])
        self.assertEqual(hashlib.sha256(out.read_bytes()).hexdigest(), payload["state_token"])
        self.assertEqual(prior, source.read_bytes())

    def test_resolved_and_cancelled_receipts_survive_targeted_reload(self):
        path = self.write_state(self.root / "state.yaml")
        patch = {"events_resolve": ["evt-near"], "resolve_outcome": "Reply received",
                 "events_cancel": ["evt-far"], "cancel_outcome": "Review withdrawn"}
        code, stdout, error = self.run_cli(COMMIT, ["--state", str(path), "--patch", json.dumps(patch),
                                                   "--format", "json"])
        self.assertEqual(0, code, error)
        receipts = {event["id"]: event for event in json.loads(stdout)["event_changes"]}
        self.assertEqual({"evt-near", "evt-far"}, set(receipts))
        self.assertEqual("resolved", receipts["evt-near"]["status"])
        self.assertEqual("Reply received", receipts["evt-near"]["outcome"])
        self.assertEqual("cancelled", receipts["evt-far"]["status"])
        self.assertEqual("Review withdrawn", receipts["evt-far"]["outcome"])
        saved = COMMON.load_yaml_file(path)
        self.assertEqual(3, saved["save_version"])
        self.assertEqual(set(valid_save()), set(saved))
        self.assertEqual(set(valid_save()["events"][0]), set(saved["events"][0]))
        self.assertEqual(2, len(saved["events"]))
        self.assertEqual(0, self.run_cli(COMMIT, ["--state", str(path), "--patch", "{}"])[0])
        code, stdout, error = self.run_cli(LIVE, [str(path), "--event", "evt-far", "--event", "evt-near",
                                                 "--format", "json"])
        self.assertEqual(0, code, error)
        payload = json.loads(stdout)
        self.assertEqual({"session", "state_path", "state_token", "events"}, set(payload))
        self.assertEqual(["Review withdrawn", "Reply received"], [e["outcome"] for e in payload["events"]])

    def test_due_event_resolution_is_in_commit_receipts(self):
        state = valid_save()
        state["events"][1]["due_at"] = "2026-07-14T20:01:00+08:00"
        path = self.write_state(self.root / "state.yaml", state)
        code, stdout, error = self.run_cli(COMMIT, ["--state", str(path), "--patch", "{}", "--format", "json"])
        self.assertEqual(0, code, error)
        receipts = json.loads(stdout)["event_changes"]
        self.assertEqual(["evt-far"], [event["id"] for event in receipts])
        self.assertEqual("resolved", receipts[0]["status"])
        self.assertTrue(receipts[0]["outcome"])

    def test_noop_same_turn_does_not_repeat_previous_commit_receipts(self):
        path = self.write_state(self.root / "state.yaml")
        self.assertEqual(0, self.run_cli(COMMIT, ["--state", str(path), "--patch",
                                                '{"events_cancel": ["evt-far"]}'])[0])
        code, stdout, error = self.run_cli(COMMIT, ["--state", str(path), "--patch",
                                                   '{"advance_turn": false}', "--format", "json"])
        self.assertEqual(0, code, error)
        self.assertEqual([], json.loads(stdout)["event_changes"])

    def test_targeted_event_bypasses_only_the_ordinary_pending_cap(self):
        state = valid_save()
        base = state["events"][0]
        for number in range(25):
            event = copy.deepcopy(base)
            event.update(id=f"extra-{number:03d}", semantic_key=f"extra-{number:03d}")
            state["events"].append(event)
        path = self.write_state(COMMON.session_state_path(self.saves, "long"), state)
        code, stdout, _ = self.run_cli(LIVE, ["--session", "long", "--format", "json"])
        self.assertEqual(0, code)
        ordinary = json.loads(stdout)
        self.assertEqual(LIVE.PENDING_EVENTS_LIMIT, sum("id" in event for event in ordinary["pending_events"]))
        self.assertNotIn("extra-024", [event.get("id") for event in ordinary["pending_events"]])
        code, stdout, error = self.run_cli(LIVE, ["--session", "long", "--event", "extra-024", "evt-far",
                                                 "--format", "json"])
        self.assertEqual(0, code, error)
        payload = json.loads(stdout)
        self.assertEqual(["extra-024", "evt-far"], [event["id"] for event in payload["events"]])
        self.assertEqual("long", payload["session"])
        self.assertNotIn("player", payload)
        self.assertEqual(1, self.run_cli(LIVE, [str(path), "--event", "missing"])[0])


class SlotSnapshotTests(RuntimeCase):
    def prepare_slot(self):
        self.store = SAVES.SaveStore(self.saves)
        self.source = self.write_state(self.root / "source.yaml")
        self.manifest = self.store.init_slot("main", self.source)

    def test_slot_load_parses_and_hashes_a_single_locked_snapshot(self):
        self.prepare_slot()
        state_path = self.store.state_path("main")
        original_read = Path.read_bytes
        original_lock = SAVES._COMMON.FileLock
        reads, held = [], []
        class ObservedLock:
            def __init__(self, path):
                self.lock = original_lock(path)
            def __enter__(self):
                self.lock.__enter__()
                held.append(True)
            def __exit__(self, *args):
                held.pop()
                return self.lock.__exit__(*args)
        def read(path):
            if path in (state_path, self.store.manifest_path("main")):
                self.assertTrue(held)
                reads.append(path)
            return original_read(path)
        with mock.patch.object(SAVES._COMMON, "FileLock", ObservedLock), \
                mock.patch.object(Path, "read_bytes", read):
            state, manifest = self.store.load_slot("main")
        self.assertEqual(1, reads.count(state_path))
        self.assertEqual(1, reads.count(self.store.manifest_path("main")))
        self.assertEqual(valid_save(), state)
        self.assertEqual(hashlib.sha256(state_path.read_bytes()).hexdigest(), manifest["state_sha256"])

    def test_mixed_manifest_and_state_are_rejected_by_load_and_list(self):
        self.prepare_slot()
        changed = valid_save()
        changed["meta"]["turn"] = 6
        self.write_state(self.store.state_path("main"), changed)
        with self.assertRaisesRegex(SAVES.SaveError, "checksum mismatch"):
            self.store.load_slot("main")
        self.assertEqual([], self.store.list_slots())

    def test_state_and_manifest_write_failures_restore_exact_prior_pair(self):
        self.prepare_slot()
        state_path, manifest_path = self.store.state_path("main"), self.store.manifest_path("main")
        prior_state, prior_manifest = state_path.read_bytes(), manifest_path.read_bytes()
        candidate = valid_save()
        candidate["meta"]["turn"] = 6
        source = self.write_state(self.root / "candidate.yaml", candidate)
        real_write = SAVES.write_atomic
        for failing in (state_path, manifest_path):
            for after_replace in (False, True):
                with self.subTest(failing=failing, after_replace=after_replace):
                    def fail_write(path, text):
                        if path != failing or after_replace:
                            real_write(path, text)
                        if path == failing:
                            raise OSError("injected write failure")
                    with mock.patch.object(SAVES, "write_atomic", side_effect=fail_write):
                        with self.assertRaisesRegex(SAVES.SaveError, "prior pair restored"):
                            self.store.save_slot("main", source, expected_updated_at=self.manifest["updated_at"])
                    self.assertEqual(prior_state, state_path.read_bytes())
                    self.assertEqual(prior_manifest, manifest_path.read_bytes())
                    self.assertEqual(valid_save(), self.store.load_slot("main")[0])

    def test_failed_init_leaves_no_slot_and_can_be_retried(self):
        source = self.write_state(self.root / "source.yaml")
        store = SAVES.SaveStore(self.saves)
        real_write = SAVES.write_atomic
        for filename in ("state.yaml", "manifest.yaml"):
            for after_replace in (False, True):
                with self.subTest(filename=filename, after_replace=after_replace):
                    slot = f"retry-{filename.split('.')[0]}-{after_replace}"
                    def fail_write(path, text):
                        if path.name != filename or after_replace:
                            real_write(path, text)
                        if path.name == filename:
                            raise OSError("injected init failure")
                    with mock.patch.object(SAVES, "write_atomic", side_effect=fail_write):
                        with self.assertRaisesRegex(SAVES.SaveError, "cannot initialize"):
                            store.init_slot(slot, source)
                    self.assertFalse(store.slot_dir(slot).exists())
                    self.assertNotIn(slot, [item["slot"] for item in store.list_slots()])
                    store.init_slot(slot, source)
                    self.assertEqual(valid_save(), store.load_slot(slot)[0])

    def test_version_one_manifest_remains_readable_and_upgrades_on_save(self):
        self.prepare_slot()
        manifest = dict(self.manifest)
        manifest["manifest_version"] = 1
        manifest.pop("state_sha256")
        COMMON.write_atomic(self.store.manifest_path("main"), COMMON.yaml_text(manifest))
        self.assertEqual(1, self.store.load_slot("main")[1]["manifest_version"])
        updated = self.store.save_slot("main", self.source, expected_updated_at=manifest["updated_at"])
        self.assertEqual(2, updated["manifest_version"])
        self.assertEqual(set(SAVES.MANIFEST_KEYS), set(updated))


class StrictYamlTests(unittest.TestCase):
    def test_duplicate_keys_at_any_depth_and_in_merges_are_rejected(self):
        samples = (b"a: 1\na: 2\n", b"outer:\n  key: 1\n  key: 2\n",
                   b"items:\n- key: 1\n  key: 2\n",
                   b"base: &base {a: 1}\nmerged: {<<: *base, a: 2}\n")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.yaml"
            for snapshot in samples:
                with self.subTest(snapshot=snapshot):
                    COMMON.write_atomic_bytes(path, snapshot)
                    with self.assertRaisesRegex(COMMON.CommonError, "duplicate key"):
                        COMMON.load_yaml_file(path)
                    with mock.patch.object(COMMON, "DATA_DIR", Path(tmp)):
                        with self.assertRaisesRegex(COMMON.CommonError, "duplicate key"):
                            COMMON.load_data_yaml("data.yaml")
                    with self.assertRaisesRegex(SAVES.SaveError, "duplicate key"):
                        SAVES.load_yaml(path)
                    with self.assertRaisesRegex(COMMIT.CommitError, "duplicate key"):
                        COMMIT.load_yaml(path)
                    with self.assertRaisesRegex(SystemExit, "duplicate key"):
                        LIVE._load(path)

    def test_valid_data_yaml_api_and_safe_types_remain_compatible(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.yaml"
            COMMON.write_atomic(path, "a: [1, 2]\nflag: true\n")
            with mock.patch.object(COMMON, "DATA_DIR", Path(tmp)):
                self.assertEqual({"a": [1, 2], "flag": True}, COMMON.load_data_yaml("data.yaml"))
            COMMON.write_atomic(path, "- sequence\n")
            with mock.patch.object(COMMON, "DATA_DIR", Path(tmp)):
                with self.assertRaisesRegex(COMMON.CommonError, "not a mapping"):
                    COMMON.load_data_yaml("data.yaml")
        with self.assertRaises(COMMON.CommonError):
            COMMON.load_yaml_bytes(b"!!python/object:builtins.object {}")
        with self.assertRaises(COMMON.CommonError):
            COMMON.load_yaml_bytes(b"? [unhashable]\n: value\n")


if __name__ == "__main__":
    unittest.main()
