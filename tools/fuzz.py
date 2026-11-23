"""Fuzz the runtime in-process through the real CLI adapter.

    python tools/fuzz.py [envelope|spec|plausible|all] [--n N] [--seed S] [--mode daily|pressure]

envelope   mutated inputs (and broken bytes) thrown at every command
spec       commit-turn with random operations generated from the operation
           specs, ids taken from the live state; undo, save, load mixed in
plausible  well-formed operations built from the live state (present people,
           known facts, pending events, held leverage) spliced into turns the
           fake narrator writes; rejected operations are dropped and the turn
           retried, the way a model repairs a record

Every mode fails (exit 1) on an INTERNAL_ERROR, a Python exception escaping
the adapter, an error code missing from the error table, an error with exit
code 0, or an error detail whose path is not a JSON path. Data goes to a
temporary directory, removed afterwards unless something failed.
"""

import collections
import copy
import io
import json
import os
import random
import re
import shutil
import sys
import tempfile
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _runtime  # noqa: E402

_runtime.use_runtime()
from adult_tension import errors as E  # noqa: E402
from adult_tension import schema as S  # noqa: E402
from adult_tension.adapters import cli  # noqa: E402
from adult_tension.application.context import Context  # noqa: E402
from adult_tension.application.fake_narrator import FakeNarrator  # noqa: E402
from adult_tension.domain import ops as OPS  # noqa: E402
from adult_tension.domain import structure as ST  # noqa: E402
from adult_tension.persistence import repo  # noqa: E402

SKILL = _runtime.SKILL_ROOT
KNOWN_CODES = set(E.ERROR_DESCRIPTIONS)
OP_PATH = re.compile(r"\$\.turns\[(\d+)\]\.operations\[(\d+)\]")
ID_RE = re.compile(r"[a-z0-9_]{1,40}")
NAMES = ["周静", "韩梅", "陈立", "宋雨", "白露", "郑岚", "方远", "顾青"]


