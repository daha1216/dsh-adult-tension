# 真实宿主闭环验收记录（基线）

对应实施报告遗留项「完整 Skill 安装端到端验收」。本文件记录 2026-09-10 在 DSH 宿主内按 `SKILL.md` 实际游玩的基线结果；修复轮完成后将追加复测记录。叙事探针（`run_playtest.py`）与宿主闭环分开报告，本文件只覆盖后者。

## 范围

按 `SKILL.md` 全流程执行：新开局（daily）→ 普通回合最小 patch 提交 → 事件添加/解决 → 元指令 → 跨天快进 → 命名槽保存/载入 → 宿主机械复制接续 → 载入后续写。正文按「世界观/人物/正文」三标题与正文+回合号格式在宿主对话内生成（第 1–5 回合）。会话与槽：

- 工作会话 `saves/sessions/host-loop-daily-1/state.yaml`（框架：成年创作者与校园艺术季；era 当代都市；place 豪门庄园顶楼琴房；player 李承泽 34；npc-001 周若彤 28；trust 起 1）
- 命名槽 `saves/slots/hostloop-base/`（manifest v2）
- 载入接续会话 `saves/sessions/host-loop-loaded-1/state.yaml`

## 验证矩阵（全部通过）

| 步骤 | 操作 | 结果 |
| --- | --- | --- |
| 开局 | `build_opening.py --complete --opening-mode daily --session host-loop-daily-1` | OK；返回 session/state_path/state_token（ce0d39d5…140） |
| 普通回合 | turn2 最小 patch（`delta_minutes` 8、`trust` 增量、`npc_updates.emotion`） | fast 提交 OK；token 9f696dd2…9150；情绪落盘 |
| 旧 token 重放 | 用过期 token 再提交同 patch | 拒绝 `ERROR: stale state token: reload the latest state before committing`，exit 1，状态未动 |
| 事件添加 | `events_add[{id,summary,trigger,due_at,consequence}]` | 存为 `kind: timed`＋`semantic_key: turn-3-<id>`＋`source: turn:3`；硬升级 deep（structural state changed）；`knowledge_add`/`memory` 生效；token f8d32c55…14eb3b |
| 事件解决 | `events_resolve["ev-trial-venue"]`＋`resolve_outcome`，`delta_minutes` 75 | `event_changes` 带 resolved 终态＋outcome＋resolved_turn；large time jump→deep→完整校准 `last_full_turn` 1→4；token 22459e3a…e18b4 |
| 元指令 | `advance_turn: false`＋`boundaries_add` | 回合不动、边界入档；伪造 token 拒绝 |
| 保存 | `manage_saves.py init hostloop-base` → 覆盖 save | manifest v2（state_sha256 dfdafdcd…c14）；无 `--expected-updated-at` 覆盖被拒（要求载入时记录的 updated_at）；带 flag 成功 |
| 载入 | `manage_saves.py load hostloop-base` | 返回同锁 manifest；宿主机械复制槽内 state.yaml 至新会话目录；`live_slice` 正常，回合 4 保持、无事件丢失、token=state_sha256 |
| 载入续写 | turn5 `delta_minutes` 708（22:12→次日 10:00，跨天）＋`situation_update` | 提交 OK，clock 2026-03-21T10:00 |

## 发现的缺陷（待修复轮处理）

1. `world.constants` 前两条句号重复（「授权。。」「合作。。」），属拼接缺陷，影响开局 brief 与切片展示。
2. `current_node.situation` 保持开局 trigger/unresolved_choice，不随回合自动更新（依赖模型 `situation_update`，设计如此但易显陈旧）。
3. `npc.emotion` 需模型显式更新才变化（设计如此，记录在案）。

## 结论

基线状态下宿主闭环全链路（开局、提交、事件、校准、锁与 token、槽保存/载入、跨会话接续、跨天追算）按 `SKILL.md` 描述工作；上述 3 项缺陷不阻断游玩。本记录不等于 `qa.py --full --release` 通过，也不与非露骨叙事探针结果混报。
