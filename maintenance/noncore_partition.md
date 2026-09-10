# 非核心单元三波划分（NOT_REVIEWED → P1/P2/P3）

- 生成方式：只读静态分析（`material_registry.units()` + `references/material_registry.yaml` 状态 + `authoring/frameworks/*.yaml` 框架字段 + `roll_opening.py`/`fill_opening.py`/`world_frameworks.py` 消费链推演），未运行任何抽取。
- 判定基准：可达性事实优先；与 `maintenance/noncore_audit_plan.md` 的冲突见文末。

## 顶部统计

| 波次 | 单元数 | pools.yaml | world_frameworks.yaml | identities.yaml | location_profiles.yaml | locations.yaml | identity_profiles.yaml | 其他 |
|---|---|---|---|---|---|---|---|---|
| P1 框架链 | 983 | 0 | 0 | 11 | 738 | 123 | 56 | 55 |
| P2 legacy 链 | 588 | 45 | 2 | 37 | 30 | 5 | 63 | 406 |
| P3 不可达 | 2 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| 合计 | 1573 | | | | | | | |

按源文件完整分解：

- action_categories.yaml：共 7 = P1 6 / P2 1 / P3 0
- action_metadata.yaml：共 21 = P1 18 / P2 3 / P3 0
- character_meta.yaml：共 48 = P1 3 / P2 45 / P3 0
- character_pools.yaml：共 35 = P1 0 / P2 35 / P3 0
- identities.yaml：共 48 = P1 11 / P2 37 / P3 0
- identity_profiles.yaml：共 119 = P1 56 / P2 63 / P3 0
- location_profiles.yaml：共 768 = P1 738 / P2 30 / P3 0
- locations.yaml：共 128 = P1 123 / P2 5 / P3 0
- names.yaml：共 32 = P1 28 / P2 3 / P3 1
- pools.yaml：共 45 = P1 0 / P2 45 / P3 0
- templates.yaml：共 284 = P1 0 / P2 284 / P3 0
- twist_profiles.yaml：共 28 = P1 0 / P2 28 / P3 0
- twists.yaml：共 7 = P1 0 / P2 7 / P3 0
- world_frameworks.yaml：共 3 = P1 0 / P2 2 / P3 1

## P1 框架链清单

共 983 个单元：label（或子条目的所属键）被至少一个 `authoring/frameworks/*.yaml` 选择字段按 label 精确相等引用。按引用框架数降序。

