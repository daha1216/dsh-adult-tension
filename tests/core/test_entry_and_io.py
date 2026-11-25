"""Entry script version gate, strict JSON input, and shape validation."""

import ast
import json
import os
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401
from adult_tension import jsonio, schema
from adult_tension.errors import AppError
from helpers.cli import ENTRY, clean_env


def run_with_fake_version(version, args):
    """Run the entry script with sys.version_info faked (no old interpreter on this machine)."""
    code = (
        "import sys, runpy\n"
        "sys.version_info = %r\n"
        "sys.argv = [%r] + %r\n"
        "runpy.run_path(%r, run_name='__main__')\n" % (version, ENTRY, args, ENTRY)
    )
    proc = subprocess.run([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=clean_env(), timeout=60)
    return proc.returncode, proc.stdout


class VersionGateTest(unittest.TestCase):
    def test_python_39_gets_runtime_unsupported(self):
        code, raw = run_with_fake_version((3, 9, 18, "final", 0), ["doctor", "--json"])
        envelope = json.loads(raw.decode("utf-8"))
        self.assertEqual(code, 20)
        self.assertFalse(envelope["ok"])
        self.assertEqual(envelope["error"]["code"], "RUNTIME_UNSUPPORTED")
        self.assertEqual(envelope["error"]["required"], "3.10")
        self.assertEqual(envelope["error"]["found"], "3.9.18")
        self.assertIn("3.10", envelope["error"]["message"])

    def test_python_38_gets_runtime_unsupported(self):
        code, raw = run_with_fake_version((3, 8, 10, "final", 0), ["version", "--json"])
        self.assertEqual(code, 20)
        self.assertEqual(json.loads(raw.decode("utf-8"))["error"]["code"], "RUNTIME_UNSUPPORTED")

    def test_entry_script_parses_with_old_grammar(self):
        with open(ENTRY, "rb") as handle:
            source = handle.read().decode("utf-8")
        tree = ast.parse(source, feature_version=(3, 4))
        for node in ast.walk(tree):
            self.assertNotIsInstance(node, (ast.JoinedStr, ast.AnnAssign, ast.NamedExpr))


class StrictJsonTest(unittest.TestCase):
    def test_duplicate_keys_are_reported_with_paths(self):
        with self.assertRaises(AppError) as caught:
            jsonio.loads_strict('{"a": 1, "b": {"c": 1, "c": 2}, "a": 3}')
        paths = sorted(d["path"] for d in caught.exception.details)
        self.assertEqual(paths, ["$.a", "$.b.c"])
        self.assertEqual(caught.exception.code, "INVALID_INPUT")

    def test_duplicate_keys_inside_arrays(self):
        with self.assertRaises(AppError) as caught:
            jsonio.loads_strict('{"ops": [{"op": "x"}, {"op": "y", "op": "z"}]}')
        self.assertEqual([d["path"] for d in caught.exception.details], ["$.ops[1].op"])

    def test_nan_and_infinity_rejected(self):
        for text in ('{"p": NaN}', '{"p": Infinity}', '{"p": -Infinity}'):
            with self.assertRaises(AppError):
                jsonio.loads_strict(text)

    def test_a_lone_surrogate_escape_is_an_input_error_with_its_path(self):
        # Valid JSON that no UTF-8 output can carry: a model that cut an emoji's escape in half.
        text = '{"a": ["ok", "\\ud83d"], "\\udc00k": 1, "e": "\\ud83d\\ude00"}'
        with self.assertRaises(AppError) as caught:
            jsonio.loads_strict(text)
        self.assertEqual(caught.exception.code, "INVALID_INPUT")
        paths = [d["path"] for d in caught.exception.details]
        self.assertEqual(paths, ["$.a[1]", "$.\\udc00k"])
        json.dumps(caught.exception.to_dict(), ensure_ascii=False).encode("utf-8")  # the error itself can be written
        self.assertEqual(jsonio.loads_strict('{"e": "\\ud83d\\ude00"}'), {"e": "\U0001F600"})  # a whole pair is fine

    def test_nesting_beyond_the_limit_is_an_input_error(self):
        deep = lambda n: '{"a": ' + "[" * n + "]" * n + "}"  # noqa: E731
        jsonio.loads_strict(deep(jsonio.MAX_DEPTH - 1))
        for n in (jsonio.MAX_DEPTH, 100000):  # the second one is past the parser's own recursion
            with self.assertRaises(AppError) as caught:
                jsonio.loads_strict(deep(n))
            self.assertEqual(caught.exception.code, "INVALID_INPUT")
            self.assertEqual(len(caught.exception.details), 1)

    def test_bom_tolerated_and_non_utf8_rejected(self):
        text = jsonio.decode_bytes(b"\xef\xbb\xbf" + '{"名":"林婉"}'.encode("utf-8"))
        self.assertEqual(jsonio.loads_strict(text), {"名": "林婉"})
        with self.assertRaises(AppError) as caught:
            jsonio.decode_bytes('{"名":"林婉"}'.encode("gbk"))
        self.assertEqual(caught.exception.code, "INVALID_INPUT")


class SchemaTest(unittest.TestCase):
    SPEC = schema.Obj(
        {
            "name": schema.Field(schema.Str(1, 10)),
            "count": schema.Field(schema.Int(0, 5)),
            "ratio": schema.Field(schema.Num(0, 1, lo_open=True, hi_open=True), required=False),
            "kind": schema.Field(schema.Enum("a", "b"), required=False, default="a"),
            "items": schema.Field(schema.List(schema.Id(), max_items=2), required=False, default=[]),
            "inner": schema.Field(schema.Obj({"flag": schema.Field(schema.Bool())}), required=False),
        }
    )

    def errors(self, value):
        _out, errs = schema.validate(self.SPEC, value)
        return {e["path"]: e["reason"] for e in errs}

    def test_valid_input_gets_defaults(self):
        out, errs = schema.validate(self.SPEC, {"name": "林婉", "count": 3})
        self.assertEqual(errs, [])
        self.assertEqual(out, {"name": "林婉", "count": 3, "kind": "a", "items": []})

    def test_unknown_and_missing_fields(self):
        errs = self.errors({"count": 1, "extra": 1, "inner": {"flag": True, "x": 2}})
        self.assertIn("$.extra", errs)
        self.assertIn("$.name", errs)
        self.assertIn("$.inner.x", errs)

    def test_a_missing_field_says_what_it_takes(self):
        spec = schema.Obj({"origin": schema.Field(schema.Enum("observed", "told"), desc="谁看见的"), "n": schema.Field(schema.Int(0, 5))})
        _out, errs = schema.validate(spec, {})
        hints = {e["path"]: e["hint"] for e in errs}
        self.assertEqual(hints, {"$.origin": "origin：枚举：`observed` / `told`；谁看见的", "$.n": "n：%s" % schema.Int(0, 5).doc()})

    def test_out_of_range_is_rejected_not_clamped(self):
        errs = self.errors({"name": "a", "count": 6, "ratio": 1.0})
        self.assertIn("$.count", errs)
        self.assertIn("$.ratio", errs)

    def test_bool_is_not_an_integer_and_float_is_not_integer(self):
        self.assertIn("$.count", self.errors({"name": "a", "count": True}))
        self.assertIn("$.count", self.errors({"name": "a", "count": 2.0}))

    def test_bad_ids_and_list_bounds(self):
        errs = self.errors({"name": "a", "count": 1, "items": ["Lin Wan"]})
        self.assertIn("$.items[0]", errs)
        errs = self.errors({"name": "a", "count": 1, "items": ["a", "b", "c"]})
        self.assertIn("$.items", errs)

    def test_all_errors_collected_at_once(self):
        _out, errs = schema.validate(self.SPEC, {"name": "", "count": -1, "kind": "z", "nope": 1})
        self.assertEqual(len(errs), 4)

    def test_tagged_unhashable_and_non_string_tag_is_input_error(self):
        spec = schema.Tagged("op", {"ok": schema.Obj({"op": schema.Field(schema.Str())})})
        for bad in ([], {}, 123, None):
            out, errs = schema.validate(spec, {"op": bad})
            self.assertIsNone(out)
            self.assertEqual(len(errs), 1)
            self.assertEqual((errs[0]["path"], errs[0]["code"]), ("$.op", "INVALID_INPUT"))

    def test_empty_object_unknown_field_hint_never_trails_empty(self):
        _out, errs = schema.validate(schema.EMPTY, {"extra": 1})
        self.assertEqual(errs[0]["hint"], schema.EMPTY.desc)
        self.assertNotIn("可用字段：", errs[0]["hint"])
        _out, errs2 = schema.validate(schema.Obj({}), {"extra": 1})
        self.assertEqual(errs2[0]["hint"], "不接受字段")

    def test_one_sided_and_unbounded_int_and_num_never_render_none(self):
        cases = [
            (schema.Int(lo=0), -1, "≥0", "整数 ≥0"),
            (schema.Int(hi=5), 6, "≤5", "整数 ≤5"),
            (schema.Int(), None, None, "整数"),
            (schema.Num(lo=0), -0.5, "≥0", "数值 ≥0"),
            (schema.Num(lo=0, lo_open=True), 0, ">0", "数值 >0"),
            (schema.Num(hi=1), 1.5, "≤1", "数值 ≤1"),
            (schema.Num(hi=1, hi_open=True), 1, "<1", "数值 <1"),
            (schema.Num(), None, None, "数值"),
        ]
        for spec, bad_val, bound_text, expected_doc in cases:
            self.assertEqual(spec.doc(), expected_doc)
            self.assertNotIn("None", spec.doc())
            if bad_val is not None:
                _out, errs = schema.validate(spec, bad_val)
                self.assertEqual(len(errs), 1)
                self.assertIn(bound_text, errs[0]["reason"])
                self.assertNotIn("None", errs[0]["reason"])
        # Two-sided bounds keep their existing formatting.
        self.assertEqual(schema.Int(0, 5).doc(), "整数 0..5")
        self.assertEqual(schema.Num(0, 1, lo_open=True, hi_open=True).doc(), "数值 (0, 1)")


class LauncherAndPathsTest(unittest.TestCase):
    def test_data_dir_arg_takes_last_value_matching_cli(self):
        from adult_tension import paths
        from adult_tension.adapters import cli

        for argv, expected in (
            (["doctor", "--data-dir", "/first", "--data-dir", "/second"], "/second"),
            (["doctor", "--data-dir=/first", "--data-dir", "/second"], "/second"),
            (["doctor", "--data-dir", "/first", "--data-dir=/second"], "/second"),
            (["doctor", "--data-dir=/first", "--data-dir=/second"], "/second"),
            (["doctor", "--data-dir", "--data-dir=/weird"], "--data-dir=/weird"),
        ):
            self.assertEqual(paths.data_dir_arg(argv), expected, argv)
            _cmd, options, _flags = cli.parse_argv(argv)
            self.assertEqual(options.get("data_dir"), expected, argv)

    def test_launcher_respects_explicit_no_bytecode_flags(self):
        from adult_tension import paths
        from helpers.cli import SKILL_ROOT
        from helpers.fs import temp_dir

        runtime_dir = os.path.join(SKILL_ROOT, "runtime")
        with temp_dir() as tmp:
            # 1. python -B preserves sys.dont_write_bytecode=True and writes no pycache
            d1 = os.path.join(tmp, "d1")
            snippet = (
                "import sys\n"
                "sys.dont_write_bytecode = True\n"
                "sys.path.insert(0, %r)\n"
                "from adult_tension import launcher\n"
                "rc = launcher.launch(['version', '--json', '--data-dir', %r], %r)\n"
                "assert rc == 0 and sys.dont_write_bytecode is %s\n"
            )
            env_no_var = clean_env()
            env_no_var.pop("PYTHONDONTWRITEBYTECODE", None)
            proc_b = subprocess.run(
                [sys.executable, "-B", "-c", snippet % (runtime_dir, d1, SKILL_ROOT, "True")],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env_no_var,
                timeout=60,
            )
            self.assertEqual(proc_b.returncode, 0, proc_b.stderr.decode("utf-8", "replace"))
            self.assertFalse(os.path.exists(paths.pycache_dir(d1)))

            # 2. PYTHONDONTWRITEBYTECODE=1 also preserves sys.dont_write_bytecode=True
            d2 = os.path.join(tmp, "d2")
            env_with_var = clean_env(PYTHONDONTWRITEBYTECODE="1")
            proc_env = subprocess.run(
                [sys.executable, "-c", snippet % (runtime_dir, d2, SKILL_ROOT, "True")],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env_with_var,
                timeout=60,
            )
            self.assertEqual(proc_env.returncode, 0, proc_env.stderr.decode("utf-8", "replace"))
            self.assertFalse(os.path.exists(paths.pycache_dir(d2)))

            # 3. Without -B or PYTHONDONTWRITEBYTECODE, launcher redirects pycache to data_dir and enables it
            d3 = os.path.join(tmp, "d3")
            proc_normal = subprocess.run(
                [sys.executable, "-c", snippet % (runtime_dir, d3, SKILL_ROOT, "False")],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env_no_var,
                timeout=60,
            )
            self.assertEqual(proc_normal.returncode, 0, proc_normal.stderr.decode("utf-8", "replace"))


class CliParseArgvTest(unittest.TestCase):
    def test_invalid_int_flag_points_to_its_own_argv_index(self):
        from adult_tension.adapters import cli

        for argv, expected_path in (
            (["smoke", "--turns", "abc"], "$.argv[1]"),
            (["smoke", "--turns=abc"], "$.argv[1]"),
            (["smoke", "--seed", "1", "--turns", "xyz"], "$.argv[3]"),
        ):
            with self.assertRaises(AppError, msg=argv) as caught:
                cli.parse_argv(argv)
            self.assertEqual(caught.exception.code, "INVALID_INPUT")
            self.assertEqual(caught.exception.details[0]["path"], expected_path)

    def test_unhashable_op_returns_invalid_input_not_internal_error(self):
        import io

        from adult_tension.adapters import cli
        from helpers.cli import SKILL_ROOT

        body = json.dumps(
            {
                "session_id": "s_12345678",
                "request_id": "req_unhashable_op",
                "expected_revision": 1,
                "turns": [
                    {
                        "action_mode": "continue",
                        "player_input": "继续",
                        "operations": [{"op": []}],
                        "content_tags": [],
                        "summary": "测试",
                        "open_action": "停住",
                    }
                ],
            },
            ensure_ascii=False,
        ).encode("utf-8")
        envelope, code, _options, _text, _payload = cli.execute(["commit-turn", "--json", "--input-file", "-"], SKILL_ROOT, io.BytesIO(body), clean_env())
        self.assertEqual((code, envelope["error"]["code"]), (10, "INVALID_INPUT"))
        self.assertEqual(envelope["error"]["details"][0]["path"], "$.turns[0].operations[0].op")

    def test_missing_option_value_before_boolean_flag_is_rejected(self):
        from adult_tension import paths
        from adult_tension.adapters import cli

        self.assertIsNone(paths.data_dir_arg(["doctor", "--data-dir", "--json"]))
        self.assertEqual(paths.data_dir_arg(["doctor", "--data-dir", "/ok", "--data-dir", "--json"]), "/ok")
        for argv, expected_path in (
            (["doctor", "--data-dir", "--json"], "$.argv[1]"),
            (["verify-content", "--world", "--skip-diversity"], "$.argv[1]"),
            (["new-game", "--input-file", "--include-drafts"], "$.argv[1]"),
        ):
            with self.assertRaises(AppError, msg=argv) as caught:
                cli.parse_argv(argv)
            self.assertEqual((caught.exception.code, caught.exception.details[0]["path"]), ("INVALID_INPUT", expected_path))

    def test_read_payload_enforces_max_input_bytes_and_jsonio_copy_is_isolated(self):
        import io
        from unittest import mock

        from adult_tension.adapters import cli
        from adult_tension.application import commands

        src = {"a": [1, {"b": "中"}], "c": True}
        cloned = jsonio.copy(src)
        self.assertEqual(cloned, src)
        cloned["a"][1]["b"] = "改"
        cloned["a"].append(2)
        self.assertEqual(src, {"a": [1, {"b": "中"}], "c": True})

        cmd = commands.get("new-game")
        big = io.BytesIO(b'{"a":"' + b"x" * 128 + b'"}')
        with mock.patch.object(cli, "MAX_INPUT_BYTES", 64):
            with self.assertRaises(AppError) as caught:
                cli.read_payload(cmd, {"input_file": "-"}, big)
        self.assertEqual((caught.exception.code, caught.exception.details[0]["path"]), ("INVALID_INPUT", "$.input_file"))


if __name__ == "__main__":
    unittest.main()
