# Skill 封装与安装

交付物是一个可以直接安装的通用 Agent Skill。引擎能跑不等于交付完成（`AGENTS.md`）。本文件定义 Skill 目录里有什么、怎么被宿主发现、第一次怎么初始化、数据放在哪里、怎么升级和卸载，以及发布前必须做的真实演练。

## 1. Skill 目录

可安装物是仓库里的一个子目录（D1，建议 `skill/adult-tension/`）：

```text
adult-tension/
├─ SKILL.md                 # 入口说明，≤ 16 KB，由 SKILL_TEMPLATE.md 改写而来
├─ agents/openai.yaml       # 可选的界面元数据与默认提示
├─ references/              # 按需读取的详细资料（见 §3）
├─ scripts/adult_tension.py # 唯一入口
├─ runtime/adult_tension/   # 运行时代码，只用标准库
└─ content/                 # 编译好的世界包与标签表
```

不得出现在 Skill 目录里的：测试、内容源文件、开发工具、报告、`PROGRESS.md`、缓存、任何用户数据、任何运行时不读的治理数据。发布检查会列出 Skill 目录的全部文件并对照这条规则。

## 2. `SKILL.md`

- frontmatter 至少有 `name` 与 `description`。`description` 说明**什么时候用**（用户要开始、继续、查看、存读、管理一局 Adult Tension 故事）和**能做什么**，不塞安装命令和规则细节。
- 正文是调用 Agent 每次都会读到的部分，只放：最高优先级规则摘要、调用流程、命令与别名、回执格式、`references/` 目录。
- 体积 ≤ 16 KB（UTF-8）。超出的内容移到 `references/`。
- 所有路径相对于 Skill 目录；不链接到仓库根目录的文档（安装后它们不存在）。

## 3. `references/`

按需读取，不要求调用 Agent 预先全部加载。至少包括：

| 文件 | 内容 | 什么时候读 |
|---|---|---|
| `narrative.md` | `NARRATIVE_RULES.md` 的内容；措辞可以压缩，规则一条不能少，章节编号保持不变（`SKILL.md` 按编号引用） | 需要判断主权、NPC 回应、亲密写作、知识边界时 |
| `operations.md` | 全部操作的字段参考，由校验器生成 | 组装提交时拿不准字段 |
| `commands.md` | 全部命令的输入输出、错误码与退出码 | 出错时或用到少见命令时 |
| `worlds.md` | 世界列表与一句话介绍，由内容编译生成 | 用户问有哪些世界时（也可以直接调用 `list-worlds`） |
| `troubleshooting.md` | `doctor` 各项失败的含义与处理 | 环境出错时 |

由代码生成的参考文件在构建时生成并提交，测试检查它与代码一致，避免文档漂移。

## 4. 安装

安装 = 把 Skill 目录放进宿主的 Skill 搜索路径。具体位置以各宿主官方文档为准，发布说明中给出至少以下三种：

- **Codex**：放入 Codex 的 Skill 目录；`agents/openai.yaml` 提供显示名与默认提示。
- **Claude Code**：放入用户级或项目级的 Skill 目录（每个 Skill 一个子目录，内含 `SKILL.md`）。
- **只有命令行的环境**：任意位置，直接运行 `python <skill_dir>/scripts/adult_tension.py doctor --json`。

用户不需要 `pip install`、不需要编辑环境变量、不需要创建数据库或复制世界包。安装方式可以是 Git 克隆、压缩包解压或宿主的安装命令，结果都是同一个目录。

## 5. Python 与入口脚本

- 需要 Python 3.10+，只用标准库。
- `SKILL.md` 告诉调用 Agent 按顺序尝试 `python3`、`python`、`py -3`，用第一个版本合格的。
- `scripts/adult_tension.py` 的前几行只用旧版本也能解析的语法，先检查版本；版本过低时输出 `RUNTIME_UNSUPPORTED` 信封并说明需要的版本，而不是抛出语法错误。
- 入口脚本根据自己的路径找到 `runtime/`，不依赖当前工作目录、`PYTHONPATH` 或安装步骤。
- 检查 `sqlite3` 可用，且 SQLite 版本支持所用特性。

## 6. 数据目录

定位顺序：

1. `--data-dir` 参数；
2. 环境变量 `ADULT_TENSION_HOME`；
3. 平台默认：Windows `%LOCALAPPDATA%\adult-tension`；macOS `~/Library/Application Support/adult-tension`；Linux `$XDG_DATA_HOME/adult-tension`，未设置时 `~/.local/share/adult-tension`。

规则：