| unit_id | label | 引用数 | 引用框架（≤5） |
|---|---|---|---|
| `mat-4d7b21a043e45da3b4bfaf4c32745870` | 社会位置关系/同侪 | 40 | 仙门山下百业镇、仙门藏书与驿镖、传媒编辑室与公开记录、千禧网络街坊、同人街区与录音协作 等40个 |
| `mat-fc559b54cfcd5e71aa549a2f0a121c84` | player/同侪 | 40 | 仙门山下百业镇、仙门藏书与驿镖、传媒编辑室与公开记录、千禧网络街坊、同人街区与录音协作 等40个 |
| `mat-ad8aa646c5215c638caf0e6c0b2444a1` | 调查与核验 | 35 | 仙门山下百业镇、仙门藏书与驿镖、传媒编辑室与公开记录、千禧网络街坊、同人街区与录音协作 等35个 |
| `mat-4a7601ec0a07568e9fdc6827377b99ec` | 调查与核验/escalation | 35 | 仙门山下百业镇、仙门藏书与驿镖、传媒编辑室与公开记录、千禧网络街坊、同人街区与录音协作 等35个 |
| `mat-63665857302c5075aa14f7f2338cc66c` | 调查与核验/function | 35 | 仙门山下百业镇、仙门藏书与驿镖、传媒编辑室与公开记录、千禧网络街坊、同人街区与录音协作 等35个 |
| `mat-ea5aa2f523635b2f829d3022d15322df` | 调查与核验/visibility | 35 | 仙门山下百业镇、仙门藏书与驿镖、传媒编辑室与公开记录、千禧网络街坊、同人街区与录音协作 等35个 |
| `mat-0009a1247d0f5d6c989b09e670d002a1` | 照护与修复 | 32 | 仙门山下百业镇、仙门藏书与驿镖、千禧网络街坊、同人街区与录音协作、后方邮路与灯火 等32个 |
| `mat-c362e4fe847a5f759f321278f0ae8557` | 照护与修复/escalation | 32 | 仙门山下百业镇、仙门藏书与驿镖、千禧网络街坊、同人街区与录音协作、后方邮路与灯火 等32个 |
| `mat-7bce7bd8bd825b33b1e8df7f48d87e72` | 照护与修复/function | 32 | 仙门山下百业镇、仙门藏书与驿镖、千禧网络街坊、同人街区与录音协作、后方邮路与灯火 等32个 |
| `mat-60d0e7f675f55be3994cbb2e89ff95a2` | 照护与修复/visibility | 32 | 仙门山下百业镇、仙门藏书与驿镖、千禧网络街坊、同人街区与录音协作、后方邮路与灯火 等32个 |
| `mat-6dbd4241ee7d5614965f179e9d52a7a0` | npc/服务与手艺 | 29 | 仙门山下百业镇、仙门藏书与驿镖、后方邮路与灯火、地下城安全层营地、地下管廊与城市修理局 等29个 |
| `mat-67848b99e10f50e695bd83e3a11af393` | 服务与手艺/conflict_response | 29 | 仙门山下百业镇、仙门藏书与驿镖、后方邮路与灯火、地下城安全层营地、地下管廊与城市修理局 等29个 |
| `mat-cf132c299375518d969b661935334b81` | 服务与手艺/evidence_habit | 29 | 仙门山下百业镇、仙门藏书与驿镖、后方邮路与灯火、地下城安全层营地、地下管廊与城市修理局 等29个 |
| `mat-011829b8cdba5e768cbb21da30932ed1` | 服务与手艺/exit_preference | 29 | 仙门山下百业镇、仙门藏书与驿镖、后方邮路与灯火、地下城安全层营地、地下管廊与城市修理局 等29个 |
| `mat-6569e4e1c2e15b358118ab79daa20db0` | 服务与手艺/follow_up_style | 29 | 仙门山下百业镇、仙门藏书与驿镖、后方邮路与灯火、地下城安全层营地、地下管廊与城市修理局 等29个 |
| `mat-dd7837dd3dbe5ca59be9c122c67fcc36` | 服务与手艺/negotiation_style | 29 | 仙门山下百业镇、仙门藏书与驿镖、后方邮路与灯火、地下城安全层营地、地下管廊与城市修理局 等29个 |
| `mat-243fe7192a4e5052b9d9412949e146fb` | 服务与手艺/public_private_shift | 29 | 仙门山下百业镇、仙门藏书与驿镖、后方邮路与灯火、地下城安全层营地、地下管廊与城市修理局 等29个 |
| `mat-a03e794158a55b2097d166f079880a30` | 服务与手艺/repair_style | 29 | 仙门山下百业镇、仙门藏书与驿镖、后方邮路与灯火、地下城安全层营地、地下管廊与城市修理局 等29个 |
| `mat-e00fb881a85c5e5dacd68b998dc1c9e3` | 日常接触 | 25 | 仙门山下百业镇、传媒编辑室与公开记录、千禧网络街坊、同人街区与录音协作、地下城安全层营地 等25个 |
| `mat-56a45e147bae52e081ce0e060c960aa3` | 日常接触/escalation | 25 | 仙门山下百业镇、传媒编辑室与公开记录、千禧网络街坊、同人街区与录音协作、地下城安全层营地 等25个 |
| `mat-45e67de683745efcb3a9f1c8e7989872` | 日常接触/function | 25 | 仙门山下百业镇、传媒编辑室与公开记录、千禧网络街坊、同人街区与录音协作、地下城安全层营地 等25个 |
| `mat-643a9b0cb6f55a1bbb2b9ea2fa008ad2` | 日常接触/visibility | 25 | 仙门山下百业镇、传媒编辑室与公开记录、千禧网络街坊、同人街区与录音协作、地下城安全层营地 等25个 |
| `mat-7b4abceaa1495274bd3da570e5efdc78` | 信息交换 | 23 | 传媒编辑室与公开记录、千禧网络街坊、同人街区与录音协作、地下城安全层营地、地方行业与公共记忆 等23个 |
| `mat-681bc8ba72c75a8f908ce405132d8efc` | 空间与退出 | 23 | 仙门藏书与驿镖、同人街区与录音协作、后方邮路与灯火、地方行业与公共记忆、城市休闲与共享会客 等23个 |
| `mat-d6ff344e918456189d6df3274a861012` | 信息交换/escalation | 23 | 传媒编辑室与公开记录、千禧网络街坊、同人街区与录音协作、地下城安全层营地、地方行业与公共记忆 等23个 |
| `mat-f8a1104f54f052569a6c4a384bb2a1cb` | 信息交换/function | 23 | 传媒编辑室与公开记录、千禧网络街坊、同人街区与录音协作、地下城安全层营地、地方行业与公共记忆 等23个 |
| `mat-88c3774f19d358d69ee38da32bb9dd44` | 信息交换/visibility | 23 | 传媒编辑室与公开记录、千禧网络街坊、同人街区与录音协作、地下城安全层营地、地方行业与公共记忆 等23个 |
| `mat-8ff6e388518e5a9182fe902ca2619840` | 空间与退出/escalation | 23 | 仙门藏书与驿镖、同人街区与录音协作、后方邮路与灯火、地方行业与公共记忆、城市休闲与共享会客 等23个 |
| `mat-868d80f5a71a58e69b9ca730cc54505b` | 空间与退出/function | 23 | 仙门藏书与驿镖、同人街区与录音协作、后方邮路与灯火、地方行业与公共记忆、城市休闲与共享会客 等23个 |
| `mat-f76c83c0afc05fca89e0b3d6f42dea7d` | 空间与退出/visibility | 23 | 仙门藏书与驿镖、同人街区与录音协作、后方邮路与灯火、地方行业与公共记忆、城市休闲与共享会客 等23个 |
| `mat-6ed4a91957265c35bc52a451b7a84f17` | npc/艺术与传播 | 17 | 传媒编辑室与公开记录、千禧网络街坊、同人街区与录音协作、地方行业与公共记忆、城市休闲与共享会客 等17个 |
| `mat-d75b32257c2753f7aa7dd82716178e7e` | 艺术与传播/conflict_response | 17 | 传媒编辑室与公开记录、千禧网络街坊、同人街区与录音协作、地方行业与公共记忆、城市休闲与共享会客 等17个 |
| `mat-b29bf1cca34b585ea578218398590e89` | 艺术与传播/evidence_habit | 17 | 传媒编辑室与公开记录、千禧网络街坊、同人街区与录音协作、地方行业与公共记忆、城市休闲与共享会客 等17个 |
| `mat-6eae8f0123015b5c8cc132a52c2f7915` | 艺术与传播/exit_preference | 17 | 传媒编辑室与公开记录、千禧网络街坊、同人街区与录音协作、地方行业与公共记忆、城市休闲与共享会客 等17个 |
| `mat-1e379991426c5d82b09d0f9dbb2dbd71` | 艺术与传播/follow_up_style | 17 | 传媒编辑室与公开记录、千禧网络街坊、同人街区与录音协作、地方行业与公共记忆、城市休闲与共享会客 等17个 |
| `mat-5b60042d182c5f8f8c602e2ca615fa2b` | 艺术与传播/negotiation_style | 17 | 传媒编辑室与公开记录、千禧网络街坊、同人街区与录音协作、地方行业与公共记忆、城市休闲与共享会客 等17个 |
| `mat-76855f97b1e451caaacf42e27ea1688a` | 艺术与传播/public_private_shift | 17 | 传媒编辑室与公开记录、千禧网络街坊、同人街区与录音协作、地方行业与公共记忆、城市休闲与共享会客 等17个 |
| `mat-bfbe2e68d8045ea2a2a13e3be414b526` | 艺术与传播/repair_style | 17 | 传媒编辑室与公开记录、千禧网络街坊、同人街区与录音协作、地方行业与公共记忆、城市休闲与共享会客 等17个 |
| `mat-78fde467705c50cea55e2d3628aae70c` | npc/学术与专业 | 12 | 仙门藏书与驿镖、千禧网络街坊、地下城安全层营地、夜校学分与开放实验室、成年创作者与校园艺术季 等12个 |
| `mat-740f0bfbd25455a5884107d73b52a163` | 学术与专业/conflict_response | 12 | 仙门藏书与驿镖、千禧网络街坊、地下城安全层营地、夜校学分与开放实验室、成年创作者与校园艺术季 等12个 |
| `mat-58e93c25abb65c1e86964b57776bb7b2` | 学术与专业/evidence_habit | 12 | 仙门藏书与驿镖、千禧网络街坊、地下城安全层营地、夜校学分与开放实验室、成年创作者与校园艺术季 等12个 |
| `mat-3ddb63bc7e975c159bd91a6096da37b9` | 学术与专业/exit_preference | 12 | 仙门藏书与驿镖、千禧网络街坊、地下城安全层营地、夜校学分与开放实验室、成年创作者与校园艺术季 等12个 |
| `mat-a545156a9bc85b78905695ee861313d7` | 学术与专业/follow_up_style | 12 | 仙门藏书与驿镖、千禧网络街坊、地下城安全层营地、夜校学分与开放实验室、成年创作者与校园艺术季 等12个 |
| `mat-da413a59b32a5fbd86303055725a7c5a` | 学术与专业/negotiation_style | 12 | 仙门藏书与驿镖、千禧网络街坊、地下城安全层营地、夜校学分与开放实验室、成年创作者与校园艺术季 等12个 |
| `mat-76e67c34aa7d53308e241771c3e2160b` | 学术与专业/public_private_shift | 12 | 仙门藏书与驿镖、千禧网络街坊、地下城安全层营地、夜校学分与开放实验室、成年创作者与校园艺术季 等12个 |
| `mat-72d9fed938275feca9a8b5935482c282` | 学术与专业/repair_style | 12 | 仙门藏书与驿镖、千禧网络街坊、地下城安全层营地、夜校学分与开放实验室、成年创作者与校园艺术季 等12个 |
| `mat-f49e614c0ad65784bc71681b73c3ce3f` | eras/当代都市 | 7 | 地下管廊与城市修理局、地方行业与公共记忆、城市休闲与共享会客、夜校学分与开放实验室、成年创作者与校园艺术季 等7个 |
| `mat-096c1fcc3757535195e606d493150ebd` | 社会位置关系/旧识 | 5 | 仙门山下百业镇、地下管廊与城市修理局、废墟复兴小镇、灵气复苏十年后、退休勇者之城 |
| `mat-c0db912abeee54c09ac99b40ec5d68a0` | player/旧识 | 5 | 仙门山下百业镇、地下管廊与城市修理局、废墟复兴小镇、灵气复苏十年后、退休勇者之城 |
| `mat-bd859437364e580397e83b22d275958f` | npc/语言与传译 | 4 | 契约城与非人街坊、明治洋裁与译书町、蜃景商路与鬼市、退休勇者之城 |
| `mat-6d43d0db1fba5a179cb80a9606b573c5` | 语言与传译/conflict_response | 4 | 契约城与非人街坊、明治洋裁与译书町、蜃景商路与鬼市、退休勇者之城 |
| `mat-d44e753b6df3550b90a18ba6280570cd` | 语言与传译/evidence_habit | 4 | 契约城与非人街坊、明治洋裁与译书町、蜃景商路与鬼市、退休勇者之城 |
| `mat-8917a4e82f075d229c711b2ebd9f72ea` | 语言与传译/exit_preference | 4 | 契约城与非人街坊、明治洋裁与译书町、蜃景商路与鬼市、退休勇者之城 |
| `mat-fa74c50938fe567196822504e941fbdf` | 语言与传译/follow_up_style | 4 | 契约城与非人街坊、明治洋裁与译书町、蜃景商路与鬼市、退休勇者之城 |
| `mat-11f55b23117b520a96539b6bfbd3ff6d` | 语言与传译/negotiation_style | 4 | 契约城与非人街坊、明治洋裁与译书町、蜃景商路与鬼市、退休勇者之城 |
| `mat-faa3e758bb9e5a31ae7e44dc62c6290b` | 语言与传译/public_private_shift | 4 | 契约城与非人街坊、明治洋裁与译书町、蜃景商路与鬼市、退休勇者之城 |
| `mat-a548b67d49f051b0bd5d34da9b72c3f1` | 语言与传译/repair_style | 4 | 契约城与非人街坊、明治洋裁与译书町、蜃景商路与鬼市、退休勇者之城 |
| `mat-4529e434dbcd573293f717cef2d5ac37` | 工作室/affordances | 4 | 千禧网络街坊、寒冬避难所公共生活、星海边境生活站、磁带与夜市街区 |
| `mat-36b8f2e0c6b254f5acc3b19f42c46bdb` | 工作室/exits | 4 | 千禧网络街坊、寒冬避难所公共生活、星海边境生活站、磁带与夜市街区 |
| `mat-941877ed25e75a8e8f6f4369e9e6cba8` | 工作室/pressure_modifiers | 4 | 千禧网络街坊、寒冬避难所公共生活、星海边境生活站、磁带与夜市街区 |
| `mat-0303a5b1ad1f5e7cac822e90de60bd20` | 工作室/privacy | 4 | 千禧网络街坊、寒冬避难所公共生活、星海边境生活站、磁带与夜市街区 |
| `mat-5243a719a0bd577884cabac6dae18275` | 工作室/visibility | 4 | 千禧网络街坊、寒冬避难所公共生活、星海边境生活站、磁带与夜市街区 |
| `mat-a99fc0d16ec0540fa41bce282440c7b2` | 工作室/witnesses | 4 | 千禧网络街坊、寒冬避难所公共生活、星海边境生活站、磁带与夜市街区 |
| `mat-998484bd74b759e2b519641924f1ceac` | 工作室 | 4 | 千禧网络街坊、寒冬避难所公共生活、星海边境生活站、磁带与夜市街区 |
| `mat-1eb1b2f8afe555dab10265d6badf480d` | 第三方与打断 | 3 | 城市休闲与共享会客、成年创作者与校园艺术季、检疫站旁的生活区 |
| `mat-7359a8a2ec8b5c1886ca1331bdfbac89` | 第三方与打断/escalation | 3 | 城市休闲与共享会客、成年创作者与校园艺术季、检疫站旁的生活区 |
| `mat-f10bbfe66b855083896e2dd338aff8bc` | 第三方与打断/function | 3 | 城市休闲与共享会客、成年创作者与校园艺术季、检疫站旁的生活区 |
| `mat-0b3ab110d37a5595a988bd11eb8b56a3` | 第三方与打断/visibility | 3 | 城市休闲与共享会客、成年创作者与校园艺术季、检疫站旁的生活区 |
| `mat-12e465ed3e665b73a0e84abfcf73197a` | 家中厨房/affordances | 3 | 检疫站旁的生活区、磁带与夜市街区、街角共同生活圈 |
| `mat-4ab367d856cc577cac4e2b0917c1fc97` | 家中厨房/exits | 3 | 检疫站旁的生活区、磁带与夜市街区、街角共同生活圈 |
| `mat-2dc32221d9a951ea89f4f8ef9bc4a407` | 家中厨房/pressure_modifiers | 3 | 检疫站旁的生活区、磁带与夜市街区、街角共同生活圈 |
| `mat-9776088b84345505a1e88b4d434296db` | 家中厨房/privacy | 3 | 检疫站旁的生活区、磁带与夜市街区、街角共同生活圈 |
| `mat-95237fca8e2f5da68ecb03605393e041` | 家中厨房/visibility | 3 | 检疫站旁的生活区、磁带与夜市街区、街角共同生活圈 |
| `mat-51d3f5712e1756cdb43c3ebaed27a6c2` | 家中厨房/witnesses | 3 | 检疫站旁的生活区、磁带与夜市街区、街角共同生活圈 |
| `mat-6ae935ed1ed05279a19a5938368342c8` | 家中厨房 | 3 | 检疫站旁的生活区、磁带与夜市街区、街角共同生活圈 |
| `mat-3966eb4c368454e98ad432168722d4dd` | 社会位置关系/外来者 | 2 | 夜校学分与开放实验室、河岸康复与互助居所 |
| `mat-27e2b04fd4d351d592ec2dcadf2f3c40` | npc/医疗与照护 | 2 | 河岸康复与互助居所、灵气复苏十年后 |
| `mat-75f2277dabb755a890dd501309ab9b32` | npc/商业与产业 | 2 | 星海边境生活站、王都工坊与委托街 |
| `mat-7b1594c9495a5381b6c6d0b6f59f43f6` | player/外来者 | 2 | 夜校学分与开放实验室、河岸康复与互助居所 |
| `mat-9fccbcdc277c5a2b8b60e38236be6072` | 医疗与照护/conflict_response | 2 | 河岸康复与互助居所、灵气复苏十年后 |
| `mat-03e3d3c5acc05418a328edfaa810f725` | 医疗与照护/evidence_habit | 2 | 河岸康复与互助居所、灵气复苏十年后 |
| `mat-735e779dc6f5528ab5db04b8bd7333f7` | 医疗与照护/exit_preference | 2 | 河岸康复与互助居所、灵气复苏十年后 |
| `mat-dc154b9d86a858f1b96a7334162f2f8c` | 医疗与照护/follow_up_style | 2 | 河岸康复与互助居所、灵气复苏十年后 |
| `mat-ee0fbaba8d4b5b92b7ce3009c271484a` | 医疗与照护/negotiation_style | 2 | 河岸康复与互助居所、灵气复苏十年后 |
| `mat-e2000a0d581554799d9d3bec5ee4a148` | 医疗与照护/public_private_shift | 2 | 河岸康复与互助居所、灵气复苏十年后 |
| `mat-5f99b2e1743b50c08eeb82a5196df23a` | 医疗与照护/repair_style | 2 | 河岸康复与互助居所、灵气复苏十年后 |
| `mat-cad9adfd480854e680bbfbba618985ce` | 商业与产业/conflict_response | 2 | 星海边境生活站、王都工坊与委托街 |
| `mat-7a5e95e98c1d5a898b5191f65ce172f5` | 商业与产业/evidence_habit | 2 | 星海边境生活站、王都工坊与委托街 |
| `mat-aa2aaf90c78155f3973bdcd3f3015646` | 商业与产业/exit_preference | 2 | 星海边境生活站、王都工坊与委托街 |
| `mat-4c382e328d7e5ece82c13ad3d4b4b250` | 商业与产业/follow_up_style | 2 | 星海边境生活站、王都工坊与委托街 |
| `mat-586c3d501532586db159a81abbb274dd` | 商业与产业/negotiation_style | 2 | 星海边境生活站、王都工坊与委托街 |
| `mat-90183b31527059958686f9aa34120fc5` | 商业与产业/public_private_shift | 2 | 星海边境生活站、王都工坊与委托街 |
| `mat-b8741911d5e35ad7905e0271ac237a56` | 商业与产业/repair_style | 2 | 星海边境生活站、王都工坊与委托街 |
| `mat-893262e993cc5777a48779c61b95e8f2` | 图书馆/affordances | 2 | 地下城安全层营地、星海边境生活站 |
| `mat-e9a7cbc2d16d59ad8e86dc652cfb209c` | 图书馆/exits | 2 | 地下城安全层营地、星海边境生活站 |
| `mat-e626e045e66354d9b6a62150f6c5fd48` | 图书馆/pressure_modifiers | 2 | 地下城安全层营地、星海边境生活站 |
| `mat-a2fa69ca6b8652f2ab966a6b59054307` | 图书馆/privacy | 2 | 地下城安全层营地、星海边境生活站 |
| `mat-50a077e1fa5455b4b7f803cb1b52117c` | 图书馆/visibility | 2 | 地下城安全层营地、星海边境生活站 |
| `mat-7d2a99412156591787d7d72abbbac041` | 图书馆/witnesses | 2 | 地下城安全层营地、星海边境生活站 |
| `mat-2d528d6799a75e35897b2829c65a2806` | 夜班值班室/affordances | 2 | 后方邮路与灯火、检疫站旁的生活区 |
| `mat-15a7bb168fe551e0a593bf3d12d7335d` | 夜班值班室/exits | 2 | 后方邮路与灯火、检疫站旁的生活区 |
| `mat-c04c7927f8c15cd1a793eef7773124dd` | 夜班值班室/pressure_modifiers | 2 | 后方邮路与灯火、检疫站旁的生活区 |
| `mat-15a1333c310456d3804d3308cc94a54f` | 夜班值班室/privacy | 2 | 后方邮路与灯火、检疫站旁的生活区 |
| `mat-456ecc928d8455deb663bf57ad4140c2` | 夜班值班室/visibility | 2 | 后方邮路与灯火、检疫站旁的生活区 |
| `mat-9fe1f156ef655c839cedda380405f88f` | 夜班值班室/witnesses | 2 | 后方邮路与灯火、检疫站旁的生活区 |
| `mat-e6bbf7c3a2c85f6e9481dbed289f3ddc` | 寺庙后院/affordances | 2 | 旧町神怪与灯会、湘西山路与乡志 |
| `mat-926b6a37f59659239fc7971b44cfb9b0` | 寺庙后院/exits | 2 | 旧町神怪与灯会、湘西山路与乡志 |
| `mat-a4d14fa1bd7356fd803f360973f5ae0a` | 寺庙后院/pressure_modifiers | 2 | 旧町神怪与灯会、湘西山路与乡志 |
| `mat-eb4246b979775409b93a01d5d1711a4f` | 寺庙后院/privacy | 2 | 旧町神怪与灯会、湘西山路与乡志 |
| `mat-036edbe478fa56f7b755dea263918b58` | 寺庙后院/visibility | 2 | 旧町神怪与灯会、湘西山路与乡志 |
| `mat-c34a671478c858d2a6c903f46e91f0f6` | 寺庙后院/witnesses | 2 | 旧町神怪与灯会、湘西山路与乡志 |
| `mat-807adc05b48b5e38844a82b50652883b` | 幸存者地下避难所/affordances | 2 | 寒冬避难所公共生活、废土驿站与修补集市 |
| `mat-64f9002689ef5afb995671d021a1c9de` | 幸存者地下避难所/exits | 2 | 寒冬避难所公共生活、废土驿站与修补集市 |
| `mat-4c0311e843855af5a36b74252d67123c` | 幸存者地下避难所/pressure_modifiers | 2 | 寒冬避难所公共生活、废土驿站与修补集市 |
| `mat-e0ffda0029aa59bc80504f0b4dc297d9` | 幸存者地下避难所/privacy | 2 | 寒冬避难所公共生活、废土驿站与修补集市 |
| `mat-0e757337e2645a76a7721c3b704c222b` | 幸存者地下避难所/visibility | 2 | 寒冬避难所公共生活、废土驿站与修补集市 |
| `mat-3ea8220582f55948936cffaaaf0888ac` | 幸存者地下避难所/witnesses | 2 | 寒冬避难所公共生活、废土驿站与修补集市 |
| `mat-7082164809db589eb2f65e05959a271f` | 录音棚控制室/affordances | 2 | 传媒编辑室与公开记录、同人街区与录音协作 |
| `mat-c58c13cebac4584f923bf259e305436c` | 录音棚控制室/exits | 2 | 传媒编辑室与公开记录、同人街区与录音协作 |
| `mat-9049bb68a38b5946ab043560616b1bfc` | 录音棚控制室/pressure_modifiers | 2 | 传媒编辑室与公开记录、同人街区与录音协作 |
| `mat-13fcd98dccf35607a123dc0d414f9663` | 录音棚控制室/privacy | 2 | 传媒编辑室与公开记录、同人街区与录音协作 |
| `mat-c36c310dcdb05ce593242be4cb0365df` | 录音棚控制室/visibility | 2 | 传媒编辑室与公开记录、同人街区与录音协作 |
| `mat-4fd823cc0d5d524ca75fba1c2c57ff8a` | 录音棚控制室/witnesses | 2 | 传媒编辑室与公开记录、同人街区与录音协作 |
| `mat-d3a8b3f5e76e55bf9ca05c1a5ad15ee2` | 旧书店/affordances | 2 | 千禧网络街坊、磁带与夜市街区 |
| `mat-c9730ce7c6a95c8b8eea2d14349b0857` | 旧书店/exits | 2 | 千禧网络街坊、磁带与夜市街区 |
| `mat-aedd94041e1c55bc9357a2e9dc685a70` | 旧书店/pressure_modifiers | 2 | 千禧网络街坊、磁带与夜市街区 |
| `mat-171f6305232e5f85a7118a1ca8ee81a2` | 旧书店/privacy | 2 | 千禧网络街坊、磁带与夜市街区 |
| `mat-7c933dc211e15421951315384a8d24aa` | 旧书店/visibility | 2 | 千禧网络街坊、磁带与夜市街区 |
| `mat-1ba690e58ef3529491ca1dce28bef874` | 旧书店/witnesses | 2 | 千禧网络街坊、磁带与夜市街区 |
| `mat-8e55d500729e57669b45a12cfd86bc5d` | 破败义庄/affordances | 2 | 湘西山路与乡志、风沙驿站与旧图 |
| `mat-547924f3a4bc5cae94b6ad057f7f4fcf` | 破败义庄/exits | 2 | 湘西山路与乡志、风沙驿站与旧图 |
| `mat-81070e45b8fe5b1eb1147393066c111e` | 破败义庄/pressure_modifiers | 2 | 湘西山路与乡志、风沙驿站与旧图 |
| `mat-1d083b6a45a45b17a5b5720fe69287e6` | 破败义庄/privacy | 2 | 湘西山路与乡志、风沙驿站与旧图 |
| `mat-3f94356485265d9d886a022eaf0ca7b0` | 破败义庄/visibility | 2 | 湘西山路与乡志、风沙驿站与旧图 |
| `mat-c9b373cc1aa45349b3adf7d510e6d822` | 破败义庄/witnesses | 2 | 湘西山路与乡志、风沙驿站与旧图 |
| `mat-d20203e5a6475f3a9a607a2d2b70aad0` | 老字号客栈/affordances | 2 | 后方邮路与灯火、地下城安全层营地 |
| `mat-c661e0009f995291b658ab13b78e0f88` | 老字号客栈/exits | 2 | 后方邮路与灯火、地下城安全层营地 |
| `mat-5e42f4b2ee865680a290dd061839f949` | 老字号客栈/pressure_modifiers | 2 | 后方邮路与灯火、地下城安全层营地 |
| `mat-4f92a3e901bb5ebc875c6c81e1e6ca55` | 老字号客栈/privacy | 2 | 后方邮路与灯火、地下城安全层营地 |
| `mat-5359784e42305da898fbc619a1f96234` | 老字号客栈/visibility | 2 | 后方邮路与灯火、地下城安全层营地 |
| `mat-ddaf52d4cb7d50d9bce7c07223eb258a` | 老字号客栈/witnesses | 2 | 后方邮路与灯火、地下城安全层营地 |
| `mat-2d52cba882af562fac50dbaa1b404700` | 迷宫中层安全屋/affordances | 2 | 地下城安全层营地、王都工坊与委托街 |
| `mat-30a5ba16eb4559babf0ba4c4f9480a11` | 迷宫中层安全屋/exits | 2 | 地下城安全层营地、王都工坊与委托街 |
| `mat-a4b2e350ad0b545ea2468985f0db1ceb` | 迷宫中层安全屋/pressure_modifiers | 2 | 地下城安全层营地、王都工坊与委托街 |
| `mat-6cb4aa3a6c5d552f89fd48b2a8137d5d` | 迷宫中层安全屋/privacy | 2 | 地下城安全层营地、王都工坊与委托街 |
| `mat-a6c4a0622cab5013b17bd3bb05383295` | 迷宫中层安全屋/visibility | 2 | 地下城安全层营地、王都工坊与委托街 |
| `mat-60ee19b220be541e815d0e84f9801251` | 迷宫中层安全屋/witnesses | 2 | 地下城安全层营地、王都工坊与委托街 |
| `mat-bc30fa859a1d56e1ba7866ca91d176dc` | 图书馆 | 2 | 地下城安全层营地、星海边境生活站 |
| `mat-68b31b957d9654f688ae9a8653d96e35` | 夜班值班室 | 2 | 后方邮路与灯火、检疫站旁的生活区 |
| `mat-8d398fc823ea5e739ec33b831c1d762e` | 寺庙后院 | 2 | 旧町神怪与灯会、湘西山路与乡志 |
| `mat-719a1c99ee1354cabe860eadd014f7d4` | 幸存者地下避难所 | 2 | 寒冬避难所公共生活、废土驿站与修补集市 |
| `mat-789062e921b35bbfb1103285b51c838e` | 录音棚控制室 | 2 | 传媒编辑室与公开记录、同人街区与录音协作 |
| `mat-532dd32e903055879ec5e7b447ec5077` | 旧书店 | 2 | 千禧网络街坊、磁带与夜市街区 |
| `mat-fb7c7dc16574551b8f1ca7af77aa0f24` | 破败义庄 | 2 | 湘西山路与乡志、风沙驿站与旧图 |
| `mat-40ed3cd453c952e3a1bcc99b7010ce40` | 老字号客栈 | 2 | 后方邮路与灯火、地下城安全层营地 |
| `mat-9b539dc0cd7a55998a1d03ab0db56bf9` | 迷宫中层安全屋 | 2 | 地下城安全层营地、王都工坊与委托街 |
| `mat-d2ab045da7f5564d9528972e06d59505` | eras/东方玄幻大陆 | 2 | 仙门山下百业镇、仙门藏书与驿镖 |
| `mat-7ace16d450205136983f7a73accca130` | eras/废土末世 | 2 | 废土驿站与修补集市、废墟复兴小镇 |
| `mat-7f57a7b0fca4558cb6b25fac0527fb60` | npc/动物与驯养 | 1 | 仙门山下百业镇 |
| `mat-392b48487c1b58e89b4e8ebe224098f1` | npc/权力与治理 | 1 | 长安夜市与坊志 |
| `mat-bb241231e75b5abf922c1a02493c8199` | 动物与驯养/conflict_response | 1 | 仙门山下百业镇 |
| `mat-09143a24ed9354648525b86923458dd0` | 动物与驯养/evidence_habit | 1 | 仙门山下百业镇 |
| `mat-845cf5d2a6965a80a7413d3d83dc46fa` | 动物与驯养/exit_preference | 1 | 仙门山下百业镇 |
| `mat-9794fe71c8c258e0b17bc8f87dba281b` | 动物与驯养/follow_up_style | 1 | 仙门山下百业镇 |
| `mat-eaaf947bceea5d499bb6267d8dc752e4` | 动物与驯养/negotiation_style | 1 | 仙门山下百业镇 |
| `mat-95961781a368586ca295af6d3507b114` | 动物与驯养/public_private_shift | 1 | 仙门山下百业镇 |
| `mat-b4c7f2d99cfb5f79ad1bf1d66f495990` | 动物与驯养/repair_style | 1 | 仙门山下百业镇 |
| `mat-8be0c24f27a65861869d2e86149afb4b` | 权力与治理/conflict_response | 1 | 长安夜市与坊志 |
| `mat-b9b78a6d39795366b1ea825e33e50036` | 权力与治理/evidence_habit | 1 | 长安夜市与坊志 |
| `mat-96506d949bd95ccf909fb94847fb3de1` | 权力与治理/exit_preference | 1 | 长安夜市与坊志 |
| `mat-b61ce54312dd5cd8ac8d4d890ac6da0d` | 权力与治理/follow_up_style | 1 | 长安夜市与坊志 |
| `mat-feb40ef064f45f88a54d08a210d76809` | 权力与治理/negotiation_style | 1 | 长安夜市与坊志 |
| `mat-bf487fc3b2fb595aa07852e069b28c6e` | 权力与治理/public_private_shift | 1 | 长安夜市与坊志 |
| `mat-e2cc656598d85276a538f512bd7e6286` | 权力与治理/repair_style | 1 | 长安夜市与坊志 |
| `mat-a155763af91052bcb09d954de83bb26f` | 24小时自习室/affordances | 1 | 成年创作者与校园艺术季 |
| `mat-c20b8b9a189653259cb068f9c540504f` | 24小时自习室/exits | 1 | 成年创作者与校园艺术季 |
| `mat-f447b76c1c5e5aa48a181136f1d25488` | 24小时自习室/pressure_modifiers | 1 | 成年创作者与校园艺术季 |
| `mat-39df95541e3a553bb5171d1cc82a1de1` | 24小时自习室/privacy | 1 | 成年创作者与校园艺术季 |
| `mat-a036abe7f8755ffd85d36b238fcaa8ab` | 24小时自习室/visibility | 1 | 成年创作者与校园艺术季 |
| `mat-fdcc7a8dbdc8517992b7b54f616f7d28` | 24小时自习室/witnesses | 1 | 成年创作者与校园艺术季 |
| `mat-c9899653990e5d13a3b0894ffffba942` | 24小时自助洗衣房/affordances | 1 | 街角共同生活圈 |
| `mat-51bfd77b05505d978628c12d18a9c985` | 24小时自助洗衣房/exits | 1 | 街角共同生活圈 |
| `mat-d3c96d6d42c550668698cd810618fc68` | 24小时自助洗衣房/pressure_modifiers | 1 | 街角共同生活圈 |
| `mat-e15cf485dae45429af128a68ce20213b` | 24小时自助洗衣房/privacy | 1 | 街角共同生活圈 |
| `mat-e4378abff8d45e6a8c902c23c089a4c1` | 24小时自助洗衣房/visibility | 1 | 街角共同生活圈 |
| `mat-6c0feb2561c25358b8e43291465c349b` | 24小时自助洗衣房/witnesses | 1 | 街角共同生活圈 |
| `mat-25a102b38e145eaf93f16c40b559d013` | Cosplay暗房/affordances | 1 | 同人街区与录音协作 |
| `mat-b47343b7d1505e34b3d26caf9263df9c` | Cosplay暗房/exits | 1 | 同人街区与录音协作 |
| `mat-f1e3c9b036085b70be47387a2ad87fab` | Cosplay暗房/pressure_modifiers | 1 | 同人街区与录音协作 |
| `mat-522b0e97553b51da803701ceb27f5867` | Cosplay暗房/privacy | 1 | 同人街区与录音协作 |
| `mat-84393c0096ba5a1e90c8fc96bfe3ec86` | Cosplay暗房/visibility | 1 | 同人街区与录音协作 |
| `mat-86e0d65c993d532280b4806a8787cb82` | Cosplay暗房/witnesses | 1 | 同人街区与录音协作 |
| `mat-df60f36f00b65a87b621d377aa5d3ce8` | livehouse/affordances | 1 | 地方行业与公共记忆 |
| `mat-7d1e10257ef45a70bc074d235e560959` | livehouse/exits | 1 | 地方行业与公共记忆 |
| `mat-2a8c00f3c64d544d98a167576b6d8d71` | livehouse/pressure_modifiers | 1 | 地方行业与公共记忆 |
| `mat-895e6836a25e514785c8ab3ed1374e59` | livehouse/privacy | 1 | 地方行业与公共记忆 |
| `mat-1838774cc79a5567af86c383575dde13` | livehouse/visibility | 1 | 地方行业与公共记忆 |
| `mat-e3f639ce982e5d5fb0f28c85b6bf931a` | livehouse/witnesses | 1 | 地方行业与公共记忆 |
| `mat-5b55828aaa4151b9b2e4ee81549ca7ba` | 倒悬石梁地宫/affordances | 1 | 风沙驿站与旧图 |
| `mat-29254a0f8258577b8058b7314cd32a9d` | 倒悬石梁地宫/exits | 1 | 风沙驿站与旧图 |
| `mat-f5f92b66be9450e5b55bd29ada2259b7` | 倒悬石梁地宫/pressure_modifiers | 1 | 风沙驿站与旧图 |
| `mat-ebde0a9c65635cbf83e1db4a4f53970f` | 倒悬石梁地宫/privacy | 1 | 风沙驿站与旧图 |
| `mat-3c53fe44a9a553bc8312ab819d26d00c` | 倒悬石梁地宫/visibility | 1 | 风沙驿站与旧图 |
| `mat-b8c5e217198d5d7b8e086ee6c5e09fc9` | 倒悬石梁地宫/witnesses | 1 | 风沙驿站与旧图 |
| `mat-6c586cc49a0655be983134699f6690da` | 偏远小镇唯一便利店/affordances | 1 | 远途休假与小镇停留 |
| `mat-ebf25544beaa5c1a9d7784bb5a8a88dd` | 偏远小镇唯一便利店/exits | 1 | 远途休假与小镇停留 |
| `mat-e16d0d71322458e58643b8ab5268bfe6` | 偏远小镇唯一便利店/pressure_modifiers | 1 | 远途休假与小镇停留 |
| `mat-0c0278d3bc2a50ae92148d995d96421d` | 偏远小镇唯一便利店/privacy | 1 | 远途休假与小镇停留 |
| `mat-cd50642eef5f55ce86682240d508a619` | 偏远小镇唯一便利店/visibility | 1 | 远途休假与小镇停留 |
| `mat-a66077d5d7b951c7ad2a900da8adb873` | 偏远小镇唯一便利店/witnesses | 1 | 远途休假与小镇停留 |
| `mat-cc5197b467225d8dbc322b86a596a315` | 停电民宿客厅/affordances | 1 | 远途休假与小镇停留 |
| `mat-e405678f732b56c8a5eba8e788327628` | 停电民宿客厅/exits | 1 | 远途休假与小镇停留 |
| `mat-50a8c8798c0354b486de73514dcc2add` | 停电民宿客厅/pressure_modifiers | 1 | 远途休假与小镇停留 |
| `mat-bf0a26556fa7576ab47deed90f81435a` | 停电民宿客厅/privacy | 1 | 远途休假与小镇停留 |
| `mat-12daa63c3cef58c9b01c2b4a0b92bc2d` | 停电民宿客厅/visibility | 1 | 远途休假与小镇停留 |
| `mat-8f2a6e60d52a50eda5b4874d3eec2627` | 停电民宿客厅/witnesses | 1 | 远途休假与小镇停留 |
| `mat-0dcc609c2de9588fa6a713919f656830` | 健身房/affordances | 1 | 城市休闲与共享会客 |
| `mat-7b723f75095a51f3b78367953bcae190` | 健身房/exits | 1 | 城市休闲与共享会客 |
| `mat-43c845feae3c5468b7f3580903803be7` | 健身房/pressure_modifiers | 1 | 城市休闲与共享会客 |
| `mat-74e2b4b3c00f5607acbf04c660e5fe05` | 健身房/privacy | 1 | 城市休闲与共享会客 |
| `mat-680f6db8134156c18318ea2d4af6e3cd` | 健身房/visibility | 1 | 城市休闲与共享会客 |
| `mat-4ef33e5f43c95a1a90842535dc6da148` | 健身房/witnesses | 1 | 城市休闲与共享会客 |
| `mat-5146ce0ddaf05fb8853f9f4cd0121937` | 全息酒吧/affordances | 1 | 赛博街区与公共终端 |
| `mat-e707628eea7f56c9be34d9c4dd06ba05` | 全息酒吧/exits | 1 | 赛博街区与公共终端 |
| `mat-d14c67f525f158bb9006a8feec161451` | 全息酒吧/pressure_modifiers | 1 | 赛博街区与公共终端 |
| `mat-65c2ed89816f5b308111591bc5e28647` | 全息酒吧/privacy | 1 | 赛博街区与公共终端 |
| `mat-5c0b4e7b08e95f459492c02b41cf9342` | 全息酒吧/visibility | 1 | 赛博街区与公共终端 |
| `mat-5dd2407f34d752819943cb35857ea9ea` | 全息酒吧/witnesses | 1 | 赛博街区与公共终端 |
| `mat-38eb6b1e82a854ad9b31115ea799893b` | 写字楼/affordances | 1 | 赛博街区与公共终端 |
| `mat-3ce91838919456a9b6faf67da4d518cb` | 写字楼/exits | 1 | 赛博街区与公共终端 |
| `mat-aac7973266395b45a793f74a9690619d` | 写字楼/pressure_modifiers | 1 | 赛博街区与公共终端 |
| `mat-470e6dd8249551799f26bc41510477cd` | 写字楼/privacy | 1 | 赛博街区与公共终端 |
| `mat-3f3fa4b986ca5cf0b7ec3b26748a6f40` | 写字楼/visibility | 1 | 赛博街区与公共终端 |
| `mat-9c4c9c2992cc5d4bae669f27dbb558f6` | 写字楼/witnesses | 1 | 赛博街区与公共终端 |
| `mat-cc83f548e01f5aa4ba3c8b63a13479ed` | 列车车厢/affordances | 1 | 千禧网络街坊 |
| `mat-276240deaa605e0bb3d800d2f7b3f401` | 列车车厢/exits | 1 | 千禧网络街坊 |
| `mat-70413296880a5edab0995857bf497225` | 列车车厢/pressure_modifiers | 1 | 千禧网络街坊 |
| `mat-4a17d8c7620d5fd687cdb12bda68c592` | 列车车厢/privacy | 1 | 千禧网络街坊 |
| `mat-02c62d1548fb5d158bd97be00c8d2a3f` | 列车车厢/visibility | 1 | 千禧网络街坊 |
| `mat-70fe311eb8ce5229859a98e1a0f3e125` | 列车车厢/witnesses | 1 | 千禧网络街坊 |
| `mat-6f132d41192f55ccaa113e5e16df8d86` | 剧院后台/affordances | 1 | 成年创作者与校园艺术季 |
| `mat-e78ff47fa4ac5b18aa46210321a0e54c` | 剧院后台/exits | 1 | 成年创作者与校园艺术季 |
| `mat-82f07e1fd439574bb70f84785e9df0d8` | 剧院后台/pressure_modifiers | 1 | 成年创作者与校园艺术季 |
| `mat-8a75ea1aede35e83b9f0f942d86854a4` | 剧院后台/privacy | 1 | 成年创作者与校园艺术季 |
| `mat-ae03ae549e645a779416f37f3327062a` | 剧院后台/visibility | 1 | 成年创作者与校园艺术季 |
| `mat-bbac6bb50c3b5649a7d3acdde78ddf07` | 剧院后台/witnesses | 1 | 成年创作者与校园艺术季 |
| `mat-6c2632795ebe5d9ea88c521534b709e9` | 医院住院部走廊/affordances | 1 | 地方行业与公共记忆 |
| `mat-54e8dd54a316509fa68db0d1bdf037c8` | 医院住院部走廊/exits | 1 | 地方行业与公共记忆 |
| `mat-33abd3c46a37548196925ebabda00276` | 医院住院部走廊/pressure_modifiers | 1 | 地方行业与公共记忆 |
| `mat-23902c4f13f756c8a523c2bd2edef41b` | 医院住院部走廊/privacy | 1 | 地方行业与公共记忆 |
| `mat-7850195db7a959cbad7d80825b47dd1d` | 医院住院部走廊/visibility | 1 | 地方行业与公共记忆 |
| `mat-6c44ad5fc021547a877d7b2ca5e3ec03` | 医院住院部走廊/witnesses | 1 | 地方行业与公共记忆 |
| `mat-bff5f0b56f7a5906af99da3e5fcff0a4` | 医馆后堂/affordances | 1 | 湘西山路与乡志 |
| `mat-20aeaca5bfd35c159e78421607161cd7` | 医馆后堂/exits | 1 | 湘西山路与乡志 |
| `mat-10488fb42f565b0caec5581780225afb` | 医馆后堂/pressure_modifiers | 1 | 湘西山路与乡志 |
| `mat-05b05147fa41554cb85684db709041ad` | 医馆后堂/privacy | 1 | 湘西山路与乡志 |
| `mat-c0286d779b2057448f742277ed719153` | 医馆后堂/visibility | 1 | 湘西山路与乡志 |
| `mat-29120cb3cd0b5e0aa4a55bbee70f72bd` | 医馆后堂/witnesses | 1 | 湘西山路与乡志 |
| `mat-899bfea6d2375688816be8f96bab4ecf` | 古籍书店/affordances | 1 | 王朝百业与书院 |
| `mat-ee4a2def0ef050b0821b36baf532b407` | 古籍书店/exits | 1 | 王朝百业与书院 |
| `mat-fa2c64b9c9935e2b8e17cb83e28da09a` | 古籍书店/pressure_modifiers | 1 | 王朝百业与书院 |
| `mat-fb7831882181574287f17518dbc8816b` | 古籍书店/privacy | 1 | 王朝百业与书院 |
| `mat-bac9e17a01615e568bfffdf4b519bb73` | 古籍书店/visibility | 1 | 王朝百业与书院 |
| `mat-47ad803ae1025573bd840313f2c1c1f6` | 古籍书店/witnesses | 1 | 王朝百业与书院 |
| `mat-25244b0c55c2587a9556f1509834d089` | 同人展备用更衣室/affordances | 1 | 同人街区与录音协作 |
| `mat-50a85fb685f654629187946f346e45a2` | 同人展备用更衣室/exits | 1 | 同人街区与录音协作 |
| `mat-5658a66eabe25808bb495df5b91cb64c` | 同人展备用更衣室/pressure_modifiers | 1 | 同人街区与录音协作 |
| `mat-117da46210ea52768416cedee52a0a2a` | 同人展备用更衣室/privacy | 1 | 同人街区与录音协作 |
| `mat-96eb350ffc6a5a98b3861bf713bea916` | 同人展备用更衣室/visibility | 1 | 同人街区与录音协作 |
| `mat-3b5576a312b05879a11a798e64cf2fb9` | 同人展备用更衣室/witnesses | 1 | 同人街区与录音协作 |
| `mat-2d49a2ba1b21510091e62b70153bc97a` | 回程前的空车站/affordances | 1 | 远途休假与小镇停留 |
| `mat-6b4c809856f450029147812f4f4c84ad` | 回程前的空车站/exits | 1 | 远途休假与小镇停留 |
| `mat-5ad2969d951d5b08a868f3df506f579e` | 回程前的空车站/pressure_modifiers | 1 | 远途休假与小镇停留 |
| `mat-e8127b1c08e75179ba44b6bbba5e0569` | 回程前的空车站/privacy | 1 | 远途休假与小镇停留 |
| `mat-2e37e706c1a753c8aaec48a326e451a6` | 回程前的空车站/visibility | 1 | 远途休假与小镇停留 |
| `mat-4bc42fbbaca050f799a3d47d8acb91ad` | 回程前的空车站/witnesses | 1 | 远途休假与小镇停留 |
| `mat-62534c73940e52f395b04b44df854a40` | 团地走廊/affordances | 1 | 昭和街角喫茶巡礼 |
| `mat-2557b107f642558691667ac723d4725d` | 团地走廊/exits | 1 | 昭和街角喫茶巡礼 |
| `mat-162e8b58022a5fa29089c1989ed9a98d` | 团地走廊/pressure_modifiers | 1 | 昭和街角喫茶巡礼 |
| `mat-2e86164c16315c24813ad008df9aba01` | 团地走廊/privacy | 1 | 昭和街角喫茶巡礼 |
| `mat-faf1f06f2a34539f922f65204d6edd8f` | 团地走廊/visibility | 1 | 昭和街角喫茶巡礼 |
| `mat-eba8c1b7eeb75410b4c4d1164c279be4` | 团地走廊/witnesses | 1 | 昭和街角喫茶巡礼 |
| `mat-921c7435379156b5827bba1f17163bf3` | 园林/affordances | 1 | 王朝百业与书院 |
| `mat-4ccbcd6b71ba516f886291944048b817` | 园林/exits | 1 | 王朝百业与书院 |
| `mat-8ead1ec157485776ae0d4fb392bff760` | 园林/pressure_modifiers | 1 | 王朝百业与书院 |
| `mat-56a8cfebdce15cf4af54a601b0f2a193` | 园林/privacy | 1 | 王朝百业与书院 |
| `mat-1484530c680756dfa5599413949a83db` | 园林/visibility | 1 | 王朝百业与书院 |
| `mat-20d18f26267756c1a8f319023e0b4e08` | 园林/witnesses | 1 | 王朝百业与书院 |
| `mat-f654651c5282522e8a656838bb1bfd19` | 城隍庙后院/affordances | 1 | 长安夜市与坊志 |
| `mat-c4d2cc8bd96a5058a5a0822e1509e1c3` | 城隍庙后院/exits | 1 | 长安夜市与坊志 |
| `mat-473cc395bff95ea7b4061d5f72ca11d2` | 城隍庙后院/pressure_modifiers | 1 | 长安夜市与坊志 |
| `mat-33bccbd912ed55fc93792dc37bc54156` | 城隍庙后院/privacy | 1 | 长安夜市与坊志 |
| `mat-d8f3fb032e0a5148a1e36adf97f1dc60` | 城隍庙后院/visibility | 1 | 长安夜市与坊志 |
| `mat-d42305e107685fdb9fbbbd0590b111b9` | 城隍庙后院/witnesses | 1 | 长安夜市与坊志 |
| `mat-cad39b6e26825287abe28def6280bacb` | 壬生屯所阴暗道场/affordances | 1 | 幕末町屋与道场 |
| `mat-f7b126953a125533803f2719e1ac0258` | 壬生屯所阴暗道场/exits | 1 | 幕末町屋与道场 |
| `mat-4c70a4960b6d56be8edcddf25887548b` | 壬生屯所阴暗道场/pressure_modifiers | 1 | 幕末町屋与道场 |
| `mat-407481fae4915050882a4da59b6184b7` | 壬生屯所阴暗道场/privacy | 1 | 幕末町屋与道场 |
| `mat-47ca708bff985ac597d592cf42da302f` | 壬生屯所阴暗道场/visibility | 1 | 幕末町屋与道场 |
| `mat-baf2b8837f845bb5afbf33692a936e8e` | 壬生屯所阴暗道场/witnesses | 1 | 幕末町屋与道场 |
| `mat-16fc0cbc4ce654ae9840662494b883ad` | 声优录音棚/affordances | 1 | 同人街区与录音协作 |
| `mat-cdd35db68da75d499f965e1852936f14` | 声优录音棚/exits | 1 | 同人街区与录音协作 |
| `mat-23e8e4b473e358cc9eb5f9e0f1375da4` | 声优录音棚/pressure_modifiers | 1 | 同人街区与录音协作 |
| `mat-c6f522cce0065db3ba7aa1edd77f01c3` | 声优录音棚/privacy | 1 | 同人街区与录音协作 |
| `mat-40a00d67fd125ac9a6da890e735b2b53` | 声优录音棚/visibility | 1 | 同人街区与录音协作 |
| `mat-8b9e18984a125e07ad0a1af01ae7bc04` | 声优录音棚/witnesses | 1 | 同人街区与录音协作 |
| `mat-f28f035a3bbc58aca03176c868701c3f` | 夜航渡轮/affordances | 1 | 海岸渡船与观测旅行 |
| `mat-bc34f7415095567e8bf7770adcc79d85` | 夜航渡轮/exits | 1 | 海岸渡船与观测旅行 |
| `mat-35aa749593125b898e7232e0ae951a1a` | 夜航渡轮/pressure_modifiers | 1 | 海岸渡船与观测旅行 |
| `mat-81d1f6e447c45813bda3e77b6c343345` | 夜航渡轮/privacy | 1 | 海岸渡船与观测旅行 |
| `mat-f6e81c0e72a6583ca24996fae939c753` | 夜航渡轮/visibility | 1 | 海岸渡船与观测旅行 |
| `mat-00fc9c6dbec85619b46e85cc13e34332` | 夜航渡轮/witnesses | 1 | 海岸渡船与观测旅行 |
| `mat-e53cd28031975b7285fffae5935557a6` | 大学钢琴练习室/affordances | 1 | 成年创作者与校园艺术季 |
| `mat-4daaca25322f57ba8e2004f7161daed4` | 大学钢琴练习室/exits | 1 | 成年创作者与校园艺术季 |
| `mat-66fa1f39c3905a268c0bbf92b55d557d` | 大学钢琴练习室/pressure_modifiers | 1 | 成年创作者与校园艺术季 |
| `mat-351e40838a0e5ef9ada1af9ca2db8a46` | 大学钢琴练习室/privacy | 1 | 成年创作者与校园艺术季 |
| `mat-6f25fb8e00565253aa450c80ed8d714c` | 大学钢琴练习室/visibility | 1 | 成年创作者与校园艺术季 |
| `mat-f0dfff7729685bcea8afdc6b5f12efe0` | 大学钢琴练习室/witnesses | 1 | 成年创作者与校园艺术季 |
| `mat-ad3df44e8d745e9babe24fdcafa55ecd` | 大雁塔顶避风藏经阁/affordances | 1 | 长安夜市与坊志 |
| `mat-1d475f4890685c719d32f1012cf9de4f` | 大雁塔顶避风藏经阁/exits | 1 | 长安夜市与坊志 |
| `mat-e2719b7beb4553f08bd1bb7b5f826fc2` | 大雁塔顶避风藏经阁/pressure_modifiers | 1 | 长安夜市与坊志 |
| `mat-920e7bb17c2f555b83790d2719a61a18` | 大雁塔顶避风藏经阁/privacy | 1 | 长安夜市与坊志 |
| `mat-0c8e3ebdbfeb54da85cedca5913150a4` | 大雁塔顶避风藏经阁/visibility | 1 | 长安夜市与坊志 |
| `mat-578ab6078e625a1785c511d78ac7f624` | 大雁塔顶避风藏经阁/witnesses | 1 | 长安夜市与坊志 |
| `mat-0871bd15efc75d969cfd92d747227b79` | 太空站舱段/affordances | 1 | 星海边境生活站 |
| `mat-a16491d7e5c05635b0f8aa897a56667f` | 太空站舱段/exits | 1 | 星海边境生活站 |
| `mat-7c0ae90f00755e409795ab99dd5e6a5c` | 太空站舱段/pressure_modifiers | 1 | 星海边境生活站 |
| `mat-13b8357f0e145d659c51247ffa434ebd` | 太空站舱段/privacy | 1 | 星海边境生活站 |
| `mat-76a0c383a5415c32910312d45b473950` | 太空站舱段/visibility | 1 | 星海边境生活站 |
| `mat-9a024fc8928b57acaf83d31b22e2b731` | 太空站舱段/witnesses | 1 | 星海边境生活站 |
| `mat-63d923a4eb6a52efb37e9b97fc289bf3` | 契约登记所/affordances | 1 | 契约城与非人街坊 |
| `mat-642f7d65ea2e5e1683c6a6a9791d10ab` | 契约登记所/exits | 1 | 契约城与非人街坊 |
| `mat-121cb919e70b571dbfba3b9360c06bc6` | 契约登记所/pressure_modifiers | 1 | 契约城与非人街坊 |
| `mat-f54c3a358c75503f9456f0717af19a60` | 契约登记所/privacy | 1 | 契约城与非人街坊 |
| `mat-c0f82047049e5831aff20d741e9f1694` | 契约登记所/visibility | 1 | 契约城与非人街坊 |
| `mat-ba998df1b9855df4b210fd39452c5df3` | 契约登记所/witnesses | 1 | 契约城与非人街坊 |
| `mat-3c21332fe9ad52489649249ae3a2b245` | 女仆咖啡厅后厨/affordances | 1 | 同人街区与录音协作 |
| `mat-594d02ea8eca50e784934bd809e9a69f` | 女仆咖啡厅后厨/exits | 1 | 同人街区与录音协作 |
| `mat-6c776cd76ecb5231ac21a9cd806e76d7` | 女仆咖啡厅后厨/pressure_modifiers | 1 | 同人街区与录音协作 |
| `mat-6cf5c6a18317536dbc3eeabad9463dec` | 女仆咖啡厅后厨/privacy | 1 | 同人街区与录音协作 |
| `mat-6c1e88e3730d53cb9ba580fa2725f53d` | 女仆咖啡厅后厨/visibility | 1 | 同人街区与录音协作 |
| `mat-ad0f7111fb5253e0a429e441b36b6c40` | 女仆咖啡厅后厨/witnesses | 1 | 同人街区与录音协作 |
| `mat-a1f3c33faa4a58ce86b912a71f37e7b9` | 婚礼宴会厅/affordances | 1 | 城市休闲与共享会客 |
| `mat-5436da5cb3fe520599dd24ce3ab7ed2b` | 婚礼宴会厅/exits | 1 | 城市休闲与共享会客 |
| `mat-77003075141956a0b3a96c39f77c88c6` | 婚礼宴会厅/pressure_modifiers | 1 | 城市休闲与共享会客 |
| `mat-0731dc07a43d5637942a51c1dda6c8b1` | 婚礼宴会厅/privacy | 1 | 城市休闲与共享会客 |
| `mat-392d2063195856149d275b4585650509` | 婚礼宴会厅/visibility | 1 | 城市休闲与共享会客 |
| `mat-9dcfe6f48e665a7d85e02d37b1a85507` | 婚礼宴会厅/witnesses | 1 | 城市休闲与共享会客 |
| `mat-1f829c5f0a2056b0b95657bc25b40ec5` | 学园祭打烊后的活动室/affordances | 1 | 成年创作者与校园艺术季 |
| `mat-53aaf35570285651a38ca5250c489814` | 学园祭打烊后的活动室/exits | 1 | 成年创作者与校园艺术季 |
| `mat-7ec9a77d8859590bbcaaedb1ae3daeff` | 学园祭打烊后的活动室/pressure_modifiers | 1 | 成年创作者与校园艺术季 |
| `mat-8691b9f53a595070af9631e6c40b8438` | 学园祭打烊后的活动室/privacy | 1 | 成年创作者与校园艺术季 |
| `mat-ec060c210ec75c1f8e5dd1c5ba1538e6` | 学园祭打烊后的活动室/visibility | 1 | 成年创作者与校园艺术季 |
| `mat-52ad7f85c94658aaa6d64014eca20735` | 学园祭打烊后的活动室/witnesses | 1 | 成年创作者与校园艺术季 |
| `mat-43d5ed5a0e9d590286f1a6bddb67da89` | 宗族祠堂/affordances | 1 | 王朝百业与书院 |
| `mat-ad12d09d82e25a3db68c9eb21c3410d1` | 宗族祠堂/exits | 1 | 王朝百业与书院 |
| `mat-f2eaf59fe336561a94a6d6646456446c` | 宗族祠堂/pressure_modifiers | 1 | 王朝百业与书院 |
| `mat-3f00655bec8b52a9ab4b49dbd3eded79` | 宗族祠堂/privacy | 1 | 王朝百业与书院 |
| `mat-02b86fc2861851d08946c82db2bcfb57` | 宗族祠堂/visibility | 1 | 王朝百业与书院 |
| `mat-69f5bd19ca2a57ea90a0218dba64190c` | 宗族祠堂/witnesses | 1 | 王朝百业与书院 |
| `mat-84f39db4899f5671a1be825db601d20c` | 宠物医院/affordances | 1 | 地方行业与公共记忆 |
| `mat-6040690715725fb59a878897a5955bc6` | 宠物医院/exits | 1 | 地方行业与公共记忆 |
| `mat-3a021d0200295c07a0653f107c88e855` | 宠物医院/pressure_modifiers | 1 | 地方行业与公共记忆 |
| `mat-8c951c5b2f0e507c8d887958d6e93469` | 宠物医院/privacy | 1 | 地方行业与公共记忆 |
| `mat-c66704fd46f55dfeacb0e1178b9cf994` | 宠物医院/visibility | 1 | 地方行业与公共记忆 |
| `mat-8e22b2ceac1f507890311c21cb5a595d` | 宠物医院/witnesses | 1 | 地方行业与公共记忆 |
| `mat-b4709ca32c825c5f80547856316bce26` | 室内夜泳馆/affordances | 1 | 城市休闲与共享会客 |
| `mat-1ad54c8389985bf4a38d2d2608e001b2` | 室内夜泳馆/exits | 1 | 城市休闲与共享会客 |
| `mat-6bf18b4aebf15dacb1cadc7b1bd1a52d` | 室内夜泳馆/pressure_modifiers | 1 | 城市休闲与共享会客 |
| `mat-c5505df5db7456efb644ad8307cf8103` | 室内夜泳馆/privacy | 1 | 城市休闲与共享会客 |
| `mat-0ea88a2b5ae55cbcaaf68ddaf5c1a74e` | 室内夜泳馆/visibility | 1 | 城市休闲与共享会客 |
| `mat-a3b47c9288f95453a4800660e48184d1` | 室内夜泳馆/witnesses | 1 | 城市休闲与共享会客 |
| `mat-f9d41865986559dcb3564f98d8487cf9` | 密歇根湖畔私酒卸货码头/affordances | 1 | 禁酒期爵士与报纸 |
| `mat-d4026aec4759573b98fa5e688cc761a4` | 密歇根湖畔私酒卸货码头/exits | 1 | 禁酒期爵士与报纸 |
| `mat-bf938cc00b645078a315657c77fd5422` | 密歇根湖畔私酒卸货码头/pressure_modifiers | 1 | 禁酒期爵士与报纸 |
| `mat-71410cb381765dd8b41efd6771ad4e78` | 密歇根湖畔私酒卸货码头/privacy | 1 | 禁酒期爵士与报纸 |
| `mat-23ee0550cba159748cb0dd71e7f98c7b` | 密歇根湖畔私酒卸货码头/visibility | 1 | 禁酒期爵士与报纸 |
| `mat-e5c8e18c5e455c4baf26195b0fc8b713` | 密歇根湖畔私酒卸货码头/witnesses | 1 | 禁酒期爵士与报纸 |
| `mat-bde5b61aa7a454fda58c442d9353c48b` | 山间温泉旅馆/affordances | 1 | 旧町神怪与灯会 |
| `mat-1591eb6cec2650d68b56099697b577ef` | 山间温泉旅馆/exits | 1 | 旧町神怪与灯会 |
| `mat-b94411a421a9504f9bcc4e7b7e0fcfbc` | 山间温泉旅馆/pressure_modifiers | 1 | 旧町神怪与灯会 |
| `mat-a1e9e2b5b72d5880ba27f379baa076de` | 山间温泉旅馆/privacy | 1 | 旧町神怪与灯会 |
| `mat-787c386338195cf0a44e2d63922c839b` | 山间温泉旅馆/visibility | 1 | 旧町神怪与灯会 |
| `mat-fdc2ac1cec5f57638101ad565764da58` | 山间温泉旅馆/witnesses | 1 | 旧町神怪与灯会 |
| `mat-1a7c1685faa750519e6b4a77b307f383` | 山顶观星台/affordances | 1 | 海岸渡船与观测旅行 |
| `mat-3b21c04a0eec5e9d9b087299ed60228c` | 山顶观星台/exits | 1 | 海岸渡船与观测旅行 |
| `mat-40b3550c66925188bfcc253110692cde` | 山顶观星台/pressure_modifiers | 1 | 海岸渡船与观测旅行 |
| `mat-51e3de814f465689ad99a319e2a0c5c0` | 山顶观星台/privacy | 1 | 海岸渡船与观测旅行 |
| `mat-ceba7ce0c1c1592b930ea43f7c8bfe5c` | 山顶观星台/visibility | 1 | 海岸渡船与观测旅行 |
| `mat-b32c42198c79528b9b779644c89df832` | 山顶观星台/witnesses | 1 | 海岸渡船与观测旅行 |
| `mat-75f79813d82f5d76a9d4eeeb04867967` | 帽店试帽间/affordances | 1 | 雾都钟表与港务街 |
| `mat-c7a4a6631465598ba6c90a5dc3180514` | 帽店试帽间/exits | 1 | 雾都钟表与港务街 |
| `mat-953068d128955ba897828ba0fe833933` | 帽店试帽间/pressure_modifiers | 1 | 雾都钟表与港务街 |
| `mat-be4dba86eb73558ca7779dc3a6c39b11` | 帽店试帽间/privacy | 1 | 雾都钟表与港务街 |
| `mat-a72748b5d8df52f89f0b22f1a1be7e5c` | 帽店试帽间/visibility | 1 | 雾都钟表与港务街 |
| `mat-3871b01f766c5ad4b5dc61d8b191a5f9` | 帽店试帽间/witnesses | 1 | 雾都钟表与港务街 |
| `mat-7c10e84181935d85bfd5e874a06ac669` | 废土驿站/affordances | 1 | 废土驿站与修补集市 |
| `mat-5f013e36d1485a28ab0266e76383b081` | 废土驿站/exits | 1 | 废土驿站与修补集市 |
| `mat-e0504b8ed859540cb95401b684054072` | 废土驿站/pressure_modifiers | 1 | 废土驿站与修补集市 |
| `mat-8f0e60f0977552bfb079ddf7550c5b07` | 废土驿站/privacy | 1 | 废土驿站与修补集市 |
| `mat-7484d5f7ff8253719c6a0dbf6d07c10e` | 废土驿站/visibility | 1 | 废土驿站与修补集市 |
| `mat-89c77d6bfa705d1c9eeb5a33a45d89a1` | 废土驿站/witnesses | 1 | 废土驿站与修补集市 |
| `mat-d10b5a0c1c855f1fb057f70b4088060f` | 废弃搜刮药房/affordances | 1 | 废土驿站与修补集市 |
| `mat-ce10b97d977b51f786c379b9c0bee1a1` | 废弃搜刮药房/exits | 1 | 废土驿站与修补集市 |
| `mat-d980083ac9dc561d8fa09e64c74049c7` | 废弃搜刮药房/pressure_modifiers | 1 | 废土驿站与修补集市 |
| `mat-5c4b24969b0e5d10a730e462ddadfc9c` | 废弃搜刮药房/privacy | 1 | 废土驿站与修补集市 |
| `mat-88bc0178a7bf5af0a0eef890a1c2615e` | 废弃搜刮药房/visibility | 1 | 废土驿站与修补集市 |
| `mat-4654b25d0e15572d92e1cd43b98c526d` | 废弃搜刮药房/witnesses | 1 | 废土驿站与修补集市 |
| `mat-432af02ec02759c3ad8b846749858137` | 当铺/affordances | 1 | 地方行业与公共记忆 |
| `mat-3c961a9de7485de3b62cf545d33e47ce` | 当铺/exits | 1 | 地方行业与公共记忆 |
| `mat-5cb9e60371b259189cd6e0e7abe77074` | 当铺/pressure_modifiers | 1 | 地方行业与公共记忆 |
| `mat-f87361850c0c58a1801c8df1bc5a309a` | 当铺/privacy | 1 | 地方行业与公共记忆 |
| `mat-94e7695240b3510ea0566411c8dfba37` | 当铺/visibility | 1 | 地方行业与公共记忆 |
| `mat-89b8f47b3fa056d48df3da3902ad4a20` | 当铺/witnesses | 1 | 地方行业与公共记忆 |
| `mat-faaf195f37275d838c29c17cfc658e69` | 悬空神殿/affordances | 1 | 仙门藏书与驿镖 |
| `mat-55bc7315808756789a4d2a1eafc54088` | 悬空神殿/exits | 1 | 仙门藏书与驿镖 |
| `mat-49d429fae37253779ae957ac5b4dbfdf` | 悬空神殿/pressure_modifiers | 1 | 仙门藏书与驿镖 |
| `mat-834183c7de5d5561af3ae54e70071194` | 悬空神殿/privacy | 1 | 仙门藏书与驿镖 |
| `mat-857d405102135f5797a9f43ed1413982` | 悬空神殿/visibility | 1 | 仙门藏书与驿镖 |
| `mat-3b33ff0e2de55244996f0bf3b9005902` | 悬空神殿/witnesses | 1 | 仙门藏书与驿镖 |
| `mat-640a407bb5cc5d33b8e36031d28917fa` | 感染检疫隔离点/affordances | 1 | 检疫站旁的生活区 |
| `mat-62a8abd814ff55ee8a710c0626bd841f` | 感染检疫隔离点/exits | 1 | 检疫站旁的生活区 |
| `mat-58eaf4cf502b53c582835936bda6f2bb` | 感染检疫隔离点/pressure_modifiers | 1 | 检疫站旁的生活区 |
| `mat-4be2231c9d925ff2b67d7720fd08e4b5` | 感染检疫隔离点/privacy | 1 | 检疫站旁的生活区 |
| `mat-9da0553e738853219f5d9ecede37353a` | 感染检疫隔离点/visibility | 1 | 检疫站旁的生活区 |
| `mat-e9641f2e36e558779f6ea0ed314f3815` | 感染检疫隔离点/witnesses | 1 | 检疫站旁的生活区 |
| `mat-3a5d39e976875005a4dce49aead38008` | 戏楼/affordances | 1 | 王朝百业与书院 |
| `mat-c0986502f15355928b99818b125465ef` | 戏楼/exits | 1 | 王朝百业与书院 |
| `mat-6515f9baa38c5a01947322112ce6c1fb` | 戏楼/pressure_modifiers | 1 | 王朝百业与书院 |
| `mat-416c36d3773852639021de891f5a8731` | 戏楼/privacy | 1 | 王朝百业与书院 |
| `mat-614bfb7364155fc998380ce55db9bd19` | 戏楼/visibility | 1 | 王朝百业与书院 |
| `mat-d5462ca6894f59c3b165a8099fab3543` | 戏楼/witnesses | 1 | 王朝百业与书院 |
| `mat-ff4dfbcafa2350a5b1fe2eaf821e65ee` | 打烊后的买手店/affordances | 1 | 城市休闲与共享会客 |
| `mat-654e04f974e55e12a4e71d1487f8df03` | 打烊后的买手店/exits | 1 | 城市休闲与共享会客 |
| `mat-afba67d3b8ae5998b94d068c4143d4f2` | 打烊后的买手店/pressure_modifiers | 1 | 城市休闲与共享会客 |
| `mat-742f5378f8575ee29dd792ee3f461545` | 打烊后的买手店/privacy | 1 | 城市休闲与共享会客 |
| `mat-944f2f649758578985f274e05767e1f4` | 打烊后的买手店/visibility | 1 | 城市休闲与共享会客 |
| `mat-9ab404a5fdd65ba8a80e0ad192644ac3` | 打烊后的买手店/witnesses | 1 | 城市休闲与共享会客 |
| `mat-fd0fbf943e1f5de78443a2272f3d2c12` | 打烊面包店/affordances | 1 | 街角共同生活圈 |
| `mat-e26726b0a6f857ebb2dad09534f62fbf` | 打烊面包店/exits | 1 | 街角共同生活圈 |
| `mat-bc02f4aac5b05031ba40c3f1f424c3ff` | 打烊面包店/pressure_modifiers | 1 | 街角共同生活圈 |
| `mat-a2be9d9e92a6571e90d1ae142a3dc8e3` | 打烊面包店/privacy | 1 | 街角共同生活圈 |
| `mat-0399a48bdf3e53cca6a6ecf3957f5e20` | 打烊面包店/visibility | 1 | 街角共同生活圈 |
| `mat-ab691882858f56909ce031623918281e` | 打烊面包店/witnesses | 1 | 街角共同生活圈 |
| `mat-81bb15e7acf0503eb81cee28546aa48b` | 拍卖行/affordances | 1 | 民国报馆与手艺街 |
| `mat-b576d94affbe5461bbe910e67907a3ab` | 拍卖行/exits | 1 | 民国报馆与手艺街 |
| `mat-36d57863db0d5f44960cca159e96418b` | 拍卖行/pressure_modifiers | 1 | 民国报馆与手艺街 |
| `mat-64786029623258759dfb9656afa55b36` | 拍卖行/privacy | 1 | 民国报馆与手艺街 |
| `mat-060de37c93ec554bbdcafb6358b1297c` | 拍卖行/visibility | 1 | 民国报馆与手艺街 |
| `mat-c53d2779a9c35206ab8b57e1e601deda` | 拍卖行/witnesses | 1 | 民国报馆与手艺街 |
| `mat-c99c758f764c5cfbb20d2f7cb520b13c` | 旗袍定制店/affordances | 1 | 民国报馆与手艺街 |
| `mat-94777ddd9241509c8bb409fa2b47e0a7` | 旗袍定制店/exits | 1 | 民国报馆与手艺街 |
| `mat-5b6ebda5805a53febaa4d19dae9c6d28` | 旗袍定制店/pressure_modifiers | 1 | 民国报馆与手艺街 |
| `mat-159df4ce38995236beac7b67c143bd71` | 旗袍定制店/privacy | 1 | 民国报馆与手艺街 |
| `mat-b2c11589be5e55e7ba5e9a0f8add7cf2` | 旗袍定制店/visibility | 1 | 民国报馆与手艺街 |
| `mat-73cd1d39520c5bb0811d868377948714` | 旗袍定制店/witnesses | 1 | 民国报馆与手艺街 |
| `mat-a158247ff9f8572ea949ba9f2be3f9f0` | 无相鬼市千佛暗窟/affordances | 1 | 蜃景商路与鬼市 |
| `mat-92815a10cb145124a5a2ab24eb356fa5` | 无相鬼市千佛暗窟/exits | 1 | 蜃景商路与鬼市 |
| `mat-0d818402573d569093a2a7646e37cf6a` | 无相鬼市千佛暗窟/pressure_modifiers | 1 | 蜃景商路与鬼市 |
| `mat-1d1c3803eee3574e8a7c06dafd38582f` | 无相鬼市千佛暗窟/privacy | 1 | 蜃景商路与鬼市 |
| `mat-942870e8c6ad537d8cc9fc14a31ad268` | 无相鬼市千佛暗窟/visibility | 1 | 蜃景商路与鬼市 |
| `mat-dbbc0701028155cfad5027abe0f7dd00` | 无相鬼市千佛暗窟/witnesses | 1 | 蜃景商路与鬼市 |
| `mat-c73ed619442250ad9d6997d367cfa785` | 昭和喫茶店/affordances | 1 | 昭和街角喫茶巡礼 |
| `mat-03f6a2ec22585976ad35a90a415d84c8` | 昭和喫茶店/exits | 1 | 昭和街角喫茶巡礼 |
| `mat-8a244fdb09485dd49638037340f68702` | 昭和喫茶店/pressure_modifiers | 1 | 昭和街角喫茶巡礼 |
| `mat-4fa7158cfcbc5993bb92648d15860354` | 昭和喫茶店/privacy | 1 | 昭和街角喫茶巡礼 |
| `mat-03e79a3cb44e52cda7e9f5ec235207d2` | 昭和喫茶店/visibility | 1 | 昭和街角喫茶巡礼 |
| `mat-7124a3adeb0753ee8a8be437b5aee2c1` | 昭和喫茶店/witnesses | 1 | 昭和街角喫茶巡礼 |
| `mat-95020e1bc9cd5d1ab0a6c63c7233e0f3` | 最后一班渡轮/affordances | 1 | 远途休假与小镇停留 |
| `mat-7c940fd53fd757029b95d8f05cc1d64d` | 最后一班渡轮/exits | 1 | 远途休假与小镇停留 |
| `mat-34b6cf08f5d75262b6a6eaabf1532768` | 最后一班渡轮/pressure_modifiers | 1 | 远途休假与小镇停留 |
| `mat-e21c384eefba5f4c8060fbee16ed2639` | 最后一班渡轮/privacy | 1 | 远途休假与小镇停留 |
| `mat-f337b8164e735585986d6fa337b6ff4c` | 最后一班渡轮/visibility | 1 | 远途休假与小镇停留 |
| `mat-162f33f3d7fc5beea5aa4f82217c3c25` | 最后一班渡轮/witnesses | 1 | 远途休假与小镇停留 |
| `mat-f114a5f674b25fb6bf7da6ac158cdb52` | 朋友客厅/affordances | 1 | 街角共同生活圈 |
| `mat-20752f2cf76f5086a89932dddfe892d0` | 朋友客厅/exits | 1 | 街角共同生活圈 |
| `mat-8b57283de77851e9b7d531b5422729f3` | 朋友客厅/pressure_modifiers | 1 | 街角共同生活圈 |
| `mat-05b217f21d5c535794dc1ead5848c82d` | 朋友客厅/privacy | 1 | 街角共同生活圈 |
| `mat-4e2c2787ae8a5a38861b4c3c2a4a4f13` | 朋友客厅/visibility | 1 | 街角共同生活圈 |
| `mat-3a600af26b8e558089780fcc41df2649` | 朋友客厅/witnesses | 1 | 街角共同生活圈 |
| `mat-1255ad41c0e852ad9d45f90bcf19c4a2` | 末班地铁/affordances | 1 | 赛博街区与公共终端 |
| `mat-e01c809d24a25918a68b7017ef655d17` | 末班地铁/exits | 1 | 赛博街区与公共终端 |
| `mat-a37575a2dbe655beb53b293b88a7a658` | 末班地铁/pressure_modifiers | 1 | 赛博街区与公共终端 |
| `mat-8533a045452854bc82ce1a114cbc5fd2` | 末班地铁/privacy | 1 | 赛博街区与公共终端 |
| `mat-687097d7c4715e589344b77a6a7ac78d` | 末班地铁/visibility | 1 | 赛博街区与公共终端 |
| `mat-5a519624b06c5b01a4b71dd2dea80227` | 末班地铁/witnesses | 1 | 赛博街区与公共终端 |
| `mat-e4fef233105654029ccbae92f00d4f82` | 桌游店/affordances | 1 | 千禧网络街坊 |
| `mat-8e7daa991a8a5f7eb07f7a7f27798dd7` | 桌游店/exits | 1 | 千禧网络街坊 |
| `mat-504734f5a24653f6b1c16254a59deaa0` | 桌游店/pressure_modifiers | 1 | 千禧网络街坊 |
| `mat-ef74787bf00f5ee5b379de790d052b7c` | 桌游店/privacy | 1 | 千禧网络街坊 |
| `mat-b24abe99b6d45df2ae8484195b16d241` | 桌游店/visibility | 1 | 千禧网络街坊 |
| `mat-dd3d7de588225ba6a14a8d6e9438d034` | 桌游店/witnesses | 1 | 千禧网络街坊 |
| `mat-42a0cad6c19657a6bdbc8ab40eaa9387` | 殡仪馆/affordances | 1 | 地方行业与公共记忆 |
| `mat-bc60b1be5e885bfb8b6d851e592773fc` | 殡仪馆/exits | 1 | 地方行业与公共记忆 |
| `mat-30f5bc4662545619a94ebfa53f913771` | 殡仪馆/pressure_modifiers | 1 | 地方行业与公共记忆 |
| `mat-6812a07029135e87a36392e1afdcdba7` | 殡仪馆/privacy | 1 | 地方行业与公共记忆 |
| `mat-8995f49d8a61542e8bad41fa41704bba` | 殡仪馆/visibility | 1 | 地方行业与公共记忆 |
| `mat-cce5df87943a54c6b024a759e73c32a1` | 殡仪馆/witnesses | 1 | 地方行业与公共记忆 |
| `mat-c2c396516ac05e4da4249c0c6d6d92d3` | 民国公馆/affordances | 1 | 民国报馆与手艺街 |
| `mat-cf2ed55f5f0f5cf3b964c627525e1e38` | 民国公馆/exits | 1 | 民国报馆与手艺街 |
| `mat-92b782636af0540e8708ff30ec4865b7` | 民国公馆/pressure_modifiers | 1 | 民国报馆与手艺街 |
| `mat-d03ad60280285292ac33a677ee42c59f` | 民国公馆/privacy | 1 | 民国报馆与手艺街 |
| `mat-3043465671b55bc0af1dcc838cced2ef` | 民国公馆/visibility | 1 | 民国报馆与手艺街 |
| `mat-d73bcc7cb5c153adb7b3d0a7709a3c9d` | 民国公馆/witnesses | 1 | 民国报馆与手艺街 |
| `mat-1a749841a8095641b6e950035e0a9ce9` | 江心画舫/affordances | 1 | 王朝百业与书院 |
| `mat-8575f6549a525f16a6f8dddce0551896` | 江心画舫/exits | 1 | 王朝百业与书院 |
| `mat-54ed1c3c491d54bab9ec0ca8ab0142df` | 江心画舫/pressure_modifiers | 1 | 王朝百业与书院 |
| `mat-a915c2363111589cb5ec9f46203eb6d4` | 江心画舫/privacy | 1 | 王朝百业与书院 |
| `mat-b5358492c2595cf7a7716174896ec5be` | 江心画舫/visibility | 1 | 王朝百业与书院 |
| `mat-06ecc5f370c256938fbb98fc075e7b0b` | 江心画舫/witnesses | 1 | 王朝百业与书院 |
| `mat-83e54f0042c25bca88fb4ad97edff58b` | 洋装裁缝铺/affordances | 1 | 明治洋裁与译书町 |
| `mat-0719926e2f755df9bfe8caf40dc51782` | 洋装裁缝铺/exits | 1 | 明治洋裁与译书町 |
| `mat-166110d2d486526495b181d4fc562319` | 洋装裁缝铺/pressure_modifiers | 1 | 明治洋裁与译书町 |
| `mat-8926e725505c5a03890ab4bdb2c06c40` | 洋装裁缝铺/privacy | 1 | 明治洋裁与译书町 |
| `mat-d58d75cc40815e558d1bd74374ef9fb7` | 洋装裁缝铺/visibility | 1 | 明治洋裁与译书町 |
| `mat-8fae69c3130f57e091b90d620fdb80d1` | 洋装裁缝铺/witnesses | 1 | 明治洋裁与译书町 |
| `mat-e3de64fde9765f18b6b96eb3da55ca4b` | 洋馆偏屋/affordances | 1 | 明治洋裁与译书町 |
| `mat-0fa2a92ad4745d9aa7711727e7a0ff3d` | 洋馆偏屋/exits | 1 | 明治洋裁与译书町 |
| `mat-95270b0f36305d90994c2a87148b34da` | 洋馆偏屋/pressure_modifiers | 1 | 明治洋裁与译书町 |
| `mat-8c5cbb8e570956bc8d806b6d82be6ba4` | 洋馆偏屋/privacy | 1 | 明治洋裁与译书町 |
| `mat-cdb9bbb892c15ba9aa62bebf5a3aa114` | 洋馆偏屋/visibility | 1 | 明治洋裁与译书町 |
| `mat-a8ff6822ffc8550bbeac21349bbd34ac` | 洋馆偏屋/witnesses | 1 | 明治洋裁与译书町 |
| `mat-be12a46a18015881a88af16cb75d1e4c` | 流动马戏团大篷车/affordances | 1 | 流动马戏与机械舞台 |
| `mat-b941dbb9fec85028af0fce09e565812d` | 流动马戏团大篷车/exits | 1 | 流动马戏与机械舞台 |
| `mat-b2342cee73ec508390ab87139deb5cac` | 流动马戏团大篷车/pressure_modifiers | 1 | 流动马戏与机械舞台 |
| `mat-300f4351c80d56629bfbb995d37ace62` | 流动马戏团大篷车/privacy | 1 | 流动马戏与机械舞台 |
| `mat-117b89265f0654a38a82e34761adc6f2` | 流动马戏团大篷车/visibility | 1 | 流动马戏与机械舞台 |
| `mat-e3a37b0b90d95334a64e41202066e09b` | 流动马戏团大篷车/witnesses | 1 | 流动马戏与机械舞台 |
| `mat-911b9635efdb5075a50dd05ec3e67645` | 流沙回廊炼金暗房/affordances | 1 | 蜃景商路与鬼市 |
| `mat-da7799f61cb753c68efe633d122b4504` | 流沙回廊炼金暗房/exits | 1 | 蜃景商路与鬼市 |
| `mat-cf900a1a711d5e27a2060ad801c660c3` | 流沙回廊炼金暗房/pressure_modifiers | 1 | 蜃景商路与鬼市 |
| `mat-7d5d3682507d5525b03d5cd9dcdb1969` | 流沙回廊炼金暗房/privacy | 1 | 蜃景商路与鬼市 |
| `mat-b6b9d258dee65b498c19a52ca5f9847e` | 流沙回廊炼金暗房/visibility | 1 | 蜃景商路与鬼市 |
| `mat-a47a6bba95fd52dd8018efcb01b8d1da` | 流沙回廊炼金暗房/witnesses | 1 | 蜃景商路与鬼市 |
| `mat-732d7d01790c5f779ee94dd883892d98` | 海岛度假村/affordances | 1 | 远途休假与小镇停留 |
| `mat-b2e2085bcf6e561582e438c9ec6aa7b6` | 海岛度假村/exits | 1 | 远途休假与小镇停留 |
| `mat-ebcf27b71bf9584596b7a5e8d0a6aaea` | 海岛度假村/pressure_modifiers | 1 | 远途休假与小镇停留 |
| `mat-cb058e434d2d518e97e26ed1d1556e3c` | 海岛度假村/privacy | 1 | 远途休假与小镇停留 |
| `mat-9686563cfa565e57ba955ebd9a084a63` | 海岛度假村/visibility | 1 | 远途休假与小镇停留 |
| `mat-9da367352ad25658824b116033b07261` | 海岛度假村/witnesses | 1 | 远途休假与小镇停留 |
| `mat-df900457288e5b13a1b96418bcf41d3a` | 海边步道/affordances | 1 | 城市休闲与共享会客 |
| `mat-208f7483571f5753b07a7d49d1d06213` | 海边步道/exits | 1 | 城市休闲与共享会客 |
| `mat-a8ccb07761a7542eab3c5e2cbb4097ea` | 海边步道/pressure_modifiers | 1 | 城市休闲与共享会客 |
| `mat-1079685816f352f393e936e968147d89` | 海边步道/privacy | 1 | 城市休闲与共享会客 |
| `mat-c9c3f606073a5f919f02aef3478e1125` | 海边步道/visibility | 1 | 城市休闲与共享会客 |
| `mat-2c1570dca3935c68bd4186c729e10fe9` | 海边步道/witnesses | 1 | 城市休闲与共享会客 |
| `mat-d2bb135985d6531a9b601ad8113b53f7` | 海边浴衣祭神社后阶梯/affordances | 1 | 旧町神怪与灯会 |
| `mat-3f516ae6c9165d95afecf174d3dd7992` | 海边浴衣祭神社后阶梯/exits | 1 | 旧町神怪与灯会 |
| `mat-1867d05a5fad5d25a2bb6948e9584253` | 海边浴衣祭神社后阶梯/pressure_modifiers | 1 | 旧町神怪与灯会 |
| `mat-a5d9373bfb65529ea865e2d1a2403e19` | 海边浴衣祭神社后阶梯/privacy | 1 | 旧町神怪与灯会 |
| `mat-527737cce86e508db3504bc3395803e9` | 海边浴衣祭神社后阶梯/visibility | 1 | 旧町神怪与灯会 |
| `mat-c907a54fae565cab8e1f3be6647fb73a` | 海边浴衣祭神社后阶梯/witnesses | 1 | 旧町神怪与灯会 |
| `mat-723cf2c4c0cc57ee95b9f2f5ab633768` | 深夜便利店/affordances | 1 | 街角共同生活圈 |
| `mat-e905f6b1aab05c71bafcceb2fecbd8f1` | 深夜便利店/exits | 1 | 街角共同生活圈 |
| `mat-94fbaa2b368256578c046f604eae8647` | 深夜便利店/pressure_modifiers | 1 | 街角共同生活圈 |
| `mat-72426021a99d5399b8f1a3d133e54b1d` | 深夜便利店/privacy | 1 | 街角共同生活圈 |
| `mat-b5e4c7a7534458ceab9514303c1b1be0` | 深夜便利店/visibility | 1 | 街角共同生活圈 |
| `mat-52bf3f8c047b536aa9ef5e8f80f95290` | 深夜便利店/witnesses | 1 | 街角共同生活圈 |
| `mat-a5971501654855778388225c68ece6b8` | 深夜机场候机区/affordances | 1 | 远途休假与小镇停留 |
| `mat-2b0f503791d459788dd2c00c7e7a6e98` | 深夜机场候机区/exits | 1 | 远途休假与小镇停留 |
| `mat-9b5f76f1de3f5fdcb434884eb0da2b9c` | 深夜机场候机区/pressure_modifiers | 1 | 远途休假与小镇停留 |
| `mat-b1b34fa13cf355fe8edda6e91ffe5113` | 深夜机场候机区/privacy | 1 | 远途休假与小镇停留 |
| `mat-81b525016361572f88ddae306df120a1` | 深夜机场候机区/visibility | 1 | 远途休假与小镇停留 |
| `mat-4164e52ef8fe5ea69e64247b33d31486` | 深夜机场候机区/witnesses | 1 | 远途休假与小镇停留 |
| `mat-efa14961427959e9b8ee3d2f843c7673` | 清晨菜市场/affordances | 1 | 街角共同生活圈 |
| `mat-cb10b4e750a95c5d80090b77358cea6e` | 清晨菜市场/exits | 1 | 街角共同生活圈 |
| `mat-bbaac0b3bf605926b217c40471ef5f45` | 清晨菜市场/pressure_modifiers | 1 | 街角共同生活圈 |
| `mat-d4701548f4985f3ab038ea5959fd0620` | 清晨菜市场/privacy | 1 | 街角共同生活圈 |
| `mat-b88902fcbaf355259a338b1ec7434bda` | 清晨菜市场/visibility | 1 | 街角共同生活圈 |
| `mat-f9c904078a5a5461bb40c8b549756008` | 清晨菜市场/witnesses | 1 | 街角共同生活圈 |
| `mat-c6225d31b6ef547c8c3394ba6c9dc5ed` | 灯塔值守屋/affordances | 1 | 海岸渡船与观测旅行 |
| `mat-f4085474897d51afa2db393dfd115a60` | 灯塔值守屋/exits | 1 | 海岸渡船与观测旅行 |
| `mat-c4ae22cdca895ffa80c3c9595ef4477b` | 灯塔值守屋/pressure_modifiers | 1 | 海岸渡船与观测旅行 |
| `mat-207583ab3187525994dafb572019647f` | 灯塔值守屋/privacy | 1 | 海岸渡船与观测旅行 |
| `mat-1253b9f4ab4d5cfd9d985aac2efbf485` | 灯塔值守屋/visibility | 1 | 海岸渡船与观测旅行 |
| `mat-57a0d56c42ac5ed3a21123465342c9a9` | 灯塔值守屋/witnesses | 1 | 海岸渡船与观测旅行 |
| `mat-5c52a610b2775e2a84498c3b553bca33` | 爵士喫茶/affordances | 1 | 昭和街角喫茶巡礼 |
| `mat-2ac005471bfc5721b217c1d31441823f` | 爵士喫茶/exits | 1 | 昭和街角喫茶巡礼 |
| `mat-57dba7ae7d7e568aa1e98b7457168dc5` | 爵士喫茶/pressure_modifiers | 1 | 昭和街角喫茶巡礼 |
| `mat-8c40f24a347751c7b03fa96cc8ccf0f8` | 爵士喫茶/privacy | 1 | 昭和街角喫茶巡礼 |
| `mat-ba61c325168e5c8aa2f90be154ea09a1` | 爵士喫茶/visibility | 1 | 昭和街角喫茶巡礼 |
| `mat-9f8bf8fcb15759dfb2e9137ca1597ada` | 爵士喫茶/witnesses | 1 | 昭和街角喫茶巡礼 |
| `mat-96fed3da65105f7e8577e474c82cfc7c` | 理发店暗门后地下酒吧/affordances | 1 | 禁酒期爵士与报纸 |
| `mat-6e11b3c8c34f5c2d998ba4199504906b` | 理发店暗门后地下酒吧/exits | 1 | 禁酒期爵士与报纸 |
| `mat-8750bffeb4f85c35b5ca7b367d2b9d4b` | 理发店暗门后地下酒吧/pressure_modifiers | 1 | 禁酒期爵士与报纸 |
| `mat-7ffb6ec6bee057eeb41b88997950acd5` | 理发店暗门后地下酒吧/privacy | 1 | 禁酒期爵士与报纸 |
| `mat-64b85de839d654a3bbcc9903839c7f0b` | 理发店暗门后地下酒吧/visibility | 1 | 禁酒期爵士与报纸 |
| `mat-6db171ea1035559db623b576acb70284` | 理发店暗门后地下酒吧/witnesses | 1 | 禁酒期爵士与报纸 |
| `mat-e1f64b181ce050c9a2659f7871968f7d` | 电竞俱乐部/affordances | 1 | 地方行业与公共记忆 |
| `mat-b1a1f1dbc3c1523fa82769d61f868143` | 电竞俱乐部/exits | 1 | 地方行业与公共记忆 |
| `mat-d8bac0778a74517887b6125596aa79f0` | 电竞俱乐部/pressure_modifiers | 1 | 地方行业与公共记忆 |
| `mat-3873cccecbd75c0291d8d874e3152ebd` | 电竞俱乐部/privacy | 1 | 地方行业与公共记忆 |
| `mat-72900b3c136d520b82cee2dc75175c16` | 电竞俱乐部/visibility | 1 | 地方行业与公共记忆 |
| `mat-42ea67d9b8405db689ef7a6802ca00d5` | 电竞俱乐部/witnesses | 1 | 地方行业与公共记忆 |
| `mat-cc130249f2e857f5ad866b9afb3a0537` | 电竞基地训练室/affordances | 1 | 同人街区与录音协作 |
| `mat-50d0a31db12f55d08d796cc1fe15c448` | 电竞基地训练室/exits | 1 | 同人街区与录音协作 |
| `mat-1ab937c73db95d28a2b6718a161d5106` | 电竞基地训练室/pressure_modifiers | 1 | 同人街区与录音协作 |
| `mat-cab83b9f7cd45cfba02c094214f62479` | 电竞基地训练室/privacy | 1 | 同人街区与录音协作 |
| `mat-bc6311f60ba358deb9f320e1273af663` | 电竞基地训练室/visibility | 1 | 同人街区与录音协作 |
| `mat-88c8a75b28615949ab8e3205bd108f24` | 电竞基地训练室/witnesses | 1 | 同人街区与录音协作 |
| `mat-5624cef363985355b08690eecdd9650e` | 画廊/affordances | 1 | 成年创作者与校园艺术季 |
| `mat-8e20c5beff3c5f8f9e7dc58643d8e1f8` | 画廊/exits | 1 | 成年创作者与校园艺术季 |
| `mat-a3622278733a5cf7a0d6aa4470d2c075` | 画廊/pressure_modifiers | 1 | 成年创作者与校园艺术季 |
| `mat-31ccc1a7c4d050f889835a81f4072741` | 画廊/privacy | 1 | 成年创作者与校园艺术季 |
| `mat-62d79e3805ec53ecb82994c9c17822d0` | 画廊/visibility | 1 | 成年创作者与校园艺术季 |
| `mat-13ed680077f957f4b3f3766d4a32202b` | 画廊/witnesses | 1 | 成年创作者与校园艺术季 |
| `mat-2c6af3a6e2985f0cb9ab82d61f3897de` | 疗养院/affordances | 1 | 后方邮路与灯火 |
| `mat-e71f51d1188b5b8999fc8b349224b6ac` | 疗养院/exits | 1 | 后方邮路与灯火 |
| `mat-ebf964464422541795a0ca7ae7448fed` | 疗养院/pressure_modifiers | 1 | 后方邮路与灯火 |
| `mat-95b874b7612857568780c7b25a99ff66` | 疗养院/privacy | 1 | 后方邮路与灯火 |
| `mat-9ad6a83f0de35184bc908619fc8b3c49` | 疗养院/visibility | 1 | 后方邮路与灯火 |
| `mat-e4679625381554fe9e870936496e329a` | 疗养院/witnesses | 1 | 后方邮路与灯火 |
| `mat-d881a99e84c35835885930e5e4f0eb8e` | 直播平台危机会议室/affordances | 1 | 传媒编辑室与公开记录 |
| `mat-5dff447ef15e5c46a524172ccd79918f` | 直播平台危机会议室/exits | 1 | 传媒编辑室与公开记录 |
| `mat-1c0a27f0dd235b828605c474a00c2dbb` | 直播平台危机会议室/pressure_modifiers | 1 | 传媒编辑室与公开记录 |
| `mat-ec4ad580813b512f9394494e9bdb64af` | 直播平台危机会议室/privacy | 1 | 传媒编辑室与公开记录 |
| `mat-0e1aef78ada952fcb8ca91117a4861e6` | 直播平台危机会议室/visibility | 1 | 传媒编辑室与公开记录 |
| `mat-463ddc56caf258e8a3703b4c7f0e26c6` | 直播平台危机会议室/witnesses | 1 | 传媒编辑室与公开记录 |
| `mat-be9df21d02a15c37aac2e98dc51b8f0e` | 真名保管库/affordances | 1 | 契约城与非人街坊 |
| `mat-08120f1acb9f53d5b3a3ebaee79282a9` | 真名保管库/exits | 1 | 契约城与非人街坊 |
| `mat-20f27caeeec45769884f27e5372034ac` | 真名保管库/pressure_modifiers | 1 | 契约城与非人街坊 |
| `mat-3e3f386b8a195386aebcd1fb0e496910` | 真名保管库/privacy | 1 | 契约城与非人街坊 |
| `mat-9e6996a822ff58fca5314bbc8d7af054` | 真名保管库/visibility | 1 | 契约城与非人街坊 |
| `mat-387ff5bcc9bd5caeb6850e04773dfee7` | 真名保管库/witnesses | 1 | 契约城与非人街坊 |
| `mat-a72676fe666151a18c078f5e6e5b4ead` | 社区诊所/affordances | 1 | 街角共同生活圈 |
| `mat-40750cf2c27d5bd4a1b992efce31e99b` | 社区诊所/exits | 1 | 街角共同生活圈 |
| `mat-dedd17ff01605e79882413dc123b72e6` | 社区诊所/pressure_modifiers | 1 | 街角共同生活圈 |
| `mat-4eda8eebd01a52f49ba56501bb41479d` | 社区诊所/privacy | 1 | 街角共同生活圈 |
| `mat-fb0b6652194f5a5f87ed5099bcad819b` | 社区诊所/visibility | 1 | 街角共同生活圈 |
| `mat-31e78ddc8c8653619fc26efbae42a4c1` | 社区诊所/witnesses | 1 | 街角共同生活圈 |
| `mat-c937e33c129d5b58ab1829af0bce8fa7` | 神乐坂置屋/affordances | 1 | 幕末町屋与道场 |
| `mat-28d7e1987be558abbcac08f4e09ec1aa` | 神乐坂置屋/exits | 1 | 幕末町屋与道场 |
| `mat-e96c7a38b7fe56bd9acff908922f4d0a` | 神乐坂置屋/pressure_modifiers | 1 | 幕末町屋与道场 |
| `mat-b984b23cc9605214a9f8e52119e91ad0` | 神乐坂置屋/privacy | 1 | 幕末町屋与道场 |
| `mat-7a570df62f82569ba8417e71d2bea42a` | 神乐坂置屋/visibility | 1 | 幕末町屋与道场 |
| `mat-71bbf9bb36f2552b94e03a0bb9a119e8` | 神乐坂置屋/witnesses | 1 | 幕末町屋与道场 |
| `mat-298f317f5df650cc8aa298af89af5c59` | 私人游艇/affordances | 1 | 海岸渡船与观测旅行 |
| `mat-b6bc779bb4ee5c2e970a75bb43a343f6` | 私人游艇/exits | 1 | 海岸渡船与观测旅行 |
| `mat-775f87f2e7a65387a2bcae148ca020da` | 私人游艇/pressure_modifiers | 1 | 海岸渡船与观测旅行 |
| `mat-4300b3c4f6485fc5a7c2b187f3a62a3c` | 私人游艇/privacy | 1 | 海岸渡船与观测旅行 |
| `mat-9b94aab24af15b0ca5bbe8509cfcc433` | 私人游艇/visibility | 1 | 海岸渡船与观测旅行 |
| `mat-f08e9c20180d588f817f49289044f8a3` | 私人游艇/witnesses | 1 | 海岸渡船与观测旅行 |
| `mat-aceab5eca99558bab2a1c0d93e24e461` | 私家宅邸/affordances | 1 | 城市休闲与共享会客 |
| `mat-5592498e6df55274981e04c0d9cb1d70` | 私家宅邸/exits | 1 | 城市休闲与共享会客 |
| `mat-af5efe47c2d2562691206f5290fe7315` | 私家宅邸/pressure_modifiers | 1 | 城市休闲与共享会客 |
| `mat-9dc4d6a0489e5cbc8bb47620f3811b10` | 私家宅邸/privacy | 1 | 城市休闲与共享会客 |
| `mat-fd7bf309a0755da4891f01f6b7d45426` | 私家宅邸/visibility | 1 | 城市休闲与共享会客 |
| `mat-53876435a67c53f3940cffdc3598612d` | 私家宅邸/witnesses | 1 | 城市休闲与共享会客 |
| `mat-5edbfcc7bd6f57e3a2c704f8fb846fb8` | 私立诊察室/affordances | 1 | 雾都钟表与港务街 |
| `mat-4cf015bf921459fdb8284ca4ef4fea43` | 私立诊察室/exits | 1 | 雾都钟表与港务街 |
| `mat-5b21d23d448d58c580fda4dd864b53e3` | 私立诊察室/pressure_modifiers | 1 | 雾都钟表与港务街 |
| `mat-38548b0d301c5925b16eadc041a48591` | 私立诊察室/privacy | 1 | 雾都钟表与港务街 |
| `mat-8c3ba847d0f05672880f0dabd5541a05` | 私立诊察室/visibility | 1 | 雾都钟表与港务街 |
| `mat-f443cbd1fcef5fa0afe990f97fc6e769` | 私立诊察室/witnesses | 1 | 雾都钟表与港务街 |
| `mat-4df5fd3d91b450bc8f48fd7e1cf243f6` | 立体停车库/affordances | 1 | 赛博街区与公共终端 |
| `mat-369f9561c31e5975bb25c34aac9fb6f0` | 立体停车库/exits | 1 | 赛博街区与公共终端 |
| `mat-db446b72059b5fafaa645db0691f2165` | 立体停车库/pressure_modifiers | 1 | 赛博街区与公共终端 |
| `mat-efbcc14c80d85e3680ffd9bd96dc883f` | 立体停车库/privacy | 1 | 赛博街区与公共终端 |
| `mat-a0135ab6558354b58b8920cf0ca65bb5` | 立体停车库/visibility | 1 | 赛博街区与公共终端 |
| `mat-b2a496cb54cd5adc84331c152fda76de` | 立体停车库/witnesses | 1 | 赛博街区与公共终端 |
| `mat-939150114e6451f89cd2aa443f5137e7` | 红丝绒马戏大帐篷/affordances | 1 | 流动马戏与机械舞台 |
| `mat-035c6bfc30815b42ae8df6a15b143761` | 红丝绒马戏大帐篷/exits | 1 | 流动马戏与机械舞台 |
| `mat-2aefe30e043a533bab2d1ce07515698b` | 红丝绒马戏大帐篷/pressure_modifiers | 1 | 流动马戏与机械舞台 |
| `mat-71e8edd8274451829641668f4830de24` | 红丝绒马戏大帐篷/privacy | 1 | 流动马戏与机械舞台 |
| `mat-32d2ee7e899456f29603030b6a6d95cc` | 红丝绒马戏大帐篷/visibility | 1 | 流动马戏与机械舞台 |
| `mat-97a62e62b70d5f16b446551fe43b5bff` | 红丝绒马戏大帐篷/witnesses | 1 | 流动马戏与机械舞台 |
| `mat-d512a084f4025f37a686378f4c983f04` | 结界检查站/affordances | 1 | 契约城与非人街坊 |
| `mat-57c95436ba445986ae716ff2c0d0c0d7` | 结界检查站/exits | 1 | 契约城与非人街坊 |
| `mat-e839826b4bfa53628b9d73936cdb1860` | 结界检查站/pressure_modifiers | 1 | 契约城与非人街坊 |
| `mat-bff2bfdcf8445b25a5e66651d281f9fa` | 结界检查站/privacy | 1 | 契约城与非人街坊 |
| `mat-54cbfba287c9589bb50b0321720a2535` | 结界检查站/visibility | 1 | 契约城与非人街坊 |
| `mat-af1855c231b653ff8670592fa7ac7d61` | 结界检查站/witnesses | 1 | 契约城与非人街坊 |
| `mat-b22467b4548151fcae0687cdef79c91f` | 美术馆/affordances | 1 | 传媒编辑室与公开记录 |
| `mat-ffd9c737266b5fe193c3a80616bc9ed0` | 美术馆/exits | 1 | 传媒编辑室与公开记录 |
| `mat-98f9cf780f4d5105a4d7f5b94166bcb7` | 美术馆/pressure_modifiers | 1 | 传媒编辑室与公开记录 |
| `mat-b58ff8a4f652534088350ffe0366880e` | 美术馆/privacy | 1 | 传媒编辑室与公开记录 |
| `mat-9360bb5a41f35547a0e4720e47401875` | 美术馆/visibility | 1 | 传媒编辑室与公开记录 |
| `mat-fa56721875305bef88face922a5f2530` | 美术馆/witnesses | 1 | 传媒编辑室与公开记录 |
| `mat-c97dd330d62053c981ec9f7ef757cdce` | 老旧小区/affordances | 1 | 街角共同生活圈 |
| `mat-342c87e288395986996eabbaf491ce21` | 老旧小区/exits | 1 | 街角共同生活圈 |
| `mat-e4800fcf16d1509299dae7808b61bc13` | 老旧小区/pressure_modifiers | 1 | 街角共同生活圈 |
| `mat-92ccf25ccd2650aaa4739f69a01e08f5` | 老旧小区/privacy | 1 | 街角共同生活圈 |
| `mat-a475076ecc95598882d1ab3b3d7f15cc` | 老旧小区/visibility | 1 | 街角共同生活圈 |
| `mat-82eb8dd8fb9552eb8138711165ee2c9f` | 老旧小区/witnesses | 1 | 街角共同生活圈 |
| `mat-12bf98a3d982569f81c762c3b43c0bfe` | 老茶馆/affordances | 1 | 王朝百业与书院 |
| `mat-8d10b0212d845474bb95be05e3a83c1b` | 老茶馆/exits | 1 | 王朝百业与书院 |
| `mat-bac625feb819558794e4f6b39bc8d766` | 老茶馆/pressure_modifiers | 1 | 王朝百业与书院 |
| `mat-bf65dfcd7f225112a49ab9bc33af0d90` | 老茶馆/privacy | 1 | 王朝百业与书院 |
| `mat-ff3494e873b05298abc386e3d5a610ed` | 老茶馆/visibility | 1 | 王朝百业与书院 |
| `mat-914807ba67f556aa9b53202f73122dd8` | 老茶馆/witnesses | 1 | 王朝百业与书院 |
| `mat-a9d099ef947e5aff9a18ef5d93995918` | 胡姬八角琉璃酒肆/affordances | 1 | 蜃景商路与鬼市 |
| `mat-5b814c2e8a9d534f8253e61db240a3fe` | 胡姬八角琉璃酒肆/exits | 1 | 蜃景商路与鬼市 |
| `mat-efea0b8ebaf9588ca92897adbe58d45c` | 胡姬八角琉璃酒肆/pressure_modifiers | 1 | 蜃景商路与鬼市 |
| `mat-b495d31a7bca5cd78aa7ea8a20da7ec7` | 胡姬八角琉璃酒肆/privacy | 1 | 蜃景商路与鬼市 |
| `mat-9559a88cb03b5165b4b50d58ad592413` | 胡姬八角琉璃酒肆/visibility | 1 | 蜃景商路与鬼市 |
| `mat-75c501ace67d5c68a2310699aa893321` | 胡姬八角琉璃酒肆/witnesses | 1 | 蜃景商路与鬼市 |
| `mat-15545e39564f5469bea3be07162d3ecd` | 舞厅/affordances | 1 | 民国报馆与手艺街 |
| `mat-5f7530e1c5035d17887f8a96c11e8afa` | 舞厅/exits | 1 | 民国报馆与手艺街 |
| `mat-87256e138bae5a96aacbcfc26efb89e4` | 舞厅/pressure_modifiers | 1 | 民国报馆与手艺街 |
| `mat-32bf57112611579fa7e7adcdfe1b2bea` | 舞厅/privacy | 1 | 民国报馆与手艺街 |
| `mat-999f5b53757b52f989ca9da6b7584a47` | 舞厅/visibility | 1 | 民国报馆与手艺街 |
| `mat-7514e0d770315fefbe779d7884fe2e2f` | 舞厅/witnesses | 1 | 民国报馆与手艺街 |
| `mat-21ea71649a7a54b0acf78dc06550cf42` | 藏经阁/affordances | 1 | 仙门藏书与驿镖 |
| `mat-0c533c3739f95509bbac0c417f02aba7` | 藏经阁/exits | 1 | 仙门藏书与驿镖 |
| `mat-f431ba0f8d1c5fa0a6dd5e076fbb7576` | 藏经阁/pressure_modifiers | 1 | 仙门藏书与驿镖 |
| `mat-a530937186b35d868963279637ee6383` | 藏经阁/privacy | 1 | 仙门藏书与驿镖 |
| `mat-26c7cdc4eee8508c912aefe21edc30d6` | 藏经阁/visibility | 1 | 仙门藏书与驿镖 |
| `mat-6bf3490aeacc5002a6d89cc2d96bb0b6` | 藏经阁/witnesses | 1 | 仙门藏书与驿镖 |
| `mat-d53cc77a24ad58dbaffac7c3a787e117` | 豪门庄园顶楼琴房/affordances | 1 | 成年创作者与校园艺术季 |
| `mat-b331b89c8a395195a11c5c50b38ac8b2` | 豪门庄园顶楼琴房/exits | 1 | 成年创作者与校园艺术季 |
| `mat-decff50814fa5e08b13f49e7ea09df7a` | 豪门庄园顶楼琴房/pressure_modifiers | 1 | 成年创作者与校园艺术季 |
| `mat-c92ee7b94fbc5f4094fa3fe272d8ed9d` | 豪门庄园顶楼琴房/privacy | 1 | 成年创作者与校园艺术季 |
| `mat-e0be1c3b5f375f7f92d0633ffb388e21` | 豪门庄园顶楼琴房/visibility | 1 | 成年创作者与校园艺术季 |
| `mat-4f85653cd04c5d13af2bd598f1539892` | 豪门庄园顶楼琴房/witnesses | 1 | 成年创作者与校园艺术季 |
| `mat-30cc58a70a285e81affa7fc0410efc45` | 车站前旅馆/affordances | 1 | 昭和街角喫茶巡礼 |
| `mat-57ac8caee22053f3ad26e19c422c2808` | 车站前旅馆/exits | 1 | 昭和街角喫茶巡礼 |
| `mat-6d374a5064125ee889a9c5c28e749932` | 车站前旅馆/pressure_modifiers | 1 | 昭和街角喫茶巡礼 |
| `mat-05bb9e8a0a73564ea9bf39c03c0fcf3b` | 车站前旅馆/privacy | 1 | 昭和街角喫茶巡礼 |
| `mat-3a4fe5b073d750ebb58b247addf46a09` | 车站前旅馆/visibility | 1 | 昭和街角喫茶巡礼 |
| `mat-547f006989485154af3c0cf4b0fc8de3` | 车站前旅馆/witnesses | 1 | 昭和街角喫茶巡礼 |
| `mat-647b1fbe5e785fa29fe00129c03ef7b4` | 通宵大排档/affordances | 1 | 磁带与夜市街区 |
| `mat-749d59829e56568596b4cefdb2ae08c1` | 通宵大排档/exits | 1 | 磁带与夜市街区 |
| `mat-7ba8922d679d50d09e4e27f506deb18b` | 通宵大排档/pressure_modifiers | 1 | 磁带与夜市街区 |
| `mat-c07455a3a8f853fbb769de60ef6f688b` | 通宵大排档/privacy | 1 | 磁带与夜市街区 |
| `mat-e2d772d00c385d2db4d1d7921201a698` | 通宵大排档/visibility | 1 | 磁带与夜市街区 |
| `mat-7eb9dedda2395ed381848610d274d320` | 通宵大排档/witnesses | 1 | 磁带与夜市街区 |
| `mat-ebb8dd0842a55022a162fba954f5c412` | 避难所防爆闸门前/affordances | 1 | 寒冬避难所公共生活 |
| `mat-e8037f92ff0350359be5f65c6652f732` | 避难所防爆闸门前/exits | 1 | 寒冬避难所公共生活 |
| `mat-a2649735376a5f75acdd510d75435b1d` | 避难所防爆闸门前/pressure_modifiers | 1 | 寒冬避难所公共生活 |
| `mat-6d479ea71b4d57fead785a376119b23e` | 避难所防爆闸门前/privacy | 1 | 寒冬避难所公共生活 |
| `mat-32e033a47cac56de9323f6761e30e972` | 避难所防爆闸门前/visibility | 1 | 寒冬避难所公共生活 |
| `mat-82209f2c461e592e90648601ccb57cf7` | 避难所防爆闸门前/witnesses | 1 | 寒冬避难所公共生活 |
| `mat-710ece499b4b535699ad6fb6359ed9c3` | 酒店套房/affordances | 1 | 城市休闲与共享会客 |
| `mat-c74f8dc2bdf254e88078cb6ec8961fd1` | 酒店套房/exits | 1 | 城市休闲与共享会客 |
| `mat-3b35ee7e44555ca1827d4a94c0f05fb2` | 酒店套房/pressure_modifiers | 1 | 城市休闲与共享会客 |
| `mat-d9148854ea7d5185b18136bca7b226ce` | 酒店套房/privacy | 1 | 城市休闲与共享会客 |
| `mat-8f62bfb02ece55c4a4ddc3771140de5a` | 酒店套房/visibility | 1 | 城市休闲与共享会客 |
| `mat-ea60cd2001e752ef92f2642c300ddf82` | 酒店套房/witnesses | 1 | 城市休闲与共享会客 |
| `mat-6a3b55b5a9f35fdc9c802d0932a4f6de` | 钱汤/affordances | 1 | 昭和街角喫茶巡礼 |
| `mat-a865873a9dbe5d5e83d0ffe58901c616` | 钱汤/exits | 1 | 昭和街角喫茶巡礼 |
| `mat-582f84dfeec95551a1a522fad99a6eb8` | 钱汤/pressure_modifiers | 1 | 昭和街角喫茶巡礼 |
| `mat-036a020ff2385c03aa5933b6c6f01940` | 钱汤/privacy | 1 | 昭和街角喫茶巡礼 |
| `mat-853a9c11a9af554fb1157e9e8d36f44b` | 钱汤/visibility | 1 | 昭和街角喫茶巡礼 |
| `mat-d4eb3901bcee5d6193de3996bc60a882` | 钱汤/witnesses | 1 | 昭和街角喫茶巡礼 |
| `mat-686e25c65cb256768312f3ba90da4eb5` | 银座料亭/affordances | 1 | 明治洋裁与译书町 |
| `mat-24d9d26ecc615aaa912ad51a7bcfa631` | 银座料亭/exits | 1 | 明治洋裁与译书町 |
| `mat-8368616943e8577bafc755acd93947d7` | 银座料亭/pressure_modifiers | 1 | 明治洋裁与译书町 |
| `mat-6d2d7cb2fb535192b9a0ea46b38a0b69` | 银座料亭/privacy | 1 | 明治洋裁与译书町 |
| `mat-9cc6399c075e5027a19c3e49072e446f` | 银座料亭/visibility | 1 | 明治洋裁与译书町 |
| `mat-8c254382ff16581081a4f8c6fcc07728` | 银座料亭/witnesses | 1 | 明治洋裁与译书町 |
| `mat-81d3aae2614953099a08c9e9cfb0e62a` | 镖局/affordances | 1 | 仙门藏书与驿镖 |
| `mat-23b408b81e3f5629ae11f2263d09b99f` | 镖局/exits | 1 | 仙门藏书与驿镖 |
| `mat-2322cce484225e968c18a3f33c701795` | 镖局/pressure_modifiers | 1 | 仙门藏书与驿镖 |
| `mat-42f05646253859838bc4073a16b94752` | 镖局/privacy | 1 | 仙门藏书与驿镖 |
| `mat-8e44b02f60fd5fa5a99e2de23104e489` | 镖局/visibility | 1 | 仙门藏书与驿镖 |
| `mat-d3dca8a6a8f15e2c95b7d85a670f5577` | 镖局/witnesses | 1 | 仙门藏书与驿镖 |
| `mat-e72c0146fdc15150a35e1c772ee1b7ff` | 长安地底暗渠方士石坛/affordances | 1 | 长安夜市与坊志 |
| `mat-1c059025920e504aa3a1cafbccdf66ef` | 长安地底暗渠方士石坛/exits | 1 | 长安夜市与坊志 |
| `mat-6e5f85dc341b5b51810683768ecd5dcc` | 长安地底暗渠方士石坛/pressure_modifiers | 1 | 长安夜市与坊志 |
| `mat-aacd1015f2c05e67a3554a70bb0ba1d6` | 长安地底暗渠方士石坛/privacy | 1 | 长安夜市与坊志 |
| `mat-6a8edf1d27db55d7943802df71bffff2` | 长安地底暗渠方士石坛/visibility | 1 | 长安夜市与坊志 |
| `mat-9ca80441f848556b8b1ee8bf09a9fce3` | 长安地底暗渠方士石坛/witnesses | 1 | 长安夜市与坊志 |
| `mat-a9a4e9b910d658c4b08ac737e357ec19` | 雾码头仓库/affordances | 1 | 雾都钟表与港务街 |
| `mat-31c2c58215f557408bc121468b6238b3` | 雾码头仓库/exits | 1 | 雾都钟表与港务街 |
| `mat-3cdf109056f051cd99449bf847c1adcb` | 雾码头仓库/pressure_modifiers | 1 | 雾都钟表与港务街 |
| `mat-55c7c79b50995f47b0133f132938b48e` | 雾码头仓库/privacy | 1 | 雾都钟表与港务街 |
| `mat-87093a20be095100821d55e7a8df326e` | 雾码头仓库/visibility | 1 | 雾都钟表与港务街 |
| `mat-30e63f0194dd5a4fa7dd0ff2b15c414b` | 雾码头仓库/witnesses | 1 | 雾都钟表与港务街 |
| `mat-dd8f775e52605beaaffa78b38bc188c1` | 雾都洋馆/affordances | 1 | 雾都钟表与港务街 |
| `mat-d5507b4b541957b790ccd051bd294802` | 雾都洋馆/exits | 1 | 雾都钟表与港务街 |
| `mat-1aa1e1fed0da5d49b0467b38bd8ed214` | 雾都洋馆/pressure_modifiers | 1 | 雾都钟表与港务街 |
| `mat-35ece92a01435520b43e292dc5c2b22e` | 雾都洋馆/privacy | 1 | 雾都钟表与港务街 |
| `mat-fa70bf4f313b570b8911a046d11bc334` | 雾都洋馆/visibility | 1 | 雾都钟表与港务街 |
| `mat-d7b4785a66745de7a7f61b7f02bcb8dc` | 雾都洋馆/witnesses | 1 | 雾都钟表与港务街 |
| `mat-aa7ca0cd19915e1786a3c13fd529f7f2` | 露营营地/affordances | 1 | 远途休假与小镇停留 |
| `mat-b2132e2dc72c535fad20c9f92eefb542` | 露营营地/exits | 1 | 远途休假与小镇停留 |
| `mat-67099914f072510f9062b082ef6efafa` | 露营营地/pressure_modifiers | 1 | 远途休假与小镇停留 |
| `mat-93c185d35c1853a283f512f776f571c5` | 露营营地/privacy | 1 | 远途休假与小镇停留 |
| `mat-37a08925b69952eeb12bb87b4262a511` | 露营营地/visibility | 1 | 远途休假与小镇停留 |
| `mat-899ec20d38b259adaad9eed8b52d29dc` | 露营营地/witnesses | 1 | 远途休假与小镇停留 |
| `mat-7d32e9527b205e2faace1a6cc4831125` | 非人族夜市/affordances | 1 | 契约城与非人街坊 |
| `mat-03526e794c215698b589532a6e011cf9` | 非人族夜市/exits | 1 | 契约城与非人街坊 |
| `mat-b83ae847a4d25726becd374d331a92b1` | 非人族夜市/pressure_modifiers | 1 | 契约城与非人街坊 |
| `mat-7e1d8fe9fdfb572d930954cfcaca8037` | 非人族夜市/privacy | 1 | 契约城与非人街坊 |
| `mat-f560f423e1a45e88b6a2f9604c9b146b` | 非人族夜市/visibility | 1 | 契约城与非人街坊 |
| `mat-3249f3f958ab5c829dea11dda3050545` | 非人族夜市/witnesses | 1 | 契约城与非人街坊 |
| `mat-83633f6fc34c5ced9b720b4b846de50c` | 领主石堡/affordances | 1 | 王都工坊与委托街 |
| `mat-2250db4273805a15adc266f071e45e9a` | 领主石堡/exits | 1 | 王都工坊与委托街 |
| `mat-cb8179151c075d109f4fd91379a78787` | 领主石堡/pressure_modifiers | 1 | 王都工坊与委托街 |
| `mat-778f45a53b0c5f6086ac46c3de23fd12` | 领主石堡/privacy | 1 | 王都工坊与委托街 |
| `mat-233ea95fcf57576ca5455d383c0e7be2` | 领主石堡/visibility | 1 | 王都工坊与委托街 |
| `mat-049cccab82fe554dbfd53c237b2098e1` | 领主石堡/witnesses | 1 | 王都工坊与委托街 |
| `mat-dae532f5d45f50d3a4b21094e41b30f6` | 香道馆/affordances | 1 | 明治洋裁与译书町 |
| `mat-cbe0d643fa5457bd8080b64762955140` | 香道馆/exits | 1 | 明治洋裁与译书町 |
| `mat-70ced3dc47315f24b8f41349ae92a4f3` | 香道馆/pressure_modifiers | 1 | 明治洋裁与译书町 |
| `mat-2988908d80445724b8641ea38aa8767a` | 香道馆/privacy | 1 | 明治洋裁与译书町 |
| `mat-e3139c96877b56ceaf4049abf31e48ed` | 香道馆/visibility | 1 | 明治洋裁与译书町 |
| `mat-dc741d96fbda500a8227e589ae68c28c` | 香道馆/witnesses | 1 | 明治洋裁与译书町 |
| `mat-0167405540995182814d3a54baec8c3c` | 马戏团宿营地/affordances | 1 | 流动马戏与机械舞台 |
| `mat-63d0ff2821c55bf193ce4d838f27b4e4` | 马戏团宿营地/exits | 1 | 流动马戏与机械舞台 |
| `mat-9f68c34151ed50cd93c311544f595780` | 马戏团宿营地/pressure_modifiers | 1 | 流动马戏与机械舞台 |
| `mat-c4e4a63b98ea55428d32b8cab946fc32` | 马戏团宿营地/privacy | 1 | 流动马戏与机械舞台 |
| `mat-84dbcc06cbed5375bfa565890606e0d8` | 马戏团宿营地/visibility | 1 | 流动马戏与机械舞台 |
| `mat-d86498ab945252d9b8a96641cfab71b5` | 马戏团宿营地/witnesses | 1 | 流动马戏与机械舞台 |
| `mat-71290e08528454acb7c9b11cc77a37cf` | 高级公寓/affordances | 1 | 城市休闲与共享会客 |
| `mat-0a667cdcfb4b520eb5d170a085097343` | 高级公寓/exits | 1 | 城市休闲与共享会客 |
| `mat-25298feb599c521183853e861d4cdb42` | 高级公寓/pressure_modifiers | 1 | 城市休闲与共享会客 |
| `mat-8843a597bcf25f168fb5aec03e5d6c5f` | 高级公寓/privacy | 1 | 城市休闲与共享会客 |
| `mat-aae5f569f88157008bc8224027ffd882` | 高级公寓/visibility | 1 | 城市休闲与共享会客 |
| `mat-1e6b982e2e4d5c5e9e8149a20d1b9353` | 高级公寓/witnesses | 1 | 城市休闲与共享会客 |
| `mat-9e82ca4a1ede585fa49ada63c4445fd3` | 高速公路服务区/affordances | 1 | 远途休假与小镇停留 |
| `mat-71a33b5136035682a3f234ffed64bc78` | 高速公路服务区/exits | 1 | 远途休假与小镇停留 |
| `mat-a4d5822d66b5534ab4afb97c986c057d` | 高速公路服务区/pressure_modifiers | 1 | 远途休假与小镇停留 |
| `mat-c2deeed7ae155097b7c0b986fdb2b5f0` | 高速公路服务区/privacy | 1 | 远途休假与小镇停留 |
| `mat-866c9e7dabdc5975bf831d719c48bbf3` | 高速公路服务区/visibility | 1 | 远途休假与小镇停留 |
| `mat-e470b17755555afbb07e363c1b66ecba` | 高速公路服务区/witnesses | 1 | 远途休假与小镇停留 |
| `mat-2fb2abf44ee35cf7b335fd33a9e87d6a` | 魔法工坊地下室/affordances | 1 | 王都工坊与委托街 |
| `mat-53a26b2282d15d9d9b90b1cdbf04f33b` | 魔法工坊地下室/exits | 1 | 王都工坊与委托街 |
| `mat-84b60fc5239d5de387d5ee580e04de4f` | 魔法工坊地下室/pressure_modifiers | 1 | 王都工坊与委托街 |
| `mat-363641413bf75c838146820d5238d56b` | 魔法工坊地下室/privacy | 1 | 王都工坊与委托街 |
| `mat-0df3d2414e2e5f54bb862a8d22621caf` | 魔法工坊地下室/visibility | 1 | 王都工坊与委托街 |
| `mat-b98ce4dca1555523a8cf99a4b191814d` | 魔法工坊地下室/witnesses | 1 | 王都工坊与委托街 |
| `mat-1ef886004bd65a489dea7259dc90e365` | 鸭川河畔町屋雨廊/affordances | 1 | 幕末町屋与道场 |
| `mat-c1f19859bdba5357975ce12177de977c` | 鸭川河畔町屋雨廊/exits | 1 | 幕末町屋与道场 |
| `mat-8ea9c52c3cdc5f61bef463c2b172e8fd` | 鸭川河畔町屋雨廊/pressure_modifiers | 1 | 幕末町屋与道场 |
| `mat-bfe67f14cfdc56e0931c039b23f1bda0` | 鸭川河畔町屋雨廊/privacy | 1 | 幕末町屋与道场 |
| `mat-572ad8cfe086515cbef68bec2050bcd1` | 鸭川河畔町屋雨廊/visibility | 1 | 幕末町屋与道场 |
| `mat-8c765d03d8b05fe5930023c97ce5e3a4` | 鸭川河畔町屋雨廊/witnesses | 1 | 幕末町屋与道场 |
| `mat-7b0bdc6c76ac5341b6d86bd5cf1816a0` | 黄昏天台/affordances | 1 | 城市休闲与共享会客 |
| `mat-708179cc8fd25236b2d8124b42414884` | 黄昏天台/exits | 1 | 城市休闲与共享会客 |
| `mat-28ab3af053625c85a4c2fbcb1fa81b4c` | 黄昏天台/pressure_modifiers | 1 | 城市休闲与共享会客 |
| `mat-269e36a17fd055a8b74a477a95399d40` | 黄昏天台/privacy | 1 | 城市休闲与共享会客 |
| `mat-18b2bfdecfdc5574a04be9973f1b2dad` | 黄昏天台/visibility | 1 | 城市休闲与共享会客 |
| `mat-b26e6cae3f8d5ad0987a62bfe157a04d` | 黄昏天台/witnesses | 1 | 城市休闲与共享会客 |
| `mat-fe9e19c6432658bf97910246e2d4d621` | 黑帮教父防弹老爷车/affordances | 1 | 禁酒期爵士与报纸 |
| `mat-c676ba0f6fd95fdcbfb9c2d70961d48c` | 黑帮教父防弹老爷车/exits | 1 | 禁酒期爵士与报纸 |
| `mat-c949a1cd95565584b3e9d2b303ab8dc2` | 黑帮教父防弹老爷车/pressure_modifiers | 1 | 禁酒期爵士与报纸 |
| `mat-87645a640bf45643850db04050f4bf7d` | 黑帮教父防弹老爷车/privacy | 1 | 禁酒期爵士与报纸 |
| `mat-f53c57f1e434507ead67a916733b999a` | 黑帮教父防弹老爷车/visibility | 1 | 禁酒期爵士与报纸 |
| `mat-3dc3a911c0445852a29ccce506b42966` | 黑帮教父防弹老爷车/witnesses | 1 | 禁酒期爵士与报纸 |
| `mat-c5ad93b223b45cc886595a763211f08a` | 龙门客栈地窖/affordances | 1 | 风沙驿站与旧图 |
| `mat-825e8350f5985ad6951014a1fd53b992` | 龙门客栈地窖/exits | 1 | 风沙驿站与旧图 |
| `mat-5adc0d2ac3315365a41adea5f9c588cf` | 龙门客栈地窖/pressure_modifiers | 1 | 风沙驿站与旧图 |
| `mat-c006d63892515e34aae39f03b0367aa1` | 龙门客栈地窖/privacy | 1 | 风沙驿站与旧图 |
| `mat-cb32ecd69ac458b38fdc66c0460629b0` | 龙门客栈地窖/visibility | 1 | 风沙驿站与旧图 |
| `mat-060f357d8803500d943c7d2dc8c8405d` | 龙门客栈地窖/witnesses | 1 | 风沙驿站与旧图 |
| `mat-efd0c2f64abe517784da5b44127f8a8f` | 24小时自习室 | 1 | 成年创作者与校园艺术季 |
| `mat-0233fa50c50356609abe81a339e1851e` | 24小时自助洗衣房 | 1 | 街角共同生活圈 |
| `mat-b0d42453d9ca534cafe0d07923b4b726` | Cosplay暗房 | 1 | 同人街区与录音协作 |
| `mat-620eab2d894b537ca59bdfa113e16109` | livehouse | 1 | 地方行业与公共记忆 |
| `mat-5d618139ee1053e7a51bdc600cd7fe26` | 倒悬石梁地宫 | 1 | 风沙驿站与旧图 |
| `mat-688ec10c23e759f19471b697849480bd` | 偏远小镇唯一便利店 | 1 | 远途休假与小镇停留 |
| `mat-cb87688a060a5e4e86ad9896ca819bf4` | 停电民宿客厅 | 1 | 远途休假与小镇停留 |
| `mat-add34f0be97d55f888bddf2177fbf598` | 健身房 | 1 | 城市休闲与共享会客 |
| `mat-2881588a76fa5f48924893aaa0af94c5` | 全息酒吧 | 1 | 赛博街区与公共终端 |
| `mat-750c3dea61915e29a288617768fc6481` | 写字楼 | 1 | 赛博街区与公共终端 |
| `mat-a67a601e768156c49646ff9cd4aa3d06` | 列车车厢 | 1 | 千禧网络街坊 |
| `mat-ca52e9e6f55b5368b3f4b4532dc1486b` | 剧院后台 | 1 | 成年创作者与校园艺术季 |
| `mat-b1d5353623dd534199a83afb94821b88` | 医院住院部走廊 | 1 | 地方行业与公共记忆 |
| `mat-4cd20a55969a516490954069eda021f0` | 医馆后堂 | 1 | 湘西山路与乡志 |
| `mat-e08b2ac494875e4fba23364e043b8d16` | 古籍书店 | 1 | 王朝百业与书院 |
| `mat-9f6de11513e25eb489939dc692014525` | 同人展备用更衣室 | 1 | 同人街区与录音协作 |
| `mat-64867ef045b0564ba3edd3bd8cdbcaaf` | 回程前的空车站 | 1 | 远途休假与小镇停留 |
| `mat-b606bf05b8b45ad7b0cfb76323ff17cd` | 团地走廊 | 1 | 昭和街角喫茶巡礼 |
| `mat-eeb8be809eef549bb95bba083400d12a` | 园林 | 1 | 王朝百业与书院 |
| `mat-a3fa5a0f57dd5f0498913c2e77717d1c` | 城隍庙后院 | 1 | 长安夜市与坊志 |
| `mat-f566e9028770596eb98c40a84cfd86a9` | 壬生屯所阴暗道场 | 1 | 幕末町屋与道场 |
| `mat-b5034cbdc3e65c5da4437657db310488` | 声优录音棚 | 1 | 同人街区与录音协作 |
| `mat-1e5a3b51e9545fce87382181699e1423` | 夜航渡轮 | 1 | 海岸渡船与观测旅行 |
| `mat-199f0ddd7dc459efa2674d1887760539` | 大学钢琴练习室 | 1 | 成年创作者与校园艺术季 |
| `mat-e6e4ee5915b95f608176d55e8f48deb5` | 大雁塔顶避风藏经阁 | 1 | 长安夜市与坊志 |
| `mat-1ae82a806c1955d3a50a136ad91be723` | 太空站舱段 | 1 | 星海边境生活站 |
| `mat-537a26712a60594c99d9c1782c54131e` | 契约登记所 | 1 | 契约城与非人街坊 |
| `mat-c069e9541160595ead3edaaec0bcd30b` | 女仆咖啡厅后厨 | 1 | 同人街区与录音协作 |
| `mat-1d17e6d4edf459579940107650a02233` | 婚礼宴会厅 | 1 | 城市休闲与共享会客 |
| `mat-86fc7fd9f2425a428fc362a64a07bfe9` | 学园祭打烊后的活动室 | 1 | 成年创作者与校园艺术季 |
| `mat-5e268efa5b1e565cb0b2c142883f1502` | 宗族祠堂 | 1 | 王朝百业与书院 |
| `mat-d193c845a1e15cd5ace2f4e10a379086` | 宠物医院 | 1 | 地方行业与公共记忆 |
| `mat-1babd1d165f05d028527016b5c460681` | 室内夜泳馆 | 1 | 城市休闲与共享会客 |
| `mat-029b1c75d65f5abf99d4926fc677526b` | 密歇根湖畔私酒卸货码头 | 1 | 禁酒期爵士与报纸 |
| `mat-8f319af312415247a641e0ce0672b3d9` | 山间温泉旅馆 | 1 | 旧町神怪与灯会 |
| `mat-189990886ce954c1881b8a6efe8b40b1` | 山顶观星台 | 1 | 海岸渡船与观测旅行 |
| `mat-bbb87c9861e55bdb860298ad001e8e73` | 帽店试帽间 | 1 | 雾都钟表与港务街 |
| `mat-c729d744e92750ad8bae7486d9135086` | 废土驿站 | 1 | 废土驿站与修补集市 |
| `mat-548e492677155fe49448cb577291e919` | 废弃搜刮药房 | 1 | 废土驿站与修补集市 |
| `mat-f45c645d8ecc5e74a4635b0fc4401b4c` | 当铺 | 1 | 地方行业与公共记忆 |
| `mat-50a9a1457e945dbcbe1f9900ae6b6762` | 悬空神殿 | 1 | 仙门藏书与驿镖 |
| `mat-b8274e7d568351a1bd2a3d8447104810` | 感染检疫隔离点 | 1 | 检疫站旁的生活区 |
| `mat-2ec1e8c1e5025da89f1e53b70cdd87ec` | 戏楼 | 1 | 王朝百业与书院 |
| `mat-b1d6a7962dca5d278cd17478b5bfbd6c` | 打烊后的买手店 | 1 | 城市休闲与共享会客 |
| `mat-c51fb43885aa5e648866b727343aa870` | 打烊面包店 | 1 | 街角共同生活圈 |
| `mat-c0a3e3256f385f98bc0131892058ac3c` | 拍卖行 | 1 | 民国报馆与手艺街 |
| `mat-2bd22c0cad345bea80fe8f134f832d99` | 旗袍定制店 | 1 | 民国报馆与手艺街 |
| `mat-163ec4cc4b9f51dc9fc56f5e131b60f3` | 无相鬼市千佛暗窟 | 1 | 蜃景商路与鬼市 |
| `mat-13b92d8d872350fa9a4eabf2866d8c59` | 昭和喫茶店 | 1 | 昭和街角喫茶巡礼 |
| `mat-1e4568a0e37752a780da88edf6dc0811` | 最后一班渡轮 | 1 | 远途休假与小镇停留 |
| `mat-e55f44f6c5345c76859c6a5aea23a4e8` | 朋友客厅 | 1 | 街角共同生活圈 |
| `mat-bd2615e0aade5fc48fdab065c5cb6693` | 末班地铁 | 1 | 赛博街区与公共终端 |
| `mat-382e7590996c5e84a9c46199cf81a747` | 桌游店 | 1 | 千禧网络街坊 |
| `mat-7045e5ba174c55868708269816798393` | 殡仪馆 | 1 | 地方行业与公共记忆 |
| `mat-bbebc0183fa6541cbb7ad302a3120a92` | 民国公馆 | 1 | 民国报馆与手艺街 |
| `mat-731bae3cfac35ba2931e4ee894646893` | 江心画舫 | 1 | 王朝百业与书院 |
| `mat-16cb343e51e6521bb6f36b3eced3ea81` | 洋装裁缝铺 | 1 | 明治洋裁与译书町 |
| `mat-b6200907719e581d9c15980ba416a47b` | 洋馆偏屋 | 1 | 明治洋裁与译书町 |
| `mat-ce1635bfed9e51f89beb9db75062405e` | 流动马戏团大篷车 | 1 | 流动马戏与机械舞台 |
| `mat-1a25a45a301a5cab8cb0f2d9b6b96c9c` | 流沙回廊炼金暗房 | 1 | 蜃景商路与鬼市 |
| `mat-3d8e1316fccd59d1bdea37148a5dd63a` | 海岛度假村 | 1 | 远途休假与小镇停留 |
| `mat-6c870e7fed1b500a82f15f43e07775d6` | 海边步道 | 1 | 城市休闲与共享会客 |
| `mat-b439d9a85b885a208c5afd0ca6910f6c` | 海边浴衣祭神社后阶梯 | 1 | 旧町神怪与灯会 |
| `mat-b10f656299485cdda7534aa0c8e22c32` | 深夜便利店 | 1 | 街角共同生活圈 |
| `mat-96f3c7ae62db56b6967114036fcbe317` | 深夜机场候机区 | 1 | 远途休假与小镇停留 |
| `mat-2a05ac67e45c5be1b2bfd89c11bb8be9` | 清晨菜市场 | 1 | 街角共同生活圈 |
| `mat-9c5bf382afd551b09b8fee3bcc3b0eb7` | 灯塔值守屋 | 1 | 海岸渡船与观测旅行 |
| `mat-e7ad79f4a2bb5928aa52e1d313bb387a` | 爵士喫茶 | 1 | 昭和街角喫茶巡礼 |
| `mat-13d0da65a92458d081e0d6243c0af3fe` | 理发店暗门后地下酒吧 | 1 | 禁酒期爵士与报纸 |
| `mat-37fa12bd06695e23a1c490f05b58ad19` | 电竞俱乐部 | 1 | 地方行业与公共记忆 |
| `mat-d054a64564a65dafbc79dcbd7715463e` | 电竞基地训练室 | 1 | 同人街区与录音协作 |
| `mat-41b36e8a6ba35a3ab2782afd50afd40d` | 画廊 | 1 | 成年创作者与校园艺术季 |
| `mat-cfc8f260559b57cf9ab4c6b1cdfbe81d` | 疗养院 | 1 | 后方邮路与灯火 |
| `mat-40577274fa645f88b129e76ca4cd99b7` | 直播平台危机会议室 | 1 | 传媒编辑室与公开记录 |
| `mat-4679b556c48b51cd9f42671c92a8050f` | 真名保管库 | 1 | 契约城与非人街坊 |
| `mat-1c70f10227ba523b874ce1ce039e3db4` | 社区诊所 | 1 | 街角共同生活圈 |
| `mat-757b5c836b405bfd9770a9c82e93c51e` | 神乐坂置屋 | 1 | 幕末町屋与道场 |
| `mat-3b267397cd1d51b59c94ab90a768de2e` | 私人游艇 | 1 | 海岸渡船与观测旅行 |
| `mat-ff04a8236b1357568bc04d7155953982` | 私家宅邸 | 1 | 城市休闲与共享会客 |
| `mat-380d97a9a214578ab14f8a860d8a6ce8` | 私立诊察室 | 1 | 雾都钟表与港务街 |
| `mat-ca59252858c55ea78f49e47bf64aebc1` | 立体停车库 | 1 | 赛博街区与公共终端 |
| `mat-abc39413d122591e91fa3042484e0785` | 红丝绒马戏大帐篷 | 1 | 流动马戏与机械舞台 |
| `mat-2f39c2ac6800517a84572ac73e9ce9dd` | 结界检查站 | 1 | 契约城与非人街坊 |
| `mat-2c0f711e2d7859229b8692d55d041cb7` | 美术馆 | 1 | 传媒编辑室与公开记录 |
| `mat-e07764235d6755e193d0a331aaed6e3a` | 老旧小区 | 1 | 街角共同生活圈 |
| `mat-ec184854b15c512d8ea485713953916f` | 老茶馆 | 1 | 王朝百业与书院 |
| `mat-15f7d30a8a6e5e3187f86cd26b8a5882` | 胡姬八角琉璃酒肆 | 1 | 蜃景商路与鬼市 |
| `mat-97f4f8639d4256a48c9903da1e18be76` | 舞厅 | 1 | 民国报馆与手艺街 |
| `mat-3a664c762fd75a2c95565a973e497ffa` | 藏经阁 | 1 | 仙门藏书与驿镖 |
| `mat-97afb746e8a95048a555987b27218c22` | 豪门庄园顶楼琴房 | 1 | 成年创作者与校园艺术季 |
| `mat-d66c2505a93a5fa2baf0a0495a3b44bd` | 车站前旅馆 | 1 | 昭和街角喫茶巡礼 |
| `mat-9ffb6120a3eb52fc80f425028fe9aaae` | 通宵大排档 | 1 | 磁带与夜市街区 |
| `mat-0948c73071f258fabf342a4023dbbde5` | 避难所防爆闸门前 | 1 | 寒冬避难所公共生活 |
| `mat-461cb1ea741056dc82ab7e24587aa985` | 酒店套房 | 1 | 城市休闲与共享会客 |
| `mat-d7767bb63d6f5bcba1dbec3668c580a4` | 钱汤 | 1 | 昭和街角喫茶巡礼 |
| `mat-52d27953dbb959c5a8e41af2b68a8906` | 银座料亭 | 1 | 明治洋裁与译书町 |
| `mat-e16121c08c335b49b28577550f9808fd` | 镖局 | 1 | 仙门藏书与驿镖 |
| `mat-a43396fd47945557a655ab9873acad05` | 长安地底暗渠方士石坛 | 1 | 长安夜市与坊志 |
| `mat-c94b0917f7345739aa183d1f5112e2be` | 雾码头仓库 | 1 | 雾都钟表与港务街 |
| `mat-6c24f63ec18b5c99bc5709682a1963d4` | 雾都洋馆 | 1 | 雾都钟表与港务街 |
| `mat-cbc6be5260cf542b87b3ccfcb3f915ed` | 露营营地 | 1 | 远途休假与小镇停留 |
| `mat-70c1754a69fb5d38a0f6d41f8a73f8b2` | 非人族夜市 | 1 | 契约城与非人街坊 |
| `mat-7798d6e379c45d1a879de3b9dd65eefd` | 领主石堡 | 1 | 王都工坊与委托街 |
| `mat-a62acab2d82150ff9e8c0aa635a0aed1` | 香道馆 | 1 | 明治洋裁与译书町 |
| `mat-c2c4b330e4d659f686d8330eede8e077` | 马戏团宿营地 | 1 | 流动马戏与机械舞台 |
| `mat-98d52c21714c53d587b8c2fae1c833cf` | 高级公寓 | 1 | 城市休闲与共享会客 |
| `mat-f5533aec201d5e8e91698e098a9c7600` | 高速公路服务区 | 1 | 远途休假与小镇停留 |
| `mat-7ad7ecec8402551cbd2aba4285888fba` | 魔法工坊地下室 | 1 | 王都工坊与委托街 |
| `mat-22a62833d0325ff48f76167d88cd4b7f` | 鸭川河畔町屋雨廊 | 1 | 幕末町屋与道场 |
| `mat-9eba250d5d74537caa9573ec047aa5a7` | 黄昏天台 | 1 | 城市休闲与共享会客 |
| `mat-122acd5a3d45543b881b2865e0131b83` | 黑帮教父防弹老爷车 | 1 | 禁酒期爵士与报纸 |
| `mat-106cecf0eada56a6b3e413384c4c4875` | 龙门客栈地窖 | 1 | 风沙驿站与旧图 |
| `mat-a09d815442f05defb2c87583391fce9e` | eras/一九二八芝加哥禁酒期 | 1 | 禁酒期爵士与报纸 |
| `mat-a1e7bf3041de53d3aaa84bfe981bf022` | eras/九十年代 | 1 | 磁带与夜市街区 |
| `mat-4d167fda94d655cb8d3692f9748cd4ce` | eras/剑与魔法大陆 | 1 | 退休勇者之城 |
| `mat-0ef8a09d45ed5b93912ec9b5995ce48e` | eras/千禧年前后 | 1 | 千禧网络街坊 |
| `mat-d99770c9cfaa5bdd8395cf097d977ae0` | eras/地下城中层营地 | 1 | 地下城安全层营地 |
| `mat-81778f5ae18853b7a3aa263f807745eb` | eras/异世界王都 | 1 | 王都工坊与委托街 |
| `mat-c96790ad3fb250cb98d7438700f4abe6` | eras/感染爆发初期 | 1 | 检疫站旁的生活区 |
| `mat-0bfd8b24314a53669d6805ba32dadea7` | eras/战时后方 | 1 | 后方邮路与灯火 |
| `mat-3664fde46b585bd1b0955bfd7335e321` | eras/文久幕末京都风云 | 1 | 幕末町屋与道场 |
| `mat-34f9c8bf74465c97a974147059bd5c2c` | eras/旧式民国都市 | 1 | 民国报馆与手艺街 |
| `mat-657b277eb05951bd887374b356674022` | eras/明治东京 | 1 | 明治洋裁与译书町 |
| `mat-2d7bdd51c88c583e868976f097eca406` | eras/星际殖民地 | 1 | 星海边境生活站 |
| `mat-b56a28771ece56a295c8091d4edda5f7` | eras/昭和末期 | 1 | 昭和街角喫茶巡礼 |
| `mat-9ad3bb1f91605064b7b3b50ea4eccbf6` | eras/晚清民初湘西密林 | 1 | 湘西山路与乡志 |
| `mat-6addc6e0da05508984f480b69b11ff14` | eras/架空王朝 | 1 | 王朝百业与书院 |
| `mat-80f7eb5fa4f7566a8917f0537d600808` | eras/架空都市 | 1 | 灵气复苏十年后 |
| `mat-dd2b9c1166285d4fbec6fe1b31b4fee2` | eras/民国初年大漠荒城 | 1 | 风沙驿站与旧图 |
| `mat-c5cd366f88c750aa88ba186d3472665d` | eras/盛唐长安百鬼夜行 | 1 | 长安夜市与坊志 |
| `mat-ae8068b16e1950599329d3d1778ba147` | eras/神怪共存旧町 | 1 | 旧町神怪与灯会 |
| `mat-c3f436fcd29859f0bdae35d8641de00b` | eras/秋叶原架空街区 | 1 | 同人街区与录音协作 |
| `mat-e453be800a615ad9b3f40d6a3e05177e` | eras/维多利亚暗黑马戏团 | 1 | 流动马戏与机械舞台 |
| `mat-da354fd31138564ba4a36c2e09ba7ad5` | eras/维多利亚雾都 | 1 | 雾都钟表与港务街 |
| `mat-ed1a5786bd555399b05ef66bfb146283` | eras/西域大漠蜃景鬼市 | 1 | 蜃景商路与鬼市 |
| `mat-182eef6f31ea53e7ba68001bd67ea950` | eras/近未来都市 | 1 | 赛博街区与公共终端 |
| `mat-adf336d2071757119540d18a6809c537` | eras/避难所管制期 | 1 | 寒冬避难所公共生活 |