class Harness:
    """One data directory, one game, and the contract checks on every reply."""

    def __init__(self, label, seed, mode):
        self.rnd = random.Random(seed)
        self.work = tempfile.mkdtemp(prefix="at-fuzz-%s-" % label)
        self.data = os.path.join(self.work, "data")
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("ADULT_TENSION")}
        self.counter = 0
        self.label = label
        self.problems = collections.Counter()
        self.shown = set()
        self.calls = collections.Counter()
        opened = self.run("new-game", {"request_id": self.rid(), "mode": mode, "seed": seed})
        if not opened["ok"]:
            raise SystemExit("new-game failed: %s" % opened["error"])
        self.sid = opened["data"]["session_id"]
        self.ctx = Context(SKILL, self.data, self.env, {}, False)
        self.narrator = FakeNarrator(seed)

    def rid(self):
        self.counter += 1
        return "fz_%s_%07d" % (self.label[:4], self.counter)

    def current(self):
        return repo.load_session(self.ctx.db(), self.sid)

    def run(self, cmd, payload, raw=None):
        body = raw if raw is not None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            env, code, _opts, _text, _payload = cli.execute([cmd, "--json", "--data-dir", self.data, "--input-file", "-"], SKILL, io.BytesIO(body), self.env)
        except Exception:
            self.problem(("raised", cmd), traceback.format_exc()[-2500:])
            return {"ok": False, "error": {"code": "RAISED", "details": []}}
        self.calls[(cmd, env["ok"])] += 1
        if not env["ok"]:
            self.check_error(cmd, env, code, payload if raw is None else repr(raw))
        return env

    def check_error(self, cmd, env, code, payload):
        err = env["error"]
        if err["code"] == "INTERNAL_ERROR":
            log = err.get("log")
            tb = ""
            if log and os.path.exists(log):
                with open(log, encoding="utf-8") as handle:
                    tb = handle.read().split(err["error_id"])[-1][:4000]
            last = tb.strip().splitlines()[-1] if tb.strip() else "?"
            self.problem(("INTERNAL", cmd, last), "payload: %s\n%s" % (json.dumps(payload, ensure_ascii=False)[:2000], tb[-2500:]))
        elif err["code"] not in KNOWN_CODES:
            self.problem(("unknown code", err["code"]), None)
        if code == 0:
            self.problem(("exit 0 on error", cmd), None)
        for d in err.get("details") or []:
            if not isinstance(d.get("path"), str) or not d["path"].startswith("$"):
                self.problem(("bad detail path", cmd), json.dumps(d, ensure_ascii=False)[:500])

    def problem(self, key, text):
        self.problems[key] += 1
        if key not in self.shown:
            self.shown.add(key)
            print("PROBLEM %s" % (key,), flush=True)
            if text:
                print(text, flush=True)

    def write(self, cmd, **fields):
        info = self.current()
        payload = dict({"session_id": self.sid, "request_id": self.rid(), "expected_revision": info["revision"]}, **fields)
        return self.run(cmd, payload)

    def side_command(self, r):
        """Undo, save, load or safety now and then; True when one ran."""
        rnd = self.rnd
        if r < 0.05:
            self.write("undo-turn")
        elif r < 0.07:
            self.write("save-slot", name="s%d" % rnd.randint(0, 1), overwrite=True)
        elif r < 0.08:
            env = self.run("load-slot", {"request_id": self.rid(), "name": "s%d" % rnd.randint(0, 1)})
            if env["ok"]:
                self.sid = env["data"]["session_id"]
        elif r < 0.10:
            self.write("set-safety", paused=rnd.random() < 0.5, change_scene=rnd.random() < 0.3)
        elif r < 0.11:
            self.write("set-boundary", action="add", text="不要暴力", tags=["violence"])
        else:
            return False
        return True

    def commit_repairing(self, turns, attempts=4, reasons=None):
        """Commit; on a rejection drop the operations the errors point at and retry."""
        env = self.write("commit-turn", turns=turns)
        for _ in range(attempts - 1):
            if env["ok"] or env["error"]["code"] in ("INTERNAL_ERROR", "RAISED"):
                break
            drop = set()
            for d in env["error"].get("details") or []:
                m = OP_PATH.match(d.get("path", ""))
                if m:
                    k, j = int(m.group(1)), int(m.group(2))
                    drop.add((k, j))
                    if reasons is not None and k < len(turns) and j < len(turns[k]["operations"]):
                        reasons[turns[k]["operations"][j].get("op", "?")][re.sub(r"[0-9a-z_]{6,}", "…", d["reason"])[:50]] += 1
            if not drop:
                break
            for k, t in enumerate(turns):
                t["operations"] = [op for j, op in enumerate(t["operations"]) if (k, j) not in drop]
            env = self.write("commit-turn", turns=turns)
        return env

    def requested_fields(self, turn, state):
        if state["requests"].get("chapter_summary"):
            turn["chapter_summary"] = "这一章几个人谁也没先开口。"
        if state["requests"].get("prologue"):
            turn["prologue"] = "很久以前的事，大家都记得一点。"

    def finish(self):
        self.ctx.close()
        failed = sum(self.problems.values())
        if failed:
            print("%s: %d problem(s), data kept in %s" % (self.label, failed, self.work))
        else:
            shutil.rmtree(self.work, ignore_errors=True)
            print("%s: no problems" % self.label)
        return failed


# -- envelope: mutated inputs at every command ---------------------------------

WEIRD = [None, "", 0, -1, 1, 2 ** 63, -(2 ** 63), 1.5, float("1e308"), True, False, [], {}, "x" * 20000, "\u0000", "\ud7ff\u200b", "汉字", [None], {"a": 1},
         "../../etc/passwd", "s_00000000", "C:\\Windows\\win.ini", "player", "  ", "\n"]
BROKEN_BYTES = [b"{", b"[]", b"\xff\xfe{}", b"null", b'{"a":1,"a":2}', b"\xef\xbb\xbf{}", b'{"x": NaN}', b"1e999"]


