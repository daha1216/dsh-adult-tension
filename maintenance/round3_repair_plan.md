# 第三轮修复计划（草案 · 2026-09-11）

依据：`maintenance/implementation_report.md`（第二轮报告，正文＝用户手上的那份，HEAD `9242216`）＋ 独立复核结论。复核基准：登记簿 `units 2374 / entries 2390 / errors 0 / warnings 0`、指纹 `5301735b…c7aab`、`pytest 291 passed`、`qa.release_errors()` 仅 1 条 `PLAYTEST_INVALID: mat-3f430a8a5ab95accb2a0db0ae2ceb369-pressure: zero-scored turn blocks acceptance` —— 以上均已由本人用脚本复现。

本计划分五段。第 0 段是报告本身的可信度修复（便宜、必做）；第 1 段补上第二轮缺失的归因对照；第 2–3 段才动协议/素材并重跑；第 4–5 段清遗留与发布。**顺序不可颠倒**：第 2 段之后当前 80 份终验证据即作废，中间态 release 门禁必红。

## 决策点（开工前需拍板）

| # | 问题 | 选项 | 影响 |
| --- | --- | --- | --- |
| D1 | 验收线 | A 接受 79/80、门禁继续按设计拦截；B 必须拿到 80/80 | 选 B 才需要第 2、3 段；选 A 则第 2 段只归档不动手 |
| D2 | 归因预算 | A 只补评 `stale-input-v4/`（80 份）；B 再补评 `stale-input-v3/`（共 160 份） | B 可把"协议/素材/评分口径"三段拆开，A 只能拆出"协议+口径 vs 素材" |
| D3 | tag 与远端 CI | A 撤 `v1.3.0`；B 保留并如实说明远端 release job 会红；C 修到全绿再打新 tag | `.github/workflows/quality.yml:34-36` 对 tag push 跑 `--release`，当前必红 |

## 阶段 0 · 报告勘误（无行为变更）

改 `maintenance/implementation_report.md` 并同步 `PROGRESS.md:55`、`README.md:197`：

1. `:53` 案例分分布 → 满分 10 ×24、9 ×50、8 ×5、6 ×1（现写 30/48/1/1，与 80 份 `*.review.yaml` 的 `total` 不符）。
2. `:53` 一维扣分 → 五维合计 87（86 为所列三维之和；另 1 处 `world_specificity` 0 分即残留案）。
3. `:22`、`:41` "Codex 环境生成" → 基线 80 份转写元数据全为 `generator=dsh-headless:deepseek-v4-flash` / `host=DeepSeek Harness` / `host_version=0.1.5-alpha.2` / `protocol=non-explicit-runtime-brief-v2`；"Codex"仅指评分侧 reviewer。即"Codex 评审"，不是"Codex 生成"。
4. `:22`、`maintenance/triage/summary.md:27-29` 基线均值 9.31 / 7.78 需注明口径：本人按 80 份重算为 9.34 / 7.80，剔除 2 份 glm 混评（`stale-input-v3/` 内 reviewer 为 `glm-independent-review-v3`）后 9.32 / 7.76，三组都不等于报告的 9.31 / 7.78。二选一：重算统一，或写明"分母为 78 份 Codex 评审 + 口径 X"。
5. `:63` restricted 74 条 → 登记簿实为 104 条（`restrictions.restricted=true`：核心池 81 + 非核心 23）。若 74 有特定口径（如"某几批新增"）则写明。
6. `:79` "28/40 框架强化" 与 `maintenance/core_review_evidence.md:287` 的"⑦31 框架第二人物组资源/限制差异化"需对齐说明（31 应为 28 强化 + 3 因源侧修复同步哈希）。
7. `:84` 历史批次命名易误导：`stale-input-v3/` 装的是 **v2 协议**基线、`stale-input-v4/` 装的是 **v3 协议**消融（目录号＝重跑轮次，非协议版本）。加一行说明。
8. `:95` "远端 CI 仍未配置" → 改为"矩阵已在 `.github/workflows/quality.yml:16-18` 定义（3.10/3.13），本轮无远端执行结果，验证全部本地 3.12"。
9. §1 因果表述收一格：写"修复 + 协议 v3 + 评分口径三者共同作用下达 79/80"，并给出第 1 段的量化拆分。

验收：`python scripts/qa.py --full` 仍 291 passed（改的是文档，指纹与冻结段不动）。

## 阶段 1 · 归因补齐（不生成、只评分）

现状：`stale-input-v4/`（协议 v3 + NSF 前素材，80 份转写齐全）**0 份评分**；`stale-input-v3/`（协议 v2 + 旧素材）由 Codex 按 v2 口径评，且混入 2 份 glm 评。所以"36/80 → 79/80"目前只能归为三者共同作用。

