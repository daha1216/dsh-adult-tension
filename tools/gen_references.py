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
    lines.append("- 开发开关（环境变量，由测试环境设置，玩家不需要）：`ADULT_TENSION_HOME` 指定数据目录；`ADULT_TENSION_INCLUDE_DRAFTS=1` 让未发布的世界参与开局与世界列表。\n\n")
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


def generated_files():
    """Map of reference file name -> expected content."""
    _runtime.use_runtime()
    return {"commands.md": render_commands(), "operations.md": render_operations(), "worlds.md": render_worlds()}


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