def mutate(rnd, value, depth=0):
    if rnd.random() < 0.12 or depth > 6:
        return copy.deepcopy(rnd.choice(WEIRD))
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            r = rnd.random()
            if r < 0.06:
                continue
            out[k] = mutate(rnd, v, depth + 1) if r < 0.35 else v
        if rnd.random() < 0.05:
            out[rnd.choice(["extra", "op", "id", "turn", "npc_id"])] = rnd.choice(WEIRD)
        return out
    if isinstance(value, list):
        out = [mutate(rnd, v, depth + 1) if rnd.random() < 0.35 else v for v in value if rnd.random() > 0.05]
        if value and rnd.random() < 0.1:
            out = out + [copy.deepcopy(rnd.choice(value))] * rnd.randint(1, 15)
        return out
    if isinstance(value, str):
        r = rnd.random()
        if r < 0.2:
            return value + rnd.choice(["_x", "'", "\"", "\\", "；", "\u3000", "%s", "{name}", "{npc.ta}"])
        if r < 0.3:
            return value * rnd.randint(2, 200)
        return value
    if isinstance(value, bool):
        return not value if rnd.random() < 0.3 else value
    if isinstance(value, (int, float)):
        return rnd.choice([value + 1, value - 1, -value, value * 1000, 0, -1, 10 ** 9])
    return value


def envelope(n, seed, mode):
    h = Harness("envelope", seed, mode)
    rnd = h.rnd
    samples = []
    for _ in range(40):
        info = h.current()
        turn = h.narrator.commit(info["state"], info["content"])
        samples.append(copy.deepcopy(turn))
        h.write("commit-turn", turns=[turn])
    h.write("save-slot", name="fz")
    export_path = os.path.join(h.work, "exp.json")
    h.run("export-save", {"session_id": h.sid, "path": export_path})

    def bases():
        info = h.current()
        rev, state, sid = info["revision"], info["state"], h.sid
        turn = copy.deepcopy(rnd.choice(samples))
        npc = next(k for k in state["characters"] if k != state["player_id"])
        return {
            "commit-turn": {"session_id": sid, "request_id": h.rid(), "expected_revision": rev, "turns": [turn, copy.deepcopy(rnd.choice(samples))][: rnd.randint(1, 2)]},
            "get-context": {"session_id": sid, "depth": rnd.choice(["brief", "full"]), "preview_time": {"minutes": 90}, "want_twist": True},
            "status": {"session_id": sid, "level": rnd.choice(["brief", "detail", "debug"])},
            "new-game": {"request_id": h.rid(), "mode": rnd.choice(["daily", "pressure", "random"]), "world_query": rnd.choice(["极道", "码头", "zzz"]),
                         "excludes": {"content_tags": ["crime"], "world_ids": []}, "player": {"gender": "female", "age": 30, "identity_hint": "裁缝", "name": "罗秀英", "title": "罗师傅"},
                         "npc_gender_preference": "mostly_female", "seed": rnd.randint(1, 10 ** 6), "preferences": {"pace": "slow", "explicitness": "subtle"}},
            "undo-turn": {"session_id": sid, "request_id": h.rid(), "expected_revision": rev},
            "save-slot": {"session_id": sid, "request_id": h.rid(), "expected_revision": rev, "name": rnd.choice(["fz", "新档", None]), "overwrite": rnd.random() < 0.5},
            "load-slot": {"request_id": h.rid(), "name": "fz"},
            "delete-slot": {"session_id": sid, "request_id": h.rid(), "expected_revision": rev, "name": "zz", "confirm": True},
            "list-sessions": {"limit": 5},
            "list-slots": {},
            "export-save": {"session_id": sid, "path": os.path.join(h.work, "e%d.json" % rnd.randint(0, 3))},
            "import-save": {"request_id": h.rid(), "path": export_path, "slot": "imp", "overwrite": True},
            "set-boundary": {"session_id": sid, "request_id": h.rid(), "expected_revision": rev, "action": "add", "text": "不要血腥"},
            "set-safety": {"session_id": sid, "request_id": h.rid(), "expected_revision": rev, "paused": rnd.random() < 0.5, "change_scene": rnd.random() < 0.3},
            "set-preferences": {"session_id": sid, "request_id": h.rid(), "expected_revision": rev, "inner_view": True, "assistant": False, "person": "second",
                                "voice": {"npc_id": npc, "voice": "inner"}, "npc_gender_preference": "any", "pace": "direct", "explicitness": "explicit"},
            "list-worlds": {"include_drafts": False, "query": rnd.choice([None, "港口"]), "tags": ["supernatural"], "exclude_tags": ["disaster"]},
            "verify-content": {"world": "harbor_night_shift"},
        }

    for _ in range(n):
        payloads = bases()
        cmd = rnd.choice(sorted(payloads))
        payload = mutate(rnd, payloads[cmd]) if rnd.random() < 0.9 else payloads[cmd]
        raw = rnd.choice(BROKEN_BYTES) if rnd.random() < 0.03 else None
        h.run(cmd, payload, raw)
    print("calls by command/ok:", sorted(h.calls.items()))
    return h.finish()


