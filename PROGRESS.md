# PROGRESS

本文件记录 Adult Tension 全量重写的执行进度。需求来源只有 `spec/`（只读）；本机约束见 `ENVIRONMENT.md`。

## 当前状态

- 当前阶段：阶段 2（人物、知识、关系与安全）
- 下一步：`reveal_fact`/`spread_rumor`/误信揭晓 → 语态与内心可见、倾向卡证据 → 把柄与亲密结构检查 → 登场与升格 → 边界、暂停、换个场景 → `set-boundary`/`set-safety`/`set-preferences`/`status`

## 待决事项（需要用户决定）

| # | 事项 | 现状与影响 | 暂行做法 |
|---|---|---|---|
| P1 | 真实宿主不可用 | 本机 `claude`（npm 安装）报 `claude native binary not installed`，修复需在仓库外运行 `node %APPDATA%\npm\node_modules\@anthropic-ai\claude-code\install.cjs` 或重装；OpenCode Go 订阅未激活（Go 模型 403）。阶段 1 起的真实宿主试玩、阶段 6 的两宿主评测都依赖这两项 | 阶段 0 用 OpenCode 免费模型 `opencode/big-pickle` 做了一次无成人内容的冒烟。含成人内容的试玩在用户决定宿主与模型之前不做 |
| P2 | Linux 测试方式 | 本机没有 WSL/Docker；规范要求 Linux CI 与 Linux 真实演练 | CI 配置已写好（`.github/workflows/ci.yml`，未推送、未启用）。请决定：推到私有仓库跑 CI，还是安装 WSL |
| P3 | Python 3.10 真实测试 | 本机只有 3.12 / 3.14 | 用静态检查兜底：`validate_skill` 以 3.10 语法解析运行时、禁止 3.11+ 接口、只允许标准库导入；安装 3.10 需用户同意 |
| P4 | 阶段 1 的真实宿主试玩（开局 + 10 回合 + 存档 + 新对话读档）与港口夜班的 `released` | 依赖 P1。按 `CONTENT_BIBLE.md` §7，没有真实 Skill 试玩记录的世界不能改为 `released`，所以港口夜班目前是 `review`，`doctor` 报 `warn`（没有可随机开局的世界） | 自动化部分已全部完成；试玩剧本与记录格式在 P1 解决后执行。宿主测试环境用 `ADULT_TENSION_INCLUDE_DRAFTS=1` 让 `review` 世界可开局（开发开关，不写进 `SKILL.md`） |

操作步骤（用户可自行处理 P1）：

1. 修复 Claude Code CLI：在终端运行 `node "%APPDATA%\npm\node_modules\@anthropic-ai\claude-code\install.cjs"`，或 `npm install -g @anthropic-ai/claude-code` 重装；之后 `claude --version` 应能输出版本号。
2. 或者激活 OpenCode Go 订阅，或明确同意用哪个 OpenCode 模型做含成人内容的试玩。

## 阶段记录

### 阶段 0：仓库与 Skill 外壳 —— 完成（收尾提交 `20f9683`）

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

### 阶段 1：单世界垂直切片 —— 自动化部分完成；真实宿主试玩待 P1/P4

做了什么：

