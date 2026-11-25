"""Context projections for the model (DATA_CONTRACTS.md section 7).

Pure functions of (state, content, save info). Lists are bounded so the
brief context stays <= 6 KB and the full context <= 32 KB (UTF-8 JSON) no
matter how long the game runs or how many people a world puts on stage.
The brief context trims lists in a fixed order. The full context degrades
detail step by step (_full_steps), least relevant first, and never drops a
section the contract names: every major or supporting NPC keeps at least a
summary card, every pending event and active leverage, every world rule and
location, the latest chapter and a name pool to draw new names from. Only a
game that piled up leverage, after every other step, has the leverage that
touches no one on stage cut and counted (leverage_omitted).
"""

import json

from ..domain import clock as CL
from ..domain import facts as FA
from ..domain import opening
from ..domain import simulation
from ..domain import state as SS
from ..domain.text import binding, render
from ..domain.turn import chapter_start

BRIEF_LIMIT = 6 * 1024
FULL_LIMIT = 32 * 1024
# size_bytes is added after fitting; its own bytes count toward the limit.
SIZE_FIELD_RESERVE = 24
LIMITS = {"due_soon": 10, "known_facts": 8, "recent": 3, "nearby": 5}


def size_of(obj):
    return len(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _clock(state, world):
    return {"day": state["clock"]["day"], "minute": state["clock"]["minute"], "label": CL.label(state["clock"], world.get("clock_style", "hm"))}


def _npc_brief(state, world, cid):
    char = state["characters"][cid]
    player = state["player_id"]
    to_player = SS.edge(state, cid, player) or {}
    entry = {
        "id": cid,
        "name": char["name"],
        "age": char["age"],
        "gender": char["gender"],
        "tier": char["tier"],
        "role": char["public_role"],
        "mood": char["status"]["mood"],
        "voice": _voice(state, cid),
        "can_act": SS.can_act(state, cid),
        "trust_to_player": to_player.get("trust", 0),
        "tension": to_player.get("tension", 0),
        "stage": SS.stage_label(world, to_player.get("stage", "stranger")),
    }
    if char["status"]["conditions"]:
        entry["conditions"] = [c["text"] for c in char["status"]["conditions"]]
    decision = char.get("decision")
    if decision:
        entry["goal"] = decision["current_goal"]
        entry["stance"] = decision["relationship_stance"]
    if char["tier"] == "background":
        entry["line"] = char.get("line")
    return entry


def player_facts(state, limit=None):
    """The player's facts, most relevant first (facts.player_score): about
    someone present, or recent. Storage answers this without reading every fact."""
    player = state["player_id"]
    present_ids = sorted(set(state["scene"]["present"]) - {player})
    present_names = [state["characters"][c]["name"] for c in present_ids]
    facts = FA.of(state).player_ranked(player, present_ids, present_names, state["turn"] - FA.RECENT_TURNS, limit)
    out = []
    for fact in facts:
        item = {"id": fact["id"], "text": fact["text"], "visibility": fact["visibility"]}
        if not fact["truth"]:
            item["believed_not_true"] = True
        out.append(item)
    return out


def _events(state, world, limit=None):
    pending = [e for e in state["events"].values() if e["state"] == "pending"]
    pending.sort(key=lambda e: (CL.to_abs(e["due"]), e["id"]))
    now = CL.to_abs(state["clock"])
    out = []
    for event in pending[:limit] if limit else pending:
        item = {
            "id": event["id"],
            "kind": event["kind"],
            "title": event["title"],
            "in_minutes": CL.to_abs(event["due"]) - now,
            "due_label": CL.label(event["due"], world.get("clock_style", "hm")),
        }
        if SS.player_involved(state, event):
            item["involves_player"] = True
        out.append(item)
    return out


def _leverage(state, only_present=False):
    """Active leverage touching someone on stage, then (unless only_present)
    the rest: the brief list is the head of the full one."""
    present = set(state["scene"]["present"])
    out, rest = [], []
    for lv in SS.active_leverage(state):
        item = {"id": lv["id"], "holder": lv["holder"], "subject": lv["subject"], "basis_fact_id": lv["basis_fact_id"]}
        if {lv["holder"], lv["subject"]} & present:
            out.append(item)
        elif not only_present:
            rest.append(item)
    return out + rest


def _voice(state, cid):
    value = state["preferences"]["voice"].get(cid)
    if isinstance(value, dict):
        return value.get("voice", "surface")
    return value or "surface"


def brief(state, content, save=None):
    world = content["world"]
    player = state["player_id"]
    pchar = state["characters"][player]
    scene = state["scene"]
    location = SS.location(world, scene["location_id"])
    present_npcs = [_npc_brief(state, world, cid) for cid in scene["present"] if cid != player]
    nearby = [
        {"id": cid, "name": char["name"], "role": char["public_role"]}
        for cid, char in sorted(state["characters"].items())
        if cid not in scene["present"] and char["status"]["location_id"] == scene["location_id"]
    ][: LIMITS["nearby"]]
    context = {
        "depth": "brief",
        "session_id": state["session_id"],
        "revision": state["revision"],
        "turn": state["turn"],
        "mode": state["mode"],
        "clock": _clock(state, world),
        "scene": {
            "id": scene["id"],
            "location_id": scene["location_id"],
            "location": location["name"] if location else scene["location_id"],
            "privacy": location["privacy"] if location else None,
            "present": list(scene["present"]),
        },
        "player": {
            "name": pchar["name"],
            "title": pchar["title"],
            "age": pchar["age"],
            "gender": pchar["gender"],
            "role": pchar["public_role"],
        },
        "present_npcs": present_npcs,
        "nearby": nearby,
        "due_soon": _events(state, world, LIMITS["due_soon"]),
        "known_facts": player_facts(state, LIMITS["known_facts"]),
        "recent": [t["summary"] for t in state["memory"]["turns"][-LIMITS["recent"] :]],
        "last_quotes": list(state["memory"]["last_quotes"]),
        "open_action": state["memory"]["open_action"],
        "scene_responses": [{"npc_id": r["npc_id"], "response": r["response"]} for r in scene["responses"][-3:]],
        "safety": {
            "paused": state["safety"]["paused"],
            "boundaries": [b["text"] for b in state["safety"]["boundaries"]],
            "leverage": _leverage(state, only_present=True),
        },
        "preferences": {
            "inner_view": state["preferences"]["inner_view"],
            "assistant": state["preferences"]["assistant"],
            "offscreen_simulation": state["preferences"]["offscreen_simulation"],
            "person": state["preferences"]["person"],
            "npc_gender_preference": state["preferences"]["npc_gender_preference"],
        },
        "save": save or {"current_slot": None, "turns_since_save": 0},
        "requests": dict(state["requests"]),
    }
    # Style preferences appear only when the player changed them: absent means standard.
    for key in ("pace", "explicitness"):
        if state["preferences"][key] != "standard":
            context["preferences"][key] = state["preferences"][key]
    chapters = state["memory"]["chapters"]
    if chapters and len(context["recent"]) < LIMITS["recent"]:
        # Right after a chapter closes its turns are archived; the chapter
        # summary keeps the thread until new turn summaries accumulate.
        context["last_chapter"] = chapters[-1]["summary"]
    _fit(context, BRIEF_LIMIT, ("known_facts", "due_soon", "nearby", "scene_responses", "recent", "last_quotes"))
    return context


def _card(state, world, char):
    cid = char["id"]
    player = state["player_id"]
    card = {
        "id": cid,
        "name": char["name"],
        "call": char.get("call"),
        "age": char["age"],
        "gender": char["gender"],
        "tier": char["tier"],
        "role": char["public_role"],
        "adult_context": char["adult_context"],
        "location_id": char["status"]["location_id"],
        "present": cid in state["scene"]["present"],
        "can_act": SS.can_act(state, cid),
        "voice": _voice(state, cid),
    }
    for key in ("appearance", "voices"):
        if char.get(key):
            card[key] = char[key]
    if char.get("identity"):
        card["identity"] = char["identity"]
    if char.get("situation"):
        card["situation"] = char["situation"]
    if char.get("decision"):
        d = char["decision"]
        card["decision"] = {
            k: d[k]
            for k in ("core_value", "current_goal", "pressure_responses", "withdrawal", "relationship_stance", "contrast", "prefers", "avoids", "never")
            if k in d
        }
    if char.get("intimacy"):
        card["intimacy"] = char["intimacy"]
    edge = SS.edge(state, cid, player)
    if edge:
        card["to_player"] = {"trust": edge["trust"], "tension": edge["tension"], "stage": SS.stage_label(world, edge["stage"])}
    return card


def full(state, content, save=None):
    world = content["world"]
    context = brief(state, content, save)
    context["depth"] = "full"
    player = state["player_id"]
    pchar = state["characters"][player]
    context["player"].update(
        {
            "social_position": pchar.get("social_position"),
            "baseline": pchar.get("baseline"),
            "resources": pchar.get("resources"),
            "reputation": pchar.get("reputation"),
            "risks": pchar.get("risks"),
            "background": pchar.get("background"),
        }
    )
    context["world"] = {
        "title": world["title"],
        "era": world["era"],
        "region": world["region"],
        "premise": world["premise"],
        "tone": world["tone"],
        "style_hint": world["style_hint"],
        "rules": [r["text"] for r in world["rules"]],
        "customs": list(world["customs"]),
    }
    if world.get("stage_labels"):
        context["world"]["stage_labels"] = world["stage_labels"]
    standby = opening.standby_previews(state, world)
    if world.get("daily_activities"):
        here_id = state["scene"]["location_id"]
        private_ids = {loc["id"] for loc in world.get("locations", []) if loc.get("privacy") == "private"}
        scopes = {cid: binding(c) for cid, c in state["characters"].items()}
        for sid, p in standby.items():
            scopes.setdefault(sid, binding(p))
        scopes["player"] = dict(binding(pchar), title=pchar.get("title") or pchar.get("call") or pchar["name"])
        acts = sorted(
            world["daily_activities"],
            key=lambda a: (here_id not in a.get("location_ids", []), not (set(a.get("location_ids", [])) & private_ids), a["id"]),
        )
        context["world"]["scene_ideas"] = [
            "%s：%s" % (a["title"], render(a["beats"][0], scopes))
            for a in acts[:6]
            if a.get("beats")
        ]
    context["locations"] = [
        {"id": loc["id"], "name": loc["name"], "privacy": loc["privacy"], "detail": loc["detail"], "affordances": loc["affordances"], "exits": loc["exits"]}
        for loc in world["locations"]
    ]
    majors = [c for c in state["characters"].values() if c["id"] != player and c["tier"] in ("major", "supporting")]
    majors.sort(key=lambda c: (c["id"] not in state["scene"]["present"], c["id"]))
    context["characters"] = [_card(state, world, c) for c in majors]
    if standby:
        context["standby_cast"] = [
            {"id": sid, "name": p["name"], "age": p["age"], "gender": p["gender"], "role": p["public_role"], "location_id": p["location_id"]}
            for sid, p in sorted(standby.items())
        ]
    context["background"] = [
        {"id": c["id"], "name": c["name"], "role": c["public_role"], "line": c.get("line"), "location_id": c["status"]["location_id"]}
        for c in sorted(state["characters"].values(), key=lambda c: c["id"])
        if c["tier"] == "background"
    ]
    relevant = {player} | {c["id"] for c in majors}
    context["relationships"] = [
        {
            "from": e["from"],
            "to": e["to"],
            "trust": e["trust"],
            "tension": e["tension"],
            "stage": SS.stage_label(world, e["stage"]),
            "recent": [h["reason"] for h in e["history"][-2:]],
        }
        for key, e in sorted(state["relationships"].items())
        if e["from"] in relevant and e["to"] in relevant
    ]
    # The brief lists are the head of these full lists; carrying both would
    # only repeat them.
    context.pop("known_facts", None)
    context.pop("due_soon", None)
    context["safety"].pop("leverage", None)
    context["player_facts"] = player_facts(state, 30)
    context["events"] = _events(state, world)
    context["leverage_all"] = _leverage(state)
    if state.get("pressure"):
        context["pressure"] = state["pressure"]
    context["chapters"] = [c["summary"] for c in state["memory"]["chapters"][-3:]]
    context.pop("last_chapter", None)
    if state["memory"].get("prologue"):
        context["prologue"] = state["memory"]["prologue"]
    if state["requests"].get("prologue"):
        context["prologue_merge"] = simulation.prologue_source(state)
    context["tags"] = [t["id"] for t in content["tags"]]
    pools = world["name_pools"]
    used = {c.get("family") for c in state["characters"].values()}
    context["name_pool"] = {
        "family_unused": [f for f in pools["family"] if f not in used][:12],
        "given_female": pools["given_female"][:12],
        "given_male": pools["given_male"][:12],
        "given_neutral": pools["given_neutral"][:8],
    }
    if pools.get("order") == "given_first":
        context["name_pool"]["order"] = "名在前、姓在后，中间用“·”"
    _fit_full(context, state)
    return context


# -- commit template -----------------------------------------------------------


def commit_template(state):
    """A commit-turn input to fill in, returned when a session starts (new
    game, load, import): the session filled in, the person on stage first,
    and the operations most turns need, so the first turn needs no reading
    of operations.md. Angle brackets mark what to write; "a|b" means pick
    one. It sits beside the context and does not count toward its budget."""
    player = state["player_id"]
    present = [cid for cid in state["scene"]["present"] if cid != player]
    npc = present[0] if present else "<npc_id>"
    return _template(
        state,
        {
            "action_mode": "attempt|result|continue|wait",
            "player_input": "<玩家原话>",
            "player_authorized": False,
            "acts_on": [npc],
            "operations": [
                {"op": "npc_response", "npc_id": npc, "response": "refuse|negotiate|partial|surface|genuine", "note": "<怎么回应，≤80 字；surface 另写 true_intent>"},
                {"op": "npc_action", "npc_id": npc, "action": "<这个 NPC 自己做了什么>"},
                {"op": "add_fact", "key": "<小写点分键，如 %s.secret.letter>" % (npc if present else "npc"), "text": "<正文里新写出、以后要用到的细节>", "visibility": "public", "origin": "observed"},
                {"op": "relationship", "from": npc, "to": player, "trust_delta": "<-2..2 的整数；关系没变就删掉这条>", "reason": "<为什么>"},
                {"op": "advance_time", "minutes": 5},
            ],
        },
    )


def skip_template(state, spec, preview):
    """The commit for a fast-forward, returned as skip_template beside
    get-context's preview: the time skip as previewed first, then one
    offscreen beat for each NPC the preview requires. A continue turn: the
    player only asked for time to pass."""
    player = state["player_id"]
    operations = [dict({"op": "advance_time"}, **spec)]
    for beat in preview["required_beats"]:
        cid = beat["npc_id"]
        operations.append(
            {
                "op": "offscreen_beat",
                "npc_id": cid,
                "summary": "<这段离屏一句话，≤120 字>",
                "operations": [{"op": "npc_action", "npc_id": cid, "action": "<按该角色的 goal 与 knows 写行动>"}],
            }
        )
    present = [cid for cid in state["scene"]["present"] if cid != player]
    if present:
        operations.append({"op": "npc_action", "npc_id": present[0], "action": "<在场的人这段时间后在做什么；用不上就删掉>"})
    return _template(state, {"action_mode": "continue", "player_input": "<玩家原话>", "acts_on": [], "operations": operations})


def _template(state, body):
    """A record (DATA_CONTRACTS 6.3) holding one turn: the model copies the
    turn once for each turn it has kept back."""
    turn = dict(body)
    turn["content_tags"] = []
    turn["summary"] = "<第三人称一两句>"
    turn["open_action"] = "<停在哪个未决动作>"
    turn["quotes"] = ["<本回合值得记住的原话，原样一句，≤80 字；没有就删掉这条>"]
    # what the engine asks of the first turn of the next record (the requests
    # a time skip raises come with the context the skip returns)
    if state["requests"].get("chapter_summary"):
        # the chapter closes where the request came, not where the model
        # gets round to writing it
        turn["chapter_summary"] = "<第 %d–%d 回合的第三人称摘要，不含后续事件，≤300 字>" % (chapter_start(state), state["turn"])
    if state["requests"].get("prologue"):
        turn["prologue"] = "<完整上下文 prologue_merge 合并成的前情，≤300 字>"
    return {
        "session_id": state["session_id"],
        "request_id": "<上一次返回的 next_request_id>",
        "expected_revision": "<上一次返回的 revision>",
        "encoding_check": "汉字",
        "turns": [turn],
    }


# -- full-context budget -------------------------------------------------------

CARD_SUMMARY_KEYS = ("id", "name", "call", "age", "gender", "tier", "role", "adult_context", "location_id", "present", "can_act", "voice", "to_player")
ROSTER_KEYS = ("id", "name", "tier", "role", "adult_context", "location_id", "present", "to_player")
ROSTER_CLIP = 24
NAME_POOL_FLOOR = {"family_unused": 6, "given_female": 4, "given_male": 4, "given_neutral": 3}
PLAYER_FACTS_FLOORS = (16, 8)
CUSTOMS_FLOOR = 2


def _card_summary(card):
    """An absent NPC: who, where, how they stand with the player, what they
    want and will never do, and their boundaries."""
    out = {k: card[k] for k in CARD_SUMMARY_KEYS if k in card}
    decision = {k: v for k, v in (card.get("decision") or {}).items() if k in ("core_value", "current_goal", "relationship_stance", "withdrawal", "never")}
    if decision:
        out["decision"] = decision
    intimacy = {k: v for k, v in (card.get("intimacy") or {}).items() if k in ("boundaries", "preconditions")}
    if intimacy:
        out["intimacy"] = intimacy
    out["detail"] = "summary"
    return out


def _card_compact(card):
    """A present NPC under budget pressure: keeps appearance and voices, plus
    decision with pressure responses, situation, intimacy numbers and boundaries."""
    out = dict(card)
    if "identity" in out:
        out["identity"] = {k: v for k, v in out["identity"].items() if k in ("authority", "resources", "exposure_risk", "hidden_mismatch")}
    if "decision" in out:
        out["decision"] = {k: v for k, v in out["decision"].items() if k not in ("prefers", "avoids", "contrast", "withdrawal")}
    if "intimacy" in out:
        out["intimacy"] = {k: v for k, v in out["intimacy"].items() if k not in ("dislikes", "attraction_sources")}
    out["detail"] = "compact"
    return out


def _card_core(card):
    """A person on stage in the tightest budget: a summary card plus pressure
    responses, what they will never do, boundaries and the present situation."""
    if card.get("detail") == "roster":
        return card
    out = _card_summary(card)
    decision = card.get("decision") or {}
    if "pressure_responses" in decision:
        out.setdefault("decision", {})["pressure_responses"] = decision["pressure_responses"]
    situation = card.get("situation") or {}
    if situation.get("trigger"):
        out["situation"] = {"trigger": situation["trigger"]}
    out["detail"] = "core"
    return out


def _roster_line(card):
    return dict({k: card[k] for k in ROSTER_KEYS if k in card}, detail="roster")


def _roster_clipped(card):
    """The last resort for a crowd of long cards: a roster line whose role and
    adult context are cut to their opening words."""
    if card.get("detail") not in ("roster", "core"):
        return card
    out = _roster_line(card)
    for key in ("role", "adult_context"):
        if isinstance(out.get(key), str) and len(out[key]) > ROSTER_CLIP:
            out[key] = out[key][:ROSTER_CLIP] + "…"
    return out


def _card_order(context, state, present):
    """Cards to shrink, least relevant first: anyone who has not just
    responded in this scene, supporting before major, those no pending event
    involves, then the weakest tie to the player."""
    in_events = set()
    for event in state["events"].values():
        if event["state"] == "pending":
            in_events.update(event["participants"])
    responded = {r["npc_id"] for r in state["scene"]["responses"][-3:]}

    def key(card):
        tie = card.get("to_player") or {}
        return (
            card["id"] in responded,
            card["tier"] == "major",
            card["id"] in in_events,
            abs(tie.get("trust", 0)) + tie.get("tension", 0),
            card["id"],
        )

    return [c["id"] for c in sorted(context["characters"], key=key) if bool(c.get("present")) == present]


def _drop_goal(context, cid):
    for npc in context.get("present_npcs", []):
        if npc["id"] == cid:
            npc.pop("goal", None)


def _replace_card(context, cid, shrink):
    context["characters"] = [shrink(c) if c["id"] == cid else c for c in context["characters"]]


def _full_steps(context, state):
    """Degradation steps in order; each makes the context smaller."""
    here = state["scene"]["location_id"]
    nearby = set()
    for loc in context["locations"]:
        if loc["id"] == here:
            nearby = set(loc.get("exits", []))

    def pop_to(key, floor, holder=None):
        def step():
            target = context if holder is None else context.get(holder, {})
            items = target.get(key)
            while isinstance(items, list) and len(items) > floor and size_of(context) > FULL_LIMIT - SIZE_FIELD_RESERVE:
                items.pop()
        return step

    def background_lines():
        for item in context["background"]:
            if item.get("location_id") != here:
                item.pop("line", None)

    def background_elsewhere():
        context["background"] = [b for b in context["background"] if b.get("location_id") == here]

    def far_locations(keep):
        def step():
            for loc in context["locations"]:
                if loc["id"] not in keep:
                    loc.pop("detail", None)
                    loc.pop("affordances", None)
        return step

    def one_reason():
        for edge in context["relationships"]:
            edge["recent"] = edge["recent"][-1:]

    def drop_nearby():
        # Who is next door is also in characters and background (location_id)
        # and in the locations' exits.
        context.pop("nearby", None)

    def background_sample_lines():
        for item in context["background"]:
            item.pop("line", None)

    def reasons_offstage():
        onstage = set(state["scene"]["present"])
        for edge in context["relationships"]:
            if not ({edge["from"], edge["to"]} & (onstage - {state["player_id"]})):
                edge.pop("recent", None)

    def present_npcs_carded():
        # Everyone on stage with a card already has name, role, voice, stance
        # and standing with the player there; the brief line keeps what the
        # card lacks (mood, conditions).
        carded = {c["id"] for c in context["characters"]}
        context["present_npcs"] = [
            {k: v for k, v in npc.items() if k in ("id", "mood", "conditions")} if npc["id"] in carded else npc
            for npc in context["present_npcs"]
        ]

    def leverage_offstage():
        # Who holds whom stays; what it rests on matters once one of them is here.
        onstage = set(state["scene"]["present"])
        for lv in context["leverage_all"]:
            if not ({lv["holder"], lv["subject"]} & onstage):
                lv.pop("basis_fact_id", None)

    def leverage_cut():
        onstage = set(state["scene"]["present"])
        items = context["leverage_all"]
        cut = 0
        while items and not ({items[-1]["holder"], items[-1]["subject"]} & onstage) and size_of(context) > FULL_LIMIT - SIZE_FIELD_RESERVE:
            items.pop()
            cut += 1
            context["leverage_omitted"] = {"count": cut, "hint": "另有 %d 条不涉及在场者的生效把柄没列出；需要时用 status（level: debug）看 state.leverage" % cut}

    def npc_edges():
        player = state["player_id"]
        context["relationships"] = [e for e in context["relationships"] if player in (e["from"], e["to"])]

    def edges_elsewhere():
        onstage = set(state["scene"]["present"])
        context["relationships"] = [e for e in context["relationships"] if e["from"] in onstage or e["to"] in onstage]

    def older_chapters():
        context["chapters"] = context["chapters"][-1:]

    def small_name_pool():
        pool = context["name_pool"]
        for key, floor in NAME_POOL_FLOOR.items():
            pool[key] = pool[key][:floor]

    def shrink_cards(present, shrink):
        return [lambda cid=cid: _replace_card(context, cid, shrink) for cid in _card_order(context, state, present)]

    def drop_standby_and_ideas():
        context.get("world", {}).pop("scene_ideas", None)
        context.pop("standby_cast", None)

    # Far from the scene.
    yield pop_to("scene_ideas", 2, holder="world")
    yield background_lines
    yield far_locations({here} | nearby)
    yield drop_standby_and_ideas
    yield from shrink_cards(False, _card_summary)
    yield background_elsewhere
    yield one_reason
    yield pop_to("player_facts", PLAYER_FACTS_FLOORS[0])
    yield older_chapters
    yield small_name_pool
    yield pop_to("customs", CUSTOMS_FLOOR, holder="world")
    yield pop_to("player_facts", PLAYER_FACTS_FLOORS[1])
    yield far_locations({here})
    # Absent people shrink to a roster line, then what the cards on stage
    # can do without goes: edges between absent people, nearby places,
    # sample lines, edges between NPCs, reasons off stage. Only then do the
    # people on stage lose flavour.
    yield from shrink_cards(False, _roster_line)
    yield edges_elsewhere
    yield drop_nearby
    yield background_sample_lines
    yield npc_edges
    yield reasons_offstage
    yield leverage_offstage
    yield present_npcs_carded
    yield from shrink_cards(True, _card_compact)
    # A crowded scene: everyone on stage but the most relevant person keeps
    # a summary, then a roster line.
    crowd = _card_order(context, state, True)[:-1]
    for shrink in (_card_summary, _roster_line):
        for cid in crowd:
            yield lambda cid=cid, shrink=shrink: _replace_card(context, cid, shrink)
    # Still too big (long world texts and many important people): goals of
    # the crowd go, then detail.
    # The people on stage keep what the next beat needs: decision with
    # pressure responses, boundaries, and their stance and mood.
    for cid in crowd:
        yield lambda cid=cid: _drop_goal(context, cid)
    for cid in _card_order(context, state, True):
        yield lambda cid=cid: _replace_card(context, cid, _card_core)
    # A crowd of long cards in a world of long texts: roster lines keep only
    # the opening words of role and adult context, absent people first; the
    # most relevant person on stage keeps a core card.
    yield from shrink_cards(False, _roster_clipped)
    for cid in crowd:
        yield lambda cid=cid: _replace_card(context, cid, _roster_clipped)
    # A game that piled up leverage: what touches no one on stage is cut from
    # the end, and the cut is counted (status lists it all). Whatever touches
    # someone on stage always stays.
    yield leverage_cut


def _fit_full(context, state):
    for step in _full_steps(context, state):
        if size_of(context) <= FULL_LIMIT - SIZE_FIELD_RESERVE:
            break
        step()
    context["size_bytes"] = size_of(context)


def _fit(context, limit, order):
    """Trim lists in the given order until the context fits."""
    limit -= SIZE_FIELD_RESERVE
    if size_of(context) <= limit:
        context["size_bytes"] = size_of(context)
        return
    for key in order:
        holder = context
        if key == "customs":
            holder = context.get("world", {})
        value = holder.get(key)
        if isinstance(value, dict):
            holder[key] = {}
        while isinstance(holder.get(key), list) and holder[key] and size_of(context) > limit:
            holder[key].pop()
        if size_of(context) <= limit:
            break
    context["size_bytes"] = size_of(context)
