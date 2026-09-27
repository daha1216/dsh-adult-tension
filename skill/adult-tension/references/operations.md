<!-- 本文件由 tools/gen_references.py 生成，不要手改。 -->

# 操作参考

`commit-turn` 的 `operations` 是一个操作数组。操作按顺序应用，后面的操作看得到前面操作的效果；任何一个不合法，整个提交被拒绝、状态不变，错误列出全部问题及其 JSON 路径。NPC 拒绝玩家（`npc_response: refuse`）是合法的叙事结果，不是错误。

提交里没有 `advance_time` 时，时钟默认推进 3 分钟。单次推进上限 30 天。

## 提交的顶层字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `action_mode` | 枚举：`result` / `attempt` / `rewrite` / `continue` / `wait` | 是 | result / attempt / rewrite / continue / wait |
| `player_input` | 字符串，≤2000 字 | 是 | 玩家这一句的原话（继续时可为空字符串） |
| `player_authorized` | 布尔 | 否，默认 `false` | 玩家本人的话授权了玩家角色的移动、承诺、交易、同意或设定修改时为 true |
| `acts_on` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}，0–8 项） 或 null | 否，默认 `null` | 玩家行动作用到的 NPC（身体、意志、财物）；attempt 不作用于任何 NPC 时写 [] |
| `operations` | 数组（操作对象（按 `op` 区分），0–40 项） | 是 | 操作列表（可以为空数组） |
| `content_tags` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}，0–12 项） | 是 | 本回合正文涉及的内容标签（可为空数组）；标签表见完整上下文的 tags |
| `intimate_participants` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}，0–6 项） | 否，默认 `[]` | content_tags 含 intimate 或 explicit 时必填：亲密参与者（含玩家） |
| `summary` | 字符串，≤120 字 | 是 | 本回合发生了什么，第三方视角，≤120 字 |
| `open_action` | 字符串，≤80 字 | 是 | 回合停在哪里、谁在等谁，≤80 字 |
| `quotes` | 数组（字符串，≤80 字，0–3 项） | 否，默认 `[]` | ≤3 条对后续有意义的原话，每条 ≤80 字 |
| `chapter_summary` | 字符串，≤300 字 或 null | 否，默认 `null` | 上下文 requests.chapter_summary 为 true 时必填，≤300 字 |
| `replaces_turn` | 整数 1..1000000 或 null | 否，默认 `null` | “刚才不算，改成……”时填上一回合的回合号 |

## 操作一览

| op | 作用 |
|---|---|
| `advance_time` | 推进游戏时钟：minutes / until / days 三选一；触发到期事件与状态到期结算。没有此操作时时钟默认推进 3 分钟 |
| `move` | 角色移动到地点。玩家移动需要 result/attempt 模式并带 player_authorized；玩家换地点即换场景 |
| `enter_scene` | 角色登场，加入当前场景 |
| `exit_scene` | 角色离场；可写去向地点。玩家角色用 move |
| `npc_response` | NPC 对玩家尝试的回应：refuse 拒绝 / negotiate 协商 / partial 有限配合 / surface 表面配合 / genuine 真诚配合。surface 必须写 true_intent（记为只有本人知道的事实） |
| `npc_action` | NPC 自主行动。significant: true 的重大行动（主动接近、揭发、交易、离开、表白、挑衅等）受冷却限制；依据事实必须在其信息集中 |
| `npc_state` | 更新 NPC 的情绪与状况（醉意、睡眠、受伤、外出等）；minutes 表示多久后自动消退 |
| `add_fact` | 记录一条事实。public 在场者自动知道；private 只有 known_by；inner 是内心，只属于一个 NPC 且永不传播。误信用 truth: false + believed_by。正文里新写出、之后要继承的细节都要用它记下 |
| `relationship` | 有向关系变化（from 对 to）：信任 -5..5（单次提交净变化 ≤2）、张力 0..5、亲近进程前进一个阶段（需要同一提交里玩家的行动 + 对方的 partial/genuine 回应）或后退。原因必填 |
| `event_create` | 创建事件（约定、截止、风声、机会、伏笔、概率事件）。due 与 in_minutes 二选一且必须晚于现在；chance 必须带 probability，到期由引擎掷骰；涉及玩家的承诺需要 player_authorized；dedupe_key 与未结束事件不能重复 |
| `event_resolve` | 在到期前结束事件：约定、截止、机会用 fulfilled（兑现）；伏笔、风声用 surfaced（提前浮出）。概率事件只能由引擎到期掷骰 |
| `event_cancel` | 因剧情取消未结束的事件（outcome: cancelled_by_story） |
| `roll` | 即时概率：引擎确定性掷骰后执行 on_success 或 on_failure（分支内不能再嵌套 roll，也不能推进时间）。结果以返回的 applied 为准 |
| `player_update` | 玩家角色的姓名、称谓、背景、资源与风险。只能在 result 或 rewrite 模式、并带 player_authorized |

