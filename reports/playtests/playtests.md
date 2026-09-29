# 世界试玩

| 世界 | 模式 | 局数 | 种子数 | 机器检查通过 | 已评审 | 玩家主权 | NPC 意志 | 知识边界 | 关系节奏 | 同意与安全 | 世界具体性 | 连续性 | 表达 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| art_season_studios | daily | 5 | 5 | 4 | 5 | 5 | 5 | 5 | 5 | 4.5 | 5 | 5 | 5 |
| art_season_studios | pressure | 6 | 6 | 4 | 6 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| bakumatsu_machiya | daily | 5 | 5 | 4 | 5 | 5 | 5 | 5 | 4.5 | 4 | 5 | 5 | 5 |
| bakumatsu_machiya | pressure | 5 | 5 | 3 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| harbor_night_shift | daily | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 4 | 5 | 5 | 5 |
| harbor_night_shift | pressure | 5 | 5 | 4 | 5 | 5 | 5 | 5 | 5 | 4 | 5 | 5 | 5 |
| lantern_festival_town | daily | 5 | 5 | 2 | 5 | 5 | 5 | 5 | 5 | 4.5 | 5 | 5 | 5 |
| lantern_festival_town | pressure | 5 | 5 | 4 | 5 | 5 | 5 | 5 | 5 | 4.5 | 5 | 5 | 5 |
| republic_press_street | daily | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 4 | 5 | 5 | 5 |
| republic_press_street | pressure | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| winter_shelter | daily | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 4.5 | 5 | 5 | 5 | 5 |
| winter_shelter | pressure | 6 | 6 | 5 | 6 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |

（维度一栏是评审分数的中位数。评审者：gemini-3.8-flash 62 条（校准 12/12）。）

gemini-3.8-flash-exp-a 与 gemini-3.8-flash 视为同一个模型（用户确认）。

满分过半的维度（锚点太松，下一轮收紧）：玩家主权、NPC 意志、知识边界、关系节奏、同意与安全、世界具体性、连续性、表达

