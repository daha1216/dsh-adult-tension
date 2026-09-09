# 最新主线审查与精品化收尾实施报告

日期：2026-09-10。来源主线：`8910ec95a332a6d95cf614fa31a15805fae60158`，本轮收尾时通过 `git ls-remote origin refs/heads/main` 再次核对一致。实现分支：`codex/governance-final`。

## 结论

本轮已落地框架精简、按框架维护、核心素材审查登记、运行状态隔离、文档同步和统一 QA。工程检查通过，但精品化验收未通过，不能宣称全部语义缺口已修复，也不能发布或合入正式主线。

当前结论分三层：

- 结构和运行回归：通过；不代表正文精彩。
- 素材语义登记：699 个核心旧池单元全部有处置，569 个仍需桥接；1,573 个非核心单元仍未审查。
- 真实模型叙事验收：保留实际失败及逐回合独立评分，完整性和通过数见本报告的实玩结果及 `scripts/playtest_report.py`。不把失败改成通过，不用静态模板代替模型回复。

## 已实施

### 框架与内容

- 按原清单移除第 37–42、47–53 项，共 13 框架，保留 40。精确名称记录在 `maintenance/baseline.yaml`，不沿用删减后的序号解释历史选择。
- 新增 `authoring/framework_index.yaml`、40 份框架编辑源和对应静态审查。构建器按明确顺序生成原运行时结构，拒绝身份冲突、漏索引和失效审查。
- `auto` 只抽取来源匹配且静态审查有效的框架，不再隐式回退旧池；显式 `legacy` 保留。静态审查有效不等于该框架实玩已达精品标准。
- 补齐活动功能、地点功能和出口、人物资源与限制、关系化学、技术边界、压力显式配对。跨城或跨主题的桥接说明进入世界常量，不能由模型自行视为同地或任意兼容。
- 压力只选已声明的活动/地点/人物组合，不再把这些候选做任意笛卡尔积；日常模式不自动生成外部压力事件。
- 删除两个没有运行入口的处境模板及失效的旧决策文件，保留来源、删除理由和回归证据。共享池、历史 Git 内容和旧存档快照未随框架删除。
- 冻结章节逐字节指纹仍与原基线一致，未扩写或放宽限制内容。

### 运行与兼容

- 默认工作状态改为独立 session，开局返回 `state_path` 和 `state_token`；提交在锁内核对预期 token，拒绝过期状态覆盖。
- 保留显式旧 `--state` 入口，不改变 v3 存档字段。原有槽位、载入、事件归档和 `legacy` 均有回归。
- 存档读取使用一致锁，状态/清单成对写入失败时恢复；开局写入成功后才记入历史。
- 终态事件保留结果收据，支持定向事件回忆；开局摘要返回已提交的姓名、年龄和当前场景信息。
- YAML 加载拒绝重复键；默认抽取不再清空既有时代、地点、美学和外观兼容元数据。

### 维护和文档

- 核心素材显式登记，普通字段实时盘点；维护 ID 与展示名称分离，支持别名、来源哈希和失效标记。紧凑登记兼容原读取 API，不让登记表进入玩家上下文。
- 699 条决策绑定 16 个实际审查依赖文件。元数据或消费者改变，即使池名未变，也必须复审，不能只刷新哈希。
- 数据文件、架构层、模式和依赖统一到 manifest；新增未登记的 YAML 会报错。
- `qa.py` 统一全量、差异、框架和素材检查，保留底层脚本。改动影响共享运行逻辑时扩展检查范围，不承诺所有变更都能只跑局部测试。
- 指纹只在完整工程检查通过且期间数据不变时更新。CI 默认工程检查，标签或显式发布检查额外核验语义与真实模型证据。
- README、SKILL 非冻结段、commands、开局、状态、事件、维护和增补文档已按实际接口同步。历史报告明确标旧，不冒充当前结论。

## 审查统计

14 个运行数据 YAML 当前有 12,587 个来源字段，属于字段级盘点，不是独立素材数量。维护目录有 2,374 个当前语义单元、2,389 条含历史处置的记录。

| 核心旧池处置 | 数量 | 含义 |
| --- | ---: | --- |
| BRIDGE_REQUIRED | 569 | 已定位缺口，尚未解决；不授予新的随机组合资格 |
| KEEP_LEGACY | 66 | 仅批准明示的局部旧入口用途 |
| KEEP_SHARED | 18 | 有限表达/核验动作复用，不等于全框架通用 |
| FROZEN_RESTRICTED | 46 | 限制来源登记，不扩写，不代表兼容已修复 |
| 合计 | 699 | 全部有记录，不等于全部闭合 |

