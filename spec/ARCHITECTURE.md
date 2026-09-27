# 架构建议

本文件是**建议**，不是合同。公开合同在 `DATA_CONTRACTS.md` 与 `RUNTIME_PROTOCOL.md`；只要满足它们，实现者可以换掉这里的任何结构，并在 `PROGRESS.md` 说明理由（`DESIGN_DECISIONS.md` 第三节）。下面几条除外，它们来自已拍板的决定，不可更改：

- 领域层纯净：不做 IO、不读系统时间、不用全局随机（D4、D10）。
- 状态只有一个写入口，一次写 = 一个数据库事务（D3、D4）。
- 运行时只用 Python 标准库（D2）。
- Skill 目录与开发目录、用户数据目录分离（D1、`SKILL_PACKAGING.md`）。

## 1. 分层

```text
宿主里的调用 Agent
   │  JSON（stdin / --input-file）
   ▼
adapters/cli         解析参数、读输入、输出信封、映射退出码
   ▼
application          用例：幂等、revision、事务边界、调用领域、组装返回
   ├──► content      读取编译好的世界包（只读、不可变）
   ├──► persistence  SQLite 仓储、迁移、备份、导入导出
   ├──► projections  上下文（brief / full）、状态（六行 / 状态+ / 调试）
   ▼
domain               纯函数：校验操作、应用操作、时间结算、开局生成、随机派生
```

依赖只能向下（向 `domain`）。`domain` 不导入 `sqlite3`、`pathlib`、`time`、`random`、`os`，也不导入任何其他层。`projections` 只读状态，不改状态。

## 2. 目录建议

```text
repo/
├─ skill/adult-tension/            # 可安装的 Skill，发布物就是这个目录
│  ├─ SKILL.md
│  ├─ agents/openai.yaml
│  ├─ references/                  # 按需读取：操作字段参考、命令参考、错误码、退出码
│  ├─ scripts/adult_tension.py     # 唯一入口，按自身路径定位 runtime/
│  ├─ runtime/adult_tension/
│  │  ├─ domain/
│  │  ├─ application/
│  │  ├─ content/
│  │  ├─ persistence/
│  │  ├─ projections/
│  │  └─ adapters/
│  └─ content/                     # 编译产物：index.json、tags.json、worlds/<id>.json
├─ spec/                           # 本蓝图，需求来源，只读
├─ content-src/                    # 内容源文件，格式自选（DESIGN_DECISIONS.md 第三节）
├─ tools/                          # 编译、脚手架、基准、模拟、评测驱动
├─ tests/{core,content,integration,e2e}/
├─ reports/                        # 验收报告、基准结果、评测记录
├─ PROGRESS.md
└─ .gitattributes                  # 强制 LF
```

`skill/adult-tension/` 里不放测试、源内容、报告与开发依赖。发布检查（`SKILL_PACKAGING.md` §9）只复制这个目录。

## 3. 唯一写路径

所有会改变状态的命令走同一个应用层函数，形如 `execute(command)`：

1. 形状校验（`DATA_CONTRACTS.md` §1：未知字段、重复键、范围）。
2. 打开写事务（例如 `BEGIN IMMEDIATE`，带有限的忙等待；拿不到锁返回 `STORAGE_BUSY`）。
3. 幂等查找；命中则提交空事务并返回旧响应（`replayed: true`）。
4. 读取当前会话快照，检查 `expected_revision`。
5. 调用领域：`domain.apply(state, command, content, rng) -> (new_state, changes)`，或返回全部错误。领域在副本上工作，失败时原状态不受影响。
6. 同一事务写入：新快照、回合记录、撤销点、幂等记录、归档移动；revision +1。
7. 提交事务后，用新状态生成投影（上下文），组装响应。

读命令不开写事务，不接受 `expected_revision`。

## 4. 领域层

- **状态**：会话状态（`DATA_CONTRACTS.md` §2）用 `dataclasses` 或普通字典加校验器表达都可以。关键是：只有领域函数能产生新状态。
- **操作**：每种 `op` 一个校验函数和一个应用函数，放在一张注册表里。未注册的 `op` 是 `INVALID_INPUT`。操作按提交中的顺序依次应用在工作副本上，后面的操作可以看到前面操作的结果。
- **错误收集**：校验阶段尽量收集全部错误后一起返回（带 JSON 路径与修改提示），而不是遇到第一个就停。
- **时间结算**：`advance_time` 触发 `RUNTIME_PROTOCOL.md` §6.1 的固定顺序，实现为一个纯函数，输入“旧时钟、新时钟、状态、随机源”，输出“结算后的状态、结算清单”。
- **开局生成**：纯函数，输入“世界包、模式、种子、约束、玩家设定、去重历史”，输出“初始状态”或 `NO_MATCH`。
- **不变量检查**：每次应用后跑一遍全局不变量（年龄、引用、时钟单调、事件状态机、`inner` 事实只属于本人等）。违反即拒绝整次提交。这是防止“某个操作漏检”的最后一道网。

