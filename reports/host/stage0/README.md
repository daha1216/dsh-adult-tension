# 阶段 0 真实宿主记录

- 日期：2026-09-28
- 宿主：OpenCode 1.18.29（`opencode run --format json`，无头模式）
- 模型：`opencode/big-pickle`（OpenCode Zen 免费模型，用 `-m` 指定）
- 测试项目：`D:\projects\at-host-test\`（本仓库之外，独立 `git init`）
- 安装方式：`python tools/install_skill.py D:\projects\at-host-test\.claude\skills\adult-tension`（项目级 Skill 目录；OpenCode 兼容 `.claude/skills/`）
- 数据目录：启动宿主时设置 `ADULT_TENSION_HOME=D:\projects\at-host-test\.at-data`，与用户真实数据目录隔离
- 权限：测试项目的 `opencode.json` 只放行 `python`/`py`/只读命令，禁止外部目录与联网
- 事先确认：`~/.claude/skills`、`~/.config/opencode/skills`、`~/.agents/skills` 下都没有同名 Skill（只检查是否存在，不打开）
- 玩家输入：`看看 Adult Tension 能不能用`
- 完整记录：`opencode-transcript.jsonl`（原样保存的 JSON 事件流）

## 过程

| # | 工具调用 | 耗时 | 结果 |
|---|---|---|---|
| 1 | `skill {"name": "adult-tension"}` | 512 ms | 宿主发现并加载了被测 Skill |
| 2 | `bash: python3 --version; python --version; py -3 --version` | 260 ms | 3.14.6 / 3.12.10 / 3.14.6 |
| 3 | `bash: python3 "D:\projects\at-host-test\.claude\skills\adult-tension\scripts\adult_tension.py" doctor --json` | 628 ms | `ok: true`，`status: warn`（还没有世界包），`skill_root` 指向被测目录，`data_dir_source: env` |

模型最终回复：“环境已就绪：Python 3.14.6、SQLite 正常、数据目录可写、数据库已完成迁移。唯一提醒是内容版本还是 0.0.0，还没有可开局的世界。”

## 发现的问题

- 本机 `claude`（npm 安装）无法运行：`claude native binary not installed`。修复需要在仓库外运行其安装脚本，已记为待决事项。
- OpenCode Go 订阅未激活，Go 系列模型返回 403；本次改用免费模型完成冒烟。免费模型可能把数据用于训练，后续含成人内容的试玩不在未经用户同意的情况下使用它，已记为待决事项。
