"""Validate an installable Skill directory.

    python tools/validate_skill.py skill/adult-tension [--json]

Checks (ACCEPTANCE.md section 1, SKILL_PACKAGING.md sections 1-3, 12):
  - SKILL.md frontmatter (name, description) and size <= 16 KB;
  - every relative link / referenced path resolves inside the Skill directory;
  - no forbidden files (tests, sources, tools, reports, caches, user data);
  - generated reference files match the code;
  - when validating the in-repo Skill (spec/ present), SKILL.md, openai.yaml
    and narrative.md stay byte-synced with their spec/ counterparts, and all
    git-tracked tests/ and tools/ Python files parse and stay Python 3.10 safe;
  - the entry script stays parseable by old Pythons; the runtime parses as
    Python 3.10, imports only the standard library and avoids 3.11+ APIs.
Exit code 0 when valid, 1 otherwise.
"""

import ast
import io
import json
import os
import re
import subprocess
import sys
import tokenize

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

PY311_MODULES = frozenset({"tomllib", "wsgiref.types"})
PY311_FROM_IMPORTS = {
    "typing": frozenset({
        "Self", "Never", "LiteralString", "Required", "NotRequired",
        "Unpack", "TypeVarTuple", "assert_never", "assert_type",
        "reveal_type", "dataclass_transform", "override", "TypeAliasType",
    }),
    "enum": frozenset({"StrEnum", "ReprEnum", "EnumCheck", "FlagBoundary", "verify", "member", "nonmember"}),
    "datetime": frozenset({"UTC"}),
    "hashlib": frozenset({"file_digest"}),
    "itertools": frozenset({"batched"}),
    "contextlib": frozenset({"chdir"}),
    "asyncio": frozenset({"TaskGroup", "Runner", "timeout", "timeout_at"}),
}
PY311_BUILTINS = frozenset({"ExceptionGroup", "BaseExceptionGroup"})
PY311_ATTRS = frozenset({
    "UTC", "StrEnum", "file_digest", "batched", "TaskGroup",
    "LiteralString", "Self", "Never", "Required", "NotRequired",
    "assert_never", "reveal_type", "autocommit", "add_note",
    "enterContext", "enterClassContext", "enterModuleContext",
})
FORBIDDEN_REPO_SCAN_PREFIXES = ("tools/readme_art/",)


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


def _check_fstrings_310(source, rel, problems):
    fstart = getattr(tokenize, "FSTRING_START", None)
    fmid = getattr(tokenize, "FSTRING_MIDDLE", None)
    fend = getattr(tokenize, "FSTRING_END", None)
    if fstart is None:
        return
    stack = []
    for ttype, tstr, (srow, _scol), _end, _line in tokenize.generate_tokens(io.StringIO(source).readline):
        if ttype == fstart:
            q = tstr.lstrip("fFrRbBuU")
            stack.append((q, len(q) == 3))
        elif ttype == fend:
            if stack:
                stack.pop()
        elif stack and ttype != fmid:
            outer_q, is_triple = stack[-1]
            if ttype == tokenize.COMMENT:
                problems.append("%s:%d 使用了 Python 3.12+ f-string 内置注释" % (rel, srow))
            if "\\" in tstr:
                problems.append("%s:%d 使用了 Python 3.12+ f-string 表达式反斜杠" % (rel, srow))
            if ttype in (tokenize.STRING, fstart) and outer_q in tstr:
                problems.append("%s:%d 使用了 Python 3.12+ f-string 同引号嵌套" % (rel, srow))
            if ttype == tokenize.NL and not is_triple:
                problems.append("%s:%d 使用了 Python 3.12+ 单引号多行 f-string" % (rel, srow))