逐项理由见 `core_review_decisions.yaml`，批次方法、消费者依据和限制见 `core_review_evidence.md`。该证据文档中的“未写回”描述的是独立审查批次；本轮随后通过 `sync_governance.py --write` 正式集成。

40 个框架静态等级均为 B，没有因为通过机械检查而提升到 A。当前有 172 组显式配套。226 个旧池条目被名称引用、473 个未被引用；这组统计与语义处置不同，不能互换。

重复治理只核定了 5 个具体候选：1 个近似条目属于不同关注对象，4 个跨文件相同项属于分类引用，均有保留理由。扫描得到的 244 个重复文案簇仍需语境审读，不宣称全库已经去重。

人物搭配还有明显集中：80 个角色视角中 73 个同侪、5 个旧识、2 个外来者；26 个资源复用候选来自前 13 个框架的双方职业视角互换。不能把这些视角计为 26 套完全不同的人物。

## 工程验证

本机 Python 3.12.10 先执行 `python -X utf8 scripts/qa.py --full`，门禁补强后再执行 `python -X utf8 scripts/qa.py --full --release`。后者工程步骤通过，发布阶段按预期退出 1：

| 检查 | 实测结果 |
| --- | --- |
| 框架构建与审查来源 | 40 框架，40 静态审查有效 |
| 内容检查 | 5,991 项，无 ERROR/WARNING |
| 跨层兼容检查 | 无 ERROR/WARNING |
| 核心审查集成 | 699 项有处置，无登记 ERROR；仍有 1 条未审非核心单元告警 |
| 确定性双模式抽样 | seeds 11、29，共 168 次，无失败 |
| 分布抽样 | auto/pressure，1,000 次完成 |
| pytest | 最后完整执行 290 passed；包含 daily/pressure/legacy 的 300 回合状态及载入回归 |
| compileall、git diff --check | 通过 |
| 冻结章节 | SHA-256 与 baseline 完全一致 |
| 发布检查 | 拒绝：`CORE_BRIDGE_GATE: 569` 及实玩未达标，不将此命令报告为通过 |

随后补充了追问协议与当前 `FOLLOWUPS` 一致性的检查，相关实玩、QA、框架及文档测试 50 项通过，其中包含新增回归；这 50 项与前述完整测试有重叠，不能相加成测试总数。

上述 300 回合是状态与事件回归，不是 300 回合模型正文；1,000 次抽样不替代实玩。GitHub 的 Linux Python 3.10/3.13 CI 尚未在本分支运行，不能把本机结果称为远端 CI 通过。

## 实玩范围

使用当前配置的 DeepSeek Harness `0.1.5-alpha.2`、`deepseek-v4-flash`，协议为 `non-explicit-runtime-brief-v2`。每框架两种模式，每案例新局加三次续写，目标为 80 案例、320 条模型回复。生成与独立评分分离；逐回合五维各 0–2 分，每回合至少 8/10、无零分和阻断问题才通过。

输入来自实际运行器的抽取与开局状态摘要，以及对应框架包；每次 headless 调用重放先前对话。测试不发送私密画像或冻结章节，不修改 DSH 路由或 Web 配置。8 条早期输入不足的试跑已归档到 `playtests/pilot-v1/`，不计入正式数量。

这属于真实模型的非露骨叙事探针，**不是**完整 Skill 安装、Web UI 运行及每回合 prose→patch→commit→reload 的端到端认证。门禁会核对当前逐回合请求协议，并用当前运行器、提示词和已记录历史重建每条请求、比对 `prompt_sha256`；因此框架名称不变但实际输入改变时，旧回复也会失效。32 条早期 v2 输入已经漂移的回复及评分另归档到 `playtests/stale-input-v2/`，与正式证据分开，不删改旧失败。旧评分的原始字节另存 `original-reviews.zip` 并核对哈希；可读 YAML 仅清理行尾空格和多余末尾空行。

当前只用 seed 11，每框架每模式选中一个组合，不能覆盖框架内全部配对。三个续写请求固定为询问/小事、提出异议、告别，较集中于协商与边界；玩家异议本身也不够具体。下一轮应补充明确行动、共同完成一件事、主动探索等探针，不能把全部低分直接归因于素材源码，也不能反向删除这轮失败来提高通过率。

## 实玩结果

正式证据为 80 案例、320 条实际回复，320 条均通过当前输入和协议指纹核验；80 份独立评分完整且摘录可追溯。**36/80 案例通过，44/80 失败；10/40 框架双模式通过。逐回合为 223/320 通过、97/320 失败。** `playtest_report.py` 返回非零，没有缺回复、缺评分或过期输入被算成成功。

