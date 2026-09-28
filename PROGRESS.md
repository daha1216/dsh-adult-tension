# PROGRESS

本文件记录 Adult Tension 全量重写的执行进度。需求来源只有 `spec/`（只读）；本机约束见 `ENVIRONMENT.md`。

## 当前状态

- 当前阶段：阶段 5（内容工具与六个世界）
- 下一步：`new-world` 脚手架与 `preview-openings` → 按 `CONTENT_BIBLE.md` 补齐其余五个世界（每个达到 §3 下限，过多样性门禁）→ 自定义世界（`custom_world` 校验与开局）→ 120 个固定种子开局 → 跨世界近似重复与时代扫描

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

阶段 4 要求的真实宿主记录（存档 → 换新版本 Skill 目录并迁移 → 新对话续玩），P1 解决后我用无头命令执行；也可以手动做：

1. 建测试项目 `D:\projects\at-host-test\`，把**阶段 3 提交**（`2aa58c8`）的 Skill 目录复制到其中的 `.claude\skills\adult-tension\`（`git -C D:\projects\adult-tension-v2 archive 2aa58c8 skill/adult-tension` 可以取出那一版）。
2. 在测试项目里开新对话，说“开一局，日常”，推进 3 个回合（其中一个说“继续”），再说“存档 夜班”，关闭对话。
3. 用当前版本的 `skill\adult-tension\` 整个替换测试项目里的 Skill 目录（数据库会从 schema 2 迁移到 3，并在数据目录的 `backups\` 留下备份）。
4. 开新对话说“读档 夜班”，确认人物、地点、未决动作接得上，再推进 1 回合。
5. 把对话记录与数据目录里的 `backups\` 列表交给我，我整理进 `reports/host/stage4/`。

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

### 阶段 1：单世界垂直切片 —— 自动化部分完成（提交 `f33352b`）；真实宿主试玩待 P1/P4

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

### 阶段 2：人物、知识、关系与安全 —— 自动化部分完成（提交 `7125655`）；真实宿主试玩待 P1

做了什么：

- **新操作**（`domain/ops_people.py`，注册进同一张操作表）：`reveal_fact`（只沿关系边；当面告知双方都在场；内心事实永不传播；告诉真相时纠正同键误信并在 `applied.corrected` 里报告信息集变化）、`spread_rumor`（生成新的假事实，来源 `rumor`，原事实不变；无渠道时沿关系边且在场，经走样渠道可达没有关系边的人，精确渠道不能走样）、`set_voice`（玩家要求 > 已激活 > NPC 自主 > 默认；NPC 自主切入里层必须有触发因素，`alone` 与 `drunk` 由引擎核对；语态与关系变化不能共用原因）、`intimacy_evidence`（同项同方向 2 个不同回合、界线放宽 3 个，同回合只算一次，数值不截断）、`identity_update`、`npc_update`、`introduce_character`（成年检查、按层级补齐字段、名字取自名字池、重要人物不同姓、世界与已有 ID 不复用、配对偏好）、`promote_character`（只升不降、保留 ID、补齐字段、身份卡与倾向卡只创建一次）、`leverage_set`/`leverage_release`（持有方必须知道依据；玩家作为持有方需要玩家本人指令）。
- **卡片**（`domain/cards.py`）：各层级的必填字段；一次提交里同一 NPC 的身份/倾向卡最多改 2 项。
- **亲密结构检查**（`domain/turn.py`）：参与者必须写明、都是在场的成年重要角色、没有醉酒/睡着/失去意识、每个 NPC 本提交有 `partial`/`genuine` 回应或主动行动、玩家的同意只来自 `result`/`attempt` + 授权、任意两人之间没有生效中的把柄（开局时生效或本提交新建的都算，本提交才解除的仍然阻断）；不保存任何同意记录。
- **元命令**（`domain/meta.py` + 应用层）：`set-boundary`（映射标签，映射不上记为 `custom` 并保留原话）、`set-safety`（暂停、恢复时清空互动判断、“换个场景”保持暂停并开新场景）、`set-preferences`（内心可见、叙事助手、离屏推演、人称、配对偏好、玩家要求的语态）。三者改变 revision、不推进回合，重放幂等。
- **`status`**（`projections/status.py`）：六行人话（不露字段名与关系数值，伏笔、传闻、概率事件不进玩家的待办）、状态+（关系变化原因、承诺与期限、玩家知道的秘密、人物、谁可能出手、设置）、调试（结构化状态、最近提交、上下文体积、不变量检查）。
- `SKILL.md` 更新为 13 478 字节（边界、暂停、偏好、状态、新操作）；参考文件重新生成。假叙述者增加告知、语态、倾向证据三类回合。

执行过的命令（阶段收尾）：

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests/core` | 0 | 133 个测试，1.01 s |
| `python -m unittest discover -s tests/content` | 0 | 10 个测试，1.42 s |
| `python -m unittest discover -s tests/integration` | 0 | 17 个测试，8.38 s |
| `python tools/validate_skill.py skill/adult-tension` | 0 | OK（第一次跑出 1 处：我的临时脚本在 Skill 里留下了 `__pycache__`，已删除，见 D4） |
| `doctor` / `verify-content` / `smoke --seed 42` | 0 / 0 / 0 | `warn`（没有 released 世界）/ 0 处问题 / 通过；另跑 `smoke --turns 30` 两条各 31 回合通过 |
| `python tools/reverse_checks.py` | 0 | 反向验证 4：五处年龄检查逐一注释掉，每一处都让测试失败（`reports/reverse/age-checks.json`） |
| `python tools/benchmark.py --json` | 0 | `reports/benchmarks/stage2.json` |

