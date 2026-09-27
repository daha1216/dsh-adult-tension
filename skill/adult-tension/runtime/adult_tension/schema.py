"""Declarative shape validation with JSON paths.

Every object rejects unknown fields; numbers are never clamped; booleans are
not integers; every problem is collected with its path. The same specs drive
the generated field reference (references/operations.md).
"""

import re

from .errors import INVALID_INPUT, detail

MISSING = object()


def _type_name(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "布尔"
    if isinstance(value, int):
        return "整数"
    if isinstance(value, float):
        return "小数"
    if isinstance(value, str):
        return "字符串"
    if isinstance(value, list):
        return "数组"
    if isinstance(value, dict):
        return "对象"
    return type(value).__name__


class Spec:
    doc_text = ""

    def check(self, value, path, errors):
        raise NotImplementedError

    def doc(self):
        return self.doc_text

    def _type_error(self, value, path, errors, expected):
        errors.append(detail(path, "应为%s，实际是%s" % (expected, _type_name(value)), None, INVALID_INPUT))
        return MISSING


class Any(Spec):
    def __init__(self, doc="任意 JSON"):
        self.doc_text = doc

    def check(self, value, path, errors):
        return value


class Str(Spec):
    def __init__(self, min_len=1, max_len=None, pattern=None, pattern_hint=None):
        self.min_len = min_len
        self.max_len = max_len
        self.pattern = re.compile(pattern) if isinstance(pattern, str) else pattern
        self.pattern_hint = pattern_hint

    def check(self, value, path, errors):
        if not isinstance(value, str):
            return self._type_error(value, path, errors, "字符串")
        if len(value) < self.min_len:
            reason = "不能为空" if self.min_len == 1 else "至少 %d 个字符" % self.min_len
            errors.append(detail(path, reason, None, INVALID_INPUT))
            return MISSING
        if self.max_len is not None and len(value) > self.max_len:
            errors.append(detail(path, "长度 %d 超过上限 %d" % (len(value), self.max_len), "缩短到 %d 字以内" % self.max_len, INVALID_INPUT))
            return MISSING
        if self.pattern is not None and not self.pattern.fullmatch(value):
            errors.append(detail(path, "格式不合法：%s" % value[:60], self.pattern_hint, INVALID_INPUT))
            return MISSING
        return value

    def doc(self):
        parts = ["字符串"]
        if self.max_len:
            parts.append("≤%d 字" % self.max_len)
        if self.pattern_hint:
            parts.append(self.pattern_hint)
        return "，".join(parts)


class Int(Spec):
    def __init__(self, lo=None, hi=None):
        self.lo = lo
        self.hi = hi

    def check(self, value, path, errors):
        if isinstance(value, bool) or not isinstance(value, int):
            return self._type_error(value, path, errors, "整数")
        if (self.lo is not None and value < self.lo) or (self.hi is not None and value > self.hi):
            errors.append(detail(path, "数值 %d 超出范围 [%s, %s]" % (value, self.lo, self.hi), "不会自动截断，请给出范围内的值", INVALID_INPUT))
            return MISSING
        return value

    def doc(self):
        return "整数 %s..%s" % ("" if self.lo is None else self.lo, "" if self.hi is None else self.hi)


class Num(Spec):
    """A real number; lo/hi are exclusive when *_open is set."""

    def __init__(self, lo=None, hi=None, lo_open=False, hi_open=False):
        self.lo, self.hi, self.lo_open, self.hi_open = lo, hi, lo_open, hi_open

    def check(self, value, path, errors):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return self._type_error(value, path, errors, "数值")
        bad = False
        if self.lo is not None:
            bad = bad or (value <= self.lo if self.lo_open else value < self.lo)
        if self.hi is not None:
            bad = bad or (value >= self.hi if self.hi_open else value > self.hi)
        if bad:
            errors.append(detail(path, "数值 %s 超出范围 %s%s, %s%s" % (value, "(" if self.lo_open else "[", self.lo, self.hi, ")" if self.hi_open else "]"), "不会自动截断", INVALID_INPUT))
            return MISSING
        return float(value)

    def doc(self):
        return "数值 %s%s, %s%s" % ("(" if self.lo_open else "[", self.lo, self.hi, ")" if self.hi_open else "]")


class Bool(Spec):
    def check(self, value, path, errors):
        if not isinstance(value, bool):
            return self._type_error(value, path, errors, "布尔值 true/false")
        return value

    def doc(self):
        return "布尔"


class Enum(Spec):
    def __init__(self, *values):
        self.values = tuple(values)

    def check(self, value, path, errors):
        if not isinstance(value, str) or value not in self.values:
            errors.append(detail(path, "取值 %r 不在允许范围内" % (value,), "可选：%s" % " / ".join(self.values), INVALID_INPUT))
            return MISSING
        return value

    def doc(self):
        return "枚举：" + " / ".join("`%s`" % v for v in self.values)


class Nullable(Spec):
    def __init__(self, inner):
        self.inner = inner

    def check(self, value, path, errors):
        if value is None:
            return None
        return self.inner.check(value, path, errors)

    def doc(self):
        return self.inner.doc() + " 或 null"


class List(Spec):
    def __init__(self, item, min_items=0, max_items=None, unique=False):
        self.item = item
        self.min_items = min_items
        self.max_items = max_items
        self.unique = unique

    def check(self, value, path, errors):
        if not isinstance(value, list):
            return self._type_error(value, path, errors, "数组")
        if len(value) < self.min_items:
            errors.append(detail(path, "至少需要 %d 项，实际 %d 项" % (self.min_items, len(value)), None, INVALID_INPUT))
            return MISSING
        if self.max_items is not None and len(value) > self.max_items:
            errors.append(detail(path, "最多 %d 项，实际 %d 项" % (self.max_items, len(value)), None, INVALID_INPUT))
            return MISSING
        out = []
        bad = False
        for index, item in enumerate(value):
            checked = self.item.check(item, "%s[%d]" % (path, index), errors)
            if checked is MISSING:
                bad = True
            out.append(checked)
        if bad:
            return MISSING
        if self.unique:
            seen = set()
            for index, item in enumerate(out):
                key = repr(item)
                if key in seen:
                    errors.append(detail("%s[%d]" % (path, index), "重复项：%s" % str(item)[:40], "删掉重复的一项", INVALID_INPUT))
                    return MISSING
                seen.add(key)
        return out

    def doc(self):
        bounds = ""
        if self.max_items is not None:
            bounds = "，%d–%d 项" % (self.min_items, self.max_items)
        elif self.min_items:
            bounds = "，≥%d 项" % self.min_items
        return "数组（%s%s）" % (self.item.doc(), bounds)


class Field:
    def __init__(self, spec, required=True, default=MISSING, desc=""):
        self.spec = spec
        self.required = required and default is MISSING
        self.default = default
        self.desc = desc


class Obj(Spec):
    def __init__(self, fields, desc="", name=None):
        self.fields = fields
        self.desc = desc
        self.name = name

    def check(self, value, path, errors):
        if not isinstance(value, dict):
            return self._type_error(value, path, errors, "对象")
        out = {}
        bad = False
        for key in value:
            if key not in self.fields:
                errors.append(detail("%s.%s" % (path, key), "未知字段：%s" % key, "可用字段：%s" % "、".join(self.fields), INVALID_INPUT))
                bad = True
        for key, field in self.fields.items():
            if key not in value:
                if field.required:
                    errors.append(detail("%s.%s" % (path, key), "缺少必填字段", field.desc or None, INVALID_INPUT))
                    bad = True
                elif field.default is not MISSING:
                    out[key] = _fresh(field.default)
                continue
            checked = field.spec.check(value[key], "%s.%s" % (path, key), errors)
            if checked is MISSING:
                bad = True
            else:
                out[key] = checked
        return MISSING if bad else out

    def doc(self):
        return "对象" if not self.name else "对象（%s）" % self.name


class Tagged(Spec):
    """An object whose shape is chosen by a discriminator field (e.g. `op`)."""

    def __init__(self, key, variants, name="操作"):
        self.key = key
        self.variants = variants
        self.name = name

    def check(self, value, path, errors):
        if not isinstance(value, dict):
            return self._type_error(value, path, errors, "对象")
        tag = value.get(self.key)
        if tag not in self.variants:
            errors.append(
                detail("%s.%s" % (path, self.key), "未知%s：%r" % (self.name, tag), "可用：%s" % "、".join(self.variants), INVALID_INPUT)
            )
            return MISSING
        return self.variants[tag].check(value, path, errors)

    def doc(self):
        return "%s对象（按 `%s` 区分）" % (self.name, self.key)


def _fresh(default):
    if isinstance(default, (list, dict)):
        import copy

        return copy.deepcopy(default)
    return default


def validate(spec, value, path="$"):
    """Return (normalized value or None, errors)."""
    errors = []
    out = spec.check(value, path, errors)
    if out is MISSING:
        return None, errors or [detail(path, "输入不合法", None, INVALID_INPUT)]
    return out, errors


ID_PATTERN = r"[a-z0-9_]{1,40}"
ID_HINT = "ASCII 小写短标识 [a-z0-9_]{1,40}"
REQUEST_ID_PATTERN = r"[A-Za-z0-9_-]{8,64}"
REQUEST_ID_HINT = "8–64 位 [A-Za-z0-9_-]；直接用上一次返回的 next_request_id"


def Id():
    return Str(1, 40, ID_PATTERN, ID_HINT)


def RequestId():
    return Str(8, 64, REQUEST_ID_PATTERN, REQUEST_ID_HINT)


EMPTY = Obj({}, "此命令不需要输入")
