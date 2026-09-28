"""A deterministic fake narrator: it plays turns by submitting operations.

Used by `smoke` (in the Skill) and by the development simulator. It reads
the session state to build commits that the engine should accept, and can
also produce deliberately invalid commits for rejection tests. It writes no
prose; it exercises the same write path a real host uses, the way a careful
model would: time goes first in the operations, a large skip is previewed
and every NPC the preview names gets an offscreen beat, and the chapter
summary and prologue are written when the context asks for them.
"""

from ..domain import facts as FA
from ..domain import rng, simulation
from ..domain import state as SS
from ..domain import structure as ST

KINDS = ("continue", "attempt", "result", "wait", "move", "time", "promise", "roll", "reveal", "voice", "evidence", "twist", "retcon", "skip")
WEIGHTS = (3, 4, 2, 2, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1)
MOODS = ("绷着", "松了口气", "若有所思", "不耐烦", "心不在焉", "警惕")
LIKES = ("被人记住随口说过的话", "安静的陪伴", "直来直去的人", "雨夜里的热茶")
INVALID_VARIANTS = 7


def _pending_key(state, key):
    return any(e["state"] == "pending" and e["dedupe_key"].split("#")[0] == key for e in state["events"].values())


class FakeNarrator:
    def __init__(self, seed):
        self.seed = seed

    def _u(self, state, purpose, *coords):
        return rng.unit(self.seed, "fake." + purpose, state["turn"], *coords)

    def _pick(self, state, purpose, items, *coords):
        return rng.pick(self.seed, "fake." + purpose, list(items), state["turn"], *coords)

    def commit(self, state, content, force_kind=None):
        world = content["world"]
        player = state["player_id"]
        present = [c for c in state["scene"]["present"] if c != player]
        kind = force_kind or rng.weighted(self.seed, "fake.kind", list(KINDS), list(WEIGHTS), state["turn"])
        if force_kind is None and state["requests"].get("twist_offer") and self._u(state, "twist.take") < 0.5:
            kind = "twist"
        ops = []
        commit = {
            "action_mode": "continue",
            "player_input": "",
            "player_authorized": False,
            "operations": ops,
            "content_tags": [],
            "summary": "",
            "open_action": "",
            "quotes": [],
        }
        turn = state["turn"] + 1
        majors = [c for c in present if state["characters"][c]["tier"] == "major" and state["characters"][c].get("intimacy")]
        if kind == "twist":
            offer = state["requests"].get("twist_offer") or simulation.requested_twists(state, world)[0]
            if offer and state["clock"]["day"] not in state["counters"]["twists"]["accepted_days"]:
                chosen = self._pick(state, "twist.pick", [t["id"] for t in offer])
                ops.append({"op": "twist_accept", "twist_id": chosen})
                commit.update(action_mode="result", player_authorized=True, player_input="就要这个转折")
                commit["summary"] = "玩家角色选了一个转折。"
                commit["open_action"] = "转折刚刚落地，众人还没反应过来"
                return self._finish(state, content, commit, turn)
            kind = "continue"
        if kind == "retcon":
            ops.append(
                {
                    "op": "add_fact",
                    "key": "player.retcon.t%d" % turn,
                    "text": "玩家角色早年在这一带住过一阵（第%d回合补充）" % turn,
                    "known_by": [player],
                    "visibility": "private",
                    "origin": "retcon",
                }
            )
            if present:
                npc = self._pick(state, "retcon.npc", sorted(present))
                ops.append({"op": "npc_action", "npc_id": npc, "action": "看了玩家角色一眼", "significant": False})
            commit.update(action_mode="rewrite", player_authorized=True, player_input="其实我早年在这一带住过")
            commit["summary"] = "玩家角色补充：早年在这一带住过。"
            commit["open_action"] = "话题停在玩家角色的旧事上"
            return self._finish(state, content, commit, turn)
        if kind == "reveal" and present:
            npc = self._pick(state, "reveal.npc", sorted(present))
            secrets = sorted(
                fact["id"]
                for fact in FA.of(state).known_to(npc)
                if npc in fact["known_by"] and player not in fact["known_by"] and fact["visibility"] == "private" and fact["truth"]
            )
            if secrets and SS.has_edge_either(state, npc, player):
                ops.append({"op": "reveal_fact", "fact_id": self._pick(state, "reveal.fact", secrets), "from": npc, "to": [player]})
                ops.append({"op": "npc_action", "npc_id": npc, "action": "压低声音说了一件事", "significant": False})
                commit.update(action_mode="continue", player_input="继续")
                commit["summary"] = "%s对玩家角色说了一件事。" % state["characters"][npc]["name"]
                commit["open_action"] = "%s说完，等着看反应" % state["characters"][npc]["name"]
                return self._finish(state, content, commit, turn)
            kind = "continue"
        if kind == "voice" and majors:
            npc = self._pick(state, "voice.npc", sorted(majors))
            current = state["preferences"]["voice"].get(npc, {})
            voice = "surface" if current.get("voice") == "inner" else "inner"
            ops.append({"op": "set_voice", "npc_id": npc, "voice": voice, "cause": "player_request", "note": "玩家要对方换个说话方式"})
            ops.append({"op": "npc_response", "npc_id": npc, "response": self._pick(state, "voice.resp", ["refuse", "partial"]), "note": "换了语气回答"})
            commit.update(action_mode="attempt", player_authorized=True, acts_on=[npc], player_input="别装了，说点真心话")
            commit["summary"] = "玩家角色请%s说真心话。" % state["characters"][npc]["name"]
            commit["open_action"] = "%s的话停在一半" % state["characters"][npc]["name"]
            return self._finish(state, content, commit, turn)
        if kind == "evidence" and majors:
            npc = self._pick(state, "evidence.npc", sorted(majors))
            likes = state["characters"][npc]["intimacy"]["likes"]
            fresh = [v for v in LIKES if v not in likes]
            if fresh:
                value, direction = self._pick(state, "evidence.value", fresh), "add"
            else:
                value, direction = self._pick(state, "evidence.value", [v for v in LIKES if v in likes]), "remove"
            ops.append({"op": "intimacy_evidence", "npc_id": npc, "item": "likes", "direction": direction, "value": value, "evidence": "玩家角色记得那句话"})
            ops.append({"op": "npc_action", "npc_id": npc, "action": "愣了一下，笑了", "significant": False})
            commit["summary"] = "%s笑了一下。" % state["characters"][npc]["name"]
            commit["open_action"] = "%s的笑还没收起来" % state["characters"][npc]["name"]
            return self._finish(state, content, commit, turn)
        if kind in ("reveal", "voice", "evidence"):
            kind = "continue"
        if kind == "move":
            here = SS.location(world, state["scene"]["location_id"])
            target = self._pick(state, "move.to", sorted(here["exits"]))
            commit.update(action_mode="result", player_authorized=True, player_input="我走去%s" % SS.location(world, target)["name"])
            if present and self._u(state, "move.follow") < 0.6:
                follower = self._pick(state, "move.follower", sorted(present))
                ops.append({"op": "move", "character_id": follower, "location_id": target})
            ops.append({"op": "move", "character_id": player, "location_id": target})
            ops.append({"op": "advance_time", "minutes": 5 + int(self._u(state, "move.min") * 10)})
            commit["summary"] = "玩家角色去了%s。" % SS.location(world, target)["name"]
            commit["open_action"] = "刚到%s，还没开口" % SS.location(world, target)["name"]
        elif kind in ("attempt", "promise") and present:
            npc = self._pick(state, "attempt.npc", sorted(present))
            response = self._pick(state, "attempt.response", ST.RESPONSES)
            op = {"op": "npc_response", "npc_id": npc, "response": response, "note": "对玩家的试探作出反应"}
            if response == "surface":
                op["true_intent"] = "先稳住对方，回头再说"
            ops.append(op)
            commit.update(action_mode="attempt", player_authorized=True, acts_on=[npc], player_input="我试着说服%s" % state["characters"][npc]["name"])
            edge = SS.edge(state, npc, player)
            trust = edge["trust"] if edge else 0
            delta = 1 if response in ("partial", "genuine") else -1
            if ST.TRUST_RANGE[0] <= trust + delta <= ST.TRUST_RANGE[1]:
                ops.append({"op": "relationship", "from": npc, "to": player, "trust_delta": delta, "reason": "第%d回合的回应" % turn})
            if kind == "promise" and response in ("partial", "genuine"):
                ops.append(
                    {
                        "op": "event_create",
                        "kind": "promise",
                        "title": "约好再谈一次",
                        "participants": [player, npc],
                        "in_minutes": 90 + int(self._u(state, "promise.due") * 600),
                        "dedupe_key": "sim.promise.t%d" % turn,
                    }
                )
            commit["summary"] = "玩家角色试着说服%s，对方%s。" % (state["characters"][npc]["name"], ST.RESPONSE_LABELS[response])
            commit["open_action"] = "%s在等玩家的下一句" % state["characters"][npc]["name"]
        elif kind == "result":
            commit.update(action_mode="result", player_authorized=True, player_input="我把手里的单据收好")
            ops.append(
                {
                    "op": "add_fact",
                    "key": "sim.note.t%d" % turn,
                    "text": "第%d回合玩家角色把一张单据收进了口袋" % turn,
                    "known_by": [player],
                    "visibility": "private",
                    "origin": "observed",
                }
            )
            pending = [
                e for e in state["events"].values()
                if e["state"] == "pending" and e["kind"] == "promise" and player in e["participants"]
            ]
            if pending and self._u(state, "result.fulfil") < 0.5:
                ops.append({"op": "event_resolve", "event_id": sorted(pending, key=lambda e: e["id"])[0]["id"], "outcome": "fulfilled", "note": "按约定做到了"})
            commit["summary"] = "玩家角色收好了单据。"
            commit["open_action"] = "单据在口袋里，没人说话"
        elif kind == "roll":
            commit.update(action_mode="attempt", player_authorized=True, acts_on=[], player_input="我试着看清远处的动静")
            ops.append(
                {
                    "op": "roll",
                    "purpose": "能不能看清远处的动静",
                    "probability": 0.5,
                    "on_success": [
                        {"op": "add_fact", "key": "sim.seen.t%d" % turn, "text": "第%d回合玩家角色看清了远处的人影" % turn, "known_by": [player], "visibility": "private", "origin": "observed"}
                    ],
                    "on_failure": [],
                }
            )
            commit["summary"] = "玩家角色试着看清远处的动静。"
            commit["open_action"] = "远处的灯晃了一下"
        else:
            mode = "wait" if kind == "wait" else "continue"
            commit["action_mode"] = mode
            commit["player_input"] = "继续" if mode == "continue" else "我不说话，看看会怎样"
            if kind == "time":
                if self._u(state, "time.big") < 0.2:
                    ops.append({"op": "advance_time", "until": self._pick(state, "time.until", ["morning", "noon", "evening", "night"])})
                else:
                    ops.append({"op": "advance_time", "minutes": 10 + int(self._u(state, "time.min") * 40)})
            elif kind == "skip":
                ops.append({"op": "advance_time", "until": "next_morning"} if self._u(state, "skip.kind") < 0.7 else {"op": "advance_time", "days": 1})
                if state["mode"] == "pressure" and present and not _pending_key(state, "sim.chance") and self._u(state, "skip.chance") < 0.5:
                    npc = self._pick(state, "skip.npc", sorted(present))
                    ops.append(
                        {
                            "op": "event_create",
                            "kind": "chance",
                            "title": "码头上的风声",
                            "participants": [npc],
                            "in_minutes": 60 + int(self._u(state, "skip.due") * 600),
                            "probability": 0.5,
                            "dedupe_key": "sim.chance",
                            "repeat": True,
                        }
                    )
            if present:
                npc = self._pick(state, "cont.npc", sorted(present))
                significant = kind == "wait" and SS.can_act(state, npc)
                ops.append({"op": "npc_action", "npc_id": npc, "action": "%s做了一件小事" % state["characters"][npc]["name"], "significant": significant, "kind": "approach" if significant else None})
                if self._u(state, "cont.mood") < 0.5:
                    ops.append({"op": "npc_state", "npc_id": npc, "mood": self._pick(state, "cont.mood.pick", MOODS)})
                commit["summary"] = "%s有了动作。" % state["characters"][npc]["name"]
                commit["open_action"] = "%s的动作停在半空" % state["characters"][npc]["name"]
            else:
                ops.append(
                    {"op": "add_fact", "key": "sim.env.t%d" % turn, "text": "第%d回合远处传来一声汽笛" % turn, "known_by": [player], "visibility": "private", "origin": "observed"}
                )
                commit["summary"] = "四周安静，远处传来汽笛。"
                commit["open_action"] = "汽笛声还在回响"
        return self._finish(state, content, commit, turn)

    # -- time, offscreen beats and requested texts ---------------------------------

    def _beat(self, state, npc, turn, index):
        char = state["characters"][npc]
        subs = [{"op": "npc_action", "npc_id": npc, "action": "忙着自己的事", "significant": False}]
        if self._u(state, "beat.fact", index) < 0.4:
            subs.append(
                {
                    "op": "add_fact",
                    "key": "sim.offscreen.%s.t%d" % (npc, turn),
                    "text": "%s在第%d回合听到一句闲话" % (char["name"], turn),
                    "known_by": [npc],
                    "visibility": "private",
                    "origin": "observed",
                    "spread": True,
                }
            )
        others = sorted(
            cid for cid, c in state["characters"].items()
            if cid not in (npc, state["player_id"]) and c["tier"] == "major"
        )
        if others and self._u(state, "beat.rel", index) < 0.3:
            other = self._pick(state, "beat.other", others, index)
            edge = SS.edge(state, npc, other)
            trust = edge["trust"] if edge else 0
            delta = 1 if trust < ST.TRUST_RANGE[1] else -1
            subs.append({"op": "relationship", "from": npc, "to": other, "trust_delta": delta, "reason": "离屏的一次交谈"})
        if not _pending_key(state, "sim.rumor.%s" % npc) and self._u(state, "beat.event", index) < 0.15:
            subs.append(
                {
                    "op": "event_create",
                    "kind": "rumor",
                    "title": "%s放出的风声" % char["name"],
                    "participants": [npc],
                    "in_minutes": 120 + int(self._u(state, "beat.due", index) * 600),
                    "dedupe_key": "sim.rumor.%s" % npc,
                    "repeat": True,
                }
            )
        return {"op": "offscreen_beat", "npc_id": npc, "summary": "%s在别处忙自己的事" % char["name"], "operations": subs}

    def _finish(self, state, content, commit, turn):
        ops = commit["operations"]
        # Time first, so the settlement matches the preview (RUNTIME_PROTOCOL 6.4).
        advance = next((op for op in ops if op["op"] == "advance_time"), None)
        if advance is not None:
            ops.remove(advance)
        spec = {k: v for k, v in (advance or {"minutes": ST.DEFAULT_ADVANCE_MINUTES}).items() if k != "op"}
        preview = simulation.preview(state, content["world"], spec)
        required = [p["npc_id"] for p in preview["required_beats"]]
        beats = [self._beat(state, npc, turn, index) for index, npc in enumerate(required)]
        optional = [c for c in sorted(set(state["requests"].get("offscreen_beat_candidates") or []) | set(preview["beat_candidates"])) if c not in required]
        if optional and commit["action_mode"] in ("continue", "wait") and self._u(state, "beat.optional") < 0.3:
            beats.append(self._beat(state, self._pick(state, "beat.optional.npc", optional), turn, len(beats)))
        if advance is not None or beats:
            ops[0:0] = [advance or {"op": "advance_time", "minutes": ST.DEFAULT_ADVANCE_MINUTES}] + beats
        requests = state["requests"]
        if requests.get("chapter_summary"):
            commit["chapter_summary"] = "第%d回合之前：玩家角色在%s度过了一段日子，人和事都往前走了一步。" % (turn, state["world_title"])
        if requests.get("prologue"):
            source = simulation.prologue_source(state)
            last = source["chapters"][-1]["to_turn"] if source["chapters"] else turn - 1
            commit["prologue"] = "前情（到第%d回合）：玩家角色在%s安顿下来，结识了几个人，也欠下了几笔人情。" % (last, state["world_title"])
        return commit

    def invalid_commit(self, state, content, variant):
        """A commit the engine must reject (for rejection tests)."""
        base = self.commit(state, content, force_kind="continue")
        player = state["player_id"]
        variant %= INVALID_VARIANTS
        if variant == 0:
            base["operations"].append({"op": "npc_response", "npc_id": "nobody_here", "response": "genuine", "note": "不存在的人"})
        elif variant == 1:
            base["action_mode"] = "continue"
            base["operations"].append({"op": "move", "character_id": player, "location_id": state["scene"]["location_id"]})
        elif variant == 2:
            base["operations"].append({"op": "advance_time", "minutes": ST.MAX_ADVANCE_MINUTES + 1})
        elif variant == 3:
            base["operations"].append(
                {"op": "event_create", "kind": "opportunity", "title": "已经过去的机会", "participants": [player], "due": dict(state["clock"]), "dedupe_key": "sim.bad"}
            )
        elif variant == 4:
            base["content_tags"] = ["not_a_tag"]
        elif variant == 5:
            # a retcon that contradicts an established fact (same key)
            base.update(action_mode="rewrite", player_authorized=True, player_input="其实我根本不是干这行的")
            base["operations"] = [
                {"op": "add_fact", "key": "player.baseline", "text": "玩家角色其实是别的身份", "known_by": [player], "visibility": "private", "origin": "retcon"}
            ]
        else:
            # an offscreen beat for someone who is on stage
            base["operations"].append({"op": "offscreen_beat", "npc_id": player, "summary": "玩家角色在别处", "operations": []})
        return base