基准（P95）：进程内 开局 4.4 ms、提交 3.85 ms、上下文 1.23 ms、保存 4.87 ms、读档 5.56 ms（各 200 次）；冷进程 `new-game` 92.4 ms、`commit-turn` 82.3 ms、`get-context` 70.2 ms、第一次 `doctor` 211.4 ms、之后 `doctor` 66.1 ms（各 50 次）。全部低于门槛。

追溯（本阶段的 P0 行）：

| 需求 | 证据 |
|---|---|
| 知识边界 / 信息差与误信 | `tests/core/test_people_safety.py::KnowledgeTravelTest`（沿关系边、在场、内心不传播、揭晓纠正误信、传闻是新事实原事实不变、走样渠道） |
| 关系传播（本阶段部分） | 同上；冻结时不传播在阶段 3 |
| 表层/里层语态 | `VoiceTest`（自主切换的触发、玩家要求优先、语态不改关系、原因不共用） |
| 内心可见 | `test_inner_facts_never_travel`；`SafetyTest.test_preferences_and_player_requested_voice` |
| 亲密偏好与演化 | `CardEvolutionTest`（2 回合、界线放宽 3 回合、同回合一次、逐项上限、数值不截断、身份卡逐项） |
| 身份与处境 | `test_identity_is_created_once`；把柄阻断亲密 |
| 新角色登场与升格 | `NewCharacterTest`（年龄、缺失年龄、层级字段、名字池、同姓、ID 不复用、配对偏好、升格只升不降并补齐） |
| 硬边界 / 暂停 / 同意可撤回 / 处境不是同意 | `LeverageAndIntimacyTest`、`SafetyTest`（边界 SAFETY_BLOCK、亲密标签边界、暂停阻断亲密与冲突但不阻断剧情、换个场景保持暂停、恢复清空判断、不继承同意） |
| 状态 / 状态+ | `StatusTest`（六行、无字段名与关系数值、伏笔不进待办、状态+ 只列玩家知道的事）；`MetaCommandTest` |
| 配对偏好 / 玩家角色设定 / 人称 | `test_gender_preference_applies_to_new_characters`；`PeopleTest`；`set-preferences` 的 `person` |
| 继续 / 等待 | `ModeRulesTest`（继续与等待不替玩家移动、承诺、同意；必须有可观察的变化） |

遗留：真实宿主试玩（剧本 3、6、7、8、9、10 的主干）依赖 P1；`SKILL.md` 余量约 2.9 KB，阶段 3、4 的说明要更紧凑。

### 阶段 3：时间、事件与长期记忆 —— 完成（提交 `2aa58c8`）；真实宿主试玩待 P1

做了什么：

- **结算六步**（`domain/settlement.py` + `domain/simulation.py`）：时钟（≥ 60 分钟开新场景、清空互动判断）→ 到期事件（按 `(due, id)`，概率事件用创建时的稳定坐标掷骰）→ 状态到期 → 离屏推演（按作息移动不在场的非背景角色；简短档列候选，完整档（≥ 60 分钟或跨日）指定 ≤ 3 个必须写离屏片段的重要 NPC）→ 传播（常规 0 跳、简短 1 跳、完整 2 跳、满一天 3 跳，每跳每个邻居 0.5 的确定性掷骰，只沿 NPC 之间的边，满 3 跳停止扩散）→ 请求（第 6 步把这次跨度要求的章节、转折、候选写进结算报告；最终的 `requests` 在提交末尾统一计算）。冻结时不移动、不传播、没有离屏片段，期限照常到期。
- **离屏片段** `offscreen_beat`：只能写候选或被点名的 NPC；子操作限于该 NPC 自己的行动、状态、移动、所知事实、NPC 之间的关系与消息、不涉及玩家的事件与把柄；不能牵涉玩家角色；被点名的 NPC 的片段必须写在 `advance_time` 之后，缺了提交被拒，错误附带与预览相同的 `preview`。
- **快进**：`get-context` 带 `preview_time` 在工作副本上走同一段结算，返回目标时钟、到期事件与确定性结果、状态到期、离屏移动、传播、必须写片段的 NPC（目标、所在、情绪、所知的最近 5 条事实）与候选；不改变状态。
- **转折**：压力模式第一次跨日自动给出 2–3 个类别不同的候选（每局一次）；`get-context` 带 `want_twist` 随时取候选；`twist_accept` 引用候选或玩家口述（类别 + 文本），`result`/`attempt` 模式并带授权，同一游戏日最多一次。
- **撤销、改写、追溯**：每次提交先存撤销点（提交前的状态块，保留最近 30 回合）；`undo-turn` 回到上一回合结束时（turn − 1、revision + 1、被撤销回合的日志标记已撤销、归档行删除），最多退到本次读档或开局；`replaces_turn` 在同一事务里撤销最后一个回合再应用新提交；`rewrite`（“其实……”）只允许追溯事实与 `player_update` 以及 NPC 的反应，追溯事实只能是玩家角色知道的私密真事，与任何同键事实冲突时被拒并指出是哪一条。
- **长期记忆**：每 20 回合或跨日要求章节摘要；写入时把到上一回合为止的回合摘要与已结束的事件移进归档表，状态里不再保留；超过 10 章时要求 `prologue`，把旧前情与最早 5 章合并（完整上下文给出 `prologue_merge`）；简要上下文在近期摘要不足 3 条时附上一章摘要；已归档的事件再被引用时明确报“已结束并归档”。
- **上下文深度**：上一次提交出错（记录在 `commit_failures`，不改状态）之后的第一次成功提交返回完整上下文；需要合并前情时也给完整上下文。
- **存储边界重做**（见 D6）：事实移出每回合读写的状态块，存为每条一行（`facts` 表）；领域层通过写时复制的 `FactView` 按需读取（`domain/facts.py`），提交只写本回合改动的事实，并按回合记下旧版本（`fact_journal`），撤销与改写据此回退。存档与导出仍是完整状态。
- **迁移**：数据库 schema 2（尚未发布过）一次性加入 `facts`、`fact_journal`、`commit_failures` 与三个索引，并把旧库每个会话状态块里的事实拆成行；状态格式 2（读取时在内存升级）补齐事实与事件的随机坐标、已用去重键计数、章节计数与 `requests.prologue`。阶段 2 生成的真实旧库（`tests/fixtures/db_v1/`）迁移后读档、续玩通过。
- **命令与 Skill**：新增 `undo-turn`；`get-context` 增加 `preview_time`、`want_twist`；提交增加 `prologue`；`SKILL.md` 加入快进、离屏片段、转折、撤销/改写/追溯、章节与前情的写法（15 622 字节）；参考文件重新生成。
- **工具**：`tools/simulate.py`（两条 300 回合模拟与增长测量）；`tools/reverse_checks.py` 增加 `time` 组；假叙述者按“谨慎的模型”行事（时间放第一个、先预览、为被点名的 NPC 写片段、按要求写章节与前情、接受转折、追溯），并能产生 7 种必被拒的提交。

