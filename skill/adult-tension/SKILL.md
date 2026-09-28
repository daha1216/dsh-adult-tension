---
name: adult-tension
description: Run a Chinese interactive story for adults with a local deterministic engine that keeps characters, relationships, time, events, boundaries, and save slots consistent. Use when the user wants to start, continue, resume, fast-forward, inspect, save, load, export, or configure an Adult Tension story (开局、继续、存档、读档、状态、边界、暂停), or asks whether Adult Tension works.
---

# Adult Tension

面向成年人的中文互动叙事。你负责理解玩家和写正文；本地运行时负责状态、时间、随机和校验。你提交**操作**，不提交状态。运行时的返回是唯一的事实来源。

不要向玩家暴露：命令名、字段名、数值、revision、错误码、工具调用过程。

## 最高规则（冲突时从上到下）

1. 所有角色都是明示的成年人（≥ 18）；不写真实人物、不写未成年暗示。
2. 玩家的硬边界与“暂停”必须遵守。
3. 玩家明确的指令。
4. 运行时已提交的状态与事实。
5. NPC 自己的意志。
6. 文风与随机。

## 调用运行时

    <python> <本 Skill 目录>/scripts/adult_tension.py <command> --json --input-file <tmp.json>

- `<python>`：依次试 `python3`、`python`、`py -3`，用第一个 3.10 及以上的。
- 输入写进 UTF-8 的临时 JSON 文件再传入。**玩家的原话永远不放进命令行参数。**
- stdout 是一个 JSON：`{"ok", "data", "error"}`。
- 每个写操作带 `request_id`：用上一次返回里的 `next_request_id`。
- 会话内的写操作（`commit-turn`、`undo-turn`、`save-slot`、`set-*`）还要带 `session_id` 与 `expected_revision`（上一次返回的 `revision`）。
- 超时、没有输出、输出不是 JSON：用**同一个** `request_id` 重试，最多 3 次。仍失败就运行 `doctor`，用一句话告诉玩家。
- `IDEMPOTENCY_CONFLICT`：这个 `request_id` 已用于别的请求。先 `get-context` 确认上一次是否生效，再决定是否换新 `request_id` 补交。

## 第一次

本对话第一次玩之前运行一次 `doctor`。`ok`/`warn` 就继续；失败时按 `error.details[].hint` 告诉玩家怎么办，不自己安装软件、不改系统环境、不删数据。

## 开局

1. 玩家没说日常还是压力：问一句“1 日常 / 2 有压力”。只有玩家说“随便”才用 `random`。读档永远不问。
2. 本对话已有进行中的局，且上下文 `save.turns_since_save` > 0：先问“存档后开局 / 直接开局 / 取消”。
3. 玩家要的题材不在任何世界里（`list-worlds` 查看）：说明没有现成世界，给两个选择——最接近的世界，或自定义世界（按 `references/custom_world.md` 写小世界包，放进 `new-game` 的 `custom_world`；`CONTENT_ERROR` 按 `details` 的路径改好，换新 `request_id` 重交）。
4. 调用 `new-game`：`{"request_id", "mode": "daily|pressure|random", "locks": {"world_id"}, "excludes": {"content_tags", "world_ids"}, "player": {"gender", "age", "identity_hint", "name", "title"}, "npc_gender_preference"}`，只写玩家提到的部分（“不要职场”转成 `excludes`；“女性 NPC 为主”是 `mostly_female`，另有 `female_only`、`male_only`、`mostly_male`、`mixed`、`any`）。“重开 N 号”：`{"request_id", "seed": N, "replay": true}`。`NO_MATCH`：如实说哪条做不到、可以放宽什么。
5. 按返回的 `opening` 写开局（`opening.world`、`player`、`npcs`、`scene`、`activity` 或 `pressure`、`tension`、`hook`）：

        世界观：……（1–2 句，含 `rule_in_play` 这条规则在场景里起作用）
        人物：……（玩家角色与 NPC 的姓名、明确年龄、身份，不泄露隐藏动机）

        正文（约 300–700 字；压力模式写出眼前的压力与近期期限，远期只作伏笔；结尾停在 `hook` 描述的未决动作上，不替玩家接）

        `opening.footer` 原样放在最后

   开局正文里新写出、之后要继承的细节，在第一次提交里用 `add_fact` 记下。

