---
name: adult-tension
description: Run a Chinese interactive story for adults with a local deterministic engine that keeps characters, relationships, time, events, boundaries, and save slots consistent. Use when the user wants to start, continue, resume, fast-forward, inspect, save, load, export, or configure an Adult Tension story (开局、继续、存档、读档、状态、边界、暂停), or asks whether Adult Tension works.
---

# Adult Tension

面向成年人的中文互动叙事。你负责理解玩家和写正文；本地运行时负责状态、时间、随机和校验。运行时的返回是唯一的事实来源。

**当前版本只完成了环境自检（预览版）。** 开局、回合、存读档等玩法还没有开放：玩家要开局或继续时，先运行 `doctor`，再如实告诉玩家“环境已就绪，玩法还在开发中”，不要自己编故事代替运行时。

不要向玩家暴露：命令名、字段名、revision、错误码、工具调用过程。

## 调用运行时

    <python> scripts/adult_tension.py <command> --json [--input-file <tmp.json>]

- `scripts/adult_tension.py` 相对于本 Skill 目录；调用时用它的完整路径。
- `<python>`：依次试 `python3`、`python`、`py -3`，用第一个 3.10 及以上的。版本过低时运行时会返回 `RUNTIME_UNSUPPORTED`，照实告诉玩家需要的版本。
- 需要输入的命令：把 JSON 写进一个 UTF-8 临时文件，用 `--input-file` 传入。**玩家的原话永远不放进命令行参数。**
- stdout 只有一个 JSON：`{"ok", "data", "error"}`。`ok` 为 false 时读 `error.message` 与 `error.details[].hint`。
- 超时、没有输出、输出不是 JSON：重试最多 3 次；仍失败就把情况用一句话告诉玩家。

## 第一次

本对话第一次使用之前运行一次 `doctor`：

- `data.status` 为 `ok` 或 `warn`：环境就绪。`warn` 的项用一句话转述即可。
- 失败：按 `error.details[].hint` 与 `error.doctor.checks` 里的建议告诉玩家怎么办。不自己安装软件、不改系统环境、不删数据。
- 数据目录不可写（沙箱只允许写工作区时常见）：告诉玩家可以用 `--data-dir` 指向一个可写目录，或让宿主放行该目录。

## 命令

| 玩家说 | 你做 |
|---|---|
| 看看能不能用、检查环境 | `doctor`，用一两句话转述结果 |
| 版本 | `version` |
| 开局、继续、存档、读档等 | 先 `doctor`；然后说明玩法尚未开放 |

## 参考资料（需要时再读）

- `references/commands.md`：命令、错误码与退出码
- `references/troubleshooting.md`：环境问题与 `doctor` 各项的处理
