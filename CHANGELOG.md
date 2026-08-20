# Changelog

## 2026-08-20

- 新增多会话存档隔离与并发保护：`scripts/manage_saves.py` 支持存档槽位、manifest 元数据、revision/hash CAS、原子写入、共享槽租约与分支能力。
- `SKILL.md` 新增「存档隔离与并发」时段及存档槽 / 分支 / 共享存档命令；`references/状态总结.md` 更新存档布局与载入流程。
- 新增 `tests/test_manage_saves.py`，覆盖并发写入冲突、共享租约、分支与访问模式切换；测试总数 51。

## 2026-08-19

- 从 `erotic-game-engine--` 仓库拆分独立，完整保留 `adult-tension-narrative` 的历史提交。
- 仓库根目录即技能本体，新增独立 README / CONTRIBUTING / CI。
