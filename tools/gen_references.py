"""Generate the code-derived reference files in <skill>/references/.

    python tools/gen_references.py            # write the files
    python tools/gen_references.py --check    # exit 1 if any file is stale

Generated files are committed; tools/validate_skill.py checks that they match
the code (SKILL_PACKAGING.md section 3). Rules live in the code and the
validators; these files only describe fields.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _runtime  # noqa: E402

GENERATED_NOTE = "<!-- 本文件由 tools/gen_references.py 生成，不要手改。 -->\n\n"


def _escape(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def _default(value):
    return json.dumps(value, ensure_ascii=False)


def field_table(obj_spec, nested=None):
    """Markdown table for an Obj spec; nested object specs are collected."""
    from adult_tension import schema as S

    nested = nested if nested is not None else []
    lines = ["| 字段 | 类型 | 必填 | 说明 |\n", "|---|---|---|---|\n"]
    for name, field in obj_spec.fields.items():
        spec = field.spec
        inner = spec.inner if isinstance(spec, S.Nullable) else spec
        if isinstance(inner, S.Obj) and inner.fields:
            nested.append((name, inner))
        if isinstance(inner, S.List) and isinstance(inner.item, S.Obj) and inner.item.fields and not isinstance(inner.item, S.Tagged):
            nested.append((name + "[]", inner.item))
        if field.required:
            need = "是"
        elif field.default is not S.MISSING:
            need = "否，默认 `%s`" % _escape(_default(field.default))
        else:
            need = "否"
        lines.append("| `%s` | %s | %s | %s |\n" % (name, _escape(spec.doc()), need, _escape(field.desc or "")))
    return "".join(lines), nested


def render_spec(obj_spec, heading_level=3):
    text, nested = field_table(obj_spec)
    out = [text]
    seen = set()
    while nested:
        name, spec = nested.pop(0)
        if name in seen:
            continue
        seen.add(name)
        sub, more = field_table(spec)
        out.append("\n%s `%s` 的字段\n\n%s" % ("#" * (heading_level + 1), name, sub))
        nested.extend(more)
    return "".join(out)


def render_commands():
    from adult_tension import errors
    from adult_tension.application import commands, specs

    lines = [GENERATED_NOTE, "# 命令参考\n\n"]
    lines.append("调用：`<python> scripts/adult_tension.py <command> --json [--input-file PATH] [--data-dir PATH]`\n\n")
    lines.append("- 输入是一个 JSON 对象，来自 `--input-file`（UTF-8，可带 BOM）。需要输入的命令在没有 `--input-file` 且 stdin 不是终端时读取 stdin；可选输入只从 `--input-file` 读取（`--input-file -` 表示 stdin）。\n")
    lines.append("- 输出是一个信封 `{\"ok\", \"data\", \"error\"}`，以 UTF-8 字节写到 stdout。成功与失败都附带 `next_request_id`（成功在 `data` 里，失败在 `error` 里），下一次写操作直接用它。\n")
    lines.append("- 全局参数：`--json`（输出 JSON，始终如此）、`--pretty`（缩进输出）、`--debug`、`--input-file PATH`、`--data-dir PATH`。\n")
    lines.append("- 写操作都带 `request_id`；会话内的写操作还带 `session_id` 与 `expected_revision`。同一 `request_id` + 同一输入重放时返回原响应并标记 `replayed: true`。\n")
    lines.append("- 开发开关（环境变量，由测试环境设置，玩家不需要）：`ADULT_TENSION_HOME` 指定数据目录；`ADULT_TENSION_INCLUDE_DRAFTS=1` 让未发布的世界参与开局与世界列表；`ADULT_TENSION_TRACE=<文件>` 把每次调用（参数、输入、信封、耗时）追加到该文件，供端到端评测采集。\n\n")
    lines.append("## 命令一览\n\n| 命令 | 类别 | 输入 | 作用 | 专用参数 |\n|---|---|---|---|---|\n")
    input_names = {"none": "无", "optional": "可选", "required": "必填"}
    for name in sorted(commands.COMMANDS):
        cmd = commands.COMMANDS[name]
        flags = "、".join("`%s`" % flag for flag in cmd.flags) or "—"
        lines.append("| `%s` | %s | %s | %s | %s |\n" % (name, cmd.category, input_names[cmd.input], _escape(cmd.summary), flags))
    lines.append("\n## 输入字段\n")
    for name in sorted(commands.COMMANDS):
        cmd = commands.COMMANDS[name]
        if not cmd.spec:
            continue
        lines.append("\n### `%s`\n\n" % name)
        if name == "commit-turn":
            lines.append("操作列表的字段见 `references/operations.md`。\n\n")
        lines.append(render_spec(getattr(specs, cmd.spec)))
    lines.append("\n## 错误码\n\n| 码 | 含义 | 退出码 |\n|---|---|---|\n")
    for code, text in errors.ERROR_DESCRIPTIONS.items():
        lines.append("| `%s` | %s | %d |\n" % (code, _escape(text), errors.exit_code_for(code)))
    lines.append("\n## 退出码\n\n| 退出码 | 类别 |\n|---|---|\n")
    lines.append("| %d | 成功 |\n" % errors.EXIT_OK)
    lines.append("| %d | 输入与领域错误：按 `details` 修正后重交 |\n" % errors.EXIT_INPUT)
    lines.append("| %d | 环境错误：Python、数据目录、存储占用、版本 |\n" % errors.EXIT_ENVIRONMENT)
    lines.append("| %d | 内部错误：状态不变，附日志位置 |\n" % errors.EXIT_INTERNAL)
    return "".join(lines)


def render_operations():
    from adult_tension import schema as S
    from adult_tension.domain import ops, structure

    lines = [GENERATED_NOTE, "# 操作参考\n\n"]
    lines.append("`commit-turn` 的 `operations` 是一个操作数组。操作按顺序应用，后面的操作看得到前面操作的效果；任何一个不合法，整个提交被拒绝、状态不变，错误列出全部问题及其 JSON 路径。NPC 拒绝玩家（`npc_response: refuse`）是合法的叙事结果，不是错误。\n\n")
    lines.append("提交里没有 `advance_time` 时，时钟默认推进 %d 分钟。单次推进上限 %d 天。\n\n" % (structure.DEFAULT_ADVANCE_MINUTES, structure.MAX_ADVANCE_MINUTES // structure.MINUTES_PER_DAY))
    lines.append("## 提交的顶层字段\n\n")
    from adult_tension.domain.turn import commit_fields

    lines.append(render_spec(S.Obj(commit_fields()), 2))
    lines.append("\n## 操作一览\n\n| op | 作用 |\n|---|---|\n")
    for name in ops.SPECS:
        lines.append("| `%s` | %s |\n" % (name, _escape(ops.DESCRIPTIONS[name])))
    for name, spec in ops.SPECS.items():
        lines.append("\n## `%s`\n\n%s\n\n" % (name, ops.DESCRIPTIONS[name]))
        lines.append(render_spec(spec))
        branch = ops.HANDLERS[name][1]
        if not branch:
            lines.append("\n不能出现在 `roll` 的分支里。\n")
    lines.append("\n## 取值表\n\n")
    lines.append("- 回应光谱：%s\n" % "、".join("`%s` %s" % (k, v) for k, v in structure.RESPONSE_LABELS.items()))
    lines.append("- 关系阶段（世界可改名）：%s\n" % "、".join("`%s` %s" % (k, v) for k, v in structure.STAGE_LABELS.items()))
    lines.append("- 事件到期：%s；`chance` 由引擎掷骰得到 `hit` / `miss`\n" % "、".join("`%s` → `%s`" % (k, v) for k, v in structure.DUE_OUTCOME.items()))
    lines.append("- 状况：%s（其中 %s 的角色不参与亲密场景）\n" % ("、".join("`%s`" % k for k in structure.CONDITION_KINDS), "、".join("`%s`" % k for k in structure.INCAPACITATING)))
    return "".join(lines)


def render_worlds():
    from adult_tension.content.store import ContentStore

    index = ContentStore(os.path.join(_runtime.SKILL_ROOT, "content")).index()
    lines = [GENERATED_NOTE, "# 世界列表\n\n"]
    lines.append("内容版本：`%s`。只有 `released` 的世界参与随机开局、出现在 `list-worlds` 里。\n\n" % index["content_version"])
    lines.append("| 世界 | ID | 时代 | 地方 | 一句话 | 模式 | 状态 |\n|---|---|---|---|---|---|---|\n")
    modes = {"daily": "日常", "pressure": "有压力"}
    for world in index["worlds"]:
        lines.append(
            "| %s | `%s` | %s | %s | %s | %s | %s |\n"
            % (world["title"], world["id"], world["era"], world["region"], _escape(world["summary"]), "、".join(modes[m] for m in world["modes"]), world["status"])
        )
    return "".join(lines)


CUSTOM_EXAMPLE = os.path.join(_runtime.REPO_ROOT, "content-src", "examples", "custom_world.json")


def render_custom_world():
    from adult_tension.content.store import ContentStore
    from adult_tension.domain import structure as ST
    from adult_tension.domain import worldpack

    m = ST.CUSTOM_MINIMUMS
    with open(CUSTOM_EXAMPLE, "rb") as handle:
        example = handle.read().decode("utf-8").strip()
    lines = [GENERATED_NOTE, "# 自定义世界\n\n"]
    lines.append(
        "玩家要的时代或地方不在任何世界里、并且选了自定义世界时，你写一个小型世界包，放进 `new-game` 的 `custom_world` 字段提交。"
        "引擎用与正式世界相同的校验器检查它：数量下限更低，其余规则一条不降。"
        "它只存在于这一局的存档里：不进世界列表，不参与开局去重，也不能“重开 N 号”（用同一个世界包和同一个种子重新开局即可复现）。\n\n"
    )
    lines.append("## 提交与修正\n\n")
    lines.append("1. 先和玩家确认：时代与地方、日常还是有压力、想见到的两三个人。玩家没说的，按时代常识补齐，不要追问细节。\n")
    lines.append("2. 从文末的示例改起，写一个 JSON 对象：`\"custom\": true`，`id` 用 `custom_` 开头的小写字母、数字、下划线，不写 `extends`。\n")
    lines.append("3. 直接调用 `new-game`（不先用 `verify-content` 预检，它是开发工具），输入 `{\"request_id\", \"mode\", \"custom_world\": {...}}`；可带 `seed`、`player`、`npc_gender_preference`、`excludes.content_tags`，不带 `locks.world_id`、`excludes.world_ids`、`replay`。\n")
    lines.append("4. 返回 `CONTENT_ERROR` 时，`details` 一次列出全部问题，路径以 `$.custom_world` 开头；逐条改好，换新的 `request_id` 重交。只有需要玩家补设定时才把问题讲给玩家。\n\n")
    lines.append("## 数量下限\n\n| 项 | 下限 |\n|---|---|\n")
    rows = [
        ("世界规则 `rules`", m["rules"]),
        ("地点 `locations`", m["locations"]),
        ("人物模板 `character_templates`", m["character_templates"]),
        ("人物组合 `cast_combos`", m["cast_combos"]),
        ("张力引擎 `tension_engines`", m["tension_engines"]),
        ("玩家身份 `player_identities`", m["player_identities"]),
        ("钩子 `hooks`", m["hooks"]),
        ("姓 `name_pools.family`", m["family"]),
        ("名（女、男、中性名合计）", m["given_total"]),
    ]
    for label, need in rows:
        lines.append("| %s | %d |\n" % (label, need))
    lines.append("| 按要开的模式：日常活动 `daily_activities` 或压力 `pressures` | %d |\n\n" % m["mode_items"])
    lines.append(
        "要开日常模式就写够日常活动，要开压力模式就写够压力；模式是“随便”时，只写够了一种就开那一种，两种都够就随机。"
        "其余列表（风俗、背景人物、关系渠道、转折、昵称规则）可以为空；写了就按同样的规则检查。"
        "名池小的世界，同性别的名用完后引擎先用中性名，再重复；每种性别各写 4 个名最稳妥。\n\n"
    )
    lines.append("## 不降低的规则\n\n")
    lines.append("- **成年**：人物模板、背景人物、玩家身份的 `age_range` 下限 ≥ 18；人物模板与背景人物写明 `adult_context`（成年身份与处境）。\n")
    lines.append(
        "- **校园与师徒意象**：%s 这类词只能出现在明示成年的语境里——同一条文字（或该人物的 `adult_context`）里要有 %s 之类的词。\n"
        % ("、".join(worldpack.MINOR_TERMS), "、".join(worldpack.ADULT_MARKERS))
    )
    lines.append(
        "- **性别可变**：`gender: \"any\"` 的人物，文本里不写“他”“她”，用 `{npc.ta}`；人物组合、钩子、转折里用 `{槽位.name}`、`{槽位.ta}`。"
        "可用属性：`name`、`ta`、`family`、`given`、`call`、`role`、`title`。`{family}`、`{given}`、`{given_last}` 只用在称呼模板里。\n"
    )
    lines.append(
        "- **占位的作用域**：人物模板与背景人物用 `npc`、`player`；钩子用 `npc`（即钩子的 `slot`）、`player`；人物组合用它的槽位与 `player`；"
        "转折用人物模板 ID 与 `player`；压力只有 `player`（带 `leverage` 时加上把柄双方）；日常活动只有 `player`；世界层、规则、地点、玩家身份、张力引擎、关系渠道的文字不用占位（玩家身份的称呼模板除外）。\n"
    )
    lines.append("- **引用按 ID**：地点出口、组合槽位与张力引擎、钩子槽位、活动与压力的地点都要能解析；ID 在包内唯一，`player` 是保留字。\n")
    lines.append("- **时代**：`forbidden_terms` 写本世界不该出现的词（器物、说法），校验器扫描全部文本。\n")
    lines.append("- **原创**：不用已知作品的角色名与专有设定。\n")
    lines.append(
        "- **有内容**：不写空串、“待补”“TODO”“—”或与字段名相同的文字；同一包内不写重复的整句。"
        "地点至少一个 `public`、一个 `semi` 或 `private`，任意两个地点的 `privacy`、`visibility`、`affordances` 不能完全相同。\n"
    )
    lines.append("- **压力**：五拍齐全，`near.deadline_minutes` 大于 `immediate.minutes`，出路至少两条且各有代价；带 `leverage` 标记的压力写明 `leverage` 的双方与依据，双方要同在某个人物组合里。\n")
    tags = ContentStore(os.path.join(_runtime.SKILL_ROOT, "content")).tags()["tags"]
    lines.append("- **标签**：`content_tags` 与各处 `tags` 只能用内容标签表里的 ID：%s。\n\n" % "、".join("`%s` %s" % (t["id"], t["label"]) for t in tags))
    lines.append("## 字段\n\n")
    lines.append(render_spec(worldpack.WORLD, 2))
    lines.append("\n## 示例\n\n一个能通过校验、两种模式都能开局的最小世界：\n\n```json\n%s\n```\n" % example)
    return "".join(lines)


def generated_files():
    """Map of reference file name -> expected content."""
    _runtime.use_runtime()
    return {
        "commands.md": render_commands(),
        "operations.md": render_operations(),
        "worlds.md": render_worlds(),
        "custom_world.md": render_custom_world(),
    }


def main(argv):
    check = "--check" in argv
    target_dir = os.path.join(_runtime.SKILL_ROOT, "references")
    stale = []
    for name, content in generated_files().items():
        path = os.path.join(target_dir, name)
        current = None
        if os.path.exists(path):
            with open(path, "rb") as handle:
                current = handle.read().decode("utf-8")
        if current != content:
            stale.append(name)
            if not check:
                with open(path, "wb") as handle:
                    handle.write(content.encode("utf-8"))
    if check and stale:
        print("stale: " + ", ".join(stale))
        return 1
    print(("updated: " + ", ".join(stale)) if stale else "up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
