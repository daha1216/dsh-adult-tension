# Adult Tension 发布说明（草稿）

> 草稿：发布前按 `spec/ACCEPTANCE.md` §9 逐条核对（`reports/release/checklist.md`）。在六个世界都是 `released`、端到端评测与发布演练完成之前，这份说明不对外。

Adult Tension 是一个面向成年人的中文互动叙事 Skill。宿主里的模型负责理解玩家和写正文；随 Skill 附带的本地运行时负责人物、关系、时间、事件、边界与存档，保证长局不失忆、不自相矛盾。

- Skill 版本：`0.3.0`；数据库格式：3；状态格式：2。
- 内容：六个世界——港口夜班、民国报馆与手艺街、幕末町屋与道场、旧町神怪与灯会、成年创作者与艺术季、寒冬避难所公共生活；另可自定义世界（只存在于那一局）。

## 需要什么

- Python 3.10 或更高（只用标准库；不需要 `pip install`）。宿主会依次试 `python3`、`python`、`py -3`。
- 一个能加载 Agent Skill 的宿主，或只有命令行的环境。

用户不需要编辑环境变量、不需要创建数据库、不需要复制世界包。

## 安装

安装 = 把整个 `adult-tension/` 目录放进宿主的 Skill 搜索路径。Git 克隆、压缩包解压或宿主的安装命令，结果都是同一个目录。

- **Claude Code**：放到用户级 Skill 目录（`~/.claude/skills/adult-tension/`）或项目级 Skill 目录（`<项目>/.claude/skills/adult-tension/`）。
- **Codex**：放到用户级 Skill 目录（`~/.agents/skills/adult-tension/`），或仓库里的 `.agents/skills/adult-tension/`（Codex 从当前目录一直找到仓库根）；`agents/openai.yaml` 提供显示名与默认提示。Codex 会自动发现新装的 Skill，没出现时重启 Codex。（位置依据 Codex 官方文档，2026-09 核对。）
- **只有命令行的环境**：放在任意位置，直接运行：

  ```bash
  python adult-tension/scripts/adult_tension.py doctor --json
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

目录里有：`adult_tension.db`（全部状态与存档）、`backups/`（升级前的数据库备份）、`exports/`（导出的存档）、`logs/`（运行日志，默认不记录玩家原文）、`cache/`（字节码缓存，可以随时删除）、`version.json`。

宿主的沙箱只允许写工作区时，`doctor` 会报 `DATA_DIR_UNAVAILABLE`，写明试过的路径与原因；请让宿主放行上面的目录，或用 `--data-dir` 指向一个可写的位置。运行时不会悄悄改用临时目录——那样存档会在重启后消失。

## 升级

用新版本的 `adult-tension/` 目录整个替换旧目录，数据目录不动。新版本第一次运行时，如果数据库格式较旧：先把数据库复制到 `backups/`（文件名带旧格式号与时间），再迁移；迁移失败会恢复备份并报 `MIGRATION_FAILED`，不加载任何会话。存档或导出文件来自更新的版本时报 `UNSUPPORTED_VERSION`，提示升级 Skill，不修改任何数据。

## 卸载与清除数据

- **卸载**：删除 `adult-tension/` 目录即可。数据目录保留，重新安装后存档都还在。
- **清除数据**是单独的操作，需要你明确确认：先用“导出”留下想保留的存档，再手动删除上面“数据目录”一节给出的目录。运行时不会自行删除数据目录。

## 换机器、留备份

对宿主说“导出”（可以指定一个存档），会在数据目录的 `exports/` 下得到一个带完整性校验的 JSON 文件；在新机器上说“导入 <文件路径>”，得到一个新会话。被改动、截断或缺字段的文件会被拒绝，原有数据不受影响。

## 已知限制

- 目前只在 Windows 11（Python 3.12）上做过完整测试；Linux 与 Python 3.10 的真实测试尚未进行（`PROGRESS.md` 待决事项 P2、P3），3.10 只有静态检查兜底。
- 所有叙事质量都依赖宿主里的模型；运行时保证状态一致、规则被执行，但写得好不好取决于模型。端到端评测的结果见 `reports/e2e/`（发布前补齐）。
- 自定义世界只存在于开它的那一局：不进世界列表，不能“重开 N 号”（同一个世界描述加同一个种子可以复现）。
- 上下文有体积上限（简要 ≤ 6 KB、完整 ≤ 20 KB）；人物很多时，不在场的人物只给摘要。
- 撤销最多退回到本次读档或开局的那一回合；每个会话保留最近 30 回合的撤销点。