## P2 legacy 链清单

共 588 个单元：未被任何框架引用，但位于 `build_opening.py --framework legacy` 显式路径（roll_opening.load_pools/build_roll + fill_opening 填料链，含 `roll_opening --twist`）的读取/抽取域内。按源池组分节。

### action_categories.yaml（1）

| unit_id | label |
|---|---|
| `mat-079668c1d10c515aaf899a72e418d277` | 身体靠近 |

### action_metadata.yaml:身体靠近（3）

| unit_id | label |
|---|---|
| `mat-7ec240d8fc415f03b6a577079d24f207` | 身体靠近/escalation |
| `mat-2f2a75a604d15832b0cb447035e73697` | 身体靠近/function |
| `mat-0501dc0f848f5d8abbca66a67c9adda7` | 身体靠近/visibility |

### character_meta.yaml:人物生成倾向（8）

| unit_id | label |
|---|---|
| `mat-7f8c395501505bbeb99f7713b128ebb5` | 人物生成倾向/conflicted |
| `mat-34848ae76a5a571dbf2b890a981b1f30` | 人物生成倾向/experienced_restrained |
| `mat-d40d155185a7593880fee382001749f2` | 人物生成倾向/inexperienced |
| `mat-ffc625ae50175f928de460d3dddfba1b` | 人物生成倾向/low_desire |
| `mat-4ef20179b5f95e0e82c1c56d8e0f577a` | 人物生成倾向/open_active |
| `mat-f539260868a15e56b86224ceb0b054e6` | 人物生成倾向/ordinary_natural |
| `mat-637a873c599d5006aec0f61d4e8e8071` | 人物生成倾向/playful |
| `mat-7134a576a7e859a09edb1d1b93499b3a` | 人物生成倾向/reserved_sensitive |

