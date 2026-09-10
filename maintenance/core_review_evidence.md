# 699 核心旧池逐项审查证据

审查日期：2026-09-10。审查者：Codex，AI 辅助逐项语义审查；不声称人工审批或实玩验收。

## 结论与边界

全部 699 个当前核心池单元已给出逐项处置，见 [core_review_decisions.yaml](core_review_decisions.yaml)。其中 BRIDGE_REQUIRED 569、KEEP_LEGACY 66、KEEP_SHARED 18、FROZEN_RESTRICTED 46。没有 KEEP_FRAMEWORK、自动名称归属、批量兜底保留或删除决策。699 条记录不等于 699 条兼容问题已解决，569 个桥接单元仍未闭合；84 个保留单元也仅在明示的局部用途内成立。

本次只产出决策与本证据文件，未应用到正式 registry，未修改源数据、runtime 或冻结 SKILL。40 框架的语义审查、结构检查和 320 实玩属于其他工作流；本文件不替代其失败记录或发布门槛。

## 审查方法

按来源逐项阅读池值及其兼容 metadata，再核对实际模板、人物/场所画像和消费路径，按内容而非名称判断是否能解释当前用途。逐项理由写在 review.reason；共 699 个不同理由。数量和字符串不同仅用于完整性核验，不作为语义质量证据。

身份族审查读其全部成员，地点审查读全部细节和画像，动作审查同时看模板、建议与分类元数据，处境审查同时看压力模板和日常覆盖。结构匹配、键名引用和关键词命中均未作为框架语义归属证明。限制内容只作中性的冻结或缺口分类，不补写或扩展。

源码阅读与内存应用是本次证据，不声称执行了 699 次运行消费者、699 场实玩或全组合回归。以下源码定位与末尾哈希共同确定审查快照。

## 字段解释与集成约束

- id、source、source_hash 来自当前 material_registry.units()，保留现有稳定 ID；未自行重命名来源。
- BRIDGE_REQUIRED 的 modes 和 owners 均为空，review.reason 写具体缺口；themes 是描述性检索信息，不是框架授权。
- FROZEN_RESTRICTED 的 frozen/restricted 均为 true，modes/owners 为空；冻结不意味着已修复或可运行，后续不得绕过冻结修改保护。
- KEEP_LEGACY/KEEP_SHARED 的 owners 使用 consumer: 函数或输出字段定位，只说明真实消费者。它们不是框架 ID，也不是框架认领。现有 apply_decisions 接受该列表，但任何将 owners 解释为框架名的下游报告应区分此命名空间。
- 18 个 KEEP_SHARED 是 11 个表达风格和 7 个证据核验动作的局部复用判断，不是已在多个框架实玩通过。
- 15 个 daily_interpretation_only 只批准日常覆盖的低压解释，不批准同名压力模板。5 个 contrast_only 只保留交易桶对照用途。其余 64 个保留项为 unit_scope_only，不能直接扩大到随机组合。
- 非空 eras/places 是本次限定范围；部分 eras 已按内容人工缩窄并标记 compatibility_basis。空列表不提供新的时代或场所承诺，须结合 technology_boundary 与逐项理由理解，不能在运行消费者中直接视作无限制通配。
- modes 是维护用途说明，不是已接入运行时的过滤器。registry 当前不被 runtime 加载；本次没有把这些限定强制写入消费者。
- review.release 使用当前真实 governance-1，没有制造发布周期。review.evidence 指向本文件相应来源批次；review.scope 提供批次与逐项序号。
- apply_decisions 接收 YAML 顶层列表，可在 load_registry() 的内存副本上应用；本次不调用 write_registry。若主任务集成时来源或冻结状态已变化，必须处理真实冲突，不删除 source_hash、不放宽 stale/frozen 检查。

## 来源批次索引

每个批次在决策文件中独立连续排列，以 G01 至 G13 注释分隔。review.scope 格式为 core_pool_unit:Gxx:NNN，批次内从 001 连续到该批次总数。逐项的完整 status、modes、owners、compatibility、restrictions 和理由均在主文件，不以本表代替。

