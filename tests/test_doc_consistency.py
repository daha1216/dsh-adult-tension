"""文档与校验脚本的一致性测试。

防止 SKILL.md / references 中手工同步的枚举、不变量和文件引用与
scripts/validate_state.py 的常量发生漂移（历史上 blocked 码、invariants
曾因手工同步漏改而失配）。
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]

SCRIPT = ROOT / "scripts" / "validate_state.py"
SPEC = importlib.util.spec_from_file_location("validate_state", SCRIPT)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)

ROLL_SCRIPT = ROOT / "scripts" / "roll_opening.py"
ROLL_SPEC = importlib.util.spec_from_file_location("roll_opening", ROLL_SCRIPT)
assert ROLL_SPEC and ROLL_SPEC.loader
ROLLER = importlib.util.module_from_spec(ROLL_SPEC)
ROLL_SPEC.loader.exec_module(ROLLER)

DOCS = {
    "SKILL": ROOT / "SKILL.md",
    "OPENING": ROOT / "references" / "开局流程.md",
    "CHARACTER": ROOT / "references" / "角色设计.md",
    "MATERIAL": ROOT / "references" / "素材库.md",
    "STATE": ROOT / "references" / "状态总结.md",
    "WORLD": ROOT / "references" / "世界运转.md",
}

TEXTS = {name: path.read_text(encoding="utf-8") for name, path in DOCS.items()}

# 每个校验器常量及其枚举值应当出现在哪个文档中。
CONSTANT_DOC = {
    "SAFETY_STATES": "STATE",
    "MODES": "STATE",
    "POWER_STRUCTURES": "STATE",
    "BOUNDARY_STATUSES": "STATE",
    "CONSENT_STATUSES": "STATE",
    "EVENT_STATUSES": "STATE",
    "DIRECTIVE_KINDS": "STATE",
    "DIRECTIVE_STATUSES": "STATE",
    "DIRECTIVE_DEADLINES": "STATE",
    "DIRECTIVE_SCOPES": "STATE",
    "DIRECTIVE_BLOCK_CODES": "STATE",
    "EVENT_KINDS": "WORLD",
    "ROLE_LEVELS": "CHARACTER",
}

# 已删除、不得再出现在任何文档中的遗留字段/阻断码。
REMOVED_TOKENS = (
    "consent_missing",
    "active_boundary",
    "boundaries_verified",
    "consent_verified",
    "创作与演艺",
    "成人行业与私密服务",
    "v2 迁移到 v3",
    "一句话字符串同样可通过校验",
)

# 冻结段口径与 PROGRESS.md「基线」一致：从标题起到下一输出约定之前。
FROZEN_START = "### 性行为场景写法"
FROZEN_END = "开局以外的每个有效指令固定输出"
FROZEN_LENGTH = 606
FROZEN_SHA256 = "80AF72827A88DDDA0FD7F1E2A173D371BF7F870A113F05E84E5BD7395C3A33CF"

HISTORY_NUMBERS = (
    ("HISTORY_LIMIT", "只保留最近 {} 条"),
    ("HISTORY_CANDIDATE_LIMIT", "比较 {} 个候选"),
    ("HISTORY_RECENT_LIMIT", "硬避最近 {} 局"),
)


class DocConsistencyTests(unittest.TestCase):
    def test_frozen_section_unchanged(self) -> None:
        text = TEXTS["SKILL"]
        start = text.index(FROZEN_START)
        end = text.index(FROZEN_END)
        segment = text[start:end]
        digest = hashlib.sha256(segment.encode("utf-8")).hexdigest().upper()
        self.assertEqual(
            (len(segment), digest),
            (FROZEN_LENGTH, FROZEN_SHA256),
            "冻结段已变更；有意改动时须按 PROGRESS.md 口径同步更新基线与变更记录",
        )

    def test_skill_referenced_files_exist(self) -> None:
        refs = re.findall(r"`((?:references|scripts)/[^`]+)`", TEXTS["SKILL"])
        self.assertTrue(refs, "SKILL.md 中没有找到文件引用")
        for ref in refs:
            self.assertTrue((ROOT / ref).exists(), f"SKILL.md 引用的文件不存在: {ref}")

    def test_save_version_matches(self) -> None:
        self.assertEqual(VALIDATOR.SAVE_VERSION, 3)
        self.assertIn("save_version: 3", TEXTS["STATE"])

    def test_validator_enum_values_documented(self) -> None:
        for constant, doc_name in CONSTANT_DOC.items():
            doc_text = TEXTS[doc_name]
            for value in getattr(VALIDATOR, constant):
                self.assertIn(value, doc_text,
                              f"{constant} 的值 {value!r} 未出现在 {DOCS[doc_name].name}")

    def test_removed_tokens_absent_from_docs(self) -> None:
        for token in REMOVED_TOKENS:
            for doc_name, text in TEXTS.items():
                self.assertNotIn(token, text,
                                 f"已删除的字段/阻断码 {token!r} 仍出现在 {DOCS[doc_name].name}")

    def test_safety_state_is_invariant(self) -> None:
        self.assertIn("亲密内容仅在 `safety_state` 为 running 时书写", TEXTS["SKILL"])

    def test_blocked_condition_includes_paused(self) -> None:
        self.assertIn("不变量 1-2 的冲突或 paused 安全状态", TEXTS["SKILL"])

    def test_view_state_command_documented(self) -> None:
        self.assertIn("| 查看状态 |", TEXTS["SKILL"])

    def test_help_command_documented(self) -> None:
        self.assertIn("| 帮助", TEXTS["SKILL"])

    def test_history_numbers_match_protocol_text(self) -> None:
        for name, template in HISTORY_NUMBERS:
            phrase = template.format(getattr(ROLLER, name))
            self.assertIn(
                phrase,
                TEXTS["OPENING"],
                f"{name} 与开局流程.md 不一致，缺少：{phrase}",
            )

    def test_custom_tail_row_documented(self) -> None:
        self.assertIn("系统自拟", TEXTS["OPENING"])

    def test_realistic_aesthetics_match_character_rules(self) -> None:
        for aesthetic in ROLLER.REALISTIC_AESTHETICS:
            self.assertIn(f"「{aesthetic}」", TEXTS["CHARACTER"])

    def test_full_calibration_step_reference(self) -> None:
        self.assertIn("「每回合事务」第 10 步为准", TEXTS["SKILL"])
        self.assertNotIn("第 8 步为准", TEXTS["SKILL"])

    def test_save_version_handling_wording(self) -> None:
        self.assertIn("始终按载入存档处理", TEXTS["SKILL"])
        self.assertIn("只接受 `save_version: 3`", TEXTS["STATE"])
        self.assertNotIn("v2", TEXTS["STATE"])

    def test_setting_shell_is_documented_as_mapping(self) -> None:
        state = TEXTS["STATE"]
        self.assertIn("`setting_shell` 必须始终是四字段映射", state)
        for field in ("type", "place", "rule", "pressure"):
            self.assertIn(f"    {field}:", state)

    def test_pending_events_require_semantic_key_documented(self) -> None:
        self.assertIn("`pending` 事件必须携带非空 `semantic_key`", TEXTS["STATE"])

    def test_world_processing_order_is_subflow(self) -> None:
        self.assertIn("追算）的内部子流程", TEXTS["WORLD"])

    def test_command_turn_semantics_documented(self) -> None:
        text = TEXTS["SKILL"]
        self.assertIn("| 输入 | 行为 | 回合 |", text)
        rows = {
            "| 载入存档 / 续玩存档 |": "不推进",
            "| 解除暂停 / 恢复场景 |": "不推进",
            "| 冻结世界 / 恢复世界推演 |": "不推进",
            "| 继续 / 仅输入省略号 |": "推进",
            "| 快进到... |": "推进",
            "| 说骚话 / 别装了 / 做自己 |": "推进",
        }
        for prefix, expected in rows.items():
            line = next(l for l in text.splitlines() if l.startswith(prefix))
            cells = [c.strip() for c in line.split("|")]
            self.assertEqual(cells[-2], expected, f"{prefix} 的回合列语义与预期不符")

    def test_opening_confirm_and_event_field_sources(self) -> None:
        self.assertIn("已有进行中状态，输入“开局”先用一句话确认", TEXTS["SKILL"])
        self.assertIn("事件字段查询", TEXTS["SKILL"])
        self.assertIn("`references/世界运转.md` 为准", TEXTS["SKILL"])

    def test_retcon_turn_semantics_documented(self) -> None:
        self.assertIn("不附带新内容时按元指令处理", TEXTS["SKILL"])
        self.assertIn("Y 作为有效叙事指令推进一个回合", TEXTS["SKILL"])

    def test_character_doc_uses_current_identity_family_names(self) -> None:
        character_text = TEXTS["CHARACTER"]
        materials = ROLLER.load_materials(ROOT / "references")
        identity_families = {name for name, _ in materials["identity_base"]}
        for family in (
            "侍奉与身契",
            "成人行业与感官服务",
            "私密撮合与契约中介",
        ):
            self.assertIn(family, character_text)
            self.assertIn(family, identity_families)

    def test_character_doc_has_parser_maintenance_contract(self) -> None:
        character_text = TEXTS["CHARACTER"]
        self.assertIn("维护契约", character_text)
        self.assertIn("scripts/roll_opening.py", character_text)

    def test_character_parser_pools_are_nonempty(self) -> None:
        materials = ROLLER.load_materials(ROOT / "references")
        for key in ("flavors", "appearance", "speech", "decision_axes", "profile_weights", "supporting_functions"):
            with self.subTest(key=key):
                self.assertTrue(materials[key], f"解析池为空: {key}")


if __name__ == "__main__":
    unittest.main()
