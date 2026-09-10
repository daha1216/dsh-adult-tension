# 素材治理与实玩验收实施报告（第二轮 · 2026-09-10）

执行者：dsh（glm-5.3 主控 + 评分/桥接/审查子代理流水）。基线为本仓库 `06ef4a7` 提交的第一轮报告（git 历史保留），本轮按用户六点指令执行，全部结论以本文件为准。

## 0. 结论总表

| 指令 | 结果 |
| --- | --- |
| 1 修复并重跑真实失败框架/模式 | 44 案三因分类→协议 v3+框架/模板定点修；实玩 36/80 → **79/80**（daily 40/40，pressure 39/40），1 例残留模型侧事实捏造（§1.4） |
| 2 真实宿主闭环验收 | 9 步全过（开局/续写/事件/快进/元指令/存档槽/载入/跨天/失败恢复），报告 `maintenance/host_loop_report.md` |
| 3 逐批处理 569 桥接单元 | **BRIDGE_REQUIRED 569→0**；核心池 699=635 KEEP_LEGACY+18 KEEP_SHARED+46 FROZEN；G01–G13 全批次闭合 |
| 4 审查 1,573 非核心单元+重复簇 | **NOT_REVIEWED 1,573→0**；244 重复候选随框架自建句自然清零（unresolved=0）；受限条目全部登记 restricted |
| 5 降低人物视角复用 | 28/40 框架 material.pairs 强化（资源/限制/见面理由差异化，两组资源零交集） |
| 6 变更后定位重审+重跑+回归 | 三轮实玩证据链+登记簿/指纹/全量测试终局全绿；失败证据全部归档，门槛未动 |

登记簿终态（`python scripts/material_registry.py --summary`）：units 2,374 / entries 2,390；KEEP_LEGACY 1,312、KEEP_SHARED 974、FROZEN_RESTRICTED 46、DEPRECATED 18、KEEP_FRAMEWORK 40；**errors 0 / warnings 0 / BRIDGE_REQUIRED 0 / NOT_REVIEWED 0**。内容指纹更新为 `5301735b7b3799e1c3700e9e5f25ee7434b1e2dc485f0a64634e61f45b5c7aab`（全量检查通过后经 `qa.py --full --update-fingerprint` 走正规流程）。pytest 291 passed（含指纹锁）。

## 1. 实玩验收（三轮证据链）

### 1.1 基线（v2，Codex 环境生成）

36/80 案例（daily 13/40、pressure 23/40）、223/320 回合通过；开局回合均值 9.31（0% 低于 8），失败全部集中在三次续写（均值 7.78，37.9% 低于 8）；23 个零分维中 20 个落 meaningful_choices。评分者 Codex 独立评审。证据归档 `maintenance/playtests/stale-input-v3/`。

### 1.2 三因分类（44 失败案全量）

四路子代理独立交叉验证：**model_deviation 28 / summary_loss 14（实为探针设计缺陷）/ source_gap 2 主+3 次**。44/44 主修复杠杆收敛于 FOLLOWUPS 措辞与 render_prompt 规则串，框架字段仅 4 处定点修、fill_opening 模板 1 处。分类明细 `maintenance/triage/summary.md` 与 `maintenance/triage/{a1,a2,b,c,d}.json`。

关键机制发现：规则句「不要替玩家说话或替玩家决定」与续写①「再选一件小事推进」直接冲突，模型为守规把已授权动作降级为提问/留言/旁观——零分潮的真正来源。

### 1.3 修复与三轮重跑

**协议 v3**（`scripts/run_playtest.py`）：FOLLOWUPS 三条重写（小事须当场有结果；异议须指定对象并当场协商改法；告别须列已完成/未完成清单）；规则串新增八条（「我」声明动作=已授权须写出执行与可观察结果、NPC 须给可当场见效小事、活动每回合可观察进展、异议先确认分歧再给取舍、时间词逐字一致、状态变化须先有动作描写、资源占用与材料一致、出口只首提）。同步 `playtest_report.py` 协议校验与测试 fixture。

