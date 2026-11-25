<!-- 本文件由 tools/gen_references.py 生成，不要手改。 -->

# 自定义世界

玩家要的时代或地方不在任何世界里、并且选了自定义世界时，你写一个小型世界包，放进 `new-game` 的 `custom_world` 字段提交。引擎用与正式世界相同的校验器检查它：数量下限更低，其余规则一条不降。它存在这一局的存档里（玩家说“保存世界”才另存一份）：不进世界列表，不参与开局去重，也不能“重开 N 号”（用同一个世界包和同一个种子重新开局即可复现）。

## 提交与修正

1. 先和玩家确认：时代与地方、日常还是压力、想见到的两三个人。玩家没说的，按时代常识补齐，不要追问细节。
2. 从文末的示例改起，写一个 JSON 对象：`"custom": true`，`id` 建议以 `custom_` 开头的小写字母、数字、下划线，避免与内置世界重名，不写 `extends`。
3. 直接调用 `new-game`（不先用 `verify-content` 预检，它是开发工具），输入 `{"request_id", "mode", "custom_world": {...}}`；可带 `seed`、`player`、`npc_gender_preference`、`preferences`、`excludes.content_tags`，不带 `world_query`、`my_world`、`locks.world_id`、`excludes.world_ids`、`replay`。
4. 返回 `CONTENT_ERROR` 时，`details` 一次列出全部问题，路径以 `$.custom_world` 开头；逐条改好，换新的 `request_id` 重新提交。只有需要玩家补设定时才把问题讲给玩家。
5. 开局后玩家说“保存世界 名字”：`save-world` 存下这一局的世界包；以后 `new-game` 带 `"my_world": "名字"`（不写 `custom_world`）再开，运行时按同样的规则重新校验。`my-worlds` 列出，`delete-world` 删除。

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
- **校园与师徒意象**：学生、师生、校园、学徒、徒弟、门生、弟子、少年、少女、幼、童 这类词只能出现在明示成年的语境里——同一条文字（或该人物的 `adult_context`）里要有 成年、成人、大学、本科、研究生、硕士、博士、夜校、驻留、年满、已婚、正式工、正式雇员、持证 之类的词。
- **性别可变**：`gender: "any"` 的人物，文本里不写“他”“她”，用 `{npc.ta}`；人物组合用 `{槽位.name}`/`{槽位.ta}`，钩子用 `{npc.*}` 或 `{槽位.*}`，转折用已写进 `requires` 的 `{模板ID.*}`。可用属性：`name`、`ta`、`family`、`given`、`call`、`role`、`title`。`{family}`、`{given}`、`{given_last}` 只用在称呼模板里。
- **占位的作用域**：人物模板与背景人物用 `npc`、`player`；钩子用 `npc` 或其 `slot`、`player`；人物组合用它的槽位与 `player`；转折用已写进其 `requires` 的人物模板 ID 与 `player`；压力只有 `player`（带 `leverage` 时加上把柄双方）；日常活动只有 `player`；世界层、规则、地点、玩家身份、张力引擎、关系渠道的文字不用占位（玩家身份的称呼模板除外）。注意原样显示字段（人物模板的 `adult_context`/`public_role`/`gender_reason`、背景人物的 `adult_context`/`role`/`name`、日常活动与压力的 `title`、地点的 `name`）不做占位替换，严禁写 `{...}`。
- **引用按 ID**：地点出口、组合槽位与张力引擎、钩子槽位、活动与压力的地点都要能解析；ID 在包内唯一，`player` 是保留字。
- **时代**：`forbidden_terms` 写本世界不该出现的词（器物、说法），校验器扫描全部文本。
- **有内容**：不写空串、“待补”“TODO”“—”或与字段名相同的文字；同一包内不写重复的整句。地点至少一个 `public`、一个 `semi` 或 `private`，任意两个地点的 `privacy`、`visibility`、`affordances` 不能完全相同。
- **压力**：五拍齐全，`near.deadline_minutes` 大于 `immediate.minutes`，出路至少两条且各有代价；带 `leverage` 标记的压力写明 `leverage` 的双方与依据，`holder` 与 `subject` 可为槽位或 `player`（双向均可拿捏），其中的非 `player` 槽位要同在某个人物组合里。
- **篇幅**：一个人物模板的全部文字合计 ≤ 1800 字，一个压力 ≤ 450 字（不含 ID 与标签）——在场的人物卡与压力每回合都进上下文，太长会挤掉别人。
- **称呼**：带性别的称呼（先生、小姐、少爷、哥、姐……）只给性别已定的人：这样的称呼与绰号模板要标上 `male` 或 `female`；不限性别的玩家身份要同时有给男、女玩家的称呼；正文里不写“{player.name}先生”，用 `{player.title}` 或 `{player.call}`。绰号模板会抽给本世界任何同性别的人，所以只写人人适用的叫法（小{family}、阿{given_last}、{given}），不写职务头衔。
- **人名**：人物的名字由引擎从名字池抽取，正文里不写名字池里的名字（两个字以上的名），用 `{npc.name}`、`{槽位.given}` 这类占位或身份称呼；名字池里也不放会在正文里当普通词用的名（秋水、斥候），也不放背景人物已经用掉的名。
- **标签**：`content_tags` 与各处 `tags` 只能用内容标签表里的 ID：`romance_light` 轻度暧昧、`intimate` 亲密、`explicit` 直白的性描写、`violence` 暴力、`coercion_theme` 胁迫、`humiliation` 羞辱、`bodily_harm` 身体伤害、`substance` 酒精与药物、`pregnancy` 怀孕、`death` 死亡、`workplace_power` 职场权力关系、`infidelity` 出轨、`crime` 违法犯罪、`gambling` 赌博、`workplace` 职场、`nightlife` 夜生活、`supernatural` 超自然、`disaster` 灾难（`custom` 仅用于玩家边界，不用于世界筛选与内容标签）。

