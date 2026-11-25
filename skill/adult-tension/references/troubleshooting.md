# 环境问题与 `doctor`

`doctor` 检查运行环境并完成首次初始化（创建数据目录、数据库与迁移）。它是幂等的：同一版本成功过一次之后走快速路径，只做轻量检查。任何命令第一次运行时都会自动初始化，`doctor` 只是给出清楚的诊断。

输出里的 `checks`（成功时在 `data.checks`；有 `fail` 时信封 `ok` 为 false，位于 `error.doctor.checks`）每一项都有 `status`：`ok`、`warn` 或 `fail`，以及人话说明 `message` 与处理建议 `hint`。失败时 `error.code` 取最要紧的那一项，处理建议同时汇总在 `error.details[].hint`。

| 检查项 | 失败时的错误码 | 含义 | 处理 |
|---|---|---|---|
| `python` | `RUNTIME_UNSUPPORTED` | Python 低于 3.10 | 换用 3.10+；依次试 `python3`、`python`、`py -3`。不要自动安装 |
| `sqlite` | `RUNTIME_UNSUPPORTED` | 缺少 `sqlite3` 模块或 SQLite 太旧 | 换用自带较新 SQLite 的 Python |
| `data_dir` | `DATA_DIR_UNAVAILABLE` | 数据目录不可写，或位于 Skill 目录内部 | 用 `--data-dir` 指向可写目录，或设置环境变量 `ADULT_TENSION_HOME`；沙箱里请宿主放行该目录。运行时不会悄悄改用临时目录，那样存档会在重启后消失 |
| `migrations` | `UNSUPPORTED_VERSION` | 数据库来自更新版本的 Skill | 升级 Skill；数据库不会被修改 |
| `migrations` | `MIGRATION_FAILED` | 迁移中途失败 | 已自动恢复迁移前的备份（`backups/`）；换回可用的 Skill 版本，或把错误报告给维护者 |
| `skill_files` | `CONTENT_ERROR` | Skill 目录缺文件 | 重新安装完整的 Skill 目录 |
| `content` | `CONTENT_ERROR` | 编译后的内容缺失或损坏，`details` 指出文件与位置 | 重新安装 Skill 目录。已有会话使用自己的内容快照，仍可续玩 |

## 数据目录

定位顺序：

1. 命令行参数 `--data-dir`；
2. 环境变量 `ADULT_TENSION_HOME`；
3. 平台默认：Windows `%LOCALAPPDATA%\adult-tension`；macOS `~/Library/Application Support/adult-tension`；Linux `$XDG_DATA_HOME/adult-tension`，未设置时 `~/.local/share/adult-tension`。

目录内容：`adult_tension.db`（全部状态与存档）、`backups/`（迁移前及旧版导入升级前的备份）、`exports/`（导出的存档）、`inputs/`（即 `doctor` 返回的 `input_dir`，供不支持 heredoc 或管道中文编码异常的终端存放临时请求 JSON；开局、读档、导入时自动清理超一日旧文件，亦可随时手动删除）、`logs/`（运行日志，默认不记录玩家原文）、`cache/`（Python 字节码缓存，可随时删除）、`version.json`（`doctor` 的版本标记）。

数据目录永远不在 Skill 目录内部。升级 Skill = 替换 Skill 目录，数据目录不动；卸载 Skill = 删除 Skill 目录，数据目录保留。

## 其他情况

| 情况 | 处理 |
|---|---|
| 宿主调用超时、没有输出、输出不是 JSON | 写操作用**同一个 `request_id`** 重试最多 3 次（读操作直接重试）；仍失败则运行 `doctor`，用一句话告诉玩家 |
| `STORAGE_BUSY` | 数据库被另一个进程短暂占用；用同一个 `request_id` 重试 |
| `INTERNAL_ERROR` | 状态没有改变；`error.log` 给出日志位置，`error.error_id` 是日志里的编号 |

## 存档冲突

- 存档名已被占用（`save-slot` / `import-save` 返回 `SLOT_CONFLICT`，`reason: exists`）：问玩家“「名称」已存在，要覆盖吗？”，确认后带 `"overwrite": true` 重新提交，或换个新名字。
- 自定义世界名已被占用（`save-world` 返回 `SLOT_CONFLICT`，`reason: exists`）：问玩家“世界「名称」已存在，要覆盖吗？”，确认后带 `"overwrite": true` 重新提交，或换个新名字。
- 本局当前槽已在别的对话里被写过（`reason: changed_elsewhere`）：给玩家“A 读取最新 / B 另存为新名 / C 取消”。
- 导入被拒：文件校验失败、损坏或结构不合规（`INVALID_INPUT` / `INVARIANT_VIOLATION`）时如实告知，不猜内容；版本过新或不兼容（`UNSUPPORTED_VERSION`，如导出格式、状态版本或随机版本 `rng_version` 不兼容）时提示升级 Skill；指定 `slot` 同名冲突（`SLOT_CONFLICT`）按首条询问是否覆盖。上述情形均不写入任何数据。

## 升级、导出与卸载

- **升级**：用新版本的 Skill 目录替换旧目录，数据目录不动。新版本第一次运行时，如果数据库格式较旧，会先把数据库复制到 `backups/`（文件名带旧格式号与时间），再迁移；迁移失败就恢复备份并报 `MIGRATION_FAILED`，不加载任何会话。
- **换机器或留备份**：`export-save` 把一个会话或存档写成 `exports/` 下的 JSON 文件（也可以写到玩家给出的绝对路径），文件带完整性校验值；`import-save` 读回来，得到一个新会话。被改动、截断或缺字段的文件会被拒绝，来自更新版本的文件返回 `UNSUPPORTED_VERSION`，都不写入任何数据；较旧的文件先把原件复制到 `backups/` 再升级。
- **卸载**：删除 Skill 目录即可，数据目录保留，重新安装后存档都还在。
- **清除数据**是单独的操作，需要玩家明确确认：先导出想保留的存档，再手动删除上面“数据目录”一节给出的目录。运行时不会自行删除数据目录。
