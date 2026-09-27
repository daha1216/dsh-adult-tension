"""A deterministic fake narrator: it plays turns by submitting operations.

Used by `smoke` (in the Skill) and by the development simulator. It reads
the session state to build commits that the engine should accept, and can
also produce deliberately invalid commits for rejection tests. It writes no
prose; it exercises the same write path a real host uses.
"""

from ..domain import rng
from ..domain import state as SS
from ..domain import structure as ST

KINDS = ("continue", "attempt", "result", "wait", "move", "time", "promise", "roll", "reveal", "voice", "evidence")
WEIGHTS = (3, 4, 2, 2, 1, 2, 1, 1, 1, 1, 1)
MOODS = ("绷着", "松了口气", "若有所思", "不耐烦", "心不在焉", "警惕")


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
        if kind == "reveal" and present:
            npc = self._pick(state, "reveal.npc", sorted(present))
            secrets = sorted(
                fid
                for fid, fact in state["facts"].items()
                if npc in fact["known_by"] and player not in fact["known_by"] and fact["visibility"] == "private" and fact["truth"]
            )
            if secrets and SS.has_edge_either(state, npc, player):
                ops.append({"op": "reveal_fact", "fact_id": self._pick(state, "reveal.fact", secrets), "from": npc, "to": [player]})
                ops.append({"op": "npc_action", "npc_id": npc, "action": "压低声音说了一件事", "significant": False})
                commit.update(action_mode="continue", player_input="继续")
                commit["summary"] = "%s对玩家角色说了一件事。" % state["characters"][npc]["name"]
                commit["open_action"] = "%s说完，等着看反应" % state["characters"][npc]["name"]
                return self._finish(state, commit, turn)
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
            return self._finish(state, commit, turn)
        if kind == "evidence" and majors:
            npc = self._pick(state, "evidence.npc", sorted(majors))
            ops.append({"op": "intimacy_evidence", "npc_id": npc, "item": "likes", "direction": "add", "value": "被人记住随口说过的话", "evidence": "玩家角色记得那句话"})
            ops.append({"op": "npc_action", "npc_id": npc, "action": "愣了一下，笑了", "significant": False})
            commit["summary"] = "%s笑了一下。" % state["characters"][npc]["name"]
            commit["open_action"] = "%s的笑还没收起来" % state["characters"][npc]["name"]
            return self._finish(state, commit, turn)
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
        return self._finish(state, commit, turn)

    def _finish(self, state, commit, turn):
        if state["requests"].get("chapter_summary"):
            commit["chapter_summary"] = "第%d回合之前：玩家角色在%s度过了一段夜班。" % (turn, state["world_title"])
        return commit

    def invalid_commit(self, state, content, variant):
        """A commit the engine must reject (for rejection tests)."""
        base = self.commit(state, content, force_kind="continue")
        player = state["player_id"]
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
        else:
            base["content_tags"] = ["not_a_tag"]
        return base