## 字段

字段类型简写：`ID` = ASCII 小写短标识 `[a-z0-9_]{1,40}`（≤40 字）。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `schema_version` | 整数 1..1 | 是 |  |
| `id` | `ID` | 是 |  |
| `title` | 字符串，≤40 字 | 是 |  |
| `extends` | `ID` 或 null | 否，默认 `null` | 时代底包 ID，编译期展开；自定义世界不写 |
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
| `daily_activities` | 数组（对象（日常活动）） | 否，默认 `[]` | 日常模式的开局活动（亦为完整上下文提供 scene_ideas 场景灵感） |
| `pressures` | 数组（对象（压力）） | 否，默认 `[]` | 压力模式的开局压力 |
| `hooks` | 数组（对象（钩子）） | 否，默认 `[]` | 开局收尾的钩子 |
| `twists` | 数组（对象（转折）） | 否，默认 `[]` | 转折候选（可绑定 standby_cast 待命角色实现突袭入局） |
| `forbidden_terms` | 数组（字符串，≤20 字） | 否，默认 `[]` | 本世界不该出现的词 |
| `content_tags` | 数组（`ID`） | 否，默认 `[]` | 本世界涉及的内容标签 |
| `status` | 枚举：`draft` / `review` / `released` | 是 | 自定义世界写 draft |
| `notes` | 字符串，≤2000 字 | 否，默认 `""` | 作者备注，运行时不读 |

### `clock_start` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `label` | 字符串，≤40 字 或 null | 否，默认 `null` | 起始日的显示标签：只写日期、季节或天气，不写钟点、时段和倒计时 |
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
| `nickname_patterns` | 数组（对象（称呼模板）） | 是 | 昵称规则，例如 小{family}；会抽给任何同性别的人，不写职务头衔 |
| `order` | 枚举：`family_first` / `given_first` | 否，默认 `"family_first"` | family_first 姓在前（沈砚舟）；given_first 名在前、姓在后，用“·”连接（艾达·米勒） |

### `rules[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | `ID` | 是 |  |
| `text` | 字符串，≤200 字 | 是 | 能在回合里改变一个选择的规则 |

### `player_identities[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | `ID` | 是 |  |
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
| `id` | `ID` | 是 |  |
| `name` | 字符串，≤20 字 | 是 |  |
| `detail` | 字符串，≤200 字 | 是 | 看得见、摸得着的细节 |
| `privacy` | 枚举：`public` / `semi` / `private` | 是 | public 人来人往；semi 半开放；private 关得上门 |
| `visibility` | 字符串，≤120 字 | 是 | 谁能看见这里发生的事 |
| `witnesses` | 数组（`ID`） | 否，默认 `[]` | 常在这里的背景人物 ID |
| `exits` | 数组（`ID`，≥1 项） | 是 | 相连的地点 ID |
| `affordances` | 数组（字符串，≤60 字，≥2 项） | 是 | 在这里能做的事 |
| `pressure_modifiers` | 对象（键 → 字符串，≤120 字） | 否，默认 `{}` | 压力 ID → 这个压力在这里有什么不同 |
| `tags` | 数组（`ID`） | 否，默认 `[]` |  |