# -- spec: operations generated from their specs -------------------------------


def id_pool(state, content):
    pool = set(state["characters"]) | set(state.get("events", {}))
    pool.update(loc["id"] for loc in content["world"].get("locations", []))
    pool.update(fact["id"] for fact in state["facts"].all())

    def walk(v):
        if isinstance(v, dict):
            for k, x in v.items():
                if k == "id" and isinstance(x, str) and ID_RE.fullmatch(x):
                    pool.add(x)
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk({k: v for k, v in state.items() if k != "facts"})
    return sorted(pool)


def gen(rnd, spec, pool):
    if isinstance(spec, S.Nullable):
        return None if rnd.random() < 0.25 else gen(rnd, spec.inner, pool)
    if isinstance(spec, S.Enum):
        return rnd.choice(spec.values)
    if isinstance(spec, S.Bool):
        return rnd.random() < 0.5
    if isinstance(spec, S.Int):
        lo = spec.lo if spec.lo is not None else -5
        hi = spec.hi if spec.hi is not None else lo + 100
        r = rnd.random()
        return lo if r < 0.3 else hi if r < 0.4 else rnd.randint(lo, min(hi, lo + 600))
    if isinstance(spec, S.Num):
        lo = spec.lo if spec.lo is not None else -1.0
        hi = spec.hi if spec.hi is not None else 1.0
        return round(rnd.uniform(lo, hi), 3)
    if isinstance(spec, S.Str):
        if spec.pattern is not None and spec.pattern.pattern.startswith("[a-z0-9_]"):
            if "." in spec.pattern.pattern:  # a fact key
                return "%s.%s" % (rnd.choice(pool) if pool else "x", rnd.choice(["secret", "status", "debt", "mood"]))
            return rnd.choice(pool) if pool and rnd.random() < 0.9 else "zz_%d" % rnd.randint(0, 9)
        if spec.pattern is not None:
            return "abcdefgh"
        lo = max(spec.min_len, 1)
        hi = spec.max_len or 40
        return ("看了一眼" * hi)[: rnd.choice([lo, min(hi, lo + 5), hi])]
    if isinstance(spec, S.List):
        lo = spec.min_items
        hi = spec.max_items if spec.max_items is not None else lo + 3
        out = []
        for _ in range(rnd.randint(lo, min(hi, lo + 3))):
            item = gen(rnd, spec.item, pool)
            if not (spec.unique and item in out):
                out.append(item)
        return out
    if isinstance(spec, S.Map):
        return {rnd.choice(pool) if pool else "k": gen(rnd, spec.value, pool) for _ in range(rnd.randint(0, 2))}
    if isinstance(spec, S.Obj):
        return {name: gen(rnd, field.spec, pool) for name, field in spec.fields.items() if field.required or rnd.random() < 0.5}
    if isinstance(spec, S.Tagged):
        return gen(rnd, spec.variants[rnd.choice(sorted(spec.variants))], pool)
    if isinstance(spec, S.Any):
        return rnd.choice([None, 1, "x", {}, []])
    raise TypeError(type(spec))