| 批次 | 协议 | 素材 | 现有评分 | 需补 |
| --- | --- | --- | --- | --- |
| `maintenance/playtests/stale-input-v3/` | v2 | 旧 | Codex v2 口径 78 份 + glm v3 份 ×2 | 按 v3 简报补评（见口径约束） |
| `maintenance/playtests/stale-input-v4/` | v3 | 旧 | 无 | 全 80 份补评 |
| `maintenance/playtests/`（顶层终验） | v3 | 新 | glm v3 全 80 份 | — |

- 评审者用同一 `glm-independent-review-v3` 身份、同一 `maintenance/playtest_review_protocol_v3.md`，产出写到**各自子目录**内的 `<stem>.review.yaml`。
- **口径约束**：对 v2 批只套用评审侧口径（简报第 1、2、7、8 条：授权语义、appellations、ne 扣分须有依据、blocking 只放真阻断）；不套用第 3、4、5、6 条（时间词、出口复述、活动推进、凭空状态），这四条是对着 v3 rules 新增的写法要求，v2 批从未被告知，套用会把 Δ口径 高估。应把这次补评记作"口径对齐版"，与 v3 简报并列存档而非覆盖。
- 产出三个差值：Δ协议 = v4批 − v3批(同口径)；Δ素材 = 顶层终验 − v4批；Δ口径 = v3批(新口径) − v3批(旧 Codex 口径)。落 `maintenance/attribution_report.md`。
- 引文校验：调用 `scripts/playtest_report.py` 的 `checked_scores`（逐字子串门），**不要**调用 `audit()`。
- **边界**：这两批一律留在子目录，不得进入 `maintenance/playtests/` 顶层。`audit()` 只认顶层 + `authoring/framework_index.yaml` 的 40 框架 × 2 模式，并要求 `source_hash` 与当前素材一致、`prompt_sha256` 能用当前素材重渲命中（`scripts/playtest_report.py:44-73`）；旧素材批次放顶层会让 `qa.py --full --release` 立刻变红。

预期结论形态（供判断用，不是预设）：若 Δ协议 占总提升的一半以上，则第二轮的"框架/模板定点修"价值需重新表述；若 Δ口径 显著，则 §1.1 的 36/80 基线应同时给出"v3 口径下的基线"。

## 阶段 2 · 残留 1 例（`mat-3f430a8a…-pressure`）修复

根因（报告 §1.4，已逐字复核）：续写②要求对"新增义务"提异议，模型在异议回合才现写该义务（turn2「联络板上刚添的那行…你的名字挂在『整篮点验』后头」），与前文 turn1「明天那篮先不写你名字；今天验过就算完」矛盾。

- **生成侧（治因，优先）**：`scripts/run_playtest.py:26-30` 的 `FOLLOWUPS[0]` 收尾要求"把当场确定的义务/安排写进正文并可观察"。
- **协议侧（兜底）**：`scripts/run_playtest.py:38-49` 的 rules 串加一条：「被异议条款必须逐字引用前文原句，不得现场书写后声称为旧有」。
- **协议版本连锁（改协议必做，顺序即防红顺序）**：
  1. `scripts/run_playtest.py:25` `PROTOCOL` → `non-explicit-runtime-brief-v4`；
  2. `scripts/playtest_report.py:53` 硬编码的 v3 → v4；
  3. 新增 `maintenance/playtest_review_protocol_v4.md`（v3 简报 + 新校准条；v3 文件保留为历史口径）；
  4. **先把顶层 80 份 `git mv` 进历史目录**（如 `maintenance/playtests/terminal-v3/`），再放新批，否则中间态 gate 红；
  5. `tests/test_playtest_report.py:47` 用 `runner.PROTOCOL` 自动跟随；`:143-152`（旧 request 必须被拒）需确认仍成立；
  6. 文档同步：`implementation_report.md:41,85`、`triage/summary.md:21`、`README.md:197`、`PROGRESS.md:55`；
  7. `maintenance/baseline.yaml` 不含 protocol 字段（已核对），无需改。
- **失效范围**（决定是否必须打包重跑）：改协议或改 `run_playtest.context()` 取材 → 80/80 全失效；只改某框架 `authoring/frameworks/*.yaml` 的 material → 该框架的 2 个案例因 `source_hash` 失配失效。两种都会让 release 门禁变红，所以"素材修复 + 重跑 + 重评"必须打包成一次提交序列。

## 阶段 3 · 重跑与证据替换

