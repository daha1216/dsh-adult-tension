<!-- 本文件由 tools/gen_references.py 生成，不要手改。 -->

# 自定义世界

玩家要的时代或地方不在任何世界里、并且选了自定义世界时，你写一个小型世界包，放进 `new-game` 的 `custom_world` 字段提交。引擎用与正式世界相同的校验器检查它：数量下限更低，其余规则一条不降。它只存在于这一局的存档里：不进世界列表，不参与开局去重，也不能“重开 N 号”（用同一个世界包和同一个种子重新开局即可复现）。

## 提交与修正

1. 先和玩家确认：时代与地方、日常还是有压力、想见到的两三个人。玩家没说的，按时代常识补齐，不要追问细节。
2. 从文末的示例改起，写一个 JSON 对象：`"custom": true`，`id` 用 `custom_` 开头的小写字母、数字、下划线，不写 `extends`。
3. 直接调用 `new-game`（不先用 `verify-content` 预检，它是开发工具），输入 `{"request_id", "mode", "custom_world": {...}}`；可带 `seed`、`player`、`npc_gender_preference`、`excludes.content_tags`，不带 `locks.world_id`、`excludes.world_ids`、`replay`。
4. 返回 `CONTENT_ERROR` 时，`details` 一次列出全部问题，路径以 `$.custom_world` 开头；逐条改好，换新的 `request_id` 重交。只有需要玩家补设定时才把问题讲给玩家。

## 数量下限

| 项 | 下限 |
|---|---|
| 世界规则 `rules` | 2 |
| 地点 `locations` | 2 |
| 人物模板 `character_templates` | 3 |
| 人物组合 `cast_combos` | 1 |
| 张力引擎 `tension_engines` | 1 |
| 玩家身份 `player_identities` | 1 |
| 钩子 `hooks` | 1 |
| 姓 `name_pools.family` | 4 |
| 名（女、男、中性名合计） | 4 |
| 按要开的模式：日常活动 `daily_activities` 或压力 `pressures` | 2 |

要开日常模式就写够日常活动，要开压力模式就写够压力；模式是“随便”时，只写够了一种就开那一种，两种都够就随机。其余列表（风俗、背景人物、关系渠道、转折、昵称规则）可以为空；写了就按同样的规则检查。名池小的世界，同性别的名用完后引擎先用中性名，再重复；每种性别各写 4 个名最稳妥。

## 不降低的规则

- **成年**：人物模板、背景人物、玩家身份的 `age_range` 下限 ≥ 18；人物模板与背景人物写明 `adult_context`（成年身份与处境）。
- **校园与师徒意象**：学生、师生、校园、学徒、徒弟、门生、弟子、少年、少女、幼、童 这类词只能出现在明示成年的语境里——同一条文字（或该人物的 `adult_context`）里要有 成年、成人、研究生、夜校、驻留、年满、已婚、正式工、正式雇员、持证 之类的词。
- **性别可变**：`gender: "any"` 的人物，文本里不写“他”“她”，用 `{npc.ta}`；人物组合、钩子、转折里用 `{槽位.name}`、`{槽位.ta}`。可用属性：`name`、`ta`、`family`、`given`、`call`、`role`、`title`。`{family}`、`{given}`、`{given_last}` 只用在称呼模板里。
- **占位的作用域**：人物模板与背景人物用 `npc`、`player`；钩子用 `npc`（即钩子的 `slot`）、`player`；人物组合用它的槽位与 `player`；转折用人物模板 ID 与 `player`；压力只有 `player`（带 `leverage` 时加上把柄双方）；日常活动只有 `player`；世界层、规则、地点、玩家身份、张力引擎、关系渠道的文字不用占位（玩家身份的称呼模板除外）。
- **引用按 ID**：地点出口、组合槽位与张力引擎、钩子槽位、活动与压力的地点都要能解析；ID 在包内唯一，`player` 是保留字。
- **时代**：`forbidden_terms` 写本世界不该出现的词（器物、说法），校验器扫描全部文本。
- **原创**：不用真实在世人物、已知作品的角色名与专有设定。
- **有内容**：不写空串、“待补”“TODO”“—”或与字段名相同的文字；同一包内不写重复的整句。地点至少一个 `public`、一个 `semi` 或 `private`，任意两个地点的 `privacy`、`visibility`、`affordances` 不能完全相同。
- **压力**：五拍齐全，`near.deadline_minutes` 大于 `immediate.minutes`，出路至少两条且各有代价；带 `leverage` 标记的压力写明 `leverage` 的双方与依据，双方要同在某个人物组合里。
- **标签**：`content_tags` 与各处 `tags` 只能用内容标签表里的 ID：`romance_light` 轻度暧昧、`intimate` 亲密、`explicit` 直白的性描写、`violence` 暴力、`coercion_theme` 胁迫、`humiliation` 羞辱、`bodily_harm` 身体伤害、`substance` 酒精与药物、`pregnancy` 怀孕、`death` 死亡、`workplace_power` 职场权力关系、`infidelity` 出轨、`crime` 违法犯罪、`gambling` 赌博、`workplace` 职场、`nightlife` 夜生活、`supernatural` 超自然、`disaster` 灾难、`custom` 自定义。

