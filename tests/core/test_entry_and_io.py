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


if __name__ == "__main__":
    unittest.main()