### character_meta.yaml:决策轴（3）

| unit_id | label |
|---|---|
| `mat-0f43bacee42c5e2c943a098aba9ac8b0` | 决策轴/关系姿态 |
| `mat-ce0aa5627ef5525d8fc16d97c89a77e0` | 决策轴/压力策略 |
| `mat-2c68e0b61e3f594aac26ce7d84caf411` | 决策轴/核心价值 |

### character_meta.yaml:年龄段区间（5）

| unit_id | label |
|---|---|
| `mat-7115835381fd5f0e9609cdf494b91b44` | 年龄段区间/三十五上下 |
| `mat-8222eb8b278c56af908eee9f29e00fa2` | 年龄段区间/三十出头 |
| `mat-deebe6dcab245417bce25dea08b35316` | 年龄段区间/二十七八 |
| `mat-770b7adc6c835ec6811b8483977fe3d4` | 年龄段区间/二十出头 |
| `mat-f1001fb0f0f251ee873f88269efebc1e` | 年龄段区间/四十出头 |

### character_meta.yaml:社会位置关系（28）

| unit_id | label |
|---|---|
| `mat-20043a4f0ecc5c738d9b618ead76bec2` | 社会位置关系/上司 |
| `mat-23a6e409172d5c0b9db4e313c1a307cf` | 社会位置关系/下属 |
| `mat-fe48c53ae7545c2485fa483e4f756fa9` | 社会位置关系/债主 |
| `mat-6c59c74fb3f95426a8d9cac81627f61a` | 社会位置关系/公会契约使魔 |
| `mat-14df35cadf3e5439aeb61900f31afade` | 社会位置关系/共同遗产继承人 |
| `mat-28aa1d8f95d55deb8e3e8b25eff3fa28` | 社会位置关系/初次见面的网友 |
| `mat-0ff4e24baf06545096168abeca88f74d` | 社会位置关系/前任 |
| `mat-62668a6ca3d65158ad9fae8bec042431` | 社会位置关系/动力舱维修工 |
| `mat-4c2bfa8e77aa59c5b4ff957b8a2f413e` | 社会位置关系/危机公关处理人 |
| `mat-6f9495c8eaf05adcb1d825046786c51e` | 社会位置关系/合租室友 |
| `mat-5d112e4bd488570abf2a7fc4e7a574fc` | 社会位置关系/合租青梅竹马 |
| `mat-81bd57dc2f90586ab6b3d7e666c36948` | 社会位置关系/同人社团原案脚本师 |
| `mat-2164fe17237b569c9fde50ea9f9d8757` | 社会位置关系/名门特聘家教 |
| `mat-48637c2cf979511cae04a315c513129a` | 社会位置关系/战队专属战术分析师 |
| `mat-4ced664c335a57e983c84421a7b44f60` | 社会位置关系/房东 / 催租人 |
| `mat-8b502e00f8ab548badbf088834cade8c` | 社会位置关系/担保人 / 连带责任人 |
| `mat-fd2560e7fc9151eebd443af6455628a8` | 社会位置关系/搜刮队搭档 |
| `mat-32b61eccc17e59318672d4e13aa1104d` | 社会位置关系/服务提供者 |
| `mat-c7d2d1ed3d3e5de9b5c9fb6b44a03da7` | 社会位置关系/深夜接单的代驾 |
| `mat-351a4daf79fc5a08bc75f2463826b239` | 社会位置关系/相亲对象 |
| `mat-01f214e7d5205a25b76078927d5ccbbf` | 社会位置关系/知情不报者 |
| `mat-57014afc47a65203bffd4b28aeaa524a` | 社会位置关系/竞争者 |
| `mat-9497d12f3fef5da4bab51d3c7b0ff56f` | 社会位置关系/被求助者 |
| `mat-10d5ede50ccd512c8c6f852e2ad9d3b6` | 社会位置关系/贴身侍从兼掌眼人 |
| `mat-a24be8d63ecc5cfdbbd8bc3a92a8e311` | 社会位置关系/远房亲戚 |
| `mat-3490e82ca100539994acf1844c57d8d8` | 社会位置关系/避难所检疫员 |
| `mat-89b23ec0b19c5494bb4182d677205056` | 社会位置关系/黑夜佣兵统帅 |
| `mat-4d7e0c063a2a5c479b46bb22a132a1b8` | 社会位置关系/黑市药贩 |