## 字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `schema_version` | 整数 1..1 | 是 |  |
| `id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `title` | 字符串，≤20 字 | 是 |  |
| `extends` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} 或 null | 否，默认 `null` | 时代底包 ID，编译期展开；自定义世界不写 |
| `custom` | 布尔 | 否，默认 `false` | 自定义世界必须为 true |
| `era` | 字符串，≤40 字 | 是 | 具体的时代 |
| `region` | 字符串，≤40 字 | 是 | 具体的地方 |
| `premise` | 字符串，≤200 字 | 是 | 人为什么同在此处、一天怎么过 |
| `tone` | 数组（字符串，≤12 字，1–8 项） | 是 | 基调词 |
| `style_hint` | 字符串，≤120 字 | 是 | 一句写给叙事者的文风提示，具体到句式或感官 |
| `clock_start` | 对象 | 是 |  |
| `clock_style` | 枚举：`hm` / `shichen` | 否，默认 `"hm"` | hm 显示 19:00；shichen 显示时辰 |
| `default_person` | 枚举：`second` / `first` / `third` | 否，默认 `"second"` | 叙述人称 |
| `default_npc_gender_mix` | 对象 | 是 | 性别可变的人物按这个比例定性别，之和为 1 |
| `stage_labels` | 对象 或 null | 否，默认 `null` | 按本世界的说法给关系阶段改名 |
| `name_pools` | 对象 | 是 |  |
| `rules` | 数组（对象（世界规则）） | 否，默认 `[]` | 影响剧情的世界规则 |
| `customs` | 数组（字符串，≤200 字） | 否，默认 `[]` | 可以直接写进正文的风俗与礼节 |
| `player_identities` | 数组（对象（玩家身份）） | 否，默认 `[]` | 玩家身份池；玩家没指定时从这里抽 |
| `locations` | 数组（对象（地点）） | 否，默认 `[]` | 地点档案 |
| `character_templates` | 数组（对象（人物模板）） | 否，默认 `[]` | 主要人物；具体姓名与年龄开局时生成 |
| `background_cast` | 数组（对象（背景人物）） | 否，默认 `[]` | 背景人物：只有角色与功能，可以被升格 |
| `channels` | 数组（对象（关系渠道）） | 否，默认 `[]` | 消息传播的路径 |
| `tension_engines` | 数组（对象（张力引擎）） | 否，默认 `[]` | 张力引擎 |
| `cast_combos` | 数组（对象（人物组合）） | 否，默认 `[]` | 谁和谁同场 |
| `daily_activities` | 数组（对象（日常活动）） | 否，默认 `[]` | 日常模式的开局活动 |
| `pressures` | 数组（对象（压力）） | 否，默认 `[]` | 压力模式的开局压力 |
| `hooks` | 数组（对象（钩子）） | 否，默认 `[]` | 开局收尾的钩子 |
| `twists` | 数组（对象（转折）） | 否，默认 `[]` | 转折候选 |
| `forbidden_terms` | 数组（字符串，≤20 字） | 否，默认 `[]` | 本世界不该出现的词 |
| `content_tags` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}） | 否，默认 `[]` | 本世界涉及的内容标签 |
| `status` | 枚举：`draft` / `review` / `released` | 是 | 自定义世界写 draft |
| `notes` | 字符串，≤2000 字 | 否，默认 `""` | 作者备注，运行时不读 |

### `clock_start` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `label` | 字符串，≤40 字 或 null | 否，默认 `null` | 起始日的显示标签 |
| `minute` | 整数 0..1439 | 是 | 开局时刻：从零点起的分钟（1140 即 19:00） |

### `default_npc_gender_mix` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `female` | 数值 [0, 1] | 是 |  |
| `male` | 数值 [0, 1] | 是 |  |
| `nonbinary` | 数值 [0, 1] | 否，默认 `0.0` |  |

### `stage_labels` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `stranger` | 字符串，≤8 字 | 否 |  |
| `acquainted` | 字符串，≤8 字 | 否 |  |
| `familiar` | 字符串，≤8 字 | 否 |  |
| `flirting` | 字符串，≤8 字 | 否 |  |
| `testing` | 字符串，≤8 字 | 否 |  |
| `intimate` | 字符串，≤8 字 | 否 |  |
| `committed` | 字符串，≤8 字 | 否 |  |

### `name_pools` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `family` | 数组（字符串，≤4 字） | 是 |  |
| `given_female` | 数组（字符串，≤4 字） | 是 |  |
| `given_male` | 数组（字符串，≤4 字） | 是 |  |
| `given_neutral` | 数组（字符串，≤4 字） | 是 |  |
| `nickname_patterns` | 数组（对象（称呼模板）） | 是 | 昵称规则，例如 小{family} |

### `rules[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `text` | 字符串，≤200 字 | 是 | 能在回合里改变一个选择的规则 |

### `player_identities[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `role` | 字符串，≤20 字 | 是 | 身份名，例如“长住的撰稿人” |
| `gender` | 枚举：`any` / `female` / `male` / `nonbinary` | 否，默认 `"any"` | any 表示按玩家设定 |
| `title_patterns` | 数组（对象（称呼模板），≥1 项） | 是 | 别人怎么称呼玩家，例如 {family}老师 |
| `age_range` | 数组（整数 0..120，2–2 项） | 是 | 年龄范围，下限 ≥ 18 |
| `social_position` | 枚举：`low` / `equal` / `high` | 是 | 相对于世界里主要人物的社会位置 |
| `baseline` | 字符串，≤200 字 | 是 | 玩家眼下的处境 |
| `resources` | 数组（字符串，≤80 字，≥1 项） | 是 | 玩家手里有什么 |
| `reputation` | 字符串，≤80 字 | 是 | 别人眼里的玩家 |
| `risks` | 数组（字符串，≤120 字，≥1 项） | 是 | 玩家怕失去什么 |

### `locations[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `name` | 字符串，≤20 字 | 是 |  |
| `detail` | 字符串，≤200 字 | 是 | 看得见、摸得着的细节 |
| `privacy` | 枚举：`public` / `semi` / `private` | 是 | public 人来人往；semi 半开放；private 关得上门 |
| `visibility` | 字符串，≤120 字 | 是 | 谁能看见这里发生的事 |
| `witnesses` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}） | 否，默认 `[]` | 常在这里的背景人物 ID |
| `exits` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}，≥1 项） | 是 | 相连的地点 ID |
| `affordances` | 数组（字符串，≤60 字，≥2 项） | 是 | 在这里能做的事 |
| `pressure_modifiers` | 对象（键 → 字符串，≤120 字） | 否，默认 `{}` | 压力 ID → 这个压力在这里有什么不同 |
| `tags` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}） | 否，默认 `[]` |  |