## `advance_time`

推进游戏时钟：minutes / until / days 三选一；触发到期事件与状态到期结算。没有此操作时时钟默认推进 3 分钟

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `op` | 枚举：`advance_time` | 是 |  |
| `minutes` | 整数 1..43200 | 否 |  |
| `until` | 枚举：`morning` / `noon` / `evening` / `night` / `next_morning` | 否 |  |
| `days` | 整数 1..30 | 否 |  |

不能出现在 `roll` 的分支里。

## `move`

角色移动到地点。玩家移动需要 result/attempt 模式并带 player_authorized；玩家换地点即换场景

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `op` | 枚举：`move` | 是 |  |
| `character_id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `location_id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |

## `enter_scene`

角色登场，加入当前场景

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `op` | 枚举：`enter_scene` | 是 |  |
| `character_id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |

## `exit_scene`

角色离场；可写去向地点。玩家角色用 move

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `op` | 枚举：`exit_scene` | 是 |  |
| `character_id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `to_location_id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} 或 null | 否，默认 `null` |  |

## `npc_response`

NPC 对玩家尝试的回应：refuse 拒绝 / negotiate 协商 / partial 有限配合 / surface 表面配合 / genuine 真诚配合。surface 必须写 true_intent（记为只有本人知道的事实）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `op` | 枚举：`npc_response` | 是 |  |
| `npc_id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `response` | 枚举：`refuse` / `negotiate` / `partial` / `surface` / `genuine` | 是 |  |
| `note` | 字符串，≤80 字 | 是 |  |
| `basis_fact_ids` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}，0–8 项） | 否，默认 `[]` |  |
| `true_intent` | 字符串，≤120 字 或 null | 否，默认 `null` |  |

## `npc_action`

NPC 自主行动。significant: true 的重大行动（主动接近、揭发、交易、离开、表白、挑衅等）受冷却限制；依据事实必须在其信息集中

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `op` | 枚举：`npc_action` | 是 |  |
| `npc_id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `action` | 字符串，≤120 字 | 是 |  |
| `significant` | 布尔 | 否，默认 `false` |  |
| `kind` | 枚举：`approach` / `reveal` / `trade` / `leave` / `confess` / `provoke` / `other` 或 null | 否，默认 `null` |  |
| `target_id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} 或 null | 否，默认 `null` |  |
| `basis_fact_ids` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}，0–8 项） | 否，默认 `[]` |  |

## `npc_state`

更新 NPC 的情绪与状况（醉意、睡眠、受伤、外出等）；minutes 表示多久后自动消退

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `op` | 枚举：`npc_state` | 是 |  |
| `npc_id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `mood` | 字符串，≤20 字 或 null | 否，默认 `null` |  |
| `add_conditions` | 数组（对象（状况），0–4 项） | 否，默认 `[]` |  |
| `remove_conditions` | 数组（枚举：`drunk` / `asleep` / `unconscious` / `injured` / `away` / `busy` / `other`，0–7 项） | 否，默认 `[]` |  |

#### `add_conditions[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `kind` | 枚举：`drunk` / `asleep` / `unconscious` / `injured` / `away` / `busy` / `other` | 是 |  |
| `text` | 字符串，≤40 字 | 是 |  |
| `minutes` | 整数 1..43200 或 null | 否，默认 `null` |  |

## `add_fact`

记录一条事实。public 在场者自动知道；private 只有 known_by；inner 是内心，只属于一个 NPC 且永不传播。误信用 truth: false + believed_by。正文里新写出、之后要继承的细节都要用它记下

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `op` | 枚举：`add_fact` | 是 |  |
| `key` | 字符串，≤80 字，点分的 ASCII 小写键，例如 lin_wan.secret.press | 是 |  |
| `text` | 字符串，≤120 字 | 是 |  |
| `truth` | 布尔 | 否，默认 `true` |  |
| `known_by` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}，0–20 项） | 否，默认 `[]` |  |
| `believed_by` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}，0–20 项） | 否，默认 `[]` |  |
| `visibility` | 枚举：`public` / `private` / `inner` | 是 |  |
| `origin` | 枚举：`observed` / `told` / `retcon` | 是 |  |
| `spread` | 布尔 | 否，默认 `false` |  |

## `relationship`

