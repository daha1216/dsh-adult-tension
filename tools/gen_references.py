"""Generate the code-derived reference files in <skill>/references/.

    python tools/gen_references.py            # write the files
    python tools/gen_references.py --check    # exit 1 if any file is stale

Generated files are committed; tools/validate_skill.py checks that they match
the code (SKILL_PACKAGING.md section 3).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _runtime  # noqa: E402

GENERATED_NOTE = "<!-- 本文件由 tools/gen_references.py 生成，不要手改。 -->\n\n"


def _escape(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_commands():
    from adult_tension import errors
    from adult_tension.application import commands

    lines = [GENERATED_NOTE, "# 命令参考\n\n"]
    lines.append("调用：`<python> scripts/adult_tension.py <command> --json [--input-file PATH] [--data-dir PATH]`\n\n")
    lines.append("- 输入是一个 JSON 对象，来自 `--input-file`（UTF-8，可带 BOM）。需要输入的命令在没有 `--input-file` 且 stdin 不是终端时读取 stdin；可选输入只从 `--input-file` 读取（`--input-file -` 表示 stdin）。\n")
    lines.append("- 输出是一个信封 `{\"ok\", \"data\", \"error\"}`，以 UTF-8 字节写到 stdout。成功与失败都附带 `next_request_id`（成功在 `data` 里，失败在 `error` 里）。\n")
    lines.append("- 全局参数：`--json`（输出 JSON，始终如此）、`--pretty`（缩进输出）、`--debug`（日志记录输入）、`--input-file PATH`、`--data-dir PATH`。\n\n")
    lines.append("## 命令一览\n\n| 命令 | 类别 | 输入 | 作用 | 专用参数 |\n|---|---|---|---|---|\n")
    input_names = {"none": "无", "optional": "可选", "required": "必填"}
    for name in sorted(commands.COMMANDS):
        cmd = commands.COMMANDS[name]
        flags = "、".join("`%s`" % flag for flag in cmd.flags) or "—"
        lines.append("| `%s` | %s | %s | %s | %s |\n" % (name, cmd.category, input_names[cmd.input], _escape(cmd.summary), flags))
    lines.append("\n## 错误码\n\n| 码 | 含义 | 退出码 |\n|---|---|---|\n")
    for code, text in errors.ERROR_DESCRIPTIONS.items():
        lines.append("| `%s` | %s | %d |\n" % (code, _escape(text), errors.exit_code_for(code)))
    lines.append("\n## 退出码\n\n| 退出码 | 类别 |\n|---|---|\n")
    lines.append("| %d | 成功 |\n" % errors.EXIT_OK)
    lines.append("| %d | 输入与领域错误：按 `details` 修正后重交 |\n" % errors.EXIT_INPUT)
    lines.append("| %d | 环境错误：Python、数据目录、存储占用、版本 |\n" % errors.EXIT_ENVIRONMENT)
    lines.append("| %d | 内部错误：状态不变，附日志位置 |\n" % errors.EXIT_INTERNAL)
    return "".join(lines)


def generated_files():
    """Map of reference file name -> expected content."""
    _runtime.use_runtime()
    return {"commands.md": render_commands()}


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