- **世界包** `content-src/worlds/harbor_night_shift.json`（港口夜班，1998 年南方港城集装箱码头）：6 条世界规则、5 条风俗、姓 18 / 女名 14 / 男名 14 / 中性名 12、4 条昵称规则、6 种玩家身份（low/equal/high 各 2）、8 个地点（出口双向连通）、7 个人物模板（全部 `gender: any`，四档压力反应、退缩、作息、表里语态、倾向卡、个人处境）、7 个背景人物（5 种功能）、4 个关系渠道（2 精确 2 走样）、6 个张力引擎、8 个人物组合（四种权力结构都有）、7 个日常活动、7 个压力（五拍齐全，2 个带把柄）、11 个钩子（7 个 approach）、9 个转折（七类全覆盖）、19 个禁用词。状态 `review`（等真实试玩）。
- **内容标签表** `content-src/tags.json`（19 个：亲密三级、冲突四类、主题、场景、custom）；**编译器** `tools/compile_content.py`（严格解析、`extends` 编译期展开、校验、确定性输出、`--check`）。
- **校验器** `domain/worldpack.py`：形状（未知字段、重复键）、全部引用按 ID 解析、占位可解析、可变性别文本不许写死“他/她”、§3 下限、年龄、压力五拍与期限、把柄声明、四种权力结构、转折类别、背景功能、渠道精确/走样、地点可区分与连通、组合可开局、占位式内容、包内整句重复、禁用词、真实人物名单、校园/师生/学徒类意象需成年语境、跨包近似重复（字二元组 Jaccard ≥ 0.85，长度 ≥ 16）、通用层对全部禁用词表。
- **领域核心**（纯函数）：确定性随机（sha256 坐标派生，不含自由文本）、时钟、开局生成（锁定、排除、性别偏好、玩家设定、权力结构/组合/活动或压力/地点/钩子分层选取、身份、名字、关系边、事实、压力三层事件、把柄）、14 个操作（`advance_time`、`move`、`enter_scene`、`exit_scene`、`npc_response`、`npc_action`（冷却）、`npc_state`、`add_fact`、`relationship`（幅度、阶段证据）、`event_create`、`event_resolve`、`event_cancel`、`roll`、`player_update`）、时间结算（§6.1 顺序，后三步留好插口）、全局不变量、提交编排（全有或全无、错误一次收集、路径）。
- **唯一写路径** `application/service.py`：形状校验 → `BEGIN IMMEDIATE` → 幂等查找 → revision → 工作副本上的领域 → 同一事务写会话、回合记录、幂等记录 → 在提交前生成响应（含上下文）。
- **命令**：`new-game`（日常/压力/随机、锁定、排除、玩家设定、性别偏好、种子复现与 `replay`、近期去重）、`get-context`（brief/full）、`commit-turn`、`save-slot`（含 `exists`/`changed_elsewhere` 冲突、自动命名、覆盖）、`load-slot`、`list-slots`、`list-worlds`、`verify-content`、`smoke`。
- **投影**：简要上下文 ≤ 6 KB、完整上下文 ≤ 20 KB，列表有上限，超出按固定顺序截取。
- **参考文件**：`references/narrative.md`（由规范压缩，章节编号不变）、`operations.md`、`commands.md`、`worlds.md`（后三个由代码生成，`validate_skill` 检查一致）。`SKILL.md` 11 228 字节，只写已实现的能力；边界与暂停在阶段 2 进引擎前，要求模型在正文里照做。
- **假叙述者** `application/fake_narrator.py`（`smoke`、基准、测试共用）。