def spec_mode(n, seed, mode):
    h = Harness("spec", seed, mode)
    rnd = h.rnd
    tags = list(ST.INTIMACY_TAGS) + ["violence", "crime"]
    outcomes = collections.Counter()
    applied = collections.Counter()
    t0 = time.time()
    for i in range(n):
        if h.side_command(rnd.random()):
            continue
        info = h.current()
        state, content = info["state"], info["content"]
        pool = id_pool(state, content)
        npcs = [c for c in state["characters"] if c != state["player_id"]]
        turns = []
        for k in range(rnd.choice([1, 1, 1, 2, 3, 12])):
            if rnd.random() < 0.45:
                t = h.narrator.commit(state, content)
                if rnd.random() < 0.6:
                    t["operations"].insert(rnd.randint(0, len(t["operations"])), gen(rnd, OPS.op_spec(), pool))
            else:
                t = {"action_mode": rnd.choice(ST.ACTION_MODES), "player_input": "试试", "operations": [gen(rnd, OPS.op_spec(), pool) for _ in range(rnd.randint(0, 5))],
                     "content_tags": rnd.sample(tags, rnd.randint(0, 2)), "summary": "有人动了一下。", "open_action": "大家等着"}
                if rnd.random() < 0.5:
                    t["player_authorized"] = rnd.random() < 0.7
                if npcs and rnd.random() < 0.4:
                    t["acts_on"] = rnd.sample(npcs, 1)
                if npcs and any(x in t["content_tags"] for x in ST.STRUCTURAL_INTIMACY_TAGS):
                    t["intimate_participants"] = [state["player_id"]] + rnd.sample(npcs, 1)
            if k == 0:
                h.requested_fields(t, state)
                if rnd.random() < 0.05:
                    t["replaces_turn"] = state["turn"]
            turns.append(t)
        env = h.commit_repairing(turns)
        outcomes[env["ok"]] += 1
        if env["ok"]:
            for tr in env["data"]["turns"]:
                applied.update(a["op"] for a in tr["applied"])
            if rnd.random() < 0.1:
                h.run("get-context", {"session_id": h.sid, "depth": "full"})
                h.run("status", {"session_id": h.sid, "level": "debug"})
        if (i + 1) % 250 == 0:
            print("progress %d calls %.0fs turn=%s commits=%s" % (i + 1, time.time() - t0, h.current()["state"]["turn"], dict(outcomes)), flush=True)
    print("ops never applied:", sorted(set(OPS.SPECS) - set(applied)))
    return h.finish()


# -- plausible: well-formed operations from the live state ---------------------

CARD = {
    "appearance": "袖口总是卷得整整齐齐",
    "identity": {"authority": "排吊装顺序", "resources": ["六频道"], "limits": ["刚来，谁都不认识"], "exposure_risk": "档案里少了一页", "hidden_mismatch": "其实会说三种方言"},
    "decision": {
        "core_value": "先站稳脚跟",
        "current_goal": "摸清谁说了算",
        "pressure_responses": {"low": "装糊涂", "mid": "讲条件", "high": "找人撑腰", "breaking": "直接走人"},
        "withdrawal": "只在对讲机里说话",
        "relationship_stance": "谁先示好就先信谁三分",
        "contrast": "看着冷，其实怕寂寞",
        "prefers": ["说清楚"],
        "avoids": ["欠人情"],
        "never": ["出卖同事"],
    },
    "intimacy": {
        "desire_level": 2,
        "attraction_sources": ["对方守信", "对方不拿身份压人"],
        "likes": ["慢"],
        "dislikes": ["被试探"],
        "preconditions": ["不在当班时"],
        "boundaries": ["不在控制塔里"],
        "expression": "递一杯茶",
        "self_control": 4,
        "desired_position": "平等",
    },
    "voices": {"surface": "“下一个。”", "inner": "“别走。”"},
    "situation": {"trigger": "刚调来就被人盯上", "pressure": "站错队就要被调走", "exits": [{"option": "低头做事", "cost": "被当成软柿子"}, {"option": "找靠山", "cost": "欠一个大人情"}]},
}