### `character_templates[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `gender` | 枚举：`any` / `female` / `male` / `nonbinary` | 是 | any 表示由会话的性别偏好决定，文本全部用占位 |
| `gender_reason` | 字符串，≤120 字 或 null | 否，默认 `null` | 性别写死时的叙事理由 |
| `age_range` | 数组（整数 0..120，2–2 项） | 是 | 年龄范围，下限 ≥ 18 |
| `adult_context` | 字符串，≤80 字 | 是 | 明示成年身份与处境的一句话 |
| `public_role` | 字符串，≤30 字 | 是 | 别人知道的身份 |
| `appearance_options` | 数组（字符串，≤120 字，≥2 项） | 是 | 外貌候选，开局抽一条 |
| `identity` | 对象 | 是 | 身份：权力、资源、限制、暴露点、隐藏的事 |
| `decision` | 对象 | 是 | 决策：NPC 按这些自己做决定 |
| `intimacy_tendency` | 对象 | 是 | 亲密倾向（不等于许可） |
| `voices` | 对象 | 是 | 表层与里层语态的示例 |
| `schedule` | 数组（对象，≥1 项） | 是 | 作息：一天里各时段在哪（从零点起的分钟），离屏推演用 |
| `situation` | 对象 | 是 | 这个人自己的处境：起因、压力、至少两条各有代价的出路 |
| `tags` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}） | 否，默认 `[]` |  |

### `background_cast[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `role` | 字符串，≤20 字 | 是 |  |
| `function` | 枚举：`witness` / `messenger` / `obstacle` / `rumor_source` / `helper` | 是 | 在剧情里起什么作用 |
| `location_ids` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}，≥1 项） | 是 | 常在的地点 |
| `line` | 字符串，≤120 字 | 是 | 一句描写，用 {npc.name} |
| `gender` | 枚举：`any` / `female` / `male` / `nonbinary` | 是 |  |
| `age_range` | 数组（整数 0..120，2–2 项） | 是 | 年龄范围，下限 ≥ 18 |
| `adult_context` | 字符串，≤80 字 | 是 | 明示成年身份的一句话 |
| `name` | 字符串，≤8 字 或 null | 否，默认 `null` | 固定名字；省略时开局生成 |

### `channels[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `text` | 字符串，≤60 字 | 是 | 渠道，例如“茶餐厅的熟客” |
| `reach` | 字符串，≤80 字 | 是 | 传到谁、多快 |
| `fidelity` | 枚举：`exact` / `distorted` | 是 | exact 原样传；distorted 传走样 |