执行过的命令（阶段收尾）：

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests/core` | 0 | 161 个测试，1.6 s |
| `python -m unittest discover -s tests/content` | 0 | 10 个测试，1.6 s |
| `python -m unittest discover -s tests/integration` | 0 | 23 个测试，14.4 s |
| `python tools/validate_skill.py skill/adult-tension` | 0 | OK，`SKILL.md` 15 622 字节 |
| `adult_tension.py verify-content --json` | 0 | 0 处问题；20 个固定种子开局通过；多样性全部通过 |
| `adult_tension.py smoke --turns 30 --json` | 0 | 日常、压力各 31 回合；重放、过期 revision、被拒提交、存读档（见 D9） |
| `python tools/reverse_checks.py` | 0 | `age` 组 5 处、`time` 组 5 处（必需离屏片段、撤销回退事实、追溯不加知情、结算顺序、章节归档）逐一关掉，每一处都让测试失败（`reports/reverse/`） |
| `python tools/benchmark.py --json` | 0 | `reports/benchmarks/stage3.json` |
| `python tools/simulate.py --turns 300 --cold 50 --out reports/simulate/stage3.json` | 0 | 两条模拟全部门禁通过，见下 |

基准（P95；Windows 11，i5-14600KF，Python 3.12.10，SQLite 3.49.1）：进程内 开局 7.18 ms、提交 6.62 ms、上下文 1.44 ms、保存 11.99 ms、读档 22.75 ms（各 200 次）；冷进程 `new-game` 94.5 ms、`commit-turn` 85.8 ms、`get-context` 78.1 ms、第一次 `doctor` 225.2 ms、之后 `doctor` 68.2 ms（各 50 次）。全部低于门槛。保存与读档比阶段 2 慢（4.87 → 11.99 ms、5.56 → 22.75 ms），因为它们要完整读出或写入全部事实行与归档行，随局长增长；见遗留。

两条 300 回合模拟（`reports/simulate/stage3.json`；回合号把开局算作第 1 回合，两条路线都在最后一次读档后再跑 10 回合）：

| 项 | 压力（种子 7301） | 日常（种子 7302） |
|---|---|---|
| 不变量违反 | 0 | 0 |
| 注入的非法提交被拒 / 被拒后状态不变 | 44/44 / 是 | 44/44 / 是 |
| 撤销后重做，随机结果相同 | 12 次全部相同 | 12 次全部相同 |
| `replaces_turn` 原子完成 | 8 次 | 8 次 |
| 第 100/200/300 回合存读档续跑，最终状态摘要与不中断路线一致 | 一致（`c10254862d24358d…`） | 一致（`3634eeb5db2778b9…`） |
| 简要上下文：第 10 / 第 300 回合（比值） | 3 004 / 1 691 B（0.56） | 2 473 / 1 924 B（0.78） |
| 简要 / 完整上下文最大值 | 3 198 / 18 426 B | 2 910 / 17 925 B |
| 提交 P95 第 10 / 第 300 回合，进程内（比值） | 4.34 / 4.78 ms（1.10） | 5.62 / 6.30 ms（1.12） |
| 提交 P95 第 10 / 第 300 回合，冷进程（比值） | 91.5 / 97.9 ms（1.07） | 89.7 / 86.7 ms（0.97） |
| 章节 / 状态内章节 / 前情 | 26 / 6 / 有 | 29 / 9 / 有 |
| 接受的转折 | 5 | 6 |

会话快照体积（每回合读写的状态块 JSON / 压缩后；事实行）：压力 第 10 回合 14 542 / 5 753 B，11 条；第 100 回合 17 312 / 6 181 B，62 条；第 300 回合 17 805 / 6 176 B，290 条（59 877 B）。日常 13 164 / 5 255 B，10 条；19 103 / 6 187 B，61 条；18 075 / 6 080 B，272 条（56 281 B）。状态块在章节达到上限后不再增长；事实行增长，但不参与每回合的读写。

增长测量的做法：第 10 与第 300 回合各复制一份数据库，在同一进程里轮流各取一个样本（提交后撤销，每点 200 次；冷进程每点 50 次）；只比较普通回合，第 300 回合恰好要写章节或前情时，先单独测这次整理性提交（压力模式：合并前情，P95 4.58 ms），再推进到下一个普通回合测量（报告里写明实际回合与提交的操作）。

退出证据：

- `ACCEPTANCE.md` §2“时间与随机”：结算顺序（`test_time_memory.py::SettlementOrderTest`，一个跨一整天的推进同时触发六步并逐步核对）；快进预览与提交一致（`ServiceTimeTest.test_fast_forward_preview_matches_the_commit_exactly`、`TimeCommandsTest`）；同一种子与命令跨进程同一摘要（`test_same_seed_and_commands_in_separate_processes_give_the_same_state`、`LongRouteTest`；跨平台待 P2）；撤销后重做与读档不重掷（`test_undo_then_redo_and_load_repeat_every_random_result`、模拟 24 次）；种子复现与 `NO_MATCH`（阶段 1 的 `DeterminismTest`、`ConstraintTest`）；转折（`TwistTest`）。
- requests 规则：章节摘要缺失被拒、未要求时被拒、前情（`ChapterTest`）；离屏片段缺失被拒并附预览、写在推进之前被拒（`OffscreenTest`）。
- 两条 300 回合模拟通过；体积与增长门槛满足；第 300 回合提交 P95 不超过第 10 回合的 1.5 倍（进程内与冷进程都满足）。

追溯（本阶段的 P0 行）：

| 需求 | 证据 |
|---|---|
| 撤销 | `ServiceTimeTest.test_undo_restores_facts_and_stops_at_the_floor`、`test_undo_after_load_stops_at_the_loaded_turn`、`RestoreTest`（玩家设置保留、ID 不复用）；CLI 的撤销与重放 |
| 改写上一回合 | `test_rewrite_replaces_the_last_turn_in_one_commit`、`test_a_failed_rewrite_leaves_the_last_turn_as_it_was`；模拟 16 次 |
| 追溯设定 | `RetconTest`（只补玩家知道的私密真事、不给 NPC 知情好感同意、同键冲突点名、只由玩家发起） |
| 快进 | 预览一致的两处测试；`SKILL.md` 快进流程 |
| 离屏推演 / 离屏片段 / 冻结 | `OffscreenTest`（分档、候选、必需、只写本人、冻结） |
| 事件与承诺、概率事件 | 阶段 1 的 `EventsTest`；结算顺序测试；撤销重做与读档不重掷 |
| 中期转折 | `TwistTest`；`want_twist` 测试 |
| 章节摘要与长期记忆 | `ChapterTest`；模拟中 26/29 章、前情合并、上下文体积 |
| 确定性随机 | 跨进程摘要测试；模拟中两条路线摘要一致 |

遗留：

- 真实宿主试玩（剧本 5、11、12、16 的主干）依赖 P1。
- 存档与读档的耗时随局长增长（要完整读写事实行与归档行）；阶段 4 改为在库内按行复制，并测量第 300 回合的存读档。
- `SKILL.md` 余量约 760 字节；阶段 4 加入导出、续玩说明时需要继续压缩。
- 跨平台（Linux）的状态摘要一致待 P2。

### 阶段 4：存档、会话与升级 —— 自动化部分完成（提交 `8accaf3`）；真实宿主记录待 P1

做了什么：

- **存档改为行复制**（数据库 schema 3）：存档槽像会话一样存放——每回合状态块与内容快照在 `slots`，事实在 `slot_facts`，归档在 `slot_archive`。存档与读档都在 SQLite 内复制行，不再经过 Python 解码和重新编码；旧存档的事实和归档在迁移时拆成行。
- **快速存档、另存为、槽冲突**（阶段 1 已有）补齐测试：`exists` 需要 `overwrite`；本局当前槽在别处被覆盖时报 `changed_elsewhere`。覆盖存档不会清掉别的会话对这个槽的引用（D15）。
- **`delete-slot`**（P1）：必须带 `confirm: true`；删除后，以它为当前槽的会话不再有当前槽。
- **`list-sessions`**：按最近一次写入排序（新增的活动序号，D17），给出世界、回合、时钟（按该世界的时钟风格）、最近摘要、未决动作、是否暂停、当前槽与未存档回合数，供“继续上次 / 恢复”使用。
- **导出与导入**：`export-save` 把会话或存档写成交换文件（完整状态含全部事实、内容快照、归档、来源），带对整份文件（除校验值外）的 sha256；默认写到数据目录的 `exports/`，玩家给出的路径必须是 Skill 目录以外、没有 `..` 的绝对 `.json` 路径，已存在的文件要 `overwrite`，写入是原子的。`import-save` 接受路径或粘贴的 JSON：先查格式、版本（更新 → `UNSUPPORTED_VERSION`）、随机算法版本、校验值，再对状态做**完整检查**（新模块 `domain/state_check.py`：各层字段必填/可选、未知字段、类型、引用、不变量），对内容快照跑世界包校验，对归档查格式；任何问题都不写入。较旧的文件先把原件复制到 `backups/` 再在内存里升级。成功后得到新会话，可同时写入存档槽。
- **调试视图**：结构化状态（每回合状态块全文，事实给数量、扩散中的与最近 20 条）、状态摘要、最近提交、上下文体积、完整状态检查结果，以及存储信息（版本、来源、撤销深度、归档与回合记录行数、最近一次失败的提交、数据目录）。
- **CLI**：信封的序列化移进错误处理之内，结果无法写成 JSON 时也返回带日志编号的 `INTERNAL_ERROR`，不会在 stdout 上什么都没有（D13）。
- **内容在加载时校验**：运行时第一次加载一个世界包时跑世界包校验，编译产物被改动时 `doctor` 与开局都报 `CONTENT_ERROR` 并指出位置（D14）；`verify-content` 读未校验的原文自行报告。
- **Skill 与文档**：`SKILL.md` 加入续玩、“恢复”的三选一、导出、导入、删除存档（15 745 字节）；`references/troubleshooting.md` 加入升级、导出导入与卸载（清除数据是单独的、需要玩家确认的操作）；参考文件重新生成。
- **工具**：`tools/fault_drills.py`（§10 七项故障演练，经真实入口脚本）；`tools/reverse_checks.py` 增加 `cli` 组（`ACCEPTANCE.md` §7 第 1、2、3、5 项）；`tools/simulate.py` 增加第 10 / 300 回合存读档耗时；`tools/make_db_fixture.py` 可指定回合数，生成了 schema 2 的真实旧库 `tests/fixtures/db_v2/`（26 回合，含撤销点、事实日志、归档与存档）。

执行过的命令（阶段收尾）：

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests/core` | 0 | 171 个测试，2.3 s |
| `python -m unittest discover -s tests/content` | 0 | 10 个测试，1.9 s |
| `python -m unittest discover -s tests/integration` | 0 | 28 个测试，18.3 s |
| `python tools/validate_skill.py skill/adult-tension` | 0 | OK，`SKILL.md` 15 745 字节 |
| `adult_tension.py smoke --turns 30 --json` / `verify-content --json` | 0 / 0 | 两条各 31 回合通过 / 0 处问题 |
| `python tools/reverse_checks.py` | 0 | `age` 5 处、`time` 5 处、`cli` 4 项全部按预期失败（`reports/reverse/`） |
| `python tools/fault_drills.py` | 0 | 七项全部符合期望（`reports/stage4/fault-drills.json`） |
| `python tools/benchmark.py --json` | 0 | `reports/benchmarks/stage4.json` |
| `python tools/simulate.py --turns 300 --cold 50` | 0 | `reports/simulate/stage4.json`，全部门禁通过，状态摘要与阶段 3 相同 |

