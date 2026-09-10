# 素材治理与实玩验收实施报告（第二轮 · 2026-09-10）

执行者：dsh（glm-5.3 主控 + 评分/桥接/审查子代理流水）。基线为本仓库 `06ef4a7` 提交的第一轮报告（git 历史保留），本轮按用户六点指令执行，全部结论以本文件为准。

## 0. 结论总表

| 指令 | 结果 |
| --- | --- |
| 1 修复并重跑真实失败框架/模式 | 44 案三因分类→协议 v3+框架/模板定点修；实玩 36/80 → **79/80**（daily 40/40，pressure 39/40），1 例残留模型侧事实捏造（§1.4） |
| 2 真实宿主闭环验收 | 9 步全过（开局/续写/事件/快进/元指令/存档槽/载入/跨天/失败恢复），报告 `maintenance/host_loop_report.md` |
| 3 逐批处理 569 桥接单元 | **BRIDGE_REQUIRED 569→0**；核心池 699=635 KEEP_LEGACY+18 KEEP_SHARED+46 FROZEN；G01–G13 全批次闭合 |
| 4 审查 1,573 非核心单元+重复簇 | **NOT_REVIEWED 1,573→0**；重复候选 unresolved=0（当前 `scripts/check_duplicates.py` 输出 reviewed_candidates 5；原文 244 不可复现，见 §3）；受限条目全部登记 restricted |
| 5 降低人物视角复用 | 28/40 框架 material.pairs 强化（资源/限制/见面理由差异化，两组资源零交集） |
| 6 变更后定位重审+重跑+回归 | 三轮实玩证据链+登记簿/指纹/全量测试终局全绿；失败证据全部归档，门槛未动 |

登记簿终态（`python scripts/material_registry.py --summary`）：units 2,374 / entries 2,390；KEEP_LEGACY 1,312、KEEP_SHARED 974、FROZEN_RESTRICTED 46、DEPRECATED 18、KEEP_FRAMEWORK 40；**errors 0 / warnings 0 / BRIDGE_REQUIRED 0 / NOT_REVIEWED 0**。内容指纹记为 `e8d68934…`（第二轮曾写 `5301735b…`：那是 Windows 工作区把 `scripts/data/pools.yaml` 以 CRLF 检出时算出的值，干净的 LF 检出会得到 `e8d68934…`，两台机器不一致导致远端 CI 红，详见 §9）。pytest 291 passed（含指纹锁）。

## 1. 实玩验收（三轮证据链）

### 1.1 基线（v2，dsh-headless 生成 + Codex 独立评分）

36/80 案例（daily 13/40、pressure 23/40）、223/320 回合通过；开局回合均值 9.34（0% 低于 8），失败全部集中在三次续写（均值 7.80，37.9% 低于 8）；23 个零分维中 20 个落 meaningful_choices。生成方为 `dsh-headless:deepseek-v4-flash`（host=DeepSeek Harness），**评分者**才是 Codex：80 份 review 中 78 份 Codex（三个身份：codex-independent-reviewer 26、Codex independent transcript review 24、codex-independent-semantic-review 28），另 2 份为 glm-independent-review-v3 混评。均值按 80 份 review 重算，原文 9.31/7.78 与证据不符，已更正。证据归档 `maintenance/playtests/stale-input-v3/`。

### 1.2 三因分类（44 失败案全量）

四路子代理独立交叉验证：**model_deviation 28 / summary_loss 14（实为探针设计缺陷）/ source_gap 2 主+3 次**。44/44 主修复杠杆收敛于 FOLLOWUPS 措辞与 render_prompt 规则串，框架字段仅 4 处定点修、fill_opening 模板 1 处。分类明细 `maintenance/triage/summary.md` 与 `maintenance/triage/{a1,a2,b,c,d}.json`。

关键机制发现：规则句「不要替玩家说话或替玩家决定」与续写①「再选一件小事推进」直接冲突，模型为守规把已授权动作降级为提问/留言/旁观——零分潮的真正来源。

### 1.3 修复与三轮重跑

**协议 v3**（`scripts/run_playtest.py`）：FOLLOWUPS 三条重写（小事须当场有结果；异议须指定对象并当场协商改法；告别须列已完成/未完成清单）；规则串新增八条（「我」声明动作=已授权须写出执行与可观察结果、NPC 须给可当场见效小事、活动每回合可观察进展、异议先确认分歧再给取舍、时间词逐字一致、状态变化须先有动作描写、资源占用与材料一致、出口只首提）。同步 `playtest_report.py` 协议校验与测试 fixture。

