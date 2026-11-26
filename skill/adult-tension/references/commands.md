<!-- 本文件由 tools/gen_references.py 生成，不要手改。 -->

# 命令参考

调用：`<python> "<本 Skill 目录>/scripts/adult_tension.py" <command> --json [--input-file "<文件>"] [--data-dir "<目录>"]`

- 输入是一个 JSON 对象，来自 `--input-file "<文件>"`（UTF-8，可带 BOM）。需要输入的命令在没有 `--input-file` 且 stdin 不是终端时读取 stdin；可选输入只从 `--input-file` 读取（`--input-file -` 表示 stdin）。Windows 环境或 JSON 载荷含反斜杠 `\`（如文件路径，防 `bash -c` 折叠 `\\`）时，一律写入 UTF-8 临时文件并用 `--input-file "<文件>"` 传入。
- 任何输入都可以带 `"encoding_check": "汉字"`。值不对说明中文在传入途中被终端改坏（例如 PowerShell 5.1 的管道把中文变成 `?`），命令被拒（`INVALID_INPUT`，路径 `$.encoding_check`），改用 `--input-file "<文件>"` 传 UTF-8 文件。这个字段在命令处理之前去掉。
- 输出是一个信封 `{"ok", "data", "error"}`，以 UTF-8 字节写到 stdout。成功与失败都附带 `next_request_id`（成功在 `data` 里，失败在 `error` 里），下一次写操作直接用它。
- 全局参数：`--json`（输出 JSON，默认行为，保留兼容）、`--pretty`（缩进输出）、`--debug`、`--input-file "<文件>"`、`--data-dir "<目录>"`。
- 写操作都带 `request_id`；会话内的写操作还带 `session_id` 与 `expected_revision`。同一 `request_id` + 同一输入重放时返回原响应并标记 `replayed: true`。
- 开局、读档、导入（`new-game`、`load-slot`、`import-save`）与带 `"depth": "full"` 的 `get-context` 另外返回 `commit_template`：会话号已填好的一次记录，`turns` 内含单回合骨架（在场的人和最常用的操作），每个攒下的回合照它写一项；尖括号是要写的内容，`a|b` 表示选一个，用不上的操作删掉。带 `preview_time` 的 `get-context` 另外返回 `skip_template`：快进这一回合的记录，`advance_time` 与每条必需的 `offscreen_beat` 已排好（攒下的回合要先记录，再预览）。
- 开发开关（环境变量，由测试环境设置，玩家不需要）：`ADULT_TENSION_HOME` 指定数据目录；`ADULT_TENSION_INCLUDE_DRAFTS=1` 让未发布的世界参与开局与世界列表；`ADULT_TENSION_TRACE=<文件>` 把每次调用（参数、输入、信封、耗时）追加到该文件，供端到端评测采集。
- 字段类型简写：`ID` = ASCII 小写短标识 `[a-z0-9_]{1,40}`（≤40 字）；`SessionId` = 会话 ID（形如 `s_1a2b3c4d`，≤40 字）；`RequestId` = 8–64 位 `[A-Za-z0-9_-]`（直接用上一次返回的 `next_request_id`）。

## 命令一览

| 命令 | 类别 | 输入 | 作用 | 专用参数 |
|---|---|---|---|---|
| `commit-turn` | session_write | 必填 | 叙事回合：提交操作，返回结果与下一回合上下文 | — |
| `delete-slot` | session_write | 必填 | 删除存档（需要 confirm: true） | — |
| `delete-world` | create | 必填 | 删除保存的世界（需要 confirm: true） | — |
| `doctor` | diagnostic | 无 | 检查环境并完成首次初始化（幂等） | — |
| `export-save` | read | 必填 | 把会话或存档导出为文件（带完整性校验值） | — |
| `get-context` | read | 必填 | 当前上下文（brief / full）；可带快进预览 preview_time 与转折候选 want_twist | — |
| `guide` | read | 可选 | 新玩家的游玩指南（“怎么玩”）：固定文字，原样转述 | — |
| `import-save` | create | 必填 | 导入导出文件，得到一个新会话（可同时写入存档槽） | — |
| `list-sessions` | read | 可选 | 最近的会话（续玩、恢复） | — |
| `list-slots` | read | 无 | 存档列表 | — |
| `list-worlds` | read | 可选 | 世界列表、一句话介绍、支持的模式 | `--include-drafts` |
| `load-slot` | create | 必填 | 读档：创建新的会话副本，原存档不变 | — |
| `my-worlds` | read | 无 | 玩家保存的自定义世界 | — |
| `new-game` | create | 必填 | 开局 | `--include-drafts` |
| `save-slot` | session_write | 必填 | 存档（省略名字时存到当前槽或自动命名） | — |
| `save-world` | create | 必填 | 保存这一局的自定义世界，以后用 new-game 的 my_world 再开 | — |
| `set-boundary` | session_write | 必填 | 登记或撤销硬边界 | — |
| `set-preferences` | session_write | 必填 | 内心可见、叙事助手、离屏推演、语态、人称、配对偏好、节奏、尺度 | — |
| `set-safety` | session_write | 必填 | 暂停、恢复、换个场景 | — |
| `smoke` | dev | 可选 | 在临时数据目录用假叙述者跑一条短局 | `--seed`、`--turns` |
| `status` | read | 必填 | 状态：brief 六行 / detail 状态+ / debug 调试 | — |
| `undo-turn` | session_write | 必填 | 撤销上一回合（最多退到本次读档或开局） | — |
| `verify-content` | dev | 可选 | 校验全部内容（结构、语义、时代、固定种子开局、多样性） | `--world`、`--stats`、`--skip-diversity`、`--file` |
| `version` | read | 无 | Skill、内容、存档格式、RNG 版本 | — |

## 输入字段

### `commit-turn`

每个回合（`turns[]`）的字段与操作列表见 `references/operations.md`。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | `SessionId` | 是 |  |
| `request_id` | `RequestId` | 是 |  |
| `expected_revision` | 整数 1..1000000000 | 是 | 上一次返回的 revision |
| `turns` | 数组（对象（回合），1–12 项） | 是 | 这次记录的回合，按发生的顺序；引擎逐项应用，全有或全无 |

**一次记录**：一次 `commit-turn` 记录 `turns` 里的回合（1–12 项，按发生的顺序）。引擎逐项应用，每项是一个回合，各自可以撤销；任何一项不合法，整次记录被拒、状态不变，错误路径以 `$.turns[i]` 开头。只有第一项可以写 `replaces_turn`；含 `roll`、`twist_accept` 或触发到期事件的回合只能作为 `turns` 的最后一项（须按引擎裁定结果续写正文）。上下文 `requests` 要求的章节摘要、前情写在第一项；记录中途引擎新提出的要求在记录结束时才出现，由下一次记录的第一项补上。返回 `turns`（每项的 `turn`、`applied`、`resolved_events`、`simulation`）、时钟和下一回合的上下文（单次提交多于 1 个回合时返回 `full`；单回合默认返回 `brief`，但在以下 6 种情形亦返回 `full`：上次提交失败后、地点变化、有新角色入场/登场、跨日、出现 `requests.prologue`、或当前回合为 5 的倍数）。

### `delete-slot`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | `SessionId` | 是 |  |
| `request_id` | `RequestId` | 是 |  |
| `expected_revision` | 整数 1..1000000000 | 是 | 上一次返回的 revision |
| `name` | 字符串，≤60 字 | 是 |  |
| `confirm` | 布尔 | 否，默认 `false` | 玩家确认删除后才为 true |

### `delete-world`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `request_id` | `RequestId` | 是 |  |
| `name` | 字符串，≤60 字 | 是 |  |
| `confirm` | 布尔 | 否，默认 `false` | 玩家确认删除后才为 true |

### `export-save`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | `SessionId` 或 null | 否，默认 `null` | 导出这个会话的当前状态（与 slot 二选一，必填其一） |
| `slot` | 字符串，≤60 字 或 null | 否，默认 `null` | 导出这个存档（与 session_id 二选一，必填其一） |
| `path` | 字符串，≤400 字 或 null | 否，默认 `null` | 玩家明确给出的绝对路径（.json）；不给时写到数据目录的 exports/ |
| `overwrite` | 布尔 | 否，默认 `false` |  |

### `get-context`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | `SessionId` | 是 |  |
| `depth` | 枚举：`brief` / `full` | 否，默认 `"brief"` | brief 简要上下文（≤6 KB）/ full 完整上下文（≤32 KB，含人物完整卡、地点、standby_cast、world.scene_ideas 等） |
| `preview_time` | 对象（预览推进） 或 null | 否，默认 `null` | 快进预览：返回目标时钟、将到期的事件与确定性结果、必须写离屏片段的 NPC（附目标与信息集）、将到期的状态；不改变状态 |
| `want_twist` | 布尔 | 否，默认 `false` | 玩家说“来点转折”时为 true：返回 2–3 个类别不同的转折候选 |

#### `preview_time` 的字段

与 advance_time 相同：minutes / until / days 三选一

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `minutes` | 整数 1..43200 | 否 |  |
| `until` | 枚举：`morning` / `noon` / `evening` / `night` / `next_morning` | 否 |  |
| `days` | 整数 1..30 | 否 |  |

### `guide`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | `SessionId` 或 null | 否，默认 `null` | 正在玩的会话；不给时是还没开局的版本 |
| `topic` | 枚举：`play` / `custom_world` | 否，默认 `"play"` | play 怎么玩 / custom_world 自定义世界的灵感清单 |

### `import-save`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `request_id` | `RequestId` | 是 |  |
| `path` | 字符串，≤400 字 或 null | 否，默认 `null` | 导出文件的路径（与 data 二选一，必填其一） |
| `data` | 导出的 JSON 对象 或 null | 否，默认 `null` | 玩家粘贴的导出内容（整个 JSON 对象；与 path 二选一，必填其一） |
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
| `query` | 字符串，≤40 字 或 null | 否，默认 `null` | 玩家问某类题材、时代、地方时的关键词（例如“港口”“民国”），与 new-game 的 world_query 同一套匹配；只列出匹配的世界，最相关的在前，最多 20 个 |
| `tags` | 数组（`ID`，0–10 项） | 否，默认 `[]` | 内容标签 ID（见返回的 tag_counts），只列出同时包含全部指定标签的世界；“有超自然的”是 supernatural |
| `exclude_tags` | 数组（`ID`，0–20 项） | 否，默认 `[]` | 内容标签 ID，排除带有任一指定标签的世界；“不要灾难”是 disaster |

### `load-slot`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `request_id` | `RequestId` | 是 |  |
| `name` | 字符串，≤60 字 | 是 |  |

### `new-game`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `request_id` | `RequestId` | 是 |  |
| `mode` | 枚举：`daily` / `pressure` / `random` 或 null | 否，默认 `null` | daily 日常 / pressure 压力 / random 玩家明确说“随便”时；replay 时可省略 |
| `seed` | 整数 1..999999 或 null | 否，默认 `null` |  |
| `replay` | 布尔 | 否，默认 `false` | “重开 N 号”：按本机记录的该种子开局条件复现 |
| `world_query` | 字符串，≤40 字 或 null | 否，默认 `null` | 玩家点名的世界名称或关键词（例如“港口夜班”“凡尔赛”），运行时按标题、ID、时代、地域与完整简介匹配；唯一命中即开局，多个匹配返回 NO_MATCH 附 candidates，无匹配返回 NOT_FOUND。不与 locks.world_id、custom_world、my_world、replay 同用 |
| `locks` | 对象（锁定） | 否，默认 `{}` |  |
| `excludes` | 对象（排除） | 否，默认 `{}` |  |
| `player` | 对象（玩家设定） | 否，默认 `{}` |  |
| `npc_gender_preference` | 枚举：`any` / `mostly_female` / `mostly_male` / `female_only` / `male_only` / `mixed` | 否，默认 `"any"` |  |
| `custom_world` | 自定义世界包 或 null | 否，默认 `null` | 自定义世界包；不与 my_world、locks.world_id、excludes.world_ids、replay、world_query 同用 |
| `my_world` | 字符串，≤60 字 或 null | 否，默认 `null` | 玩家保存过的世界名（my-worlds 列出），不与 custom_world、locks.world_id、excludes.world_ids、replay、world_query 同用 |
| `preferences` | 对象（偏好） | 否，默认 `{}` |  |
| `include_drafts` | 布尔 | 否，默认 `false` |  |

#### `locks` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `world_id` | `ID` 或 null | 否，默认 `null` |  |
| `location_id` | `ID` 或 null | 否，默认 `null` |  |
| `combo_id` | `ID` 或 null | 否，默认 `null` |  |
| `activity_id` | `ID` 或 null | 否，默认 `null` |  |
| `pressure_id` | `ID` 或 null | 否，默认 `null` |  |
| `hook_id` | `ID` 或 null | 否，默认 `null` |  |
| `identity_id` | `ID` 或 null | 否，默认 `null` |  |

#### `excludes` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `content_tags` | 数组（`ID`，0–20 项） | 否，默认 `[]` |  |
| `world_ids` | 数组（`ID`，0–20 项） | 否，默认 `[]` |  |
| `location_ids` | 数组（`ID`，0–20 项） | 否，默认 `[]` |  |

#### `player` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `gender` | 枚举：`female` / `male` / `nonbinary` 或 null | 否，默认 `null` |  |
| `age` | 整数 0..120 或 null | 否，默认 `null` | 玩家角色年龄（须 ≥ 18，低于 18 返回 SAFETY_BLOCK） |
| `age_band` | 数组（整数 0..120，2–2 项） 或 null | 否，默认 `null` | 年龄区间 [下限, 上限]（下限须 ≥ 18，低于 18 返回 SAFETY_BLOCK；下限 > 上限返回 INVALID_INPUT） |
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
| `pace` | 枚举：`slow` / `standard` / `direct` | 否 | 节奏：slow 慢热 / standard 标准 / direct 直接；只影响写法，不影响规则 |
| `explicitness` | 枚举：`subtle` / `standard` / `explicit` | 否 | 尺度：subtle 含蓄 / standard 标准 / explicit 直白；只影响写法，不影响规则 |

### `save-slot`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | `SessionId` | 是 |  |
| `request_id` | `RequestId` | 是 |  |
| `expected_revision` | 整数 1..1000000000 | 是 | 上一次返回的 revision |
| `name` | 字符串，≤60 字 或 null | 否，默认 `null` |  |
| `overwrite` | 布尔 | 否，默认 `false` |  |
| `save_as` | 布尔 | 否，默认 `false` |  |

### `save-world`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `request_id` | `RequestId` | 是 |  |
| `session_id` | `SessionId` | 是 | 用自定义世界开的这一局 |
| `name` | 字符串，≤60 字 | 是 | 玩家起的名字 |
| `overwrite` | 布尔 | 否，默认 `false` | 玩家确认覆盖同名世界后才为 true |

### `set-boundary`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | `SessionId` | 是 |  |
| `request_id` | `RequestId` | 是 |  |
| `expected_revision` | 整数 1..1000000000 | 是 | 上一次返回的 revision |
| `action` | 枚举：`add` / `remove` | 是 | add 登记 / remove 撤销 |
| `text` | 字符串，≤80 字 或 null | 否，默认 `null` | 玩家的原话，例如“不要涉及怀孕”（action 为 add 时必填；remove 时与 boundary_id 至少填一个） |
| `tags` | 数组（`ID`，0–6 项） | 否，默认 `[]` | 映射到的内容标签；映射不上就留空（记为 custom，由你自己遵守） |
| `boundary_id` | `ID` 或 null | 否，默认 `null` | 撤销时可用边界 ID（action 为 remove 时与 text 至少填一个） |

### `set-preferences`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | `SessionId` | 是 |  |
| `request_id` | `RequestId` | 是 |  |
| `expected_revision` | 整数 1..1000000000 | 是 | 上一次返回的 revision |
| `inner_view` | 布尔 | 否 |  |
| `assistant` | 布尔 | 否 |  |
| `offscreen_simulation` | 布尔 | 否 |  |
| `person` | 枚举：`second` / `first` / `third` | 否 |  |
| `npc_gender_preference` | 枚举：`any` / `mostly_female` / `mostly_male` / `female_only` / `male_only` / `mixed` | 否 |  |
| `pace` | 枚举：`slow` / `standard` / `direct` | 否 | 节奏：slow 慢热 / standard 标准 / direct 直接；只影响写法，不影响规则 |
| `explicitness` | 枚举：`subtle` / `standard` / `explicit` | 否 | 尺度：subtle 含蓄 / standard 标准 / explicit 直白；只影响写法，不影响规则 |
| `voice` | 对象（语态） | 否 |  |

#### `voice` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `npc_id` | `ID` | 是 |  |
| `voice` | 枚举：`surface` / `inner` | 是 |  |

### `set-safety`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | `SessionId` | 是 |  |
| `request_id` | `RequestId` | 是 |  |
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
| `session_id` | `SessionId` | 是 |  |
| `level` | 枚举：`brief` / `detail` / `debug` | 否，默认 `"brief"` | brief 六行 / detail 状态+ / debug 调试 |

### `undo-turn`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | `SessionId` | 是 |  |
| `request_id` | `RequestId` | 是 |  |
| `expected_revision` | 整数 1..1000000000 | 是 | 上一次返回的 revision |

### `verify-content`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `world` | `ID` 或 null | 否，默认 `null` |  |
| `stats` | 布尔 | 否，默认 `false` |  |
| `skip_diversity` | 布尔 | 否，默认 `false` |  |
| `file` | 字符串，≤400 字 或 null | 否，默认 `null` | 只校验这一个世界包文件（写作中的源文件或 tools/new_world.py 骨架） |

## 错误码

| 码 | 含义 | 退出码 |
|---|---|---|
| `INVALID_INPUT` | 输入格式或字段错误 | 10 |
| `STALE_REVISION` | expected_revision 过期；错误中附当前 revision 与简要上下文 | 10 |
| `IDEMPOTENCY_CONFLICT` | 同一 request_id 携带了不同的内容 | 10 |
| `INVARIANT_VIOLATION` | 违反叙事与状态规则（冷却、知情边界、玩家授权、变化幅度等） | 10 |
| `SAFETY_BLOCK` | 触及玩家硬边界、处于暂停状态，或违反全员成年（18+）底线 | 10 |
| `CONTENT_ERROR` | 内容包或自定义世界校验失败 | 10 |
| `NOT_FOUND` | 会话、存档、角色、事件不存在 | 10 |
| `SLOT_CONFLICT` | 存档名或自定义世界名已被占用（exists），或本局当前槽已在别的对话里被写过（changed_elsewhere） | 10 |
| `UNSUPPORTED_VERSION` | 存档、数据库或内容版本不受支持 | 20 |
| `RUNTIME_UNSUPPORTED` | Python 版本过低或缺少 SQLite 等必要能力 | 20 |
| `DATA_DIR_UNAVAILABLE` | 数据目录不可写；附尝试过的路径与建议 | 20 |
| `STORAGE_BUSY` | 数据库被其他进程短暂占用；用同一 request_id 重试 | 20 |
| `NO_MATCH` | 开局约束在所选世界中无法满足（附冲突的约束与可放宽项），或 world_query 命中多个世界（附 candidates） | 10 |
| `MIGRATION_FAILED` | 数据库迁移失败，已恢复迁移前的备份 | 20 |
| `INTERNAL_ERROR` | 内部运行异常；附日志路径，状态未改变 | 30 |

## 退出码

| 退出码 | 类别 |
|---|---|
| 0 | 成功 |
| 10 | 输入与领域错误：按 `details` 修正后重新提交 |
| 20 | 环境错误：Python、数据目录、存储占用、版本 |
| 30 | 内部运行异常：状态未改变，附日志路径 |
