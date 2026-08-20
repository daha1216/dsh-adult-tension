# 进度与基线

## 冻结段基线

`SKILL.md` 的「性行为场景写法（硬约束）」一节声明引言与 1-4 条写法标准、词汇表逐字冻结，改动前必须核对本文件的基线哈希。

- 文件：`SKILL.md`
- 冻结范围：自「当场景中已发生」起，至「不得用一句话跳过整段性行为。」止（含两者之间的空行；即该节引言段落与第 1-4 条全文，不含 `###` 标题与 HTML 注释行）。
- 基线哈希（SHA-256）：`1a4491449446b88cd1971234d17787e72e29f4f11e1252378a10cf8713ba526e`
- 建立日期：2026-08-14

校验命令（在 Skill 根目录运行）：

```powershell
$code = @'
import hashlib
text = open("SKILL.md", encoding="utf-8").read()
start = text.index("当场景中已发生")
end = text.index("不得用一句话跳过整段性行为。") + len("不得用一句话跳过整段性行为。")
print(hashlib.sha256(text[start:end].encode("utf-8")).hexdigest())
'@
$code | python -
```

规则：校验哈希与基线不一致时，冻结段已被改动。要么恢复原文，要么经明确记录后更新本基线哈希。

## 变更记录

| 日期 | 变更 |
|---|---|
| 2026-08-14 | 补齐缺失文件：`references/开局流程.md`、`references/素材库.md`、`scripts/roll_opening.py`、`PROGRESS.md`。统一旧存档策略为「不自动迁移、报错停载」（`SKILL.md` 失败处理与状态模型）。`directives[].block_code` 新增 `boundary_conflict`，同步 `SKILL.md`、`references/状态总结.md`、`scripts/validate_state.py` 与测试。新增可选扩展字段 `function`（NPC）与 `appellation`（player）并写入落点说明。`references/世界运转.md` 增补转折池解析契约。新增 `tests/test_roll_opening.py`（18 项）。 |
| 2026-08-17 | 统一 `save` / `opening` 校验 profile，绑定 `scene_id`、地点与参与者，补齐 `far_event_id`、事件 `source`/`due_at`、顶层关系唯一来源、`force_full` 生命周期、NPC `autonomy`、指令事件引用、命名审计、supporting 升级、开局步骤 6-9 及首次完整校准。`validate_state.py` 新增严格时间、场景许可、关系覆盖、事件、指令、checkpoint 与 opening C1-C14 可判定结构校验；`roll_opening.py` 新增 `opening-roll/v2`、严格素材维护检查、lock/custom 规则与默认历史去重。测试扩展至 45 项；`SKILL.md` 冻结段保持原哈希。 |
| 2026-08-20 | 新增多会话存档隔离与并发保护：`scripts/manage_saves.py` 提供存档槽位、manifest 元数据、revision/hash CAS、原子写入、共享槽租约与分支能力；`SKILL.md` 新增「存档隔离与并发」与存档槽/分支/共享命令；`references/状态总结.md` 更新存档布局与载入流程。新增 `tests/test_manage_saves.py`（6 项，并发写入一次成功一次冲突）；测试总数 51；`SKILL.md` 冻结段保持原哈希。 |