故障演练（`SKILL_PACKAGING.md` §10；每项之前先存档，之后用正常进程确认存档能读、能玩）：

| 演练 | 实际结果 |
|---|---|
| Python 版本过低（模拟 3.9.18） | exit 20，`RUNTIME_UNSUPPORTED`，写明需要 3.10，提示换用哪个解释器；数据库字节不变 |
| 数据目录不可写（已有存档的目录被拒写） | exit 20，`DATA_DIR_UNAVAILABLE`，附路径与建议；数据库字节不变 |
| 编译后的内容删掉一个被引用的地点 | `doctor` exit 10，`CONTENT_ERROR`，逐条指出引用它的位置；篡改前开的局照常提交成功 |
| 数据库 schema 比 Skill 新（99） | exit 20，`UNSUPPORTED_VERSION`，提示升级；数据库字节不变 |
| 迁移中途失败（注入，真实 schema 2 旧库） | exit 20，`MIGRATION_FAILED`，`restored: true`，全部表内容与迁移前一致；下一次正常运行迁移成功并读档 |
| 写事务期间进程被杀 | exit 137 且无半写入；revision 停在 4；同一请求重交后成功（revision 5） |
| 两个进程同时提交同一会话 | 一个成功，另一个 `STALE_REVISION`；revision 只前进一次 |

