# 端到端评测（`ACCEPTANCE.md` §6）

回答一个问题：**真实的宿主和模型，通过真实安装的 Skill，能不能把这个游戏玩好。**

这里的一切都不调用模型；真正的评测要在两个真实宿主上跑，属于成批消耗模型额度的操作，开始之前需要用户许可（`PROGRESS.md` 待决事项 P1、P5）。

## 目录

| 路径 | 内容 |
|---|---|
| `scripts/NN-*.json` | 16 条剧本：玩家会打的话，外加给机器检查用的 `expect` 标注（被测模型看不到） |
| `rubric.md` | 评分量表：8 个维度，每一档都有锚点与示例 |
| `reviewer.md` | 给独立评审的说明与输出格式 |
| `calibration/` | 校准集：6 条好的、6 条植入已知缺陷的记录，`key.json` 是答案；`build.py` 生成它们 |
| `harness/record.py` | 记录格式、给评审看的 Markdown |
| `harness/hosts.py` | 宿主驱动：Claude Code（`claude -p … --output-format stream-json`）与 OpenCode（`opencode run --format json`） |
| `harness/run_script.py` | 跑一条剧本、写一条记录 |
| `harness/machine_checks.py` | §6.2 的机器检查 |
| `harness/report.py` | 评审材料包、校准判定、最终报告 |
| `test_harness.py` | 这套工具自己的测试（`python -m unittest discover -s tests/e2e`，不调用模型） |

## 一次运行怎么进行

`run_script.py` 为每一次运行：

1. 在本仓库之外建一个全新的测试项目（默认 `D:\projects\at-e2e\<宿主>-s<剧本>-r<次>-<时间>\`，独立 `git init`）；
2. 把 Skill 装进项目级目录 `.claude/skills/adult-tension/`（剧本 16 先装旧版，中途整目录替换为当前版）；
3. 写项目级的权限设置（只放行运行 Python 与在项目内读写临时文件；不含任何给模型的指示）；
4. 设置 `ADULT_TENSION_HOME`（项目内的数据目录）、`ADULT_TENSION_TRACE`（引擎自己的调用记录）、`ADULT_TENSION_INCLUDE_DRAFTS=1`（世界还是 `review` 时才需要）；
5. 按剧本逐句发给宿主，同一个对话用同一个宿主会话；剧本里标了 `conversation` 的步骤开新对话；
6. 每一轮记下：玩家输入、宿主的工具调用、引擎记录里这一轮新增的全部调用（参数、输入、返回、耗时）、玩家看到的全部文字；
7. 结束后经运行时导出最终状态（不进引擎记录），连同宿主名称与版本、模型标识、日期、Skill 根目录与版本写进记录；
8. 当场跑机器检查。

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

剧本 16 从旧版开始：

```bash
python tests/e2e/harness/run_script.py --host claude-code --script 16 --run 1 --previous <旧版的 git 提交>
```

记录写在 `reports/e2e/records/<宿主>/`。每条剧本在每个宿主上至少跑 3 次（`--run 1`、`2`、`3`）；第 1 次就是首跑，之后的运行不替换它。

## 评审

1. **先校准。** 为校准集的每条记录生成材料包，交给一个全新上下文的评审（人或独立模型实例），把它输出的 JSON 存到 `reports/e2e/calibration-reviews/<记录名>.json`，然后判定：

   ```bash
   python tests/e2e/harness/report.py packet --record tests/e2e/calibration/good-1.json --out <材料包.md>
   ```

   ```bash
   python tests/e2e/harness/report.py calibrate --reviews reports/e2e/calibration-reviews
   ```

   对 12 条判对 ≥ 10 条才能开始正式评审；否则先改 `rubric.md` 的锚点。收紧锚点只能在看到下一轮结果之前做。

2. **正式评审。** 每条记录生成材料包，交给全新上下文的评审；评审只拿到说明、量表、`NARRATIVE_RULES.md` 与这条记录，不看实现、不改剧本。输出存到 `reports/e2e/reviews/<宿主>/<记录名>.json`。

3. **报告。**

   ```bash
   python tests/e2e/harness/report.py build --records reports/e2e/records --reviews reports/e2e/reviews --fixes reports/e2e/fixes.json --out reports/e2e
   ```

   报告给出：宿主与模型身份、首跑通过率、每个维度的分布与中位数、同一剧本多次运行之间的分布、触顶的维度（下一轮收紧）、关键维度的低分、普通回合的平均调用次数、失败记录与修复的对应（`fixes.json`：记录名 → `{"commit": …, "note": …}`）。

**通过条件**（`ACCEPTANCE.md` §6.4）：至少两个宿主；所有记录的机器检查都通过；每个维度的中位数 ≥ 4；没有任何一次运行在“玩家主权”“同意与安全”“知识边界”得 ≤ 2 分；普通回合平均调用 ≤ 1.2。

## 无头命令跑不通时

按下面的步骤手动跑一条剧本，把结果交给我整理成记录：

1. 用 `run_script.py` 的同样方式建测试项目（或手动：在 `D:\projects\at-e2e\` 下新建目录、`git init`、用 `python tools/install_skill.py <项目>\.claude\skills\adult-tension` 安装 Skill）。
2. 在终端里先设置三个环境变量再启动宿主：`ADULT_TENSION_HOME=<项目>\.at-data`、`ADULT_TENSION_TRACE=<项目>\trace.jsonl`、`ADULT_TENSION_INCLUDE_DRAFTS=1`。
3. 开新对话，按剧本文件里 `say` 的顺序逐句输入；遇到 `harness: upgrade_skill` 时关掉对话、用当前版本替换 Skill 目录、再开对话继续；遇到 `conversation` 变化时开新对话。
4. 结束后用宿主自带的导出功能把整段对话导出到测试项目里，连同 `trace.jsonl` 一起交给我。
