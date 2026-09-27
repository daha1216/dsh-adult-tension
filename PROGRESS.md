# PROGRESS

本文件记录 Adult Tension 全量重写的执行进度。需求来源只有 `spec/`（只读）；本机约束见 `ENVIRONMENT.md`。

## 当前状态

- 当前阶段：阶段 1（单世界垂直切片）
- 下一步：港口夜班世界包 + 内容编译器与 `verify-content` 结构检查 → 领域核心 → 唯一写路径 → `new-game`/`get-context`/`commit-turn`/存读档/`smoke`

## 待决事项（需要用户决定）

| # | 事项 | 现状与影响 | 暂行做法 |
|---|---|---|---|
| P1 | 真实宿主不可用 | 本机 `claude`（npm 安装）报 `claude native binary not installed`，修复需在仓库外运行 `node %APPDATA%\npm\node_modules\@anthropic-ai\claude-code\install.cjs` 或重装；OpenCode Go 订阅未激活（Go 模型 403）。阶段 1 起的真实宿主试玩、阶段 6 的两宿主评测都依赖这两项 | 阶段 0 用 OpenCode 免费模型 `opencode/big-pickle` 做了一次无成人内容的冒烟。含成人内容的试玩在用户决定宿主与模型之前不做 |
| P2 | Linux 测试方式 | 本机没有 WSL/Docker；规范要求 Linux CI 与 Linux 真实演练 | CI 配置已写好（`.github/workflows/ci.yml`，未推送、未启用）。请决定：推到私有仓库跑 CI，还是安装 WSL |
| P3 | Python 3.10 真实测试 | 本机只有 3.12 / 3.14 | 用静态检查兜底：`validate_skill` 以 3.10 语法解析运行时、禁止 3.11+ 接口、只允许标准库导入；安装 3.10 需用户同意 |

操作步骤（用户可自行处理 P1）：

1. 修复 Claude Code CLI：在终端运行 `node "%APPDATA%\npm\node_modules\@anthropic-ai\claude-code\install.cjs"`，或 `npm install -g @anthropic-ai/claude-code` 重装；之后 `claude --version` 应能输出版本号。
2. 或者激活 OpenCode Go 订阅，或明确同意用哪个 OpenCode 模型做含成人内容的试玩。

## 阶段记录

### 阶段 0：仓库与 Skill 外壳 —— 完成

`spec/DELIVERY_PLAN.md` 阶段 0 第一条（新建空仓库、放入 `spec/`、写根目录说明文件）已由上一个会话完成：独立 Git 仓库 `D:\projects\adult-tension-v2`（分支 `main`）；`spec/` 已放入并与原蓝图逐字核对；根目录 `AGENTS.md`、`CLAUDE.md`、`ENVIRONMENT.md`、`.gitattributes`（`* text=auto eol=lf`）。

本会话完成的其余部分：