## 5. 随机

- 每一次随机都从**结构化坐标**派生：`(会话种子, rng_version, 用途, 回合号, 事件或操作 ID, 序号)`。不从玩家文本或正文派生。
- 建议用 `hashlib.sha256` 对坐标的规范化编码求摘要，取前 8 字节作为 `[0, 1)` 的均匀数。这比依赖 `random.Random` 的各个方法更稳：Python 只保证 `random()` 序列跨版本可复现，`choice`、`randrange` 等方法的实现历史上变过。
- 需要从列表中抽取时，用派生出的均匀数自己实现加权抽样，并固定候选列表的排序（按 ID），不依赖字典或文件遍历顺序。
- 这样，撤销后重做同一回合得到同样的结果；读档不会重掷；同一内容版本下同一种子复现同一开局。

## 6. 存储

建议的表（SQLite，一个数据库文件）：

| 表 | 内容 |
|---|---|
| `meta` | schema_version、最后一次迁移、Skill 版本 |
| `sessions` | session_id、revision、turn、当前快照（JSON，可用 `zlib` 压缩）、创建与更新时间、来源（开局 / 读档 / 导入） |
| `turn_log` | session_id、turn、revision、action_mode、规范化后的操作、结算清单、summary、open_action、quotes |
| `undo_points` | session_id、turn、该回合开始前的快照；只保留到最近一次读档或开局 |
| `idempotency` | 作用域、request_id、输入摘要、响应；每个作用域保留最近 1000 条 |
| `archive` | 已结束事件、被章节摘要覆盖的旧回合记录；不进入上下文，导出时带上 |
| `slots` | 槽名、来源 session_id、revision、turn、显示信息、快照、保存时间 |
| `opening_history` | 最近开局签名，用于去重 |

- 撤销用“回合开始前的快照”实现最简单，也最不容易错；快照被归档机制限制了体积，所以代价可控。实现者可以换成逆操作，但必须通过同样的撤销测试。
- 快照体积必须有界：章节摘要后，旧回合记录与已结束事件移到 `archive`。基准报告中记录第 10、100、300 回合的快照体积。
- 日志写到数据目录下的 `logs/`，按大小轮转。默认日志不记录玩家原文与正文；`--debug` 时才记录，并在 `doctor` 里说明。

## 7. 内容管线

```text
content-src/（作者编辑，格式自选）
   │  tools/compile（开发时）
   ▼
skill/adult-tension/content/
   index.json           世界列表、一句话介绍、模式、状态、content_version
   tags.json            内容标签表
   worlds/<id>.json     每个世界一个完整的、已展开 extends 的包
```

- 运行时只读编译产物，不解析源格式，不做 `extends` 展开。
- 运行时按需加载：`list-worlds` 只读 `index.json`；开局只读被选中的那个世界；回合提交不读世界包（开局时已把用到的内容放进会话快照）。
- `verify-content` 在 Skill 目录内也能运行，校验的是编译产物；开发环境还会校验源文件。
- 编译是确定性的：同样的源文件产生字节相同的产物（固定键顺序、固定换行）。

## 8. 投影

- **上下文**：`brief` 与 `full` 两档（`DATA_CONTRACTS.md` §7）。列表截取规则写在一处，并由测试检查体积上限。
- **状态**：六行人话（`PRODUCT_SPEC.md` §4.4），由投影直接生成中文句子，不暴露字段名与数值；`detail` 为状态+；`debug` 给结构化数据。
- 投影函数只接受状态与内容，不访问数据库，便于在测试中直接调用。

## 9. 冷启动性能

CLI 每次调用都是一个新进程，冷启动是主要开销。建议：

- 入口脚本只做最少的导入，按子命令懒加载模块。
- 不在启动时扫描目录、编译内容或校验全部世界包。
- 数据库连接打开后只执行必要的 `PRAGMA`；迁移检查用一次 `meta` 读取完成。
- 回合提交只读一行会话快照、写几行记录。
- 用基准脚本分别测进程内耗时与冷进程耗时（`ACCEPTANCE.md` §4），两者都要报告。

## 10. 错误

- 领域错误是带 `code`、`path`、`reason`、`hint` 的结构化对象，不靠匹配异常文本。
- 未预期的异常在适配层统一捕获，返回 `INTERNAL_ERROR`，附一个错误编号（日志里能查到同一编号）。事务已经回滚，状态不变。
- 不吞异常：任何被捕获后继续执行的地方都必须有测试说明为什么可以继续。