基准（P95；各 200 / 50 次）：进程内 开局 9.87 ms、提交 6.93 ms、上下文 1.50 ms、保存 14.39 ms、读档 17.90 ms；冷进程 `new-game` 162.5 ms（P50 93.3 ms）、`commit-turn` 85.8 ms、`get-context` 75.9 ms、第一次 `doctor` 259.3 ms、之后 `doctor` 71.9 ms。全部低于门槛。冷进程 `new-game` 比阶段 3 多了开局前的世界包校验：新进程里导入校验模块约 18 ms、校验约 7 ms。

两条 300 回合模拟（`reports/simulate/stage4.json`）：全部门禁通过；最终状态摘要与阶段 3 相同（压力 `c10254862d24358d…`、日常 `3634eeb5db2778b9…`）；第 300 回合提交 P95 是第 10 回合的 1.07 / 0.97 倍（进程内）、0.97 / 0.96 倍（冷进程）。存读档（同一进程轮流取样，各 50 次，P50 / P95）：压力 第 10 回合 保存 1.70 / 3.05 ms、读档 6.08 / 12.42 ms，第 300 回合 保存 3.83 / 19.19 ms、读档 8.33 / 17.52 ms；日常 第 10 回合 2.89 / 9.04、7.00 / 9.26 ms，第 300 回合 5.33 / 28.41、10.10 / 24.58 ms。存档是一份完整副本，复制的行数随局长增长（第 300 回合约 290 条事实、330 条归档），但都在 SQLite 内部完成，远低于 100 ms 的门槛。

