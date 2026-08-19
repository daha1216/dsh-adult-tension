# 维护指南

本仓库只包含 `adult-tension-narrative` 一个技能。一次改动应明确属于技能本体、脚本工具，或仓库级维护。

## 修改原则

1. `SKILL.md` 只保留执行时必须加载的入口规则，详细规范和长示例放入 `references/`。
2. 不要在两个文件中维护互相竞争的字段定义；确定一个唯一来源，其他位置使用链接或职责指针。
3. 修改 `references/素材库.md` 中可被脚本读取的标题、列表或字段时，同步检查 `scripts/roll_opening.py` 和相关测试。
4. 修改 v3 存档字段时，同步检查 `references/状态总结.md`、`scripts/validate_state.py` 和 `tests/test_validate_state.py`。
5. 不提交本地历史、Python 缓存、测试缓存或临时生成文件。

## 提交前检查

在仓库根目录运行：

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q scripts tests
python scripts/roll_opening.py --seed 1 --no-history
git diff --check
```

提交信息建议使用简短的动作前缀，例如 `docs:`、`fix:`、`feat:`、`test:` 或 `chore:`。