- 数据目录永远不在 Skill 目录内部。升级会覆盖 Skill 目录，不能带走存档。
- 目录不可写时（例如宿主沙箱只允许写工作区），返回 `DATA_DIR_UNAVAILABLE`，附上尝试过的路径、失败原因和可行的建议（例如让宿主放行该目录，或用 `--data-dir` 指向可写位置）。不静默退回到临时目录——那样存档会在重启后消失。
- 目录内容：数据库、备份、`exports/`、`logs/`、版本标记。

## 7. 首次初始化与 `doctor`

- 任何命令第一次运行时都幂等地完成初始化：创建数据目录、创建数据库、执行迁移。
- `doctor` 做同样的事，再加上完整诊断：Python 版本、Skill 根目录、数据目录可写、SQLite 版本、迁移状态、内容编译产物完整且校验通过、`SKILL.md` 与 `references/` 存在。
- 每一项输出 `ok` / `warn` / `fail` 与人话说明；任何 `fail` 都附处理建议。
- 同一 Skill 版本已经成功过的 `doctor` 走快速路径（只做轻量检查），满足 `ACCEPTANCE.md` §4 的首次与后续耗时。
- 初始化被中断（进程被杀）后，下一次运行能继续完成，不留下“看起来成功”的半成品。

## 8. 升级与卸载

- **升级** = 用新的 Skill 目录替换旧的。数据目录不动。
- 新版本第一次运行时，如果数据库 schema 较旧：先把数据库复制到 `backups/`（带时间戳与旧版本号），再迁移；迁移失败则恢复备份，返回明确错误，不加载任何会话。
- 存档或导入文件的 schema 比当前版本新：`UNSUPPORTED_VERSION`，提示升级 Skill。
- 只做经过测试的向前迁移。每个迁移都有一个用旧版本真实数据库做的测试。
- **卸载** = 删除 Skill 目录。数据目录保留。清除数据是一个单独的、需要明确确认的操作，发布说明里写清数据目录的位置。

## 9. 发布前的真实演练

在一台干净的机器（或干净的虚拟机 / 容器，Windows 与 Linux 各一次）上：

1. 只复制 Skill 目录，按 §4 安装到一个真实宿主。
2. 新开对话，用玩家的话说“开一局”。确认宿主发现并加载了 Skill，调用了 `doctor` 与 `new-game`。
3. 推进 3 个回合，其中一个是“继续”。
4. 存档，关闭对话。
5. 新开对话，说“读档”，确认续上，正文与上一局的人物、地点、未决动作一致。
6. 用新版本的 Skill 目录替换旧的（模拟升级，至少包含一次 schema 迁移）。
7. 继续推进 1 回合。

全过程用户不执行任何 Python、SQLite 或环境变量操作。记录宿主名称与版本、模型身份、每一步的实际调用与耗时，放进 `reports/`。

## 10. 故障演练

每项都必须失败得可识别、给出可执行的建议，并且不损坏已有存档：

| 演练 | 期望 |
|---|---|
| Python 版本过低（用 3.8 或 3.9 运行入口脚本） | `RUNTIME_UNSUPPORTED` 信封，说明需要的版本 |
| 数据目录不可写 | `DATA_DIR_UNAVAILABLE`，附尝试过的路径与建议 |
| 编译后的内容被篡改（删掉一个被引用的地点） | `doctor` 报 `CONTENT_ERROR` 并指出位置；已有会话仍然可以续玩（它们用自己的内容快照） |
| 数据库 schema 比 Skill 新（先用新版本打开，再换回旧版本） | `UNSUPPORTED_VERSION`，数据库不被修改 |
| 迁移中途失败（测试钩子注入） | 自动恢复备份，错误说明清楚，下一次正常版本可以继续 |
| 写事务期间进程被杀 | 下一次打开时状态停在上一个 revision，没有半写入 |
| 两个进程同时提交同一会话 | 一个成功，另一个得到 `STALE_REVISION` 或 `STORAGE_BUSY`，没有重复推进 |

## 11. 宿主差异与调用错误

- 宿主可能超时、截断输出、在沙箱中拒绝写入或拒绝执行命令。`SKILL.md` 告诉调用 Agent：超时或输出不完整时，用同一个 `request_id` 重试最多 3 次（幂等保证不会重复推进；与 `RUNTIME_PROTOCOL.md` §11 一致）；沙箱拒绝时，把原因告诉玩家，不绕开。
- stdout 永远只有一个 JSON 信封；任何诊断输出走 stderr 或日志，避免宿主把日志当结果解析。
- 输出以 UTF-8 字节写出，不依赖控制台代码页（Windows 上尤其重要）。

## 12. 仓库卫生

- `.gitattributes` 强制文本文件为 LF；编译产物与生成的参考文件是确定性的。
- CI 至少在 Windows 与 Linux 上各跑一次核心测试、内容校验和 Skill 结构检查（`tools/validate_skill` 之类的脚本：frontmatter、体积、相对链接、禁止文件）。