def plausible_op(rnd, state, content, fresh):
    def pick(seq):
        seq = list(seq)
        return rnd.choice(seq) if seq else None

    player = state["player_id"]
    chars = state["characters"]
    npcs = [c for c in chars if c != player]
    present = [c for c in state["scene"]["present"] if c != player]
    locations = [loc["id"] for loc in content["world"]["locations"]]
    facts = state["facts"].all()
    pending = [e for e, v in state["events"].items() if v["state"] == "pending"]
    who = pick(present) or pick(npcs)
    kind = rnd.choice(["introduce", "introduce", "promote", "promote", "leverage_set", "leverage_release", "rumor", "rumor", "identity", "event_resolve",
                       "event_cancel", "exit", "enter", "move", "reveal", "relationship", "beat", "npc_update", "voice", "player_update"])
    if kind == "introduce":
        fresh[0] += 1
        tier = rnd.choice(["background", "supporting", "major"])
        op = {"op": "introduce_character", "id": "fz_new_%d" % fresh[0], "name": NAMES[fresh[0] % len(NAMES)] + "%d" % fresh[0],
              "tier": tier, "age": rnd.choice([18, 25, 34, 47, 60, 17]), "gender": rnd.choice(["female", "male", "nonbinary"]),
              "adult_context": "在这里做了十年账房", "public_role": "账房"}
        if tier != "background":
            op.update(copy.deepcopy(CARD))
        if rnd.random() < 0.7:
            op["present"] = True
        if rnd.random() < 0.3:
            op["location_id"] = pick(locations)
        if rnd.random() < 0.2:
            op["kin_of"] = pick(npcs)
        return op
    if kind == "promote":
        low = [c for c in npcs if chars[c]["tier"] != "major"] or npcs
        op = {"op": "promote_character", "character_id": pick(low), "to_tier": rnd.choice(["supporting", "major"])}
        if rnd.random() < 0.8:
            op.update(copy.deepcopy(CARD))
        return op
    if kind == "leverage_set":
        op = {"op": "leverage_set", "holder": pick([player] + npcs), "subject": pick([player] + npcs), "origin": "偷看到的账本"}
        known = [f for f in facts if op["holder"] in f.get("known_by", [])]
        if known and rnd.random() < 0.8:
            op["basis_fact_id"] = pick(known)["id"]
        else:
            op["basis_text"] = "他欠了一笔不能说的钱"
        return op
    if kind == "leverage_release":
        return {"op": "leverage_release", "leverage_id": pick(state["leverage"]) or "lv1", "reason": "用掉了"}
    if kind == "rumor":
        src = who or player
        crowd = present or npcs
        op = {"op": "spread_rumor", "from": src, "key": "%s.rumor.r%d" % (pick(npcs), rnd.randint(1, 3)), "text": "听说他们昨晚吵过",
              "believed_by": [c for c in rnd.sample(crowd, min(len(crowd), rnd.randint(1, 2))) if c != src] or [player]}
        if facts and rnd.random() < 0.4:
            op["source_fact_id"] = pick(facts)["id"]
        return op
    if kind == "identity":
        item = rnd.choice(["authority", "resources", "limits", "obligations", "exposure_risk", "hidden_mismatch"])
        action = "set" if item in ("authority", "exposure_risk", "hidden_mismatch") else rnd.choice(["add", "remove"])
        return {"op": "identity_update", "npc_id": who, "item": item, "action": action, "value": "管着码头的钥匙", "reason": "刚接手"}
    if kind == "event_resolve":
        return {"op": "event_resolve", "event_id": pick(pending) or "e1", "outcome": rnd.choice(["fulfilled", "surfaced"]), "note": "事情到头了"}
    if kind == "event_cancel":
        return {"op": "event_cancel", "event_id": pick(pending) or "e1", "reason": "没人再提"}
    if kind == "exit":
        op = {"op": "exit_scene", "character_id": who}
        if rnd.random() < 0.5:
            op["to_location_id"] = pick(locations)
        return op
    if kind == "enter":
        from adult_tension.domain import opening as OP

        absent = [c for c in npcs if c not in state["scene"]["present"]] + list(OP.standby_previews(state, content["world"]))
        return {"op": "enter_scene", "character_id": pick(absent) or who}
    if kind == "move":
        return {"op": "move", "character_id": pick([who, player]), "location_id": pick(locations)}
    if kind == "reveal":
        f = pick(facts)
        if f is None:
            return {"op": "advance_time", "minutes": 3}
        return {"op": "reveal_fact", "fact_id": f["id"], "from": pick(f.get("known_by") or [player]), "to": [pick([player] + present)]}
    if kind == "relationship":
        return {"op": "relationship", "from": who, "to": pick([player] + present), "trust_delta": rnd.choice([-12, -3, 2, 6, 15]), "reason": "刚才那句话%d" % rnd.randint(0, 9)}
    if kind == "beat":
        npc = pick(npcs)
        return {"op": "offscreen_beat", "npc_id": npc, "summary": "在后面清点了货",
                "operations": [{"op": "npc_action", "npc_id": npc, "action": "数了一遍"}] if rnd.random() < 0.5 else []}
    if kind == "npc_update":
        return {"op": "npc_update", "npc_id": who, "field": rnd.choice(["public_role", "appearance", "current_goal", "relationship_stance", "situation_trigger", "situation_pressure"]),
                "value": "先把账对平", "reason": "老板催"}
    if kind == "player_update":
        return {"op": "player_update", "title": rnd.choice(["陈师傅", "老板", None]), "add_resources": ["一把旧钥匙"]}
    return {"op": "set_voice", "npc_id": who, "voice": rnd.choice(["inner", "surface"]), "cause": rnd.choice(["player_request", "npc_self", "revert"]),
            "trigger": rnd.choice([None, "alone", "drunk", "breakdown", "exposed"]), "note": "她不再装了"}