退出证据：

- `ACCEPTANCE.md` §2“存档”：`SLOT_CONFLICT`（`exists` 与 `changed_elsewhere`）→ `test_transactions.py::SaveLoadTest`；读档恢复边界、暂停、事件、冷却、语态、偏好，读档创建新会话且原存档不变 → `test_saves.py::SaveLoadRestoreTest`；导入被篡改、截断、缺字段、版本过新（以及未知字段、未成年、内容快照损坏）的文件被拒且数据不变 → `ExportImportTest`；旧 schema 自动备份、迁移失败恢复 → `test_migration.py`（schema 1 与 schema 2 两个真实旧库）与故障演练。
- `SKILL_PACKAGING.md` §10 故障演练全部符合期望（上表）。
- 真实宿主记录：**未做**，依赖 P1（手动步骤见“待决事项”）。

追溯（本阶段的 P0 行）：

| 需求 | 证据 |
|---|---|
| 命名存档 / 快速存档 / 另存为 / 冲突 | `SaveLoadTest`；`SKILL.md` 命令表 |
| 读档 | `SaveLoadRestoreTest`；读档不重掷（阶段 3 测试） |
| 续玩与“恢复” | `SessionListTest`；`SKILL.md`（一个就接上、多个列出、暂停时三选一） |
| 导出 / 导入 | `ExportImportTest`、`SavesThroughCliTest`、反向验证 7.3 |
| 调试 | `MetaCommandTest`（完整检查、摘要、存储信息、可序列化）、`SavesThroughCliTest` |
| 升级与迁移、备份、卸载说明 | `test_migration.py`、故障演练、`references/troubleshooting.md` |
| 错误可识别且不损坏存档 | 故障演练 |

遗留：

- 真实宿主记录（存档 → 升级 → 新对话续玩）依赖 P1。
- 存档与读档随局长线性增长（复制行）；第 300 回合 P95 在 30 ms 以内。
- `SKILL.md` 余量约 640 字节；阶段 5 加自定义世界的说明时需要继续压缩。

## 规范冲突与选择

| # | 冲突 | 暂行选择 | 理由 | 状态 |
|---|---|---|---|---|
| C1 | 追溯事实能否给 NPC 追加知情：`NARRATIVE_RULES.md` §2【引擎】“不得为 NPC 追加同意、好感或知情”、`ACCEPTANCE.md` §2“追溯不能给 NPC 追加知情”；`DATA_CONTRACTS.md` §5.1 允许“玩家明确说明对方知道，且不涉及同意、好感”时例外 | 按优先级取 `NARRATIVE_RULES.md`：追溯事实的 `known_by` 不能含 NPC。“其实我早就认识她”记为玩家角色的背景事实，她记不记得由 NPC 与剧情决定 | NR 优先于 DC；也更符合“玩家不能替 NPC 决定”的主权规则 | 阶段 3 已按此实现（`RetconTest`）；请用户确认 |

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
- **上下文深度**：开局、读档、每 5 回合、地点变化、新角色登场、跨日、上一次提交出错、需要合并前情时给完整上下文。提交失败记在 `commit_failures` 表（不改状态、不进 revision）；数据库正忙时跳过记录，错误照常返回。
- **`identity_update` 与 `npc_update`**（新增操作）：规范要求身份卡“只能逐项演化”、其余字段“通过对应操作修改”，但没有列出操作名；这两个操作各改一项，原因必填。
- **一次提交里同一 NPC 的身份/倾向卡最多改 2 项**：落实“不允许一次重写整张卡或整体翻转”。
- **新角色的名字**：重要与次要角色的姓必须取自世界名字池，且与本局重要人物不同姓（亲属写 `kin_of`）；背景人物不限。
- **`reveal_fact` 告知假事实**：接收者加入误信名单；告知真事实时，接收者若误信同键假事实，会被移出误信名单、改为“知道这个说法不真”。
- **元命令的重复调用**：已经暂停时再暂停、登记同一句边界，返回同样的回执但不改状态（revision 不变），避免玩家重复说一遍时报错。
- **状态里的待办**只列约定、截止、机会；伏笔、风声、概率事件属于引擎与叙事，不作为玩家可见的倒计时。

