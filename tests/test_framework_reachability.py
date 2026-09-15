"""O2 反向可达门禁：每个 activity / place / pair 都必须被至少一条压力绑定提及。

check_frameworks 里有两组方向相反的校验：
  正向（原有）：每个 place / pair 至少有一个 activity 入口；
  反向（本次新增）：每个 activity / place / pair 至少被一条 pressure binding 提及。
反向缺失正是死料的成因——运行时 world_frameworks.pressure_allows 要求
(activity, place, pair) 三元组精确命中 pressure["bindings"]，因此一个没有任何
压力认领的三元组永远抽不到，它独占的 place / pair 也随之死掉。

这里用最小合成 registry 分别验证：合法框架通过；缺 activity / place / pair 绑定时
各自报出对应的中文错误。
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


def _load(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CF = _load("check_frameworks_gate", "scripts/check_frameworks.py")


class _Report:
    """Minimal stand-in for the real report object: collects errors and counts checks."""

    def __init__(self):
        self.errors: list[str] = []
        self.checks = 0

    def error(self, message: str) -> None:
        self.errors.append(message)


def _beats(text: str) -> dict:
    return {
        "trigger": text,
        "objective": text,
        "choice": text,
        "immediate": text,
        "near": text,
    }


def _pair() -> dict:
    return {
        "family": "测试身份族",
        "position": "独居",
        "appellations": ["测试称谓"],
        "relationship_reason": "测试理由",
        "npc": {
            "role": "测试角色",
            "function": "测试功能",
            "authority": "测试权限",
            "resource": "测试资源",
            "limitation": "测试限制",
            "obligation": "测试义务",
            "exposure": "测试暴露",
        },
        "player": {
            "identity": "测试玩家身份",
            "baseline": "测试基线",
            "reputation": "测试名声",
            "resources": ["测试资源"],
        },
    }


def _place(name: str) -> tuple:
    return name, {
        "details": ["测试细节"],
        "profile": {
            "privacy": "medium",
            "visibility": "low",
            "exits": ["测试出口"],
            "witnesses": ["测试目击者"],
            "affordances": ["测试可做之事"],
            "pressure_modifiers": ["测试修正"],
        },
    }


def _activity(places: list, pairs: list) -> dict:
    return {
        "places": places,
        "pairs": pairs,
        "category": "测试分类",
        "action": "测试动作",
        "beats": _beats("测试活动节拍"),
    }


def _pressure(bindings: list) -> dict:
    return {
        "source": "测试压力来源",
        "engines": ["时限逼近", "资源锁定"],
        "beats": _beats("测试压力节拍"),
        "far_trigger": "测试远期触发",
        "far_consequence": "测试远期后果",
        "exits": ["测试退出方式"],
        "bindings": bindings,
    }


def _framework(activities: dict, pressures: dict, places: list, pairs: int) -> dict:
    package = {
        "eras": ["当代都市"],
        "aesthetics": ["都市日常"],
        "rule": "测试规则",
        "social_rule": "测试社会规则",
        "themes": ["测试主题"],
        "technology_boundary": "测试技术边界",
        "bridge_status": "not_required",
        "customs": ["测试习俗"],
        "places": dict(_place(p) for p in places),
        "pairs": [_pair() for _ in range(pairs)],
        "activities": activities,
        "pressures": pressures,
    }
    return {"version": 1, "frameworks": {"测试框架": package}}


POOLS = {"时代与地点": {"时代": ["当代都市"]}, "美学基调": ["都市日常"], "张力引擎": ["时限逼近", "资源锁定"], "玩家化身轴": {"社会位置": ["独居"], "称谓": ["测试称谓"]}}
IDENTITY = {"测试身份族": {}}


def _run(registry: dict) -> _Report:
    report = _Report()
    CF.check_frameworks(registry, POOLS, {"测试分类": []}, IDENTITY, report)
    return report


class ReverseReachabilityTests(unittest.TestCase):
    def test_valid_framework_passes(self) -> None:
        """每个 activity / place / pair 都有压力绑定 -> 无错。"""
        reg = _framework(
            activities={"测试活动甲": _activity(["测试地点甲"], [0]),
                        "测试活动乙": _activity(["测试地点乙"], [1])},
            pressures={
                "压力甲": _pressure([{"activity": "测试活动甲", "place": "测试地点甲", "pair": 0}]),
                "压力乙": _pressure([{"activity": "测试活动乙", "place": "测试地点乙", "pair": 1}]),
            },
            places=["测试地点甲", "测试地点乙"],
            pairs=2,
        )
        report = _run(reg)
        self.assertEqual([], report.errors, "；".join(report.errors))

    def test_activity_without_binding_is_reported(self) -> None:
        """测试活动乙 没有任何压力绑定 -> 报「存在没有压力绑定的活动」。"""
        reg = _framework(
            activities={"测试活动甲": _activity(["测试地点甲"], [0]),
                        "测试活动乙": _activity(["测试地点乙"], [1])},
            pressures={"压力甲": _pressure([{"activity": "测试活动甲", "place": "测试地点甲", "pair": 0}])},
            places=["测试地点甲", "测试地点乙"],
            pairs=2,
        )
        report = _run(reg)
        self.assertTrue(any("存在没有压力绑定的活动" in e for e in report.errors), report.errors)

    def test_place_without_binding_is_reported(self) -> None:
        """测试地点乙 只被无绑定的活动引用 -> 报「存在没有压力绑定的地点」。"""
        reg = _framework(
            activities={"测试活动甲": _activity(["测试地点甲"], [0]),
                        "测试活动乙": _activity(["测试地点乙"], [1])},
            pressures={"压力甲": _pressure([{"activity": "测试活动甲", "place": "测试地点甲", "pair": 0}]),
                       "压力乙": _pressure([{"activity": "测试活动乙", "place": "测试地点甲", "pair": 1}])},
            places=["测试地点甲", "测试地点乙"],
            pairs=2,
        )
        report = _run(reg)
        self.assertTrue(any("存在没有压力绑定的地点" in e for e in report.errors), report.errors)

    def test_pair_without_binding_is_reported(self) -> None:
        """人物搭配索引 1 从未出现在任何绑定里 -> 报「存在没有压力绑定的人物搭配」。"""
        reg = _framework(
            activities={"测试活动甲": _activity(["测试地点甲"], [0])},
            pressures={"压力甲": _pressure([{"activity": "测试活动甲", "place": "测试地点甲", "pair": 0}])},
            places=["测试地点甲"],
            pairs=2,
        )
        report = _run(reg)
        self.assertTrue(any("存在没有压力绑定的人物搭配" in e for e in report.errors), report.errors)

    def test_real_registry_has_no_dead_material(self) -> None:
        """真实聚合数据经反向门禁后应无死料错误。"""
        report = _run(yaml.safe_load((ROOT / "scripts" / "data" / "world_frameworks.yaml").read_text(encoding="utf-8")))
        dead = [e for e in report.errors if "没有压力绑定" in e]
        self.assertEqual([], dead, "；".join(dead))


if __name__ == "__main__":
    unittest.main()