def _check_ast_310(source, rel, problems, stdlib_only=False, stdlib=None):
    try:
        tree = ast.parse(source, filename=rel, feature_version=(3, 10))
    except SyntaxError as exc:
        problems.append("%s 不能按 Python 3.10 解析：%s" % (rel, exc))
        return
    _check_fstrings_310(source, rel, problems)
    for node in ast.walk(tree):
        if hasattr(ast, "TryStar") and isinstance(node, ast.TryStar):
            problems.append("%s:%d 使用了 Python 3.11+ except* 语法" % (rel, node.lineno))
        if hasattr(ast, "TypeAlias") and isinstance(node, ast.TypeAlias):
            problems.append("%s:%d 使用了 Python 3.12+ type 别名语法" % (rel, node.lineno))
        if getattr(node, "type_params", None):
            problems.append("%s:%d 使用了 Python 3.12+ PEP 695 泛型语法" % (rel, node.lineno))
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in PY311_MODULES or alias.name.split(".")[0] in PY311_MODULES:
                    problems.append("%s:%d 导入了 Python 3.11+ 模块：%s" % (rel, node.lineno, alias.name))
                if stdlib_only and stdlib is not None:
                    top = alias.name.split(".")[0]
                    if top != "adult_tension" and top not in stdlib:
                        problems.append("%s 导入了非标准库模块：%s" % (rel, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module in PY311_MODULES or node.module.split(".")[0] in PY311_MODULES:
                problems.append("%s:%d 导入了 Python 3.11+ 模块：%s" % (rel, node.lineno, node.module))
            banned = PY311_FROM_IMPORTS.get(node.module)
            if banned:
                for alias in node.names:
                    if alias.name in banned:
                        problems.append("%s:%d 导入了 Python 3.11+ 接口：%s.%s" % (rel, node.lineno, node.module, alias.name))
            if stdlib_only and stdlib is not None:
                top = node.module.split(".")[0]
                if top != "adult_tension" and top not in stdlib:
                    problems.append("%s 导入了非标准库模块：%s" % (rel, node.module))
        elif isinstance(node, ast.Name) and node.id in PY311_BUILTINS:
            problems.append("%s:%d 使用了 Python 3.11+ 内置异常：%s" % (rel, node.lineno, node.id))
        elif isinstance(node, ast.Attribute):
            if node.attr in PY311_ATTRS:
                problems.append("%s:%d 使用了 Python 3.11+ 属性/接口：%s" % (rel, node.lineno, node.attr))
            elif node.attr == "Blob" and isinstance(node.value, ast.Name) and node.value.id == "sqlite3":
                problems.append("%s:%d 使用了 Python 3.11+ 接口：sqlite3.Blob" % (rel, node.lineno))
            elif node.attr == "walk" and not (isinstance(node.value, ast.Name) and node.value.id in ("os", "ast")):
                problems.append("%s:%d 疑似使用了 Python 3.12+ Path.walk" % (rel, node.lineno))


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
            _check_ast_310(source, rel, problems, stdlib_only=True, stdlib=stdlib)
            for api in POST_310_APIS:
                if api in source:
                    problems.append("%s 使用了 Python 3.11+ 才有的接口：%s" % (rel, api))


def _repo_root_for(skill_dir):
    """Return the repository root iff `skill_dir` sits at `<repo>/skill/<name>`
    with `<repo>/spec/SKILL_TEMPLATE.md` present; None for standalone bare copies."""
    real_skill = os.path.realpath(skill_dir)
    parent = os.path.dirname(real_skill)
    if os.path.basename(parent) != "skill":
        return None
    repo_root = os.path.dirname(parent)
    if os.path.isfile(os.path.join(repo_root, "spec", "SKILL_TEMPLATE.md")):
        return repo_root
    return None


def _extract_markdown_fence(template_bytes):
    text = template_bytes.decode("utf-8")
    marker = "\n```markdown\n"
    start = text.find(marker)
    end = text.rfind("\n```")
    if start < 0 or end <= start:
        return None
    body = text[start + len(marker) : end] + "\n"
    return body.encode("utf-8")


def check_repo_sync_and_py310(skill_dir, problems):
    repo_root = _repo_root_for(skill_dir)
    if repo_root is None:
        return
    spec_dir = os.path.join(repo_root, "spec")

    # 1. SKILL.md <-> spec/SKILL_TEMPLATE.md markdown fence
    skill_md = os.path.join(skill_dir, "SKILL.md")
    tpl_md = os.path.join(spec_dir, "SKILL_TEMPLATE.md")
    if os.path.isfile(skill_md) and os.path.isfile(tpl_md):
        expected_skill = _extract_markdown_fence(open(tpl_md, "rb").read())
        if expected_skill is None:
            problems.append("spec/SKILL_TEMPLATE.md 缺少 ```markdown 围栏")
        elif open(skill_md, "rb").read() != expected_skill:
            problems.append("SKILL.md 与 spec/SKILL_TEMPLATE.md 围栏内容不一致（请保持双写真源逐字节同步）")

    # 2. agents/openai.yaml <-> spec/agents/openai.yaml
    skill_yaml = os.path.join(skill_dir, "agents", "openai.yaml")
    spec_yaml = os.path.join(spec_dir, "agents", "openai.yaml")
    if os.path.isfile(skill_yaml) and os.path.isfile(spec_yaml):
        if open(skill_yaml, "rb").read() != open(spec_yaml, "rb").read():
            problems.append("agents/openai.yaml 与 spec/agents/openai.yaml 不一致（请保持双写真源逐字节同步）")

    # 3. references/narrative.md <-> spec/NARRATIVE_RULES.md
    skill_nar = os.path.join(skill_dir, "references", "narrative.md")
    spec_nar = os.path.join(spec_dir, "NARRATIVE_RULES.md")
    if os.path.isfile(skill_nar) and os.path.isfile(spec_nar):
        if open(skill_nar, "rb").read() != open(spec_nar, "rb").read():
            problems.append("references/narrative.md 与 spec/NARRATIVE_RULES.md 不一致（请保持双写真源逐字节同步）")

    # 4. Python 3.10 floor check on git-tracked tests/ and tools/ (excluding untracked & readme_art)
    if not os.path.exists(os.path.join(repo_root, ".git")):
        return
    try:
        proc = subprocess.run(
            ["git", "-C", repo_root, "ls-files", "--", "tests", "tools"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )
    except OSError:
        return
    if proc.returncode != 0:
        return
    for raw_line in proc.stdout.decode("utf-8", "replace").splitlines():
        rel = raw_line.strip().replace("\\", "/")
        if not rel.endswith(".py"):
            continue
        if any(rel.startswith(p) for p in FORBIDDEN_REPO_SCAN_PREFIXES):
            continue
        full = os.path.join(repo_root, rel)
        if not os.path.isfile(full):
            continue
        source = open(full, "rb").read().decode("utf-8")
        _check_ast_310(source, rel, problems, stdlib_only=False)


def validate(skill_dir):
    problems = []
    if not os.path.isdir(skill_dir):
        return ["目录不存在：%s" % skill_dir]
    check_skill_md(skill_dir, problems)
    check_links(skill_dir, problems)
    check_files(skill_dir, problems)
    check_python_floor(skill_dir, problems)
    check_generated(skill_dir, problems)
    check_repo_sync_and_py310(skill_dir, problems)
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