**框架定点修**：mat-0cc59e867（通告 beats 写明新取物时段）、mat-de87cf5c（执行主体=楼宇前台人工复核，测试账号无权操作正式预约）、mat-be59cd31（obligation 加计时实测+资源补校准沙漏）、mat-295d0099（留痕仅在活动实际发生后）。**模板修**：fill_opening.py 句号重复 bug、L600 语病、直呼其名话术。

**证据完整性事件（两起，均已归档）**：

1. v3 首轮并行重跑 80/80 全部离世界——dsh.CMD 垫片在首个换行处截断多行 argv（材料从未送达）+ headless 加载用户根技能目录致本 SKILL 劫持开局提示。修复：`maintenance/playtest_headless_patch.yml`（skill-filesystem 隔离）+ run_playtest turn0 守卫 + node 直连调用 + 串行监督器。污染证据归档 `contaminated-session-v1/`。
2. 三轮重跑窗口内 provider 故障：促销中转模型 `deepseek-v4.1-flash-expires-on-0910` 到期返回 `400 MODEL_DISABLED`，harness 将无体 400 误映射为 `CONTEXT_WINDOW_EXCEEDED`。修复：`~/.dsh/settings.yaml` agent-default-model 切换官方 `deepseek-v4-flash`（订阅通道，实测零按量消耗）。

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

案例分分布：满分 10 分 ×30、9 分 ×48、8 分 ×1、6 分 ×1。一维扣分合计 86 处（meaningful_choices 31、consequence_continuity 29、natural_expression 26），character_credibility 全程满分，world_specificity 仅 1 处 0 分（下述残留案）。v2 的结构性病灶全部消失：无越权操作、无替玩家锁定同意、无活动停滞、无时间线破坏。

### 1.4 残留失败（如实报告，不删不改门槛）

`mat-3f430a8a5ab95accb2a0db0ae2ceb369-pressure`（寒冬避难所公共生活·压力）6/10：turn1 明写「明天那篮先不写你名字；今天验过就算完」，turn2 却出现「联络板上**刚添的那行**——你的名字挂在『整篮点验』后头」再当场划掉——把从未存在的板面状态当作被异议义务补种出来，与前文事实直接矛盾，world_specificity=0 阻断。评审证据逐字核实无误。

该案是「义务补种」模式的最重实例（其余案例同模式仅 consequence_continuity=1）：协商结构本身合规（先确认分歧点、改法保分明），但被异议义务是异议当下新写的。修复假设（供下轮）：① 生成侧——续写①收尾时把义务条款写上屏（避免异议回合才补种）；② 协议侧——v4 规则「被异议条款必须逐字引用前文原句，不得现场书写后声称为旧有」。次级残留形态（不阻断）：免责/出口口径跨回合复述（ne 1 ×26）、探针言语由 NPC 代指认（mc 1 ×31，其中相当部分属评审口径从严格度差异）。

## 2. 核心桥接闭合（569→0）

G01–G13 十三批次全闭合，模式统一：id/source_hash/source 与 registry 逐字绑定、owners 用 rg 实证的真实 consumer 定位符（`consumer:<file>.<函数>#<池键>` 式）、modes 按消费实证（张力引擎/处境侧/交易摊牌主体仅 pressure，daily 白名单机制 roll_opening.py:745-764 三重拦截实证）、FROZEN 46 行全程未动、每批 reason 点名具体绑定依据。闭合轨迹：569→438（G07+G10+G12/13）→327（G05）→0（G01-G04/G06/G08/G09/G11 五波合并）。restricted 登记 74 条（成人场所组 5、权力处境 19「不推导亲密许可」、身体靠近 16+4、身份侧未成年指向从严 3、地点 2 等）。