分数是该模式四回合中最低总分，达到 8 分但某回合有零分或阻断项仍然失败。下表是当前 40 框架索引顺序，不是原 53 框架的删除序号；点击成绩可查逐回合原文依据。

| 当前序号 | 框架 | 日常 | 压力 |
| ---: | --- | --- | --- |
| 1 | 仙门藏书与驿镖 | [7/10 未过](playtests/mat-42c81e4bce155f60965e7f38a05f9f1a-daily.review.yaml) | [7/10 未过](playtests/mat-42c81e4bce155f60965e7f38a05f9f1a-pressure.review.yaml) |
| 2 | 海岸渡船与观测旅行 | [7/10 未过](playtests/mat-136cffe204385cf0a24a21141c98f486-daily.review.yaml) | [8/10 通过](playtests/mat-136cffe204385cf0a24a21141c98f486-pressure.review.yaml) |
| 3 | 地方行业与公共记忆 | [7/10 未过](playtests/mat-4b650ae3628b5c79b6f00d09d3ffb1c0-daily.review.yaml) | [8/10 通过](playtests/mat-4b650ae3628b5c79b6f00d09d3ffb1c0-pressure.review.yaml) |
| 4 | 城市休闲与共享会客 | [6/10 未过](playtests/mat-260b72b95d8e52d2853d796a97e9c46e-daily.review.yaml) | [7/10 未过](playtests/mat-260b72b95d8e52d2853d796a97e9c46e-pressure.review.yaml) |
| 5 | 成年创作者与校园艺术季 | [7/10 未过](playtests/mat-d0c513c689a45b7885d414535748b9b7-daily.review.yaml) | [8/10 通过](playtests/mat-d0c513c689a45b7885d414535748b9b7-pressure.review.yaml) |
| 6 | 远途休假与小镇停留 | [8/10 通过](playtests/mat-00c8740516f7519592b47bb547fe5c27-daily.review.yaml) | [8/10 通过](playtests/mat-00c8740516f7519592b47bb547fe5c27-pressure.review.yaml) |
| 7 | 契约城与非人街坊 | [9/10 通过](playtests/mat-9f184a419c415aac8ecb2bcf0168a6cc-daily.review.yaml) | [9/10 通过](playtests/mat-9f184a419c415aac8ecb2bcf0168a6cc-pressure.review.yaml) |
| 8 | 传媒编辑室与公开记录 | [6/10 未过](playtests/mat-1d837f8f99fc51d99a76cd57594978fd-daily.review.yaml) | [8/10 通过](playtests/mat-1d837f8f99fc51d99a76cd57594978fd-pressure.review.yaml) |
| 9 | 旧町神怪与灯会 | [7/10 未过](playtests/mat-994ec96dc0825679ab200cdfdc65c56f-daily.review.yaml) | [8/10 通过](playtests/mat-994ec96dc0825679ab200cdfdc65c56f-pressure.review.yaml) |
| 10 | 同人街区与录音协作 | [7/10 未过](playtests/mat-295d0099c528557f847e965c60eeefe5-daily.review.yaml) | [6/10 未过](playtests/mat-295d0099c528557f847e965c60eeefe5-pressure.review.yaml) |
| 11 | 寒冬避难所公共生活 | [8/10 通过](playtests/mat-3f430a8a5ab95accb2a0db0ae2ceb369-daily.review.yaml) | [7/10 未过](playtests/mat-3f430a8a5ab95accb2a0db0ae2ceb369-pressure.review.yaml) |
| 12 | 检疫站旁的生活区 | [7/10 未过](playtests/mat-0cc59e86706659aa89202725d9f89f5c-daily.review.yaml) | [7/10 未过](playtests/mat-0cc59e86706659aa89202725d9f89f5c-pressure.review.yaml) |
| 13 | 废土驿站与修补集市 | [8/10 通过](playtests/mat-ceb44925590351c48e181e6abd9f79c5-daily.review.yaml) | [8/10 通过](playtests/mat-ceb44925590351c48e181e6abd9f79c5-pressure.review.yaml) |
| 14 | 星海边境生活站 | [7/10 未过](playtests/mat-bea6535a01305dd6b8e8903f6d521c08-daily.review.yaml) | [8/10 通过](playtests/mat-bea6535a01305dd6b8e8903f6d521c08-pressure.review.yaml) |
| 15 | 赛博街区与公共终端 | [6/10 未过](playtests/mat-de87cf5cd73859139a93b09b472d4e59-daily.review.yaml) | [4/10 未过](playtests/mat-de87cf5cd73859139a93b09b472d4e59-pressure.review.yaml) |
| 16 | 地下城安全层营地 | [8/10 通过](playtests/mat-eb4dfde0e57f537db14d8c03c31bf028-daily.review.yaml) | [8/10 通过](playtests/mat-eb4dfde0e57f537db14d8c03c31bf028-pressure.review.yaml) |
| 17 | 王都工坊与委托街 | [6/10 未过](playtests/mat-be59cd317bd15c268ca4e877683d27d1-daily.review.yaml) | [7/10 未过](playtests/mat-be59cd317bd15c268ca4e877683d27d1-pressure.review.yaml) |
| 18 | 幕末町屋与道场 | [7/10 未过](playtests/mat-d8ec69422b1354538ef3c705f4beb804-daily.review.yaml) | [8/10 通过](playtests/mat-d8ec69422b1354538ef3c705f4beb804-pressure.review.yaml) |
| 19 | 禁酒期爵士与报纸 | [8/10 通过](playtests/mat-03b5642c3fc9592c915e402dcbcacb01-daily.review.yaml) | [8/10 通过](playtests/mat-03b5642c3fc9592c915e402dcbcacb01-pressure.review.yaml) |
| 20 | 长安夜市与坊志 | [7/10 未过](playtests/mat-8ad2df5335435696a3508c6f7223a3d0-daily.review.yaml) | [8/10 通过](playtests/mat-8ad2df5335435696a3508c6f7223a3d0-pressure.review.yaml) |
| 21 | 蜃景商路与鬼市 | [8/10 通过](playtests/mat-de3184d40c645541b9bea1798a7633c9-daily.review.yaml) | [8/10 通过](playtests/mat-de3184d40c645541b9bea1798a7633c9-pressure.review.yaml) |
| 22 | 流动马戏与机械舞台 | [8/10 通过](playtests/mat-5eb6b8ace29355a28f3fe076f9834afe-daily.review.yaml) | [8/10 通过](playtests/mat-5eb6b8ace29355a28f3fe076f9834afe-pressure.review.yaml) |
| 23 | 湘西山路与乡志 | [8/10 通过](playtests/mat-2bfa7ee5ec9a5289aa2ca12c4af25323-daily.review.yaml) | [8/10 通过](playtests/mat-2bfa7ee5ec9a5289aa2ca12c4af25323-pressure.review.yaml) |
| 24 | 风沙驿站与旧图 | [9/10 通过](playtests/mat-9de13e83d7fa5038aef27ca1665f97b4-daily.review.yaml) | [8/10 通过](playtests/mat-9de13e83d7fa5038aef27ca1665f97b4-pressure.review.yaml) |
| 25 | 雾都钟表与港务街 | [7/10 未过](playtests/mat-63910e70d6515d33b712a1b3251b5d60-daily.review.yaml) | [8/10 通过](playtests/mat-63910e70d6515d33b712a1b3251b5d60-pressure.review.yaml) |
| 26 | 明治洋裁与译书町 | [8/10 通过](playtests/mat-c63d8b1b82ad5acd81d82f9f087a0956-daily.review.yaml) | [8/10 通过](playtests/mat-c63d8b1b82ad5acd81d82f9f087a0956-pressure.review.yaml) |
| 27 | 民国报馆与手艺街 | [7/10 未过](playtests/mat-232c29d387b257da9f10218587eba099-daily.review.yaml) | [7/10 未过](playtests/mat-232c29d387b257da9f10218587eba099-pressure.review.yaml) |
| 28 | 王朝百业与书院 | [5/10 未过](playtests/mat-18cd509fb7815b8188a771e4966bc7c6-daily.review.yaml) | [8/10 通过](playtests/mat-18cd509fb7815b8188a771e4966bc7c6-pressure.review.yaml) |
| 29 | 后方邮路与灯火 | [5/10 未过](playtests/mat-63dd15d920ee5fd693c917b26f3617d6-daily.review.yaml) | [7/10 未过](playtests/mat-63dd15d920ee5fd693c917b26f3617d6-pressure.review.yaml) |
| 30 | 昭和街角喫茶巡礼 | [6/10 未过](playtests/mat-5c23e7b8931d5da7aa19503d079f35a9-daily.review.yaml) | [6/10 未过](playtests/mat-5c23e7b8931d5da7aa19503d079f35a9-pressure.review.yaml) |
| 31 | 千禧网络街坊 | [8/10 通过](playtests/mat-cdd67109e5e555db92c6d982ca09f3ed-daily.review.yaml) | [6/10 未过](playtests/mat-cdd67109e5e555db92c6d982ca09f3ed-pressure.review.yaml) |
| 32 | 磁带与夜市街区 | [7/10 未过](playtests/mat-d136423bf1195d8fb009a708bcb0219f-daily.review.yaml) | [5/10 未过](playtests/mat-d136423bf1195d8fb009a708bcb0219f-pressure.review.yaml) |
| 33 | 街角共同生活圈 | [8/10 通过](playtests/mat-a8de42dfb83753db94e47e7b0d0e8175-daily.review.yaml) | [5/10 未过](playtests/mat-a8de42dfb83753db94e47e7b0d0e8175-pressure.review.yaml) |
| 34 | 仙门山下百业镇 | [7/10 未过](playtests/mat-9a093702ba565679b7c385e98752251a-daily.review.yaml) | [8/10 通过](playtests/mat-9a093702ba565679b7c385e98752251a-pressure.review.yaml) |
| 35 | 退休勇者之城 | [7/10 未过](playtests/mat-453926bfbbdb51ae8cbd3510af219549-daily.review.yaml) | [7/10 未过](playtests/mat-453926bfbbdb51ae8cbd3510af219549-pressure.review.yaml) |
| 36 | 灵气复苏十年后 | [7/10 未过](playtests/mat-ddf812ba8b975540a8f108d4b4fcb65e-daily.review.yaml) | [9/10 通过](playtests/mat-ddf812ba8b975540a8f108d4b4fcb65e-pressure.review.yaml) |
| 37 | 废墟复兴小镇 | [6/10 未过](playtests/mat-4851892aeeda5d819ed8ec1123084cef-daily.review.yaml) | [6/10 未过](playtests/mat-4851892aeeda5d819ed8ec1123084cef-pressure.review.yaml) |
| 38 | 夜校学分与开放实验室 | [7/10 未过](playtests/mat-3ae739c0ff775d2ca0fb4568e23d8811-daily.review.yaml) | [7/10 未过](playtests/mat-3ae739c0ff775d2ca0fb4568e23d8811-pressure.review.yaml) |
| 39 | 地下管廊与城市修理局 | [6/10 未过](playtests/mat-33ffa06662dd50978821b62840ae86f4-daily.review.yaml) | [7/10 未过](playtests/mat-33ffa06662dd50978821b62840ae86f4-pressure.review.yaml) |
| 40 | 河岸康复与互助居所 | [7/10 未过](playtests/mat-e9178ea6150b59fb9e7d7f3288c4196d-daily.review.yaml) | [8/10 通过](playtests/mat-e9178ea6150b59fb9e7d7f3288c4196d-pressure.review.yaml) |