| 批次 | 来源 | 总数 | BRIDGE_REQUIRED | KEEP_LEGACY | KEEP_SHARED | FROZEN_RESTRICTED |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| [G01](#G01) | 核心规则 | 47 | 44 | 3 | 0 | 0 |
| [G02](#G02) | 美学基调 | 46 | 29 | 5 | 11 | 1 |
| [G03](#G03) | 张力引擎 | 72 | 66 | 3 | 0 | 3 |
| [G04](#G04) | 时代与地点/时代 | 31 | 30 | 1 | 0 | 0 |
| [G05](#G05) | 时代与地点/地点 | 128 | 111 | 16 | 0 | 1 |
| [G06](#G06) | 社会规则 | 30 | 27 | 3 | 0 | 0 |
| [G07](#G07) | 压力来源 | 74 | 72 | 0 | 0 | 2 |
| [G08](#G08) | 场景动作/交易摊牌 | 22 | 15 | 5 | 0 | 2 |
| [G09](#G09) | 场景动作/非交易靠近 | 91 | 51 | 20 | 7 | 13 |
| [G10](#G10) | 身份侧 | 17 | 13 | 0 | 0 | 4 |
| [G11](#G11) | 处境侧 | 84 | 65 | 6 | 0 | 13 |
| [G12](#G12) | 玩家化身轴/称谓 | 26 | 25 | 1 | 0 | 0 |
| [G13](#G13) | 玩家化身轴/社会位置 | 31 | 21 | 3 | 0 | 7 |
| 合计 | 全部核心池 | 699 | 569 | 66 | 18 | 46 |

<a id="G01"></a>

### G01 核心规则

覆盖 47 条。已读：pools.yaml 的核心规则、daily_opening.核心规则、fill_opening 的世界常量和压力分支代价句。

处置依据与未解决项：44 条未闭合。身份公开成本高缺公开对象、实际损失与撤回路径；资源按需配给缺需求判定和申诉机制。3 条保留只指日常分支的邻里互助、自持与承诺表达，不认可压力分支自动赋予违例惩罚。

逐项定位：决策文件 review.scope 从 core_pool_unit:G01:001 到 core_pool_unit:G01:047。

<a id="G02"></a>

### G02 美学基调

覆盖 46 条。已读：全部美学标签、gate_aesthetics、aesthetic_eras、地点时代约束、fill_opening 的质感常量与外观门控。

处置依据与未解决项：29 条仍缺文化、场所或技术边界。雨夜霓虹未区分照明设施与比喻，旧年代质感不能提供具体技术基线。11 条 KEEP_SHARED 仅为文体或表达用途，5 条 KEEP_LEGACY 按逐项限定范围保留；另 1 条冻结。写实风格不证明随机世界符合现实。

逐项定位：决策文件 review.scope 从 core_pool_unit:G02:001 到 core_pool_unit:G02:046。

<a id="G03"></a>

### G03 张力引擎

覆盖 72 条。已读：引擎条目、leverage_engines、situation_leverage、daily_opening 的引擎白名单，以及 roll_opening 的关键词对齐和组合选择。

处置依据与未解决项：66 条缺触发条件、实际事件或关系事实。时限逼近没有数值；资源锁定没有资源与取得路径。情感拉扯、对等试探、旧情重逢仅保留日常低压解释；3 条仅冻结。关键词重合不能证明因果链已连接。

逐项定位：决策文件 review.scope 从 core_pool_unit:G03:001 到 core_pool_unit:G03:072。

<a id="G04"></a>

### G04 时代与地点/时代

覆盖 31 条。已读：31 个时代壳、地点与美学的时代映射、material_compatibility、names.yaml 及 fill_opening 的按时代命名路径。

处置依据与未解决项：30 条缺具体技术、地域或制度基线。近未来不自动包括星际航行；架空不是任意技术的兜底；部分时代标签实际上是事件或地点状态。只保留当代都市的普通民用背景用途，不因此认领某个都市框架。姓名表匹配不等于文化一致。

逐项定位：决策文件 review.scope 从 core_pool_unit:G04:001 到 core_pool_unit:G04:031。

<a id="G05"></a>

### G05 时代与地点/地点

覆盖 128 条。已读：128 个地点标签对应的 locations.yaml 全部细节、location_profiles.yaml 画像、location_eras 映射，以及 fill_opening 的细节/画像独立选择路径。

处置依据与未解决项：111 条保留具体空间缺口，1 条冻结。高层公寓没有证实高层出口；同一住宅画像混用公共楼道、阳台和私域；车库与消防通道不能共享未经验证的实际出口。16 条保留仅认可逐项记录的普通场所用途，部分时代范围已人工缩窄；不会把商业或公共画像作为私密、封闭或可任意开门的证明。

逐项定位：决策文件 review.scope 从 core_pool_unit:G05:001 到 core_pool_unit:G05:128。

2026-09-10 桥接闭合：111 条 BRIDGE_REQUIRED 逐项改判 KEEP_LEGACY（modes 按地点在两种开局均被抽取消费的事实授双模式——roll_opening.py:544-545 时代与地点无条件抽取、fill_opening.py:358-365 两模式都要求地点；owners 锚定 roll_opening.build_roll 地点抽取、fill_opening.load_tables 载入 locations 与 location_profiles、fill_opening.fill_opening 消费细节与画像写入 scene_profile、live_slice.extract_live_slice 与 opening_brief 续读，被框架实例化的地点追加 world_frameworks.prepare_tables places 按名称覆盖；eras 三档核定——31 条按 pools.yaml meta.location_eras 名单（roll_opening.py:546-567 抽取和解执行），78 条按实例化框架 era 并集绑定（world_frameworks.py:191-193 按名称覆盖该地点细节与画像），2 条（夜场会所、洗浴中心）无绑定源按细节语义核定现代商业营业五时代）。清晨菜市场细节限定清晨、天蒙蒙亮与压力叙述统一今晚错配（fill_opening.py:534、555）、密歇根湖畔私酒卸货码头 location_eras 含旧式民国都市（密歇根湖为一九二八芝加哥专属地理）、壬生屯所阴暗道场 location_eras 含明治东京（新选组建制属幕末），共 3 项记入源缺陷清单，不改源文件。16 条已闭合 KEEP_LEGACY 与 1 条冻结（学园祭打烊后的活动室）不动。

<a id="G06"></a>

### G06 社会规则

覆盖 30 条。已读：30 条规则、daily_opening.社会规则 与 fill_opening 的世界常量消费。

处置依据与未解决项：27 条缺适用主体、执行或退出机制。等级分明没有等级与流动制度；名声会被清算没有事实核验与后果。3 条保留限日常的人情互助、隐私约定和暂不追问，不授权资源特权、强制噤声或回避求助。

逐项定位：决策文件 review.scope 从 core_pool_unit:G06:001 到 core_pool_unit:G06:030。

<a id="G07"></a>

### G07 压力来源

覆盖 74 条。已读：全部压力条目、timed_pressures、material_compatibility.压力来源、roll_opening 的筛选/关键词与 fill_opening 的事件期限。

处置依据与未解决项：72 条需要桥接，2 条冻结，无直接保留。死线只剩几小时与统一八小时消费未对齐；债务到期缺债权事实与偿还路径；秘密即将暴露缺载体和具体窗口。后续必须把期限文本、事件 due_at 与实际触发证据对齐，不能只补一个主题标签。

逐项定位：决策文件 review.scope 从 core_pool_unit:G07:001 到 core_pool_unit:G07:074。

2026-09-10 桥接闭合：72 条 BRIDGE_REQUIRED 逐项改判 KEEP_LEGACY（modes 按压力来源仅在压力开局被消费的事实授 pressure 单模式——roll_opening.py:603-606 日常开局强制空串、fill_opening.py:361-363 校验空串；owners 锚定 roll_opening.build_roll 压力来源抽取与 fill_opening 压力来源写入；eras 按各条压力链的制度与技术依赖收窄，普适机制按全时代名单保留）。发电机燃油告罄 material_compatibility 名单含星际殖民地（星际缺燃油发电证据）、巡沙狼骑号角逼近名单含民国初年大漠荒城（现实向时代缺狼骑建制）、同人展压盘死线文本「三小时」与 timed 事件统一八小时期限错配，共 3 项记入源缺陷清单，不改源文件。2 条冻结（私密照外流、换脸视频外流）不动。

<a id="G08"></a>

### G08 场景动作/交易摊牌

覆盖 22 条。已读：22 条动作、templates.yaml 的 trade_beats 与建议、动作类别/元数据、roll_opening 的动作桶和 fill_opening.action_sentence。

处置依据与未解决项：15 条缺交易对象、许可或退出路径，2 条冻结。要求一个答复的模板先挡后路，与普通询问不同；开出一句价码缺对象与条款。5 条保留明确为 contrast_only，只作交易桶对照，不作为有效非交易未决动作，也不证明交易已经完成。

逐项定位：决策文件 review.scope 从 core_pool_unit:G08:001 到 core_pool_unit:G08:022。

<a id="G09"></a>

### G09 场景动作/非交易靠近

覆盖 91 条。已读：91 条动作的文本模板、玩家建议、action_categories.yaml、action_metadata.yaml、material_compatibility.场景动作、日常动作解释，以及动作填充和未决项验证消费者。

处置依据与未解决项：51 条桥接，13 条冻结。录音动作缺设备技术约束；开门动作未与行驶舱段、隔离场所的门禁连接；靠近出口坐下缺座位和真实出口。类别不能覆盖模板含义，例如锁门与退出/降压元数据不一致。7 条 KEEP_SHARED 限证据核验表达，20 条 KEEP_LEGACY 各自限定日常或压力用途，不把普通照护自动解释为接触许可。

逐项定位：决策文件 review.scope 从 core_pool_unit:G09:001 到 core_pool_unit:G09:091。

<a id="G10"></a>

### G10 身份侧

覆盖 17 条。已读：17 个身份族的全部 identities.yaml/npc 成员、identity_profiles.yaml 行为画像、identity_weights、material_compatibility.身份族 与按 seed 选成员的消费者。

处置依据与未解决项：13 个族需要成员级桥接，4 个族仅冻结，无整族保留。职业、设备和职责混装时，族级 metadata 不能覆盖每个成员；保护退出的子项也不能替其余子项背书。动力舱维修工的未来/太空映射与地下避难所燃油发电机、防爆门文本不一致。需要成员级时代、场所、职责和行为证据，不按族名挂框架。

逐项定位：决策文件 review.scope 从 core_pool_unit:G10:001 到 core_pool_unit:G10:017。

2026-09-10 桥接闭合：13 条 BRIDGE_REQUIRED 已按成员级证据改为 KEEP_LEGACY（交集时代 + consumer 定位），4 条冻结不动。成员级理由见决策文件各 review.reason。

<a id="G11"></a>

### G11 处境侧

覆盖 84 条。已读：84 个处境的完整 situation_beats、日常覆盖、timed_situations、引擎关联与 fill_opening.situation_bundle/事件消费。

处置依据与未解决项：65 条桥接，13 条冻结。债务模板含保护边界仍不能代替债权人与金额证据；秘密将破默认知情人要价，缺已发生的信息流；时限临门缺实际期限。6 条保留仅 daily_interpretation_only，指日常覆盖后的解释，不批准同名压力模板中的强制过夜、旁人安排等内容。

逐项定位：决策文件 review.scope 从 core_pool_unit:G11:001 到 core_pool_unit:G11:084。

<a id="G12"></a>

### G12 玩家化身轴/称谓

覆盖 26 条。已读：26 个称谓、时代与身份兼容信息、roll_opening 的独立抽取顺序、fill_opening 的玩家文本和命名路径。

处置依据与未解决项：25 条桥接。医生不能给非医师玩家赋予执业资格；老师没有与社会位置配对；直呼其名被写成字面称谓，缺名字替换。先生仅作为指定语言文化范围内成年男性玩家的普通敬称保留，不附加职业或关系权限。

逐项定位：决策文件 review.scope 从 core_pool_unit:G12:001 到 core_pool_unit:G12:026。

2026-09-10 桥接闭合：25 条 BRIDGE_REQUIRED 逐项改判 KEEP_LEGACY（modes 按称谓在 daily 与 pressure legacy 抽取均被消费的事实授双模式、owners 锚定 roll_opening.build_roll 称谓抽取与 fill_opening 玩家称谓写入、eras 按称谓文化范围收窄）；「直呼其名」缺名字替换机制、运行时按字面拼成「别人称你直呼其名」（fill_opening.py:526），记入源缺陷清单，不改源文件。

<a id="G13"></a>

### G13 玩家化身轴/社会位置

覆盖 31 条。已读：31 个位置的 identities.yaml/player 文本、character_meta.yaml 关系参数、material_compatibility.玩家社会位置、位置抽取与玩家填充消费者。

处置依据与未解决项：21 条桥接，7 条冻结。旧识的文本明确不知道对方是否可靠，却预设 trust=2；外来者被赋予未绑定场所的通行证与退路；同侪没有与 NPC 行业配对。合租室友、上司、相亲对象共 3 条仅保留文本与关系参数一致的定位，不把同住、职权或相亲当成额外许可。

逐项定位：决策文件 review.scope 从 core_pool_unit:G13:001 到 core_pool_unit:G13:031。

2026-09-10 桥接闭合：21 条 BRIDGE_REQUIRED 逐项改判 KEEP_LEGACY（modes 按社会位置在 daily 与 pressure legacy 抽取均被消费的事实授双模式、owners 锚定 roll_opening.build_roll 社会位置抽取与 fill_opening 玩家位置写入、eras 按画像建制收窄）；旧识 trust=2 与 reputation 矛盾、共同遗产继承人 type=family 预设血亲、搜刮队搭档与黑市药贩 material_compatibility 名单含画像不支持的时代、动力舱维修工名单与画像零交集（eras 收窄为空），共 5 项记入源缺陷清单，不改源文件。

## 消费者证据与待解决问题

| 证据位置 | 当前行为 | 审查影响 |
| --- | --- | --- |
| scripts/roll_opening.py:446 | 旧池 build_roll 消费入口 | 池单元进入抽取不等于框架归属 |
| scripts/roll_opening.py:592 | compatible_values 按 era/place 筛选，结果为空时回退原列表 | metadata 命中或存在不能证明约束一定生效 |
| scripts/roll_opening.py:634 | 按词组猜测引擎/处境主题 | 主题相似不等于事件因果和期限闭合 |
| scripts/roll_opening.py:645 | 在玩家社会位置生成前形成兼容报告 | 玩家位置约束可能未被该阶段检查覆盖 |
| scripts/roll_opening.py:726 | 称谓、社会位置各自抽取 | 职业称谓、权力与角色资源可能错配 |
| scripts/roll_opening.py:740 | 日常模式使用明确白名单和覆盖规则 | 15 条日常保留不能回填成压力版本批准 |
| scripts/fill_opening.py:116 | 按时代选名字 | 命名适配不解决技术、地理和文化基线 |
| scripts/fill_opening.py:299 | action_sentence 与后续玩家建议消费模板 | 必须对照真实动作，不只看类别名 |
| scripts/fill_opening.py:426 | 身份族内部按 seed 选成员 | 族级约束没有逐成员语义筛选 |
| scripts/fill_opening.py:437 | 地点细节和画像分别取值 | 共用画像不能保证每个具体场所的出口、访问和隐私 |
| scripts/fill_opening.py:457 | timed 项统一设为八小时 | 与秒/分钟/具体小时标签的期限需逐项对齐 |
| scripts/fill_opening.py:461 | 年龄数值设成人 | 不能仅凭数值消除学校或角色语境歧义 |
| scripts/fill_opening.py:465 | 日常分支替换处境 beat_table | 同名条目在两模式中的证据不能互换 |
| scripts/fill_opening.py:495 | 规则进入世界常量，压力分支自动附加代价 | 空泛规则缺执法者、范围和退出机制 |
| scripts/world_frameworks.py:22 | 框架包按候选名匹配 | 名称交集只证明候选存在 |
| scripts/world_frameworks.py:180 | 框架准备替换旧池人物、场所和模板 | 不能据同名候选认定旧正文已被完整复用 |
| scripts/check_material_compatibility.py:106 | REFERENCED 明示统计名称引用而非完整画像复用 | 引用覆盖率不是本次语义验收 |
| scripts/validate_state.py:414 | 检查未决动作结构 | 结构合法不等于语义、事实或许可成立 |

后续优先解决：真实期限与事件绑定；地点出口/门禁/隐私差异；身份成员级时代和职责；玩家称谓与社会位置配对；动作文本与分类/建议的一致性；压力与处境的事实因果。各条所缺的具体对象和证据已留在对应 review.reason，不能通过统一赋值或挂靠框架消除。保留项的限定也需要消费者实现或组合证据，才可用于进一步运行批准。

## 机械核验结果

以下只是格式、覆盖与 API 回归检查，不是语义正确性的替代证明。使用 python -X utf8 -B 在当前工作树中执行只读断言，没有调用脚本的写入 CLI，没有运行全套测试。

- YAML 顶层为列表，严格拒绝重复映射键；699 行、699 唯一 ID，精确等于当前 13 组核心池集合。
- 每条 source_hash、source 均与当前 units() 一致；699 条理由均非空且不同。
- 所有桥接/冻结行没有获批模式和所有者；46 条冻结行双标记完整。
- apply_decisions(sync({}, core), decisions, core) 成功；核心子集 audit(require_reviewed=True) 为 0 errors / 0 warnings。此门槛只确认已有处置记录，也接受 BRIDGE_REQUIRED，不能据此称桥接问题已闭合。
- 在完整当前 2,374 单元的空白内存目录上应用成功，普通 audit 为 0 errors / 1 warning；剩余 1,675 非核心单元为 NOT_REVIEWED，这是隔离验证的预期值，不是正式目录审查结论。
- 在当前正式 registry 的内存副本上应用成功，未写回。严格 audit 拒绝通过：REVIEW_GATE，尚有 1,573 单元 NOT_REVIEWED。快照含 2,389 条记录、2,374 当前单元；这些总数可能随其他任务正常变化。
- 输入 registry 和 decisions 均保持不变；篡改 source_hash 的决策被 Stale or unknown decision 拒绝。
- 本次未宣称运行消费者测试或实玩通过，未撤销全目录严格门槛。正式目录原 699 条核心记录在验证时仍为 NOT_REVIEWED。

## 依赖快照与失效边界

机器可读清单为 [core_review_dependencies.yaml](core_review_dependencies.yaml)，严格使用 version: 1 / files: {仓库相对路径: SHA-256}。哈希针对磁盘实际字节，不做换行或 YAML 规范化；文件缺失或哈希变化都应让本次证据失效，不能只更新哈希后继续应用旧决策。sync_governance 的核验由主任务接入，本次不修改其代码。

当前 source_hash 对池单元只散列其标量内容，不会自动绑定外部 metadata、画像、模板或消费者代码。即使池名不变，以下依赖改变也可能让语义证据失效。单独调用 apply_decisions 仍不会读取本 map，集成入口必须先检查依赖，再应用逐项 hash/source 绑定；两项检查不能互相替代。

清单采用本次实际审查依据的最小文件集合：10 个源数据/兼容数据文件，6 个运行消费者或共享加载器。包含 pools.yaml 本体，是因为同一文件还含兼容 metadata、日常覆盖和 timed 列表；不能只检查 699 个标量。补读 _common.py 的 load_yaml_bytes/load_yaml_file/load_data_yaml/load_sibling，确认数据和消费者的真实加载路径，故同时绑定该文件。build_opening 和 validate_state 分别绑定编排与运行状态检查，但检查存在仍不构成语义通过。

不纳入 material_registry.py、check_material_compatibility.py、maintenance/data_manifest.yaml 或 references/material_architecture.yaml：它们属于维护 API/契约、统计报告或非运行文档，不是这 699 条内容判断的依据。前文对统计报告的引用仅用于说明引用覆盖不等于语义审查；维护 API 字段迁移按当前合同另做机械校验。

不纳入 world_frameworks.yaml：本次没有将任何旧池条目认领到框架，也没有对框架包正文给出批准。保留 world_frameworks.py 是为了绑定框架替换旧表的消费边界。此清单不是整个应用的所有传递依赖、框架审查依赖或发布回归范围，不应由此推导未列文件已通过审查。

2026-09-10 漂移记录：主任务修复 fill_opening.py 两处缺陷——constants 组装对源句尾句号去重（L496-497 rstrip，仅标点归一，不改变 G01/G06 规则语义判断）与 knowledge_gap 模板语病（L600「说哪一层」→「告诉你到哪一步」，消除楼层误读，不改变 G10/G11 语义）。全量测试 290 项通过佐证；699 条评审理由不受影响。依赖表 fill_opening.py 行同步更新。

审查过程中其他任务删除了两个非核心处境模板；核对确认不属于本次 84 个核心处境，核心对应模板未变。下表记录该变化后的字节快照；最终核验时 16 项均与机器清单和工作树一致。后续发生漂移应定位受影响批次并复审，不可机械刷新哈希。决策主文件内容没有因新增依赖清单而改变。

| 路径 | SHA-256 |
| --- | --- |
| `scripts/_common.py` | `98283fb233533773baee31e67ff8931d3f8d56029b68a4aab0ce05e356271b94` |
| `scripts/build_opening.py` | `4503ed32ba379509ff18ee67953e0696a23ab6044d5732d3a08a34068c44dd5d` |
| `scripts/data/action_categories.yaml` | `933abd18aad6d876f3dc36f958af07615c4b3a3d6c6f9ce141d3bc04ef51f24f` |
| `scripts/data/action_metadata.yaml` | `87161b91a9f891ae251b9b5988c79a49962363be2607221e51b7453522bbd974` |
| `scripts/data/character_meta.yaml` | `feeaab984e7819fd3ff0a771cf57c1a62bd0f95b58579d73fdf34349a270c791` |
| `scripts/data/identities.yaml` | `d9d28e13011481ace29b0be731153651afd765ab09a8c42c77b0a40d4cf59ed7` |
| `scripts/data/identity_profiles.yaml` | `47005b328e9f38f44b845222fb2ad8320bf2d58498d993688506a8aaa1a90870` |
| `scripts/data/location_profiles.yaml` | `9a2c4c4bd6f7fd1948a608b8ca90908ebc5f67f6f35570fd5a5d520d658c09f8` |
| `scripts/data/locations.yaml` | `4c1a973cc12acaf327664b7d9033d81e153e52351ef1164bef0bf32d019e7793` |
| `scripts/data/names.yaml` | `5989b214d9a846f549f532a14537e15cb91e6f6718c0690985ae397b8a8676d0` |
| `scripts/data/pools.yaml` | `00bdbecf9fa56ad48766c7ead08b84f0329aeb8cec441ed858c6ab04686ab11f` |
| `scripts/data/templates.yaml` | `9de0b9198da06d35d087858e0c8f3682e505765dbdc3540b7ba9b7694b4ec1a5` |
| `scripts/fill_opening.py` | `e9eb6cf76221b5ab7c2f0239c25202cac572b076b316f6f099f512ba07fe47c1` |
| `scripts/roll_opening.py` | `8069c70095f81a8bf355d862d9d20e42baa924f481e852dbbbabdfd68aeeb624` |
| `scripts/validate_state.py` | `303640c3c65770cc94a77101b2e0e52b1b76353d508cab9ab904ee9c545eda8c` |
| `scripts/world_frameworks.py` | `e48a2857e831d2f112646cb0e3bca0cc4f1ff7b4907211ca857b7c4eb2e3d259` |

### 依赖漂移记录（2026-09-10 第二批）

旧识 trust 下调、共同遗产继承人 estate 化、玩家社会位置 compat 名单收窄与 fill_opening 称谓句修复（含句号归一、appellation_text 改写）已落盘；core_review_dependencies.yaml 四文件哈希同步刷新（character_meta a8136851…、identities c67915f0…、pools a5efa300…、fill_opening cca7d05e…）。受影响单元均属非核心 identity/pools 波次，已按刷新哈希重新核定落库；G01-G13 核心批次绑定语义不受影响（这些修复不触及其 owners/modes 依据）。G07 压力来源批次同日闭合（72 KEEP_LEGACY + 2 FROZEN 未动），BRIDGE_REQUIRED 569→438。


### G04/G06 桥接闭合（2026-09-10）

G04 时代 30 桥（G04:001、003-031）与 G06 社会规则 27 桥（G06:001-007、009、011-019、021-030）全部闭合为 KEEP_LEGACY（disposition unit_scope_only，reviewer dsh/governance-bridge-g04-g06，片段 maintenance/bridge_fragments/g04_g06.yaml 程序化合并）。modes 按消费实证：G04 全部与 G06 行会自治为 [daily,pressure]（roll_opening.py:544 无条件抽时代、fill_opening.py:358-365 两模式必填、行会自治为 meta.daily_opening.社会规则 白名单唯一桥接单元）；G06 其余 26 条为 [pressure]（roll_opening.py:588 全池抽取、日常白名单排除）。owners 时代单元 6 锚、社会规则 2-3 锚（build_roll/fill_opening/world_frameworks.build#eras）。needs_source_fix 空：location_eras/aesthetic_eras/material_compatibility/names.eras/40 框架 eras/daily_opening 全量交叉验证无悬空引用，40 框架自建 social_rule 与 27 池标签零重合。

### 依赖漂移记录（2026-09-10 第三批）

G07 needs_source_fix 三项落盘：压盘句子时间修正（三处「仅剩三小时」→「近在眼前」，核心单元改名 mat-07bbad24→mat-50a51f67，旧单元 verified_direct 移除登记、decisions G07:073 行重绑定）、location_eras 收窄（密歇根码头去旧式民国都市、壬生道场去明治东京）、发电机/狼骑 compat 名单收窄。清晨菜市场 details 时段修正（天蒙蒙亮/清晨→深夜/凌晨前，兼容开局「今晚」叙述）。成年锚定源修五处（学园祭活动室、琴房试卷、娇矜作精小花、模范长女/小小姐、名门特聘家教）。非核心组级行与 pools meta 三表（timed_pressures/location_eras/material_compatibility）落库；names.given 按 P3 判 DEPRECATED 登记。core_review_dependencies.yaml 两度刷新（locations 180eb58f…、pools 05ca430b…）。BRIDGE_REQUIRED 轨迹：569→438（G07）→327（G05）→270（G04/G06）。

### G03 / G01+G02 / G11 / G08+G09 桥接闭合（2026-09-10）

G03 张力引擎 66 桥、G01 核心规则 44 桥、G02 美学基调 29 桥、G11 处境侧 65 桥、G08 交易摊牌 15 桥、G09 非交易靠近 51 桥全部改判 KEEP_LEGACY（合计 270；加 G04/G06 57，五波片段合并后核心 BRIDGE_REQUIRED 569→0 清零；id/source_hash/source 与 registry 逐字绑定，FROZEN 行全程未动）。modes 按消费实证：G02 全部+G01:018+G09:042/047+G04 全部+G06 行会自治为 [daily,pressure]，其余为 [pressure]——daily 白名单机制（roll_opening.py:745-764 apply_daily_roll 覆写+AnchorError 拒绝）三重拦截实证。restricted 合计 35：G11 权力处境 19 条（reason 含「不推导亲密许可」）、G09 身体靠近 16 条（按分类一致性保留）。G02 eras 23 条按 aesthetic_eras 收窄、G11 46 条按画像收窄、G01 六条硬绑定收窄（040/041 中式民俗、042/043 禁酒期、044/045 幕末）。

needs_source_fix 登记未改源（待实玩重跑窗口结束后统一处理）：①三池缺 compat 门禁——张力引擎/处境/核心规则(040-045) 无 meta.material_compatibility 节且 roll_opening.py:646-651 兼容检查不覆盖，时代强依赖条目可跨时代抽出（G03/G11/G01 独立发现同一缺口）；②fill_opening.py:719 far 事件字面拼接引擎名；③timed_situations 仅覆盖 22/65 处境且统一 8h 与文本时钟不符；④G02:010 雨夜霓虹/G01:025 记账二义性与 G02:011 旧年代质感基线提示；⑤G08/G09 十二项模板-元数据错位（action_categories.yaml:38+action_metadata.yaml:15 与锁门/调灯矛盾、施受方向 4 处、pools.yaml:979 老爷车到站语义、医疗断言 G08:013/016、建议句越权/代词 G09:065/071）。

### NSF 源修批次与第三轮重跑（2026-09-10）

按各桥接批次的 needs_source_fix 台账完成源侧修复，登记簿同步重放：①模板九处（教她一个身段/替她扶正防毒面罩/金樽/半板药片/衣领伤口的施受方向与医疗断言，猫耳发箍/宽大队服/干烙馍建议句越权与代词）；②把灯调暗归位日常接触、反手反锁包厢门归位身体靠近（空间与退出恢复 exit/deescalate 语义一致）；③司机提醒即将到站 places 移除黑帮教父防弹老爷车；④meta.timed_situations 由统一 8h 名单改为逐条时钟映射（密室暗槽排酒前三十秒 0.01h、洗刀水色变红 0.05h、颁奖礼候场二十分钟 0.33h、直播意外事故 0.5h、其余 8h；fill_opening.py:452-462 消费端兼容 list/dict）；⑤meta.material_compatibility 新增处境 65 条与核心规则 6 条 {eras:[...]} 契约门禁（张力引擎经 G03 核定为抽象轴、eras 恒空，不设门禁），roll_opening.py:646 兼容检查扩展至 处境/张力引擎/核心规则；⑥fill_opening.py:719 far 事件触发句去引擎名直拼；⑦31 框架第二人物组资源/限制差异化（pairs resource/limitation/resources/identity/baseline/relationship_reason，两组资源零交集）经 build_frameworks --write 重建，31 份 framework_reviews 源哈希同步，40/40 恢复可默认抽取。核心 BRIDGE_REQUIRED 维持 0，全库 errors 0/warnings 0；受影响单元按 history 快照重放（reviewer dsh/nsf-fix-2026-09-10）。张三池 compat 缺口中的 张力引擎 项经实证关闭：G03 全部 66 桥 compatibility.eras 为空、technology_boundary 声明抽象轴不绑定时代，时代强依赖由处境与压力来源门禁承载。协议 v3 第二轮 80 transcript（纯协议消融：材料为 NSF 前状态）归档 stale-input-v4/；第三轮全量重跑覆盖 40 框架 × daily/pressure，作为最终验收证据基线。