### `tension_engines[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `text` | 字符串，≤120 字 | 是 | 不靠外部压力也持续制造张力的结构 |

### `cast_combos[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `power_structure` | 枚举：`player_high` / `npc_high` / `equal` / `switchable` | 是 | 玩家占上风、NPC 占上风、平等、可反转 |
| `player_positions` | 数组（枚举：`low` / `equal` / `high`，≥1 项） | 是 | 配得上的玩家社会位置 |
| `identity_ids` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}） | 否，默认 `[]` | 只配这些玩家身份；省略表示不限 |
| `slots` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}，1–4 项） | 是 | 同场的人物模板 ID |
| `tension_engine_ids` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}，≥1 项） | 是 | 用到的张力引擎 |
| `chemistry` | 字符串，≤200 字 | 是 | 人物之间的化学反应，用 {槽位.name} |
| `stakes` | 对象 | 是 |  |
| `relations` | 数组（对象，≥1 项） | 是 |  |
| `tags` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}） | 否，默认 `[]` |  |

### `daily_activities[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `title` | 字符串，≤20 字 | 是 |  |
| `location_ids` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}，≥1 项） | 是 | 可以发生的地点 |
| `duration_minutes` | 整数 5..600 | 是 | 时长（分钟） |
| `beats` | 数组（字符串，≤80 字，≥2 项） | 是 | 活动里会发生的小事 |
| `hook_ids` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}） | 否，默认 `[]` | 偏好的钩子 |
| `start_minute` | 整数 0..1439 或 null | 否，默认 `null` | 开局时刻（从零点起的分钟）；省略时用世界的起始时刻 |
| `tags` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}） | 否，默认 `[]` |  |

### `pressures[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `title` | 字符串，≤20 字 | 是 |  |
| `source` | 枚举：`institution` / `person` / `nature` / `money` / `rumor` / `accident` | 是 | 压力来自哪里 |
| `flags` | 数组（枚举：`timed` / `leverage`） | 否，默认 `[]` | timed 有明确倒计时；leverage 一方握有另一方的把柄或生计 |
| `location_ids` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}，≥1 项） | 是 | 可以发生的地点 |
| `trigger` | 字符串，≤120 字 | 是 | 发生了什么 |
| `objective` | 字符串，≤120 字 | 是 | 要在什么之前做到什么 |
| `choice` | 字符串，≤120 字 | 是 | 真正的两难 |
| `immediate` | 对象 | 是 | 立即层：本场景内看得见的压力 |
| `near` | 对象 | 是 | 近期层：带期限 |
| `far` | 对象 | 是 | 远期层：开局只作伏笔 |
| `exits` | 数组（对象，≥2 项） | 是 | 出路，至少两条，各有代价 |
| `leverage` | 对象 或 null | 否，默认 `null` | 带 leverage 标记时必填：holder、subject 取槽位或 player |
| `hook_ids` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}） | 否，默认 `[]` | 偏好的钩子 |
| `start_minute` | 整数 0..1439 或 null | 否，默认 `null` | 开局时刻（从零点起的分钟）；省略时用世界的起始时刻 |
| `tags` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}） | 否，默认 `[]` |  |

### `hooks[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `kind` | 枚举：`approach` / `observe` / `request` / `accident` | 是 | approach 非交易性的靠近（优先）；observe；request；accident |
| `slot` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 | 发出钩子的人物模板 ID |
| `location_ids` | 数组（字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40}） | 否，默认 `[]` | 只在这些地点；省略表示不限 |
| `text` | 字符串，≤120 字 | 是 | 开局收尾的动作，用 {npc.name} |

### `twists[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `category` | 枚举：`信息` / `人事` / `资源` / `制度` / `时限` / `关系` / `意外` | 是 |  |
| `requires` | 数组（字符串，≤40 字） | 否，默认 `[]` | 前提：pressure 或 daily（只在该模式）、人物模板 ID（该人物在局）、压力 ID |
| `text` | 字符串，≤160 字 | 是 |  |

### `nickname_patterns[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `pattern` | 字符串，≤20 字 | 是 |  |
| `gender` | 枚举：`any` / `female` / `male` / `nonbinary` | 否，默认 `"any"` |  |

### `title_patterns[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `pattern` | 字符串，≤20 字 | 是 |  |
| `gender` | 枚举：`any` / `female` / `male` / `nonbinary` | 否，默认 `"any"` |  |

### `identity` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `authority` | 字符串，≤120 字 | 是 | 能决定什么 |
| `resources` | 数组（字符串，≤80 字，≥1 项） | 是 | 手里有什么 |
| `limits` | 数组（字符串，≤80 字，≥1 项） | 是 | 做不到什么 |
| `obligations` | 数组（字符串，≤80 字） | 否，默认 `[]` | 对谁负有什么责任 |
| `exposure` | 字符串，≤120 字 | 是 | 一旦被人知道就麻烦的事 |
| `hidden` | 字符串，≤120 字 | 是 | 只有自己知道的事 |

