# 端到端评测（`ACCEPTANCE.md` §6）

回答一个问题：**真实的宿主和模型，通过真实安装的 Skill，能不能把这个游戏玩好。**

这套工具自己的测试不调用模型；真正的评测要在两个真实宿主上跑，属于成批消耗模型额度的操作，要用户许可（`PROGRESS.md` 待决事项 P4、P5：用户 2026-09-28 同意执行）。

## 目录

| 路径 | 内容 |
|---|---|
| `scripts/NN-*.json` | 16 条剧本：玩家会打的话，外加给机器检查用的 `expect` 标注（被测模型看不到） |
| `drills/release-drill.json` | 发布前的真实演练（`SKILL_PACKAGING.md` §9），格式与剧本相同 |
| `playtests/` | 世界试玩（`CONTENT_BIBLE.md` §7）：`pt-<世界>-<daily\|pressure>.json` 每个世界每种模式一条，开局后 5 回合、存档、新对话读档、再 1 回合；`pt-stage1.json` 是阶段 1 的试玩（开局 + 10 回合 + 存档 + 新对话读档）。格式与剧本相同 |
| `rubric.md` | 评分量表：8 个维度，每一档都有锚点与示例 |
| `reviewer.md` | 给独立评审的说明与输出格式 |
| `calibration/` | 校准集：6 条好的、6 条植入已知缺陷的记录，`key.json` 是答案；`build.py` 生成它们 |
| `harness/record.py` | 记录格式、给评审看的 Markdown |
| `harness/hosts.py` | 宿主驱动：Claude Code（`claude -p … --output-format stream-json`）与 OpenCode（`opencode run --format json`） |
| `harness/run_script.py` | 跑一条剧本、写一条记录 |
| `harness/machine_checks.py` | §6.2 的机器检查 |
| `harness/report.py` | 评审材料包、校准判定、最终报告 |
| `harness/review.py` | 请一个独立的模型实例评审一条记录（OpenAI 兼容接口，一次请求只含材料包，不带工具） |
| `test_harness.py` | 这套工具自己的测试（`python -m unittest discover -s tests/e2e`，不调用模型） |

## 一次运行怎么进行

`run_script.py` 为每一次运行：

1. 在本仓库之外建一个全新的测试项目（默认 `D:\projects\at-e2e\<宿主>-s<剧本>-r<次>-<时间>\`，独立 `git init`）；
2. 把 Skill 装进项目级目录 `.claude/skills/adult-tension/`（剧本 16 先装旧版，中途整目录替换为当前版）；
3. 让宿主只看这个项目自己的设置，不含任何给模型的指示：
   - Claude Code：`--setting-sources project,local --strict-mcp-config`（操作者的用户级设置、插件、MCP 不进来）；权限写在命令行（只放行运行 Python、在项目内编辑文件，禁止上网），因为没被交互信任过的工作区里，项目设置的权限规则不生效；
   - OpenCode：它的全局配置目录（`XDG_CONFIG_HOME`）、会话库（`OPENCODE_DB`）、临时目录（`TEMP`/`TMP`）都放在项目的 `.host/` 里；关掉 `~/.claude`、`~/.agents` 下的外部 Skill 扫描、`~/.claude/CLAUDE.md`、自动更新、分享、默认插件、语言服务器下载；项目的 `opencode.json` 写权限（同上）、`skills.paths: [".claude/skills"]`、`share: disabled`；
   - 由一个 Claude Code 会话启动测试时，去掉调用方自己的 `CLAUDE*`、`ANTHROPIC_*` 变量；
4. 设置 `ADULT_TENSION_TRACE`（引擎自己的调用记录）；剧本没有另说时，再设置 `ADULT_TENSION_HOME`（项目内的数据目录）。`ADULT_TENSION_INCLUDE_DRAFTS=1` 只在剧本要求时设置（`"include_drafts": true`）：六个世界都已 `released`，只有从旧版起步的剧本 16 需要它，旧版里的世界还是 `review`。宿主环境里原有的这两个变量一律先清掉；
5. 按剧本逐句发给宿主，同一个对话用同一个宿主会话；剧本里标了 `conversation` 的步骤开新对话；
6. 每一轮记下：玩家输入、宿主的工具调用、这一轮的全部运行时调用（参数、输入、返回、耗时、是哪一份 Skill 跑的）、玩家看到的全部文字。运行时调用取自引擎记录；装的是引擎记录出现之前的旧版时（剧本 16 与发布演练的升级前），改从宿主自己的工具调用里还原（命令行、写进输入文件的内容、打印出的 JSON），这一轮标 `calls_source: host`；
7. 结束后经运行时导出最终状态（不进引擎记录），连同宿主名称与版本、模型标识、日期、每次安装的 Skill 版本与数据库格式（`installs`）、最后一版的 Skill 根目录与版本写进记录；
8. 当场跑机器检查。除了 `ACCEPTANCE.md` §6.2 的各项，还核对记录本身，下面任何一种都算记录不合格：
   - 某一轮宿主没有正常结束（进程出错、超时、宿主自己报告这一轮出错），或者玩家什么也没看到。出错之前宿主做过的工具调用照样记下，便于查原因；
   - 宿主调用运行时的次数多于引擎记录的（记录没写全）；
   - 某次调用来自测试项目之外的另一份 Skill（宿主加载的不是被测版本）。

被测模型只收到玩家说的话。`expect` 标注、量表、剧本重点都不会出现在宿主那边。

**调用次数的口径**：`ACCEPTANCE.md` §5 的“工具调用”按引擎记录里的运行时调用计（`doctor`、`new-game`、`commit-turn`……）。宿主为了写临时输入文件而做的额外工具调用单独记在 `host_calls` 里，报告中另列，不计入 §5 的预算。

## 命令

先确认环境：两个宿主的命令行可用；用户级 Skill 目录里没有同名 Skill（只检查是否存在，不打开）。

跑一条剧本：

```bash
python tests/e2e/harness/run_script.py --host claude-code --script 01 --run 1
```

```bash
python tests/e2e/harness/run_script.py --host opencode --model <provider/model> --script 01 --run 1
```

两个常用参数：

- `--host-exe <路径>`：宿主程序的完整路径。Windows 上的 OpenCode 要传 npm 包里的平台二进制（`…\node_modules\opencode-ai\node_modules\opencode-windows-x64\bin\opencode.exe`）：`opencode.cmd` 经过 cmd.exe，玩家原话里的 `%` 之类会被改写。
- `--host-env-file <文件>`：宿主要用的环境变量（`KEY=VALUE`，`#` 开头是注释），例如模型接口。文件放在仓库之外；记录里的 `host_env` 列出这些变量，名字含 `KEY`、`TOKEN`、`SECRET`、`PASSWORD` 的只写“已设置”。OpenCode 用自定义接口时，可以在这里用 `OPENCODE_CONFIG` 指向一个只写 provider 的配置文件，密钥写成 `{env:变量名}`。

