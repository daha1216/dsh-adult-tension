# 少用的流程

`SKILL.md` 只放触发条件和要点；用到下面这些流程时再读对应一节。

## 1. 快进与离屏片段

- 快进只在玩家要求时预览：`get-context` 带 `preview_time`（`until`: `morning`/`noon`/`evening`/`night`/`next_morning`，或 `days`、`minutes`，只给一个）。只预览一次，照返回的 `skip_template` 记录（时间与必需的离屏片段已排好）；途中分开的人同时 `exit_scene`。
- 正文写清到期事件的结果，不替玩家决定做什么、去哪、见谁。
- `offscreen_beat`：只写这个不在场 NPC 自己的行动、状态、去向、NPC 之间的关系与消息，依据他的目标与所知（预览的 `goal`、`knows`），不碰玩家角色。
- 玩家“继续”时，可以为 `requests.offscreen_beat_candidates` 里的 NPC 插一段简短离屏片段。
- 跨度 ≥ 60 分钟或跨日时，被点名的 NPC 必须有离屏片段。离屏推演关闭时（`preferences.offscreen_simulation` 为 false）不写。

## 2. 转折

- 触发：上下文出现 `requests.twist_offer`，或玩家说“来点转折”（`get-context` 带 `"want_twist": true`）。
- 正文之后用一句话列出候选：“① …… ② ……，或说你想要的”。
- 玩家选定后记录 `twist_accept`：给 `twist_id`，或玩家口述的 `category` + `text`；`result` 模式带 `player_authorized`。若选定的转折带入原本不在场的角色（含 `standby_cast` 待命角色），同一回合用 `enter_scene` 让其入场，勿用 `introduce_character`。
- 每个游戏日最多一次；玩家不理会就照常继续。

## 3. 撤销、改写、追溯

- “撤销”“刚才不算”：还没记录的回合直接改写正文；已记录的用 `undo-turn`，回执后再用一句话定位当前场景。
- “刚才不算，改成 Y”：还没记录的直接按 Y 重写；已记录的最后一回合，立即记录一次，第一项带 `"replaces_turn": 该回合号`，按 Y 重新判定行动模式。
- “其实……”：补玩家角色自己的背景、物品、经历、称谓，记法见 `narrative.md` §2。不给 NPC 追加知情、好感或同意；与已发生的事矛盾的，请玩家换个说法。

## 4. 读档、继续上次、导出导入

- 读档：玩家给了名称就直接 `load-slot` `{"request_id", "name"}`；没给名称才先 `list-slots`。回执后用返回的 `resume` 写两三句前情，从未决动作的前一刻接着写，不重复开局。
- 继续上次、恢复：`list-sessions`。只有一个就接上，多个就列出让玩家选；接上时 `get-context` 带 `"depth": "full"`，写两三句前情再接续。当前局暂停中说“恢复”：问“恢复上次会话 / 读取存档 / 解除暂停”。
- 删除存档：先问“确定删除「名称」吗？”，确认后 `delete-slot` 带 `"confirm": true`。
- 导出：`export-save`，把返回的文件路径告诉玩家。导入：`import-save`（路径或玩家粘贴的内容），回执后写两三句前情接续。
- 存档冲突（`SLOT_CONFLICT`）、导入被拒：照 `troubleshooting.md` 的“存档冲突”处理。
- 对话压缩（`/compact`）后恢复：严禁凭压缩摘要猜测人设、边界或 `revision`。先用 `list-sessions` 找回 `session_id`（若已丢失），再调 `get-context` 带 `"depth": "full"` 拉取 ≤32KB 完整快照与 `commit_template`。对比返回的 `turn` 与上文可见的最后页脚回合号：若有压缩前攒下未交且上文仍可见的回合，先按序 `commit-turn` 补齐；若早先细节已被压缩隐去，则直接以引擎 `context` 当前回合与事实为准往下接续，绝不凭印象补造未记录的承诺、亲密或事实。

## 5. 风格偏好

上下文的 `preferences.pace`（节奏）与 `preferences.explicitness`（尺度）；没有出现就是“标准”。描写尺度只在 `narrative.md` §7 定义，偏好只决定在那个范围里往哪一端伸缩（§7 第 2 条）。

| 偏好 | 取值 | 写法 |
|---|---|---|
| 节奏 | `slow` 慢热 | 多写铺垫、试探和停顿，每个回合推进得少 |
| | `standard` 标准 | 默认 |
| | `direct` 直接 | 少铺垫，尽快把冲突和选择摆到玩家面前 |
| 尺度 | `subtle` 含蓄 | 收敛克制：重眼神、衣料摩挲与呼吸停顿，点到即止，不写露骨器官细节 |
| | `standard` 标准 | 成年情色默认档：体温、喘息、敏感带触感与肢体交缠具体可感，随情节自然推进，不拉灯回避 |
| | `explicit` 直白 | 高张力直白档：正面写透肉体交合、生理失控、器具刺激、体液声响与口嫌体正直细节，直白粗粝用词贴合语态 |

只影响写法，不影响规则：硬边界、暂停、逐步推进、NPC 的人设反应都照旧。玩家这一回合的明确要求优先于偏好。
