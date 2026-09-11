# 🎭 adult-tension

[![Release](https://img.shields.io/github/v/release/daha1216/dsh-adult-tension?style=flat-square)](https://github.com/daha1216/dsh-adult-tension/releases)
[![Host: DeepSeek Harness](https://img.shields.io/badge/Host-DeepSeek_Harness-blue?style=flat-square)](https://github.com/daha1216/dsh-adult-tension)
[![Content: 18+ Adult RP](https://img.shields.io/badge/Content-18%2B_Adult_RP-critical?style=flat-square)](https://github.com/daha1216/dsh-adult-tension)

> **插件形态：AI Skill**：以 **DeepSeek Harness** 为主要运行与实玩验收宿主，核心入口是 `SKILL.md`。其他 AI Agent 的兼容性按各自实测确认。安装时完整复制仓库，不要只复制单个文件。

**专为高张力、强连续性的成人互动叙事打造**——从暗流涌动的身份博弈，到扣人心弦的情感纠葛，随机开局组合出几乎不重复的完整新故事。

**自带破甲，尺度放开**——内置深层语境铺垫与脱敏叙事引导，告别机械死板的说教与扫兴拒答，让角色坦诚面对欲望、私心与对抗，剧情沉浸不断档。

**内置上千项素材的世界库，NPC 会真正记得你**——从时代地点、角色身份到张力与压力，角色拥有自己的立场与底线，会犹豫、拒绝、试探，也可能在你离开后自行行动。

**世界真的会往前**——离屏事件按时追算，一句闲话可能变成几章后的伏笔。

**随时存档，随时续玩**——YAML 存档从原节点继续，长线剧情不重掷、不丢失、不漂移。

> ⚠️ **成年人内容（18+ Only）**：仅限虚构成年人，所有参与角色必须明确年满 18 岁。

---

## 🎬 体验切片

在这里，NPC 不做被动迎合的工具人，世界也不会在你离开后停滞：

```text
> 玩家：开局 盛唐长安 压力开局

【世界观】盛唐长安。宵禁将至，六百响更鼓只余最后的沉闷尾音。
【人物】沈青澜，大理寺录事，素白袖口沾着未干的墨迹，手中紧攥着半截暗账案卷。
【正文】她背抵着卷宗库沉重的楠木门，听见你逼近的脚步声，指尖骤然收紧：
       “今夜值守的明明不是你……站住，再往前一步，休怪我不念旧情。”
       她呼吸微促，目光死死钉在你腰间的巡夜佩刀上，身后的门闩已被悄悄插死。

> 玩家：我没有拔刀，走上前反手扣住门板，低头凑近她耳边：“把账本交出来，或者我现在就带你出去。”
```

---

## 🚀 快速安装

让 AI 直接安装本仓库：

```text
帮我安装这个 skill：https://github.com/daha1216/dsh-adult-tension
```

也可以手动安装：把仓库根目录的一整套文件（含 `SKILL.md`、`commands.yaml`、`references/`、`scripts/data/`、`authoring/`、`maintenance/`、`saves/`、`tests/`、`agents/` 与依赖清单）完整复制到 DeepSeek Harness 的技能目录。不要只复制 `SKILL.md`；维护清单与审查文件也有实际消费者。

复制完成后，让 AI 加载 `adult-tension` 技能即可开始。

---

## ▶️ 怎么开始

**想直接玩，一句话就够：**

```text
开局
```

未指定类型时先选择“压力开局”或“日常开局”；直接说出类型则立即生成，只有明确委托“随便”才默认日常。日常模式复用旧素材的低压解释，不预设外部压力、危机倒计时或事件链；压力模式保持原有流程。载入与续玩不重新选择。

仅新局依次使用 `世界观`、`人物`、`正文` 三个标题，前两项各 1-2 句；正文停在你能接手的动作前。载入与续玩不重复三个标题。之后直接描述角色的行动或台词即可：

```text
我走到她面前，把文件放在桌上
对她说：我们单独谈谈
跟着她钻进电梯，问今晚去哪
```

**开始前想加点控制？** 不必记技术参数，直接说你的想法就行：

| 我有这个想法 | 我直接对 AI 说 |
| --- | --- |
| 要一个能一模一样复刻的开局 | 「种子 42」——固定随机结果，下次照着来 |
| 先定人物方向或题材，其它随便 | 「开局，想玩帝国女帝，走宫廷权谋」——由模型映射到合适的时代、身份和压力组合 |
| 锁定某几项设定，其余随机 | 「预锁 处境=资源断供」「预锁 张力引擎=信任透支」 |
| 内容只许来自技能自带素材 | 「强制表内」——仅从技能自带素材中生成设定 |
| 允许在自带素材之外自拟核心设定 | 「表外全随机」——后台显式使用 `--framework legacy --all-custom`，仍遵守成年角色规则 |

故事开始后，用这些自然指令推进和管理：

| 命令 | 什么时候用 |
| --- | --- |
| `继续`（`c`） | 剧情停在可接续处时，向前推一个节拍 |
| `快进到明天早上` | 跳过一段时间，让离屏事件被追算、世界自己长 |
| `状态` | 六行人话看板：地点、在场、当前压力、所处情境、可接续动作 |
| `存档`（`qs`） | 写入当前槽；成功只回一句「已保存到「名称」·第 N 回合」，不刷屏 |
| `保存 X` | 另存为命名存档 X，可开多条独立走向互不覆盖 |
| `载入 X` | 载入命名存档 X 并绑定为写入目标，从原节点继续 |
| `列出存档` | 显示所有命名存档的名称、回合与一句话处境 |
| `导出存档` / `载入存档` | 把当前局面导出成 YAML 文本带走备份，之后再发回来即可原地续玩 |
| `撤销刚才的 X` | 只撤销最近一个事件，不推进回合 |

> 提示：高级功能随用随说：`帮助` 列出全部命令，另有贴视角、语态切换、冻结世界推演、叙事助手等，触发词详见 [`commands.yaml`](./commands.yaml)。一个会话默认使用自己的专属存档；需要继续已有主线时明确「载入 X」。保存时若存档已被其他窗口修改，会提示你读取最新版本、另存为其他名称或取消，不会静默覆盖。

---

## ✨ 核心能力

这个 Skill 把角色、世界、时间、关系和存档放进同一套运行规则，服务的是长期连续游玩的场景：一次开局的文采只是开始，多轮互动之后的状态是否连贯、角色是否可信、能否从原节点继续，才是它的重心。

* **角色：记得你，也有自己的判断**
  * **记忆与连续性**——NPC 记住对话与事件，立场、目标与底线不因一次回复重置，关系不会无故归零。
  * **自主决策**——NPC 会犹豫、拒绝、协商、试探，也可能在你离开后主动行动，行为由状态、关系与当前压力共同决定。
  * **层次推进**——关系推进讲求铺垫与氛围层次，随互动深入自然演进，拒绝突兀展开。

* **世界：真的会一直走下去**
  * **时间推进**——场景之外的事件按规则追算，世界不会在你离开时停摆。
  * **连续记录**——地点、参与者、压力与事件留下连续记录，一句闲话可能成为之后的伏笔。

* **体验：想开就开，想续就续**
  * **随机开局 + 定向控制**——可以完整随机生成，也可以预锁身份、时代、题材或张力方向；时代与地点自动和解，不会出现「魔法工坊 × 当代都市」式的错位组合。
  * **可恢复存档**——YAML 保存世界时钟、角色状态、关系、事件与当前节点，载入后从原节点继续，不重新生成开局。
  * **存档简单直接**——`存档` / `保存 X` / `载入 X` 管理命名存档；多窗口写入冲突时有友好提示，不会悄悄覆盖。

---

## 🧠 用什么模型玩

具体游玩体验和出文效果，会随模型版本、上下文长度和平台配置而变化。以下是维护者在体验中的参考建议：

* **DeepSeek**：长线中文叙事底蕴深厚，人物心理状态连续性极佳，适合历史权谋与多轮慢热游玩。
* **Grok**：临场感强，语言风格更放开，在紧张对峙与快节奏情节推进中表现突出。

其他主流模型也能正常游玩；对话轮次越深，角色一致性、时间线和语感就越依赖所选模型的上下文能力。建议按你的平台与偏好实际试用。

---

## 📦 内置素材：从设定到角色的一整套世界库

每次开局不是简单的关键词拼接，而是多层叙事素材的深度咬合。系统内置 **40 个世界框架** 与上千项微观素材，在 `authoring/frameworks/` 编辑并经由 [`scripts/data/`](./scripts/data/) 运行，涵盖了从历史正剧、都市暗潮到异界幻想的丰富舞台：

* **历史与风云**：盛唐夜市坊志、幕末町屋道场、一九二八芝加哥禁酒期黑帮……
* **近未来与边缘**：赛博街区公共终端、星海边境生活站、废土修补集市……
* **异界与志怪**：契约城非人街坊、旧町神怪灯会、仙门藏书与驿镖……
* **当代与暗流**：传媒编辑室暗访、成年创作者艺术季、同人展录音协作……

当这套庞大的素材库运转时，世界框架决定风土，人物反差注入戏剧性，压力来源倒逼抉择，而细腻的动作库则保证了关系推进真实可信：

| 内容 | 数量 | 示例 |
| --- | --- | --- |
| 时代与地点 | 时代 31 · 地点 128 | 盛唐长安百鬼夜行、一九二八芝加哥禁酒期、文久幕末京都风云 |
| 张力引擎 | 72 条 | 天枢锁妖大阵灵气逆流、黑帮教父暗账审计之夜、时限逼近 |
| 压力来源 | 74 条 | 宵禁六百响更鼓将毕、同人展压盘死线近在眼前、经纪人在录音室门外敲门查岗 |
| 角色身份 | NPC 17 族 89 身份 · 玩家化身 31 种 | 权力与治理、家族与继承、服务与手艺 |
| 角色处境 | 84 条 | 秘密将破、旧事上门、洗刀水色变红的瞬间、录音红灯亮起时的实景耳语夜 |
| 人物性格与反差 | 反差轴 26 种 | 外冷内热、端庄放浪、禁欲破戒、严苛沦陷 |
| 关系与权力 | 4 种 | 玩家上位、NPC 上位、平等或动态切换 |
| 语言风格 | 表层风味 120 · 口癖语感 48 | 敬语过剩、句尾口癖、拟声词多 |
| 场景动作 | 交易摊牌 22 · 非交易靠近 91 | 核对一条时间线、让对方决定是否查看文件、在防喷罩前替她理顺耳机线 |
| 中期转折池 | 7 类 × 9~12（共 70 条） | 信息类、资源类、时限类等 |
| 配角功能 | 15 类 | 盟友、竞争者、误导者、催化剂 |

**更有质感的微观细节**：
- **拒绝出戏的命名**：内置专属名池（汉化、古代名、时代名），命名服从时代文化背景，不局限现代姓名。
- **立体的对话质感**：26 种称谓体系、46 种美学基调与 48 组语感口癖，写实基调下自动收口外观与口癖。
- **微观动作画像**：涵盖地点画像、动作分类、身份行为与转折画像，赋予角色自然的肢体语言。想要扩充自定义内容？详见 [`references/加内容.md`](./references/加内容.md)。

---

## 🛠️ 辅助工具与底层架构

<details>
<summary>点击展开：本地 CLI 辅助工具、状态契约与维护规范</summary>

普通游玩不需要运行脚本。以下命令适合需要固定随机结果、生成转折方向、查看状态或检查内容的场景。请在仓库根目录执行，先装依赖：

```bash
# 依赖只有 PyYAML（Python 3.10+）
python -m pip install -r requirements.txt

# 维护和运行测试额外安装
python -m pip install -r requirements-dev.txt

# 全自动开局：一次生成可开场的 v3 状态与开局简报（「开局」命令的后端）
python scripts/build_opening.py --complete --opening-mode daily --seed 42
# 压力开局将 daily 替换为 pressure；省略模式只返回选择提示，不写状态。
# 默认 auto 只选审查有效的框架；没有合格框架时报错，不隐式回退 legacy。
# 需要独立旧池时显式追加 --framework legacy。

# 生成 2～3 个中期转折方向（压力模式首次跨天或玩家明确要求时）
python scripts/roll_opening.py --twist --seed 42

# 人话状态视图（「状态」命令的后端）
python scripts/live_slice.py --session <session> --human

# 后台切片与定向事件查询（session 来自成功开局 brief）
python scripts/live_slice.py --session <session> --format json
python scripts/live_slice.py --session <session> --event <ID>

# 明确绑定本会话，并校验上一拍看到的 token
python scripts/commit_turn.py --session <session> --expected-state-token <state_token> --patch '<json>'

# 校验 YAML 存档的结构和状态
python scripts/validate_state.py path/to/save.yaml

# 列出命名存档 / 校验并查看某个命名存档
python scripts/manage_saves.py list
python scripts/manage_saves.py load main
```

`build_opening.py` 支持 `--framework auto|legacy|框架名称` 选择世界框架，支持 `--lock 字段=值` 锁定特定设定（可重复）、`--force-table` 仅用自带素材、`--all-custom` 配合 `--custom KEY=VALUE` 自拟核心设定。存档由 `manage_saves.py` 原子写入：每个存档目录包含 `state.yaml`（v3 叙事状态）与 `manifest.yaml`（创建/更新时间），覆盖保存需携带载入时记录的 `--expected-updated-at`，不一致即拒绝且不自动合并——按提示读取最新版本、另存为其他名称或取消。

`--all-custom` 不解除框架约束：默认 `auto` 下，自拟核心规则、时代等若与所有已审框架都不兼容，开局会拒绝，不会静默回退。自由表外世界必须显式使用 `--framework legacy --all-custom` 并补齐所需 `--custom KEY=VALUE`；这也不绕过日常模式限制或状态校验。

新局默认工作档是唯一的 `saves/sessions/<uuid>/state.yaml`，可用 `--session ID` 显式指定稳定会话。后台返回 `session/state_path/state_token`，token 是文件原始字节 SHA256，不进 v3 状态。提交必须显式指定 `--session` 或 `--state`；前者必须携带 token，旧路径可显式 `--state saves/current_state.yaml` 接续。保留 `--out`、`--working`、`--no-working` 工件用法，细节见 [开局流程](./references/开局流程.md)。输出已存在或状态写入失败不污染开局历史。

命名槽与工作会话分开；`load` CLI 只返回 manifest，宿主用 `SaveStore.load_slot` 的同锁快照建立会话副本，详见 [载入流程](./references/状态总结.md#载入流程)。槽位解析和 checksum 校验使用同一字节快照；保存失败恢复原有效文件对，初始化失败不留可用槽。终态事件保留在 events 中，不做物理归档；新解决/取消结果通过 `event_changes` 和 outcome 返回，旧事件可用 `live_slice.py --event` 定向读取。

维护日常顺序是 **编辑 authoring → build_frameworks --write → sync_governance --write → qa**：

```text
python scripts/build_frameworks.py --write
python scripts/sync_governance.py --write
python scripts/qa.py --changed
```

`qa.py --framework <名称>`、`--material <稳定ID>` 用于定向验证；`--full` 做全量结构与回归检查；`--full --release` 另核验当前语义审查与实玩证据；`--full --update-fingerprint` 只在检查通过且数据未再次变化时更新指纹。`--plan` 只查看计划。构建和同步不会代替人工审查。

单框架源或 review 连同生成聚合、registry、指纹的改动，在 `--changed` 中仍按框架抽样；其他共享改动可扩大范围。`--material` 遇框架 ID 同样选择对应框架。全量 QA 的分布分析运行 `analyze_content.py --samples 1000`，默认是 `--framework auto --opening-mode pressure`；独立旧池须显式指定 `--framework legacy`，其分布不能代表默认玩法。重复候选由 `check_duplicates.py` 对照人工记录核验，不自动删重；当前保留项与人物资源复用的计数口径见 [加内容](./references/加内容.md#2-标准维护流程)。

**结构通过不等于语义通过，不等于 320 条实玩响应已完成。** 实玩门槛为 40 框架 × daily/pressure × 新局及 3 次续写，证据与独立评分由 `playtest_report.py` 检查。`run_playtest.py --framework <名称>` 必须显式调用，会消耗模型额度；默认 QA 不会自动调用它。未跑、缺评分或来源哈希过期时如实报告，不用内存开局或单测数充当实玩完成数。

### 📁 仓库文件结构

| 位置 | 里面是什么 |
| --- | --- |
| `SKILL.md` | 技能运行规则（主控文档） |
| `commands.yaml` | 命令总表：触发词、行为与后台 CLI 的唯一来源 |
| `references/` | 开局流程、角色设计、世界运转、存档格式与扩充指南 |
| `scripts/` | 开局生成、回合提交、活切片、存档管理与内容体检工具 |
| `scripts/data/` | 运行数据；`world_frameworks.yaml` 是生成文件，不直接编辑 |
| `authoring/frameworks/` | 单框架编辑源；顺序与稳定 ID 由 `authoring/framework_index.yaml` 维护 |
| `maintenance/` | data_manifest 职责与依赖、core_review_decisions、framework_reviews、冻结基线、指纹及实玩证据 |
| `saves/` | 工作会话在 `sessions/`，命名槽在 `slots/`，两者独立 |
| `tests/` | 自动化测试与文档一致性检查 |
| `agents/` | AI 工具配置（如 `openai.yaml`） |

职责导航见 [素材架构](./references/素材架构.md)，L0-L3 扩充、审查和有证据的直接清理见 [加内容](./references/加内容.md)。`maintenance/data_manifest.yaml` 管文件职责与依赖，`maintenance/core_review_decisions.yaml` 管核心池人工处置，`maintenance/framework_reviews/*.yaml` 管框架审查。冻结整节的字节哈希须与 `maintenance/baseline.yaml` 一致；历史记录见 [PROGRESS.md](./PROGRESS.md)，不当作当前验收证明。

</details>

---

## 🏷️ 版本发布

各阶段稳定版本可在 [GitHub Releases](https://github.com/daha1216/dsh-adult-tension/releases) 获取。日常游玩建议直接拉取 `main` 分支获取最新的世界框架与素材更新。