### character_meta.yaml:配角功能（1）

| unit_id | label |
|---|---|
| `mat-fc316c8faee2525fa50c7159e05b8b4c` | 配角功能 |

### character_pools.yaml:口癖（9）

| unit_id | label |
|---|---|
| `mat-b419784dafff5e42abaaadf3d8a0244d` | 口癖/典雅语感 |
| `mat-d214d12fa02d5623bf10665b15fe2f2d` | 口癖/句式节奏 |
| `mat-24b44394dd065233ac05e135acbdd82b` | 口癖/称呼习惯 |
| `mat-b02d8f09a6a059c58ef0d9b99f7a238a` | 口癖/自言习惯 |
| `mat-b522be2d3f6e5876b4cb1ddeed8396bc` | 口癖/表达策略 |
| `mat-94f9cece3a275b06afb2bc465a5ce6d2` | 口癖/词汇底色 |
| `mat-c166d741ab565b75b339d6c5c9508bcb` | 口癖/语域腔调 |
| `mat-5a86fb897dd65c93b866d3c683fda6aa` | 口癖/里层口头 |
| `mat-d772c29a30485721b560055940ea9867` | 口癖/音量语气 |

### character_pools.yaml:外观轴（9）

| unit_id | label |
|---|---|
| `mat-92d65da4dd6855d1bdfcad799dfa27bb` | 外观轴/体型气质 |
| `mat-c6ac282e70b95cb0826b88c6d1b157d6` | 外观轴/发型 |
| `mat-414a68d97e0258ba95a5de79626141de` | 外观轴/发色 |
| `mat-865046d3393059159ecc2cb1ac63b9f1` | 外观轴/嗓音 |
| `mat-f94fc55eda00513387e381ddc972e05b` | 外观轴/手部 |
| `mat-a4c4e8250ced565b94c6077f7ef02887` | 外观轴/标志配饰 |
| `mat-1065329a7dd65a4e9528cc614fa7722d` | 外观轴/气味与体温 |
| `mat-698dd478af3c505382bad8200e7dbcd5` | 外观轴/着装 |
| `mat-8d50b9eb91285630b94b096a59a196ec` | 外观轴/瞳与面部 |