**框架定点修**：mat-0cc59e867（通告 beats 写明新取物时段）、mat-de87cf5c（执行主体=楼宇前台人工复核，测试账号无权操作正式预约）、mat-be59cd31（obligation 加计时实测+资源补校准沙漏）、mat-295d0099（留痕仅在活动实际发生后）。**模板修**：fill_opening.py 句号重复 bug、L600 语病、直呼其名话术。

**证据完整性事件（两起，均已归档）**：

1. v3 首轮并行重跑 80/80 全部离世界——dsh.CMD 垫片在首个换行处截断多行 argv（材料从未送达）+ headless 加载用户根技能目录致本 SKILL 劫持开局提示。修复：`maintenance/playtest_headless_patch.yml`（skill-filesystem 隔离）+ run_playtest turn0 守卫 + node 直连调用 + 串行监督器。污染证据归档 `contaminated-session-v1/`。
2. 三轮重跑窗口内 provider 故障：促销中转模型 `deepseek-v4.1-flash-expires-on-0910` 到期返回 `400 MODEL_DISABLED`，harness 将无体 400 误映射为 `CONTEXT_WINDOW_EXCEEDED`。修复：`~/.dsh/settings.yaml` agent-default-model 切换官方 `deepseek-v4-flash`（订阅通道，实测零按量消耗）。复核注记：本报告复核时该 headless profile 的 composed config 报 `deepseek-official / deepseek-flash`，故重跑批次的 `generator`、`host_version` 字符串会与本批不同（门禁只要求非空，不做等值比对；跨批次横比时以协议与素材为准）。

**三轮终验**（串行、seed 11、generator=dsh-headless:deepseek-v4-flash、protocol=non-explicit-runtime-brief-v3）：80/80 transcript 完整；独立评分（reviewer=glm-independent-review-v3，与生成器异模型，按 `maintenance/playtest_review_protocol_v3.md` 八条校准，evidence 逐字子串、sha256 绑定、最低回合聚合）：

| 指标 | v2 基线 | v3 终验 |
| --- | --- | --- |
| 案例通过 | 36/80（45%） | **79/80（98.75%）** |
| 回合通过 | 223/320（69.7%） | **318/320（99.4%）** |
| daily / pressure | 13/40 · 23/40 | **40/40 · 39/40** |
| 开局回合均值 | 9.31 | 9.91 |
| 续写回合均值 | 7.78 | **9.66** |
| 续写低于 8 比例 | 37.9% | **0.4%** |
| 零分维（320 回合） | 23 个 | **1 个** |

案例分分布：满分 10 分 ×24、9 分 ×50、8 分 ×5、6 分 ×1（按 80 份 review 重算；原文 30/48/1/1 与证据不符，已更正）。一维扣分合计 86 处（meaningful_choices 31、consequence_continuity 29、natural_expression 26），character_credibility 全程满分，world_specificity 仅 1 处 0 分（下述残留案）。v2 的结构性病灶全部消失：无越权操作、无替玩家锁定同意、无活动停滞、无时间线破坏。

### 1.4 残留失败（如实报告，不删不改门槛）

`mat-3f430a8a5ab95accb2a0db0ae2ceb369-pressure`（寒冬避难所公共生活·压力）6/10：turn1 明写「明天那篮先不写你名字；今天验过就算完」，turn2 却出现「联络板上**刚添的那行**——你的名字挂在『整篮点验』后头」再当场划掉——把从未存在的板面状态当作被异议义务补种出来，与前文事实直接矛盾，world_specificity=0 阻断。评审证据逐字核实无误。

该案是「义务补种」模式的最重实例（其余案例同模式仅 consequence_continuity=1）：协商结构本身合规（先确认分歧点、改法保分明），但被异议义务是异议当下新写的。修复假设（供下轮）：① 生成侧——续写①收尾时把义务条款写上屏（避免异议回合才补种）；② 协议侧——v4 规则「被异议条款必须逐字引用前文原句，不得现场书写后声称为旧有」。次级残留形态（不阻断）：免责/出口口径跨回合复述（ne 1 ×26）、探针言语由 NPC 代指认（mc 1 ×31，其中相当部分属评审口径从严格度差异）。

## 2. 核心桥接闭合（569→0）

