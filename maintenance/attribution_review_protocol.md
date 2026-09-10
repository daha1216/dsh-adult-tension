# 补评评分简报（第二轮归因与可复现评分）

用途：对**已归档**的实玩转写做评分侧补评，用于"协议 / 素材 / 评分口径"三段归因，以及后续批次的可复现独立评分。本文件不改变任何门槛：维度、聚合与门槛仍以 `maintenance/baseline.yaml`（`minimum_score: 8`）和 `scripts/playtest_report.py` 的机器复核为准。

评分者必须独立于生成器（reviewer ≠ generator），逐案例输出 `<stem>.review.yaml`。

## 维度与门槛（与 `maintenance/playtest_review_protocol_v3.md` 一致）

- 每案例 4 回合（开局 + 3 续写），五维各 0–2 分：`world_specificity`、`character_credibility`、`meaningful_choices`、`consequence_continuity`、`natural_expression`。
- 回合分 = 五维合计；案例分 = 最低回合分；任一维 0 分或回合分 < 8 或 `blocking_findings` 非空即失败。门槛不随轮次调整。
- 每维 `evidence` 必须是该回合正文的**逐字子串**（机器用 `in prose` 校验，引文不在正文即 untraceable）。

## 批次适用（重要，决定用哪几条校准）

| 批次 | 协议 | 素材 | 用哪些校准 |
| --- | --- | --- | --- |
| `maintenance/playtests/stale-input-v4/*.json` | v3 | 修复前 | 第 1–8 条全用 |
| `maintenance/playtests/stale-input-v3/*.json` | v2 | 修复前 | **只用第 1、2、6、7、8 条** |
| 重跑新批（协议 v4） | v4 | 修复后 | 第 1–8 条全用 |

为什么 v2 批不用第 3、4、5 条：这三条（时间词逐字一致、出口只首提免责不堆叠、每回合活动须有可观察进展）依据的是 v3 规则**新增**的写法要求，v2 批次从未被告知；套用会把"协议效应"重复计进"评分口径效应"。因此 v2 批的补评是**口径对齐版**：只保留评审侧校准（第 1、2、7 条）与通用凭空事实阻断（第 6 条）+ 阻断归置（第 8 条）。

素材漂移：旧批次转写生成于源侧修复之前，`authoring/frameworks/<id>.yaml` 现值可能与当时不同。判分以转写正文自身为准（首回合的「世界观 / 人物 / 正文」标题与各回合动作、状态），框架文件只用于姓名、年龄、称呼核对；**不得**因素材后来被修改而扣分。

## 八条校准（引自 v3 简报，逐字保留）

1. **「我」声明=玩家授权**：v3 续写请求以第一人称声明动作。模型写出该动作的执行过程与可观察结果不构成"替玩家决定"，`meaningful_choices` 不得仅因此判 0。只有模型替玩家发表**未声明**的台词、立场、异议内容或关键选择才是 agency 越界。
2. **appellations 内称呼不算错**：package 中 `appellations` 列出的称呼不构成角色错认或扣分依据。
3. **时间词逐字一致**：续写③请求「今天到此为止」，正文写成「明天」是时间连续性错误。
4. **出口/免责复述**：出口信息只首次提及、免责话术不堆叠；逐回合复述是不绑定取舍的 `natural_expression` 扣分依据。
5. **活动推进**：每回合核心活动须有可观察进展或写明受阻原因；停在邀请、选项复述、无结果悬置是 `meaningful_choices`/`consequence_continuity` 扣分依据。
6. **凭空状态变化**：世界状态变化（书写、放置、移交、资源占用变化）若无前置动作描写支撑，是 `world_specificity` 0 分候选——硬阻断（事实捏造）。
7. **`natural_expression` 扣分须有具体依据**：仅因句式克制、对白以事务为主而不指出具体复用句或元叙述，不构成扣 1 分的理由。
8. **`blocking_findings` 只放真阻断**：越权操作、凭空事实、替玩家锁定关键选择、时间连续性破坏。其余质量瑕疵写入 `reason`。

协议 v4 追加一条（用于 v4 新批）：**被异议条款必须能在前文逐字找到**；在异议回合现场书写某条款再声称其为旧有安排，按第 6 条判 `world_specificity` 0 并记 blocking。

## 输出契约（机器复核）

`framework_id / name / mode / transcript_sha256 / reviewer / protocol / aggregation: lowest_scoring_turn_with_all_turns_required_to_pass / scores{五维} / evidence{五维引文} / total / passed / blocking_findings[] / turn_reviews[{turn, scores, evidence, reason, blocking_findings, total, passed}]（4 条）/ summary`

- `turn_reviews[i].scores` 只对该回合正文评分，`evidence` 只能是该回合正文的子串。
- 案例级 `scores`/`evidence` 必须等于最低回合那一套；`total = sum(scores)`；`passed = (最低回合分 ≥ 8 且无 0 维且无 blocking)`。
- `transcript_sha256`、`reviewer`、`protocol` 由驱动写入要求值，照抄即可。

## 产出纪律

- 只写自己的 review 文件：不修改转写、不重跑生成、不改门槛、不改其他文件。
- 判分失败就如实失败；不要为了"通过"放宽任何一项（所有通过条件最终由 `scripts/playtest_report.py` 机器复核）。
