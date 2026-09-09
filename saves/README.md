# 叙事存档槽

新局默认使用唯一的 `saves/sessions/<uuid>/state.yaml`，相同 seed 也不会共用工作档。`--session ID` 可指定稳定会话；后台 brief/切片返回 session、绝对 state_path、原始字节 SHA256 state_token。它们只用于宿主绑定，不加入 v3 状态。

`commit_turn.py` 不提供全局工作档默认值：必须使用 `--session ID --expected-state-token TOKEN` 或显式 `--state PATH`。旧文件仍兼容 `--state saves/current_state.yaml`；携带 token 时也在锁内校验。过期拒绝写入，重新读取切片并判断 patch，成功后记录新 token。

`build_opening --out` 单独使用只写指定工件；`--working` 保留自定义工作路径，`--no-working` 只写输出。`--session` 不能与 `--no-working` 混用，与 `--working` 同用时必须指向同一会话。输出已存在或状态写入失败不追加开局历史。

命名槽在 `slots/<slot>/state.yaml` + `manifest.yaml`，与工作会话独立；`legacy/` 只读。旧 manifest 多余字段可忽略；v1 可读取，保存时升级为 v2。v2 用 state_sha256 校验存档对，读取、解析和校验都基于同锁快照；保存失败恢复先前有效文件对，初始化失败不留可用槽。

CLI 以 `python scripts/manage_saves.py --help` 为准（list / load / init / save）。覆盖保存必须带最近载入或成功保存返回的 updated_at（`--expected-updated-at`），不匹配即拒绝。load CLI 只返回 manifest；宿主用 SaveStore.load_slot 返回的已校验状态建立独立会话副本，流程仍见 [状态总结](../references/状态总结.md#载入流程)，命令解析以 `commands.yaml` 为准。

槽名允许中文，空格改 `-`。`.write.lock` 保护状态的读改写提交，不影响回合号、事件 ID、边界、同意或叙事主权。开局历史默认按工作副本隔离并最多保留 200 条；需要测试或自定义位置时可设置 `ADULT_TENSION_HISTORY_PATH`。

终态事件保留在 events 中，不做物理归档。提交回执 event_changes 带新 resolved/cancelled 结果；`python scripts/live_slice.py --session <session> --event <ID>` 可定向读取 outcome，普通 pending 上限不变。载入与续玩不重复新局的三个标题。