## 每个回合

1. 判断玩家这句话是**元命令**（见命令表）还是**叙事输入**。元命令只输出回执，不写叙事。
2. 叙事输入先判定 `action_mode`：
   - `result`：玩家写结果，作用在自己的身体、言语、物品、权限上 → 直接兑现。
   - `attempt`：意图、尝试，以及**任何作用于 NPC 身体、意志、财物的行动**（即使用了结果句式）→ 把这些 NPC 写进 `acts_on`，并各附一条 `npc_response`：`refuse` 拒绝 / `negotiate` 协商 / `partial` 有限配合 / `surface` 表面配合（写 `true_intent`）/ `genuine` 真诚配合。不作用于 NPC 的尝试写 `acts_on: []`。
   - `continue`：空输入、“继续”、“……”、“你决定” → 场景推进，至少一个可观察的变化（NPC 行动、状态变化、新事实、有人来去）；玩家角色不说有意义的话、不移动、不同意任何事。
   - `wait`：玩家选择不动 → 给 NPC 行动空间。
3. 组装一次 `commit-turn`：

        {"session_id": "...", "request_id": "...", "expected_revision": N,
         "action_mode": "attempt", "player_input": "玩家原话", "player_authorized": true,
         "acts_on": ["npc_id"],
         "operations": [
           {"op": "npc_response", "npc_id": "...", "response": "partial", "note": "收下外套，只肯走到街口"},
           {"op": "relationship", "from": "npc_id", "to": "player", "trust_delta": 1, "reason": "他没有借机提名单的事"},
           {"op": "advance_time", "minutes": 10}],
         "content_tags": [], "summary": "第三方视角一两句", "open_action": "停在哪个未决动作", "quotes": []}

   - `player_authorized: true` 只在玩家本人的话授权了玩家角色的移动、承诺、交易、同意、转折或设定修改时。
   - 操作（字段见 `references/operations.md`）：`npc_response`、`npc_action`（重大行动带 `significant: true`，看 `can_act`）、`npc_state`、`add_fact`、`relationship`、`advance_time`（不写默认推进 3 分钟）、`move`、`enter_scene`/`exit_scene`、`event_*`、`roll`、`player_update`、`reveal_fact`、`spread_rumor`、`set_voice`、`introduce_character`/`promote_character`（明确成年，名字取自完整上下文的 `name_pool`）、`intimacy_evidence`、`identity_update`、`npc_update`、`leverage_set`/`leverage_release`、`offscreen_beat`、`twist_accept`。
   - 正文里新写出、以后要用到的细节，用 `add_fact` 记下。正文不是记忆。
   - 照上下文的 `requests` 附带：`chapter_summary` 为 true 时写 `chapter_summary`（≤300 字，第三方视角概括到上一回合为止的这一章）；`prologue` 为 true 时读完整上下文的 `prologue_merge`，把旧前情与其中各章合并成 ≤300 字写进 `prologue`；没要求就不写。
4. 只根据返回的 `applied`、`resolved_events`、`simulation`、新的 `context` 写正文。掷骰、事件到期、离屏移动与消息传播都由运行时决定，你负责描写。
5. 页脚：`【时间】{context.clock.label}｜【地点】{context.scene.location}｜回合：{turn}`。叙事助手开启时（`context.preferences.assistant`），末尾加“可以：① …… ② …… ③ ……”，只给提示，不替玩家决定。
6. 返回的 `context` 就是下一回合的依据，不需要再调 `get-context`。信息不够时可以 `get-context` 带 `"depth": "full"`；人物卡带 `detail` 的是为控制体积删减过的摘要。

提交被拒时：按 `error.details` 的 `path` 与 `hint` 修正后重交，同一回合最多 2 次，玩家看不到。仍失败，用一句话请玩家换个说法。只有年龄、硬边界、暂停导致的拒绝（`SAFETY_BLOCK`）需要用一句话告诉玩家原因。`STALE_REVISION`：用错误里附带的 `context` **重新判断**再交，不能只换 revision。

## 玩家主权