### character_pools.yaml:表层风味（17）

| unit_id | label |
|---|---|
| `mat-9038709e3b015430ae33703e824d2c66` | 表层风味/侠气江湖 |
| `mat-56c8ae30a3f052749bb203e85b4ab101` | 表层风味/傲娇反差 |
| `mat-f0307beca72c5d87855c09bb762e01df` | 表层风味/傲慢高冷 |
| `mat-19992c7158d75c04aa8c7279184dfb37` | 表层风味/其他单体 |
| `mat-6102fd6c2ae35211a522bfba3d490f77` | 表层风味/军旅飒爽 |
| `mat-03f007cc66685a2db8879d8c60f4adad` | 表层风味/冷淡疏离 |
| `mat-1016bf0a95e05d96add4c7ef4ecf5d2a` | 表层风味/危险腹黑 |
| `mat-17be45ec07715d2bb5afc1cc7fe6563a` | 表层风味/巫祝神秘 |
| `mat-df5e69f179315fb291e505f830008f9c` | 表层风味/成熟市井 |
| `mat-b59e00c023f05f328f204a7cfbdd61ee` | 表层风味/活力外放 |
| `mat-30a23330d4d05cd8ab8102ec46bf6ed2` | 表层风味/温柔亲和 |
| `mat-b11d3c5d7bf9597ebec00dfad5cfb2ad` | 表层风味/破碎易感 |
| `mat-ace5c8a8bc0b5e37a2948eb9c1a4e36b` | 表层风味/端庄教养 |
| `mat-5e6d839541525318887c14ab978ae512` | 表层风味/艳丽魅惑 |
| `mat-9434000e844f540e8fca863850c034ac` | 表层风味/街头亚文化 |
| `mat-8cbf06e394245461a798e77b1c4b5d21` | 表层风味/认真内敛 |
| `mat-fb5151aaafc15df88068c99c8412bf3e` | 表层风味/运动系 |

### identities.yaml:npc（身份侧/社会位置 池联动）（9）

| unit_id | label |
|---|---|
| `mat-db3a425952005b7d8f9cbd9292f05339` | npc/传统与雅艺 |
| `mat-4f17b96903345f7a871101bc642f9679` | npc/侍奉与身契 |
| `mat-eb2d8901d7e055c7ad227acfa36ad154` | npc/地下与灰色地带 |
| `mat-01f0b5bb42e25cd8a33b1077eed7f647` | npc/家族与继承 |
| `mat-79cc2ec7129858089590fd92ff0ed0e7` | npc/屏幕与镜头 |
| `mat-550cc15d4bf35926ad747aa943a0ae2d` | npc/成人行业与感官服务 |
| `mat-6d43bc023a3d539a8e33af992468a55d` | npc/私密撮合与契约中介 |
| `mat-39d05753e1f5537db93782f257bf7e4c` | npc/秩序与执法 |
| `mat-ed232f9c6ffa5a2fb2172c5c36ee5031` | npc/终点与殡葬 |

### identities.yaml:player（身份侧/社会位置 池联动）（28）

| unit_id | label |
|---|---|
| `mat-fbd20c7a965e55b2a8b4eec09204ae18` | player/上司 |
| `mat-055b61d40e315a1ab219929f492dbb08` | player/下属 |
| `mat-0a52ad84df975324aa9e233afd733b23` | player/债主 |
| `mat-5971dde3b31c5c20a2368d94f6b50082` | player/公会契约使魔 |
| `mat-ec44394663985862a7a143f731b572a4` | player/共同遗产继承人 |
| `mat-ebb36baa26d6537aa90ca2427170fb63` | player/初次见面的网友 |
| `mat-f6732d1558965c7eb8367447cbacb23f` | player/前任 |
| `mat-c112d29dd81258ed88478e3ad1c7577f` | player/动力舱维修工 |
| `mat-de4829f76a335489a9a961aeb4da8197` | player/危机公关处理人 |
| `mat-546f312b34b750b3b1eb104929e92b8b` | player/合租室友 |
| `mat-21f2add573045ccbbefabd467adffd92` | player/合租青梅竹马 |
| `mat-8ceb699cbdd251faa0e26caa733ff9e9` | player/同人社团原案脚本师 |
| `mat-b824867a86195ff3a4fdd4ab09b69cf4` | player/名门特聘家教 |
| `mat-591cfff0798b58b592adead830b6d222` | player/战队专属战术分析师 |
| `mat-55b47b3be30d59638fa6182e6f3f4b70` | player/房东 / 催租人 |
| `mat-74f5523d72885198a8ef390f0d53be45` | player/担保人 / 连带责任人 |
| `mat-ade222e156935baea68b709d85a98a0e` | player/搜刮队搭档 |
| `mat-b8405c64f34f530ea7979a73013182e3` | player/服务提供者 |
| `mat-b55e84e9e66a54c7b52522ece0cbde8e` | player/深夜接单的代驾 |
| `mat-f53d4d076a5a58c59d60c5809905802c` | player/相亲对象 |
| `mat-d2adbdeb1c515c1cb82e25ed64b4c921` | player/知情不报者 |
| `mat-2393942071ff51979589e4a48d52f2f1` | player/竞争者 |
| `mat-a5558ebfa92754929bf6516b400c1105` | player/被求助者 |
| `mat-7659a00feb9054ba9eb23a7f07e40fbe` | player/贴身侍从兼掌眼人 |
| `mat-c1c67288ab795016985cde827dddf22d` | player/远房亲戚 |
| `mat-1b70daf95dbe591398a5ca9b0938e303` | player/避难所检疫员 |
| `mat-c4c7eecda8f65d21bec7cd90f748ce87` | player/黑夜佣兵统帅 |
| `mat-94c67d8d0ddd5d53b579a160f6c91b4b` | player/黑市药贩 |

### identity_profiles.yaml:传统与雅艺（7）

| unit_id | label |
|---|---|
| `mat-7181bd41fc22538eb40e72bfdf20c36c` | 传统与雅艺/conflict_response |
| `mat-35af1f2f2b0058ad9a13b8bf8ceb0d2c` | 传统与雅艺/evidence_habit |
| `mat-466384097c6759b3a58ca8002b921256` | 传统与雅艺/exit_preference |
| `mat-b57ed29cee615977b8816eb0a1329f27` | 传统与雅艺/follow_up_style |
| `mat-ed16a5d78a5051fcb12ec7abb84f24b0` | 传统与雅艺/negotiation_style |
| `mat-38cf4e5ba27f509cae4c68411304a247` | 传统与雅艺/public_private_shift |
| `mat-bc7471a29ec75799951bdb320aff6b38` | 传统与雅艺/repair_style |

### identity_profiles.yaml:侍奉与身契（7）

| unit_id | label |
|---|---|
| `mat-0e40ce4a5062536cb70343f504499950` | 侍奉与身契/conflict_response |
| `mat-acef28f84588574faecdbd9104cdd8c8` | 侍奉与身契/evidence_habit |
| `mat-09c3470c80395e62a017ccd3c9cc49b5` | 侍奉与身契/exit_preference |
| `mat-9ad9a3ea3e9e593b8d4072f2cd792ec9` | 侍奉与身契/follow_up_style |
| `mat-3a1be108796f5d43bf6ba2fedf865093` | 侍奉与身契/negotiation_style |
| `mat-8999bff99c815b9fbe83d8274b060a68` | 侍奉与身契/public_private_shift |
| `mat-17ec38daa7c757708f5e6d3b4aa9f627` | 侍奉与身契/repair_style |

### identity_profiles.yaml:地下与灰色地带（7）

| unit_id | label |
|---|---|
| `mat-2b5240c5e3b2539788a4c49774aeda8b` | 地下与灰色地带/conflict_response |
| `mat-70671c78c1c4540e9a301388c941c283` | 地下与灰色地带/evidence_habit |
| `mat-97b17aee63fc57e5bd3da85e5c82a901` | 地下与灰色地带/exit_preference |
| `mat-c6ddcf523f1058859a13a25e31d1dcdd` | 地下与灰色地带/follow_up_style |
| `mat-9d1158e2eafb59aabe6a62ceb55b2780` | 地下与灰色地带/negotiation_style |
| `mat-3579c6e6429b584b9305bb751c59077a` | 地下与灰色地带/public_private_shift |
| `mat-d801652f8af150d2873372bcc32f02ff` | 地下与灰色地带/repair_style |

### identity_profiles.yaml:家族与继承（7）

| unit_id | label |
|---|---|
| `mat-e49c16b57c395355af2c6a8563780d11` | 家族与继承/conflict_response |
| `mat-9fd8b8f742c65fb9b16b663b2f866515` | 家族与继承/evidence_habit |
| `mat-abd3e491208d5f3ba036b3298e337ea6` | 家族与继承/exit_preference |
| `mat-a3d177024bd352daaae12eaaa96b77b0` | 家族与继承/follow_up_style |
| `mat-ddd2559980fe54ccb14f3f0fdb71324f` | 家族与继承/negotiation_style |
| `mat-8d565d4c92a751cbbbcc73981812b4d9` | 家族与继承/public_private_shift |
| `mat-adb25bec7bdb559ea066bf95e35f4a11` | 家族与继承/repair_style |

### identity_profiles.yaml:屏幕与镜头（7）

| unit_id | label |
|---|---|
| `mat-08157f7886e351e29c788acee9d5ae84` | 屏幕与镜头/conflict_response |
| `mat-605a17e8d0e151ce8b94c46eb046d2a8` | 屏幕与镜头/evidence_habit |
| `mat-7834476be76c53c5b5bff60bd09f752d` | 屏幕与镜头/exit_preference |
| `mat-4512bf7c4a9d5727a44f086cabcc06d5` | 屏幕与镜头/follow_up_style |
| `mat-6e4367d151fc5d0fa384a08ae742a19e` | 屏幕与镜头/negotiation_style |
| `mat-a722afb9c92d5c05b865a5a909907715` | 屏幕与镜头/public_private_shift |
| `mat-1355d0158fc3502d82eb295bfed01372` | 屏幕与镜头/repair_style |

### identity_profiles.yaml:成人行业与感官服务（7）

| unit_id | label |
|---|---|
| `mat-c50e95cae3575a6c8cfeeb3bc97758dd` | 成人行业与感官服务/conflict_response |
| `mat-bf1f040ecfaa58ddaea94f5f9f286bb3` | 成人行业与感官服务/evidence_habit |
| `mat-a90fe944f0b4557bbfaa1f3c203bfb74` | 成人行业与感官服务/exit_preference |
| `mat-b4f75e9ae37e597698ac2d3afb6a9eb0` | 成人行业与感官服务/follow_up_style |
| `mat-1edf99df6c925488846a1f2595148cdb` | 成人行业与感官服务/negotiation_style |
| `mat-a111c71ec33f5fa69afa23f21d0e2ee1` | 成人行业与感官服务/public_private_shift |
| `mat-dfac5ee950135302b759d404b90e027d` | 成人行业与感官服务/repair_style |

### identity_profiles.yaml:私密撮合与契约中介（7）

| unit_id | label |
|---|---|
| `mat-54b042008c2c59898a2fe604a234ba3e` | 私密撮合与契约中介/conflict_response |
| `mat-9c58d57370665ed48e9ff79f9e9bbb86` | 私密撮合与契约中介/evidence_habit |
| `mat-15f0b4c869a65488a7d26638e3c4b14a` | 私密撮合与契约中介/exit_preference |
| `mat-91edc4aa03dd52aa9589284de49c8560` | 私密撮合与契约中介/follow_up_style |
| `mat-949034b151715fd8ba91a704c25896bf` | 私密撮合与契约中介/negotiation_style |
| `mat-c4fb9943ac665b5abdecc64179574a87` | 私密撮合与契约中介/public_private_shift |
| `mat-6989fd52383d5582973f86c4f4aa4e96` | 私密撮合与契约中介/repair_style |

### identity_profiles.yaml:秩序与执法（7）

| unit_id | label |
|---|---|
| `mat-51271c0df6ee5c6690f696396b286149` | 秩序与执法/conflict_response |
| `mat-514245d466f95fdbaf7d1113d2a2e990` | 秩序与执法/evidence_habit |
| `mat-cde27f3c371656438007278f30718331` | 秩序与执法/exit_preference |
| `mat-6472dc57b94d57be9ce8efc8ad9bf57a` | 秩序与执法/follow_up_style |
| `mat-dd07d60a40e2567da7e1601f04306401` | 秩序与执法/negotiation_style |
| `mat-2df587abde3d58e88f8d1ee8cdbfa692` | 秩序与执法/public_private_shift |
| `mat-73ca264fd54051ed977f75f720bfcd14` | 秩序与执法/repair_style |

### identity_profiles.yaml:终点与殡葬（7）

| unit_id | label |
|---|---|
| `mat-8ac857d419025b298d7df50b18390e5e` | 终点与殡葬/conflict_response |
| `mat-c6ccfcba940251eabc70782bfb4a3456` | 终点与殡葬/evidence_habit |
| `mat-365db7cda7b45e95ad50f26c0731d73f` | 终点与殡葬/exit_preference |
| `mat-ca33fe5cd8de524ca8a8876c44a7a3d4` | 终点与殡葬/follow_up_style |
| `mat-65349eb3c15d56e08d4e7b2103153df7` | 终点与殡葬/negotiation_style |
| `mat-20e6d06e36335a329a0465b0434ec0e5` | 终点与殡葬/public_private_shift |
| `mat-320a608981795dd0942d2d142a2c64b3` | 终点与殡葬/repair_style |

### location_profiles.yaml:夜场会所（6）

| unit_id | label |
|---|---|
| `mat-a5c781b073985bf9b15e507c9e23c201` | 夜场会所/affordances |
| `mat-40568e6de58853bbb369c7dd23d15663` | 夜场会所/exits |
| `mat-6bee2636c6d25111b6b1b43fdc82ef5e` | 夜场会所/pressure_modifiers |
| `mat-cceeb3b75a5d5fa6999d7bbfcb000092` | 夜场会所/privacy |
| `mat-b77e29ba342b5eb184bee94f71ffdbec` | 夜场会所/visibility |
| `mat-ce1b96731e845a578cfbf9df22367924` | 夜场会所/witnesses |

### location_profiles.yaml:平康坊顶层花魁琴房（6）

| unit_id | label |
|---|---|
| `mat-7705960913b45b15b3035b7f9dde22f4` | 平康坊顶层花魁琴房/affordances |
| `mat-3cacb636ee6452af8457337edfb27582` | 平康坊顶层花魁琴房/exits |
| `mat-39d7e236178756568984830036c8c6f6` | 平康坊顶层花魁琴房/pressure_modifiers |
| `mat-4aa8173a880a5e4f97de3e1fd418d092` | 平康坊顶层花魁琴房/privacy |
| `mat-a435029074c15d86acd3f43c6e3c8dab` | 平康坊顶层花魁琴房/visibility |
| `mat-5a33df86f9af51099991fba69b7d13de` | 平康坊顶层花魁琴房/witnesses |

### location_profiles.yaml:洗浴中心（6）

| unit_id | label |
|---|---|
| `mat-625202b8d7f85439ae985b6a481ba460` | 洗浴中心/affordances |
| `mat-3c79b0a2cdd454a1a4397dc9882bc177` | 洗浴中心/exits |
| `mat-0203c158facb5ada80c792c715cf924b` | 洗浴中心/pressure_modifiers |
| `mat-f07bc2c699f15cde819569ca6fddc82a` | 洗浴中心/privacy |
| `mat-5e9f0520b09d531da088bb17b6cdf5c3` | 洗浴中心/visibility |
| `mat-0cb76f49a42a5a34ae9142d54de80051` | 洗浴中心/witnesses |

