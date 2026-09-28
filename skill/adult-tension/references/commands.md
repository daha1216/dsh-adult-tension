<!-- 本文件由 tools/gen_references.py 生成，不要手改。 -->

# 命令参考

调用：`<python> scripts/adult_tension.py <command> --json [--input-file PATH] [--data-dir PATH]`

- 输入是一个 JSON 对象，来自 `--input-file`（UTF-8，可带 BOM）。需要输入的命令在没有 `--input-file` 且 stdin 不是终端时读取 stdin；可选输入只从 `--input-file` 读取（`--input-file -` 表示 stdin）。
- 输出是一个信封 `{"ok", "data", "error"}`，以 UTF-8 字节写到 stdout。成功与失败都附带 `next_request_id`（成功在 `data` 里，失败在 `error` 里），下一次写操作直接用它。
- 全局参数：`--json`（输出 JSON，始终如此）、`--pretty`（缩进输出）、`--debug`、`--input-file PATH`、`--data-dir PATH`。
- 写操作都带 `request_id`；会话内的写操作还带 `session_id` 与 `expected_revision`。同一 `request_id` + 同一输入重放时返回原响应并标记 `replayed: true`。
- 开发开关（环境变量，由测试环境设置，玩家不需要）：`ADULT_TENSION_HOME` 指定数据目录；`ADULT_TENSION_INCLUDE_DRAFTS=1` 让未发布的世界参与开局与世界列表。

## 命令一览

| 命令 | 类别 | 输入 | 作用 | 专用参数 |
|---|---|---|---|---|
| `commit-turn` | session_write | 必填 | 叙事回合：提交操作，返回结果与下一回合上下文 | — |
| `delete-slot` | session_write | 必填 | 删除存档（需要 confirm: true） | — |
| `doctor` | diagnostic | 无 | 检查环境并完成首次初始化（幂等） | — |
| `export-save` | read | 必填 | 把会话或存档导出为文件（带完整性校验值） | — |
| `get-context` | read | 必填 | 当前上下文（brief / full）；可带快进预览 preview_time 与转折候选 want_twist | — |
| `import-save` | create | 必填 | 导入导出文件，得到一个新会话（可同时写入存档槽） | — |
| `list-sessions` | read | 可选 | 最近的会话（续玩、恢复） | — |
| `list-slots` | read | 无 | 存档列表 | — |
| `list-worlds` | read | 可选 | 世界列表、一句话介绍、支持的模式 | `--include-drafts` |
| `load-slot` | create | 必填 | 读档：创建新的会话副本，原存档不变 | — |
| `new-game` | create | 必填 | 开局 | `--include-drafts` |
| `save-slot` | session_write | 必填 | 存档（省略名字时存到当前槽或自动命名） | — |
| `set-boundary` | session_write | 必填 | 登记或撤销硬边界 | — |
| `set-preferences` | session_write | 必填 | 内心可见、叙事助手、离屏推演、语态、人称、配对偏好 | — |
| `set-safety` | session_write | 必填 | 暂停、恢复、换个场景 | — |
| `smoke` | dev | 可选 | 在临时数据目录用假叙述者跑一条短局 | `--seed`、`--turns` |
| `status` | read | 必填 | 状态：brief 六行 / detail 状态+ / debug 调试 | — |
| `undo-turn` | session_write | 必填 | 撤销上一回合（最多退到本次读档或开局） | — |
| `verify-content` | dev | 可选 | 校验全部内容（结构、语义、时代、固定种子开局、多样性） | `--world`、`--stats`、`--skip-diversity`、`--file` |
| `version` | read | 无 | Skill、内容、存档格式、RNG 版本 | — |

## 输入字段

### `commit-turn`

