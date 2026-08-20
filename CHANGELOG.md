# Changelog

## 2026-08-21

- **存档简化为三命令**：`存档` / `载入` / `列出存档`（+`保存 X` / `载入 X` / `快速保存 qs`）。`scripts/manage_saves.py` 删除共享模式、租约、revision/hash CAS 与分支，改为 `updated_at` 冲突检测 + 原子写入；`SKILL.md` 删除「存档隔离与并发」整节，冲突提示保留为用户友好的三选项。
- **删除指令契约系统**：「玩家叙事主权」改为结果档 / 尝试档 / 改写档三档规则；「每回合事务」12 步重构为解析 / 候选 / 校验 / 提交 / 输出 5 步，轻量与完整校准合并为「提交前校验 + 每 5 回合 / force 深度校准」。`validate_state.py` 移除指令契约校验（`directive` 事件源与 `directives` 字段仅作旧档兼容保留）。
- **统一回合计数**：开局提交点即回合 1，删除「内部回合 0」概念（骨架、opening 校验、C15、存档模板与 fixture 同步迁移）。
- **体验与文档**：`SKILL.md` 新增「文档结构」分层与「语态调度」三层分离（台词语态 / 叙述层 / 身体反应），退化规则简化，年龄检查改为开局与新角色加入时执行；新增 `requirements.txt`（PyYAML，Python 3.10+）。
- 测试 63 项全绿；既有存档全部通过 `save` 校验；`SKILL.md` 冻结段哈希保持不变。

## 2026-08-20

- 新增多会话存档隔离与并发保护：`scripts/manage_saves.py` 支持存档槽位、manifest 元数据、revision/hash CAS、原子写入、共享槽租约与分支能力。
- `SKILL.md` 新增「存档隔离与并发」时段及存档槽 / 分支 / 共享存档命令；`references/状态总结.md` 更新存档布局与载入流程。
- 新增 `tests/test_manage_saves.py`，覆盖并发写入冲突、共享租约、分支与访问模式切换；测试总数 51。

## 2026-08-19

- 从 `erotic-game-engine--` 仓库拆分独立，完整保留 `adult-tension-narrative` 的历史提交。
- 仓库根目录即技能本体，新增独立 README / CONTRIBUTING / CI。