G01–G13 十三批次全闭合，模式统一：id/source_hash/source 与 registry 逐字绑定、owners 用 rg 实证的真实 consumer 定位符（`consumer:<file>.<函数>#<池键>` 式）、modes 按消费实证（张力引擎/处境侧/交易摊牌主体仅 pressure，daily 白名单机制 roll_opening.py:745-764 三重拦截实证）、FROZEN 46 行全程未动、每批 reason 点名具体绑定依据。闭合轨迹：569→438（G07+G10+G12/13）→327（G05）→0（G01-G04/G06/G08/G09/G11 五波合并）。restricted 登记 104 条（登记簿 `restrictions.restricted=true`：核心池 81 + 非核心 23；其中成人场所组 5、权力处境 19「不推导亲密许可」、身体靠近 16+4、身份侧未成年指向从严 3、地点 2 等）。原文 74 条的口径不可由登记簿复现，已按实算更正。

口径限定（第三轮补记）：`authoring/frameworks/*.yaml` 的框架级 `material.bridge_status` 是内容设计说明，与登记簿里单元级 `BRIDGE_REQUIRED`（治理缺口）不是同一口径——例如 `authoring/frameworks/mat-d8ec69422b1354538ef3c705f4beb804.yaml`（幕末町屋与道场）声明江户神乐坂是异地联络点、须另写旅程或通信（`bridge_explanation` 已逐字写明）。本节的 569→0 指后者；框架级说明按内容设计保留，不计入治理缺口。

配套源侧修复（改源→sync→受影响行重放→依赖哈希刷新，reviewer=dsh/nsf-fix-2026-09-10）：三池 compat 门禁补齐（处境 65+核心规则 6，roll_opening.py:646 门禁扩至三池）、timed_situations 34 条 list→{label:hours}、模板施受方向/医疗断言/越权扩展 9 处、action 分类 2 处归位、老爷车到站语义、far 事件去引擎名、压盘三小时错配（含 README 示例同步）、学园祭/琴房/娇矜小花/模范长女/特聘家教等成年锚定。漂移注记见 `maintenance/core_review_evidence.md`。

## 3. 非核心审查（1,573→0）

分波审查（`maintenance/noncore_partition.md` 口径）四路落库：geo 891（KEEP_SHARED 861+KEEP_LEGACY 30）、textile 385（全 KEEP_LEGACY）、identity 215（70/145）、pools 杂项 76（含 world_frameworks version 按 P3 判 DEPRECATED，只登记不删源）。片段经 `material_registry.py --sync --decisions` 原子落库。共享事实未删任何一条；真重复经查为零（`check_duplicates.py` 当前输出 reviewed_candidates 5 / unresolved 0）。原文「244 候选」系首轮盘点口径，本轮无法由工具复现，保留于此仅作历史记录，不作为可复核数字。

登记-only 遗留（issues 台账在案）：legacy_weight 死值（roll_opening.py:316 赋值后无下游）、3 个时代名池整体缺失（传媒舆论危机期/契约共存时代/远途休假季，触发顶层回退）、templates 近重复 7 对。

## 4. 宿主闭环验收（第 2 点）

会话 host-loop-daily-1（成年创作者与校园艺术季框架）：build_opening --complete → 最小 patch 提交 → 过期 token 拒绝与恢复 → 事件增删（semantic_key/source 自动落账）→ 75 分钟快进+事件 resolve → 元指令 advance_turn:false → 存档槽 init/save/load（缺 --expected-updated-at 拒绝）→ 宿主机械复制载入 → 跨天续写。全部通过。发现并已修：world.constants 句号重复、L600 语病。报告 `maintenance/host_loop_report.md`。

## 5. 人物差异化（第 5 点）

28/40 框架 material.pairs 强化（每框架第二组人物独立资源/限制/见面理由；两组资源零交集复核；schema/场域字段未动）。未动的 12 框架经审计本已达标（含 1 例 pairs[0] 内部重复修复）。结构性发现：约 6/10 框架原为「镜像双视角」结构，弱项集中在 pairs[1] 资源与 pairs[0] 互拷、relationship_reason 同骨架——本轮已按框架各自机制重写。31 份 framework_reviews 源哈希同步，build 40/40 reviewed。

## 6. 证据索引