- `git rev-parse --show-toplevel` → `D:/projects/adult-tension-v2`，不在 worktree 中。
- 提交 `ed811cd`：只含 `spec/` 与根目录四个文件；随后按 `spec/AGENTS.md` 顺序通读全部规范。
- `.gitignore`（`.claude/`、`.venv/`、`.pycache/`、`__pycache__/` 等）；`.github/workflows/ci.yml`（Windows + Linux × Python 3.10 / 3.12，跑 AC §1 前 7 条；未启用，见 P2）。
- 目录按 `ARCHITECTURE.md` §2：`skill/adult-tension/`、`content-src/`、`tools/`、`tests/{core,content,integration,e2e}/`、`reports/`。
- Skill 目录：`SKILL.md`（只写已实现的自检能力）、`agents/openai.yaml`、`references/commands.md`（生成）、`references/troubleshooting.md`、`scripts/adult_tension.py`、`runtime/adult_tension/`、`content/index.json`（空世界列表）。
- 入口脚本：只用旧语法（静态检查禁止 f-string、注解、海象运算符）；版本 < 3.10 输出 `RUNTIME_UNSUPPORTED` 信封（纯 ASCII，退出码 20）；按自身路径找到 `runtime/`。
- 运行时：严格 JSON（重复键带路径、拒绝 NaN/Infinity、容忍 BOM、非 UTF-8 报错）；声明式形状校验（未知字段、缺字段、类型、范围不截断、布尔不是整数、一次收集全部错误）；信封以 UTF-8 字节写 stdout；退出码 0/10/20/30；未预期异常转 `INTERNAL_ERROR` 并写日志编号。
- 数据目录：`--data-dir` > `ADULT_TENSION_HOME` > 平台默认；拒绝 Skill 目录内部；真实写入探测；不可写时 `DATA_DIR_UNAVAILABLE` 附尝试过的路径、原因与建议，不退回临时目录。
- SQLite：WAL、`synchronous=FULL`、`busy_timeout=2000ms`、`BEGIN IMMEDIATE`；schema v1 全部表；迁移在单事务中执行，已有数据库先备份，失败回滚并恢复备份（`MIGRATION_FAILED`）；数据库版本更新时 `UNSUPPORTED_VERSION` 且不修改数据库。
- `doctor`：python、data_dir、sqlite、migrations、skill_files、content 六项，每项 ok/warn/fail + 人话 + 建议；成功后写 `version.json`；同版本、同 Skill 根目录、同 Python、内容文件未变时走快速路径。`version`。
- 工具：`tools/validate_skill.py`、`tools/gen_references.py`（`--check`）、`tools/benchmark.py`、`tools/install_skill.py`、`tools/evidence_stage0.py`。

