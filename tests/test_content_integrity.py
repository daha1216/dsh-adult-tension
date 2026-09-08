"""内容完整性：数据文件指纹锁 + 内容体检进回归。

指纹锁覆盖 scripts/data/ 下全部内容数据文件。任何改动都会让指纹测试失败，
这是故意的：改动应当先经过内容体检、抽样审查和开局探针，再更新 EXPECTED。
当前指纹可用 `python scripts/check_content.py --fingerprint` 查看。
"""

from __future__ import annotations

import hashlib
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
DATA = ROOT / "scripts" / "data"

DATA_FILES = (
    "pools.yaml",
    "character_meta.yaml",
    "twists.yaml",
    "templates.yaml",
    "names.yaml",
    "identities.yaml",
    "locations.yaml",
    "character_pools.yaml",
    "location_profiles.yaml",
    "action_categories.yaml",
    "action_metadata.yaml",
    "identity_profiles.yaml",
    "twist_profiles.yaml",
)

EXPECTED = "287ea92b758165a6305a7455a83aa1c804ae3db0a165bcb7be8b985ee563b638"


def _load(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECK = _load("check_content", "scripts/check_content.py")


def fingerprint() -> str:
    digest = hashlib.sha256()
    for name in DATA_FILES:
        digest.update(name.encode("utf-8"))
        digest.update((DATA / name).read_bytes())
    return digest.hexdigest()


class ContentIntegrityTests(unittest.TestCase):
    def test_data_files_exist(self) -> None:
        for name in DATA_FILES:
            self.assertTrue((DATA / name).exists(), name)

    def test_voice_filter_is_structured(self) -> None:
        fill = _load("fill_opening_for_check", "scripts/fill_opening.py")
        templates = CHECK._load("templates.yaml")
        for flavor, quirk in (("—", "—"), ("冷淡疏离", "话留半句")):
            voice = fill.voice_filter({"表层风味": flavor, "口癖": quirk, "反差轴": ""},
                                      "测试身份", templates)
            self.assertEqual({"surface", "inner", "switch_conditions"}, set(voice))
            self.assertTrue(voice["surface"])
            self.assertTrue(voice["inner"])
            self.assertTrue(voice["switch_conditions"])


    def test_content_check_includes_voice_format_gate(self) -> None:
        report = CHECK.check()
        voice_errors = [e for e in report.errors if "语态" in e]
        self.assertEqual([], voice_errors, f"双语态检查不应报错：{voice_errors}")
        self.assertGreaterEqual(report.checks, 340)

    def test_content_fingerprint(self) -> None:
        actual = fingerprint()
        self.assertEqual(
            EXPECTED, actual,
            f"内容数据已变化。若此次改动是故意的，把 EXPECTED 更新为：{actual!r}")

    def test_check_content_passes(self) -> None:
        report = CHECK.check()
        self.assertEqual([], report.errors, "；".join(report.errors))

    def test_commands_yaml_syntax_and_structure(self) -> None:
        cmd_path = ROOT / "commands.yaml"
        self.assertTrue(cmd_path.exists(), "commands.yaml must exist at root")
        yaml_mod = CHECK.yaml
        data = yaml_mod.safe_load(cmd_path.read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict)
        self.assertIn("command_categories", data)
        self.assertIn("parse_rules", data)
        self.assertIn("core", data["command_categories"])
        self.assertIn("advanced", data["command_categories"])


if __name__ == "__main__":
    unittest.main()