- 实玩终验：`maintenance/playtests/mat-*.json`（80 转写）+ `mat-*.review.yaml`（80 独立评分）
- 历史批次（**目录号是重跑轮次，不是协议版本**）：`stale-input-v3/`（协议 v2 + 修复前素材 = 基线，36/80）、`stale-input-v4/`（协议 v3 + 修复前素材 = 协议消融，80 转写、当时 0 评分）、`contaminated-session-v1/`（垫片截断污染批）
- 评分简报：`maintenance/playtest_review_protocol_v3.md`；分类：`maintenance/triage/`；桥接批次与漂移：`maintenance/core_review_evidence.md` + `core_review_decisions.yaml`（699 行）
- 非核心：`maintenance/noncore_partition.md` + `noncore_reviews/*.yaml`；宿主闭环：`maintenance/host_loop_report.md`
- 基础设施：`maintenance/playtest_headless_patch.yml`

## 7. 遗留与建议

1. **残留失败 1 案**（§1.4）：2026-09-11 定为按「必须 80/80」处置——生成侧修（`scripts/run_playtest.py` FOLLOWUPS[0] 要求义务当回合上屏）+ 协议 v4 规则（被异议条款须逐字见于前文）双管，随后全量重跑并重新独立评分；第三轮计划见 `maintenance/round3_repair_plan.md`，「接受 79/80」不再是候选。
2. **release 门禁**：`qa.py --full --release` 按设计继续拦截。第三轮重跑期间旧终验已归档、顶层证据为空，门禁必然报 `PLAYTEST_MISSING`，属中间态而非回归（见 §8）。
3. 评审口径差异说明：四段评分中 mc 扣分密度存在段间差异（22 vs 2/5/2），横比时以 0 分阻断与案例级结论为准。
4. 登记-only 项（§3）与动力舱维修工玩家侧时代映射（G10 遗留）留待下批源修。
5. **远端 CI 已经配置**（`.github/workflows/quality.yml:16-18` 为 Python 3.10/3.13 矩阵；`:34-36` 对 tag push 执行 `--release`），但本轮全部验证在本地 Python 3.12 完成，没有远端执行记录。原文「仍未配置」有误，已更正。相关风险：`v1.3.0` 的 tag 已推到 origin，一旦触发 release job 必红（当前 `qa.py --full --release` 按设计拦截实玩 79/80）。

## 8. 第三轮（协议 v4 与全量重跑）

目标（用户 2026-09-11 拍板）：实玩必须 80/80；补评 160 份消融转写；撤销 `v1.3.0` 并在 release 门禁全绿后重打。计划见 `maintenance/round3_repair_plan.md`。

**协议 v4 的三次措辞迭代（每轮都先小批验证，废弃批次原样归档）**：

1. **v4 草案**（`FOLLOWUPS[0]` 要求义务当回合上屏 + 规则串「被异议条款须逐字见于前文」）。试点 4 例：原残留案 `mat-3f430a8a…-pressure` 达到 10/10，但 `mat-d8ec69422b1354538ef3c705f4beb804-daily`（幕末町屋与道场）把「往后替人过问松紧」说成旧有安排——该条只在异议回合的木牌背面被现写，`world_specificity=0` 且 blocking，案例 6/10。归档 `maintenance/playtests/v4-draft-aborted/`（含 README）。
2. **v4-a**（加入「逐字引用原句」+ 允许「前文确无新增义务时据实说明」）。抽查已完成 4 回合的 36 份转写：**34 份**的异议回合以「没有可议条款／没有新增义务」收场，只有 2 份出现实质协商——该措辞把异议回合整体架空，批次可能全绿而协商能力未被检验，废弃。归档 `maintenance/playtests/v4-a-nullified/`（含 README，逐字核对样例在案）。
3. **v4-b（现行）**：`FOLLOWUPS[0]` 改为「请把这件事牵连出的具体安排当回合写清（谁在什么时间做什么、边界在哪），我还没答应其中任何后续」；`FOLLOWUPS[1]` 改为「对刚才那项安排里的一条提出异议：逐字引用前文原句（写明出处），当场协商改法（改哪一条、保哪一条）」；规则串取消宽松出口，改为「续写①当回合就要把可被引用的具体安排写清」。评分简报 `maintenance/playtest_review_protocol_v4.md` 第 9 条同步：异议回合主张「没有可议条款」时，评分者必须核对前文——前文已写出可引用安排而模型仍主张没有，属规避协商，记入 reason 与 summary。

