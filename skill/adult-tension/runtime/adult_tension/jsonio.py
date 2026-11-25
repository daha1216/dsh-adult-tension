"""Strict JSON reading and deterministic JSON writing.

The standard library silently keeps the last value of a duplicated key and
accepts NaN/Infinity. Input from the calling agent and content files must
reject both, with a JSON path for every problem. It also accepts a lone
UTF-16 surrogate escape ("\\ud83d" without its pair), which no UTF-8 output
can carry, and nesting deep enough to exhaust the recursion of the code that
reads the result; both are input errors too.
"""

import json
import re

from .errors import INVALID_INPUT, AppError, detail

MAX_DEPTH = 64  # real inputs nest under 10 levels
SURROGATE_ESCAPE = re.compile(r"\\u[dD][89a-fA-F]")


class DupDict(dict):
    """A dict that remembers which keys appeared more than once."""

    __slots__ = ("dup_keys",)

    def __init__(self):
        super().__init__()
        self.dup_keys = ()


def _dup_dict(pairs):
    obj = DupDict()
    dups = []
    for key, value in pairs:
        if key in obj and key not in dups:
            dups.append(key)
        obj[key] = value
    obj.dup_keys = tuple(dups)
    return obj


def _reject_constant(name):
    raise ValueError("不允许的数值常量 %s" % name)


def decode_bytes(raw, source="input"):
    """Decode UTF-8 bytes, tolerating a BOM."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AppError(
            INVALID_INPUT,
            "%s 不是 UTF-8 编码" % source,
            [detail("$", "第 %d 字节无法按 UTF-8 解码" % exc.start, "把输入保存为 UTF-8（可带 BOM）后重新提交")],
        )


def loads_strict(text, source="input"):
    """Parse JSON text into plain dicts and lists; raise INVALID_INPUT on
    syntax errors, duplicate keys and the shapes described above."""
    found_dups = []

    def hook(pairs):
        obj = dict(pairs)
        if len(obj) != len(pairs):
            # only a repeated key needs the slow object (then this raises)
            obj = _dup_dict(pairs)
            found_dups.append(obj)
        return obj

    try:
        obj = json.loads(text, object_pairs_hook=hook, parse_constant=_reject_constant)
    except ValueError as exc:
        line = getattr(exc, "lineno", None)
        col = getattr(exc, "colno", None)
        where = "（第 %s 行第 %s 列）" % (line, col) if line else ""
        raise AppError(
            INVALID_INPUT,
            "%s 不是合法的 JSON%s" % (source, where),
            [detail("$", str(exc), "检查引号、逗号与括号；字符串里的换行写成 \\n")],
        )
    except RecursionError:
        raise AppError(INVALID_INPUT, "%s 嵌套太深" % source, [_too_deep("$")])
    check_strings = SURROGATE_ESCAPE.search(text) is not None
    if not _shape_ok(obj, check_strings):
        raise AppError(INVALID_INPUT, "%s 有无法处理的结构或字符" % source, _shape_details(obj, check_strings))
    # Walking the whole tree for the paths is needed only when a duplicate
    # was seen while parsing.
    problems = duplicate_key_details(obj) if found_dups else []
    if problems:
        raise AppError(INVALID_INPUT, "JSON 中有重复键", problems)
    return obj


def _too_deep(path):
    return detail(path, "嵌套超过 %d 层" % MAX_DEPTH, "按命令说明的结构提交，不要多套数组或对象")


def _broken(text):
    try:
        text.encode("utf-8")
        return False
    except UnicodeEncodeError:
        return True


def _printable(text):
    return text.encode("utf-8", "backslashreplace").decode("utf-8")


_BROKEN_KEY = object()


def _shape_ok(obj, check_strings):
    """The cheap pass, level by level and without paths (doctor reads every
    content file through here); _shape_details runs only when it fails."""
    if isinstance(obj, str):
        return not (check_strings and _broken(obj))
    level = [obj] if isinstance(obj, (dict, list)) else []
    depth = 0
    while level:
        depth += 1
        if depth > MAX_DEPTH:
            return False
        below = []
        for value in level:
            if isinstance(value, dict):
                if check_strings and any(_broken(key) for key in value):
                    return False
                value = value.values()
            for item in value:
                if isinstance(item, (dict, list)):
                    below.append(item)
                elif check_strings and isinstance(item, str) and _broken(item):
                    return False
        level = below
    return True


def _shape_details(obj, check_strings):
    """Nesting beyond MAX_DEPTH, and (when the text had a surrogate escape)
    strings and keys holding a lone surrogate. Iterative: the input may be
    too deep for recursion. Paths in document order."""
    problems = []
    stack = [(obj, "$", 1)]
    while stack:
        value, path, depth = stack.pop()
        if value is _BROKEN_KEY:
            problems.append(detail(path, "键名里有落单的 UTF-16 代理字符", "键名按命令说明写"))
            continue
        if isinstance(value, str):
            if check_strings and _broken(value):
                problems.append(detail(path, "字符串里有落单的 UTF-16 代理字符", "表情等字符要么直接写原字符，要么写成成对的 \\u 转义（例如 \\ud83d\\ude00）"))
            continue
        if not isinstance(value, (dict, list)):
            continue
        if depth > MAX_DEPTH:
            problems.append(_too_deep(path))
            continue
        if isinstance(value, dict):
            children = []
            for key, item in value.items():
                child = "%s.%s" % (path, _printable(key) if check_strings else key)
                if check_strings and _broken(key):
                    children.append((_BROKEN_KEY, child, depth))
                children.append((item, child, depth + 1))
        else:
            children = [(item, "%s[%d]" % (path, index), depth + 1) for index, item in enumerate(value)]
        stack.extend(reversed(children))
    return problems


def duplicate_key_details(obj, path="$"):
    found = []
    _walk_dups(obj, path, found)
    return found


def _walk_dups(obj, path, found):
    if isinstance(obj, dict):
        for key in getattr(obj, "dup_keys", ()):
            found.append(detail("%s.%s" % (path, key), "重复键：%s" % key, "删掉多余的一个，同一对象里每个键只能出现一次"))
        for key, value in obj.items():
            _walk_dups(value, "%s.%s" % (path, key), found)
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            _walk_dups(value, "%s[%d]" % (path, index), found)


def dumps(obj, pretty=False):
    """Compact (or indented) UTF-8-friendly JSON text."""
    if pretty:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def canonical(obj):
    """Deterministic text used for digests and byte-stable artifacts."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def copy(obj):
    """Fast deep copy of JSON-compatible data."""
    if isinstance(obj, dict):
        return {k: copy(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [copy(v) for v in obj]
    return obj