操作列表的字段见 `references/operations.md`。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | 字符串，≤40 字，会话 ID，形如 s_1a2b3c4d | 是 |  |
| `request_id` | 字符串，≤64 字，8–64 位 [A-Za-z0-9_-]；直接用上一次返回的 next_request_id | 是 |  |
| `expected_revision` | 整数 1..1000000000 | 是 | 上一次返回的 revision |
| `action_mode` | 枚举：`result` / `attempt` / `rewrite` / `continue` / `wait` | 是 | result / attempt / rewrite（“其实……”）/ continue / wait |
| `player_input` | 字符串，≤2000 字 | 是 | 玩家这一句的原话（继续时可为空字符串） |
| `player_authorized` | 布尔 | 否，默认 `false` | 玩家本人的话授权了玩家角色的移动、承诺、交易、同意、转折或设定修改时为 true |
| `acts_on` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}，0–8 项） 或 null | 否，默认 `null` | 玩家行动作用到的 NPC（身体、意志、财物）；attempt 不作用于任何 NPC 时写 [] |
| `operations` | 数组（操作对象（按 `op` 区分），0–40 项） | 是 | 操作列表（可以为空数组） |
| `content_tags` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}，0–12 项） | 是 | 本回合正文涉及的内容标签（可为空数组）；标签表见完整上下文的 tags |
| `intimate_participants` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}，0–6 项） | 否，默认 `[]` | content_tags 含 intimate 或 explicit 时必填：亲密参与者（含玩家） |
| `summary` | 字符串，≤120 字 | 是 | 本回合发生了什么，第三方视角，≤120 字 |
| `open_action` | 字符串，≤80 字 | 是 | 回合停在哪里、谁在等谁，≤80 字 |
| `quotes` | 数组（字符串，≤80 字，0–3 项） | 否，默认 `[]` | ≤3 条对后续有意义的原话，每条 ≤80 字 |
| `chapter_summary` | 字符串，≤300 字 或 null | 否，默认 `null` | 上下文 requests.chapter_summary 为 true 时必填：上一章（到上一回合为止）的摘要，≤300 字；没有要求时不写 |
| `prologue` | 字符串，≤300 字 或 null | 否，默认 `null` | 上下文 requests.prologue 为 true 时必填：把完整上下文 prologue_merge 里的旧前情与最早几章合并成一段前情，≤300 字；没有要求时不写 |
| `replaces_turn` | 整数 1..1000000 或 null | 否，默认 `null` | “刚才不算，改成……”：填当前最后一个回合的回合号，引擎在同一事务里撤销它再应用本次提交 |

### `delete-slot`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | 字符串，≤40 字，会话 ID，形如 s_1a2b3c4d | 是 |  |
| `request_id` | 字符串，≤64 字，8–64 位 [A-Za-z0-9_-]；直接用上一次返回的 next_request_id | 是 |  |
| `expected_revision` | 整数 1..1000000000 | 是 | 上一次返回的 revision |
| `name` | 字符串，≤60 字 | 是 |  |
| `confirm` | 布尔 | 否，默认 `false` | 玩家确认删除后才为 true |

### `export-save`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | 字符串，≤40 字，会话 ID，形如 s_1a2b3c4d 或 null | 否，默认 `null` | 导出这个会话的当前状态 |
| `slot` | 字符串，≤60 字 或 null | 否，默认 `null` | 或导出这个存档 |
| `path` | 字符串，≤400 字 或 null | 否，默认 `null` | 玩家明确给出的绝对路径（.json）；不给时写到数据目录的 exports/ |
| `overwrite` | 布尔 | 否，默认 `false` |  |

### `get-context`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | 字符串，≤40 字，会话 ID，形如 s_1a2b3c4d | 是 |  |
| `depth` | 枚举：`brief` / `full` | 否，默认 `"brief"` |  |
| `preview_time` | 对象（预览推进） 或 null | 否，默认 `null` | 快进预览：返回目标时钟、将到期的事件与确定性结果、必须写离屏片段的 NPC（附目标与信息集）、将到期的状态；不改变状态 |
| `want_twist` | 布尔 | 否，默认 `false` | 玩家说“来点转折”时为 true：返回 2–3 个类别不同的转折候选 |

#### `preview_time` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `minutes` | 整数 1..43200 | 否 |  |
| `until` | 枚举：`morning` / `noon` / `evening` / `night` / `next_morning` | 否 |  |
| `days` | 整数 1..30 | 否 |  |