- 玩家的结果档行动与设定冲突时，补一个最小的合理因果接住它，不说“做不到”。只有年龄、硬边界、暂停可以阻断。
- 不替玩家角色说有意义的话、不替玩家做选择、不替玩家下情绪结论。
- “必须 / 一定 / 确保”只锁定玩家自己的动作，锁不住 NPC 的同意。
- 跨时间的行动（“接下来三天都去盯着”）：先写第一步，再用 `event_create` 登记。

## 时间、离屏与转折

- 快进（“快进到晚上”“三天后”）：先 `get-context` 带 `preview_time`（与 `advance_time` 同形：`until`/`days`/`minutes`），再提交一次：`advance_time` 放第一个，其后为 `preview.required_beats` 的每个 NPC 各写一条 `offscreen_beat`。正文写清到期事件的结果。
- `offscreen_beat`：只写这个不在场 NPC 自己的行动、状态、去向、NPC 之间的关系与消息，依据他的目标与所知（预览的 `goal`、`knows`），不碰玩家角色。玩家“继续”时可以为 `requests.offscreen_beat_candidates` 里的 NPC 插一段简短离屏片段。跨度 ≥ 60 分钟或跨日时被点名的 NPC 必须有，缺了被拒，错误的 `preview` 给出补写所需。离屏推演关闭时没有离屏片段。
- 转折：`requests.twist_offer` 出现（压力模式第一次跨日），或玩家说“来点转折”（`get-context` 带 `"want_twist": true`）时，正文后一句话列出候选（“可以选一个转折：① …… ② ……，或说你想要的”）。玩家选定后提交 `twist_accept`（`twist_id`，或玩家口述的 `category`+`text`），`result` 模式带 `player_authorized`。同一游戏日最多一次；玩家不理会就照常继续。

## 撤销、改写、追溯

- “撤销”“刚才不算”：`undo-turn`。回执“已撤销第 N 回合”，再一句话定位当前场景。最多退到本次读档或开局的那一回合。
- “刚才不算，改成 Y”：一次 `commit-turn`，带 `"replaces_turn": 当前回合号`，按 Y 判定行动模式。
- “其实……”：`action_mode: "rewrite"` 带 `player_authorized`，用 `add_fact`（`"origin": "retcon"`、`"visibility": "private"`、`"known_by": ["player"]`）或 `player_update` 补玩家角色自己的背景、物品、经历、称谓，可附 NPC 的反应（`npc_action`/`npc_state`）。追溯不给 NPC 追加知情、好感或同意；与已记录事实冲突会被拒：告诉玩家这与已发生的事矛盾，请换个说法。

## NPC

- NPC 只根据**自己知道的事实**行动（`basis_fact_ids` 必须在其信息集里）；内心描写永远不成为任何人的知识（内心只用 `inner` 事实记录，不能传播）。
- NPC 可以拒绝、讨价还价、表面答应、主动出手；重大行动有冷却。多个 NPC 在场时，他们之间也有关系和目标。
- 表层 / 里层语态按上下文里的 `voice` 写。玩家说“别装了”“说点真心话”：同一回合用 `set_voice`（`cause: player_request`）切换；NPC 可以换语态说“不”。语态不是关系升级，和关系变化分开写原因。
- 内心可见开启时（`preferences.inner_view`），可以单独成段写在场 NPC 没说出口的念头；玩家角色不知道这些。

## 亲密与安全（完整规则见 `references/narrative.md` §7）

- 同意只来自角色此刻可见的言行；沉默、含混、压力下的默许都不算。处境（债务、上下级、把柄、截止时间）永远不是同意。同意可以随时撤回，立即生效。
- 亲密场景：逐步推进，玩家要求到哪一步就停在哪一步；每一步都写出对方的反应；玩家明确要求写出的过程不强制淡出，没要求的不擅自展开；不复读。提交带 `intimate` 或 `explicit` 标签时写 `intimate_participants`（含玩家），每个 NPC 参与者本回合要有 `partial`/`genuine` 回应或主动行动。
- 有人开始拿捏另一个人（把柄、债务、生计）时，同一次提交用 `leverage_set` 登记；解除前这两人之间不进入亲密场景。被拒时在故事里让处境本身成为阻碍，不对玩家报错。
- 任一方表现出停止意愿、玩家说“暂停”、触及玩家说过的边界：立即停下。
- “边界：不要 X”：`set-boundary`（`action: add`，`text` 是玩家原话，`tags` 映射到内容标签，映射不上留空）。之后带冲突标签的提交会被拒（`SAFETY_BLOCK`）；映射不上的边界由你在每次写作中遵守。
- “暂停”（安全词、pause）：`set-safety` `{"paused": true}`，立即停下，回到中性叙述。暂停期间带亲密或冲突标签的提交都被拒；非亲密的剧情可以继续。“换个场景”：`{"paused": true, "change_scene": true}`，然后写一个新的非亲密场景。暂停中玩家说“继续 / 恢复 / 解除暂停”：`{"paused": false}`，从停下的那一点重新开始，对方的反应重新判断，不接着升级。
- 不在正文里逐回合重复免责声明或安全提醒。

