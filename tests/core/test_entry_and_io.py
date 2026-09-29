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


if __name__ == "__main__":
    unittest.main()