def plausible(n, seed, mode):
    h = Harness("plausible", seed, mode)
    rnd = h.rnd
    fresh = [0]
    reasons = collections.defaultdict(collections.Counter)
    applied = collections.Counter()
    outcomes = collections.Counter()
    t0 = time.time()
    for i in range(n):
        if h.side_command(rnd.random()):
            continue
        info = h.current()
        state, content = info["state"], info["content"]
        turns = []
        for k in range(rnd.choice([1, 1, 1, 2, 4])):
            t = h.narrator.commit(state, content)
            for _ in range(rnd.randint(1, 3)):
                t["operations"].insert(rnd.randint(0, len(t["operations"])), plausible_op(rnd, state, content, fresh))
            if k == 0:
                h.requested_fields(t, state)
                if rnd.random() < 0.06:
                    t["replaces_turn"] = state["turn"]
            turns.append(t)
        env = h.commit_repairing(turns, reasons=reasons)
        outcomes[env["ok"]] += 1
        if env["ok"]:
            for tr in env["data"]["turns"]:
                applied.update(a["op"] for a in tr["applied"])
        if (i + 1) % 200 == 0:
            print("progress %d %.0fs turn=%d commits=%s" % (i + 1, time.time() - t0, h.current()["state"]["turn"], dict(outcomes)), flush=True)
    print("ops never applied:", sorted(set(OPS.SPECS) - set(applied)))
    for op, c in sorted(reasons.items()):
        print("  rejected %s: %s" % (op, c.most_common(3)))
    return h.finish()


MODES = {"envelope": (envelope, 300), "spec": (spec_mode, 1000), "plausible": (plausible, 600)}


def main(argv):
    which = argv[0] if argv and not argv[0].startswith("--") else "all"
    if which not in MODES and which != "all":
        print(__doc__)
        return 2

    def opt(name, default):
        return argv[argv.index(name) + 1] if name in argv else default

    seed = int(opt("--seed", 1))
    mode = opt("--mode", "pressure")
    failed = 0
    for name in sorted(MODES) if which == "all" else [which]:
        fn, default_n = MODES[name]
        failed += fn(int(opt("--n", default_n)), seed, mode)
    print("fuzz: %s" % ("FAILED (%d problem(s))" % failed if failed else "OK"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
