"""Placeholder rendering and gendered-pronoun checks (DESIGN_DECISIONS.md D15)."""

import re

PLACEHOLDER_RE = re.compile(r"\{([a-z0-9_]+)\.([a-z_一-鿿]+)\}|\{(family|given|given_last)\}")
ANY_BRACE_RE = re.compile(r"\{[^{}]*\}")

ATTRS = {"name", "ta", "family", "given", "call", "role", "title", "称呼"}
PRONOUN = {"female": "她", "male": "他", "nonbinary": "TA"}

# Compounds where 他 is not a pronoun for a specific person.
TA_COMPOUNDS = ("其他", "他人", "他乡", "他处", "他日", "他国", "他物", "吉他", "他方", "利他", "排他", "他们", "他杀", "无他", "他念")


def pronoun(gender):
    return PRONOUN.get(gender, "TA")


def gendered_pronoun_positions(text):
    """Indexes of hard-coded 他/她 that refer to a person."""
    hits = []
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
        "name": character.get("name", ""),
        "ta": pronoun(character.get("gender")),
        "family": character.get("family", ""),
        "given": character.get("given", ""),
        "call": character.get("call") or character.get("name", ""),
        "称呼": character.get("call") or character.get("name", ""),
        "role": character.get("public_role") or character.get("role", ""),
        "title": character.get("title") or character.get("call") or character.get("name", ""),
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
