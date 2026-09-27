"""Validate an installable Skill directory.

    python tools/validate_skill.py skill/adult-tension [--json]

Checks (ACCEPTANCE.md section 1, SKILL_PACKAGING.md sections 1-3, 12):
  - SKILL.md frontmatter (name, description) and size <= 16 KB;
  - every relative link / referenced path resolves inside the Skill directory;
  - no forbidden files (tests, sources, tools, reports, caches, user data);
  - generated reference files match the code;
  - the entry script stays parseable by old Pythons; the runtime parses as
    Python 3.10, imports only the standard library and avoids 3.11+ APIs.
Exit code 0 when valid, 1 otherwise.
"""

import ast
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _runtime  # noqa: E402

SKILL_MD_LIMIT = 16 * 1024
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
ALLOWED_FRONTMATTER = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
CODE_PATH_RE = re.compile(r"`((?:references|scripts|agents|content|runtime)/[A-Za-z0-9_./-]+)`")

# Python 3.11+ standard-library names that a 3.10 runtime must not use.
POST_310_APIS = (
    "tomllib",
    "StrEnum",
    "datetime.UTC",
    "file_digest",
    "itertools.batched",
    "ExceptionGroup",
    "TaskGroup",
    "LiteralString",
    "typing.Self",
    "typing.Never",
    "assert_never",
    "reveal_type",
    "Path.walk",
    "sqlite3.Blob",
    ".autocommit",
    "add_note",
)


def _frontmatter(text):
    if not text.startswith("---\n"):
        return None, ["SKILL.md 必须以 --- 开头的 frontmatter 开始"]
    end = text.find("\n---\n", 4)
    if end < 0:
        return None, ["frontmatter 没有以 --- 结束"]
    fields = {}
    problems = []
    for number, line in enumerate(text[4:end].split("\n"), start=2):
        if not line.strip():
            continue
        if ":" not in line or line.startswith(" "):
            problems.append("frontmatter 第 %d 行无法解析：%s" % (number, line[:60]))
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key in fields:
            problems.append("frontmatter 重复键：%s" % key)
        fields[key] = value.strip()
    return fields, problems


def check_skill_md(skill_dir, problems):
    path = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(path):
        problems.append("缺少 SKILL.md")
        return
    raw = open(path, "rb").read()
    if len(raw) > SKILL_MD_LIMIT:
        problems.append("SKILL.md 为 %d 字节，超过 %d 字节上限" % (len(raw), SKILL_MD_LIMIT))
    text = raw.decode("utf-8")
    fields, fm_problems = _frontmatter(text)
    problems.extend(fm_problems)
    if fields is None:
        return
    for key in fields:
        if key not in ALLOWED_FRONTMATTER:
            problems.append("frontmatter 未知键：%s" % key)
    name = fields.get("name", "")
    if not name:
        problems.append("frontmatter 缺少 name")
    elif not NAME_RE.match(name) or len(name) > 64:
        problems.append("name 必须是 ≤64 位的小写字母、数字与连字符：%s" % name)
    elif name != os.path.basename(os.path.normpath(skill_dir)):
        problems.append("name（%s）应与目录名（%s）一致" % (name, os.path.basename(os.path.normpath(skill_dir))))
    description = fields.get("description", "")
    if not description:
        problems.append("frontmatter 缺少 description")
    elif len(description) > 1024:
        problems.append("description 超过 1024 字符")
    elif re.search(r"<[A-Za-z/]", description):
        problems.append("description 不能包含 XML 标签")


def check_links(skill_dir, problems):
    root = os.path.realpath(skill_dir)
    for base, _dirs, names in os.walk(skill_dir):
        for name in names:
            if not name.endswith(".md"):
                continue
            path = os.path.join(base, name)
            rel_file = os.path.relpath(path, skill_dir).replace(os.sep, "/")
            text = open(path, "rb").read().decode("utf-8")
            targets = [(m, "link") for m in LINK_RE.findall(text)]
            targets += [(m, "path") for m in CODE_PATH_RE.findall(text)]
            for target, kind in targets:
                if re.match(r"^[a-z]+:", target) or target.startswith("#"):
                    continue
                clean = target.split("#", 1)[0]
                if kind == "link":
                    resolved = os.path.realpath(os.path.join(base, clean))
                else:
                    resolved = os.path.realpath(os.path.join(skill_dir, clean))
                if os.path.commonpath([resolved, root]) != root:
                    problems.append("%s 链接指向 Skill 目录之外：%s" % (rel_file, target))
                elif not os.path.exists(resolved):
                    problems.append("%s 引用的路径不存在：%s" % (rel_file, target))


