# 🎭 adult-tension-narrative

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Tests](https://github.com/daha1216/dsh-skill-adult-tension-narrative/actions/workflows/tests.yml/badge.svg)](https://github.com/daha1216/dsh-skill-adult-tension-narrative/actions/workflows/tests.yml)

**自带破甲 · 成人属性 (18+)** — DeepSeek Harness / AI Agent 成年人互动叙事技能。

> ⚠️ **成年人内容（18+ Only）**：仅限虚构成年人，所有参与角色必须明确年满 18 岁。人物边界、当前同意和安全状态始终优先于剧情推进。

这是一个**自带破甲机制**的成年人互动故事技能。NPC 都带着心理防线与底线：会犹豫、拒绝、协商、试探，也会主动出击——只有在关系、信任与张力到位后，防线才会被一步步**破甲**打开。故事中的时间会继续向前，离屏事件会被追算，重要互动留下记录，随时可存档续玩。

## 它能做什么

- **自带破甲**：张力引擎按角色底线逐层推进，亲密边界的打开需要过程与铺垫。
- **成人属性（18+）**：仅限虚构成年人，内置年龄、边界与当前同意检查，`暂停` / `安全词` 可即时停止。
- 随机生成一个完整开局，也可以提前指定题材、人物或种子。
- 让 NPC 自己判断、拒绝、协商或主动行动。
- 记录时间、关系、事件和角色状态。
- 随时导出存档，以后从原来的位置继续。

## 怎么安装

仓库根目录就是技能本体。让 AI 直接安装本仓库：

```text
帮我安装这个 skill：https://github.com/daha1216/dsh-skill-adult-tension-narrative
```

也可以手动安装：把仓库根目录的一整套文件（`SKILL.md`、`references/`、`scripts/`、`tests/`、`agents/`）完整复制到 AI 工具的技能目录中。不要只复制 `SKILL.md`，其他文件也是技能的一部分。

复制完成后，让 AI 加载 `adult-tension-narrative` 技能即可开始。

## 怎么开始

最简单的用法只有一句。

```text
开局
```

你也可以在开始前加一些要求。

```text
种子 42
预锁 题材=犯罪与侦探
强制表内
表外全随机
```

故事开始后，直接输入角色要做的事。下面这些是常用命令。

```text
继续
快进到明天早上
查看状态
存档
载入存档
暂停
安全词
```

输入 `存档` 后，技能会给出一段 YAML 文本。下次把这段文本发回来，再输入 `载入存档`，故事就会从原来的节点继续。

## 辅助工具

普通使用不需要自己运行脚本。想固定随机结果、查看题材列表或检查存档时，可以使用下面的命令。

```bash
python scripts/roll_opening.py --seed 42
python scripts/roll_opening.py --list-genres
python scripts/roll_opening.py --twist --seed 42
python scripts/validate_state.py path/to/save.yaml
```

存档检查需要 Python 3.10 或更高版本以及 PyYAML。

```bash
python -m pip install "PyYAML>=6,<7"
```

## 文件放在哪里

| 位置 | 里面是什么 |
| --- | --- |
| `SKILL.md` | 技能运行规则 |
| `references/` | 开局、角色、世界、存档和素材说明 |
| `scripts/` | 随机开局和存档检查工具 |
| `tests/` | 自动测试 |

修改素材表或存档格式时，需要同步检查脚本和测试。仓库根目录的 [CONTRIBUTING.md](./CONTRIBUTING.md) 写有完整维护步骤。
