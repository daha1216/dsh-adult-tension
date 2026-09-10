# v4 草案批次（已废弃）

本目录是协议 v4 首轮试点批次的归档：9 份转写 + 3 份独立评分（reviewer=`glm-independent-review-v4`，按 `maintenance/playtest_review_protocol_v4.md` 评分）。

废弃原因：试点 4 例中 `mat-d8ec69422b1354538ef3c705f4beb804-daily`（幕末町屋与道场·日常）在异议回合把「往后替人过问松紧」说成玩家拒过的旧安排，而该条只在本回合的木牌背面被现写——正是 v4 第 9 条要挡的「回溯补植」，world_specificity=0 且 blocking 成立（案例 6/10，失败）。同批 `mat-3f430a8a5ab95accb2a0db0ae2ceb369-pressure`（第二轮唯一残留案）在新协议下达到 10/10，说明 v4 对原失败案有效，但覆盖不了全部补植形态。

因此 v4 在冻结前修订（当时未提交任何 v4 证据，故不加版本号）：

- `scripts/run_playtest.py` `FOLLOWUPS[1]`：增加「逐字引用前文原句并写明出处、只议这一条」。
- `scripts/run_playtest.py` 规则串：增加「不得把前文未出现的第二项一并当作旧有安排」「前文确无新增义务时据实说明并确认既有进展，不得为凑异议而编造」。
- `maintenance/playtest_review_protocol_v4.md` 第 9 条：同步补充上述两种形态的判定，并注明「据实说明没有可议条款」不扣分。

本目录转写按修订前措辞生成，**不得作为发布证据**，只作修订依据留档。
