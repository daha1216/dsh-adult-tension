"""Data directory location order and platform defaults (SKILL_PACKAGING.md section 6)."""

import os
import unittest

import _bootstrap  # noqa: F401
from adult_tension import paths


class DataDirTest(unittest.TestCase):
    def test_argument_beats_environment(self):
        path, source = paths.resolve("/explicit", {"ADULT_TENSION_HOME": "/from-env"})
        self.assertEqual((path, source), (os.path.abspath("/explicit"), "arg"))

    def test_environment_beats_default(self):
        path, source = paths.resolve(None, {"ADULT_TENSION_HOME": "/from-env"})
        self.assertEqual((path, source), (os.path.abspath("/from-env"), "env"))

    def test_platform_defaults(self):
        self.assertEqual(
            paths.platform_default("win32", {"LOCALAPPDATA": r"C:\Users\x\AppData\Local"}, "/home/x"),
            os.path.join(r"C:\Users\x\AppData\Local", "adult-tension"),
        )
        self.assertEqual(
            paths.platform_default("darwin", {}, "/Users/x"),
            os.path.join("/Users/x", "Library", "Application Support", "adult-tension"),
        )
        self.assertEqual(
            paths.platform_default("linux", {"XDG_DATA_HOME": "/xdg"}, "/home/x"),
            os.path.join("/xdg", "adult-tension"),
        )
        self.assertEqual(
            paths.platform_default("linux", {}, "/home/x"),
            os.path.join("/home/x", ".local", "share", "adult-tension"),
        )

    def test_data_dir_argument_scan(self):
        self.assertEqual(paths.data_dir_arg(["doctor", "--data-dir", "/d"]), "/d")
        self.assertEqual(paths.data_dir_arg(["doctor", "--data-dir=/e"]), "/e")
        self.assertIsNone(paths.data_dir_arg(["doctor"]))

    def test_inside_detection(self):
        root = os.path.abspath("skill-root")
        self.assertTrue(paths.is_inside(os.path.join(root, "data"), root))
        self.assertFalse(paths.is_inside(os.path.abspath("elsewhere"), root))


if __name__ == "__main__":
    unittest.main()
