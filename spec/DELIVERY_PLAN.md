# 交付计划

从空仓库到发布，按什么顺序做，每一步拿什么证明做完了。阶段内部怎么做由实现者决定；顺序上只有两条硬要求（`AGENTS.md`）：

1. **先有能被真实宿主加载的 Skill 外壳，再做玩法。**
2. **先用一个世界打通全链路，再加世界。**

**每个阶段结束时都要做：**

- 跑本阶段相关的测试，再跑一次 `ACCEPTANCE.md` §1 的前 7 条命令。阶段 0 只跑其中已经存在的，从阶段 1 起 7 条都必须跑通。
- 跑一次 `benchmark`，把数字写进 `PROGRESS.md`。任何一项超过 `ACCEPTANCE.md` §4 的门槛，先解决，再进入下一阶段。性能问题不留到最后。
- `validate_skill` 通过。`SKILL.md` 只描述已经实现的能力；`references/` 与代码一致。
- 本阶段的改动全部提交，工作区干净；`PROGRESS.md` 记下对应的提交号。
- 更新 `PROGRESS.md`（见文末“执行纪律”）。

## 阶段 0：仓库与 Skill 外壳

**目标**：一个能被真实宿主发现、加载并完成自检的空壳 Skill。

- 新建空仓库。本蓝图（不含 `REVIEW.md`，也不含任何旧项目副本）原样放在 `spec/`，视为只读。根目录的 `AGENTS.md`（以及宿主需要的同类说明文件，例如 Claude Code 读的 `CLAUDE.md`，它可以直接导入 `@spec/AGENTS.md`）只写一句：先读 `spec/AGENTS.md`。用户在仓库根目录另外放的本机环境说明一并遵守，不要删改。
- `.gitattributes` 强制 LF；CI 在 Windows 与 Linux 上运行。
- 按 `ARCHITECTURE.md` §2 建目录。`skill/adult-tension/` 里有：由 `SKILL_TEMPLATE.md` 改写的 `SKILL.md`（先只写已经能用的部分）、入口脚本、运行时包骨架、空的内容目录。
- 入口脚本：版本检查（`RUNTIME_UNSUPPORTED`）、信封、UTF-8 输出、`--input-file` 与 stdin、退出码。
- 数据目录定位与初始化、`doctor`（含快速路径）、`version`。
- `tools/validate_skill.py`。
- `tools/benchmark.py` 的骨架：先测 `doctor` 与 `version` 的冷进程耗时，之后每个阶段往里加新路径。

**退出证据**：

- `doctor` 在三种情况下的输出：全新数据目录、不可写目录、已初始化目录。
- 用 Python 3.8 或 3.9 运行入口脚本，得到 `RUNTIME_UNSUPPORTED`。没有旧解释器时，用测试模拟并在 `PROGRESS.md` 注明。
- 把 Skill 目录装进一个真实宿主，在新对话里说“看看 Adult Tension 能不能用”。宿主发现 Skill 并调用了 `doctor`。保存记录。

**不做**：任何玩法。

## 阶段 1：单世界垂直切片

**目标**：一个世界、两种模式，能开局、推进、存读档，全程只经过唯一写路径。

- 选一个世界，按 `CONTENT_BIBLE.md` §3 的下限写完整。建议港口夜班，`DATA_CONTRACTS.md` §8.1 的示例就是它的一部分。
- 内容编译器；`verify-content` 的结构检查与年龄检查。
- 领域核心：会话、角色（含年龄检查）、关系三条线、事实、事件的基本生命周期、确定性随机。
- 操作：`advance_time`、`move`、`enter_scene` / `exit_scene`、`npc_response`、`npc_action`（含冷却）、`npc_state`、`add_fact`、`relationship`、`event_create` / `event_resolve`、`roll`、`player_update`。
- 命令：`new-game`（日常与压力，含锁定、排除、种子复现与近期去重）、`get-context`（简要）、`commit-turn`、`save-slot`、`load-slot`、`list-slots`、`list-worlds`、`smoke`。
- 写路径：形状校验 → 幂等 → revision → 在工作副本上应用 → 单个事务 → 投影（`ARCHITECTURE.md` §3）。

**退出证据**：

- `ACCEPTANCE.md` §2 的“事务与幂等”全部有测试并通过。
- 固定种子下两种模式各开局 10 次，全部通过结构校验。
- 一段 20 回合的脚本化运行：每次都用冷进程 CLI，中途存档，读档后续跑。最终状态摘要与不中断的路线一致。
- 进程内的开局与提交耗时已经低于 `ACCEPTANCE.md` §4 的门槛。
- 第一次真实宿主试玩：开局 + 10 回合（含“继续”和一次会被 NPC 拒绝的尝试）+ 存档 + 新对话读档。记录原样保存，发现的问题写进 `PROGRESS.md`。

**不做**：其余世界、离屏推演、转折、撤销。

## 阶段 2：人物、知识、关系与安全