配套源侧修复（改源→sync→受影响行重放→依赖哈希刷新，reviewer=dsh/nsf-fix-2026-09-10）：三池 compat 门禁补齐（处境 65+核心规则 6，roll_opening.py:646 门禁扩至三池）、timed_situations 34 条 list→{label:hours}、模板施受方向/医疗断言/越权扩展 9 处、action 分类 2 处归位、老爷车到站语义、far 事件去引擎名、压盘三小时错配（含 README 示例同步）、学园祭/琴房/娇矜小花/模范长女/特聘家教等成年锚定。漂移注记见 `maintenance/core_review_evidence.md`。

## 3. 非核心审查（1,573→0）

分波审查（`maintenance/noncore_partition.md` 口径）四路落库：geo 891（KEEP_SHARED 861+KEEP_LEGACY 30）、textile 385（全 KEEP_LEGACY）、identity 215（70/145）、pools 杂项 76（含 world_frameworks version 按 P3 判 DEPRECATED，只登记不删源）。片段经 `material_registry.py --sync --decisions` 原子落库。共享事实未删任何一条；真重复经查为零（244 候选系框架自建句后自然消解，`check_duplicates.py` unresolved=0）。

登记-only 遗留（issues 台账在案）：legacy_weight 死值（roll_opening.py:316 赋值后无下游）、3 个时代名池整体缺失（传媒舆论危机期/契约共存时代/远途休假季，触发顶层回退）、templates 近重复 7 对。

## 4. 宿主闭环验收（第 2 点）

会话 host-loop-daily-1（成年创作者与校园艺术季框架）：build_opening --complete → 最小 patch 提交 → 过期 token 拒绝与恢复 → 事件增删（semantic_key/source 自动落账）→ 75 分钟快进+事件 resolve → 元指令 advance_turn:false → 存档槽 init/save/load（缺 --expected-updated-at 拒绝）→ 宿主机械复制载入 → 跨天续写。全部通过。发现并已修：world.constants 句号重复、L600 语病。报告 `maintenance/host_loop_report.md`。

## 5. 人物差异化（第 5 点）

28/40 框架 material.pairs 强化（每框架第二组人物独立资源/限制/见面理由；两组资源零交集复核；schema/场域字段未动）。未动的 12 框架经审计本已达标（含 1 例 pairs[0] 内部重复修复）。结构性发现：约 6/10 框架原为「镜像双视角」结构，弱项集中在 pairs[1] 资源与 pairs[0] 互拷、relationship_reason 同骨架——本轮已按框架各自机制重写。31 份 framework_reviews 源哈希同步，build 40/40 reviewed。

## 6. 证据索引

- 实玩终验：`maintenance/playtests/mat-*.json`（80 转写）+ `mat-*.review.yaml`（80 独立评分）
- 历史批次：`stale-input-v3/`（v2 基线）、`stale-input-v4/`（v3 协议消融二轮）、`contaminated-session-v1/`（垫片截断污染批）
- 评分简报：`maintenance/playtest_review_protocol_v3.md`；分类：`maintenance/triage/`；桥接批次与漂移：`maintenance/core_review_evidence.md` + `core_review_decisions.yaml`（699 行）
- 非核心：`maintenance/noncore_partition.md` + `noncore_reviews/*.yaml`；宿主闭环：`maintenance/host_loop_report.md`
- 基础设施：`maintenance/playtest_headless_patch.yml`

## 7. 遗留与建议

1. **残留失败 1 案**（§1.4）：建议下轮协议 v4 加「被异议条款须逐字引用前文」规则后全量重跑；或接受 79/80 为当前诚实验收线。
2. **release 门禁**：`qa.py --full --release` 按设计继续拦截（实玩 79/80 未达 80/80 全过线）——这是门禁正确行为，不是回归。
3. 评审口径差异说明：四段评分中 mc 扣分密度存在段间差异（22 vs 2/5/2），横比时以 0 分阻断与案例级结论为准。
4. 登记-only 项（§3）与动力舱维修工玩家侧时代映射（G10 遗留）留待下批源修。
5. 远端 CI（Python 3.10/3.13 矩阵）仍未配置，本轮全部为本地 3.12 验证。