执行过的命令与结果（提交 `feb2f0f` 之后的工作区，阶段收尾复跑）：

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests/core` | 0 | 18 个测试，0.10 s |
| `python -m unittest discover -s tests/content` | 0 | 2 个测试 |
| `python -m unittest discover -s tests/integration` | 0 | 12 个测试，2.5 s |
| `python tools/validate_skill.py skill/adult-tension` | 0 | OK；`SKILL.md` 2675 字节 |
| `python skill/adult-tension/scripts/adult_tension.py doctor --json` | 0 | `status: warn`（还没有世界包），默认数据目录 `%LOCALAPPDATA%\adult-tension` |
| `verify-content`、`smoke` | — | 阶段 0 尚不存在（阶段 1 起必须跑通） |
| `python tools/benchmark.py --json` | 0 | 见下表；原始报告 `reports/benchmarks/stage0.json` |

冷进程基准（Windows 11 10.0.26340，Intel Core i5-14600KF，MSI MS-7D42，Python 3.12.10，SQLite 3.49.1，每项 50 次）：

| 操作 | P50 | P95 | 最大 | 门槛（P95） |
|---|---|---|---|---|
| 第一次 `doctor`（全新数据目录，含初始化与编译） | 196.1 ms | 204.2 ms | 210.9 ms | < 1500 ms |
| 之后的 `doctor`（快速路径） | 59.8 ms | 62.4 ms | 89.1 ms | < 400 ms |
| `version` | 51.6 ms | 53.5 ms | 54.3 ms | < 400 ms |

退出证据：

- `doctor` 三种情况：`reports/stage0/doctor-fresh.json`（exit 0，完整检查）、`doctor-unwritable.json`（icacls 拒写的真实目录，exit 20，`DATA_DIR_UNAVAILABLE`）、`doctor-initialized.json`（exit 0，`fast_path: true`）。
- 旧解释器：本机没有 3.8/3.9，**用测试模拟**——在子进程里把 `sys.version_info` 改成 3.9.18 / 3.8.10 后运行入口脚本，得到 `RUNTIME_UNSUPPORTED`（exit 20），见 `tests/core/test_entry_and_io.py::VersionGateTest` 与 `reports/stage0/old-python.json`；另有静态检查保证入口脚本能被旧语法解析。
- 真实宿主：OpenCode 1.18.29 + `opencode/big-pickle`，玩家输入“看看 Adult Tension 能不能用”，宿主用 `skill` 工具加载被测 Skill 并调用 `doctor`，记录见 `reports/host/stage0/`。Claude Code 因 CLI 损坏未能测试（P1）。

追溯（`TRACEABILITY.md` §2 中阶段 0 的行）：

| 需求 | 证据 |
|---|---|
| 自包含、可被发现的 Skill 目录 | `tools/validate_skill.py`；`reports/host/stage0/`（宿主经 `skill` 工具发现并加载） |
| Python 3.10+，只用标准库 | `VersionGateTest`（模拟）；`validate_skill` 的 3.10 语法、标准库导入与 3.11+ 接口检查；Linux CI 待 P2 |
| 数据目录与程序目录分离；首次初始化；`doctor` | `tests/integration/test_cli_doctor.py`（全新、快速路径、不可写、被文件挡住、位于 Skill 内、环境变量、内容被篡改、数据库版本过新、首次迁移失败）；`reports/stage0/`；基准数字 |
| 中文输入输出与编码 | `test_fresh_then_initialized_data_dir` 断言 stdout 为 UTF-8 字节（控制台代码页为 cp936）；输入侧在阶段 1 用 `new-game`/`commit-turn` 覆盖 |
| 规则只有一个权威位置 | `validate_skill` 检查 `references/commands.md` 与代码一致 |
| 仓库卫生 | `.gitattributes`；`validate_skill` 禁止文件清单（缓存、测试、源文件、用户数据）；CI 待 P2 |

遗留：P1、P2、P3；`references/narrative.md`、`operations.md`、`worlds.md` 在阶段 1 随玩法加入。

## 规范冲突与选择

| # | 冲突 | 暂行选择 | 理由 | 状态 |
|---|---|---|---|---|
| C1 | 追溯事实能否给 NPC 追加知情：`NARRATIVE_RULES.md` §2【引擎】“不得为 NPC 追加同意、好感或知情”、`ACCEPTANCE.md` §2“追溯不能给 NPC 追加知情”；`DATA_CONTRACTS.md` §5.1 允许“玩家明确说明对方知道，且不涉及同意、好感”时例外 | 按优先级取 `NARRATIVE_RULES.md`：追溯事实的 `known_by` 不能含 NPC。“其实我早就认识她”记为玩家角色的背景事实，她记不记得由 NPC 与剧情决定 | NR 优先于 DC；也更符合“玩家不能替 NPC 决定”的主权规则 | 请用户确认（阶段 3 实现追溯时生效） |

## 设计替代与自主决策

- **可选输入只从 `--input-file` 读取**（`--input-file -` 表示 stdin）；必填输入在没有 `--input-file` 且 stdin 不是终端时读 stdin。理由：无输入命令若默认读取 stdin，遇到宿主保持打开却不写入的管道会卡死；语义不变。
- **退出码**：0 成功；10 输入与领域错误；20 环境错误；30 内部错误。避开 Python 自身的 1（未捕获异常）与 2（参数错误）。
- **新增错误码** `MIGRATION_FAILED`（迁移失败并已恢复备份，归入环境错误）。
- **信封里的 `next_request_id`**：成功时在 `data` 里，失败时在 `error` 里，保持信封只有 `ok/data/error` 三个键。
- **字节码缓存**：入口脚本先禁止写字节码，启动器把 `sys.pycache_prefix` 指到数据目录 `cache/pycache/`，Skill 目录保持无缓存，冷启动仍能用缓存。
- **`doctor` 快速路径的失效判断**用内容文件的大小与修改时间（缓存失效条件，不是 D9 禁止的哈希锁，也不阻止任何修改）。
- **测试框架**：标准库 `unittest`，不引入第三方开发依赖（避免安装软件）。测试目录各有 `_bootstrap.py`；共享工具在 `tests/helpers/`。
- **schema 纪律**：默认数据目录已被初始化，此后任何数据库结构变化都通过新的迁移完成，不再修改 v1。
- **真实宿主测试隔离**：测试项目 `D:\projects\at-host-test\` 独立 `git init`；启动宿主时用 `ADULT_TENSION_HOME` 指向测试项目内的数据目录；`SKILL_PACKAGING.md` §9 的发布演练再用默认数据目录。

## 默认值调整

（暂无）

## 缺陷记录

（暂无）
