from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "scripts" / "data"


def resolve(value, path):
    """Require every wildcard branch to resolve, including list entries."""
    if not path:
        if value is None or value == "" or value == [] or value == {}:
            raise ValueError("empty source")
        return
    key, *tail = path
    if key == "*":
        if not isinstance(value, (dict, list)) or not value:
            raise ValueError("wildcard needs a non-empty mapping or list")
        for child in value.values() if isinstance(value, dict) else value:
            resolve(child, tail)
    else:
        if not isinstance(value, dict) or key not in value:
            raise ValueError(f"missing source key: {key}")
        resolve(value[key], tail)


class MaterialArchitectureTests(unittest.TestCase):
    def test_index_matches_existing_sources(self):
        index = yaml.safe_load((ROOT / "references/material_architecture.yaml").read_text(encoding="utf-8"))
        self.assertEqual(1, index["version"])
        self.assertEqual(
            ["world", "space", "character", "relationship", "activity", "opening", "development", "expression"],
            list(index["layers"]),
        )
        groups = list(index["layers"].values())
        groups.append({"title": "compatibility", "modes": ["daily", "pressure"], "sources": index["compatibility"]})
        cache = {}
        for group in groups:
            self.assertTrue(group["title"])
            self.assertEqual(["daily", "pressure"], group["modes"])
            self.assertTrue(group["sources"])
            seen = set()
            for source in group["sources"]:
                with self.subTest(layer=group["title"], source=source):
                    name, path = source["file"], source["path"]
                    self.assertEqual(name, Path(name).name)
                    self.assertTrue(name.endswith(".yaml"))
                    self.assertIsInstance(path, list)
                    self.assertTrue(all(isinstance(key, str) and key for key in path))
                    modes = source.get("modes", group["modes"])
                    self.assertTrue(modes)
                    self.assertTrue(set(modes) <= set(group["modes"]))
                    marker = (name, tuple(path))
                    self.assertNotIn(marker, seen)
                    seen.add(marker)
                    if name not in cache:
                        cache[name] = yaml.safe_load((DATA / name).read_text(encoding="utf-8"))
                    resolve(cache[name], path)

    def test_wildcard_checks_every_branch(self):
        resolve({"a": [{"value": "ok"}]}, ["*", "*", "value"])
        for value in ({"a": {"value": "ok"}, "b": {}}, {}, {"a": {"value": ""}}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve(value, ["*", "value"])


if __name__ == "__main__":
    unittest.main()

