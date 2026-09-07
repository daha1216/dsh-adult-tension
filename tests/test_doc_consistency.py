from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
DATA = ROOT / "scripts" / "data"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class DocumentationConsistencyTests(unittest.TestCase):
    def test_readme_material_counts_match_data(self) -> None:
        pools = yaml.safe_load((DATA / "pools.yaml").read_text(encoding="utf-8"))
        identities = yaml.safe_load((DATA / "identities.yaml").read_text(encoding="utf-8"))
        twists = yaml.safe_load((DATA / "twists.yaml").read_text(encoding="utf-8"))

        readme = read("README.md")
        markers = (
            f"时代 {len(pools['时代与地点']['时代'])} · 地点 {len(pools['时代与地点']['地点'])}",
            f"压力来源 | {len(pools['压力来源'])} 条",
            f"角色处境 | {len(pools['处境侧'])} 条",
            f"非交易靠近 {len(pools['场景动作']['非交易靠近'])}",
            f"共 {sum(len(items) for items in twists.values())} 条",
            f"NPC 17 族 {sum(len(items) for items in identities['npc'].values())} 身份",
        )
        for marker in markers:
            self.assertIn(marker, readme, marker)

    def test_runtime_data_files_are_documented(self) -> None:
        opening = read("references/开局流程.md")
        maintenance = read("references/加内容.md")
        for name in (
            "location_profiles.yaml",
            "action_categories.yaml",
            "action_metadata.yaml",
            "identity_profiles.yaml",
            "twist_profiles.yaml",
        ):
            self.assertIn(name, opening, name)
            self.assertIn(name, maintenance, name)

        role_doc = read("references/角色设计.md")
        self.assertIn("identity_profiles.yaml", role_doc)
        self.assertIn("behavior:", role_doc)

    def test_active_opening_docs_do_not_require_fixed_three_blocks(self) -> None:
        docs = (read("SKILL.md"), read("references/开局流程.md"), read("scripts/build_opening.py"))
        obsolete = ("写三段开局正文", "写三块正文", "三段开局正文")
        for text in obsolete:
            for document in docs:
                self.assertNotIn(text, document, text)

    def test_state_doc_matches_non_persistent_consent_model(self) -> None:
        state = read("references/状态总结.md")
        self.assertNotIn("consent.grants[].status", state)
        self.assertNotIn("当前场景的同意记录", state)
        self.assertEqual(1, state.count("| `meta.safety_state` |"))
        self.assertIn("当前互动判断不作为同意记录持久化", state)

    def test_runtime_slice_reading_contract_is_documented(self) -> None:
        skill = read("SKILL.md")
        quick = read("references/运行状态速览.md")
        self.assertIn("references/运行状态速览.md", skill)
        for marker in (
            "current_node.situation",
            "npcs[].situation",
            "pending",
            "resolved` / `cancelled",
            "checked_turns",
            "checkpoint",
        ):
            self.assertIn(marker, quick, marker)

    def test_skill_sections_have_current_boundaries(self) -> None:
        text = read("SKILL.md")
        self.assertIn("### 语态调度", text)
        self.assertNotIn("### 失控语言退化", text)
        self.assertIn("### 内心可见（可选，玩家开启）", text)
        self.assertIn("### 性行为场景写法（硬约束）", text)
        self.assertNotIn("词分三层使用", text)
        self.assertNotIn("每段性行为按五拍写清", text)

    def test_skill_runtime_contract_has_single_authority_and_current_terms(self) -> None:
        text = read("SKILL.md")
        self.assertIn("## 运行优先级", text)
        self.assertIn("权威来源只有一份", text)
        self.assertIn("当前互动判断、明确反应、撤回信号", text)
        self.assertNotIn("场景同意", text)
        self.assertNotIn("配合档位", text)
        self.assertNotIn("不重写 YAML", text)
        self.assertIn("禁止直接覆盖整份 `state.yaml`", text)


if __name__ == "__main__":
    unittest.main()
