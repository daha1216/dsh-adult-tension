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
| 2026-08-21 | 按体验审阅全部修复：①`roll_opening.py` 张力引擎 lock 支持单值自动补抽/双值锁定，杜绝单引擎违反「两项互不相同」，重复/超量/表外值拒绝；②`validate_state.py` 的 `directive_priority_preserved` 改为仅存在指令时必填，与 `references/状态总结.md` 一致；③根目录残留开局样例 `opening_*.yaml`（turn 6 存档）归入 `saves/legacy/`；④新增 `scripts/build_opening.py` 开局编排器（结构骰→v3 骨架→`--check` 待填清单→`opening_request`），`references/开局流程.md` 新增「开局编排」；⑤`SKILL.md`/`saves/README.md` 补充会话绑定与自然语言存档命令映射、租约续期规则；⑥「玩家叙事主权」第 2 条澄清行动句解释（依赖外部条件/对方响应的动作先发生、由世界判定，除非锁定措辞）；⑦「完整开局」规定一次回复完成、不输出中间态；⑧明确 `attraction.orientation` 为唯一表末自拟位；⑨新增 `tests/test_build_opening.py`（骨架/填充/CLI/槽位端到端/fixtures 回归）与张力引擎 lock、checkpoint 条件用例，测试 66 项全绿；`SKILL.md` 冻结段保持原哈希。 |
| 2026-08-21 | 按体验审阅优化方案二次修复：①删除指令契约系统——`SKILL.md`「玩家叙事主权」改为结果档/尝试档/改写档三档规则，「每回合事务」12 步重构为解析/候选/校验/提交/输出 5 步并合并轻量与完整校准为「提交前校验 + 每 5 回合/force 深度校准」；`validate_state.py` 移除 `validate_directives` 与 `directive_priority_preserved`，`directive` 事件源与 `directives` 字段仅作兼容保留；②统一回合计数——开局提交点即回合 1（`build_opening.py` 骨架、`validate_state.py` opening profile、C15、模板、fixture `saves/_opening_zhao.yaml` 全部迁移，删除「内部回合 0」概念）；③存档简化为三命令（存档/载入/列出存档 + `保存 X`/`载入 X`/qs）——`manage_saves.py` 删除共享模式、租约、revision/hash CAS 与分支，改为 `updated_at` 冲突检测；`SKILL.md` 删除「存档隔离与并发」整节；`commands.yaml`/`saves/README.md`/`references/状态总结.md`/`P0优化说明.md`/`quickstart.md`/`优化实施总结.md` 同步；④新增 `requirements.txt`（PyYAML，Python 3.10+）；⑤`SKILL.md` 新增「文档结构」分层（执行主控与领域规则、玩家可见与后台机制分离）、「语态调度」明确台词语态/叙述层/身体反应三层分离、退化规则简化、年龄检查改为开局与新角色加入时执行；⑥测试 63 项全绿（去掉 3 项指令契约用例、新增旧档兼容与冲突检测用例），既有 4 槽位存档全部通过 `save` 校验；`SKILL.md` 冻结段保持原哈希 `1a449144…`。 |
| 2026-08-21 | 按玩家实测方案修复（性行为写法冻结段不动）：结构骰升 `opening-roll/v3`，防塌缩（杠杆引擎不叠、player_high 不配把柄处境、场景动作默认非交易靠近、身份族加权、玩家化身轴）；开局三行进度 +【此刻】HUD；存档人话确认、中文槽名、`导出存档` 才打 YAML；新局禁止 `directives`；亲密动作默认尝试档且锁不住同意；时钟必须走、离场最小追算、相邻私密空间许可可继承；开关类命令不推进回合；作废 P0/响应时间/叙事助手/实施总结纸面文档。 |