有向关系变化（from 对 to）：信任 -5..5（单次提交净变化 ≤2）、张力 0..5、亲近进程前进一个阶段（需要同一提交里玩家的行动 + 对方的 partial/genuine 回应）或后退。原因必填

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `op` | 枚举：`relationship` | 是 |  |
| `from` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `to` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `trust_delta` | 整数 -2..2 | 否，默认 `0` |  |
| `tension_delta` | 整数 -5..5 | 否，默认 `0` |  |
| `stage_advance` | 布尔 | 否，默认 `false` |  |
| `stage_retreat_to` | 枚举：`stranger` / `acquainted` / `familiar` / `flirting` / `testing` / `intimate` / `committed` 或 null | 否，默认 `null` |  |
| `reason` | 字符串，≤80 字 | 是 |  |

## `event_create`

创建事件（约定、截止、风声、机会、伏笔、概率事件）。due 与 in_minutes 二选一且必须晚于现在；chance 必须带 probability，到期由引擎掷骰；涉及玩家的承诺需要 player_authorized；dedupe_key 与未结束事件不能重复

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `op` | 枚举：`event_create` | 是 |  |
| `kind` | 枚举：`promise` / `deadline` / `rumor` / `opportunity` / `foreshadow` / `chance` | 是 |  |
| `title` | 字符串，≤40 字 | 是 |  |
| `text` | 字符串，≤120 字 或 null | 否，默认 `null` |  |
| `tier` | 枚举：`immediate` / `near` / `far` 或 null | 否，默认 `null` |  |
| `participants` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}，1–12 项） | 是 |  |
| `due` | 对象（游戏时钟） | 否 |  |
| `in_minutes` | 整数 1..576000 | 否 |  |
| `probability` | 数值 (0, 1) 或 null | 否，默认 `null` |  |
| `dedupe_key` | 字符串，≤80 字，点分的 ASCII 小写键，例如 lin_wan.secret.press | 是 |  |
| `repeat` | 布尔 | 否，默认 `false` |  |

#### `due` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `day` | 整数 1..100000 | 是 |  |
| `minute` | 整数 0..1439 | 是 |  |

## `event_resolve`

在到期前结束事件：约定、截止、机会用 fulfilled（兑现）；伏笔、风声用 surfaced（提前浮出）。概率事件只能由引擎到期掷骰

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `op` | 枚举：`event_resolve` | 是 |  |
| `event_id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `outcome` | 枚举：`fulfilled` / `surfaced` | 是 |  |
| `note` | 字符串，≤80 字 | 是 |  |

## `event_cancel`

因剧情取消未结束的事件（outcome: cancelled_by_story）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `op` | 枚举：`event_cancel` | 是 |  |
| `event_id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `reason` | 字符串，≤80 字 | 是 |  |

## `roll`

即时概率：引擎确定性掷骰后执行 on_success 或 on_failure（分支内不能再嵌套 roll，也不能推进时间）。结果以返回的 applied 为准

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `op` | 枚举：`roll` | 是 |  |
| `purpose` | 字符串，≤60 字 | 是 |  |
| `probability` | 数值 (0, 1) | 是 |  |
| `on_success` | 数组（分支操作，0–8 项） | 否，默认 `[]` |  |
| `on_failure` | 数组（分支操作，0–8 项） | 否，默认 `[]` |  |

不能出现在 `roll` 的分支里。

## `player_update`

玩家角色的姓名、称谓、背景、资源与风险。只能在 result 或 rewrite 模式、并带 player_authorized

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `op` | 枚举：`player_update` | 是 |  |
| `name` | 字符串，≤12 字 或 null | 否，默认 `null` |  |
| `title` | 字符串，≤12 字 或 null | 否，默认 `null` |  |
| `add_background` | 字符串，≤120 字 或 null | 否，默认 `null` |  |
| `add_resources` | 数组（字符串，≤60 字，0–4 项） | 否，默认 `[]` |  |
| `add_risks` | 数组（字符串，≤60 字，0–4 项） | 否，默认 `[]` |  |

## 取值表

- 回应光谱：`refuse` 拒绝、`negotiate` 协商、`partial` 有限配合、`surface` 表面配合、`genuine` 真诚配合
- 关系阶段（世界可改名）：`stranger` 陌生、`acquainted` 认识、`familiar` 熟络、`flirting` 暧昧、`testing` 试探、`intimate` 亲密、`committed` 稳定
- 事件到期：`promise` → `expired`、`deadline` → `expired`、`opportunity` → `expired`、`foreshadow` → `surfaced`、`rumor` → `surfaced`；`chance` 由引擎掷骰得到 `hit` / `miss`
- 状况：`drunk`、`asleep`、`unconscious`、`injured`、`away`、`busy`、`other`（其中 `drunk`、`asleep`、`unconscious` 的角色不参与亲密场景）
