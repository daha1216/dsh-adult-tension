"""Character card parts and what each tier requires (DATA_CONTRACTS.md 3).

background: name and one line;
supporting: + appearance, identity, decision.core_value/current_goal;
major:      + the full decision card, intimacy tendency, voices, situation.
`identity` and `intimacy` are created once (at introduction or promotion)
and afterwards only evolve item by item.
"""

from .. import schema as S
from . import structure as ST

F = S.Field


def _texts(min_items=1, hi=80):
    return S.List(S.Str(1, hi), min_items=min_items, max_items=8)


EXIT = S.Obj({"option": F(S.Str(1, 80)), "cost": F(S.Str(1, 120))})

IDENTITY = S.Obj(
    {
        "authority": F(S.Str(1, 120)),
        "resources": F(_texts()),
        "limits": F(_texts()),
        "obligations": F(_texts(0), required=False, default=[]),
        "exposure_risk": F(S.Str(1, 120)),
        "hidden_mismatch": F(S.Str(1, 120)),
    },
    name="身份",
)

PRESSURE_RESPONSES = S.Obj({level: F(S.Str(1, 120)) for level in ("low", "mid", "high", "breaking")}, name="压力反应四档")

DECISION = S.Obj(
    {
        "core_value": F(S.Str(1, 60), required=False),
        "current_goal": F(S.Str(1, 80), required=False),
        "pressure_responses": F(PRESSURE_RESPONSES, required=False),
        "withdrawal": F(S.Str(1, 120), required=False),
        "relationship_stance": F(S.Str(1, 80), required=False),
        "contrast": F(S.Str(1, 80), required=False),
        "prefers": F(_texts(), required=False),
        "avoids": F(_texts(), required=False),
        "never": F(_texts(), required=False),
    },
    name="决策卡",
)
SUPPORTING_DECISION_KEYS = ("core_value", "current_goal")
MAJOR_DECISION_KEYS = (
    "core_value",
    "current_goal",
    "pressure_responses",
    "withdrawal",
    "relationship_stance",
    "contrast",
    "prefers",
    "avoids",
    "never",
)

INTIMACY = S.Obj(
    {
        "desire_level": F(S.Int(0, 5)),
        "attraction_sources": F(_texts(2)),
        "likes": F(_texts()),
        "dislikes": F(_texts()),
        "preconditions": F(_texts()),
        "boundaries": F(_texts()),
        "expression": F(S.Str(1, 80)),
        "self_control": F(S.Int(0, 5)),
        "desired_position": F(S.Str(1, 40)),
    },
    name="私密倾向卡",
)
INTIMACY_NUMERIC = ("desire_level", "self_control")
INTIMACY_LISTS = ("attraction_sources", "likes", "dislikes", "preconditions", "boundaries")
INTIMACY_TEXT = ("expression", "desired_position")

VOICES = S.Obj({"surface": F(S.Str(1, 120)), "inner": F(S.Str(1, 120))}, name="语态")
SITUATION = S.Obj(
    {
        "trigger": F(S.Str(1, 120)),
        "pressure": F(S.Str(1, 120)),
        "exits": F(S.List(EXIT, min_items=2, max_items=4)),
    },
    name="处境",
)
SCHEDULE = S.List(S.Obj({"from": F(S.Int(0, 1439)), "to": F(S.Int(0, 1439)), "location_id": F(S.Id())}), max_items=6)

IDENTITY_ITEMS = ("authority", "resources", "limits", "obligations", "exposure_risk", "hidden_mismatch")
IDENTITY_LISTS = ("resources", "limits", "obligations")

TIER_ORDER = {tier: index for index, tier in enumerate(ST.TIERS)}


def card_fields():
    """Optional card parts, shared by introduce_character and promote_character."""
    return {
        "appearance": F(S.Nullable(S.Str(1, 120)), required=False, default=None),
        "line": F(S.Nullable(S.Str(1, 120)), required=False, default=None),
        "identity": F(S.Nullable(IDENTITY), required=False, default=None),
        "decision": F(S.Nullable(DECISION), required=False, default=None),
        "intimacy": F(S.Nullable(INTIMACY), required=False, default=None),
        "voices": F(S.Nullable(VOICES), required=False, default=None),
        "situation": F(S.Nullable(SITUATION), required=False, default=None),
        "schedule": F(S.Nullable(SCHEDULE), required=False, default=None),
    }


def missing_for_tier(tier, card):
    """Names of the fields a card of this tier still lacks."""
    missing = []
    if tier == "background":
        if not card.get("line"):
            missing.append("line")
        return missing
    if not card.get("appearance"):
        missing.append("appearance")
    if not card.get("identity"):
        missing.append("identity")
    decision = card.get("decision") or {}
    keys = SUPPORTING_DECISION_KEYS if tier == "supporting" else MAJOR_DECISION_KEYS
    missing.extend("decision.%s" % key for key in keys if key not in decision)
    if tier == "major":
        for part in ("intimacy", "voices", "situation"):
            if not card.get(part):
                missing.append(part)
    return missing