| 记录 | 种子 | Skill（提交） | 机器检查 | 评审 ≤ 2 的维度 |
|---|---|---|---|---|
| opencode-pt-art_season_studios-daily-r1.json | 227796 | 未记（未记） | 未通过：正文里出现机制用语 提交回合；正文里出现机制用语 回合行动 | 表达 |
| opencode-pt-art_season_studios-daily-r2.json | 797160 | 7da24032e8b0e162（48ef63d） | 通过 | 无 |
| opencode-pt-art_season_studios-daily-r3.json | 64480 | 7da24032e8b0e162（cef6f03） | 通过 | 无 |
| opencode-pt-art_season_studios-pressure-r1.json | 505921 | 未记（未记） | 未通过：玩家角色说了玩家没说过的话：“别急着谈展位，” | 无 |
| opencode-pt-art_season_studios-pressure-r2.json | 10763 | 7da24032e8b0e162（48ef63d） | 通过 | 无 |
| opencode-pt-art_season_studios-pressure-r3.json | 334878 | 7da24032e8b0e162（cef6f03） | 通过 | 无 |
| opencode-pt-bakumatsu_machiya-daily-r1.json | 705036 | 未记（未记） | 通过 | 无 |
| opencode-pt-bakumatsu_machiya-daily-r2.json | 115717 | 7da24032e8b0e162（a724726） | 通过 | 无 |
| opencode-pt-bakumatsu_machiya-daily-r3.json | 590139 | 7da24032e8b0e162（cef6f03） | 通过 | 无 |
| opencode-pt-bakumatsu_machiya-pressure-r1.json | 415 | 未记（未记） | 未通过：工具调用 3 次，超过这一步的预算 2（ACCEPTANCE §5） | 无 |
| opencode-pt-bakumatsu_machiya-pressure-r2.json | 140247 | 7da24032e8b0e162（a724726） | 未通过：玩家这一轮什么也没看到 | 无 |
| opencode-pt-bakumatsu_machiya-pressure-r3.json | 248059 | 7da24032e8b0e162（cef6f03） | 通过 | 无 |
| opencode-pt-harbor_night_shift-daily-r1.json | 695581 | e0e8151e8a1bb751（a50c76a） | 通过 | 无 |
| opencode-pt-harbor_night_shift-daily-r2.json | 322506 | 7da24032e8b0e162（a724726） | 通过 | 无 |
| opencode-pt-harbor_night_shift-daily-r3.json | 623046 | 7da24032e8b0e162（cef6f03） | 通过 | 无 |
| opencode-pt-harbor_night_shift-pressure-r1.json | 342456 | e0e8151e8a1bb751（d43ba38） | 未通过：正文里出现命令名 load-slot；正文里出现命令名 commit-turn；正文里有一整行英文：I will execute `commit-turn` to submit the turn progress to  | 表达 |
| opencode-pt-harbor_night_shift-pressure-r2.json | 490426 | 7da24032e8b0e162（a724726） | 通过 | 无 |
| opencode-pt-harbor_night_shift-pressure-r3.json | 654935 | 7da24032e8b0e162（77d3416） | 通过 | 无 |
| opencode-pt-lantern_festival_town-daily-r1.json | 427642 | 3573ef69c9a1aa27（f61a525） | 未通过：正文前照抄了格式里的“正文：” | 无 |
| opencode-pt-lantern_festival_town-daily-r2.json | 385535 | 7da24032e8b0e162（bb5391a） | 通过 | 无 |
| opencode-pt-lantern_festival_town-daily-r3.json | 907872 | 7da24032e8b0e162（77d3416） | 未通过：正文里出现命令名 new-game；正文里出现命令名 doctor；正文里有一整行英文：Running doctor to check runtime environment and initialize l | 表达 |
| opencode-pt-lantern_festival_town-pressure-r1.json | 203818 | 3573ef69c9a1aa27（f61a525） | 未通过：玩家角色说了玩家没说过的话：“明晚那份契约，我一个人扛不下。眼下这局，谁替我分担一手？” | 无 |
| opencode-pt-lantern_festival_town-pressure-r2.json | 784876 | 7da24032e8b0e162（bb5391a） | 通过 | 无 |
| opencode-pt-lantern_festival_town-pressure-r3.json | 441418 | 7da24032e8b0e162（77d3416） | 通过 | 无 |
| opencode-pt-republic_press_street-daily-r1.json | 619394 | a3b94a7781c457c5（a9a6b0a） | 通过 | 无 |
| opencode-pt-republic_press_street-daily-r2.json | 187703 | 7da24032e8b0e162（d100aea） | 通过 | 无 |
| opencode-pt-republic_press_street-daily-r3.json | 838020 | 7da24032e8b0e162（77d3416） | 通过 | 无 |
| opencode-pt-republic_press_street-pressure-r1.json | 370971 | 7da24032e8b0e162（9a42229） | 通过 | 无 |
| opencode-pt-republic_press_street-pressure-r2.json | 691079 | 7da24032e8b0e162（cef6f03） | 通过 | 无 |
| opencode-pt-republic_press_street-pressure-r3.json | 3061 | 7da24032e8b0e162（17a1678） | 通过 | 无 |
| opencode-pt-winter_shelter-daily-r1.json | 514605 | 7da24032e8b0e162（48ef63d） | 通过 | 无 |
| opencode-pt-winter_shelter-daily-r2.json | 883321 | 7da24032e8b0e162（cef6f03） | 通过 | 无 |
| opencode-pt-winter_shelter-daily-r3.json | 495913 | 7da24032e8b0e162（17a1678） | 通过 | 无 |
| opencode-pt-winter_shelter-pressure-r1.json | 764363 | 7da24032e8b0e162（48ef63d） | 通过 | 无 |
| opencode-pt-winter_shelter-pressure-r2.json | 294593 | 7da24032e8b0e162（cef6f03） | 通过 | 无 |
| pi-pt-art_season_studios-daily-r4.json | 2153 | 7f11c7898c141ca3（6a954b3） | 通过 | 无 |
| pi-pt-art_season_studios-daily-r5.json | 333469 | 7f11c7898c141ca3（6a954b3） | 通过 | 无 |
| pi-pt-art_season_studios-pressure-r4.json | 3676 | 7f11c7898c141ca3（6a954b3） | 未通过：宿主这一轮没有正常结束：宿主重试后仍失败：503: {"message":"auth_unavailable: no auth available (providers=antigravity, model=gemini-3.8-flash-high; last upstream error: {\n  \"error\": {\n    \"code\": 503,\n    \"message\": \"The se（记录不完整，ACCEPTANCE §6.1 第 3 条）；这一步应当调用 new-game，实际调用：['doctor']；工具调用 2 次，超过这一步的预算 1（ACCEPTANCE §5） | 无 |
| pi-pt-art_season_studios-pressure-r5.json | 122788 | 7f11c7898c141ca3（6a954b3） | 通过 | 无 |
| pi-pt-art_season_studios-pressure-r6.json | 667768 | 0c47e9d0cac79ff4（c003f09） | 通过 | 无 |
| pi-pt-bakumatsu_machiya-daily-r4.json | 204193 | 7f11c7898c141ca3（6a954b3） | 未通过：正文里出现了引擎不知道的人：松井伊织（新人物要先登场） | 无 |
| pi-pt-bakumatsu_machiya-daily-r5.json | 513259 | 7f11c7898c141ca3（6a954b3） | 通过 | 无 |
| pi-pt-bakumatsu_machiya-pressure-r4.json | 56103 | 7f11c7898c141ca3（6a954b3） | 通过 | 无 |
| pi-pt-bakumatsu_machiya-pressure-r5.json | 342557 | 7f11c7898c141ca3（6a954b3） | 通过 | 无 |
| pi-pt-harbor_night_shift-daily-r4.json | 799738 | 7f11c7898c141ca3（6a954b3） | 通过 | 无 |
| pi-pt-harbor_night_shift-daily-r5.json | 37722 | 7f11c7898c141ca3（6a954b3） | 通过 | 无 |
| pi-pt-harbor_night_shift-pressure-r4.json | 227073 | 7f11c7898c141ca3（6a954b3） | 通过 | 无 |
| pi-pt-harbor_night_shift-pressure-r5.json | 615254 | 7f11c7898c141ca3（6a954b3） | 通过 | 无 |
| pi-pt-lantern_festival_town-daily-r4.json | 76631 | 7f11c7898c141ca3（6a954b3） | 通过 | 无 |
| pi-pt-lantern_festival_town-daily-r5.json | 997241 | 7f11c7898c141ca3（6a954b3） | 未通过：玩家这一轮什么也没看到；这一步应当调用 load-slot，实际调用：['doctor']；工具调用 2 次，超过这一步的预算 1（ACCEPTANCE §5） | 无 |
| pi-pt-lantern_festival_town-pressure-r4.json | 76727 | 7f11c7898c141ca3（6a954b3） | 通过 | 无 |
| pi-pt-lantern_festival_town-pressure-r5.json | 806226 | 7f11c7898c141ca3（6a954b3） | 通过 | 无 |
| pi-pt-republic_press_street-daily-r4.json | 436854 | 7f11c7898c141ca3（6a954b3） | 通过 | 无 |
| pi-pt-republic_press_street-daily-r5.json | 806130 | 7f11c7898c141ca3（6a954b3） | 通过 | 无 |
| pi-pt-republic_press_street-pressure-r4.json | 21701 | 7f11c7898c141ca3（6a954b3） | 通过 | 无 |
| pi-pt-republic_press_street-pressure-r5.json | 707397 | 7f11c7898c141ca3（6a954b3） | 通过 | 无 |
| pi-pt-winter_shelter-daily-r4.json | 915803 | 7f11c7898c141ca3（6a954b3） | 通过 | 无 |
| pi-pt-winter_shelter-daily-r5.json | 905483 | 7f11c7898c141ca3（6a954b3） | 通过 | 无 |
| pi-pt-winter_shelter-pressure-r3.json | 843781 | 7f11c7898c141ca3（6a954b3） | 未通过：宿主这一轮没有正常结束：宿主重试后仍失败：503: {"message":"auth_unavailable: no auth available (providers=antigravity, model=gemini-3.8-flash-high; last upstream error: {\n  \"error\": {\n    \"code\": 503,\n    \"message\": \"The se（记录不完整，ACCEPTANCE §6.1 第 3 条） | 无 |
| pi-pt-winter_shelter-pressure-r4.json | 658988 | 7f11c7898c141ca3（6a954b3） | 通过 | 无 |
| pi-pt-winter_shelter-pressure-r5.json | 453882 | 7f11c7898c141ca3（6a954b3） | 通过 | 无 |
| pi-pt-winter_shelter-pressure-r6.json | 387672 | 0c47e9d0cac79ff4（c003f09） | 通过 | 无 |