- **事实的存储边界**（D6）：事实不进每回合读写的状态块，每条一行；领域层通过写时复制的 `FactView` 读取（`facts.of(state)` 统一了字典、存储来源与视图三种持有方式），提交只写改动的事实并按回合记下旧版本；存档、导出、状态摘要仍用完整状态。替代了“整份状态一个 JSON”的做法：语义不变，每回合的成本不再随局长增长；验证见模拟与 `FactStore`/撤销/改写测试。
- **撤销点**：每次提交存提交前的状态块（直接在库内复制），保留最近 30 回合；事实改动的旧版本与撤销点同步修剪。撤销保留玩家设置：边界、暂停、偏好，以及通过 `set-preferences` 设的语态（标记 `via: meta`）；回合里 `set_voice` 的切换随回合撤销。ID 计数不回退，撤销后新建的事实、事件不会复用旧 ID；去重键计数随状态回退，所以撤销后重做同一回合仍然合法。
- **改写（`replaces_turn`）**：应用层先在同一事务里回退该回合的事实，再交给领域层；领域层失败则整个事务回滚，上一回合原样保留。
- **“其实……”回合的操作白名单**：`add_fact`（必须是追溯）、`player_update`、`npc_action`、`npc_state`、`enter_scene`、`exit_scene`、`advance_time`、`offscreen_beat`；必须带玩家授权，且至少一条追溯事实或 `player_update`。规范说“只允许追溯事实与 `player_update`，其余操作按继续的规则处理”，白名单把“继续规则下不会给 NPC 追加知情、好感、同意”的那部分落成结构检查。
- **追溯事实的形状**：必须为真、私密、`known_by` 只有玩家角色、不扩散；与任何同键事实（真或假）冲突都拒绝。“无人知晓的环境细节”也记在玩家角色名下，这样它会出现在上下文里，不会被遗忘。
- **提交新增 `prologue` 字段**：规范要求把最早几章合并成一段“前情”但没有给字段；超过 10 章时要求合并最早 5 章（连同旧前情），完整上下文给出 `prologue_merge`。没有要求时写章节摘要或前情会被拒，避免模型自造章节打乱归档。
- **章节范围**：第一章从第 1 回合（开局）开始；之后每章从上一章的下一回合开始，到写摘要的前一回合为止。写摘要的那个回合属于下一章。
- **必需的离屏片段写在推进之后**：片段描述的是跳过的这段时间，所以被点名的 NPC 的片段必须在 `advance_time` 之后；默认 3 分钟推进跨过午夜也算跨日（完整档），这时提示模型在开头显式写一条 `advance_time` 再补片段。
- **离屏候选**：每次提交末尾按“下一回合”计算（不在场、不在冷却中的重要 NPC，最多 3 个，优先有待办事件的、最久没有片段的）；玩家“继续”时可写，不强制。
- **转折的授权**：`twist_accept` 需要 `result`/`attempt` 模式并带玩家授权（转折由玩家选定）；候选可从 `requests.twist_offer` 或 `want_twist` 取得，也可以接受玩家口述（类别必填）。
- **幂等记录的修剪**：`idempotency(scope)` 上建索引，按行号找第 1000 条的位置删除更早的，成本不随记录数增长（D7）。
- **存档的存放方式**（schema 3）：存档槽与会话同构（状态块 + 事实行 + 归档行），存档和读档都在库内复制。替代了“一个槽存一个完整 JSON”：语义不变（槽仍是某一 revision 的完整副本），存读档不再在 Python 里编解码整份数据。旧存档在迁移时拆成行，迁移用 schema 1、2 两个真实旧库测试。
- **导出文件格式**：规范示例的字段之外增加 `skill_version`、`source`（来自会话还是存档）与 `checksum`；`session` 里是 `state`（完整状态）、`content`（内容快照）、`archive`。校验值覆盖除它自己以外的整个文件。
- **导入的完整检查**：`domain/state_check.py` 按实际状态结构逐层列出必填与可选字段（从 300 回合模拟的真实状态中收集，并对照代码补齐只在少数路径出现的字段），未知字段一律报错；在 78 个开局、约 300 个模拟状态和两个旧库上零误报。未成年角色经不变量检查报 `SAFETY_BLOCK`，内容快照问题报 `CONTENT_ERROR`。
- **导出路径**：不给路径时写 `exports/<世界>-第N回合-<时间>.json`；给路径时必须是绝对路径、以 `.json` 结尾、不含 `..`、不在 Skill 目录里、父目录已存在，已存在的文件要 `overwrite`。
- **“最近会话”的排序**：会话表新增活动序号（有索引），每次状态写入时取全局最大值加一；时间戳只有秒级，不能用来区分同一秒内的写入（D17）。
- **内容在加载时校验**：世界包第一次加载时校验（每个进程一次，约 7 ms，另加约 18 ms 的模块导入），换来 `doctor` 与开局都能发现编译后被改动的内容；`verify-content` 用 `world_raw()` 读原文，按“世界 + JSON 路径”报告。
- **`delete-slot` 的分类**：按规范归为会话内写（带 `session_id` 与 `expected_revision`），不改变 revision。
- **状态格式与事实行**：以后若有状态格式升级要改事实的形状，必须同时写一个数据库迁移去更新 `facts` 与 `slot_facts` 里的行（读取时的内存升级只作用于每回合状态块与完整状态）。

## 默认值调整

## 默认值调整

（暂无）

## 缺陷记录

