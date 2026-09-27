# 数据合同

本文件定义数据的**语义**。示例是合法 JSON，用于说明形状；字段名可以由实现者调整（`DESIGN_DECISIONS.md` 刻意留白），但语义、约束和校验行为必须保持。实现者最终以代码中的校验器为准，并由校验器生成一份字段参考放进 `references/`。

## 1. 通用约定

- 所有交换数据为 UTF-8 JSON。
- 所有对象都拒绝未知字段，错误中带 JSON 路径（例如 `$.operations[2].npc_id`）。
- JSON 中的重复键也是错误（标准库 `json` 默认静默保留后一个值，必须显式拒绝）。
- 数值不静默截断：超出范围就报错，不“帮忙”夹到边界。
- 所有持久化格式都带 `schema_version`；内容包带 `content_version`；随机带 `rng_version`。
- ID 是 ASCII 小写短标识（`[a-z0-9_]{1,40}`）；显示名是中文。ID 在会话内唯一，一经分配永不复用，角色升格也保留原 ID。
- 时间用游戏内时钟：`{"day": 1, "minute": 1230}`，`minute` 为当天 0–1439。时间永不倒流。不使用公历日期，古代与幻想世界同样适用；世界包可以提供起始日的显示标签（如“庆应三年·霜月初七”），引擎只负责按天数递推。
- 所有 CLI 输出都是信封：