def _allowed(rel):
    parts = rel.split("/")
    top = parts[0]
    if rel == "SKILL.md":
        return True
    if top == "agents":
        return len(parts) == 2 and parts[1].endswith(".yaml")
    if top == "references":
        return len(parts) == 2 and parts[1].endswith(".md")
    if top == "scripts":
        return rel == "scripts/adult_tension.py"
    if top == "runtime":
        return len(parts) >= 3 and parts[1] == "adult_tension" and rel.endswith(".py") and not parts[-1].startswith("test_")
    if top == "content":
        if rel in ("content/index.json", "content/tags.json"):
            return True
        return len(parts) == 3 and parts[1] == "worlds" and parts[2].endswith(".json")
    return False


def check_files(skill_dir, problems):
    for base, dirs, names in os.walk(skill_dir):
        for directory in list(dirs):
            if directory == "__pycache__" or directory.startswith("."):
                rel = os.path.relpath(os.path.join(base, directory), skill_dir).replace(os.sep, "/")
                problems.append("禁止的目录（缓存或隐藏目录）：%s" % rel)
                dirs.remove(directory)
        for name in names:
            rel = os.path.relpath(os.path.join(base, name), skill_dir).replace(os.sep, "/")
            if not _allowed(rel):
                problems.append("Skill 目录里不允许的文件：%s" % rel)


def check_generated(skill_dir, problems):
    import gen_references

    _runtime.use_runtime(skill_dir)
    for name, expected in gen_references.generated_files().items():
        path = os.path.join(skill_dir, "references", name)
        if not os.path.exists(path):
            problems.append("缺少生成的参考文件：references/%s（运行 tools/gen_references.py）" % name)
            continue
        if open(path, "rb").read().decode("utf-8") != expected:
            problems.append("references/%s 与代码不一致（运行 tools/gen_references.py）" % name)


def check_python_floor(skill_dir, problems):
    entry = os.path.join(skill_dir, "scripts", "adult_tension.py")
    if not os.path.isfile(entry):
        problems.append("缺少入口脚本 scripts/adult_tension.py")
    else:
        source = open(entry, "rb").read().decode("utf-8")
        try:
            tree = ast.parse(source, feature_version=(3, 4))
        except SyntaxError as exc:
            problems.append("入口脚本必须能被旧版本 Python 解析：%s" % exc)
        else:
            for node in ast.walk(tree):
                modern = isinstance(node, (ast.JoinedStr, ast.AnnAssign, ast.NamedExpr, ast.AsyncFunctionDef))
                if isinstance(node, ast.FunctionDef):
                    modern = modern or node.returns is not None
                    modern = modern or any(a.annotation is not None for a in node.args.args + node.args.kwonlyargs)
                if modern:
                    problems.append("入口脚本第 %d 行用了新语法（f-string、注解、海象运算符等），旧 Python 无法解析" % node.lineno)
    stdlib = set(sys.stdlib_module_names)
    runtime_root = os.path.join(skill_dir, "runtime")
    for base, _dirs, names in os.walk(runtime_root):
        for name in names:
            if not name.endswith(".py"):
                continue
            path = os.path.join(base, name)
            rel = os.path.relpath(path, skill_dir).replace(os.sep, "/")
            source = open(path, "rb").read().decode("utf-8")
            try:
                tree = ast.parse(source, feature_version=(3, 10))
            except SyntaxError as exc:
                problems.append("%s 不能按 Python 3.10 解析：%s" % (rel, exc))
                continue
            for node in ast.walk(tree):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    modules = [node.module]
                for module in modules:
                    top = module.split(".")[0]
                    if top != "adult_tension" and top not in stdlib:
                        problems.append("%s 导入了非标准库模块：%s" % (rel, module))
            for api in POST_310_APIS:
                if api in source:
                    problems.append("%s 使用了 Python 3.11+ 才有的接口：%s" % (rel, api))


def validate(skill_dir):
    problems = []
    if not os.path.isdir(skill_dir):
        return ["目录不存在：%s" % skill_dir]
    check_skill_md(skill_dir, problems)
    check_links(skill_dir, problems)
    check_files(skill_dir, problems)
    check_python_floor(skill_dir, problems)
    check_generated(skill_dir, problems)
    return problems


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    skill_dir = os.path.abspath(args[0] if args else _runtime.SKILL_ROOT)
    problems = validate(skill_dir)
    size = os.path.getsize(os.path.join(skill_dir, "SKILL.md")) if os.path.isfile(os.path.join(skill_dir, "SKILL.md")) else None
    if "--json" in argv:
        out = {"ok": not problems, "skill_dir": skill_dir, "skill_md_bytes": size, "problems": problems}
        sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode("utf-8") + b"\n")
    else:
        lines = ["validate_skill: %s" % skill_dir, "SKILL.md: %s bytes (limit %d)" % (size, SKILL_MD_LIMIT)]
        lines += ["FAIL " + p for p in problems] or ["OK"]
        sys.stdout.buffer.write(("\n".join(lines) + "\n").encode("utf-8"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
