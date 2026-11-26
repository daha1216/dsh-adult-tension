"""Placeholder rendering and gendered-pronoun checks (DESIGN_DECISIONS.md D15)."""

import re

PLACEHOLDER_RE = re.compile(r"\{([a-z0-9_]+)\.([a-z_一-鿿]+)\}|\{(family|given|given_last)\}")
ANY_BRACE_RE = re.compile(r"\{[^{}]*\}")

ATTRS = {"name", "ta", "family", "given", "call", "role", "title", "称呼"}
PRONOUN = {"female": "她", "male": "他", "nonbinary": "TA"}

# Compounds where 他 is not a pronoun for a specific person.
TA_COMPOUNDS = ("其他", "他人", "他乡", "他处", "他日", "他国", "他物", "吉他", "他方", "利他", "排他", "他们", "他杀", "无他", "他念")


# Address terms that tell a person's gender ("{family}先生"): a title or
# nickname pattern holding one must say whose gender it is for.
MALE_ADDRESS = ("先生", "少爷", "公子", "老爷", "相公", "王子", "少帅", "大少", "阔少", "哥", "兄", "郎", "爷", "叔", "伯", "男")
FEMALE_ADDRESS = ("小姐", "夫人", "太太", "女士", "姑娘", "公主", "千金", "名媛", "影后", "长媳", "遗孀", "未亡人", "娘", "姐", "妹", "嫂", "婶", "姨", "女")
# compounds that hold one of those characters without a gender
NEUTRAL_ADDRESS = ("郎中",)


def address_gender(text):
    """"male" / "female" / "mixed" for a text holding gendered address terms, else None."""
    for neutral in NEUTRAL_ADDRESS:
        text = text.replace(neutral, "")
    male = any(term in text for term in MALE_ADDRESS)
    female = any(term in text for term in FEMALE_ADDRESS)
    return "mixed" if male and female else "male" if male else "female" if female else None


def pronoun(gender):
    return PRONOUN.get(gender, "TA")


def gendered_pronoun_positions(text):
    """Indexes of hard-coded 他/她 that refer to a person."""
    hits = []
    if "她" not in text and "他" not in text:
        return hits
    for index, char in enumerate(text):
        if char == "她":
            hits.append(index)
        elif char == "他":
            window = text[max(0, index - 1) : index + 2]
            if not any(compound in window for compound in TA_COMPOUNDS):
                hits.append(index)
    return hits


def placeholders(text):
    """Yield (scope, attr) for {scope.attr}; (None, name) for {family}-style."""
    for match in PLACEHOLDER_RE.finditer(text):
        if match.group(3):
            yield None, match.group(3)
        else:
            yield match.group(1), match.group(2)


def stray_braces(text):
    """Brace groups that are not valid placeholders (typos like {npc.nmae})."""
    valid = {m.group(0) for m in PLACEHOLDER_RE.finditer(text)}
    return [m.group(0) for m in ANY_BRACE_RE.finditer(text) if m.group(0) not in valid]


def binding(character):
    """The attribute map a placeholder scope resolves to."""
    return {
        "name": character.get("name") or "",
        "ta": pronoun(character.get("gender")),
        "family": character.get("family") or "",
        "given": character.get("given") or "",
        "call": character.get("call") or character.get("name") or "",
        "称呼": character.get("call") or character.get("name") or "",
        "role": character.get("public_role") or character.get("role") or "",
        "title": character.get("title") or character.get("call") or character.get("name") or "",
    }


def render(text, scopes, names=None):
    """Render placeholders. `scopes` maps scope -> attribute dict (see binding)."""
    names = names or {}

    def repl(match):
        if match.group(3):
            return names.get(match.group(3), match.group(0))
        scope, attr = match.group(1), match.group(2)
        values = scopes.get(scope)
        if values is None or attr not in values:
            return match.group(0)
        return values[attr]

    return PLACEHOLDER_RE.sub(repl, text)


def render_name_pattern(pattern, family, given):
    return render(pattern, {}, {"family": family, "given": given, "given_last": given[-1:] if given else ""})


def full_name(pools, family, given):
    """A full name in the world's name order (name_pools.order)."""
    if pools.get("order") == "given_first":
        return "·".join(p for p in (given, family) if p)
    return (family or "") + (given or "")


def split_name(pools, name):
    """(family, given) of a full name; family is None when no pool family fits."""
    if pools.get("order") == "given_first":
        given, sep, family = name.rpartition("·")
        if sep and given and family in pools["family"]:
            return family, given
        return None, name
    family = next((f for f in sorted(pools["family"], key=len, reverse=True) if name.startswith(f)), None)
    return family, name[len(family) :] if family else name