本机现在的跑法（OpenCode + 本地接口上的 `gemini-3.8-flash-high`，见 `PROGRESS.md` 的“真实宿主的接法”）：

```bash
python tests/e2e/harness/run_script.py --host opencode --model local-proxy/gemini-3.8-flash-high --host-exe <opencode.exe> --host-env-file <仓库外的 env 文件> --script 01 --run 1
```

世界试玩与阶段 1 的试玩（记录写在 `reports/playtests/`、`reports/host/stage1/`）：

```bash
python tests/e2e/harness/run_script.py --host opencode --model local-proxy/gemini-3.8-flash-high --host-exe <opencode.exe> --host-env-file <env 文件> --script pt-harbor_night_shift-daily --run 1 --out reports/playtests
```

剧本 16 从旧版开始：

```bash
python tests/e2e/harness/run_script.py --host claude-code --script 16 --run 1 --previous <旧版的 git 提交>
```

记录写在 `reports/e2e/records/<宿主>/`。每条剧本在每个宿主上至少跑 3 次（`--run 1`、`2`、`3`）；第 1 次就是首跑，之后的运行不替换它。

## 发布前的真实演练（`SKILL_PACKAGING.md` §9）

`drills/release-drill.json` 把 §9 的七步写成剧本：新对话说“开一局” → 选日常 → 3 个回合（其中一个是“继续”）→ 存档“演练” → 新对话读档 → 整目录替换为当前版本（从旧版 `2aa58c8` 起步，数据库从格式 2 迁移到 3，迁移前自动备份）→ 再推进 1 回合。

它和评测剧本的区别在 `setup` 里：

- `"data_dir": "default"`：不设 `ADULT_TENSION_HOME`，数据目录由运行时按平台默认位置决定——和真实用户一样，用户不做任何环境变量操作；
- `"include_drafts": false`：不开草稿开关，只有 `released` 的世界能开局。旧版 `2aa58c8` 的内容里没有 `released` 的世界，所以照这个设置，升级前的那一段永远开不了局：§9 在首个发布版之前做不到原样执行，怎么做见 `PROGRESS.md` 待决事项 P7；
- 唯一由测试框架设置的变量是引擎记录 `ADULT_TENSION_TRACE`，它只负责记录，不改变任何行为。