```json
{"ok": true, "data": {}, "error": null}
```

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "INVALID_INPUT",
    "message": "有 2 处错误",
    "details": [
      {"path": "$.operations[1].npc_id", "reason": "角色 lin_wan 不在当前场景", "hint": "先用 enter_scene 让她登场"},
      {"path": "$.summary", "reason": "缺少必填字段", "hint": null}
    ]
  }
}
```

## 2. 会话

一个会话是一局游戏。会话包含：

| 部分 | 语义 |
|---|---|
| `session_id`、`revision`、`turn` | revision 每次状态变化 +1；turn 只在叙事回合推进时 +1；开局后 revision=1、turn=1 |
| `seed`、`rng_version`、`content_snapshot` | 开局种子；所用世界包的快照（包括自定义世界） |
| `mode` | `daily` 或 `pressure` |
| `clock` | 游戏内时间 |
| `scene` | 当前地点、在场角色、场景编号（地点变化或跳过 ≥ 60 分钟时换新编号） |
| `player_id` | 玩家角色的 ID |
| `characters`、`relationships`、`facts`、`events`、`leverage` | 见 §3–§5 |
| `preferences` | 呈现偏好，见下 |
| `safety` | 硬边界与暂停状态 |
| `memory` | 章节摘要与回合摘要 |
| `counters` | 冷却、上次转折等由引擎维护的计数 |

呈现偏好：

```json
{
  "inner_view": false,
  "assistant": false,
  "offscreen_simulation": true,
  "voice": {"lin_wan": "surface"},
  "npc_gender_preference": "mostly_female",
  "person": "second",
  "pace": "standard",
  "explicitness": "standard"
}
```

- `npc_gender_preference`：`any`、`mostly_female`、`mostly_male`、`female_only`、`male_only`、`mixed`。
- `person`：称呼玩家角色的人称，`second`（默认）、`first` 或 `third`；NPC 始终用第三人称。开局时取世界包的 `default_person`，玩家可以改。
- `pace`、`explicitness` 为 P1，P0 阶段固定为 `standard`，但字段从第一天存在。

安全：

```json
{
  "paused": false,
  "boundaries": [
    {"id": "b1", "text": "不要涉及怀孕", "tags": ["pregnancy"], "created_turn": 3}
  ]
}
```

- 玩家用自然语言登记边界，模型把它映射为一个或多个内容标签（标签表见 §8.4），并保留原文。
- 无法映射到已知标签的边界，以原文登记，并标为 `tags: ["custom"]`；模型在每次上下文中都能看到原文。

## 3. 角色

```json
{
  "id": "lin_wan",
  "name": "林婉",
  "tier": "major",
  "age": 29,
  "gender": "female",
  "adult_context": "报馆排字房的正式雇员",
  "public_role": "排字房领班",
  "appearance": "袖口总沾着油墨，头发用一支铅笔别住",
  "identity": {
    "resources": ["排字房钥匙", "认识每一个送稿的人"],
    "limits": ["不能得罪主编", "没有积蓄"],
    "exposure_risk": "替地下刊物排过版",
    "hidden_mismatch": "识字比报馆里大多数编辑都多"
  },
  "situation": {
    "trigger": "主编要她今晚交出送稿人名单",
    "pressure": "交不出就丢工作",
    "deadline": {"day": 1, "minute": 1380},
    "exits": [
      {"option": "编一份假名单", "cost": "被查出就是同谋"},
      {"option": "辞职离开", "cost": "母亲的药钱断了"}
    ]
  },
  "decision": {
    "core_value": "护住自己人",
    "current_goal": "拖过今晚",
    "pressure_response": "表面顺从，暗中转移",
    "relationship_stance": "先观察，再决定信不信",
    "contrast": "嘴硬，但对弱者心软",
    "prefers": ["用手艺换人情"],
    "avoids": ["当众冲突"],
    "never": ["出卖送稿人"]
  },
  "intimacy": {
    "desire_level": 2,
    "attraction_sources": ["对方尊重她的手艺", "在她为难时没有趁机要挟"],
    "likes": ["慢", "被认真看着"],
    "dislikes": ["被当作交易"],
    "preconditions": ["确信对方不会把事情说出去"],
    "boundaries": ["不在报馆里"],
    "expression": "用动作代替话语",
    "self_control": 4,
    "desired_position": "平等"
  },
  "voices": {
    "surface": "简短、客气、带点刺",
    "inner": "低声、直接、会笑"
  },
  "status": {"location_id": "type_room", "mood": "绷着", "condition": []}
}
```

约束：

- `age` 必填且 ≥ 18；`adult_context` 必填，用一句话说明成年身份。缺失即 `INVARIANT_VIOLATION`。
- `tier`：`background`（只有名字和一句话）、`supporting`（有身份与目标）、`major`（完整卡）。只升不降；升格时补齐对应字段。
- 可以同时有多个 `major`。只有 `major` 可以参与亲密场景；配角需要先升格。
- 字段写权限：`id`、`name`、`age`、`gender` 永不可改（玩家角色的姓名与称谓例外，经 `player_update`）；`intimacy` 与 `identity` 只能在升格时创建一次，之后只能逐项演化；其余字段可以通过对应操作修改。
- 角色卡里的 `intimacy.boundaries` 是角色自己的界线，和玩家登记的硬边界（`safety.boundaries`）是两回事，命名上必须区分。
- 玩家角色也是角色，但没有 `decision` 与 `intimacy`（模型不替玩家决定），额外有 `title`（称谓）、`social_position`、`resources`、`risks`。
- `situation` 永远不是同意；校验器不以它为任何亲密变化的依据。
- `intimacy` 只能通过 `intimacy_evidence` 操作逐项演化（§6），不能整体替换。
- `status.mood` 与 `condition` 由模型通过 `npc_state` 操作更新，引擎只校验格式。

## 4. 关系

关系是有向边，首次实际接触时建立。

```json
{
  "from": "lin_wan",
  "to": "player",
  "trust": 1,
  "tension": 2,
  "intimacy_stage": "acquainted",
  "history": [
    {"turn": 2, "change": "trust+1", "reason": "他没有追问名单的事"},
    {"turn": 4, "change": "tension+2", "reason": "他看见了她藏起来的校样"},
    {"turn": 6, "change": "stage:acquainted", "reason": "一起把校样搬回了库房", "evidence": {"player_action_turn": 6, "npc_response": "genuine"}}
  ]
}
```

- `trust`：-5..5；`tension`：0..5；`intimacy_stage`：世界包定义的有序阶段表中的一项（默认 `stranger`、`acquainted`、`familiar`、`flirting`、`testing`、`intimate`、`committed`）。
- 每次变化必须带 `reason` 与 `turn`；阶段前进必须带 `evidence`。
- 阶段可以后退（关系破裂），后退不需要双方证据，但需要原因。
- 阶段是历史，不是许可。校验器不因为阶段足够高就放行任何行为。
- 开局时，玩家与每个在场 NPC 之间、各重要 NPC 两两之间都必须已有关系边（可以是陌生），并带一句关系原因。

## 5. 事实与事件

### 5.1 事实

```json
{
  "id": "f12",
  "key": "lin_wan.secret.underground_press",
  "text": "林婉替地下刊物排过版",
  "truth": true,
  "known_by": ["lin_wan"],
  "believed_by": [],
  "visibility": "private",
  "origin": "setup",
  "turn": 1
}
```

- `visibility`：`public`（在场者自动知道）、`private`、`inner`（内心，`known_by` 只能是本人，且永远不能被 `reveal_fact` 传播）。
- `origin`：`setup`、`observed`、`told`、`retcon`、`offscreen`、`rumor`。
- 误信用 `truth: false` 加 `believed_by` 表达；同一个 `key` 可以同时有一条真事实和一条假事实。
- `retcon` 事实不得与同 `key` 的已有事实矛盾，不得出现在 NPC 的 `known_by` 中（除非玩家明确说明对方知道，且不涉及同意、好感）。
- 传播：`reveal_fact` 只能沿已存在的关系边进行；`spread_rumor` 生成一条走样的新事实（`origin: "rumor"`），原事实不变。

### 5.2 事件

```json
{
  "id": "e3",
  "kind": "deadline",
  "tier": "near",
  "title": "主编要名单",
  "participants": ["lin_wan", "editor_zhou"],
  "due": {"day": 1, "minute": 1380},
  "probability": null,
  "dedupe_key": "editor_zhou.demand_list",
  "state": "pending",
  "outcome": null,
  "created_turn": 1
}
```

- `kind`：`promise`、`deadline`、`rumor`、`opportunity`、`foreshadow`、`chance`。
- `tier`：`immediate`、`near`、`far`（仅压力模式开局必须三层齐全）。
- `state`：`pending` → `resolved` 或 `cancelled`。只有这三种。终态事件不可再修改。
- `outcome`：`fulfilled`（在到期前被兑现）、`expired`（到期未兑现，由引擎判定）、`hit` / `miss`（概率事件）、`cancelled_by_story`。“到期”与“兑现”必须区分。
- `id`、`kind`、`dedupe_key`、`created_turn` 不可变。`pending` 事件的 `due` 必须晚于当前时钟。
- `dedupe_key` 相同的 `pending` 事件不能同时存在；已结束事件的键要复用，必须显式声明为重复发生（例如带序号）。
- 带 `probability` 的事件到期时由引擎掷骰（种子来自会话种子派生，见 `DESIGN_DECISIONS.md` D10），结果写入 `outcome`，模型只负责描写。同一事件同一回合最多掷一次。
- 到期事件在任何推进时间的提交中都由引擎自动结算，并在返回结果里列出，模型必须在正文中体现。
- `promise` 与涉及玩家的交易，创建时必须 `player_authorized: true`。
- 压力模式开局必须有 `immediate`、`near`、`far` 三层事件，其中 `far` 为 `foreshadow`；日常模式开局不得有 `deadline` 与 `chance` 事件。

### 5.3 把柄

“一方握有另一方的把柄、债务或生计”必须有记录，引擎才能执行“处境永远不是同意”（`NARRATIVE_RULES.md` §7.1）。

```json
{
  "id": "lv1",
  "holder": "editor_zhou",
  "subject": "lin_wan",
  "basis_fact_id": "f15",
  "origin": "pressure:p_list_demand",
  "state": "active",
  "created_turn": 1,
  "released_turn": null,
  "release_reason": null
}
```

- 来源：开局时由带 `leverage` 标记的压力生成（§8.1）；局中由 `leverage_set` 登记，例如 NPC 发现了玩家的秘密并开始暗示。
- `holder`、`subject` 是角色 ID，可以是玩家；`basis_fact_id` 指向构成把柄的事实，且 `holder` 知道这条事实。
- `state` 只有 `active` → `released`；解除用 `leverage_release`，必须写原因（把柄被销毁、债务结清、秘密已经公开等）。
- 生效期间，`holder` 与 `subject` 之间的亲密提交被拒（§6）。在同一次提交里先解除再亲密，不算解除。
- 正文里一方开始拿捏另一方时，必须在同一次提交中登记。正文有要挟而状态里没有记录，是端到端评测的失败项（`ACCEPTANCE.md` §6）。

## 6. 回合提交

一次叙事回合 = 一次 `commit-turn`。模型先提交，再根据返回结果写正文。

```json
{
  "session_id": "s_7f3a",
  "request_id": "r_0142",
  "expected_revision": 12,
  "action_mode": "attempt",
  "player_input": "我把外套搭在她肩上，问她要不要一起走一段",
  "player_authorized": true,
  "operations": [
    {"op": "advance_time", "minutes": 10},
    {"op": "npc_response", "npc_id": "lin_wan", "response": "partial", "basis_fact_ids": ["f3"], "note": "收下外套，但只肯走到街口"},
    {"op": "relationship", "from": "lin_wan", "to": "player", "trust_delta": 1, "tension_delta": 0, "reason": "他没有借机提名单的事"},
    {"op": "roll", "purpose": "巡警是否注意到两人", "probability": 0.3,
     "on_success": [{"op": "add_fact", "key": "patrol.saw_pair", "text": "巡警看见两人一起离开", "truth": true, "known_by": ["patrol_wu"], "visibility": "private", "origin": "observed"}],
     "on_failure": []}
  ],
  "content_tags": ["romance_light"],
  "summary": "你把外套给了林婉，她同意陪你走到街口。",
  "open_action": "林婉在街口停下，等你开口",
  "quotes": ["“只到街口。”"],
  "chapter_summary": null,
  "replaces_turn": null
}
```

必填：`session_id`、`request_id`、`expected_revision`、`action_mode`、`player_input`、`operations`（可以为空数组）、`content_tags`（可以为空数组）、`summary`、`open_action`。

条件必填：`content_tags` 含 `intimate` 或 `explicit` 时必须有 `intimate_participants`（角色 ID 数组，含玩家）；引擎在 `requests` 中提出要求时，必须有 `chapter_summary` 或对应的 `offscreen_beat` 操作（见 `RUNTIME_PROTOCOL.md` §5）。

- `summary`：本回合发生了什么，≤ 120 字，第三方可读，用于记忆与读档。
- `open_action`：回合停在哪里、谁在等谁，≤ 80 字，用于读档后接续与“继续”。
- `quotes`：≤ 3 条、每条 ≤ 80 字的原话，只收对后续有意义的台词。
- 提交中没有 `advance_time` 时，引擎按默认值推进时钟（`DESIGN_DECISIONS.md` 默认值表），并在返回中注明。

`replaces_turn`：改写（“刚才不算，改成 Y”）时填上一回合的回合号，引擎在同一事务中撤销该回合再应用本次提交。

**全有或全无**：提交中任何一个操作不合法，整个提交被拒绝，状态不变，错误列出全部问题。NPC 拒绝玩家是合法的叙事结果（`npc_response: refuse`），不是错误。

**亲密场景的结构信号**：`content_tags` 含 `intimate` 或 `explicit` 的提交必须附 `intimate_participants`。引擎检查：

- 每个参与者都是 `major` 且在场、年龄合规；
- 当前不在暂停中，且标签不与硬边界冲突；
- 每个 NPC 参与者在本次提交中有 `npc_response`（`partial` 或 `genuine`）或主动的 `npc_action`。
- 任意两名参与者之间没有生效中的把柄（§5.3）。

这保证“反应持续可见”在结构上成立。这个检查只针对本次提交，不产生任何可以延续到之后回合的同意记录。

### 6.1 操作表（P0 最小集合）

| op | 作用 | 关键约束 |
|---|---|---|
| `advance_time` | `minutes` 或 `until`（`morning`/`noon`/`evening`/`night`/`next_morning`）或 `days` | 不能倒流；触发推演分档与事件到期 |
| `move` | 角色移动到地点 | 玩家移动需 `player_authorized`；地点必须在快照中 |
| `enter_scene` / `exit_scene` | 角色登场 / 离场 | 角色必须存在 |
| `introduce_character` | 新角色 | 完整角色卡；年龄 ≥ 18；符合性别偏好或说明原因 |
| `promote_character` | 升格 | 保留 ID，补齐字段 |
| `npc_response` | 回应光谱 | `refuse`/`negotiate`/`partial`/`surface`/`genuine`；`basis_fact_ids` 必须在其信息集中；`surface` 必须同时 `add_fact` 记录真实意图 |
| `npc_action` | NPC 自主行动 | `significant: true` 时检查冷却；依据事实同上；离屏冻结时仅限在场者 |
| `npc_state` | 情绪与状况 | 只改 `status` |
| `set_voice` | 语态切换 | `cause`：`player_request`/`npc_self`/`revert`；`npc_self` 需填 `trigger` |
| `add_fact` / `reveal_fact` / `spread_rumor` | 知识变化 | 见 §5.1 |
| `relationship` | 关系变化 | 幅度限制；原因必填；`stage_advance: true` 需要同一提交中的对应 `npc_response` |
| `intimacy_evidence` | 倾向卡证据 | 指明项、方向与证据；满足证据数后由引擎应用改动 |
| `event_create` / `event_resolve` / `event_cancel` | 事件 | 去重；涉及玩家的承诺需授权 |
| `roll` | 即时概率 | 引擎掷骰并执行 `on_success` 或 `on_failure` 分支（分支内不能再嵌套 `roll`） |
| `player_update` | 玩家角色的姓名、称谓、背景 | 只能在 `result` 或 `rewrite` 模式 |
| `leverage_set` / `leverage_release` | 把柄的登记与解除 | 见 §5.3；解除必须写原因 |
| `twist_accept` | 接受转折 | 引用上下文中提供的候选，或给出自定义转折（类别必填） |
| `offscreen_beat` | 离屏片段 | 只能是上下文列出的候选 NPC |

实现者可以增加操作，但不能让操作绕开上述约束。

### 6.2 提交的返回

```json
{
  "revision": 13,
  "turn": 7,
  "applied": [
    {"op": "npc_response", "npc_id": "lin_wan", "response": "partial"},
    {"op": "roll", "purpose": "巡警是否注意到两人", "result": "failure"}
  ],
  "resolved_events": [],
  "simulation": null,
  "context": {"depth": "brief"},
  "next_request_id": "r_0143",
  "replayed": false
}
```

- `applied` 是模型写正文的唯一事实依据；`roll` 的结果、到期事件、离屏推演结果都在这里。
- `next_request_id` 是引擎建议的下一个请求号，模型可以直接使用，省去自己生成；`replayed: true` 表示这是同一 `request_id` 的重放结果，状态没有再次变化。
- `context` 是下一回合所需的上下文（§7），模型不需要再调用 `get-context`。

## 7. 上下文

`get-context` 与 `commit-turn` 都返回上下文。深度由引擎决定（`DESIGN_DECISIONS.md` 默认值）。

简要上下文（示意，省略部分数组内容）：

```json
{
  "depth": "brief",
  "revision": 13,
  "turn": 7,
  "clock": {"day": 1, "minute": 1250, "label": "第一天 20:50"},
  "scene": {"id": "sc3", "location": "报馆后巷", "present": ["player", "lin_wan"]},
  "player": {"name": "沈既白", "title": "沈先生", "age": 34},
  "present_npcs": [
    {"id": "lin_wan", "name": "林婉", "mood": "绷着", "voice": "surface", "stance": "先观察", "can_act": true, "trust_to_player": 2, "tension": 2, "stage": "acquainted"}
  ],
  "due_soon": [{"id": "e3", "title": "主编要名单", "in_minutes": 130}],
  "recent": ["你把外套给了林婉，她同意陪你走到街口。"],
  "safety": {"paused": false, "boundaries": ["不要涉及怀孕"], "leverage": [{"id": "lv1", "holder": "editor_zhou", "subject": "lin_wan"}]},
  "preferences": {"inner_view": false, "assistant": false, "offscreen_simulation": true},
  "save": {"current_slot": "港口夜班-第3回合", "turns_since_save": 4},
  "requests": {"chapter_summary": false, "twist_offer": null, "offscreen_beat_candidates": []}
}
```

简要上下文的 `safety.leverage` 只列出涉及在场者的生效把柄。`save` 给出本局的当前槽（没有则为 `null`）和自上次存档以来的回合数，模型据此处理“再开一局”的确认（`RUNTIME_PROTOCOL.md` §4.2）。完整上下文额外包含：全部重要 NPC 的卡片摘要、关系及最近原因、玩家角色知道的事实、世界规则、地点列表、章节摘要、未决事件全集、全部生效把柄。

体积要求：

- 简要 ≤ 6 KB；完整 ≤ 20 KB。
- 第 300 回合时的简要上下文体积不超过第 10 回合的 1.5 倍。
- 简要上下文中的列表有上限（默认：近期事件 ≤ 10、玩家已知事实 ≤ 8、近期摘要 ≤ 3），超出部分按相关性与时间截取；需要更多时由引擎升级为完整上下文，而不是无限增长。
- 状态本身也不能无限增长：已结束的事件与旧回合记录在章节摘要后归档，归档不进入上下文，但仍可在存档中查询。

## 8. 内容包

### 8.1 世界包

世界包是一个时代、一个地方、一群人的整体（`DESIGN_DECISIONS.md` D7、D16）。开局的全部组合都只在同一个包内发生。下面是一个压缩示例：每个数组只写一条，真实的包必须达到 `CONTENT_BIBLE.md` §3 的下限。

```json
{
  "schema_version": 1,
  "id": "harbor_night_shift",
  "title": "港口夜班",
  "extends": null,
  "era": "1990 年代末",
  "region": "南方港城",
  "premise": "集装箱码头的夜班，灯一直亮到天明，交接班的十分钟里什么都可能发生。",
  "tone": ["潮湿", "疲惫", "克制的热"],
  "style_hint": "短句，多写声音与气味，少写心理独白；方言词点到即止",
  "clock_start": {"label": "一九九八年，台风季", "minute": 1260},
  "default_person": "second",
  "default_npc_gender_mix": {"female": 0.6, "male": 0.4},
  "stage_labels": null,
  "name_pools": {
    "family": ["陈", "梁", "何", "麦"],
    "given_female": ["秀琴", "嘉欣", "美玲"],
    "given_male": ["志强", "国栋", "家豪"],
    "given_neutral": ["子晴"],
    "nickname_patterns": ["阿{given_last}", "老{family}"]
  },
  "rules": [
    {"id": "r_shift", "text": "夜班 20:00 到 8:00，凌晨两点有一次交接，所有人都在控制塔签到。"}
  ],
  "customs": ["收工后去茶餐厅吃一碗云吞面是默认的散伙仪式", "红包要当着人面推两次再收"],
  "player_identities": [
    {
      "id": "tally_clerk",
      "role": "理货员",
      "title_patterns": ["{family}仔", "理货的"],
      "age_range": [24, 40],
      "social_position": "low",
      "baseline": "干了四年夜班，谁的箱子有问题一眼就看得出",
      "resources": ["知道每个箱子的真实重量"],
      "reputation": "嘴紧",
      "risks": ["收过船东的红包"]
    }
  ],
  "locations": [
    {
      "id": "berth_7",
      "name": "七号泊位",
      "detail": "吊臂的影子一格一格扫过地面",
      "privacy": "public",
      "visibility": "塔吊司机能从高处看见整片泊位",
      "witnesses": ["bg_lashing_crew"],
      "exits": ["control_tower", "tool_shed"],
      "affordances": ["躲进两排集装箱的夹缝", "借吊车的噪音说悄悄话"],
      "pressure_modifiers": {"p_customs_raid": "查柜从这里开始"},
      "tags": ["workplace"]
    }
  ],
  "character_templates": [
    {
      "id": "crane_operator",
      "gender": "any",
      "age_range": [26, 38],
      "adult_context": "持证塔吊司机，码头正式工",
      "public_role": "夜班塔吊司机",
      "appearance_options": ["安全帽下压着一条褪色的头巾", "手背上有一道缆绳勒出的疤"],
      "identity": {
        "authority": "能决定哪个箱子先吊",
        "resources": ["高处的视野", "对讲机频道"],
        "limits": ["不能离开驾驶室超过十分钟"],
        "obligations": ["每月寄钱回乡下"],
        "exposure": "替人漏吊过一个箱子",
        "hidden": "准备在年底辞职去学开货车"
      },
      "decision": {
        "core_value": "不欠人情",
        "goal_options": ["今晚别出事", "攒够学车的钱"],
        "pressure_responses": {
          "low": "装没听见",
          "mid": "讨价还价，先问你能给什么",
          "high": "拉一个人下水，分摊风险",
          "breaking": "直接去找主管摊牌"
        },
        "withdrawal": "把驾驶室的门关上，整夜只用对讲机说话",
        "prefers": ["用帮忙换帮忙"],
        "avoids": ["欠下说不清的人情"],
        "never": ["在对讲机里说别人的私事"]
      },
      "intimacy_tendency": {
        "attraction_sources": ["对方在夜里也守规矩", "对方记得{npc.ta}说过的小事"],
        "likes": ["在高处", "不说破"],
        "dislikes": ["被当成可以收买的人"],
        "preconditions": ["确定不会被工友知道"],
        "boundaries": ["不在上班时间"],
        "expression": "用递东西代替说话"
      },
      "voices": {
        "surface": "“七号，下一个。”——短，公事公办",
        "inner": "“你又站在那盏灯底下，是故意让我看见的吧。”"
      },
      "schedule": [
        {"from": 1200, "to": 1439, "location_id": "control_tower"},
        {"from": 0, "to": 480, "location_id": "control_tower"}
      ]
    }
  ],
  "background_cast": [
    {"id": "bg_lashing_crew", "role": "绑扎工", "function": "witness", "location_ids": ["berth_7"], "line": "他们什么都看见，但只在茶餐厅里说"}
  ],
  "channels": [
    {"id": "ch_radio", "text": "对讲机公共频道", "reach": "所有当班的人", "fidelity": "exact"},
    {"id": "ch_teahouse", "text": "茶餐厅的熟客", "reach": "第二天所有熟客", "fidelity": "distorted"}
  ],
  "tension_engines": [
    {"id": "te_same_roster", "text": "两人在同一张值班表上，每晚两点必然碰面"}
  ],
  "cast_combos": [
    {
      "id": "combo_1",
      "power_structure": "npc_high",
      "slots": ["crane_operator", "shift_lead"],
      "tension_engine_ids": ["te_same_roster"],
      "chemistry": "{crane_operator.name}看不起你，又需要你帮{crane_operator.ta}瞒一件事"
    }
  ],
  "daily_activities": [
    {"id": "a_supper", "title": "凌晨的宵夜", "location_ids": ["teahouse"], "duration_minutes": 40, "beats": ["抢最后一份叉烧", "有人提起白天的事"], "hook_ids": ["h1"]}
  ],
  "pressures": [
    {
      "id": "p_customs_raid",
      "title": "海关突击查柜",
      "source": "institution",
      "flags": ["timed"],
      "location_ids": ["berth_7"],
      "trigger": "对讲机里传来海关的车已经进了闸口",
      "objective": "在查到那个超重箱子之前做出决定",
      "choice": "替人瞒下，或者自己先报上去",
      "immediate": "查柜人员二十分钟后到七号泊位",
      "near": {"text": "明早主管要一份理货说明", "deadline_minutes": 660},
      "far": {"trigger": "三天后船东的人来码头", "consequence": "瞒下的人和说出去的人，船东都会记住"},
      "exits": [
        {"option": "把箱子挪到别的泊位", "cost": "要欠塔吊司机一个大人情"},
        {"option": "如实上报", "cost": "得罪带你入行的师傅"}
      ]
    }
  ],
  "hooks": [
    {"id": "h1", "kind": "approach", "slot": "crane_operator", "text": "{npc.name}把自己的保温杯推到你面前"}
  ],
  "twists": [
    {"id": "t1", "category": "人事", "requires": ["pressure"], "text": "新来的调度是{crane_operator.name}的前任"}
  ],
  "forbidden_terms": ["手机", "微信", "网购"],
  "content_tags": ["romance_light", "workplace"],
  "status": "draft",
  "notes": ""
}
```

字段语义：

- **世界层**：`era`、`region` 必填且具体；`style_hint` 一句，写给模型的文风提示；`clock_start.label` 是起始日的显示标签，可省略；`customs` 是可以直接写进正文的风俗与礼节；`rules` 是影响剧情的世界规则。
- **`extends`**：可以引用一个时代底包（D16），编译期展开，运行时不可见。
- **玩家身份池**：`social_position` 取 `low`、`equal`、`high`（相对于世界里的主要人物）；开局未指定玩家设定时，从这里抽取并按玩家的性别偏好渲染称谓。
- **地点档案**：`privacy` 取 `public`、`semi`、`private`；`visibility` 说明谁能看见这里；`witnesses` 引用背景人物；`exits` 引用其他地点 ID；`affordances` 是这个地点能让人做什么；`pressure_modifiers` 说明某个压力在这里有什么不同。亲密场景的描写受 `privacy` 与在场者约束，这由模型遵守、评审检查，引擎只在上下文里提供这些信息。
- **人物模板**：形状与 §3 的角色卡对应，运行时字段（`status`、具体年龄、具体姓名）在开局时生成。`gender: "any"` 表示由会话的性别偏好决定，此时模板内所有指代都必须用占位（D15）。`decision.pressure_responses` 必须有四档；`withdrawal` 是角色退缩时的具体表现。`schedule` 供离屏推演决定角色不在场时在哪里。
- **背景人物**：只有角色与功能（`witness`、`messenger`、`obstacle`、`rumor_source`、`helper`），可以被升格。
- **关系渠道**：消息传播的路径。`fidelity: "distorted"` 的渠道传出的消息用 `spread_rumor` 生成走样事实。
- **张力引擎**：独立于压力的、持续制造张力的结构（同一张值班表、同住一个院子、共同的秘密）。日常模式的张力主要来自这里。
- **人物组合**：`power_structure` 取 `player_high`、`npc_high`、`equal`、`switchable`；`slots` 引用人物模板；必须至少引用一个张力引擎。
- **压力五拍**：`trigger`（发生了什么）、`objective`（要在什么之前做到什么）、`choice`（真正的两难）、`immediate`（本场景内）、`near`（带 `deadline_minutes`）、`far`（`trigger` 与 `consequence`，开局时生成 `foreshadow` 事件）。`exits` 至少两条，每条都有代价。
- **压力标记**：`flags` 可含 `timed`（有明确倒计时）与 `leverage`（一方握有另一方的把柄或生计）。带 `leverage` 的压力必须声明 `leverage: {"holder", "subject", "basis"}`：`holder`、`subject` 取人物组合的槽位或 `player`，`basis` 是构成把柄的一句事实。开局时引擎据此生成事实与把柄记录（§5.3）。把柄生效期间，双方之间的亲密提交被拒（`INVARIANT_VIOLATION`，提示“处境不是同意”），直到把柄被解除；这把 `NARRATIVE_RULES.md` §7.1 的“处境永远不是同意”落到结构上。
- **钩子**：`kind` 取 `approach`（非交易性的靠近）、`observe`、`request`、`accident`。开局收尾优先用 `approach`。
- **转折**：`category` 取七类之一（信息、人事、资源、制度、时限、关系、意外）；`requires` 可以限定只在压力模式或只在日常模式出现。
- **禁用词表与状态**：`forbidden_terms` 是本世界不该出现的词，供跨世界扫描（`CONTENT_BIBLE.md` §6）；`status` 取 `draft`、`review`、`released`（`CONTENT_BIBLE.md` §7）。
- **占位语法**：`{npc.name}`、`{npc.ta}`（他/她/TA 的渲染）、`{slot_id.name}`、`{family}` 等。未解析的占位、引用不存在的 ID，都是 `CONTENT_ERROR`。

最低数量与质量标准见 `CONTENT_BIBLE.md` §3；下限是地板，不是目标。

### 8.2 自定义世界

自定义世界使用同一个模式，但最低数量降低（`CONTENT_BIBLE.md` §5），并带 `"custom": true`。它只存在于会话快照中。

### 8.3 编译产物

内容源文件编译为运行时读取的 JSON（可以合并成一个文件），带 `content_version`。运行时不解析源格式。

### 8.4 内容标签表

标签表是一个受控词表，放在内容目录中，用于边界匹配与提交声明。至少包含：亲密程度分级（`romance_light`、`intimate`、`explicit`）、`violence`、`coercion_theme`、`substance`、`pregnancy`、`humiliation`、`bodily_harm`、`death`、`workplace_power`、`infidelity`，以及 `custom`。实现者可以扩展。

## 9. 存档与导出

- 存档槽：`{name, session_id, revision, turn, world_title, clock_label, open_action, saved_at}`。存档是会话在某一 revision 的完整副本；读档创建新会话副本，不影响原存档。
- 槽名：允许中文，空白转为短横线，长度 ≤ 40，拒绝路径分隔符、控制字符和平台保留名。
- 导出路径只能落在数据目录的 `exports/` 下或用户明确给出的路径；拒绝路径穿越。
- 导出文件：

```json
{
  "format": "adult-tension-save",
  "schema_version": 1,
  "content_version": "2026.10.0",
  "rng_version": 1,
  "exported_at": "2026-10-01T12:00:00+08:00",
  "session": {}
}
```

- 导入时先校验全部字段；版本较旧时先备份再迁移；版本较新时报 `UNSUPPORTED_VERSION`。

## 10. 错误码

至少包括以下错误码，实现者可以增加：

| 码 | 含义 |
|---|---|
| `INVALID_INPUT` | 输入格式或字段错误 |
| `STALE_REVISION` | `expected_revision` 过期；错误中附当前 revision 与简要上下文 |
| `IDEMPOTENCY_CONFLICT` | 同一 `request_id` 携带了不同的内容 |
| `INVARIANT_VIOLATION` | 违反领域规则（冷却、知识边界、授权、幅度等） |
| `SAFETY_BLOCK` | 与硬边界冲突、暂停中、年龄问题 |
| `CONTENT_ERROR` | 内容包或自定义世界校验失败 |
| `NOT_FOUND` | 会话、存档、角色、事件不存在 |
| `SLOT_CONFLICT` | `reason: "exists"`：存档名已被占用；`reason: "changed_elsewhere"`：本局的当前槽已在别的对话里被写过，附 A/B/C 三个可选动作（`RUNTIME_PROTOCOL.md` §9.2） |
| `UNSUPPORTED_VERSION` | 存档或内容版本不受支持 |
| `RUNTIME_UNSUPPORTED` | Python 版本过低或缺少 SQLite 等必要能力 |
| `DATA_DIR_UNAVAILABLE` | 数据目录不可写；附尝试过的路径与建议 |
| `STORAGE_BUSY` | 数据库被其他进程短暂占用；用同一 `request_id` 重试 |
| `NO_MATCH` | 开局约束（锁定、排除、性别偏好）在所选世界中无法满足；附哪条约束冲突与可放宽项 |
| `INTERNAL_ERROR` | 未预期错误；附日志位置，状态不变 |

同一 `request_id`、相同内容的重复提交返回第一次的结果，不报错。