### `import-save`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `request_id` | 字符串，≤64 字，8–64 位 [A-Za-z0-9_-]；直接用上一次返回的 next_request_id | 是 |  |
| `path` | 字符串，≤400 字 或 null | 否，默认 `null` | 导出文件的路径 |
| `data` | 导出的 JSON 对象 或 null | 否，默认 `null` | 或玩家粘贴的导出内容（整个 JSON 对象） |
| `slot` | 字符串，≤60 字 或 null | 否，默认 `null` | 同时写入这个存档槽（可省略） |
| `overwrite` | 布尔 | 否，默认 `false` | 存档名已被占用时，玩家确认覆盖 |

### `list-sessions`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `limit` | 整数 1..20 | 否，默认 `10` |  |

### `list-worlds`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `include_drafts` | 布尔 | 否，默认 `false` |  |

### `load-slot`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `request_id` | 字符串，≤64 字，8–64 位 [A-Za-z0-9_-]；直接用上一次返回的 next_request_id | 是 |  |
| `name` | 字符串，≤60 字 | 是 |  |

### `new-game`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `request_id` | 字符串，≤64 字，8–64 位 [A-Za-z0-9_-]；直接用上一次返回的 next_request_id | 是 |  |
| `mode` | 枚举：`daily` / `pressure` / `random` 或 null | 否，默认 `null` | daily 日常 / pressure 有压力 / random 玩家明确说“随便”时；replay 时可省略 |
| `seed` | 整数 1..999999 或 null | 否，默认 `null` |  |
| `replay` | 布尔 | 否，默认 `false` | “重开 N 号”：按本机记录的该种子开局条件复现 |
| `locks` | 对象（锁定） | 否，默认 `{}` |  |
| `excludes` | 对象（排除） | 否，默认 `{}` |  |
| `player` | 对象（玩家设定） | 否，默认 `{}` |  |
| `npc_gender_preference` | 枚举：`any` / `mostly_female` / `mostly_male` / `female_only` / `male_only` / `mixed` | 否，默认 `"any"` |  |
| `custom_world` | 自定义世界包 或 null | 否，默认 `null` |  |
| `preferences` | 对象（偏好） | 否，默认 `{}` |  |
| `include_drafts` | 布尔 | 否，默认 `false` |  |

#### `locks` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `world_id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} 或 null | 否，默认 `null` |  |
| `location_id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} 或 null | 否，默认 `null` |  |
| `combo_id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} 或 null | 否，默认 `null` |  |
| `activity_id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} 或 null | 否，默认 `null` |  |
| `pressure_id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} 或 null | 否，默认 `null` |  |
| `hook_id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} 或 null | 否，默认 `null` |  |
| `identity_id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} 或 null | 否，默认 `null` |  |

#### `excludes` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `content_tags` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}，0–20 项） | 否，默认 `[]` |  |
| `world_ids` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}，0–20 项） | 否，默认 `[]` |  |
| `location_ids` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}，0–20 项） | 否，默认 `[]` |  |

#### `player` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `gender` | 枚举：`female` / `male` / `nonbinary` 或 null | 否，默认 `null` |  |
| `age` | 整数 0..120 或 null | 否，默认 `null` |  |
| `age_band` | 数组（整数 0..120，2–2 项） 或 null | 否，默认 `null` |  |
| `identity_hint` | 字符串，≤20 字 或 null | 否，默认 `null` |  |
| `social_position` | 枚举：`low` / `equal` / `high` 或 null | 否，默认 `null` |  |
| `name` | 字符串，≤12 字 或 null | 否，默认 `null` |  |
| `title` | 字符串，≤12 字 或 null | 否，默认 `null` |  |

#### `preferences` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `inner_view` | 布尔 | 否 |  |
| `assistant` | 布尔 | 否 |  |
| `offscreen_simulation` | 布尔 | 否 |  |
| `person` | 枚举：`second` / `first` / `third` | 否 |  |

