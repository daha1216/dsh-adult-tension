"""Architecture rules that must hold in the code (ARCHITECTURE.md, D2, D4)."""

import ast
import os
import sys
import unittest

import _bootstrap  # noqa: F401
from helpers.cli import SKILL_ROOT

RUNTIME = os.path.join(SKILL_ROOT, "runtime", "adult_tension")
DOMAIN_FORBIDDEN = {"sqlite3", "pathlib", "time", "random", "os", "datetime", "subprocess", "socket", "shutil", "tempfile", "io", "logging"}


def modules(root):
    for base, _dirs, names in os.walk(root):
        for name in names:
            if name.endswith(".py"):
                path = os.path.join(base, name)
                with open(path, "rb") as handle:
                    yield path, ast.parse(handle.read().decode("utf-8"))


def imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, 0
        elif isinstance(node, ast.ImportFrom):
            yield node.module or "", node.level


class ArchitectureTest(unittest.TestCase):
    def test_domain_is_pure(self):
        for path, tree in modules(os.path.join(RUNTIME, "domain")):
            for name, level in imports(tree):
                top = name.split(".")[0]
                if level == 0:
                    self.assertNotIn(top, DOMAIN_FORBIDDEN, "%s imports %s" % (path, name))
                elif level >= 2:
                    # from the domain, only pure sibling modules of the package may be imported
                    self.assertIn(top, ("", "errors", "schema", "jsonio"), "%s imports ..%s" % (path, name))

    def test_runtime_imports_only_the_standard_library(self):
        stdlib = set(sys.stdlib_module_names)
        for path, tree in modules(RUNTIME):
            for name, level in imports(tree):
                if level == 0:
                    top = name.split(".")[0]
                    self.assertTrue(top in stdlib or top == "adult_tension", "%s imports %s" % (path, name))

    def test_only_the_application_layer_commits_transactions(self):
        for path, tree in modules(RUNTIME):
            rel = os.path.relpath(path, RUNTIME).replace(os.sep, "/")
            source = ast.unparse(tree)
            if "COMMIT" in source and "execute" in source:
                self.assertTrue(rel.startswith("application/") or rel == "persistence/db.py", rel)

    def test_projections_do_not_touch_storage(self):
        for path, tree in modules(os.path.join(RUNTIME, "projections")):
            for name, _level in imports(tree):
                self.assertNotIn("persistence", name, path)
                self.assertNotIn("sqlite3", name, path)


if __name__ == "__main__":
    unittest.main()
