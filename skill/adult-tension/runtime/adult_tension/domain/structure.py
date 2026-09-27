"""The generic structure layer (DESIGN_DECISIONS.md D16).

Only structure lives here: stage tables, response spectrum, power structures,
twist categories, enums. No text tied to an era, place, trade or title; every
display string here must pass every world's forbidden-term scan.
"""

# Relationship stages (NARRATIVE_RULES.md section 6). Worlds may relabel them.
STAGES = ("stranger", "acquainted", "familiar", "flirting", "testing", "intimate", "committed")
STAGE_LABELS = {
    "stranger": "陌生",
    "acquainted": "认识",
    "familiar": "熟络",
    "flirting": "暧昧",
    "testing": "试探",
    "intimate": "亲密",
    "committed": "稳定",
}

TRUST_RANGE = (-5, 5)
TENSION_RANGE = (0, 5)
MAX_TRUST_DELTA = 2  # per commit, per directed edge (default value table)

# NPC response spectrum (NARRATIVE_RULES.md section 3)
RESPONSES = ("refuse", "negotiate", "partial", "surface", "genuine")
RESPONSE_LABELS = {
    "refuse": "拒绝",
    "negotiate": "协商",
    "partial": "有限配合",
    "surface": "表面配合",
    "genuine": "真诚配合",
}
COOPERATIVE_RESPONSES = ("partial", "genuine")

ACTION_MODES = ("result", "attempt", "rewrite", "continue", "wait")
POWER_STRUCTURES = ("player_high", "npc_high", "equal", "switchable")
SOCIAL_POSITIONS = ("low", "equal", "high")
TWIST_CATEGORIES = ("信息", "人事", "资源", "制度", "时限", "关系", "意外")
HOOK_KINDS = ("approach", "observe", "request", "accident")
BACKGROUND_FUNCTIONS = ("witness", "messenger", "obstacle", "rumor_source", "helper")
CHANNEL_FIDELITY = ("exact", "distorted")
PRIVACY = ("public", "semi", "private")
PRESSURE_SOURCES = ("institution", "person", "nature", "money", "rumor", "accident")
PRESSURE_FLAGS = ("timed", "leverage")
GENDERS = ("female", "male", "nonbinary")
TEMPLATE_GENDERS = ("any",) + GENDERS
NPC_GENDER_PREFERENCES = ("any", "mostly_female", "mostly_male", "female_only", "male_only", "mixed")
PERSONS = ("second", "first", "third")
TIERS = ("background", "supporting", "major")
PACES = ("slow", "standard", "direct")
EXPLICITNESS = ("subtle", "standard", "explicit")

FACT_VISIBILITY = ("public", "private", "inner")
FACT_ORIGINS = ("setup", "observed", "told", "retcon", "offscreen", "rumor")
MODEL_FACT_ORIGINS = ("observed", "told", "retcon")  # setup/offscreen/rumor come from the engine or dedicated ops

EVENT_KINDS = ("promise", "deadline", "rumor", "opportunity", "foreshadow", "chance")
EVENT_TIERS = ("immediate", "near", "far")
EVENT_STATES = ("pending", "resolved", "cancelled")
# What happens when a pending event reaches its due time without being resolved.
DUE_OUTCOME = {
    "promise": "expired",
    "deadline": "expired",
    "opportunity": "expired",
    "foreshadow": "surfaced",
    "rumor": "surfaced",
}
MANUAL_OUTCOMES = {
    "promise": ("fulfilled",),
    "deadline": ("fulfilled",),
    "opportunity": ("fulfilled",),
    "foreshadow": ("surfaced",),
    "rumor": ("surfaced",),
    "chance": (),
}

CONDITION_KINDS = ("drunk", "asleep", "unconscious", "injured", "away", "busy", "other")
# Characters in these conditions never take part in intimate scenes.
INCAPACITATING = ("drunk", "asleep", "unconscious")

# Clock anchors for advance_time.until (minutes of day)
UNTIL_ANCHORS = {"morning": 7 * 60, "noon": 12 * 60, "evening": 18 * 60, "night": 21 * 60}
MINUTES_PER_DAY = 1440
MAX_ADVANCE_MINUTES = 30 * MINUTES_PER_DAY
DEFAULT_ADVANCE_MINUTES = 3
SCENE_BREAK_MINUTES = 60

COOLDOWN_TURNS = 3
MAX_FIX_ATTEMPTS = 2

# Content minimums (CONTENT_BIBLE.md sections 3 and 5)
FULL_MINIMUMS = {
    "rules": 4,
    "customs": 4,
    "family": 12,
    "given_female": 12,
    "given_male": 12,
    "given_neutral": 12,
    "nickname_patterns": 2,
    "player_identities": 4,
    "locations": 3,
    "character_templates": 6,
    "background_cast": 6,
    "background_functions": 3,
    "channels": 2,
    "tension_engines": 4,
    "cast_combos": 4,
    "daily_activities": 6,
    "pressures": 6,
    "hooks": 4,
    "twists": 6,
    "twist_categories": 4,
}
CUSTOM_MINIMUMS = {
    "rules": 2,
    "customs": 0,
    "family": 4,
    "given_female": 0,
    "given_male": 0,
    "given_neutral": 0,
    "given_total": 4,
    "nickname_patterns": 0,
    "player_identities": 1,
    "locations": 2,
    "character_templates": 3,
    "background_cast": 0,
    "background_functions": 0,
    "channels": 0,
    "tension_engines": 1,
    "cast_combos": 1,
    "daily_activities": 0,
    "pressures": 0,
    "mode_items": 2,
    "hooks": 1,
    "twists": 0,
    "twist_categories": 0,
}

# Content tags that "pause" blocks besides intimacy tags (RUNTIME_PROTOCOL.md section 10).
INTIMACY_TAGS = ("romance_light", "intimate", "explicit")
STRUCTURAL_INTIMACY_TAGS = ("intimate", "explicit")
CONFLICT_TAGS = ("violence", "coercion_theme", "humiliation", "bodily_harm")


def generic_strings():
    """Every display string of the generic layer, for the cross-world scan."""
    out = list(STAGE_LABELS.values()) + list(RESPONSE_LABELS.values()) + list(TWIST_CATEGORIES)
    return out