### `decision` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `core_value` | 字符串，≤60 字 | 是 | 最看重的东西 |
| `goal_options` | 数组（字符串，≤80 字，≥2 项） | 是 | 目标候选，开局抽一条 |
| `pressure_responses` | 对象 | 是 | 四档压力下的反应：low、mid、high、breaking |
| `withdrawal` | 字符串，≤120 字 | 是 | 退缩时的具体表现 |
| `relationship_stance` | 字符串，≤80 字 | 是 | 对人的基本态度 |
| `contrast` | 字符串，≤80 字 | 是 | 表面和内里的反差 |
| `prefers` | 数组（字符串，≤80 字，≥1 项） | 是 | 偏好的做法 |
| `avoids` | 数组（字符串，≤80 字，≥1 项） | 是 | 回避的事 |
| `never` | 数组（字符串，≤80 字，≥1 项） | 是 | 无论如何不做的事 |

### `intimacy_tendency` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `attraction_sources` | 数组（字符串，≤80 字，≥2 项） | 是 | 被什么吸引 |
| `likes` | 数组（字符串，≤60 字，≥1 项） | 是 |  |
| `dislikes` | 数组（字符串，≤60 字，≥1 项） | 是 |  |
| `preconditions` | 数组（字符串，≤80 字，≥1 项） | 是 | 靠近之前需要的条件 |
| `boundaries` | 数组（字符串，≤80 字，≥1 项） | 是 | 不越过的线 |
| `expression` | 字符串，≤80 字 | 是 | 好感怎么表现出来 |
| `desire_range` | 数组（整数 0..5，2–2 项） | 是 | 欲望 0–5 的范围，开局取一个值 |
| `self_control_range` | 数组（整数 0..5，2–2 项） | 是 | 自制 0–5 的范围，开局取一个值 |
| `desired_position` | 字符串，≤40 字 | 是 | 想要的相处位置 |

### `voices` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `surface` | 字符串，≤120 字 | 是 | 说出口的话 |
| `inner` | 字符串，≤120 字 | 是 | 心里的话 |

### `schedule[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `from` | 整数 0..1439 | 是 |  |
| `to` | 整数 0..1439 | 是 |  |
| `location_id` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |

### `situation` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `trigger` | 字符串，≤120 字 | 是 |  |
| `pressure` | 字符串，≤120 字 | 是 |  |
| `exits` | 数组（对象，≥2 项） | 是 |  |

### `stakes` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `resource_gap` | 字符串，≤120 字 | 是 | 资源差异 |
| `limit_gap` | 字符串，≤120 字 | 是 | 限制差异 |
| `meeting_reason` | 字符串，≤120 字 | 是 | 为什么会遇到 |
| `irreplaceable_goal` | 字符串，≤120 字 | 是 | 一条不可被替代的个人目标 |

### `relations[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `a` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 | player 或槽位 |
| `b` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 | player 或槽位 |
| `stage` | 枚举：`stranger` / `acquainted` / `familiar` / `flirting` / `testing` / `intimate` / `committed` | 是 |  |
| `a_to_b` | 对象 | 是 |  |
| `b_to_a` | 对象 | 是 |  |
| `reason` | 字符串，≤80 字 | 是 |  |

### `immediate` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `text` | 字符串，≤120 字 | 是 |  |
| `minutes` | 整数 1..240 | 是 | 本场景的时长 |

### `near` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `text` | 字符串，≤120 字 | 是 |  |
| `deadline_minutes` | 整数 1..4320 | 是 | 从开局算起，大于 immediate.minutes |

### `far` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `trigger` | 字符串，≤120 字 | 是 |  |
| `consequence` | 字符串，≤120 字 | 是 |  |
| `due_days` | 整数 1..30 | 是 | 几天后 |

### `exits[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `option` | 字符串，≤80 字 | 是 |  |
| `cost` | 字符串，≤120 字 | 是 |  |

### `leverage` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `holder` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `subject` | 字符串，≤40 字，ASCII 小写短标识 [a-z0-9_]{1,40} | 是 |  |
| `basis` | 字符串，≤120 字 | 是 | 构成把柄的一句事实 |

### `pressure_responses` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `low` | 字符串，≤120 字 | 是 |  |
| `mid` | 字符串，≤120 字 | 是 |  |
| `high` | 字符串，≤120 字 | 是 |  |
| `breaking` | 字符串，≤120 字 | 是 |  |

### `a_to_b` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `trust` | 整数 -5..5 | 是 | 信任 |
| `tension` | 整数 0..5 | 是 | 张力 |

### `b_to_a` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `trust` | 整数 -5..5 | 是 | 信任 |
| `tension` | 整数 0..5 | 是 | 张力 |