### `character_templates[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | `ID` | 是 |  |
| `gender` | 枚举：`any` / `female` / `male` / `nonbinary` | 是 | any 表示由本局的配对偏好决定，文本全部用占位 |
| `gender_reason` | 字符串，≤120 字 或 null | 否，默认 `null` | 性别写死时的叙事理由 |
| `age_range` | 数组（整数 0..120，2–2 项） | 是 | 年龄范围，下限 ≥ 18 |
| `adult_context` | 字符串，≤80 字 | 是 | 明示成年身份与处境的一句话 |
| `public_role` | 字符串，≤30 字 | 是 | 别人知道的身份 |
| `appearance_options` | 数组（字符串，≤120 字，≥2 项） | 是 | 外貌候选，开局抽一条 |
| `identity` | 对象 | 是 | 身份：权力、资源、限制、暴露点、隐藏的事 |
| `decision` | 对象 | 是 | 决策：NPC 按这些自己做决定 |
| `intimacy_tendency` | 对象 | 是 | 私密偏好、敏感防线与失守表现 |
| `voices` | 对象 | 是 | 表层与里层语态的示例 |
| `schedule` | 数组（对象，≥1 项） | 是 | 作息：一天里各时段在哪（从零点起的分钟），离屏推演用 |
| `situation` | 对象 | 是 | 这个人自己的处境：起因、压力、至少两条各有代价的出路 |
| `tags` | 数组（`ID`） | 否，默认 `[]` |  |

### `background_cast[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | `ID` | 是 |  |
| `role` | 字符串，≤20 字 | 是 |  |
| `function` | 枚举：`witness` / `messenger` / `obstacle` / `rumor_source` / `helper` | 是 | 在剧情里起什么作用 |
| `location_ids` | 数组（`ID`，≥1 项） | 是 | 常在的地点 |
| `line` | 字符串，≤120 字 | 是 | 一句描写，用 {npc.name} |
| `gender` | 枚举：`any` / `female` / `male` / `nonbinary` | 是 |  |
| `age_range` | 数组（整数 0..120，2–2 项） | 是 | 年龄范围，下限 ≥ 18 |
| `adult_context` | 字符串，≤80 字 | 是 | 明示成年身份的一句话 |
| `name` | 字符串，≤8 字 或 null | 否，默认 `null` | 固定名字；省略时开局生成 |

### `channels[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | `ID` | 是 |  |
| `text` | 字符串，≤60 字 | 是 | 渠道，例如“茶餐厅的熟客” |
| `reach` | 字符串，≤80 字 | 是 | 传到谁、多快 |
| `fidelity` | 枚举：`exact` / `distorted` | 是 | exact 原样传；distorted 传走样 |

### `tension_engines[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | `ID` | 是 |  |
| `text` | 字符串，≤120 字 | 是 | 不靠外部压力也持续制造张力的结构 |

### `cast_combos[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | `ID` | 是 |  |
| `power_structure` | 枚举：`player_high` / `npc_high` / `equal` / `switchable` | 是 | 玩家占上风、NPC 占上风、平等、可反转 |
| `player_positions` | 数组（枚举：`low` / `equal` / `high`，≥1 项） | 是 | 配得上的玩家社会位置 |
| `identity_ids` | 数组（`ID`） | 否，默认 `[]` | 只配这些玩家身份；省略表示不限 |
| `slots` | 数组（`ID`，1–4 项） | 是 | 同场的人物模板 ID |
| `tension_engine_ids` | 数组（`ID`，≥1 项） | 是 | 用到的张力引擎 |
| `chemistry` | 字符串，≤200 字 | 是 | 人物之间的化学反应，用 {槽位.name} |
| `stakes` | 对象 | 是 |  |
| `relations` | 数组（对象，≥1 项） | 是 |  |
| `tags` | 数组（`ID`） | 否，默认 `[]` |  |

### `daily_activities[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | `ID` | 是 |  |
| `title` | 字符串，≤20 字 | 是 |  |
| `location_ids` | 数组（`ID`，≥1 项） | 是 | 可以发生的地点 |
| `duration_minutes` | 整数 5..600 | 是 | 时长（分钟） |
| `beats` | 数组（字符串，≤80 字，≥2 项） | 是 | 活动推进节拍（首条同时作为完整上下文 world.scene_ideas 的场景灵感） |
| `hook_ids` | 数组（`ID`） | 否，默认 `[]` | 偏好的钩子 |
| `start_minute` | 整数 0..1439 或 null | 否，默认 `null` | 开局时刻（从零点起的分钟）；省略时用世界的起始时刻 |
| `tags` | 数组（`ID`） | 否，默认 `[]` |  |