代表性阻断及修复方向：

- `赛博街区与公共终端 / pressure`：测试账号被写成可以改变正式预约和门禁状态。修复重点是将测试结果、正式操作与有权限的执行者分开，不能用“可回退”代替权限。
- `王都工坊与委托街 / daily`：未做计时却准备标定连续照明上限。明确区分观察、猜测和实测；只保留已经发生的证据。
- `地下管廊与城市修理局 / pressure`：玩家还未作出具体选择，正文已替其摆放资料；异议又只得到“不加义务”的回答。应先澄清具体分歧，让选择改变接下来的动作。

以上是真实探针中的失败，不等同于已证明所有实际玩家流程必然出现同样错误；但在本轮承诺的门槛下都不能放行。

## 尚未完成与下一步

1. 先修复并重跑真实失败的框架/模式。区分来源配套不足、运行摘要丢事实和模型执行偏差；优先修权限/事实越界、时间连续性和替玩家决策，不通过追加大量免责话术掩盖活动不推进。
2. 补齐真实宿主闭环验收：按实际安装 Skill 发起开局和续写，记录提交状态、事件变化、保存载入和失败恢复；与现有叙事探针分别报告。
3. 逐批处理 569 个桥接单元，优先期限与事件、地点门禁出口、身份成员级时代、称谓与社会位置、动作文本与分类的一致性。允许有理由留在 legacy，不机械挂靠框架，不让未获批条目进入默认入口。
4. 按当前运行读取频率审查 1,573 个非核心单元，补审 244 个重复文案簇。共享事实不删，真正重复才合并，限制条目只登记。
5. 降低人物视角复用和社会位置集中；先给同框架第二组人物不同资源、限制和见面理由，再衡量是否需要新素材。暂不扩充框架数量。
6. 新版来源或运行逻辑变更后，定位并重审受影响证据，重跑失败案例及回归；达标前不合并 main、不发布精品版。不得用调整评分门槛或手改指纹消除失败。

本轮保留可检查的实现与失败证据，不把以上遗留写成已完成事项。
