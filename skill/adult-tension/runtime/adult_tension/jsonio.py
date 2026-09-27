"""Strict JSON reading and deterministic JSON writing.

The standard library silently keeps the last value of a duplicated key and
accepts NaN/Infinity. Input from the calling agent and content files must
reject both, with a JSON path for every problem.
"""

import json

from .errors import INVALID_INPUT, AppError, detail


class DupDict(dict):
    """A dict that remembers which keys appeared more than once."""

    __slots__ = ("dup_keys",)

    def __init__(self):
        super().__init__()
        self.dup_keys = ()


def _pairs_hook(pairs):
    obj = DupDict()
    dups = []
    for key, value in pairs:
        if key in obj and key not in dups:
            dups.append(key)
        obj[key] = value
    if dups:
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
            [detail("$", "第 %d 字节无法按 UTF-8 解码" % exc.start, "把输入保存为 UTF-8（可带 BOM）后重交")],
        )


def loads_strict(text, source="input"):
    """Parse JSON text; raise INVALID_INPUT on syntax errors or duplicate keys."""
    try:
        obj = json.loads(text, object_pairs_hook=_pairs_hook, parse_constant=_reject_constant)
    except ValueError as exc:
        line = getattr(exc, "lineno", None)
        col = getattr(exc, "colno", None)
        where = " (第 %s 行第 %s 列)" % (line, col) if line else ""
        raise AppError(
            INVALID_INPUT,
            "%s 不是合法的 JSON%s" % (source, where),
            [detail("$", str(exc), "检查引号、逗号与括号；字符串里的换行写成 \\n")],
        )
    problems = duplicate_key_details(obj)
    if problems:
        raise AppError(INVALID_INPUT, "JSON 中有重复键", problems)
    return obj


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


def plain(obj):
    """Convert DupDict trees to plain dicts (after validation)."""
    if isinstance(obj, dict):
        return {key: plain(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [plain(value) for value in obj]
    return obj


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
    return json.loads(json.dumps(obj, ensure_ascii=False))