**代码与文件**：`scripts/run_playtest.py:25` `PROTOCOL = "non-explicit-runtime-brief-v4"`；`scripts/playtest_report.py:53` 协议校验同步 v4；新增 `maintenance/playtest_review_protocol_v4.md`（v4 简报，八条与 v3 逐字相同 + 第 9 条）、`maintenance/attribution_review_protocol.md`（消融补评简报：v4 批用 1–8 条，v2 批只用 1/2/6/7/8 条）、`maintenance/playtest_reviewer_glm.yml`（评审模型覆盖）、`maintenance/playtest_generator_pin.yml`（生成模型固定）、`scripts/review_playtest.py`（独立评分驱动 `run|check|stats`，机器复核与 `playtest_report.py` 同规则、不校验探针身份与 prompt 重放）。

**证据归档与中间态**：旧终验 80 转写 + 80 评分经 `git mv` 移入 `maintenance/playtests/terminal-v3/`；顶层为空（门禁报 PLAYTEST_MISSING 属预期）。`v1.3.0` 已从本地与 origin 撤销（`git push origin :refs/tags/v1.3.0`），待门禁全绿后重打。消融补评与归因结果见 `maintenance/attribution_report.md`（素材段已完成：协议相同、素材不同 → 44/80 vs 79/80）。

**定位符修复（第四阶段）**：`maintenance/noncore_reviews/pools.yaml` 中 15 行 owner 定位符指向不存在的符号（`check_content.run`×8 → `check_content.check`、`check_frameworks.audit`×4 → `check_frameworks.check_frameworks`、`build_frameworks.build`×2 → `build_frameworks.aggregate`、`roll_opening.compatibility_reasons`×1 → `roll_opening.apply_daily_roll`），已同时修正决策档与 `references/material_registry.yaml`（44 处，含镜像行），`material_registry.py --summary` 仍为 units 2,374 / entries 2,390 / errors 0 / warnings 0，registry 相关 25 项测试通过。每个新符号都有 `scripts/` 内逐行证据（最内层 def）。

**新发现（治理缺口，待单独一轮）**：`maintenance/noncore_reviews/pools.yaml` 的 76 条决策里有 8 条与 `references/material_registry.yaml` 不一致，`material_registry.py --decisions` 会直接抛 `Stale or unknown decision: mat-84a36e2c46a35581aaa97810c9a125dd`。其中 `mat-d31d0ab0…` 决策写 `KEEP_LEGACY` 而登记簿是 `KEEP_SHARED`、`mat-2077cd01…` 决策 modes `[daily, pressure]` 而登记簿为 `[pressure]`，另有 4 条 restrictions 说明文字不同。结论：**该文件当前不可整体重放**；重放会把登记簿里更新的结论回退，因此本轮只做定点修正，建议下一轮按 8 条逐条重审后再同步。

**登记-only 项与 G10（本轮不改源，理由=证据冻结）**：`legacy_weight` 死值、3 个时代名池缺失（传媒舆论危机期／契约共存时代／远途休假季）、templates 近重复 7 对、动力舱维修工玩家侧时代映射，均落在 `scripts/data/*` 或素材侧。任何此类改动都会改变 `context()` 生成的 `committed_opening`，使已采转写的 `prompt_sha256` 与当前素材不符（门禁报 `stale runtime input or prompt`）。因此这些修复必须与下一批转写同轮进行，不能在本轮证据链中间插入。

**当前阻塞（2026-09-11 04:5x）**：本机默认模型被切到 `jian/grok-4.6`（`~/.dsh/settings.yaml` 03:47），上游网关对任何 headless 调用返回 `INVALID_REQUEST: OpenAI API error (400): unknown provider for model grok-4.6`；`--patch` 覆盖在用户层设置之后失效，故生成与评审都无法继续：v4-b 全量生成在各自首框架 turn 0 后中断，消融补评停在 17/80（v2 批）与 80/80（v4 批已完成）。已于 04:46 自行恢复并续跑（`run_playtest.py` 会跳过已完成转写，`review_playtest.py run` 会跳过已完成 review），04:35–04:46 的残批作废重来；另新增 `maintenance/playtest_generator_pin.yml` 固定生成模型，`run_playtest.py` 增加 `CALL_TIMEOUT = 300` 与超时重试一次（并发下 180s 超时曾整条框架 lane 崩掉）。

## 9. 第三轮终态（2026-09-11 07:1x）

**实玩 80/80 达成**（协议 v4，全部 40 框架 × daily/pressure）：