执行过的命令（阶段收尾）：

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests/core` | 0 | 93 个测试，0.86 s |
| `python -m unittest discover -s tests/content` | 0 | 9 个测试，1.30 s |
| `python -m unittest discover -s tests/integration` | 0 | 17 个测试，8.28 s |
| `python tools/validate_skill.py skill/adult-tension` | 0 | OK，`SKILL.md` 11 228 字节 |
| `python skill/adult-tension/scripts/adult_tension.py doctor --json` | 0 | `status: warn`（没有 `released` 世界，见 P4） |
| `python skill/adult-tension/scripts/adult_tension.py verify-content --json` | 0 | 0 处问题；20 个固定种子开局通过；多样性 6 组全部通过 |
| `python skill/adult-tension/scripts/adult_tension.py smoke --seed 42 --json` | 0 | 日常、压力各 8 回合 + 重放 + 过期 revision + 被拒提交 + 存读档，每条约 50 ms |
| `python tools/benchmark.py --json` | 0 | 见下表；原始报告 `reports/benchmarks/stage1.json` |

基准（Windows 11，i5-14600KF，Python 3.12.10，SQLite 3.49.1）：

| 路径 | 样本 | P50 | P95 | 最大 | 门槛（P95） |
|---|---|---|---|---|---|
| 进程内 开局（含写库与完整上下文） | 200 | 6.87 ms | 10.45 ms | 23.74 ms | < 300 ms |
| 进程内 回合提交 | 200 | 3.23 ms | 7.21 ms | 14.08 ms | < 80 ms |
| 进程内 读取上下文 | 200 | 1.55 ms | 1.92 ms | 3.11 ms | < 30 ms |
| 进程内 保存 | 200 | 4.35 ms | 9.78 ms | 14.48 ms | < 100 ms |
| 进程内 读档 | 200 | 5.17 ms | 9.83 ms | 20.08 ms | < 100 ms |
| 冷进程 `new-game` | 50 | 77.0 ms | 85.1 ms | 157.7 ms | < 800 ms |
| 冷进程 `commit-turn` | 50 | 72.0 ms | 74.9 ms | 79.2 ms | < 500 ms |
| 冷进程 `get-context` | 50 | 65.3 ms | 70.1 ms | 84.6 ms | < 400 ms |
| 冷进程 第一次 `doctor` | 50 | 188.4 ms | 192.7 ms | 193.6 ms | < 1.5 s |
| 冷进程 之后的 `doctor` | 50 | 60.0 ms | 70.3 ms | 87.8 ms | < 400 ms |

其他实测：开局时简要上下文 2.1–2.6 KB、完整上下文 14.8–16.3 KB；200 回合后会话快照压缩后 9 696 字节；`verify-content` 冷进程 0.23 s。

多样性门禁（每个世界、每种模式，用三条独立的确定性种子流各模拟 20 次连续随机开局，走与 `new-game` 相同的带历史去重的选取路径）：日常 20/20/20 种签名、压力 20/19/19 种；最低权力结构占比 0.20；玩家身份 6 种；approach 钩子占比 0.85–1.00。

退出证据：

- `ACCEPTANCE.md` §2“事务与幂等”7 条：`tests/core/test_transactions.py`（被拒提交全部不变、重放、同 ID 不同内容冲突、响应丢失后重试拿回原响应、过期 revision 附当前 revision 与上下文、幂等记录上限）；`tests/integration/test_cli_game.py`（两个进程并发提交同一 revision 四轮，每轮恰好一个成功；写事务中途 `os._exit(137)` 后 revision、回合记录、幂等记录都不变，同一请求随后正常成功）。
- 固定种子两种模式各 10 次开局通过结构校验：`tests/content/test_worlds.py::test_fixed_seed_openings_come_from_one_world`、`verify-content` 报告。
- 20 回合脚本化运行，每回合一个冷进程，第 10 回合存档、读档续跑，最终状态摘要与不中断路线一致：`tests/integration/test_cli_game.py::LongRouteTest`。
- 进程内开局与提交耗时见上表。
- 真实宿主试玩：**未做**，依赖 P1（见 P4）。

追溯（本阶段首次实现的 P0 行）：

| 需求 | 证据 |
|---|---|
| 随机开局 | `test_worlds.py`（固定种子、同一世界包的名字与地点）；`verify-content` |
| 日常 / 压力两种模式 | `test_opening.py`；`SKILL.md` 开局第 1 步（剧本 1、13 待宿主） |
| 日常模式语义 | `check_opening`：日常开局没有任何事件；`EventsTest.test_daily_mode_has_no_countdowns` |
| 压力模式语义 | `check_opening` 三层齐全、远期为伏笔；`EventsTest.test_pressure_opening_has_three_tiers` |
| 指定锁定 / 否定约束 | `ConstraintTest`（锁定、排除、`NO_MATCH` 附可放宽项） |
| 权力结构多样 | 多样性门禁（最低占比 0.20） |
| 种子复现 | `DeterminismTest`；`test_replay_restores_the_recorded_conditions` |
| 近期去重 | `RandomSeedTest`；`test_random_openings_avoid_recent_signatures`（不指定种子连开 10 局，签名全不同） |
| 自然语言行动 / 结果与尝试档 | `ModeRulesTest` |
| 场景跳转 | `PlayerAndSceneTest.test_player_move_changes_scene_and_companions_follow_when_moved` |
| NPC 决策卡、回应光谱 | 开局角色卡；`NpcRulesTest` |
| NPC 自主行动与冷却 | `NpcRulesTest.test_significant_action_cooldown`、冻结时不在场者不能行动 |
| 关系与张力（基础） | `RelationshipTest`（幅度、不截断、阶段证据、原因、玩家态度不由模型决定） |
| 事件与承诺、概率事件 | `EventsTest`（到期只结算一次、终态不可改、去重、概率确定性、日常模式无倒计时） |
| 成年人断言 | `PeopleTest`、`InvariantNetTest`、校验器年龄检查 |
| 自动保存 | 每次提交即写库；写事务被杀测试 |
| 命名存档 / 读档 / 存档列表 | `SaveLoadTest` |
| 世界列表 | `test_unreleased_worlds_need_include_drafts` |
| 内容校验 | `test_worlds.py`；反向验证 1、5 的测试 |
| 状态只有一个写入口；领域层纯净 | `test_architecture.py` |
| 严格输入 / 错误可修复 | `test_entry_and_io.py`；`EncodingAndInputTest.test_input_errors_have_json_paths` |
| 中文输入输出 | `EncodingAndInputTest`（文件、stdin、BOM；控制台 cp936） |

遗留：P1/P4（真实宿主试玩与 `released`）；反向验证 4（注释掉年龄检查）在阶段 2 年龄检查全部到位后统一做并保存输出。

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
- **`acts_on`**：提交新增可选字段，列出玩家行动作用到的 NPC。`attempt` 要么对这些 NPC 各附回应，要么写 `acts_on: []` 声明不作用于 NPC；`result` 不能作用于 NPC。理由：引擎无法从自然语言判断“目标是 NPC”，需要结构化声明才能执行 §1 的【引擎】规则。
- **表面配合的真实意图**：`npc_response` 在 `surface` 时带 `true_intent`，引擎自动生成只有本人知道的私密事实，替代“同一提交里另写一条 `add_fact`”，语义不变且更不易漏。
- **一次提交最多一个 `advance_time`**；没有时在提交末尾默认推进 3 分钟。
- **`until` 语义**：morning 07:00、noon 12:00、evening 18:00、night 21:00、next_morning 次日 07:00；取严格晚于现在的下一个时刻。
- **日常模式整局不接受 `deadline` 与 `chance` 事件**（开局也没有任何事件）：`PRODUCT_SPEC.md` 的“没有倒计时、没有到期事件”严于 `DATA_CONTRACTS.md` 的开局限制，按优先级取前者；约定、机会、伏笔、风声仍可由剧情创建。
- **事件结果新增 `surfaced`**：伏笔与风声到期或提前浮出时使用（规范列出的结果里没有对应项）。
- **关系阶段是双方共有的历史**：阶段变化同时写入两个方向的边；信任、张力仍按方向分开。玩家对别人的信任/张力只能在 `result`/`attempt` 回合变化。
- **知识的在场限制**：普通回合里，新事实的知情人必须在场（离屏得知走阶段 3 的离屏片段与传播）。
- **人物组合的 `identity_ids`** 与 **钩子的 `location_ids`**（均可选）：限定组合适合的玩家身份、钩子适用的地点，避免开局拼出不连贯的场面。
- **随机开局的去重扩展**：候选种子按惩罚分选取——最近 10 局签名重复（硬性）、与上一局同一权力结构/身份/组合、非 approach 钩子连续出现都会加分；最多试 24 个候选，全部重复时接受惩罚最低的。多样性门禁模拟的就是这条真实路径。
- **“重开 N 号”**：本机 `opening_history` 记录每个种子的开局条件；`new-game` 带 `replay: true` 时恢复这些条件；不带时 `seed` + 条件就是纯函数。
- **`include_drafts` 的开发开关**：环境变量 `ADULT_TENSION_INCLUDE_DRAFTS=1` 等同 `--include-drafts`，只由测试环境设置，不写进 `SKILL.md`。
- **上下文深度**：开局、读档、每 5 回合、地点变化、新角色登场、跨日给完整上下文；“上一次提交出错后给完整上下文”在阶段 3 实现（需要在不改变状态的前提下记录失败）。

## 默认值调整

（暂无）

## 缺陷记录

| # | 发现 | 根因 | 修复 |
|---|---|---|---|
| D1 | 开局把台风、医务室、凌晨两点签到等写死在人物组合的文本里，与抽到的活动/压力/地点矛盾（例：压力是“被扣下的外烟”，组合文本却说台风前吊最后一船） | 组合文本描述了具体场景，而组合与活动、地点是独立抽取的 | 组合文本改为只写人物之间的关系与处境；钩子去掉场所假设，必须依赖地点的钩子用 `location_ids` 限定 |
| D2 | `smoke` 的两次运行复用了同一批 `request_id` 与存档名 | 测试脚本的计数器按运行重置 | 请求号与存档名按模式区分；引擎当时正确返回了 `IDEMPOTENCY_CONFLICT` 与 `SLOT_CONFLICT` |
