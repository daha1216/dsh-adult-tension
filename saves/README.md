# Narrative Save Slots

`saves/current_state.yaml` 是会话工作活档：`build_opening.py --complete` 写入它，`commit_turn.py` 默认 `--state` 指向它。命名槽在 `slots/<slot>/state.yaml` + `manifest.yaml`；`legacy/` 只读。旧 manifest 可能残留 `branch_id`/`revision` 等已废弃 CAS 字段，忽略即可——冲突检测只用 `updated_at`。

CLI 以 `python scripts/manage_saves.py --help` 为准（list / load / init / save）。覆盖保存必须带载入时观察到的 `updated_at`（`--expected-updated-at`），不匹配即拒绝写入。自然语言命令到 CLI 的映射见 SKILL.md「命令」一节。

槽名允许中文，空格改 `-`。`.write.lock` 只是 manage_saves.py 原子提交的咨询锁，不影响回合号、事件 ID、边界、同意或叙事主权。
