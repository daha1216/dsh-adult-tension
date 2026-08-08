# 变更记录

## 2026-08-09 一致性修复收尾

- `scripts/validate_state.py`：supporting 配角可省略五项表现字段；字段存在时仍校验字符串类型；main 与 important_supporting 保持严格要求。pending 事件现在必须有非空 `semantic_key`，resolved/cancelled 事件保持兼容。
- `references/角色设计.md`、`references/状态总结.md`：同步分层持久化规则；角色设计增加实时解析维护契约。
- `SKILL.md`：明确纯撤销与替换式 retcon 的回合语义。
- `references/素材库.md`、`.gitignore`：修复引号并忽略 pytest 缓存目录。
- `tests/`：补充 supporting 最小字段、错误类型、解析池非空、retcon 文档和事件语义键测试。

## 2026-08-09 状态总结收敛

- `references/状态总结.md`：删除 v2 迁移说明，统一为仅接受 v3；新增字段枚举速查表、时间关系、`resolved_summary` 与 checkpoint 语义说明；保存检查收敛为人工语义约束并明确以 `validate_state.py` 为机器校验唯一来源。
- `scripts/validate_state.py`：`world.setting_shell` 强制使用 `type/place/rule/pressure` 四字段映射，不再接受一句话字符串。
- `SKILL.md`、`references/世界运转.md`：同步载入与历史压缩的职责指向。
- `tests/`：更新有效存档夹具并覆盖字符串形式 `setting_shell` 的反向失败。

## 2026-08-09 素材库重构收尾

- `references/素材库.md`：补维护契约注释，明确现实档排除与兼容档位的职责边界；张力引擎新增「名分与承认」「环境与准入」分组；身份侧把过宽族拆成 `创作与传统演艺` / `二次元与同人` / `电竞与直播` 与 `成人行业与感官服务` / `私密撮合与契约中介`。
- `references/角色设计.md`：同步三类成人相关身份族的区分口径，避免继续引用旧族名。
- `tests/test_roll_opening.py`：更新引擎总项数、基础身份族数和三档身份池尺寸基线；新增新分组与旧族名退场断言。
- `tests/test_doc_consistency.py`：把 `创作与演艺`、`成人行业与私密服务` 纳入遗留词门禁，并校验角色设计引用的是当前身份族命名。

## 2026-08-08 一致性与校验加固

- `SKILL.md`：删除与 `references/开局流程.md` 重复的 1-14 步清单，后者成为步骤名称、规则与产出的唯一来源；新增「帮助 / 命令 / 能做什么」元指令及人话输出约定。
- `scripts/validate_state.py`：要求 `world.constants` 至少包含一项世界常量；同意记录的参与者除须为已知角色外，还必须出现在 `current_node.participants` 中。
- `scripts/roll_opening.py`：美学基调为「青年漫写实」或「写实文学」时，主 NPC 与配角的表层风味、口癖统一输出 `—`；其他美学保持原抽样行为。
- `references/角色设计.md`：把原有“写实或文学向可跳过”收敛为上述两个精确枚举值，与脚本行为一致。
- `tests/`：新增冻结段哈希门禁、开局历史数值与系统自拟末位文档一致性、帮助命令、写实美学枚举、世界常量非空、同意参与者在场及写实/非写实抽样行为测试。
- 本地目录原 Git 元数据不可用；重新初始化仓库并先提交导入基线，再提交本轮优化，保留可审阅的前后差异。

## 2026-08-08 语态调度与内心可见

- `SKILL.md`：「输出规范」在冻结段**之前**新增三节——「语态调度」（亲密线角色维护表层/里层两档语态，玩家明确要求或情绪、酒意、快感累积、关系深化时切入里层，深化后可自主切回；语态只约束台词，叙述层与生理细节仍按性写法硬约束全额执行）、「失控语言退化」（按当前激活语态分档退化：表层态句碎而词仍雅，里层态词粗而句渐短，对所有角色生效）、「内心可见（可选，玩家开启）」（默认关闭，开启后叙述层可展现 NPC 未表露的念头与生理真实，但可作为行动依据的信息必须先经言行表露）。
- `SKILL.md`：「NPC 决策」在条目列表后补一段——叙述层展示内心不改变该 NPC 的信息集，自主语态切换计入第 6 条冷却；未改动原有 1-7 条编号。
- `SKILL.md`：命令表新增「说骚话 / 别装了 / 做自己」（有效叙事指令，推进回合）、「贴视角 / 偷窥视角」与「退出偷窥 / 收回视角」（元指令，不推进回合）。
- `references/角色设计.md`：9f 增列双语态要求；新增「表里双语态」小节，规定两档语态与切换触发的生成方式，并声明不改人格、目标、底线、画像或当前许可。
- `references/状态总结.md`：新增「叙事表现类可选扩展字段」小节，登记 NPC 的 `active_voice_mode`（`surface|inner`，缺失按 `surface`）与 `meta.voyeur_pov`（`on|off`，缺失按 `off`）；存档模板加对应注释。两者均为可选扩展，不进入 v3 核心 schema。
- 冻结段（性行为场景写法硬约束）逐字未改，改动前后 SHA-256 一致；`scripts/validate_state.py` 与 `tests/` 未改动，94 项测试与 31 项子测试全部通过，带新扩展字段的存档校验零错误。

## 2026-07-31 一致性修复

- `SKILL.md`：不变量新增第 5 条（亲密内容仅在 `safety_state` 为 running 时书写）；玩家叙事主权 #6 将 paused 安全状态纳入 `blocked` 条件；命令表补「查看状态」行；输出规范去除与命令表重复的三行行为规则，改为只补充输出格式；修正完整校准触发引用（第 8 步 → 第 10 步）；统一「包含顶层 `save_version` 的输入按载入存档处理」措辞；冻结段上方加冻结标记注释。
- `references/世界运转.md`：声明「处理顺序」是 `SKILL.md` 每回合事务第 4 步（追算）的子流程。
- `tests/test_doc_consistency.py`：新增文档与校验脚本常量一致性测试。
- `tests/test_validate_state.py`：清理 `valid_save()` 夹具中已删除的 `boundaries_verified` / `consent_verified` 字段。

## 2026-07-28 删除同意类不变量

- 删除 `SKILL.md` 不变量 #3（NPC 底线与当前同意）与 #4（亲密升级前确认同意）；blocked 码收敛为 `adult_requirement|safety_paused`，同步清理 `references/状态总结.md`、`scripts/validate_state.py` 和相关引用文件。