在干净的机器上跑（Windows 与 Linux 各一次；干净指：没有旧的数据目录、没有 `ADULT_TENSION_*` 变量、宿主的用户级目录里没有同名 Skill）：

```bash
python tests/e2e/harness/run_script.py --host claude-code --script tests/e2e/drills/release-drill.json --previous 2aa58c8 --out reports/release/drill
```

记录写在 `reports/release/drill/<宿主>/`：宿主名称与版本、模型、两次安装的版本与数据库格式、每一步的实际调用与耗时。升级前的调用来自宿主自己的记录（旧版没有引擎记录），没有单次耗时，只有整轮的耗时。演练结束后在数据目录的 `backups/` 里应当有一份 `adult_tension-schema2-*.db`。

## 评审

评审由 `review.py` 交给一个独立的模型实例：一次请求，只含评审材料包（同 `report.py packet`），不带工具。接口写在仓库之外的文件里（`REVIEW_BASE_URL`、`REVIEW_API_KEY`、`REVIEW_MODEL`）。答案不是 `reviewer.md` 要求的 JSON 时重问，最多 3 次，每次的原始答案都存进输出；三次都不合格的评审记为不可用（校准时算判错，报告里算“没有可用评审”）。

```bash
python tests/e2e/harness/review.py --record <记录.json> --out <评审.json> --endpoint-file <仓库外的接口文件>
```

1. **先校准。** 为校准集的每条记录生成材料包，交给一个全新上下文的评审（人或独立模型实例），把它输出的 JSON 存到 `reports/e2e/calibration-reviews/<记录名>.json`，然后判定：

   ```bash
   python tests/e2e/harness/report.py packet --record tests/e2e/calibration/good-1.json --out <材料包.md>
   ```

   ```bash
   python tests/e2e/harness/report.py calibrate --reviews reports/e2e/calibration-reviews
   ```

   对 12 条判对 ≥ 10 条才能开始正式评审；否则先改 `rubric.md` 的锚点。收紧锚点只能在看到下一轮结果之前做。

   评审者按接口报告的实际应答模型认（每次回答的 `served_model`），不按请求的名字：接口可能用同一个名字换着上不同的模型。一次校准只替一个模型说话，12 条要由同一个模型回答。报告只计入通过校准的模型给出的评审；换了模型的，照样列出，注明“未通过校准，不计入”。

2. **正式评审。** 每条记录生成材料包，交给全新上下文的评审；评审只拿到说明、量表、`NARRATIVE_RULES.md` 与这条记录，不看实现、不改剧本。输出存到 `reports/e2e/reviews/<宿主>/<记录名>.json`。

3. **报告。**

   ```bash
   python tests/e2e/harness/report.py build --records reports/e2e/records --reviews reports/e2e/reviews --calibration reports/e2e/calibration-reviews --fixes reports/e2e/fixes.json --out reports/e2e
   ```

   `--calibration` 给校准结果所在的目录，每个评审者一个，可以重复。

   报告给出：宿主与模型身份、评审者与各自的校准结果、首跑通过率、每个维度的分布与中位数、同一剧本多次运行之间的分布、触顶的维度（下一轮收紧）、关键维度的低分、普通回合的平均调用次数、失败记录与修复的对应（`fixes.json`：记录名 → `{"commit": …, "note": …}`）。

**通过条件**（`ACCEPTANCE.md` §6.4）：至少两个宿主；所有记录的机器检查都通过；每个维度的中位数 ≥ 4；没有任何一次运行在“玩家主权”“同意与安全”“知识边界”得 ≤ 2 分；普通回合平均调用 ≤ 1.2。

## 无头命令跑不通时

按下面的步骤手动跑一条剧本，把结果交给我整理成记录：

1. 用 `run_script.py` 的同样方式建测试项目（或手动：在 `D:\projects\at-e2e\` 下新建目录、`git init`、用 `python tools/install_skill.py <项目>\.claude\skills\adult-tension` 安装 Skill）。
2. 在终端里先设置两个环境变量再启动宿主：`ADULT_TENSION_HOME=<项目>\.at-data`、`ADULT_TENSION_TRACE=<项目>\trace.jsonl`；剧本 16 另设 `ADULT_TENSION_INCLUDE_DRAFTS=1`（从旧版起步）；发布演练只设 `ADULT_TENSION_TRACE`。
3. 开新对话，按剧本文件里 `say` 的顺序逐句输入；遇到 `harness: upgrade_skill` 时关掉对话、用当前版本替换 Skill 目录、再开对话继续；遇到 `conversation` 变化时开新对话。
4. 结束后用宿主自带的导出功能把整段对话导出到测试项目里，连同 `trace.jsonl` 一起交给我。