### `save-slot`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | 字符串，≤40 字，会话 ID，形如 s_1a2b3c4d | 是 |  |
| `request_id` | 字符串，≤64 字，8–64 位 [A-Za-z0-9_-]；直接用上一次返回的 next_request_id | 是 |  |
| `expected_revision` | 整数 1..1000000000 | 是 | 上一次返回的 revision |
| `name` | 字符串，≤60 字 或 null | 否，默认 `null` |  |
| `overwrite` | 布尔 | 否，默认 `false` |  |
| `save_as` | 布尔 | 否，默认 `false` |  |

### `set-boundary`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | 字符串，≤40 字，会话 ID，形如 s_1a2b3c4d | 是 |  |
| `request_id` | 字符串，≤64 字，8–64 位 [A-Za-z0-9_-]；直接用上一次返回的 next_request_id | 是 |  |
| `expected_revision` | 整数 1..1000000000 | 是 | 上一次返回的 revision |
| `action` | 枚举：`add` / `remove` | 是 | add 登记 / remove 撤销 |
| `text` | 字符串，≤80 字 或 null | 否，默认 `null` | 玩家的原话，例如“不要涉及怀孕” |
| `tags` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}，0–6 项） | 否，默认 `[]` | 映射到的内容标签；映射不上就留空（记为 custom，由你自己遵守） |
| `boundary_id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} 或 null | 否，默认 `null` | 撤销时可用边界 ID |

### `set-preferences`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | 字符串，≤40 字，会话 ID，形如 s_1a2b3c4d | 是 |  |
| `request_id` | 字符串，≤64 字，8–64 位 [A-Za-z0-9_-]；直接用上一次返回的 next_request_id | 是 |  |
| `expected_revision` | 整数 1..1000000000 | 是 | 上一次返回的 revision |
| `inner_view` | 布尔 | 否 |  |
| `assistant` | 布尔 | 否 |  |
| `offscreen_simulation` | 布尔 | 否 |  |
| `person` | 枚举：`second` / `first` / `third` | 否 |  |
| `npc_gender_preference` | 枚举：`any` / `mostly_female` / `mostly_male` / `female_only` / `male_only` / `mixed` | 否 |  |
| `voice` | 对象（语态） | 否 |  |

#### `voice` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `npc_id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `voice` | 枚举：`surface` / `inner` | 是 |  |

### `set-safety`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | 字符串，≤40 字，会话 ID，形如 s_1a2b3c4d | 是 |  |
| `request_id` | 字符串，≤64 字，8–64 位 [A-Za-z0-9_-]；直接用上一次返回的 next_request_id | 是 |  |
| `expected_revision` | 整数 1..1000000000 | 是 | 上一次返回的 revision |
| `paused` | 布尔 | 是 | true 暂停 / false 恢复 |
| `change_scene` | 布尔 | 否，默认 `false` | “换个场景”：保持暂停，换到新的非亲密场景 |

### `smoke`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `seed` | 整数 1..999999 | 否，默认 `42` |  |
| `turns` | 整数 2..60 | 否，默认 `8` |  |

### `status`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | 字符串，≤40 字，会话 ID，形如 s_1a2b3c4d | 是 |  |
| `level` | 枚举：`brief` / `detail` / `debug` | 否，默认 `"brief"` | brief 六行 / detail 状态+ / debug 调试 |

### `undo-turn`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | 字符串，≤40 字，会话 ID，形如 s_1a2b3c4d | 是 |  |
| `request_id` | 字符串，≤64 字，8–64 位 [A-Za-z0-9_-]；直接用上一次返回的 next_request_id | 是 |  |
| `expected_revision` | 整数 1..1000000000 | 是 | 上一次返回的 revision |

### `verify-content`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `world` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} 或 null | 否，默认 `null` |  |
| `stats` | 布尔 | 否，默认 `false` |  |
| `skip_diversity` | 布尔 | 否，默认 `false` |  |
| `file` | 字符串，≤400 字 或 null | 否，默认 `null` | 只校验这一个世界包文件（写作中的源文件或 new-world 骨架） |

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
