"""The in-game clock: {"day": N, "minute": 0..1439}. Time never flows back."""

from .structure import MINUTES_PER_DAY, UNTIL_ANCHORS

CN_DIGITS = "零一二三四五六七八九"
SHICHEN = ("子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥")


def to_abs(clock):
    return (clock["day"] - 1) * MINUTES_PER_DAY + clock["minute"]


def from_abs(total):
    return {"day": total // MINUTES_PER_DAY + 1, "minute": total % MINUTES_PER_DAY}


def add_minutes(clock, minutes):
    return from_abs(to_abs(clock) + minutes)


def until_target(clock, anchor):
    """Minutes from `clock` to the next occurrence of an anchor (strictly later)."""
    now = to_abs(clock)
    if anchor == "next_morning":
        target = clock["day"] * MINUTES_PER_DAY + UNTIL_ANCHORS["morning"]
        return target - now
    minute = UNTIL_ANCHORS[anchor]
    target = (clock["day"] - 1) * MINUTES_PER_DAY + minute
    if target <= now:
        target += MINUTES_PER_DAY
    return target - now


def cn_number(value):
    """Chinese numerals for day counts (1..9999)."""
    if value < 10:
        return CN_DIGITS[value]
    if value < 20:
        return "十" + (CN_DIGITS[value - 10] if value > 10 else "")
    if value < 100:
        tens, ones = divmod(value, 10)
        return CN_DIGITS[tens] + "十" + (CN_DIGITS[ones] if ones else "")
    return str(value)


def day_label(day):
    return "第%s天" % cn_number(day)


def hm(minute):
    return "%02d:%02d" % divmod(minute, 60)


def shichen(minute):
    # 子时 is 23:00-01:00; each 时辰 spans two hours.
    index = ((minute + 60) // 120) % 12
    return SHICHEN[index] + "时"


def label(clock, style="hm"):
    text = "%s %s" % (day_label(clock["day"]), hm(clock["minute"]))
    if style == "shichen":
        text = "%s %s（%s）" % (day_label(clock["day"]), shichen(clock["minute"]), hm(clock["minute"]))
    return text


def minutes_between(a, b):
    return to_abs(b) - to_abs(a)


def compare(a, b):
    return (to_abs(a) > to_abs(b)) - (to_abs(a) < to_abs(b))