### location_profiles.yaml:猛兽铁笼暗室车厢（6）

| unit_id | label |
|---|---|
| `mat-49ce5df1c297573fad7223916a67a085` | 猛兽铁笼暗室车厢/affordances |
| `mat-335e4b6d053b566c94c5aa8440efbb6c` | 猛兽铁笼暗室车厢/exits |
| `mat-20e6c5ca7fe356edad81080cb6b77349` | 猛兽铁笼暗室车厢/pressure_modifiers |
| `mat-ba201b231b7e562cbb680da5f1dcd4f3` | 猛兽铁笼暗室车厢/privacy |
| `mat-897b6462d0de52aeaad2fee31ba8d88f` | 猛兽铁笼暗室车厢/visibility |
| `mat-c29b12223c865d6796727c3642223cde` | 猛兽铁笼暗室车厢/witnesses |

### location_profiles.yaml:祗园艺伎置屋纸拉门后（6）

| unit_id | label |
|---|---|
| `mat-9c31911ee39950ccb2e093b841d3571c` | 祗园艺伎置屋纸拉门后/affordances |
| `mat-2ffd8a71694d5dada4ce966b480ac159` | 祗园艺伎置屋纸拉门后/exits |
| `mat-db43662b78ad56459d0169f060ca78f2` | 祗园艺伎置屋纸拉门后/pressure_modifiers |
| `mat-d5c02116ee815f2c9e5862f4615bed4d` | 祗园艺伎置屋纸拉门后/privacy |
| `mat-4c88e6dbd0a55c6d80049b237be2235e` | 祗园艺伎置屋纸拉门后/visibility |
| `mat-758bb314b42256409b0748acb8cabed6` | 祗园艺伎置屋纸拉门后/witnesses |

### locations.yaml（5）

| unit_id | label |
|---|---|
| `mat-35ab1b43a77654129b963566c214ed6f` | 夜场会所 |
| `mat-6a2617c46cc95357bdcc5d83ce2f1a6d` | 平康坊顶层花魁琴房 |
| `mat-3eaf06778141583ebd09969a35e705f2` | 洗浴中心 |
| `mat-7510d634f91e5ed08460094c49a1e74b` | 猛兽铁笼暗室车厢 |
| `mat-3eb4054afed15917bd0a946586dd7a4c` | 祗园艺伎置屋纸拉门后 |

### names.yaml:顶层回退名池（3）

| unit_id | label |
|---|---|
| `mat-466e36f24a1a5825bc2bcda4b610bd0f` | given_female |
| `mat-a8931907a81b51e498f900c45629200e` | given_male |
| `mat-cdf0fcd9fc2e5e5990b96daef2ca622f` | surnames |

### pools.yaml:meta（10）

| unit_id | label |
|---|---|
| `mat-f58f1bc1a4f6532487dea3b7e877b50d` | meta/aesthetic_eras |
| `mat-763e0c77c9f658b7ae8f756caea724cf` | meta/daily_opening |
| `mat-cdd7c2a5d66e51dda82a2531de987755` | meta/gate_aesthetics |
| `mat-bf1b11b7a8195b1e8508474af8127c1d` | meta/identity_weights |
| `mat-c207b07932d652deb385c991327a9292` | meta/leverage_engines |
| `mat-ab0245956bc056d89679a59658de45d1` | meta/location_eras |
| `mat-d31d0ab0e1875388a94890516879b310` | meta/material_compatibility |
| `mat-cf6988cf9b045e738527ed75f0859362` | meta/situation_leverage |
| `mat-2077cd01859653aeb23c4745020dcca7` | meta/timed_pressures |
| `mat-84a36e2c46a35581aaa97810c9a125dd` | meta/timed_situations |

### pools.yaml:反差轴（26）

| unit_id | label |
|---|---|
| `mat-e27fc579bee15bf2af73e777fefcb14e` | 反差轴/世故笨拙 |
| `mat-696d4aeba9fe5138960d7885549869d9` | 反差轴/严苛沦陷 |
| `mat-1656e7cfc5875414a546022100ad6f2e` | 反差轴/主导渴从 |
| `mat-3a6a13992d7c55719f810c67a7a0ccaf` | 反差轴/假小子娇羞 |
| `mat-16cf27f807215d6abfb6ae3c3f8dc867` | 反差轴/健谈守口 |
| `mat-bcf1117302275242911832cce4fc22d2` | 反差轴/傲沉易推 |
| `mat-127f5bfca85d5ae98e190203876e2187` | 反差轴/克制失控 |
| `mat-232ccff3011357f49a0e7764892cca2b` | 反差轴/刻薄依恋 |
| `mat-d2b518192c115219ad1c72a605a078e5` | 反差轴/外冷内热 |
| `mat-0a52ee5e336f5da197bdaa05e860e853` | 反差轴/大小姐笨拙 |
| `mat-442c083ad8fa5627a32d832ed888c9c5` | 反差轴/女骑羞赧 |
| `mat-d0ab08eae7255619b4a682c16209dea8` | 反差轴/妖艳羞怯 |
| `mat-9aff5645f23853c98c46e3509a3deae7` | 反差轴/市侩重义 |
| `mat-afbcb11d1343506aaa75bc12c638f398` | 反差轴/强势示弱 |
| `mat-2682fa162e605e6a94f00ff59437a6c4` | 反差轴/御姐撒娇 |
| `mat-dcffa43f77f456738b5dfe8873b23477` | 反差轴/无口心热 |
| `mat-6038c56e4b975d45b82ad0e812fce6f7` | 反差轴/武者破戒 |
| `mat-49e7df7a26ab518eaa7fce34538610b8` | 反差轴/毒舌心软 |
| `mat-0c3556e943a852ee8012e6861fdbb990` | 反差轴/泼辣胆小 |
| `mat-8aea8f5bb16b59ceb48ac36518166f3b` | 反差轴/疏离黏人 |
| `mat-f5b15a6aa5c2506c8c8e2d6c2c996452` | 反差轴/禁欲破戒 |
| `mat-953a234cdab0576ba00234490b40f632` | 反差轴/端庄放浪 |
| `mat-8b1e2cfd3eef5322824fa9ac18fdf0be` | 反差轴/粗人细活 |
| `mat-59b3ea4339d850b3a6676b11cc4868af` | 反差轴/精明糊涂 |
| `mat-2c9a28aaf8295cc1b18a5cdd577b7d37` | 反差轴/老练纯情 |
| `mat-a6b93636f8205adf97ea8658eb2c8772` | 反差轴/高岭破防 |

### pools.yaml:权力结构（4）

| unit_id | label |
|---|---|
| `mat-f2c45a06f42a586e8c5b7d143b326fd5` | 权力结构/equal |
| `mat-92ebb18ac45d5ce4a96525f966ce76f8` | 权力结构/npc_high |
| `mat-7160d6ac9a7e5059bfa79c597a18213d` | 权力结构/player_high |
| `mat-695b581f2aa9538a8a62ef3ce80abd7b` | 权力结构/switchable |

### pools.yaml:玩家化身轴/年龄段（5）

| unit_id | label |
|---|---|
| `mat-20c9c909d43b55c9a81b60bfb3e3afef` | 玩家化身轴/年龄段/三十五上下 |
| `mat-4fd97b61971950d4affb6ebd20a1101c` | 玩家化身轴/年龄段/三十出头 |
| `mat-2bcb35ec942c558abf36f7ddb2c19d68` | 玩家化身轴/年龄段/二十七八 |
| `mat-36a2bffd212d57189d6a7bdf3eeee27f` | 玩家化身轴/年龄段/二十出头 |
| `mat-cad1ddb5f95b54319643052fb60ff016` | 玩家化身轴/年龄段/四十出头 |

### templates.yaml:contrast_line（26）

| unit_id | label |
|---|---|
| `mat-e75b896a9dcd5194a683dbd18dd796b8` | contrast_line/世故笨拙 |
| `mat-9293083c3e9f571ab02a0aca2660e122` | contrast_line/严苛沦陷 |
| `mat-f7c4bb2679485a82bc5ea66ed2a5b801` | contrast_line/主导渴从 |
| `mat-6a88509235dc51a5a17337303a26efb0` | contrast_line/假小子娇羞 |
| `mat-54490917c9755c3195f70821907ba627` | contrast_line/健谈守口 |
| `mat-a047b82f7aac53fe92c8f1dd7b75c273` | contrast_line/傲沉易推 |
| `mat-e9e1920c0e9f54159d1839096a2dd617` | contrast_line/克制失控 |
| `mat-9b7f26c02525513a8727ac9e13dcb4be` | contrast_line/刻薄依恋 |
| `mat-a271716f908f5ce791b0771687e8e0a0` | contrast_line/外冷内热 |
| `mat-31765214333959d5bda1eac1988e2ec4` | contrast_line/大小姐笨拙 |
| `mat-26d87effdf415d75a59809ac9d11bab1` | contrast_line/女骑羞赧 |
| `mat-d463e015b9835a838cf48e78b763f540` | contrast_line/妖艳羞怯 |
| `mat-bfc886a647145f0381d97991a6e8cbd6` | contrast_line/市侩重义 |
| `mat-efd229fb43965f75bcb027fa4f3e74e3` | contrast_line/强势示弱 |
| `mat-0ff7cea6636b5047a54458597dd86384` | contrast_line/御姐撒娇 |
| `mat-7b7f82d0fd96542aaa52c53a7f6f4d77` | contrast_line/无口心热 |
| `mat-3108077b515c582ba091d191711ab03c` | contrast_line/武者破戒 |
| `mat-4944a37390c5505c9cad1f5de39d4c5e` | contrast_line/毒舌心软 |
| `mat-8c0f8e3085ad574c913e634cf7953c02` | contrast_line/泼辣胆小 |
| `mat-da999e24655e52eaa42629c69e27da99` | contrast_line/疏离黏人 |
| `mat-2f5cea6b22e65c78bfce0b7b0c3e2e7f` | contrast_line/禁欲破戒 |
| `mat-328cfd6ce71755a3b852ce92bb4a99e6` | contrast_line/端庄放浪 |
| `mat-a1453f5bd6b0571ebfefedffd02bef50` | contrast_line/粗人细活 |
| `mat-ea5cf64e053b51bfaab885674b5963a9` | contrast_line/精明糊涂 |
| `mat-84b9748863965711b96fd80054165c48` | contrast_line/老练纯情 |
| `mat-6cdb3442af3b5349a933cd062fdd5874` | contrast_line/高岭破防 |

### templates.yaml:near_beats（60）

| unit_id | label |
|---|---|
| `mat-70c471ff33a85665951686f7c68bd8ef` | near_beats/下意识揪住你的后衣角 |
| `mat-7d12ec48beaf52509a7c31fbfd094025` | near_beats/为她描一次眉 |
| `mat-819b4876eb325612b3c2b4c9101050e3` | near_beats/以指尖朱砂点向她眉心镇妖 |
| `mat-182ee2c1a0ca5a729c8f3f8890c604c7` | near_beats/伸手帮她托住沉重的大拖尾裙摆 |
| `mat-7e6fc1820c2b5fd3bfa4fa76600d8821` | near_beats/伸手捏了捏她气鼓鼓泛红的脸颊 |
| `mat-0939478f8e525cb38880f940d12bfe70` | near_beats/伸手捏了捏她的精灵耳 |
| `mat-4576597ed51e5dceb7c92bc96c873e6f` | near_beats/侧身挡住通风口的风 |
| `mat-77ce4d9e4c0c555e837a343d33f256a4` | near_beats/借口魔力供给贴近 |
| `mat-49ddc3dbb5d852a8a1579f6096742bdd` | near_beats/先开口叫名字 |
| `mat-25e41ff68fce5751ab3c41a2b8d40f91` | near_beats/分享一只耳机 |
| `mat-37b38ea5ceda512faa02860bc326573e` | near_beats/分半张烤得焦黄的干烙馍 |
| `mat-18fa1229f0e5544ea36d1329df963496` | near_beats/反手反锁包厢门 |
| `mat-5c30f298992c542ca4fd09e5409e42a4` | near_beats/在防喷罩前替她理顺耳机线 |
| `mat-271688b0b9485ed39189062d971b5d61` | near_beats/对弈时让半子 |
| `mat-ec05fc786ec65693bbd1d6953a19b371` | near_beats/将一支点燃的雪茄递到她唇边 |
| `mat-b315fe576b1056dba5a4dc68e2297a3e` | near_beats/将改好的满分试卷推到她面前 |
| `mat-e383178295db5fa5ba020bf19c5e7a7b` | near_beats/当面卸下她沾满冰霜的秘银肩甲 |
| `mat-d5d1e557b0dc5595bb02e05aeb4b7a87` | near_beats/承认紧张 |
| `mat-51c8d839d48a54169a7415d85684b6b2` | near_beats/把发烫的脸埋进你的掌心 |
| `mat-fd7bf88a3314537aa791bcaca280e38d` | near_beats/把灯调暗 |
| `mat-adfa41fa477552f082012941df7892e5` | near_beats/把热的那份推过来 |
| `mat-5e711c07b7905b97b38797845156617e` | near_beats/把防身桃木小符塞进他袖口 |
| `mat-37ba1ca0c9fd564b86effa7048c88bb3` | near_beats/按住她因为羞耻而发颤的尖长精灵耳 |
| `mat-e6c741b4d5905cb783db9dbc8408b2b5` | near_beats/掀开厚重的毛毯将她整个人裹进怀里 |
| `mat-d7d846c57ca0509eaeaf23cf044c6200` | near_beats/接住掉落的东西 |
| `mat-f8f054bb322e5181b63553343d34b1a8` | near_beats/教一个动作 |
| `mat-247334b78bf25bbf86bd0ae5f1fa1472` | near_beats/教她一个身段 |
| `mat-5cda545409c1576097a2c5029f4c1f8c` | near_beats/替他拂去罗盘上的青铜尘土 |
| `mat-22d700857f895933bf1cc803dc90553f` | near_beats/替你挡下一通电话 |
| `mat-b47b24f4f555527b9e4aa48c5caf4f26` | near_beats/替她扣紧手腕上的皮质护腕 |
| `mat-da27a1c832225d7cb7eaa79f3d466e65` | near_beats/替她扶正猫耳发箍 |
| `mat-4395da6f67325b2c928f4d1c8d8a9b7e` | near_beats/替她扶正防毒面罩 |
| `mat-ca933097aca8583c8424b028cf5bdbf9` | near_beats/替她拉上背后拉链 |
| `mat-0f613384d4895865ab087e5efc3eea52` | near_beats/替她挽一次发 |
| `mat-1368b6e1b9d05528b2972621f933bcb8` | near_beats/替她挽紧被狂风吹散的红纱面罗 |
| `mat-9a032ad8fbf35fe4a5aace1e2d8f3eb4` | near_beats/替她摘下后颈沉重的鸽子蛋钻石项链 |
| `mat-439b0a6c167d59bcbdcffbe8275c2fb8` | near_beats/替她擦去后颈渗出的细汗并拉上防窥帘 |
| `mat-f782af89dc335034a4f6ab09d7e5e4a3` | near_beats/替她系松开的盘扣 |
| `mat-7fa75ffee0c452ea9ef2f4d885db6734` | near_beats/替她解开被眼泪浸湿的礼服束腰 |
| `mat-4f206cd68306599eac9c3b67fd2da046` | near_beats/用嘴咬住发绳扎单马尾 |
| `mat-0eb2e3b8a11855a89fbd6f03e932c59c` | near_beats/用指尖替她抹匀眼角油彩 |
| `mat-5ee3b4fcc35759b9bce9b16871350137` | near_beats/用掌心温热她腕上冰凉的翡翠玉镯 |
| `mat-fc728d5659b658f8b64948443d4a232d` | near_beats/用酒精棉按住渗血 |
| `mat-b5b29e1186395dd3b143a302774ad561` | near_beats/留一盏灯 |
| `mat-231b78279ffb5cbe95a13eba73a77803` | near_beats/约在午夜 |
| `mat-ee367a80862256a890aaba854fc2964c` | near_beats/让出座位 |
| `mat-ddc370869e665f159e323925904740e7` | near_beats/试探底线 |
| `mat-43dc382b56495e788fd1df3c7cce52ee` | near_beats/请求庇护 |
| `mat-2678cac344125222b2fa84474cd4975e` | near_beats/递一盏刚沏的茶 |
| `mat-3f317f465298558f8011629db9ad2c34` | near_beats/递上一块干净白布替她拭刀 |
| `mat-2d53ac88386c52aeaeaf36e1ab283180` | near_beats/递上一杯酒 |
| `mat-dae8693aa8f7510cbd46539b75c72738` | near_beats/递外套 |
| `mat-77c577b6df3257d7b6cd2d9407650d3a` | near_beats/递纸巾 |
| `mat-1fb70237c3b15ba9835822d1d3d5cef7` | near_beats/递过半瓶干净水 |
| `mat-210b57186faa5d64920f648340e79349` | near_beats/递过宽大队服 |
| `mat-ba8bbfffdeeb5cb995ccb48031c17b95` | near_beats/递过斟满葡萄美酒的金樽 |
| `mat-a234e40b1c4f55639a935c556ed92cec` | near_beats/邀请留下 |
| `mat-6743923a74d25083aaefead528f0d64b` | near_beats/问一句不该问的 |
| `mat-dc3a8800b95d5bbfa60f9d4026aea98a` | near_beats/陪你等末班车 |
| `mat-e85cdf94d0045638ab6224b932080075` | near_beats/雨里把伞偏过去 |

### templates.yaml:pressure_response（13）

| unit_id | label |
|---|---|
| `mat-e40172b02a8b5949b64618de200e92a0` | pressure_response/以攻代守 |
| `mat-d1088cd4c56855749722dbbd9f26f519` | pressure_response/借力打力 |
| `mat-63afca5333645b6e9090b9334016718b` | pressure_response/先退后进 |
| `mat-db319feb74135fc19b602a0991768a76` | pressure_response/寻求帮助 |
| `mat-8f1d930876d65ccb93716a26ef917583` | pressure_response/收集证据 |
| `mat-bdd892564d065708a3c88fa903107279` | pressure_response/正面解决 |
| `mat-384d8784f65b5949a93f35299eced288` | pressure_response/独自承担 |
| `mat-c6ede7e11d955811b010ea7da6437f14` | pressure_response/用行动代替解释 |
| `mat-b568795948e55b27b6df04d193d69734` | pressure_response/破罐破摔 |
| `mat-2e755c170b1f5ea2bb065199914bead4` | pressure_response/维持表面稳定 |
| `mat-0c8ac160e065534988aa5165b972223a` | pressure_response/谈判交换 |
| `mat-222aac7efd5252909043bd0fd84ab88a` | pressure_response/转移风险 |
| `mat-aba823822d3e59c3b8810967d9a9acc5` | pressure_response/隐瞒拖延 |

### templates.yaml:situation_beats（84）

| unit_id | label |
|---|---|
| `mat-75de2ddaa9b35cc6bf93ba52310c3fee` | situation_beats/两面将穿帮 |
| `mat-3b7f012f23015b99b3470c6016e54d96` | situation_beats/个展前夜 |
| `mat-c3b7e609951b5a90aaae94171cb78546` | situation_beats/临终陪护 |
| `mat-8c9445a497835ef59ba745be90ddf3b6` | situation_beats/义庄纸人借宿夜 |
| `mat-c21107cc1288599e89d7f1220d82ff7c` | situation_beats/产后重来 |
| `mat-9495dab472f6570fa0f99e608fadcacd` | situation_beats/今夜话没说完 |
| `mat-920164bea155580799aab1fef6df1627` | situation_beats/以身赎城交割夜 |
| `mat-f7de5a0708f95872b92ca94622064a94` | situation_beats/债务压身 |
| `mat-c952fd1632fc5eff861cb5cb2b2603df` | situation_beats/公关底片销毁前夜 |
| `mat-dd779ef40f985b499624c1e22f26f817` | situation_beats/公馆暖阁寒疾夜 |
| `mat-6d60994961845c66af488293001b0a15` | situation_beats/共处一室 |
| `mat-c26a42569a0a54e8a25b644187105a79` | situation_beats/冷战第三天 |
| `mat-2b309d8c0fee515fb267df3a14f9bdcb` | situation_beats/创业清盘夜 |
| `mat-8040ea0d9e5c5cbab44625b6e9e246ed` | situation_beats/前任婚礼前夜 |
| `mat-fff0f26e8330552698f1e09a31521e29` | situation_beats/名声危机 |
| `mat-e89ff0a4d7725f79a07f1c8f2bd1525e` | situation_beats/回流无处安放 |
| `mat-162303dae97b5deabac05be335e44a47` | situation_beats/回程车票只剩一张 |
| `mat-0bb3d13dc492510f9c7e6877aee4786f` | situation_beats/地宫断龙石落下一半 |
| `mat-e0593637285d5dfcadf4d8344100f7f0` | situation_beats/契约自动续期前夜 |
| `mat-2179de8d84a1594fa6bc15d7739c98fc` | situation_beats/女仆装拉链卡死 |
| `mat-f7cb827d5d10531dba71bc7142a43f00` | situation_beats/婚约在身 |
| `mat-f8a1c5624f5b5188b4c9f2142bd2909c` | situation_beats/守孝之年 |
| `mat-c881dd7c84755302a709fcb72860b40e` | situation_beats/审查将至 |
| `mat-95abc99a51745a949bc2891f9013c0fa` | situation_beats/客居篱下 |
| `mat-85974ebc75225c06ba0c10913fb90243` | situation_beats/家里在逼 |
| `mat-91aee7936df95c43b4e0075dd6bf4f0f` | situation_beats/密室暗槽开闸排酒前三十秒 |
| `mat-12b4203a162457f08dd7d585eda94bc4` | situation_beats/寻亲有果 |
| `mat-17a99bf8d8445b4cae393c50f705bfd3` | situation_beats/尸潮封门第一夜 |
| `mat-7d8e4804c9d550e5b35f0c1c68bd49d8` | situation_beats/常识改写特训夜 |
| `mat-2bd43f18d0a6515590a6c96a463b5f52` | situation_beats/废嫡千金破灭夜 |
| `mat-e4e8d8cc6e505d0aaa781a61bdbc16ef` | situation_beats/异族证件更新日 |
| `mat-db685ddee5c957a3b4af903ae62f155a` | situation_beats/录音红灯亮起时的实景耳语夜 |
| `mat-909af03e144b55318a843a73ca4c60d4` | situation_beats/戏班交割夜 |
| `mat-998c21e723a65997bee1560c4fc5549c` | situation_beats/戒断第一夜 |
| `mat-f8331a47dcb355af935ed69ba5b89ed6` | situation_beats/戒酒周年夜 |
| `mat-100fdbb04ee05b5db5c2ae7be766dc38` | situation_beats/拍卖夜信托解冻前 |
| `mat-9d6d2fef8c395982986d135231de2a2c` | situation_beats/掌眼走不得 |
| `mat-7b1f2a5e201058dcb6ef4d46bc8c1bb4` | situation_beats/撤离名额二选一 |
| `mat-f45691e7bbb55233a06221bbceeb24e6` | situation_beats/新刊截稿前夜 |
| `mat-19baefb2ffe25f298e69239eb1d9c7bf` | situation_beats/旅行结束前最后一晚 |
| `mat-9cf4044f394e545d9353c66b9a3382a4` | situation_beats/旗袍店最后一单 |
| `mat-481635a99bd05dfdaa33ce73a0b7f0bf` | situation_beats/无处可归 |
| `mat-684560d562df59628814df97b398ada8` | situation_beats/无性婚姻重启 |
| `mat-1955bcb4a50e517690c7b0c344edc58b` | situation_beats/旧事上门 |
| `mat-47e712b5e73f51c2a062baf2aeea15b4` | situation_beats/旧伤复发 |
| `mat-5fe1a48ea8c75ef096a407a4bb87a15e` | situation_beats/旧情未了 |
| `mat-bd79fac717a757228cc02a13b541e07b` | situation_beats/旧疤初见 |
| `mat-258335c9a7e3539bbc02d46a092829cb` | situation_beats/时限临门 |
| `mat-97b61a48277c53a6be52b6b09471a6db` | situation_beats/晋升窗口 |
| `mat-9064ad85c6985d7e92067ea2674fef83` | situation_beats/更衣间考核锁门夜 |
| `mat-5bdc755055ec5f11a6ad62b5364f9d6c` | situation_beats/术后初愈 |
| `mat-2c21ff71a5b8563fa4c901cc3ff380ee` | situation_beats/权力易手 |
| `mat-685e453db7b85ad48c5abb7198b47b10` | situation_beats/母树枯竭授种夜 |
| `mat-0957b4333b0252e5ac01bbd13ae38084` | situation_beats/比赛前夜 |
| `mat-051018308bd65f0099bfbb5ee26d6336` | situation_beats/民宿停电后的第二天 |
| `mat-ec10c9e60d6659f9b86484d729e4af16` | situation_beats/洗刀水色变红的瞬间 |
| `mat-bd7b92d545225ddbbb99b4da492de53c` | situation_beats/流言缠身 |
| `mat-97dd36b1d8065eb9897681fd498c5649` | situation_beats/热搜澄清前夜 |
| `mat-c2b2e8f7e47a565e8d5e512f01d5fd80` | situation_beats/照护失智母亲 |
| `mat-4597ffd795e2561380393eaf4274490a` | situation_beats/疗后敏感 |
| `mat-7e2860bfb3d65ef4bde6bee96586dd5a` | situation_beats/目击待证 |
| `mat-09a1b758abc75a1bb206d8a6b26816b5` | situation_beats/直播意外事故 |
| `mat-a33bc389b75452918943ba2bc85a5129` | situation_beats/真名追索令下达 |
| `mat-662353bc64bf550d89cda501c13688cc` | situation_beats/瞒报咬伤 |
| `mat-9c8e8431314f5949bb8328b45db32042` | situation_beats/离城前夜 |
| `mat-13a4e1b1714056b6acbf169c22f21f97` | situation_beats/离婚冷静期 |
| `mat-05433a3268075105a0ac8e0d8b70569c` | situation_beats/私藏抗生素 |
| `mat-70eab69443e35c89ba9ffde540f17a59` | situation_beats/秘密将破 |
| `mat-70b934888e1a5c259e0c70039d8f0785` | situation_beats/空中飞人搭扣松动前一刻 |
| `mat-f04572b2534451ffa8dae91ffb57833a` | situation_beats/老茶馆转让夜 |
| `mat-214c1c6f5a0e585894bee0ba88f94bd8` | situation_beats/试衣间帘后半分钟 |
| `mat-b02afbe772ec5450820c76fac98ee047` | situation_beats/谁也不欠谁 |
| `mat-78db36ad7217521d920790ffe032412a` | situation_beats/资源断供 |
| `mat-895b72d4627a521e8ad4dfccf4daa557` | situation_beats/身体见底 |
| `mat-b9c31abcf9f55a94a595c8055ebd31fc` | situation_beats/还俗前夜 |
| `mat-65fc53629d9c53d5b4f9da767279d399` | situation_beats/迷宫停滞第一夜 |
| `mat-adbd342979165a4f8a062cb886306c2a` | situation_beats/退役重逢第一夜 |
| `mat-0f28cfd348de519b97e05b8a1a6427a7` | situation_beats/遗嘱将宣读 |
| `mat-2fe531ee746253a39d4da58b10091558` | situation_beats/避难所清退名单 |
| `mat-91b81fff746d5681bfbbd5437ea0cf1d` | situation_beats/雪山木屋断电长夜 |
| `mat-9ab3d858b5e05bf5ba884a7a0089f3f8` | situation_beats/非人之躯将露 |
| `mat-a3b2da3724d951ec8c51de53e8005f39` | situation_beats/颁奖礼候场二十分钟 |
| `mat-59903a844daf509cbb2165d0119806c1` | situation_beats/风纪会长掉马夜 |
| `mat-8fa4fa8c516b56df86611f17f634594d` | situation_beats/魔力暴走临界 |

### templates.yaml:suggestion_player_first（60）