### `pressures[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | `ID` | 是 |  |
| `title` | 字符串，≤20 字 | 是 |  |
| `source` | 枚举：`institution` / `person` / `nature` / `money` / `rumor` / `accident` | 是 | 压力来自哪里 |
| `flags` | 数组（枚举：`timed` / `leverage`） | 否，默认 `[]` | timed 有明确倒计时；leverage 一方握有另一方的把柄或生计 |
| `location_ids` | 数组（`ID`，≥1 项） | 是 | 可以发生的地点 |
| `trigger` | 字符串，≤120 字 | 是 | 发生了什么 |
| `objective` | 字符串，≤120 字 | 是 | 要在什么之前做到什么 |
| `choice` | 字符串，≤120 字 | 是 | 真正的两难 |
| `immediate` | 对象 | 是 | 立即层：本场景内看得见的压力 |
| `near` | 对象 | 是 | 近期层：带期限 |
| `far` | 对象 | 是 | 远期层：开局只作伏笔 |
| `exits` | 数组（对象，≥2 项） | 是 | 出路，至少两条，各有代价 |
| `leverage` | 对象 或 null | 否，默认 `null` | 带 leverage 标记时必填：holder、subject 取槽位或 player |
| `hook_ids` | 数组（`ID`） | 否，默认 `[]` | 偏好的钩子 |
| `start_minute` | 整数 0..1439 或 null | 否，默认 `null` | 开局时刻（从零点起的分钟）；省略时用世界的起始时刻 |
| `tags` | 数组（`ID`） | 否，默认 `[]` |  |

### `hooks[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | `ID` | 是 |  |
| `kind` | 枚举：`approach` / `observe` / `request` / `accident` | 是 | approach 主动近身试探（占优，停在贴身未决瞬间）；observe 暗中观察；request 开口相求；accident 突发擦碰 |
| `slot` | `ID` | 是 | 发出钩子的人物模板 ID |
| `location_ids` | 数组（`ID`） | 否，默认 `[]` | 只在这些地点；省略表示不限 |
| `text` | 字符串，≤120 字 | 是 | 开局收尾的动作，用 {npc.name} |

