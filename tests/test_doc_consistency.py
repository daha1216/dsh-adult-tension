from __future__ import annotations

import ast
import hashlib
import re
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

    def test_readme_material_examples_exist_in_corresponding_pools(self) -> None:
        pools = yaml.safe_load(read("scripts/data/pools.yaml"))
        characters = yaml.safe_load(read("scripts/data/character_pools.yaml"))
        meta = yaml.safe_load(read("scripts/data/character_meta.yaml"))
        twists = yaml.safe_load(read("scripts/data/twists.yaml"))
        power_labels = {
            "player_high": "玩家上位",
            "npc_high": "NPC 上位",
            "equal": "平等",
            "switchable": "动态切换",
        }
        sources = {
            "时代与地点": pools["时代与地点"]["时代"] + pools["时代与地点"]["地点"],
            "张力引擎": pools["张力引擎"],
            "压力来源": pools["压力来源"],
            "角色身份": pools["身份侧"],
            "角色处境": pools["处境侧"],
            "人物性格与反差": pools["反差轴"],
            "关系与权力": [power_labels[key] for key in pools["权力结构"]],
            "语言风格": [
                item
                for key in ("表层风味", "口癖")
                for group in characters[key].values()
                for item in group
            ],
            "场景动作": pools["场景动作"]["交易摊牌"] + pools["场景动作"]["非交易靠近"],
            "中期转折池": twists,
            "配角功能": meta["配角功能"],
        }
        table = read("README.md").split("| 内容 | 数量 | 示例 |", 1)[1].split("\n\n", 1)[0]
        checked = set()
        for line in table.splitlines():
            if not line.startswith("| ") or line.startswith("| ---"):
                continue
            label, _, examples = [cell.strip() for cell in line.strip("|").split("|")]
            self.assertIn(label, sources)
            checked.add(label)
            for example in re.split("、|或", examples.removesuffix("等")):
                with self.subTest(category=label, example=example):
                    self.assertIn(example, sources[label])
        self.assertEqual(set(sources), checked)

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

    def test_only_new_openings_require_three_headings_and_short_introductions(self) -> None:
        for path in ("SKILL.md", "README.md", "references/开局流程.md", "commands.yaml"):
            with self.subTest(path=path):
                document = read(path)
                for marker in ("仅新局", "世界观", "人物", "正文", "1-2 句"):
                    self.assertIn(marker, document, marker)
                self.assertNotIn("不强制标题", document)
                self.assertNotIn("不得强制标题", document)
        for path in ("SKILL.md", "README.md", "references/开局流程.md", "references/状态总结.md"):
            self.assertRegex(read(path), r"(?:载入与续玩|载入和普通回合|载入本身)[^\n]*不重复|不重复新局")

    def test_frozen_section_matches_exact_baseline_bytes(self) -> None:
        baseline = yaml.safe_load(read("maintenance/baseline.yaml"))["frozen_section"]
        raw = (ROOT / baseline["file"]).read_bytes()
        heading = baseline["heading"].encode("utf-8")
        self.assertEqual(1, raw.count(heading))
        start = raw.index(heading)
        end = raw.find(b"\n## ", start)
        section = raw[start:end if end >= 0 else len(raw)]
        self.assertEqual(baseline["sha256"], hashlib.sha256(section).hexdigest())

    def test_readme_framework_count_matches_authoring_and_runtime(self) -> None:
        index = yaml.safe_load(read("authoring/framework_index.yaml"))["frameworks"]
        runtime = yaml.safe_load((DATA / "world_frameworks.yaml").read_text(encoding="utf-8"))["frameworks"]
        baseline = yaml.safe_load(read("maintenance/baseline.yaml"))["framework_selection"]
        self.assertEqual(baseline["retained_count"], len(index))
        self.assertEqual({row["name"] for row in index}, set(runtime))
        self.assertIn(f"{len(index)} 个世界框架", read("README.md"))

    def test_runtime_docs_bind_sessions_and_keep_legacy_paths_explicit(self) -> None:
        paths = ("SKILL.md", "README.md", "saves/README.md", "references/状态总结.md",
                 "references/运行状态速览.md", "references/开局流程.md", "commands.yaml")
        for path in paths:
            with self.subTest(path=path):
                document = read(path)
                for marker in ("saves/sessions/", "state_path", "state_token"):
                    self.assertIn(marker, document, marker)
                for obsolete in ("默认 `--state` 指向它", "current_state.yaml` 是本会话工作活档",
                                 "产物写到两处", "无名称存档默认写 main"):
                    self.assertNotIn(obsolete, document)
                for line in document.splitlines():
                    if "saves/current_state.yaml" in line:
                        self.assertIn("--state", line, line)
        for path in ("SKILL.md", "references/状态总结.md", "references/运行状态速览.md", "commands.yaml"):
            document = read(path)
            self.assertIn("--expected-state-token", document)
            self.assertIn("锁内", document)
            self.assertIn("过期", document)

    def test_opening_failure_does_not_pollute_history_contract(self) -> None:
        for path in ("SKILL.md", "README.md", "references/开局流程.md", "commands.yaml"):
            document = read(path)
            self.assertRegex(document, r"(?:写入失败|状态写入失败)不污染(?:开局)?历史")
            self.assertIn("输出已存在", document)
        maintenance = read("references/加内容.md")
        self.assertIn("成功仍会追加历史", maintenance)
        self.assertIn("sample_materials.py", maintenance)

    def test_terminal_receipts_are_retained_and_targeted_without_full_dump(self) -> None:
        for path in ("SKILL.md", "README.md", "references/世界运转.md", "references/状态总结.md",
                     "references/运行状态速览.md", "commands.yaml"):
            with self.subTest(path=path):
                document = read(path)
                for marker in ("event_changes", "outcome", "--event", "终态", "保留"):
                    self.assertIn(marker, document, marker)
                self.assertNotIn("才可移出队列", document)
        quick = read("references/运行状态速览.md")
        for marker in ("10 条", "省略提示", "未知 ID", "不改变普通上限", "resolved_turn"):
            self.assertIn(marker, quick)

    def test_named_slot_load_uses_same_snapshot_and_keeps_schema_entry(self) -> None:
        document = read("references/状态总结.md")
        for marker in ("## 存档格式 v3", "## 载入流程", "SaveStore.load_slot", "同一字节快照",
                       "--expected-updated-at", "state_sha256", "有效文件对", "初始化失败"):
            self.assertIn(marker, document, marker)
        self.assertRegex(document, r"CLI[^\n]*只输出 manifest|CLI[^\n]*只返回 manifest")
        commands = yaml.safe_load(read("commands.yaml"))
        self.assertIn("runtime_binding", commands)
        self.assertIn("SaveStore.load_slot", commands["slot_binding"])
        core = {row["canonical"]: row for row in commands["command_categories"]["core"]["commands"]}
        self.assertIn("<state_path>", core["存档"]["cli"])
        self.assertIn("--session", core["状态"]["cli"])

    def test_maintenance_workflow_matches_cli_flags(self) -> None:
        flags = ("--changed", "--full", "--framework", "--material", "--release", "--update-fingerprint")
        tree = ast.parse(read("scripts/qa.py"))
        accepted = {arg.value for node in ast.walk(tree) if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument"
                    for arg in node.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)}
        self.assertTrue(set(flags) <= accepted)
        for path in ("README.md", "references/加内容.md", "references/素材架构.md"):
            document = read(path)
            for flag in flags:
                self.assertIn(flag, document, (path, flag))
            commands = re.findall(r"^python(?: -X utf8)? scripts/(\S+)(.*)$", document, re.MULTILINE)
            ordered = [name for name, args in commands if "--write" in args or name == "qa.py"]
            self.assertLess(ordered.index("build_frameworks.py"), ordered.index("sync_governance.py"))
            self.assertLess(ordered.index("sync_governance.py"), ordered.index("qa.py"))

    def test_maintenance_authorities_and_content_levels_are_documented(self) -> None:
        for path in ("README.md", "references/加内容.md", "references/素材架构.md"):
            document = read(path)
            for marker in ("authoring/frameworks/", "maintenance/data_manifest.yaml",
                           "maintenance/core_review_decisions.yaml", "maintenance/framework_reviews/",
                           "maintenance/baseline.yaml"):
                self.assertIn(marker, document, (path, marker))
        document = read("references/加内容.md")
        for level in ("L0", "L1", "L2", "L3"):
            self.assertRegex(document, rf"\| {level}[^\n]+\|")
        for marker in ("verified_direct", "regression_evidence", "source_hash", "history"):
            self.assertIn(marker, document)

    def test_auto_requires_current_reviews_without_implicit_legacy(self) -> None:
        for path in ("README.md", "SKILL.md", "references/开局流程.md", "references/加内容.md",
                     "references/素材架构.md", "commands.yaml"):
            document = read(path).replace("`", "")
            self.assertRegex(document, r"(?:无|不)隐式", path)
            self.assertIn("legacy", document, path)
            self.assertRegex(document, r"(?:审查|review)[^\n]*(?:有效|哈希)|哈希[^\n]*审查")

    def test_playtest_is_explicit_quota_use_and_separate_evidence_gate(self) -> None:
        baseline = yaml.safe_load(read("maintenance/baseline.yaml"))
        config = baseline["playtest"]
        required = baseline["framework_selection"]["retained_count"] * len(config["modes"]) * (config["continuation_turns"] + 1)
        self.assertEqual(config["minimum_model_responses"], required)
        for path in ("README.md", "references/加内容.md", "references/素材架构.md"):
            document = read(path)
            for marker in ("DeepSeek Harness", str(required), "结构通过不等于语义通过", "独立评分",
                           "playtest_report.py", "run_playtest.py", "显式调用", "模型额度", "默认 QA 不会自动"):
                self.assertIn(marker, document, (path, marker))

    def test_stale_reports_and_removed_reviews_are_not_current_authority(self) -> None:
        for path in ("PROGRESS.md", "references/素材整理报告.md"):
            lead = read(path)[:1200]
            self.assertIn("已过时", lead)
            self.assertIn("320", lead)
        maintenance = read("references/加内容.md")
        for marker in ("references/governance_decisions.yaml", "10 份历史 review", "已删除", "git", "history"):
            self.assertIn(marker, maintenance)
        self.assertNotRegex(maintenance, r"--decisions\s+references/governance_decisions\.yaml")

    def test_naming_is_not_limited_to_modern_names(self) -> None:
        for path in ("README.md", "SKILL.md", "references/角色设计.md", "references/开局流程.md"):
            self.assertIn("不局限现代", read(path), path)

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