- 知识边界：`reveal_fact`、`spread_rumor`、误信、内心事实。
- 表层与里层语态、内心可见、倾向卡与证据、关系阶段与证据。
- 把柄记录（`DATA_CONTRACTS.md` §5.3）与亲密提交的结构检查。
- 新角色登场与升格：`introduce_character`、`promote_character`；登场同样做年龄检查。
- 硬边界、暂停与“换个场景”；场景切换后清空互动判断。
- 行动模式的结构约束：`attempt` 必须有 NPC 回应；`continue` 与 `wait` 不替玩家行动。
- 命令：`set-boundary`、`set-safety`、`set-preferences`、`status`（简要与状态+）。
- 人物命名、性别与配对偏好、玩家设定、人称（D15；`NARRATIVE_RULES.md` §10）。

**退出证据**：`ACCEPTANCE.md` §2 的“输入”“领域规则”中对应条目全部有测试。再做一次真实宿主试玩，覆盖 `ACCEPTANCE.md` §6.4 剧本 3、6、7、8、9、10 的主干。

## 阶段 3：时间、事件与长期记忆

- 结算顺序（`RUNTIME_PROTOCOL.md` §6.1）、离屏分档与冻结、事件的完整生命周期与概率事件。
- 快进（预览 + 提交）、转折、`undo-turn`、`replaces_turn`、追溯。
- 章节摘要与归档、上下文列表上限、`requests`。
- `tools/simulate.py`：两条 300 回合模拟（`ACCEPTANCE.md` §9 第 4 条）。

**退出证据**：

- `ACCEPTANCE.md` §2 的“时间与随机”全部有测试。
- 两条 300 回合模拟通过。
- 满足 `ACCEPTANCE.md` §5 的体积与增长门槛。
- 第 300 回合的提交 P95 不超过第 10 回合的 1.5 倍。

## 阶段 4：存档、会话与升级

- 快速存档、另存为、槽冲突（`exists` / `changed_elsewhere`）。
- 上下文里的 `save` 状态，以及“再开一局”前的未存档确认。
- 续玩、“恢复”的歧义处理、`list-sessions`。
- 导出与导入（完整性校验）。
- 调试视图。
- schema 迁移与自动备份；卸载说明。

**退出证据**：

- `ACCEPTANCE.md` §2 的“存档”全部有测试。
- `SKILL_PACKAGING.md` §10 的故障演练全部符合期望。
- 一份真实宿主记录：先存档，再换上新版本的 Skill 目录（含一次迁移），然后在新对话里续玩。

## 阶段 5：内容工具与六个世界

- 内容工具：`new-world`、`verify-content` 的全部检查（语义、时代与边界、近似重复、多样性）、`preview-openings`。
- 自定义世界：`CONTENT_BIBLE.md` §5。
- 按 `CONTENT_BIBLE.md` §8.2 的流程完成其余五个世界，每个都走 `draft` → `review` → `released`。
- 这一阶段可以在阶段 1 之后**并行**进行：内容写作只依赖世界包格式和校验器，不依赖其余玩法。

**退出证据**：`ACCEPTANCE.md` §3 全部通过；每个世界都有试玩记录。

## 阶段 6：端到端评测

- `tests/e2e/` 中准备以下内容：
  - 16 条剧本；
  - 评分量表与锚点；
  - 校准集；
  - 记录采集脚本与机器检查脚本。
- 先校准，再正式评审。两个宿主，每条剧本在每个宿主上跑 ≥ 3 次。
- 失败按根因修改代码、内容或 `SKILL.md`。原始失败记录保留，并链接到修复。

**退出证据**：`ACCEPTANCE.md` §6 要求的完整报告，包括：

- 首跑通过率；
- 每个维度的分数分布；
- 宿主与模型身份；
- 失败记录与修复的对应关系。

## 阶段 7：发布

- 性能全量测量：`ACCEPTANCE.md` §4，冷进程在 Windows 与 Linux 上都测。只优化超过门槛的路径。
- `SKILL_PACKAGING.md` §9 的真实演练，Windows 与 Linux 各一次。
- 对照 `ACCEPTANCE.md` §9 逐条给出证据。
- 写发布说明：安装方法、数据目录位置、卸载与清除数据、已知限制。

## 执行纪律

- `PROGRESS.md` 每个阶段至少更新一次，写这些：
  - 阶段与完成度；
  - 执行过的命令与退出码；
  - 实际数字：测试数、耗时、P50 与 P95、上下文体积；
  - 文档冲突与当时的选择；
  - 替代了哪些设计、为什么；
  - 遗留问题；
  - 下一步。
- 写实测数字，不用“通过”“达标”之类的结论代替数字。
- `spec/` 只读。发现规范有错或做不到，记在 `PROGRESS.md` 里请用户决定，不要自己改规范来迁就实现。
- 同一门禁连续三次修复仍不通过：停止局部补丁，记录根因，重做该模块的边界。
- 不为赶进度放松合同、删断言，也不把失败写进例外清单。