| # | 发现 | 根因 | 修复 |
|---|---|---|---|
| D1 | 开局把台风、医务室、凌晨两点签到等写死在人物组合的文本里，与抽到的活动/压力/地点矛盾（例：压力是“被扣下的外烟”，组合文本却说台风前吊最后一船） | 组合文本描述了具体场景，而组合与活动、地点是独立抽取的 | 组合文本改为只写人物之间的关系与处境；钩子去掉场所假设，必须依赖地点的钩子用 `location_ids` 限定 |
| D2 | `smoke` 的两次运行复用了同一批 `request_id` 与存档名 | 测试脚本的计数器按运行重置 | 请求号与存档名按模式区分；引擎当时正确返回了 `IDEMPOTENCY_CONFLICT` 与 `SLOT_CONFLICT` |
| D3 | 反向验证 4 第一次运行：注释掉“登场年龄”“亲密参与者年龄”“内容校验年龄”三处检查后测试仍然通过 | 前两处被不变量兜底网以另一个路径拦下，测试只断言了错误码；第三处没有测试 | 测试改为断言各自检查的错误路径，并补了内容校验的年龄测试；复跑五处全部让测试失败 |
| D4 | `validate_skill` 报 Skill 运行时目录里有 `__pycache__` | 我的一次临时预览脚本没有设置字节码缓存目录 | 删除缓存；之后的临时脚本都设置 `PYTHONPYCACHEPREFIX`；`validate_skill` 的这条检查本身工作正常 |
| D5 | 状态六行把远期伏笔连同倒计时列进了“压力与待办” | 待办取了所有涉及玩家的事件 | 只列约定、截止、机会，并补测试 |
| D6 | 第一次跑 300 回合模拟：第 300 回合的提交 P95 是第 10 回合的 3.58 倍（压力）/ 2.34 倍（日常），门禁失败 | 每次提交都要完整解码、复制、编码、压缩整份状态；事实永不删除，状态从 17.5 KB 长到 87 KB，提交成本随局长线性增长 | 不做局部提速，重做存储边界：事实存为行、写时复制视图、按回合记录旧版本（见“设计替代”）。改后同一测量降到 1.91 / 1.82 倍，状态摘要与改造前逐字一致 |
| D7 | 剖析发现幂等记录的修剪语句在第 300 回合慢 4 倍 | `NOT IN (… ORDER BY rowid DESC LIMIT 1000)` 每次读整个作用域 | 按索引定位第 1000 条后删除更早的 |
| D8 | 修完 D6、D7 后比值仍是 1.8 倍 | 测量本身有两处混杂：第 300 回合那次恰好是合并前情的整理性提交（多写 6 行归档、返回完整上下文），不是普通回合；两个点在不同时刻测，前者在进程刚启动时、后者在跑完 300 回合后 | 两个点各复制一份数据库，同一进程里轮流取样；只比较普通回合，整理性提交单独测并报告；另加冷进程测量。结果 1.10 / 1.12（冷进程 1.07 / 0.97）。最初的失败数字保留在本条 |
| D9 | Skill 自带的 `smoke` 报“被拒的提交改变了状态” | 比较的是两次读出的状态对象，事实来源是不同实例；同时发现没有任何测试运行 `smoke` | 改为比较状态摘要；新增 CLI 测试运行 `smoke --turns 30` 并检查每一步 |
| D10 | 长局里假叙述者重复提交已生效的倾向证据，被引擎拒绝 | 叙述者每次都写同一个值 | 叙述者只写卡片上还没有的值（都有时写移除）；引擎行为正确 |
| D11 | 写在 `advance_time` 之前的离屏片段也能满足“必须有片段”的要求 | 必需检查只看“本提交有没有这个 NPC 的片段” | 只认推进之后的片段，之前的给出专门的错误；反向验证覆盖 |
| D12 | 提交后发现迁移测试以读写方式打开仓库里的旧库样本（WAL 库，打开时在样本目录生成临时的 -wal/-shm 文件） | 辅助函数对样本和临时副本用了同一个连接方式 | 样本改用 `immutable=1` 只读打开；样本文件本身未被改动（修改时间与 git 状态均未变） |
| D13 | 经 CLI 调“调试”时进程崩溃，stdout 上没有信封（阶段 3 的回归） | 调试视图直接返回状态对象，事实来源不能写成 JSON；CLI 在错误处理之外序列化信封；测试只在内存状态上测过状态投影 | 调试视图只输出数据；信封在错误处理之内序列化，失败即 `INTERNAL_ERROR`；新增 CLI 测试与注入测试 |
| D14 | 故障演练 3：删掉编译后内容里一个被引用的地点，`doctor` 仍报成功 | 内容检查只确认世界文件能解析 | 加载世界包时运行世界包校验（见“设计替代”） |
| D15 | 覆盖别人的存档后，另一个对话再快速存档没有得到 `changed_elsewhere` | 我让覆盖时顺手清除所有会话对这个槽的引用 | 只有明确删除才清除引用；原有测试捕获 |
| D16 | 引入活动序号后，基准的提交 P50 从约 2.6 ms 升到 10 ms | `MAX(activity)` 没有索引，每次写入都扫描整个会话表（含大字段） | 加索引；同样负载复测 P50 2.4 ms |
| D17 | 新测试发现 `list-sessions` 顺序不对 | 按秒级 `updated_at` 排序，同一秒内的写入无法区分 | 改用活动序号 |
