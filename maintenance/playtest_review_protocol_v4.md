# 实玩独立评分简报 v4（non-explicit-runtime-brief-v4）

适用对象：`scripts/run_playtest.py` 以 PROTOCOL v4 生成的非露骨叙事探针 transcript。评分者必须独立于生成器（reviewer ≠ generator），逐案例输出 `<stem>.review.yaml` 与 transcript 同目录。

v3 简报（`maintenance/playtest_review_protocol_v3.md`）作为历史口径保留，用于 `maintenance/playtests/stale-input-v3/`、`maintenance/playtests/stale-input-v4/` 与 `maintenance/playtests/terminal-v3/` 等历史批次；本文件的八条校准与 v3 逐字一致，只追加第 9 条。

## 结构与门槛（与 v2/v3 相同，来自 maintenance/baseline.yaml）

- 每案例 4 回合（开局+3 续写），五维各 0–2 分：`world_specificity`、`character_credibility`、`meaningful_choices`、`consequence_continuity`、`natural_expression`。
- 回合分=五维合计；案例分=最低回合分；任一维 0 分或回合分 <8 或 blocking_findings 非空即失败。门槛不随轮次调整。
- 每维 evidence 必须是该回合正文的**逐字子串**（`playtest_report.py` 用 `in prose` 校验，引文不在正文=untraceable）。案例级 scores/evidence 取最低回合。

## review.yaml 字段

`framework_id / name / mode / transcript_sha256（=sha256(transcript 文件字节)）/ reviewer / protocol: non-explicit-runtime-brief-v4 / aggregation: lowest_scoring_turn_with_all_turns_required_to_pass / scores{五维} / evidence{五维引文} / total / passed / blocking_findings[] / turn_reviews[{turn, scores, evidence, reason, blocking_findings, total, passed}] / summary`

## 评分校准（第 1–8 条与 v3 简报逐字相同）

1. **「我」声明=玩家授权**。续写请求以第一人称声明动作（如「我再亲手做一件现在能帮忙、当场有结果的小事」）。模型写出该动作的执行过程与可观察结果**不构成**「替玩家决定」，meaningful_choices 不得仅因此判 0。只有模型替玩家发表**未声明**的台词、立场、异议内容或关键选择（例如替玩家指定异议对象、替玩家向第三方承诺）才是 agency 越界。
2. **appellations 内称呼不算错**。package 中 `appellations` 列表列出的称呼（如「师傅」「先生」）被 NPC 用于称呼玩家，不构成角色错认或扣分依据。
3. **时间词逐字一致**。续写③请求「今天到此为止」；正文把告别写成「明天」是时间连续性错误，按 `consequence_continuity` 或 `natural_expression` 扣分。
4. **出口/免责复述**。v3 规则要求出口信息只首次提及、免责话术不堆叠。逐回合复述出口或不绑定具体取舍的免责清单是 `natural_expression` 扣分依据。
5. **活动推进**。每回合核心活动须有可观察进展或写明受阻原因。四回合停在邀请、选项复述、无结果悬置，是 `meaningful_choices`/`consequence_continuity` 扣分依据。
6. **凭空状态变化**。世界状态变化（黑板字、放置、移交、资源占用变化）若无前置动作描写支撑，是 `world_specificity` 0 分候选——这是硬阻断（事实捏造）。
7. **natural_expression 扣分须有具体依据**。仅因句式克制、对白以事务为主而不指出具体复用句或元叙述，不构成扣 1 分的理由。
8. **blocking_findings 只放真阻断**：越权操作、凭空事实、替玩家锁定关键选择、时间连续性破坏。7 分类质量瑕疵写入 reason，不进 blocking。
9. **被异议条款须逐字见于前文**（v4 新增）。续写②提出的被异议义务/安排，必须能在前文（尤其续写①）正文中逐字找到对应句子。模型在异议回合当场书写一条再声称其为旧有安排，即属凭空事实：按第 6 条判 `world_specificity` 0 并记 blocking_findings（写明是哪一句被现写、与哪一句前文矛盾）。同一回合里把前文**根本没有出现过的第二项**一并说成「你不接的旧安排」，同样按第 6/9 条处理（即使真实条款的协商结构合规，blocking 仍成立）。反过来，异议回合若主张「前文没有可议条款」，评分者须先核对前文：前文已写出可被引用的具体安排而模型仍主张没有，属**规避协商**，记入该回合 reason 与案例 summary（不单独阻断，但必须写明前文哪一句本可引用）；前文确实没有写出任何可引用安排，才不扣分。**此条只适用于协议 v4 转写，不得倒套到 v2/v3 旧批**；反过来，本批若出现该形态也不得按「协商结构合规」从宽。

## 产出纪律

- 评分前重读 transcript 全部 4 回合与 record 内 request 原文；对照 package（selection/package/committed_opening）判断素材是否被忠实使用。
- 不修改 transcript、不重跑生成、不调门槛；评分结论失败就如实失败。
- 案例通过条件全部由 `playtest_report.py` 机器复核，评分者不需要也不应该放宽任何一项来「帮助通过」。