- 生成：4 路并行 chunk（每路 10 框架、串行 8 次调用），`--dsh-extra=--patch maintenance/playtest_headless_patch.yml` + `--dsh-extra=--patch maintenance/playtest_generator_pin.yml`，node 直连 `C:\dsh\deepseek-harness\apps\cli\lib\bin.js`；80 份转写全部 4 回合、`protocol=non-explicit-runtime-brief-v4`、`seed=11`、`generator=dsh-headless:deepseek-flash`（generator 字符串与旧批的 `dsh-headless:deepseek-v4-flash` 不同，门禁只要求非空，已如实记录）。
- 评分：`glm-independent-review-v4`（简报 `maintenance/playtest_review_protocol_v4.md`）80 份，`review_playtest.py run|check` 全 ok、failed 0。
- 门禁：`playtest_report.audit()` → `{"responses": 320, "required_responses": 320, "current_responses": 320, "passed_cases": 80, "required_cases": 80, "passed": true, "errors": []}`。
- 统计（`review_playtest.py stats`）：案例 80/80；daily 40/40、pressure 40/40；`turns_passed_flag` 320、`turns_passed_by_score` 320；案例分分布 10×60 / 9×20；开局均值 10.00、续写均值 9.92、续写 <8 = 0；零分维度 0；扣分点仅 `natural_expression` 20（其余四维 0）；`blocking_cases` 空。历史失败案 `mat-3f430a8a…-pressure` 本轮 9/10 通过。
- 交叉复核（防「绿而空」）：抽 12 例（8 例 9 分 + 4 例 10 分，含 `mat-3f430a8a…-pressure`）用第二个模型 `gemini-3.8-flash-high`（`maintenance/playtest_crosscheck_gemini.yml`，reviewer `gemini-independent-review-v4`）独立评分，结果 12/12 通过、11/12 与主评分同分（1 例差 1 分）、双方阻断均为 0；抽查文本逐条引用前文原句并按第 9 条核对，非空转评分。结论：80/80 由两个不同模型的独立评分一致支持，但仍是「同一简报、同一驱动」的评分口径，不是跨口径认证。
- 全量门禁：`python scripts/qa.py --full --release` 退出码 0（registry、核心桥接、非核心审查、重复候选、实玩证据全过；`pytest` 291 passed；`sample_materials` 168 样本 0 失败；`compileall`、`git diff --check` 干净）。
- 归因（`maintenance/attribution_report.md`）：A 基线 36/80（Codex v2 口径）→ A' 同批转写换评分者 79/80（口径段 +43）→ B' 协议 v3 同素材 44/80（协议段 −35）→ C 修复后素材 79/80（素材段 +35）。因此第二轮报告的「36→79」主要是评分口径变化，素材修复的真实作用是「把更严探针下的 44 拉回 79」；本轮 v4 的 80/80 是在比第二轮更严的探针下取得的。
- 遗留（下轮，均属素材侧，会改 `committed_opening` → `prompt_sha256`，必须与下批转写同轮）：`maintenance/noncore_reviews/pools.yaml` 8 条决策与登记簿不一致（不可整体重放）、`legacy_weight` 死值、3 个时代名池缺失、templates 近重复 7 对、动力舱维修工玩家侧时代映射（G10）。

**CI 本地失真修复（本机绿、远端红）**：`v1.3.0` 首次重推后远端 `quality` 两个 job（3.10/3.13）在 10 秒内失败，报 `CORE_REVIEW_DEPENDENCY_STALE: scripts/data/pools.yaml`。根因：`scripts/data/pools.yaml` 是唯一一个工作区为 CRLF、而 git blob 为 LF 的文件（工作区 61,569 字节 / blob 59,260 字节），于是 `check_content.content_fingerprint()`（逐文件 `read_bytes()`）与 `data_contract.core_review_errors()`（`sha256(read_bytes())`）在本机算出的都是 CRLF 值——`maintenance/content_fingerprint.txt` 记 `5301735b…`、`maintenance/core_review_dependencies.yaml` 记 `09dd9de8…`，两处都只在 Windows 工作区成立，干净 LF 检出必然报 STALE。修复：① 把工作区文件规范化为 LF（字节与 blob 一致，`git status` 干净）；② 两份记录改为 LF 规范值（指纹 `e8d68934…`、依赖哈希 `7228d018…`）；③ 两处哈希改为先 `replace(b"\r\n", b"\n")` 再算，避免任何工作区换行风格造成误判。验证：干净 clone（模拟远端 Linux 检出）里跑同一条 `python scripts/qa.py --full --release` 全绿。受影响的只是哈希记录口径，素材内容、review 结论与 80 份转写（`source_hash`/`prompt_sha256` 均为结构化 digest）都不受影响。
