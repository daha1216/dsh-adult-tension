# adult-tension-narrative

这是一个成年人互动故事技能。它会准备世界、角色和开场，让 NPC 按自己的性格和处境行动。故事中的时间会继续向前，重要事件也会留下记录。

## 它能做什么

- 随机生成一个完整开局，也可以提前指定题材、人物或种子。
- 让 NPC 自己判断、拒绝、协商或主动行动。
- 记录时间、关系、事件和角色状态。
- 随时导出存档，以后从原来的位置继续。
- 在亲密场景中检查年龄、人物边界和当前同意。

## 怎么安装

把整个 `adult-tension-narrative` 文件夹复制到 AI 工具的技能目录中。不要只复制 `SKILL.md`，其他文件也是技能的一部分。

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

修改素材表或存档格式时，需要同步检查脚本和测试。仓库根目录的 [CONTRIBUTING.md](../CONTRIBUTING.md) 写有完整维护步骤。
