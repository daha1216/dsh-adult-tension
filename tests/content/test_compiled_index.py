"""The compiled content directory is self-consistent."""

import os
import unittest

import _bootstrap  # noqa: F401
from adult_tension.content.store import ContentStore
from adult_tension.content.verify import verify_installed
from helpers.cli import SKILL_ROOT


class CompiledIndexTest(unittest.TestCase):
    def setUp(self):
        self.store = ContentStore(os.path.join(SKILL_ROOT, "content"))

    def test_index_parses_strictly_and_has_versions(self):
        index = self.store.index()
        self.assertIsInstance(index.get("content_version"), str)
        self.assertIsInstance(index.get("worlds"), list)

    def test_every_listed_world_is_present(self):
        problems, summary = verify_installed(self.store)
        self.assertEqual(problems, [])
        self.assertEqual(summary["worlds"], len(self.store.index()["worlds"]))


if __name__ == "__main__":
    unittest.main()