## 示例

一个能通过校验、两种模式都能开局的最小世界：

```json
{
 "schema_version": 1,
 "id": "custom_guesthouse",
 "title": "淡季民宿",
 "custom": true,
 "era": "当代，十一月",
 "region": "北方海边小镇的一家民宿",
 "premise": "旅游季过去了，民宿只剩两个长住的客人和一个守店的人；风大的晚上，谁也不想一个人待在房间里。",
 "tone": ["冷风", "慢", "试探"],
 "style_hint": "多写风声、暖气片和海的颜色；对话短，停顿多。",
 "clock_start": {"label": "十一月的第二个周末", "minute": 1140},
 "default_npc_gender_mix": {"female": 0.5, "male": 0.5},
 "name_pools": {
  "family": ["林", "许", "周", "宋"],
  "given_female": ["晚晴", "若溪", "静宜", "书瑶"],
  "given_male": ["远舟", "启明", "振声", "海川"],
  "given_neutral": ["一帆", "知秋"],
  "nickname_patterns": [{"pattern": "小{family}", "gender": "any"}]
 },
 "rules": [
  {"id": "r_heating", "text": "锅炉晚上十一点自动关，之后只有一楼客厅的壁炉是暖的。"},
  {"id": "r_ferry", "text": "去市区的末班车下午五点就走，天黑以后谁也离不开镇子。"}
 ],
 "customs": ["守店的人每晚九点在客厅煮一锅姜茶，谁下来谁喝。"],
 "player_identities": [
  {
   "id": "long_stay_writer",
   "role": "长住的撰稿人",
   "title_patterns": [{"pattern": "{family}老师", "gender": "any"}],
   "age_range": [28, 45],
   "social_position": "equal",
   "baseline": "来这里赶一本拖了半年的稿子，已经住了三个星期。",
   "resources": ["一台旧笔记本", "付到月底的房费"],
   "reputation": "早出晚归，客气但不熟",
   "risks": ["编辑下周要来看稿"]
  }
 ],
 "locations": [
  {
   "id": "living_room",
   "name": "一楼客厅",
   "detail": "壁炉、长沙发、一整面对着海的窗，窗框被风吹得轻轻响。",
   "privacy": "public",
   "visibility": "住客进出都要经过，门口和楼梯口都能看见沙发，只有壁炉边的角落看不见",
   "exits": ["terrace"],
   "affordances": ["坐在壁炉边烤手", "借一本架子上的旧书"]
  },
  {
   "id": "terrace",
   "name": "屋顶露台",
   "detail": "晾衣绳上挂着没收的床单，能看见整条黑下来的海岸线。",
   "privacy": "private",
   "visibility": "只有从客厅的楼梯上来才看得见",
   "exits": ["living_room"],
   "affordances": ["一起把床单收下来", "躲在床单后面避风"]
  }
 ],
 "character_templates": [
  {
   "id": "keeper",
   "gender": "any",
   "age_range": [30, 42],
   "adult_context": "民宿的合伙人，淡季一个人守店",
   "public_role": "守店的人",
   "appearance_options": ["袖口总挽到手肘，手背上有烫伤的旧疤", "围一条洗得发白的格子围巾，走路很轻"],
   "identity": {"authority": "决定谁能用壁炉、谁的房费可以晚交", "resources": ["每个房间的备用钥匙"], "limits": ["合伙人在城里，大事要打电话问"], "exposure": "民宿其实下个月就要转让，还没告诉长住的客人", "hidden": "想留下来的只有{npc.ta}自己"},
   "decision": {"core_value": "把手上的事做完", "goal_options": ["撑过这个冬天", "找到愿意接手的人"], "pressure_responses": {"low": "笑一笑，去厨房再烧一壶水", "mid": "把话题转到天气上", "high": "直接说出转让的事", "breaking": "关了店，当晚就走"}, "withdrawal": "整晚待在厨房，门开着一条缝", "relationship_stance": "对长住的人好，但不交底", "contrast": "看上去什么都不在乎，其实记得每个客人喝茶放不放糖", "prefers": ["用做事代替说话"], "avoids": ["被人可怜"], "never": ["翻客人的东西"]},
   "intimacy_tendency": {"attraction_sources": ["对方愿意帮忙干活", "对方不追问{npc.ta}的过去"], "likes": ["安静的陪伴"], "dislikes": ["被人一眼看穿"], "preconditions": ["确定对方不是一时兴起"], "boundaries": ["不在客房里"], "expression": "把最好的那只杯子留给对方", "desire_range": [1, 4], "self_control_range": [3, 5], "desired_position": "平等，各自有退路"},
   "voices": {"surface": "“姜茶在锅里，自己盛。”", "inner": "“你要是也走了，这里就真的只剩风了。”"},
   "schedule": [{"from": 1080, "to": 1439, "location_id": "living_room"}, {"from": 0, "to": 1079, "location_id": "terrace"}],
   "situation": {"trigger": "合伙人今晚打电话，说有人想来看房", "pressure": "看房的人明早就到，客人们还什么都不知道", "exits": [{"option": "今晚就告诉大家", "cost": "长住的客人可能提前搬走"}, {"option": "先瞒着", "cost": "明早被撞见时更难解释"}]}
  },
  {
   "id": "photographer",
   "gender": "any",
   "age_range": [26, 38],
   "adult_context": "独立摄影师，接商业单子养活自己",
   "public_role": "来拍冬海的摄影师",
   "appearance_options": ["相机一直挂在脖子上，镜头盖总是找不到", "头发被风吹得乱糟糟，自己也不在意"],
   "identity": {"authority": "决定拍谁、不拍谁", "resources": ["一台老胶片机和最后三卷胶卷"], "limits": ["钱只够再住十天"], "exposure": "这次来其实是躲一个合作方", "hidden": "那组冬海的照片是给已经分开的人的"},
   "decision": {"core_value": "只拍真的东西", "goal_options": ["拍到一次暴风前的海", "决定要不要回城"], "pressure_responses": {"low": "举起相机，把话题拍掉", "mid": "开个玩笑，说自己明天就走", "high": "把胶卷交给别人保管", "breaking": "连夜收拾东西"}, "withdrawal": "一整天待在海边，谁也不理", "relationship_stance": "先靠近，再后退一步", "contrast": "看上去最随便，冲洗照片时比谁都认真", "prefers": ["并肩走，不面对面"], "avoids": ["被问什么时候回去"], "never": ["偷拍别人"]},
   "intimacy_tendency": {"attraction_sources": ["对方在镜头前不躲", "对方能陪{npc.ta}在风里站很久"], "likes": ["黄昏"], "dislikes": ["被安排好的浪漫"], "preconditions": ["双方都清楚这可能只是一个冬天"], "boundaries": ["不拍对方不愿意的样子"], "expression": "把刚冲好的一张照片塞进对方口袋", "desire_range": [2, 4], "self_control_range": [2, 4], "desired_position": "轮流主导"},
   "voices": {"surface": "“别动，光正好。”", "inner": "“我拍了你十几张，一张都不敢给你看。”"},
   "schedule": [{"from": 960, "to": 1439, "location_id": "terrace"}, {"from": 0, "to": 959, "location_id": "living_room"}],
   "situation": {"trigger": "躲着的合作方打听到了{npc.ta}在这个镇子", "pressure": "对方说周末要来当面谈", "exits": [{"option": "见一面把话说清楚", "cost": "那组照片可能保不住"}, {"option": "再换一个地方躲", "cost": "钱只够买一张车票"}]}
  },
  {
   "id": "night_guest",
   "gender": "any",
   "age_range": [32, 50],
   "adult_context": "外地来的工程监理，住在镇上等风停",
   "public_role": "被风困住的过路客",
   "appearance_options": ["工装外套上还沾着水泥灰", "说话前总先清一下嗓子"],
   "identity": {"authority": "能签字决定码头工程停不停", "resources": ["一辆停在镇口的皮卡"], "limits": ["工程不停，每天都要去工地看一眼"], "exposure": "工地上周出了点事，报告还没交", "hidden": "其实是这家民宿老板的旧识"},
   "decision": {"core_value": "说话算数", "goal_options": ["等风停就走", "弄清楚民宿为什么要卖"], "pressure_responses": {"low": "沉默，喝完手里的茶", "mid": "用工程上的事岔开", "high": "直说自己认识老板", "breaking": "开车冒着风走"}, "withdrawal": "回到皮卡里坐着，发动机一直开着暖风", "relationship_stance": "不主动，但有求必应", "contrast": "看起来最硬的人，每晚都给家里的老狗打电话问好", "prefers": ["把话说在明处"], "avoids": ["欠别人的情"], "never": ["在背后议论人"]},
   "intimacy_tendency": {"attraction_sources": ["对方说话算数", "对方不怕{npc.ta}的沉默"], "likes": ["一起修东西"], "dislikes": ["拐弯抹角"], "preconditions": ["事情都摆在明处"], "boundaries": ["不做让人说闲话的事"], "expression": "默默把对方的车窗擦干净", "desire_range": [1, 3], "self_control_range": [4, 5], "desired_position": "照顾对方，但不替对方做主"},
   "voices": {"surface": "“风明天下午停，我查过了。”", "inner": "“我在这儿多住一晚，不全是因为风。”"},
   "schedule": [{"from": 1140, "to": 1439, "location_id": "living_room"}, {"from": 0, "to": 1139, "location_id": "terrace"}],
   "situation": {"trigger": "工地打来电话，报告明天必须交", "pressure": "要么照实写，要么替手下的人担着", "exits": [{"option": "照实写", "cost": "手下的人会丢工作"}, {"option": "自己担下来", "cost": "明年的工程可能拿不到"}]}
  }
 ],
 "tension_engines": [
  {"id": "te_one_fire", "text": "整栋楼只剩一楼的壁炉是暖的，晚上谁也躲不开谁"}
 ],
 "cast_combos": [
  {
   "id": "combo_storm_night",
   "power_structure": "equal",
   "player_positions": ["equal"],
   "slots": ["keeper", "photographer"],
   "tension_engine_ids": ["te_one_fire"],
   "chemistry": "{keeper.name}守着这家店，{photographer.name}住在你隔壁；三个人都有一件没说出口的事，风大的晚上都下楼来烤火。",
   "stakes": {"resource_gap": "{keeper.name}有全部的钥匙，你只有到月底的房费", "limit_gap": "你得赶稿，{photographer.name}的钱只够再住十天", "meeting_reason": "淡季里最后几个没走的人", "irreplaceable_goal": "你想在编辑来之前写完最后一章"},
   "relations": [
    {"a": "player", "b": "keeper", "stage": "acquainted", "a_to_b": {"trust": 1, "tension": 0}, "b_to_a": {"trust": 1, "tension": 1}, "reason": "住了三个星期，每晚都喝{keeper.name}煮的姜茶"},
    {"a": "player", "b": "photographer", "stage": "stranger", "a_to_b": {"trust": 0, "tension": 1}, "b_to_a": {"trust": 0, "tension": 1}, "reason": "住隔壁，只在楼梯上点过头"},
    {"a": "keeper", "b": "photographer", "stage": "acquainted", "a_to_b": {"trust": 0, "tension": 1}, "b_to_a": {"trust": 1, "tension": 0}, "reason": "房费是按天付的，{keeper.name}从来没催过"}
   ]
  }
 ],
 "daily_activities": [
  {"id": "a_ginger_tea", "title": "九点的姜茶", "location_ids": ["living_room"], "duration_minutes": 40, "beats": ["锅里的姜茶快见底了", "有人问起楼上那盏总亮着的灯"]},
  {"id": "a_sheets", "title": "收床单", "location_ids": ["terrace"], "duration_minutes": 20, "beats": ["一阵风把床单掀到栏杆外", "两个人同时伸手去抓"]}
 ],
 "pressures": [
  {
   "id": "p_viewing",
   "title": "明早有人来看房",
   "source": "person",
   "flags": ["timed"],
   "location_ids": ["living_room"],
   "trigger": "合伙人在电话里说，买家明早九点来看房",
   "objective": "在客人们下楼吃早饭之前，决定转让的事说不说",
   "choice": "今晚说出实情，还是让大家明早自己撞见",
   "immediate": {"text": "守店的人在客厅里打完这通电话，一抬头就看见了你", "minutes": 20},
   "near": {"text": "明早九点买家进门", "deadline_minutes": 840},
   "far": {"trigger": "月底合伙人回镇上办手续", "consequence": "留下的人和先走的人，都要重新决定这个冬天住在哪", "due_days": 5},
   "exits": [
    {"option": "今晚就在壁炉边告诉所有人", "cost": "长住的客人可能提前退房"},
    {"option": "替守店的人瞒到买家走", "cost": "明早被撞见时，你也成了知情不报的人"}
   ],
   "start_minute": 1140
  },
  {
   "id": "p_storm_tide",
   "title": "今晚的风暴潮",
   "source": "nature",
   "flags": ["timed"],
   "location_ids": ["terrace", "living_room"],
   "trigger": "镇上的广播喇叭说今晚十点风暴潮到岸，让人别出门",
   "objective": "在风到之前把露台上的东西收下来、把窗钉牢",
   "choice": "冒风上露台抢收，还是守在一楼等别人去",
   "immediate": {"text": "露台上的床单已经被风扯开了一角", "minutes": 15},
   "near": {"text": "十点整风暴潮到岸", "deadline_minutes": 180},
   "far": {"trigger": "风停以后镇上来人检查受损的房子", "consequence": "民宿要是被判定不安全，这个冬天谁也住不下去", "due_days": 2},
   "exits": [
    {"option": "一起上露台抢收", "cost": "风太大，有人可能会受伤"},
    {"option": "放弃露台，只守一楼", "cost": "晾着的东西全被吹走，第二天要赔"}
   ],
   "start_minute": 1140
  }
 ],
 "hooks": [
  {"id": "h_blanket", "kind": "approach", "slot": "keeper", "text": "{npc.name}把沙发上唯一的毯子往你那边推了推"}
 ],
 "forbidden_terms": ["飞船", "魔法"],
 "content_tags": ["romance_light"],
 "status": "draft",
 "notes": "自定义世界的最小示例（references/custom_world.md 引用）"
}
```