| unit_id | label |
|---|---|
| `mat-4d2b5cbb5dd15a34b8ba6e3dfb56a1c8` | suggestion_player_first/下意识揪住你的后衣角 |
| `mat-318204cbdad359cbb9b08f74c74f6ed8` | suggestion_player_first/为她描一次眉 |
| `mat-e7bcee1054b4590db4968c5401144e30` | suggestion_player_first/以指尖朱砂点向她眉心镇妖 |
| `mat-788200570822577787bc9af8ff8a0faa` | suggestion_player_first/伸手帮她托住沉重的大拖尾裙摆 |
| `mat-eb79684f0e4459b38569bfc338127d94` | suggestion_player_first/伸手捏了捏她气鼓鼓泛红的脸颊 |
| `mat-b5945e93c9f5551e9c913c91b25d9b3a` | suggestion_player_first/伸手捏了捏她的精灵耳 |
| `mat-9f3f52baee46588db32ad47365c1719d` | suggestion_player_first/侧身挡住通风口的风 |
| `mat-e7cfd21aaae15ff48b5f0804604b4f3e` | suggestion_player_first/借口魔力供给贴近 |
| `mat-639c0e98ce2555e6942a6e4f6c6f39fe` | suggestion_player_first/先开口叫名字 |
| `mat-fb50bdf5f7665077b6a9d6dd562883f3` | suggestion_player_first/分享一只耳机 |
| `mat-3f104374867855698258f34ee9d4d0e0` | suggestion_player_first/分半张烤得焦黄的干烙馍 |
| `mat-74135846ec3b5dc59622710f53e502a4` | suggestion_player_first/反手反锁包厢门 |
| `mat-f85bbec029d3517088e3afb729c9d44c` | suggestion_player_first/在防喷罩前替她理顺耳机线 |
| `mat-319235f93a0452038358c259fcc47d2b` | suggestion_player_first/对弈时让半子 |
| `mat-e1324a3d646452ecbe926770fc684204` | suggestion_player_first/将一支点燃的雪茄递到她唇边 |
| `mat-32fba66ab09c5f4994ebfa110dc7285e` | suggestion_player_first/将改好的满分试卷推到她面前 |
| `mat-8af37f9ae480506caf0fa747b60c7aad` | suggestion_player_first/当面卸下她沾满冰霜的秘银肩甲 |
| `mat-c57885f1b1b052a888c907aba44ca7e1` | suggestion_player_first/承认紧张 |
| `mat-51c1025b0fce5f7f95e7527287b4d4a3` | suggestion_player_first/把发烫的脸埋进你的掌心 |
| `mat-b4b45ff08509523ab8ce9d43febcc4c0` | suggestion_player_first/把灯调暗 |
| `mat-2def82c019545981951d90f29583de29` | suggestion_player_first/把热的那份推过来 |
| `mat-42a5343d875754418bb8de93f3998044` | suggestion_player_first/把防身桃木小符塞进他袖口 |
| `mat-e94269b45e375174b73d312a294d2c13` | suggestion_player_first/按住她因为羞耻而发颤的尖长精灵耳 |
| `mat-7c4a2ef44e545a55b0bfb61031325e60` | suggestion_player_first/掀开厚重的毛毯将她整个人裹进怀里 |
| `mat-7ed9a25e6cbf53c297949ff2b0591735` | suggestion_player_first/接住掉落的东西 |
| `mat-566c4a490f82559cb7ba0a72554586f5` | suggestion_player_first/教一个动作 |
| `mat-68194783419656df98e967795d2ccab2` | suggestion_player_first/教她一个身段 |
| `mat-ee671c0a38505827a31370df213f27e4` | suggestion_player_first/替他拂去罗盘上的青铜尘土 |
| `mat-8af9b7d9f81e55c6b2c1ab34bd37e88a` | suggestion_player_first/替你挡下一通电话 |
| `mat-5f77b60ba0fb5731b757818ab0b22ae9` | suggestion_player_first/替她扣紧手腕上的皮质护腕 |
| `mat-2103172210e05485a4667a1355d95fc4` | suggestion_player_first/替她扶正猫耳发箍 |
| `mat-2b7610ac7b2459b29cca23f536af544b` | suggestion_player_first/替她扶正防毒面罩 |
| `mat-609daca7ee915cf79d7ee427d423b2bc` | suggestion_player_first/替她拉上背后拉链 |
| `mat-b9a273d5e42e555f9832b233096652c8` | suggestion_player_first/替她挽一次发 |
| `mat-4d7ea91fb1d45b3080125436d277225c` | suggestion_player_first/替她挽紧被狂风吹散的红纱面罗 |
| `mat-4665cb5f6a6256ebb5078e83ff4d4740` | suggestion_player_first/替她摘下后颈沉重的鸽子蛋钻石项链 |
| `mat-498b408fb98a56049277a9a31a74d1e7` | suggestion_player_first/替她擦去后颈渗出的细汗并拉上防窥帘 |
| `mat-8ebcb8c6c2df513b91ac2594502222a0` | suggestion_player_first/替她系松开的盘扣 |
| `mat-6a059d54dc59548ea6778c08469a8f06` | suggestion_player_first/替她解开被眼泪浸湿的礼服束腰 |
| `mat-9c761beef8d65c6b82695729c995dc4f` | suggestion_player_first/用嘴咬住发绳扎单马尾 |
| `mat-0699993f67a5585cbbce5db5b8975e14` | suggestion_player_first/用指尖替她抹匀眼角油彩 |
| `mat-914ddd0637785ea6806655687f148cc5` | suggestion_player_first/用掌心温热她腕上冰凉的翡翠玉镯 |
| `mat-629fe81f4c845dc79a564e0ab92e78f8` | suggestion_player_first/用酒精棉按住渗血 |
| `mat-be52ecdafad6520caafa4f8bc014e14c` | suggestion_player_first/留一盏灯 |
| `mat-a8abe29b931f5a839d53a55c7e0753b1` | suggestion_player_first/约在午夜 |
| `mat-d01746b3fbce5c788e28cda7fb3474c3` | suggestion_player_first/让出座位 |
| `mat-ff11606ad55859d0bc1aae441261f0f3` | suggestion_player_first/试探底线 |
| `mat-4f6137b471685771ae7e0248d698ebff` | suggestion_player_first/请求庇护 |
| `mat-04871dfc36af51be8e1c082e4c3ee0a2` | suggestion_player_first/递一盏刚沏的茶 |
| `mat-3394615a9dc452c9b76e60759177c315` | suggestion_player_first/递上一块干净白布替她拭刀 |
| `mat-c3b35ad1d20d5e17a2741df4412f560c` | suggestion_player_first/递上一杯酒 |
| `mat-526042214b4351c8a9d7517c0fc892c9` | suggestion_player_first/递外套 |
| `mat-37e4f150809a582d9cabdf779ed2284f` | suggestion_player_first/递纸巾 |
| `mat-16e1df683d8a5a97a8732a850f91bbca` | suggestion_player_first/递过半瓶干净水 |
| `mat-75e322f3b8d5555ea8762264a77b1112` | suggestion_player_first/递过宽大队服 |
| `mat-ef6f3f3b6c9b578191f704fbb412aaf9` | suggestion_player_first/递过斟满葡萄美酒的金樽 |
| `mat-1746b84246085978a504ff2cef25bcb9` | suggestion_player_first/邀请留下 |
| `mat-4f7635fe65dc50d99802070cb30bc19c` | suggestion_player_first/问一句不该问的 |
| `mat-848d0e927d295387ba20759693f58dce` | suggestion_player_first/陪你等末班车 |
| `mat-daf7dbced999525a8c25ffdd9ec1e99b` | suggestion_player_first/雨里把伞偏过去 |

### templates.yaml:trade_beats（22）

| unit_id | label |
|---|---|
| `mat-2df459810b1658ca9b3e5eead4bf5f39` | trade_beats/交出一样东西 |
| `mat-39de74f4ece95672b678885b4bc5f2bf` | trade_beats/亮出后台未退登账号 |
| `mat-42e70375a77458afaf4fdeca7fa486b9` | trade_beats/亮出惩罚契约卡 |
| `mat-66de558132135afeb623a09b6b064f84` | trade_beats/亮出锁骨上的契约印记 |
| `mat-7a55a921a8895c1b96329926bc81965f` | trade_beats/出示证据 |
| `mat-1104c46264d256e3bb73795f5d1406fc` | trade_beats/开出一句价码 |
| `mat-f949addad6165c8bb24e9c1e6cf86909` | trade_beats/当面卸下弹匣 |
| `mat-cd05d3086e9b5b8baa03de1fccd80c26` | trade_beats/当面摊牌 |
| `mat-421aa2d46d395427a119c8a41a421480` | trade_beats/当面撕掉一张合租禁令 |
| `mat-b52873b51cb55169945636a35f2631be` | trade_beats/当面质问 |
| `mat-793b71acda4553258380c5219576f6a0` | trade_beats/拍出一本未打码原稿 |
| `mat-34e59adb0c4553d89e2f3abaf87a1de1` | trade_beats/拍出写有黑历史的旧日记 |
| `mat-4fb4a285772e5f2f883eb4b0622fdeaa` | trade_beats/推过半板抗生素 |
| `mat-2d46d2537e3e58bf99d6d30c54ea08e6` | trade_beats/提出一场对赌 |
| `mat-f3052b538f305212a30367a0a5b62539` | trade_beats/提出交易 |
| `mat-eda1401f40b95524a387591716d408b4` | trade_beats/摆出两个选项 |
| `mat-b412e2f0e77759229fe9927e196244be` | trade_beats/撕开衣领露出伤口 |
| `mat-051397efdf505b9f805fe0d53ffe3333` | trade_beats/给出最后期限 |
| `mat-dcbd75c9362d5eb695efded8ee5b412c` | trade_beats/要求一个答复 |
| `mat-e141d705b1115a9cb26e3fd8dd2fabd3` | trade_beats/递出一份文件 |
| `mat-3fafb3c03e3758209ea8199687ca40e0` | trade_beats/递出一张乘车通行证 |
| `mat-2a6fc30125d154fb93ed0309ea95af2a` | trade_beats/递出一支笔 |

### templates.yaml:withdrawal（13）

| unit_id | label |
|---|---|
| `mat-d3870455063a587495f4e4f1346da2f8` | withdrawal/以攻代守 |
| `mat-4d8b9bceacae57d2990ca5281c884a54` | withdrawal/借力打力 |
| `mat-24516a3e2e805055b6f439dd16a3bec7` | withdrawal/先退后进 |
| `mat-d7332e7a47b8584ca3fcf325963ce118` | withdrawal/寻求帮助 |
| `mat-bd0cb20b0a835d47a9798f94ba437384` | withdrawal/收集证据 |
| `mat-7c4a4e520c32503d898e551ae2c83f1c` | withdrawal/正面解决 |
| `mat-b984870ff84d5739bfcdb38102ff310b` | withdrawal/独自承担 |
| `mat-78fbba19a8fb5dcc934f21738b77e8cb` | withdrawal/用行动代替解释 |
| `mat-d501ae8ba845548d84b524e65f6b594d` | withdrawal/破罐破摔 |
| `mat-7af9091e77275764b0af0fde74ce6370` | withdrawal/维持表面稳定 |
| `mat-2cf402bde24c50df9d2a91700e6c1f2c` | withdrawal/谈判交换 |
| `mat-14cc53716e185a1c901f371401909d99` | withdrawal/转移风险 |
| `mat-5615f6a1c5ea57d5b32c1a0b1e1e4c8b` | withdrawal/隐瞒拖延 |

### templates.yaml:顶层兜底/建议句（6）

| unit_id | label |
|---|---|
| `mat-81f58eebbfec5931884d22d688e1ae20` | action_fallback_near |
| `mat-7efabc54bae35ef29e5d4192e96d3fc8` | action_fallback_trade |
| `mat-c9d0d3b4835c5028a5109fcd69e880e1` | orientations |
| `mat-bf763b0b921956668c0bc06d3ddb6dbc` | suggestion_default |
| `mat-c7cf8a0730685698b0e8c4a892bbf0b8` | suggestion_extras |
| `mat-c609b0423a47522aa8258a9049540052` | suggestion_nontrade_guard |

### twist_profiles.yaml:人事类（4）

| unit_id | label |
|---|---|
| `mat-af7cda8dcb3e591a9791f322e80ec1c0` | 人事类/affects |
| `mat-77f5e1e9bc9d5864b9e229317141a00f` | 人事类/escalation |
| `mat-4b545bc540f3560f87dd3005e450edd7` | 人事类/introduces_third_party |
| `mat-bfe3ba4c06f75c8cbcaae9bb47d89949` | 人事类/opens_exit |

### twist_profiles.yaml:信息类（4）

| unit_id | label |
|---|---|
| `mat-7f4a90ad6654506cadc172fc17a961f7` | 信息类/affects |
| `mat-07352269ca66533b82dba66394c1841b` | 信息类/escalation |
| `mat-963c24b549a8551c846c947eec7fbb7f` | 信息类/introduces_third_party |
| `mat-de4915a87a895b1fb5420d155bb29f50` | 信息类/opens_exit |

### twist_profiles.yaml:关系类（4）

| unit_id | label |
|---|---|
| `mat-aa714ef920e05ddaa9bac7b864886582` | 关系类/affects |
| `mat-a4f67204acc75a4bacc79313edcba485` | 关系类/escalation |
| `mat-5c6a79d7dc7257f7891a08b73389ce8e` | 关系类/introduces_third_party |
| `mat-b202add3ae3e5c28b5e66a5bae5976de` | 关系类/opens_exit |

### twist_profiles.yaml:制度类（4）

| unit_id | label |
|---|---|
| `mat-a6396eb438665a7ba106a69224d3ea87` | 制度类/affects |
| `mat-afdd8120b6cd5f2c9fc65df781111274` | 制度类/escalation |
| `mat-bef09b1a413f514d93b066a0107e6ae9` | 制度类/introduces_third_party |
| `mat-1ebe1335dd2a5f6e867f4a4e5c332434` | 制度类/opens_exit |

### twist_profiles.yaml:意外类（4）

| unit_id | label |
|---|---|
| `mat-fcb81c6632315a1daf2dbf432072dc6d` | 意外类/affects |
| `mat-2e0316d484255a2f80a31fabf4f338ec` | 意外类/escalation |
| `mat-832794919cc75867b80350809d406230` | 意外类/introduces_third_party |
| `mat-d952cb2af15a5c479128f7f97829ad41` | 意外类/opens_exit |

### twist_profiles.yaml:时限类（4）

| unit_id | label |
|---|---|
| `mat-01e4a759e71b55c7a740b7e47a3cd989` | 时限类/affects |
| `mat-6f22227885815136b5a76e069b30b5d2` | 时限类/escalation |
| `mat-c5ab6c08fcf650efacf8295355bfa134` | 时限类/introduces_third_party |
| `mat-8a24b228b27b537aa665f311b676dad9` | 时限类/opens_exit |

### twist_profiles.yaml:资源类（4）

| unit_id | label |
|---|---|
| `mat-5a764185f7885c4595f2ded242aa9660` | 资源类/affects |
| `mat-267611c0beba581a964ce48f6b5ef299` | 资源类/escalation |
| `mat-3db301ef754454a9ace58906e23a5f0d` | 资源类/introduces_third_party |
| `mat-3f3b70e421ac56c3b59f45cc1e45c287` | 资源类/opens_exit |

### twists.yaml（7）

| unit_id | label |
|---|---|
| `mat-407b80cf143454d684b2195c8f31d29a` | 人事类 |
| `mat-dc0f40bbf7f856ca8b0ab551e38375fb` | 信息类 |
| `mat-f6e0790f6a5f5aa18f58a0324858267c` | 关系类 |
| `mat-267deba0b1965107a407833a51d96d72` | 制度类 |
| `mat-5cf0d991218c51a8b9d0719e573ffea8` | 意外类 |
| `mat-cd0a54db58fa5334bcb2a497fd7d4626` | 时限类 |
| `mat-94eccaa5dd7053e3ac3c650e3ba9d954` | 资源类 |

### world_frameworks.yaml:顶层契约（2）

| unit_id | label |
|---|---|
| `mat-45320bc0f8ce500f853ca9760dadc863` | legacy_weight |
| `mat-e095a3ccb34452789794b79d3540afc9` | reviewed_frameworks |

## P3 不可达清单

共 2 个单元：既不被任何框架选择字段引用，也不在 legacy 抽取路径上。

| unit_id | label | source 定位 | 不可达原因 |
|---|---|---|---|
| `mat-eb1b701281f2547da611bcc52342516c` | given | `names.yaml#:group:given` | 顶层回退名池 `given`：fill_opening.name_pool_for_era 的回退顺序是 given_male/given_female → given，顶层 given_male/given_female 都存在，故 `given` 永不被读取（3 个名池不完整时代的回退也只落到 given_male/given_female）。 |
| `mat-6dfcf198381e5e48aedbd013359f2f60` | version | `world_frameworks.yaml#:contract:version` | 顶层契约键 `version`：roll_opening.load_pools 只读 frameworks/legacy_weight/reviewed_frameworks 三个键；`version` 仅被维护工具 check_frameworks.py 校验，不在框架链或 legacy 抽取链上。 |

## 方法说明

1. **单元枚举**：`scripts/material_registry.py` 的 `units()` 枚举 live 单元，与 `references/material_registry.yaml`(v2) 按 id 连接后取 `status == NOT_REVIEWED`（1,573 个，与计划文件一致；注册表 2,389 行中另有 15 行 DEPRECATED 已下线）。
2. **P1 框架链（label 精确相等）**：以 `authoring/framework_index.yaml` 的 40 个 `authoring/frameworks/mat-*.yaml` 为准，对每个框架 material 收集选择字段引用，采用与 `check_material_compatibility.py` owners 相同的轴映射：
   - `material.eras[]` → 时代；`material.aesthetics[]` → 美学基调；`material.places` 的键 → 地点；`material.rule`/`material.social_rule` 整串 → 核心规则/社会规则；
   - `material.pairs[].family` → 身份侧；`pairs[].position` → 玩家化身轴/社会位置；`pairs[].appellations[]` → 玩家化身轴/称谓；
   - `material.activities` 键 → 场景动作；`material.pressures` 键 → 处境侧；`pressures[].source` → 压力来源；`pressures[].engines[]` → 张力引擎；
   - 另计 `activities[].category` → action_categories/action_metadata 的类别键（框架模式下 `world_frameworks.build` 以该类别重建 场景动作分类 并读 场景动作元数据）。
   - 跨文件 label 联动：identities.yaml `npc/<family>`、`player/<position>`，identity_profiles.yaml `<family>/*`（7 子键），locations.yaml `<place>`，location_profiles.yaml `<place>/*`（6 子键），names.yaml `eras/<era>`，character_meta.yaml `社会位置关系/<position>` 与上述引用按同一 label 匹配（框架模式 `prepare_tables` 以框架内联素材覆盖 identities/locations/location_profiles 的同名键，故这类引用是「名称级」而非「内容级」消费，见冲突 3）。
   - 框架字段结构示例（`authoring/frameworks/mat-00c8740516f7519592b47bb547fe5c27.yaml`「远途休假与小镇停留」）：`material: {eras: [远途休假季], aesthetics: [暖色生活流, 写实文学, 恋爱轻喜], rule: <整句>, social_rule: <整句>, places: {深夜机场候机区: {details: [...], profile: {...}}}, pairs: [{family: 艺术与传播, position: 同侪, appellations: [直呼其名], ...}], activities: {交换沿途手账: {category: 信息交换, ...}}, pressures: {返程班次取消: {source: 预定返程班次被取消, engines: [时限逼近, 资源锁定], ...}}}`。
3. **P2 legacy 链**：`build_opening.py --framework legacy`（非 complete 默认即 legacy；显式 `--framework legacy` 同路径）→ `roll_opening.load_pools()` 读取 pools.yaml（顶层抽取池 + 时代与地点/场景动作/玩家化身轴 + meta 契约）、character_meta、twists、character_pools、action_categories、action_metadata、twist_profiles、world_frameworks（legacy_weight/reviewed_frameworks）→ `build_roll` legacy 分支抽取（含 `场景动作·对照` 读交易摊牌桶、`--twist` 读转折池/转折画像）→ `fill_opening.fill_opening` 依 roll 值查 names/identities/locations/location_profiles/identity_profiles/action_metadata/templates/character_meta。单元落在这些读取域内（按 label ∈ 对应池/桶判定，如 situation_beats 键须 ∈ 处境侧）即 P2。
4. **P3**：其余单元，逐一给出不可达原因（所在池组 + roll_opening 是否读取该组）。

## 结构性事实（读取链完整性）

- 框架 places 引用但不在 地点 池：21 个 → ['互助居所共享厨房', '公共修理台', '冒险者旧会馆', '城墙花园', '复兴集市', '夜校作品交流廊', '夜校拆装教室', '夜间培训室', '居民报修茶桌', '山门集市', '康复居所阅读廊', '开放实验室样品台']…
- 框架 pairs.family ∉ 身份侧 池：无
- 框架 pairs.position ∉ 社会位置 池：无
- 框架 pairs.appellations ∉ 称谓 池：无
- 框架 activities 键 ∉ 场景动作 两桶：162 个 → ['为彼此挑一段短读物', '为旧物写一张来历卡', '交换一周的生活小窍门', '交换一处街角设施的记忆', '交换失败作品的故事', '交换沿途手账', '交换沿途明信片', '交换营地菜谱', '交换街区故事', '交接夜班服务问答', '交流香材别称', '体验灵气小夜灯课程']…
- 框架 pressures 键 ∉ 处境侧 池：80 个 → ['两处报修争用同一组工时', '乡俗记录出现异议', '会馆用途表决', '传说署名有争议', '住宿账单项目不明', '修缮委托签名不明', '借展归期改变', '公共修补台损坏', '公共工具缺件', '公共庭院预约撞期', '公共房间预约重复', '公共材料分配争议']…
- 框架 pressures.source ∉ 压力来源 池：80 个 → ['一位作者不同意原定的网络直播', '一位老熟客寄存的唱片在店铺转让前无人认领', '一批公用设备故障被归责于同一家调试站', '一支维修队收到两条同等级工单', '一段交接记录缺失导致多封信无法确认去向', '一段旧街封修占用了灯会通道', '两个课程预约了同一台仪器', '两份山川志记录了不同的渡口', '两份正式记录对同一时间写法不同', '两位讲述者都认为刊物混淆了自己的版本', '两处驿站使用相同简称', '两种语言对服务期限的理解不同']…
- 框架 pressures.engines ∉ 张力引擎 池：无
- 框架 eras ∉ 时代 池：无
- 框架 aesthetics ∉ 美学基调 池：无
- 框架 rule ∉ 核心规则 池：40 个 → ['不同族群共同生活，契约为公共服务约定边界，不能代替人的意愿。', '京都町屋与壬生道场以修缮、借场和手递书信维持往来。江户神乐坂是异地艺事联络点，需另写旅行或通信经过，个人手艺不等于政治归属。', '人、精怪与方士共同生活在坊市中，宵夜、营生和登记各循不同节奏。', '修行之外，藏书、路图和镖运维持各地往来，凡人的手艺同样进入行会记录。', '修行资源进入民间百业，法器维修、灵兽寄养和传音服务都有明确行规。', '公共终端协调城市服务，居民保留线下申诉和匿名参与社区活动的渠道。', '创作者、配音者与店铺围绕公开活动协作，作品归属和休息时间同样重要。', '喫茶店、团地与末班车织成生活路线，老熟客的习惯常比招牌更持久。', '城内百业由行会与书院共同维系，手艺、学问和人情各有来路。', '城市居民在预约空间里安排运动、看景与小型聚会，休闲不必服务于紧迫目标。', '城市手艺与公共服务通过记录、展览和相互学习留下日常经验。', '城市把地下设施的维修记录向居民开放；现场作业由合格人员承担，公众可以核实影响范围并提出优先顺序。']…
- 框架 social_rule ∉ 社会规则 池：40 个 → ['乘船与观测遵从实际开放安排，同行人各自决定是否继续行程。', '事实、推测与评论分开标记，发布须遵守当事人授权范围。', '代收信件必须登记，紧缺公共物资不能只凭私人承诺分配。', '借阅与护送按委托说明办理，师门身份不替代具体许可。', '公共仪器按预约共享，原始记录与个人评价分开保管。', '公共安排需说明理由并接受复核，临时值班不授予支配他人的权力。', '公共服务中断必须说明范围和恢复安排；参观者不进入作业隔离区。', '公共活动以张贴的名单和当面约定为准。', '公共空间按不同体力需求布置，照护者也有可以交班休息的时段。', '公共空间按预约使用，邻里帮助不等于无限义务。', '共同物资要登记来源，交换可以拒绝，不以未知风险强迫同行。', '共同费用与行程先说明，任何人都能选择独自活动。']…
- 框架 activities.category ∉ action_categories：无
- 地点池缺 locations.yaml 条目（legacy 抽中即 FillError）：无
- 地点池缺 location_profiles.yaml 条目：无
- locations.yaml 有、地点池没有的地点：无
- location_profiles.yaml 有、地点池没有的地点：无
- 身份侧 池缺 identities.yaml npc 条目：无
- 社会位置 池缺 identities.yaml player 条目：无
- identities npc 有、身份侧 池没有的族：无
- identity_profiles 有、身份侧 池没有的族：无
- trade_beats 键 ∉ 交易摊牌 桶：无
- near_beats 键 ∉ 非交易靠近 桶：无
- action_categories 条目 ∉ 非交易靠近 桶：无
- situation_beats 键 ∉ 处境侧 池：无
- 处境侧 池缺 situation_beats 键：无
- 年龄段 池 ⊕ 年龄段区间 键：无
- 社会位置 池 ⊕ 社会位置关系 键：无
- 反差轴 池 ⊕ contrast_line 键：无
- 压力策略 池 ⊕ pressure_response 键：无
- authoring 框架名 ⊕ scripts/data/world_frameworks.yaml 框架名：无
- 可抽时代中 names.eras 专属名池不完整的：['传媒舆论危机期', '契约共存时代', '远途休假季']
- 交易摊牌桶 22 项；action_categories 共 91 项。
- 框架复用不对称：eras/aesthetics/family/position/appellation/engines 引用全部落在对应池内（名称级复用），而 40 条 rule、40 条 social_rule 全部为框架自有整句（不在 核心规则/社会规则 池），162 个 activities 键均不在 场景动作 两桶，80 个 pressures 键与 80 条 pressures.source 均不在 处境侧/压力来源 池——剧情句层完全自建。
- 框架引用不同地点 144 个：123 个与 locations.yaml/location_profiles.yaml 共享名称，21 个为框架内联专属地点（locations.yaml 无条目，`prepare_tables` 注入框架自带 details/profile）。地点池 128 个地点与 locations.yaml/location_profiles.yaml 键完全一致。

## 与 noncore_audit_plan.md 的对照（冲突点）

1. **P1 口径**：计划把 P1 描述为「world_frameworks.yaml depends_on 文件中被 40 框架实际引用的单元」，并把 names/character_pools/templates/twist_profiles 列入 depends_on；但框架 yaml 的选择字段（eras/aesthetics/places/rule/social_rule/pairs/activities/pressures）从不按 label 引用 character_pools、templates、twist_profiles 的条目（框架自带内联文案，`prepare_tables` 只覆盖同名键）——这些文件里没有 P1 单元，P1 实际集中在 identities/identity_profiles/locations/location_profiles/names.eras/action_categories/action_metadata/character_meta.社会位置关系。`check_material_compatibility.py` 的 REFERENCED 统计也只索引 pools.yaml，与本文件口径互补不冲突。
2. **P2 口径**：计划把 P2 概括为「identities 成员、locations 细节、aesthetics、names、templates、twists」，未提 action_categories/action_metadata/character_pools/character_meta/twist_profiles/pools.meta——后者同样被 legacy 路径全程读取，本文件按读取事实归入 P2。另 twists/twist_profiles 只被 `roll_opening --twist`（维护侧扭转路径）读取，不在 `build_opening --framework legacy` 的开局链上，按「roll_opening 读取的池组」口径仍归 P2。
3. **框架链是名称级引用**：框架 places/pairs 自带 details/profile/npc 内联素材，运行时 `prepare_tables` 直接覆盖 identities/locations/location_profiles 同名条目；因此「框架引用了地点 X」不代表框架模式会消费 locations.yaml[X] 的内容，locations/location_profiles 的既有条目实际只被 legacy 路径按 地点池 抽中消费。P1 名单按计划要求的 label 引用排序仍有意义（读频近似），但语义审查时须按「名称引用≠语义认证」理解（计划自己也注明了这一点）。
4. **P3 非空但极小**：计划把 P3 定义为「无消费者的候选 DEPRECATED」并预期一波工作量；本划分按读取事实只找到 2 个真实不可达单元（names.yaml 顶层 `given` 回退名池、world_frameworks.yaml `version` 契约键，见 P3 清单），波次 C 的 DEPRECATED 候选实际极少，审查重心应放在 P1/P2 的语义核定上。

## 不确定边界情形

- **world_frameworks.yaml `version`**：运行时无读者（load_pools 只读 frameworks/legacy_weight/reviewed_frameworks），但维护工具 check_frameworks.py 会校验它=1。按任务口径（框架链+legacy 链）判 P3；若把治理工具视为消费者，可改判 P2。
- **names.yaml 顶层 `surnames/given_male/given_female`**：判 P2 依赖「传媒舆论危机期/契约共存时代/远途休假季」3 个可抽时代缺少完整专属名池这一现状；一旦补齐这 3 个名池，三个顶层池即回到不可达（`given` 则任何情况下都需要 given_male/given_female 同时缺失才可达）。DEPRECATED 前建议保留或加 cleanup 标注。
- **identities.yaml npc 成员的「成员级」可达**：本划分以「族条目」为单元（族 ∈ 身份侧 即可达）；族内单个成员 dict 按 `seed % len(npc_pool)` 全员可达，无成员级死条目判定。
- **meta.gate_aesthetics 门控**：美学基调命中 gate 时 表层风味/口癖 抽「—」；但两个池仍被 load/展平，character_pools 单元按「被读取」判 P2，不按「必被抽中」。
- **`场景动作·对照`**：legacy 压力开局会从 交易摊牌 桶抽一个对照动作（世界框架模式 pop 掉该键），交易桶条目因此仍算 legacy 可达；纯框架模式下交易桶仅剩 build() 里 `scoped['场景动作·交易']=[]` 的空覆盖。
