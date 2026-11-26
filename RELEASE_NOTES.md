# Adult Tension 发布说明

Adult Tension 是一个面向成年人（18+）、尺度全开的中文高张力互动叙事 Skill。宿主模型负责理解玩家意图与撰写正文；随包附带的本地确定性引擎负责人物表里状态、关系张力、时间结算、把柄事件、玩家边界与 SQLite 存档，保证长局零漂移、不失忆。

- Skill 版本：`0.3.0`；数据库格式：4；状态格式：2。
- 内容：211 个世界（内容版本以随包 `content/index.json` 为准），说“世界列表”查看；另可自定义世界，说“保存世界 名字”存下来以后再玩。

## 需要什么

- Python 3.10 或更高（只用标准库；不需要 `pip install`）。宿主会依次试 `python3`、`python`、`py -3`。
- 一个能加载 Agent Skill 的宿主，或只有命令行的环境。

用户不需要编辑环境变量、不需要创建数据库、不需要复制世界包。

## 安装

安装 = 把整个 `adult-tension/` 目录放进宿主的 Skill 搜索路径。Git 克隆、压缩包解压或宿主的安装命令，结果都是同一个目录。

- **Claude Code**：放到用户级 Skill 目录（`~/.claude/skills/adult-tension/`）或项目级 Skill 目录（`<项目>/.claude/skills/adult-tension/`）。
- **Codex**：放到用户级 Skill 目录（`~/.agents/skills/adult-tension/`），或仓库里的 `.agents/skills/adult-tension/`（Codex 从当前目录一直找到仓库根）；`agents/openai.yaml` 提供显示名与默认提示。Codex 会自动发现新装的 Skill，没出现时重启 Codex。
- **OpenCode**：放到用户级 Skill 目录（`~/.config/opencode/skills/adult-tension/`）或项目里的 `.opencode/skills/adult-tension/`；OpenCode 也会读 Claude Code 的 `.claude/skills/`。
- **pi**：放到用户级 Skill 目录（`~/.pi/agent/skills/adult-tension/`，或几个宿主共用的 `~/.agents/skills/adult-tension/`），或项目里的 `.pi/skills/adult-tension/`、`.agents/skills/adult-tension/`（项目级的要先信任这个项目）。
- **只有命令行的环境**：放在任意位置，直接运行：

  ```bash
  python "adult-tension/scripts/adult_tension.py" doctor --json
  ```

装好之后，在新对话里说“开一局”。第一次玩之前，宿主会先运行一次 `doctor` 完成初始化（创建数据目录与数据库）。

## 数据目录

存档、备份、导出和日志都在数据目录里，**永远不在 Skill 目录内部**。定位顺序：

1. 命令行参数 `--data-dir`；
2. 环境变量 `ADULT_TENSION_HOME`；
3. 平台默认：
   - Windows：`%LOCALAPPDATA%\adult-tension`
   - macOS：`~/Library/Application Support/adult-tension`
   - Linux：`$XDG_DATA_HOME/adult-tension`，未设置时 `~/.local/share/adult-tension`

目录里有：`adult_tension.db`（全部状态与存档）、`backups/`（升级前的数据库备份）、`exports/`（导出的存档）、`inputs/`（宿主交给运行时的输入文件，可以随时删除）、`logs/`（运行日志，默认不记录玩家原文）、`cache/`（字节码缓存，可以随时删除）、`version.json`。

宿主的沙箱只允许写工作区时，`doctor` 会报 `DATA_DIR_UNAVAILABLE`，写明试过的路径与原因；请让宿主放行上面的目录，或用 `--data-dir` 指向一个可写的位置。运行时不会悄悄改用临时目录——那样存档会在重启后消失。

## 升级

用新版本的 `adult-tension/` 目录整个替换旧目录，数据目录不动。新版本第一次运行时，如果数据库格式较旧：先把数据库复制到 `backups/`（文件名带旧格式号与时间），再迁移；迁移失败会恢复备份并报 `MIGRATION_FAILED`，不加载任何会话。存档或导出文件来自更新的版本时报 `UNSUPPORTED_VERSION`，提示升级 Skill，不修改任何数据。

## 卸载与清除数据

- **卸载**：删除 `adult-tension/` 目录即可。数据目录保留，重新安装后存档都还在。
- **清除数据**是单独的操作，需要你明确确认：先用“导出”留下想保留的存档，再手动删除上面“数据目录”一节给出的目录。运行时不会自行删除数据目录。

## 换机器、留备份

对宿主说“导出”（可以指定一个存档），会在数据目录的 `exports/` 下得到一个带完整性校验的 JSON 文件；在新机器上说“导入 文件路径”（或直接粘贴文件内容），即可接上进度继续游玩。被改动、截断或缺字段的文件会被拒绝，原有数据不受影响。

## 已知限制

- 目前只在 Windows 11（Python 3.12）上做过完整测试；Linux 与 Python 3.10 的真实测试尚未进行，3.10 由静态检查与语法校验兜底。
- 所有叙事质量都依赖宿主里的模型；运行时保证状态一致、边界与规则被执行，但文笔与表现力取决于模型本身。
- 自定义世界不进世界列表，不能“重开 N 号”（同一个世界描述加同一个种子可以复现）；想再玩就在开局后说“保存世界 名字”，以后说“我的世界”找到它。
- 上下文有体积上限（简要 ≤ 6 KB、完整 ≤ 32 KB）；人物极多时，按相关性分级精简离场人物卡片。
- 撤销最多退回到本次读档或开局的那一回合；每个会话保留最近 30 回合的撤销点。