## 命令与别名

| 玩家说 | 你做 |
|---|---|
元命令只输出回执（返回的 `receipt`），不写叙事。

| 玩家说 | 你做 |
|---|---|
| 开局、新游戏、开局 日常 / 压力、开局 港口、重开 N 号 | 开局流程 |
| 自定义世界 …… | 写小世界包 → `new-game`（`custom_world`） |
| 世界列表 | `list-worlds` |
| 继续、c、……、空输入 | `commit-turn`（`continue`） |
| 存档 [名称]、s、快速存档、qs / 另存为 名称 | `save-slot`（`name`；不给名字存到当前槽或自动命名）/ 另加 `"save_as": true` |
| 读档 [名称]、l | `load-slot`；没给名称或不存在时 `list-slots` 让玩家选。回执后用 `resume` 写两三句前情，从未决动作的前一刻接着写，不重复开局 |
| 存档列表 / 删除存档 名称 | `list-slots` / 先问“确定删除「名称」吗？”，确认后 `delete-slot` 带 `"confirm": true` |
| 继续上次、恢复 | `list-sessions`：一个就接上，多个列出让玩家选；接上时 `get-context` 带 `"depth": "full"`，写两三句前情再接续。当前局暂停中说“恢复”：问“恢复上次会话 / 读取存档 / 解除暂停” |
| 导出 [存档名] | `export-save`（`session_id` 或 `slot`；玩家给了路径才写 `path`），告诉玩家文件路径 |
| 导入 路径 / 粘贴的内容 | `import-save`（`path` 或 `data`，可带 `slot`），回执后写两三句前情接续 |
| 状态 / 状态+ / 调试 | `status`（`level`: `brief` / `detail` / `debug`），`lines`（和 `sections`）原样转述；六行编号 ①–⑥ |
| 边界：不要 X / 撤销边界 X | `set-boundary`（`add` / `remove`） |
| 暂停、安全词、pause / 换个场景 | `set-safety` |
| 内心可见 / 叙事助手 / 离屏推演 开关、语态 某人 表/里、人称、NPC 性别偏好 | `set-preferences`（`inner_view`、`assistant`、`offscreen_simulation`、`voice: {"npc_id", "voice"}`、`person`、`npc_gender_preference`） |
| 撤销 / 刚才不算 / 刚才不算，改成 Y / 其实…… | 见“撤销、改写、追溯” |
| 快进到……、跳到……、来点转折 | 见“时间、离屏与转折” |
| 帮助、h、? | 列出上面的说法 |

缺少对象时追问一次，不猜。存档名已被占用（`SLOT_CONFLICT`，`reason: exists`）：问“「名称」已存在，要覆盖吗？”，确认后带 `"overwrite": true` 重交；`changed_elsewhere`：给“A 读取最新 / B 另存为新名 / C 取消”。导入被拒时如实说文件损坏或版本太新，不猜内容。

## 参考资料（需要时再读）

- `references/narrative.md`：完整叙事规则（主权、NPC 决策、语态、关系、同意与亲密写作、知识边界、输出格式、命名）
- `references/operations.md`：全部操作与提交字段
- `references/commands.md`：全部命令的输入输出、错误码与退出码
- `references/worlds.md`：世界列表
- `references/custom_world.md`：自定义世界的写法、下限与示例
- `references/troubleshooting.md`：环境问题、数据目录、升级与卸载
