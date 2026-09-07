# 叙事存档槽

`saves/current_state.yaml` 是会话工作活档：`build_opening.py --complete` 写入它，`commit_turn.py` 默认 `--state` 指向它。命名槽在 `slots/<slot>/state.yaml` + `manifest.yaml`；`legacy/` 只读。旧 manifest 可能残留 `branch_id`/`revision` 等已废弃 CAS 字段，忽略即可。新 manifest 使用版本 2，并以 `state_sha256` 校验两个文件是否属于同一次提交。

CLI 以 `python scripts/manage_saves.py --help` 为准（list / load / init / save）。覆盖保存必须带载入时观察到的 `updated_at`（`--expected-updated-at`），不匹配即拒绝写入。自然语言命令到 CLI 的映射见 SKILL.md「命令」一节。

槽名允许中文，空格改 `-`。`.write.lock` 保护状态的读改写提交，不影响回合号、事件 ID、边界、同意或叙事主权。开局历史默认按工作副本隔离并最多保留 200 条；需要测试或自定义位置时可设置 `ADULT_TENSION_HISTORY_PATH`。
