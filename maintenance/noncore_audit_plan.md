# 非核心单元审查与重复簇补审计划（第 4 点执行方案）

目标：按读取频率审查 1,573 个 NOT_REVIEWED 非核心单元；补审 244 个未核定重复候选；共享事实不删、真重复才合并、限制条目只登记。

## 优先级（按消费路径的读取频率）

1. **P1 框架生成链**（读频最高）：world_frameworks.yaml 由 authoring/frameworks/ 聚合生成，其 depends_on（见 data_manifest.yaml）中的 identities.yaml 成员、location_profiles.yaml 画像、action_categories/metadata、character_pools、names、identity_profiles、templates、twist_profiles 中被 40 框架实际引用的单元。判定工具：`check_material_compatibility.py` 的 REFERENCED 统计（名称引用≠语义认证，仅作排序）。
2. **P2 legacy 抽取链**：仅被 roll_opening legacy 显式路径消费的单元（identities 成员、locations 细节、aesthetics、names、templates、twists）。
3. **P3 低频/不可达**：无消费者的候选 DEPRECATED（需 cleanup.marked_release+reason 或 policy verified_direct+regression_evidence）。

## 决策约定（沿用 699 核心审查的字段惯例）

- 状态机：NOT_REVIEWED → KEEP_LEGACY（consumer: 定位符 owners + modes + 收窄 compatibility）/ KEEP_SHARED（跨文件真实复用，canonical 指向）/ DEPRECATED（不可达，需清理证据）/ DUPLICATE（canonical 指向保留项）。
- 单元 source_hash 必须与 material_registry.units() 当前值一致；改源后 hash 变化须重新决策（apply_decisions 拒绝 stale）。
- registry 不被 runtime 加载：闭合=证据记录，不是运行时过滤器；默认入口仍只认已审框架。

## 重复簇补审（duplicate_reviews.yaml）

- `check_duplicates.py` 的三类候选：exact 列表重复（未核定即 unresolved）、near（file+path+values 匹配）、cross_file（files+path_prefixes）。
- 补审=往 maintenance/duplicate_reviews.yaml 增加决策条目：KEEP_DISTINCT（语义不同，共享事实不删）/ KEEP_INDEX_REFERENCE（跨文件同名索引指向）/ MERGE候选→真重复走源编辑+单测，改源须避开实玩录制窗口。
- 5 条已核定先例：orientations 近重复 KEEP_DISTINCT×1、跨文件同名 KEEP_INDEX_REFERENCE×4。

## 执行波次（每波子代理 + 主代理验收）

- 波次 A：P1 框架链单元（引用排序 top），同时补审 exact 重复簇（纯机械，先清零）。
- 波次 B：P2 legacy 链 + near/cross_file 重复簇语义裁定。
- 波次 C：P3 不可达候选 DEPRECATED（需 regression 证据）+ 收尾 audit。
- 每波验收：material_registry audit 无新错、sync_governance --write 通过、抽查 5 条 reason 具体性。

## 时序约束

实玩重跑（v3）进行期间禁止改 scripts/data/**与 authoring/**（context() 对源变化敏感，会作废录制中的 transcript）；重复簇若需 MERGE 改源，排到重跑窗口之后单独执行。
