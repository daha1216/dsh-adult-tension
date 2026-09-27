<!-- 本文件由 tools/gen_references.py 生成，不要手改。 -->

# 命令参考

调用：`<python> scripts/adult_tension.py <command> --json [--input-file PATH] [--data-dir PATH]`

- 输入是一个 JSON 对象，来自 `--input-file`（UTF-8，可带 BOM）。需要输入的命令在没有 `--input-file` 且 stdin 不是终端时读取 stdin；可选输入只从 `--input-file` 读取（`--input-file -` 表示 stdin）。
- 输出是一个信封 `{"ok", "data", "error"}`，以 UTF-8 字节写到 stdout。成功与失败都附带 `next_request_id`（成功在 `data` 里，失败在 `error` 里）。
- 全局参数：`--json`（输出 JSON，始终如此）、`--pretty`（缩进输出）、`--debug`（日志记录输入）、`--input-file PATH`、`--data-dir PATH`。

## 命令一览

| 命令 | 类别 | 输入 | 作用 | 专用参数 |
|---|---|---|---|---|
| `doctor` | diagnostic | 无 | 检查环境并完成首次初始化（幂等） | — |
| `version` | read | 无 | Skill、内容、存档格式、RNG 版本 | — |

## 错误码

| 码 | 含义 | 退出码 |
|---|---|---|
| `INVALID_INPUT` | 输入格式或字段错误 | 10 |
| `STALE_REVISION` | expected_revision 过期；错误中附当前 revision 与简要上下文 | 10 |
| `IDEMPOTENCY_CONFLICT` | 同一 request_id 携带了不同的内容 | 10 |
| `INVARIANT_VIOLATION` | 违反领域规则（冷却、知识边界、授权、幅度等） | 10 |
| `SAFETY_BLOCK` | 与硬边界冲突、暂停中、年龄问题 | 10 |
| `CONTENT_ERROR` | 内容包或自定义世界校验失败 | 10 |
| `NOT_FOUND` | 会话、存档、角色、事件不存在 | 10 |
| `SLOT_CONFLICT` | 存档名已被占用（exists），或本局当前槽已在别的对话里被写过（changed_elsewhere） | 10 |
| `UNSUPPORTED_VERSION` | 存档、数据库或内容版本不受支持 | 20 |
| `RUNTIME_UNSUPPORTED` | Python 版本过低或缺少 SQLite 等必要能力 | 20 |
| `DATA_DIR_UNAVAILABLE` | 数据目录不可写；附尝试过的路径与建议 | 20 |
| `STORAGE_BUSY` | 数据库被其他进程短暂占用；用同一 request_id 重试 | 20 |
| `NO_MATCH` | 开局约束在所选世界中无法满足；附冲突的约束与可放宽项 | 10 |
| `MIGRATION_FAILED` | 数据库迁移失败，已恢复迁移前的备份 | 20 |
| `INTERNAL_ERROR` | 未预期错误；附日志位置，状态不变 | 30 |

## 退出码

| 退出码 | 类别 |
|---|---|
| 0 | 成功 |
| 10 | 输入与领域错误：按 `details` 修正后重交 |
| 20 | 环境错误：Python、数据目录、存储占用、版本 |
| 30 | 内部错误：状态不变，附日志位置 |
