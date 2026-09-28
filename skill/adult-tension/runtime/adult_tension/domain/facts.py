"""The session's facts: read on demand, written copy-on-write.

Facts are never deleted (RUNTIME_PROTOCOL 7), so they are the one part of a
game that grows with its length. To keep a commit's cost independent of the
game's length they are not part of the per-turn state blob: storage keeps
them as rows and puts a *source* in state["facts"]; a commit reads through a
FactView and records its changes there. A plain dict of facts is also a
valid state["facts"] (openings, slots, tests, in-memory play).

Every source answers the same questions (FactsAPI):
    get(fid)                 one fact or None
    by_key(key)              facts with that key
    known_to(cid)            facts cid knows or (mis)believes
    spreading()              facts still spreading (never inner ones)
    player_ranked(...)       the player's facts, most relevant first
    all()                    every fact
Lists are ordered by creation (the number in the id). Facts handed out are
read-only; a commit changes a fact only through FactView.edit().
"""

from ..jsonio import copy

RECENT_TURNS = 5


def order(fact):
    return int(fact["id"][1:])


def knows(fact, cid):
    return cid in fact["known_by"] or cid in fact["believed_by"]


def player_score(fact, present_ids, present_names, recent_turn):
    """Relevance of a fact the player knows, for the bounded context lists."""
    head = fact["key"].split(".", 1)[0]
    score = 0
    if head in present_ids or any(name and name in fact["text"] for name in present_names):
        score += 3
    if fact["turn"] >= recent_turn:
        score += 2
    if fact["origin"] == "setup" and head == "player":
        score -= 1
    return score


def rank_key(present_ids, present_names, recent_turn):
    return lambda f: (-player_score(f, present_ids, present_names, recent_turn), -f["turn"], order(f))


class FactsAPI:
    """Mapping sugar over get() and all(), shared by every source."""

    def __getitem__(self, fid):
        fact = self.get(fid)
        if fact is None:
            raise KeyError(fid)
        return fact

    def __contains__(self, fid):
        return self.get(fid) is not None

    def values(self):
        return self.all()

    def items(self):
        return [(f["id"], f) for f in self.all()]

    def keys(self):
        return [f["id"] for f in self.all()]

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self.all())

    def as_dict(self):
        return {f["id"]: f for f in self.all()}


class DictSource(FactsAPI):
    """Facts held in a plain dict, answered by scanning."""

    def __init__(self, facts):
        self.facts = facts

    def get(self, fid, default=None):
        return self.facts.get(fid, default)

    def all(self):
        return sorted(self.facts.values(), key=order)

    def by_key(self, key):
        return sorted((f for f in self.facts.values() if f["key"] == key), key=order)

    def known_to(self, cid):
        return sorted((f for f in self.facts.values() if knows(f, cid)), key=order)

    def spreading(self):
        return sorted((f for f in self.facts.values() if f.get("spreading") and f["visibility"] != "inner"), key=order)

    def player_ranked(self, player, present_ids, present_names, recent_turn, limit=None, exclude=()):
        found = [f for f in self.facts.values() if knows(f, player) and f["id"] not in exclude]
        found.sort(key=rank_key(present_ids, present_names, recent_turn))
        return found[:limit] if limit else found


def of(state):
    """The FactsAPI for a state's facts, whatever holds them."""
    facts = state["facts"]
    return DictSource(facts) if isinstance(facts, dict) else facts


class FactView(FactsAPI):
    """One commit's copy-on-write view over a source.

    New facts and edited copies live in `changed`; the source is never
    touched. `before` keeps the original of every edited fact (None for new
    ones) so storage can journal the turn for undo.
    """

    def __init__(self, source):
        self.source = DictSource(source) if isinstance(source, dict) else source
        self.changed = {}
        self.before = {}

    def get(self, fid, default=None):
        if fid in self.changed:
            return self.changed[fid]
        fact = self.source.get(fid)
        return default if fact is None else fact

    def __setitem__(self, fid, fact):
        if self.get(fid) is not None:
            raise KeyError("fact id reused: %s" % fid)
        self.changed[fid] = fact
        self.before[fid] = None

    def edit(self, fid):
        """A mutable copy of an existing fact, recorded as changed."""
        if fid not in self.changed:
            original = self.source.get(fid)
            if original is None:
                raise KeyError(fid)
            self.before[fid] = original
            self.changed[fid] = copy(original)
        return self.changed[fid]

    def _merge(self, found, keep):
        out = {f["id"]: f for f in found if f["id"] not in self.changed}
        for fid, fact in self.changed.items():
            if keep(fact):
                out[fid] = fact
        return sorted(out.values(), key=order)

    def all(self):
        return self._merge(self.source.all(), lambda f: True)

    def by_key(self, key):
        return self._merge(self.source.by_key(key), lambda f: f["key"] == key)

    def known_to(self, cid):
        return self._merge(self.source.known_to(cid), lambda f: knows(f, cid))

    def spreading(self):
        return self._merge(self.source.spreading(), lambda f: f.get("spreading") and f["visibility"] != "inner")

    def player_ranked(self, player, present_ids, present_names, recent_turn, limit=None, exclude=()):
        skip = set(exclude) | set(self.changed)
        wanted = None if limit is None else limit + len(self.changed)
        found = self.source.player_ranked(player, present_ids, present_names, recent_turn, wanted, tuple(sorted(skip)))
        found += [f for fid, f in self.changed.items() if knows(f, player) and fid not in exclude]
        found.sort(key=rank_key(present_ids, present_names, recent_turn))
        return found[:limit] if limit else found

    def changed_facts(self):
        return [self.changed[fid] for fid in sorted(self.changed, key=lambda i: int(i[1:]))]

    def settle(self):
        """End of a commit: a dict source becomes a plain dict again; storage
        sources stay a view so the application can write the changes."""
        if isinstance(self.source, DictSource):
            merged = dict(self.source.facts)
            merged.update(self.changed)
            return {fid: merged[fid] for fid in sorted(merged, key=lambda i: int(i[1:]))}
        return self


def edit(state, fid):
    """A fact to change: the view's copy during a commit; a plain dict state
    (owned by the caller) is changed in place."""
    facts = state["facts"]
    return facts[fid] if isinstance(facts, dict) else facts.edit(fid)


def working_copy(state):
    """A copy of the state for one commit: the rest is deep-copied, the facts
    are viewed copy-on-write."""
    work = copy({k: v for k, v in state.items() if k != "facts"})
    work["facts"] = FactView(state["facts"])
    return work


def full_state(state):
    """The state with its facts as a plain dict (for slots, exports, digests)."""
    out = {k: v for k, v in state.items() if k != "facts"}
    out["facts"] = of(state).as_dict()
    return out