- 前置：阶段 2 全部落地、`qa.py --full` 绿。
- 先小样 2 框架（1 daily + 1 pressure）跑通，再串行全量；第二批的两次事故（垫片换行截断 argv、provider `MODEL_DISABLED`）都要按已知修复执行：`--dsh-extra --patch maintenance/playtest_headless_patch.yml`、node 直连入口、`~/.dsh/settings.yaml` 的 `agent-default-model` 用官方 `deepseek-v4-flash`。
- 生成后独立评审（reviewer ≠ generator，`playtest_report.py:80` 强制），落顶层；`transcript_sha256` 必须与转写字节一致（本轮 80/80 已验，继续保持）。
- 验收：`python scripts/qa.py --full` 全绿 → `python scripts/qa.py --full --release`（若 80/80 全过则应全绿；仍有残留则如实登记）。**不调 `minimum_score`（`maintenance/baseline.yaml:32` = 8）、不放宽任何一条门禁**。
- 若 D1 选 A：跳过本阶段，仅把"79/80 + 门禁拦截"写成正式验收线，并删掉报告里"建议下轮 v4 全量重跑"中不可执行的部分。

## 阶段 4 · 遗留清零

1. **owner 定位符 40 条**（全部在 `maintenance/noncore_reviews/pools.yaml`，占 6748 条 consumer 引用的 0.6%，函数名不存在）：
   - `check_content.run` ×28 → `check_content.check`（`scripts/check_content.py:109`）
   - `check_frameworks.audit` ×9 → `check_frameworks.check_frameworks`（`scripts/check_frameworks.py:7`）
   - `build_frameworks.build` ×2 → `world_frameworks.build`（`scripts/world_frameworks.py:60`）
   - `roll_opening.compatibility_reasons` ×1 → 需重新 rg 定位（`scripts/roll_opening.py` 无顶层定义）
   - 改完走 `material_registry.py --sync --decisions` → `qa.py --full --update-fingerprint`。
2. **登记-only 项**（报告 §3）：`legacy_weight` 死值（报告称 `roll_opening.py:316`）、3 个时代名池缺失（传媒舆论危机期/契约共存时代/远途休假季）、templates 近重复 7 对。
3. **G10 遗留**：动力舱维修工玩家侧时代映射。
4. **框架级 `bridge_status`**：`authoring/frameworks/mat-d8ec69422b1354538ef3c705f4beb804.yaml`（幕末町屋与道场）仍为 `bridge_required`（`material.bridge_explanation` 已填）。这与单元级 `BRIDGE_REQUIRED=0` 不是同一口径，报告 §2 需加一句限定，否则"全闭合"会被误读为框架级也无待办。
5. **244 重复候选**：当前 `scripts/check_duplicates.py` 输出 `reviewed_candidates 5 / unresolved 0`，244 不可复现 → 报告改成工具可复现的口径或删数。

## 阶段 5 · CI 与发布

- 按 D3 处置 tag。若要让远端真正承担门禁：先在本地 `python3.10`/`3.13` 各跑一次 `qa.py --full`（本轮全部为 3.12），再依赖矩阵。
- `quality.yml` 的三条 gate（registry / framework review / duplicate + playtest）已在本地验证为真门禁，无需改；除非 D3 选 C，否则不动 workflow。

## 风险

- **顺序风险**：阶段 2 落地后若忘记先归档旧批，`qa.py --full --release` 会报 80 条 `PLAYTEST_INVALID`，容易被误判成回归。
- **归因风险**：阶段 1 若对 v2 批套用 v3 专属规则，会把 Δ口径 高估，反而给第二轮修复记错功。
- **成本**：阶段 1 = 80 或 160 份评审（无生成）；阶段 3 = 80 框架×模式×4 回合模型请求 + 80 份评审，是唯一的高成本段。
- **证据风险**：阶段 3 期间顶层不能保留部分新批部分旧批的状态。

## 完成定义

- 阶段 0：报告 9 处改动完成，`qa.py --full` 291 passed，`PROGRESS.md`/`README.md` 同步。
- 阶段 1：`maintenance/attribution_report.md` 给出 Δ协议/Δ素材/Δ口径 三个差值与分母；两批 review 均通过逐字引文校验。
- 阶段 2：`PROTOCOL` 与 `playtest_report.py:53` 同步为 v4，旧批已归档，v4 简报在库，`qa.py --full` 绿。
- 阶段 3：顶层 80 份为 v4 协议 + 新素材，`qa.py --full --release` 结果如实记录（全绿或明确残留）。
- 阶段 4：owners 40 条修正并落库，登记-only 三项有处置记录，§2 口径限定补上。
- 阶段 5：tag/CI 状态与报告表述一致。