### `twists[]` 的字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | `ID` | 是 |  |
| `category` | 枚举：`信息` / `人事` / `资源` / `制度` / `时限` / `关系` / `意外` | 是 |  |
| `requires` | 数组（字符串，≤40 字） | 否，默认 `[]` | 前提：pressure 或 daily（限定模式）、人物模板 ID（绑定在场或 standby_cast 待命角色并解锁其占位符）、压力 ID |
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
| `likes` | 数组（字符串，≤60 字，≥1 项） | 是 | 喜欢的亲近方式或细节 |
| `dislikes` | 数组（字符串，≤60 字，≥1 项） | 是 | 反感的亲近方式或举动 |
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
| `location_id` | `ID` | 是 |  |

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
| `a` | `ID` | 是 | player 或槽位 |
| `b` | `ID` | 是 | player 或槽位 |
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
| `holder` | `ID` | 是 |  |
| `subject` | `ID` | 是 |  |
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
 "premise": "旅游季过了，海边民宿只剩两个长住客和一个守店人；暴风夜停暖封路，暗夜里的秘密与体温比壁炉火光更烫。",
 "tone": ["海风", "私密", "试探", "紧绷"],
 "style_hint": "多写潮声、壁炉余烬、毛衣摩擦与耳畔呼吸；体面客套下暗流贴身，停顿处留住未撤回的指尖。",
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
  {"id": "r_heating", "text": "锅炉晚上十一点自动停暖，之后整栋楼只有一楼客厅的壁炉和窄沙发透着热气。"},
  {"id": "r_ferry", "text": "去市区的末班车下午五点就走，入夜起风后谁也离不开发潮的海边镇子。"}
 ],
 "customs": ["守店的人每晚九点在客厅煮一锅加烈酒的姜茶，谁下来谁就能分一杯暖身。"],
 "player_identities": [
  {
   "id": "long_stay_writer",
   "role": "长住的撰稿人",
   "title_patterns": [{"pattern": "{family}老师", "gender": "any"}],
   "age_range": [28, 45],
   "social_position": "equal",
   "baseline": "来这里赶一本拖了半年的稿子，已经住了三个星期，摸清了整栋楼的动静。",
   "resources": ["一台旧笔记本", "付到月底的房费", "几张昨晚在走廊捡到的底价单残页"],
   "reputation": "早出晚归，面上客气克制，眼睛却毒得很",
   "risks": ["编辑下周要来验收稿件", "手头的房租押金快见底"]
  }
 ],
 "locations": [
  {
   "id": "living_room",
   "name": "一楼客厅",
   "detail": "壁炉余烬发红、窄长沙发铺着旧羊毛毯、一整面对着黑海的窗被风吹得轻颤。",
   "privacy": "public",
   "visibility": "门口和楼梯口都看得见客厅中央，唯独壁炉侧边的弧形窄沙发陷在灯影死角里",
   "exits": ["terrace"],
   "affordances": ["共披一条羊毛毯在壁炉边暖手", "靠在窄沙发盲区里低声谈判"]
  },
  {
   "id": "terrace",
   "name": "屋顶露台",
   "detail": "晾衣绳上挂着被海风扯得猎猎作响的素白床单，围墙外是整片墨黑的海岸线。",
   "privacy": "private",
   "visibility": "只有顺着客厅边窄铁梯上来才能看见，湿重床单能挡住大半身形",
   "exits": ["living_room"],
   "affordances": ["钻进垂落的湿床单阴影里贴身避风", "把人按在晾衣栏杆边低声逼问"]
  }
 ],
 "character_templates": [
  {
   "id": "keeper",
   "gender": "any",
   "age_range": [30, 42],
   "adult_context": "民宿的成年合伙人，淡季独自守店周转账目",
   "public_role": "守店的人",
   "appearance_options": ["米白针织袖口挽到手肘，手背有烫伤旧疤，领口总松开一颗扣", "颈间松松缠着羊绒围巾，站近时身上带着暖甜的姜酒气"],
   "identity": {"authority": "掌管全楼房门备用钥匙与暖炉开关，决定谁的房费能宽限", "resources": ["挂在腰间的整串备用钥匙", "吧台里锁着的烈酒"], "limits": ["城里合伙人攥着转让大权，随时能收回店面"], "exposure": "民宿下个月初就要低价盘出去，至今不敢告诉长住的客人", "hidden": "其实舍不得搬走，更舍不得趁夜留下来的人"},
   "decision": {"core_value": "死守体面直到最后一张底牌被掀开", "goal_options": ["稳住客人别在签字前闹翻", "试探你到底愿不愿替{npc.ta}把消息压住"], "pressure_responses": {"low": "笑得滴水不漏，转身去吧台温一壶烈酒岔开话头", "mid": "斜倚在门框上压低声线，拿宽限房费和钥匙同你谈条件", "high": "呼吸发紧地拽住你衣袖把人往壁炉死角带，要你今晚兜底", "breaking": "反锁客厅内门抵在你肩头失控喘息，嘴上却硬撑着骂你别趁火打劫"}, "withdrawal": "把吧台小门虚掩着独自喝闷酒，手指攥得骨节发白", "relationship_stance": "面上热络周到，真动了心反倒喜欢拿规矩当挡箭牌", "contrast": "在外人面前算盘打得极精，私下被戳穿软肋时连耳根都会泛红发颤", "prefers": ["借递酒送毯子的名义把距离逼到半寸之内"], "avoids": ["被直接掀穿窘境后还装作施舍可怜"], "never": ["当着外人面彻底丢掉店东架子"]},
   "intimacy_tendency": {"attraction_sources": ["看穿{npc.ta}窘境却不急着点破的从容掌控感", "冷夜贴近时隔着毛衣传来的滚烫体温与压迫"], "likes": ["隔着单薄针织贴紧腰背的热意", "耳廓与后颈敏感带被指腹反复摩挲"], "dislikes": ["不冷不热的敷衍试探"], "preconditions": ["门栓落死、确认楼梯口无人偷听"], "boundaries": ["不当着第三人彻底失态"], "expression": "借递茶时指尖故意擦过你腕骨内侧，眼神湿热却嘴硬赶人回房", "desire_range": [3, 5], "self_control_range": [2, 4], "desired_position": "台面上店东做主，私下享受被按住失守"},
   "voices": {"surface": "“烈酒姜茶煮好了，自己来喝——手冷就往火边挪点。”", "inner": "“别用那种眼神盯着我算账，真想要什么，锁上门直说就是。”"},
   "schedule": [{"from": 1080, "to": 1439, "location_id": "living_room"}, {"from": 0, "to": 1079, "location_id": "terrace"}],
   "situation": {"trigger": "合伙人今晚来电，说买家明早九点上门验房", "pressure": "底价协议残页还落在外头，客人们却毫不知情", "exits": [{"option": "今晚就坦白交底", "cost": "长住客可能当场撕破脸退租"}, {"option": "拉拢知情者一道压住明早", "cost": "把自己的软肋和夜晚一并抵出去"}]}
  },
  {
   "id": "photographer",
   "gender": "any",
   "age_range": [26, 38],
   "adult_context": "独立商业摄影师，接品牌单子谋生的成年住客",
   "public_role": "来拍冬海的摄影师",
   "appearance_options": ["宽松衬衫下摆塞进长裤一半，脖子上挂着冷冰冰的金属胶片机", "黑发被海风吹得乱而湿，眼尾带着熬夜修片后的慵懒绯红"],
   "identity": {"authority": "决定拍谁的私密底片、又把哪几张放进公开画册", "resources": ["装满私密底片的金属暗盒", "最后三卷高感黑白胶卷"], "limits": ["手头存款只够再付十天房费"], "exposure": "躲在小镇其实是为避开一笔违约的私密约拍旧账", "hidden": "镜头背后偷偷对焦过你的背影和侧颈好几次"},
   "decision": {"core_value": "只留真正烧得人发慌的画面", "goal_options": ["赶在退房前拍一组失控边缘的近照", "决定要不要把最后那盒底片托付给你"], "pressure_responses": {"low": "举起取景器把你框进去，懒洋洋用镜头盖挡开试探", "mid": "故意凑近核对光线，气息扫过你眉骨开半真半假的玩笑", "high": "把揣得微热的金属底片盒塞进你大衣里，压低声音要你替{npc.ta}藏好", "breaking": "把你拉进床单阴影里抵住围墙，指尖发抖扯松衣领失控吻上来"}, "withdrawal": "独自站在风口抽完半包烟，指尖沾满冰凉的海水味", "relationship_stance": "嘴上放肆撩拨，真被反手扣住脉门反而绷紧屏息", "contrast": "平时看似最散漫不羁，贴身对焦时喘息与心跳比谁都诚实", "prefers": ["借量光和遮风把身体挤进同一片狭窄阴影"], "avoids": ["干巴巴的道德审问"], "never": ["把别人明确拒绝留存的私密底片外传"]},
   "intimacy_tendency": {"attraction_sources": ["你在镜头前毫不避让反而反盯回来的滚烫眼神", "暴风夜里肯陪{npc.ta}在暗处淋湿衣领的疯劲"], "likes": ["湿冷空气里突然贴紧的唇齿与掌心热度", "锁骨被指节轻刮时压不住的细颤"], "dislikes": ["装腔作势的客套推拉"], "preconditions": ["风声够大或拉上阻隔视线的厚帘"], "boundaries": ["绝不拍下对方真正抗拒留档的失态瞬间"], "expression": "借递胶卷俯身覆住你手背，鼻尖贴着颈侧故意拖慢了呼吸", "desire_range": [3, 5], "self_control_range": [2, 4], "desired_position": "轮流抢占上风，越抵触越缠得紧"},
   "voices": {"surface": "“别动，壁炉这束侧光正好打在你颈窝上。”", "inner": "“拍了十几张都没敢冲印——其实我更想把手直接放上去。”"},
   "schedule": [{"from": 960, "to": 1439, "location_id": "terrace"}, {"from": 0, "to": 959, "location_id": "living_room"}],
   "situation": {"trigger": "催讨私密约拍底片的旧合作方摸到了镇口消息", "pressure": "对方扬言周末上门当面索取原片", "exits": [{"option": "拿最后三卷底片去硬谈解约", "cost": "私藏的几张暗房底片可能保不住"}, {"option": "拉着信任的人连夜转移胶卷", "cost": "余下的盘缠几乎耗尽"}]}
  },
  {
   "id": "night_guest",
   "gender": "any",
   "age_range": [32, 50],
   "adult_context": "外地港口工程的成年监理，因封路暂住镇上",
   "public_role": "被风困住的过路客",
   "appearance_options": ["深色工装夹克下摆沾着风尘，挽袖时小臂线条利落", "眉眼冷硬沉稳，说话前指节习惯性摩挲打火机金属壳"],
   "identity": {"authority": "能一笔签停整片码头冬期工程", "resources": ["停在镇口带独立暖风的皮卡", "工程方预留的现金备付"], "limits": ["风一停就得连夜赶回工地交差"], "exposure": "上周码头漏查的一份安全报告至今压在手里未交", "hidden": "十年前就和这家民宿老板有过一段未清的旧情"},
   "decision": {"core_value": "扛得住事，也认得准人", "goal_options": ["摸清民宿半夜易主的真实底细", "在封路这夜试出你嘴有多严"], "pressure_responses": {"low": "沉默着仰头喝干烈酒，眼神沉沉压在人脸上", "mid": "拿工程规矩作比喻敲打，手掌却不露声色按上桌面", "high": "直接摊明与旧老板的渊源，起身逼近半步要求交换底牌", "breaking": "把人拽进走廊暗处反锁扣紧腰线，滚烫呼吸抵在耳侧低声喘息认栽"}, "withdrawal": "独自回镇口皮卡里发动暖风，车窗蒙满白雾", "relationship_stance": "惯于居高临下拿主意，唯有在私密时刻肯任人攥住领口", "contrast": "外表最冷硬寡言，动了情却寸步不退、护短又霸道", "prefers": ["开门见山谈好代价再直接上手兑现"], "avoids": ["虚头巴脑的试探废话"], "never": ["把私底下交托的秘密卖给外人"]},
   "intimacy_tendency": {"attraction_sources": ["敢当面拆穿{npc.ta}底细却不退缩的胆量", "风暴夜肯钻进{npc.ta}狭窄空间取暖的贴近"], "likes": ["微热指腹摩挲发烫的耳垂与腰窝", "狭窄角落里膝盖相抵的闷热缠斗"], "dislikes": ["撩完就想抽身装傻"], "preconditions": ["避开外人视线，彼此看准了眼"], "boundaries": ["不在工程熟人面前漏出破绽"], "expression": "一言不发脱下带体温的厚夹克裹住你，手掌顺势扣紧后腰没放开", "desire_range": [2, 5], "self_control_range": [3, 5], "desired_position": "沉稳压制主导，但吃软不吃硬"},
   "voices": {"surface": "“风明天下午才停，今晚谁都出不去。”", "inner": "“我留在这里多挨一夜，可不光是为了等这阵海风。”"},
   "schedule": [{"from": 1140, "to": 1439, "location_id": "living_room"}, {"from": 0, "to": 1139, "location_id": "terrace"}],
   "situation": {"trigger": "工地深夜来电，明早必须提交安全事故签字报告", "pressure": "要么如实上报保住自己，要么私下压住护住老下属", "exits": [{"option": "按规矩照实签报", "cost": "手下跟了多年的技术员会被连带开除"}, {"option": "自己一肩担下来压住", "cost": "明年港务局的新合同多半泡汤"}]}
  }
 ],
 "tension_engines": [
  {"id": "te_one_fire", "text": "整栋楼只剩一楼壁炉与狭窄露台避风角容得下人，停暖夜里谁也躲不开谁的体温。"}
 ],
 "cast_combos": [
  {
   "id": "combo_storm_night",
   "power_structure": "equal",
   "player_positions": ["equal"],
   "slots": ["keeper", "photographer"],
   "tension_engine_ids": ["te_one_fire"],
   "chemistry": "{keeper.name}攥着整栋楼的房门钥匙与转让秘辛，{photographer.name}的底片盒藏着见不得光的旧照；暴风停暖的夜里三个人挤在热气边各怀算计。",
   "stakes": {"resource_gap": "{keeper.name}握着所有房间钥匙与宽限房租的权柄，你捏着转让底价残页", "limit_gap": "你急着交稿保住预付金，{photographer.name}盘缠将尽还被旧账逼到墙角", "meeting_reason": "淡季封路夜里最后几个没散场的成年人", "irreplaceable_goal": "赶在编辑与买家明早进门前，抢到能护住稿子与退路的筹码"},
   "relations": [
    {"a": "player", "b": "keeper", "stage": "flirting", "a_to_b": {"trust": 1, "tension": 3}, "b_to_a": {"trust": 1, "tension": 3}, "reason": "上回停电在壁炉边共披一条毯子，指尖擦过腰侧时{keeper.name}没躲开"},
    {"a": "player", "b": "photographer", "stage": "testing", "a_to_b": {"trust": 0, "tension": 3}, "b_to_a": {"trust": 0, "tension": 3}, "reason": "隔墙听见对方夜里出入，楼梯擦肩时袖口总若有似无勾在一起"},
    {"a": "keeper", "b": "photographer", "stage": "acquainted", "a_to_b": {"trust": 0, "tension": 2}, "b_to_a": {"trust": 1, "tension": 1}, "reason": "房费拖了好几天按天记账，{keeper.name}却总借送酒由头往暗房门外走"}
   ]
  }
 ],
 "daily_activities": [
  {"id": "a_ginger_tea", "title": "烈酒姜茶夜", "location_ids": ["living_room"], "duration_minutes": 40, "beats": ["酒气混着姜辣漫开在狭窄壁炉边，两个人膝盖隔着羊毛毯抵在了一起", "门外突然传来脚步声，手里端着的酒盏泼出半滴滚烫酒液落上手背"]},
  {"id": "a_sheets", "title": "夜风收床单", "location_ids": ["terrace"], "duration_minutes": 20, "beats": ["阵风掀翻垂落的湿重床单，把两个人严严实实裹进同一片白布阴影里", "伸手去扯栏杆绳结时掌心正好扣住对方冰凉泛抖的手腕"]}
 ],
 "pressures": [
  {
   "id": "p_viewing",
   "title": "明早有人来看房",
   "source": "person",
   "flags": ["timed", "leverage"],
   "location_ids": ["living_room"],
   "trigger": "守店人在客厅接完合伙人压价电话转过身，正撞见你指间夹着那半页转让底价协议",
   "objective": "在买家明早九点进门前，决定用这份把柄换取什么条件",
   "choice": "现在拿协议单把守店人逼进死角谈筹码，还是佯装不知换对方欠你一次贴身人情",
   "immediate": {"text": "客厅吊灯熄了大半，守店人反手带上门挡在你和楼梯口之间，眼神发暗却咬住牙没退", "minutes": 20},
   "near": {"text": "明早九点买家带律师进门验房", "deadline_minutes": 840},
   "far": {"trigger": "月底合伙人带新东家来清点民宿资产", "consequence": "屋里留下来的人和交出的把柄，都要换一套新的依附关系", "due_days": 5},
   "exits": [
    {"option": "贴近壁炉死角亮出底价单压价谈判", "cost": "守店人被迫低头签下宽限契据，暗地里却将你恨进了骨子里"},
    {"option": "当面把半页协议贴进守店人衣襟口袋", "cost": "对方欠下你一笔说不清的贴身人情债，明早被外人撞见再难撇清"}
   ],
   "leverage": {"holder": "player", "subject": "keeper", "basis": "你攥着民宿下月低价转让的底价协议残页，一旦声张长住客明早就会退租"},
   "start_minute": 1140
  },
  {
   "id": "p_storm_tide",
   "title": "今晚的风暴潮",
   "source": "nature",
   "flags": ["timed"],
   "location_ids": ["terrace", "living_room"],
   "trigger": "镇广播连发风暴潮橙色警报，全镇停暖并封锁外路，屋顶露台挂着的重要物品还没收",
   "objective": "在狂风十点掀翻露台之前把人手与物件拉回安全门内",
   "choice": "冒风钻上露台抢收再湿透回房贴身取暖，还是留在壁炉前锁门独守一隅",
   "immediate": {"text": "湿重的白床单被海风扯脱一角抽在栏杆上，露台门缝灌进刺骨湿风", "minutes": 15},
   "near": {"text": "十点整风暴潮越堤封锁整片海滨", "deadline_minutes": 180},
   "far": {"trigger": "风停后镇安监专员上门查验受损老屋", "consequence": "民宿若被定为危楼封门，屋里藏着私密底片与债务的人谁也保不住现下庇护", "due_days": 2},
   "exits": [
    {"option": "顶风上露台并肩抢收湿床单与胶卷箱", "cost": "衣衫湿透贴在皮肤上冷得发颤，回屋后不得不共挤壁炉旁取暖"},
    {"option": "直接反扣露台铁门守在一楼", "cost": "晒在楼上的贴身衣物与旧物全被狂风卷走，次日再难向同伴交代"}
   ],
   "start_minute": 1140
  }
 ],
 "hooks": [
  {"id": "h_blanket", "kind": "approach", "slot": "keeper", "location_ids": ["living_room"], "text": "{npc.name}把壁炉边唯一的羊毛毯搭上你膝头，指尖擦着你腕骨内侧停住没撤。"},
  {"id": "h_terrace", "kind": "approach", "slot": "photographer", "location_ids": ["terrace"], "text": "海风掀翻床单将你们裹进同一片暗影，{npc.name}呼吸滚烫地擦过你耳廓却偏不退开。"}
 ],
 "forbidden_terms": ["飞船", "魔法"],
 "content_tags": ["intimate", "coercion_theme"],
 "status": "draft",
 "notes": "自定义世界的最小高张力示例（references/custom_world.md 引用）"
}
```
