"""Create a real database with the current Skill code, as a migration fixture.

    python tools/make_db_fixture.py <dest_dir> [turns]

Plays a short game (new game, a few turns, one save) through the real write
path and leaves the data directory at <dest_dir>. Run it with the version of
the Skill whose schema should be frozen as a fixture, before changing the
schema; tests then migrate that real database.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _runtime  # noqa: E402

_runtime.use_runtime()

from adult_tension import DB_SCHEMA_VERSION  # noqa: E402
from adult_tension.application import service  # noqa: E402
from adult_tension.application.context import Context  # noqa: E402
from adult_tension.application.fake_narrator import FakeNarrator  # noqa: E402
from adult_tension.persistence import repo  # noqa: E402


def main(argv):
    dest = os.path.abspath(argv[0])
    turns = int(argv[1]) if len(argv) > 1 else 6
    env = {k: v for k, v in os.environ.items() if not k.startswith("ADULT_TENSION")}
    ctx = Context(_runtime.SKILL_ROOT, dest, env, {}, False)
    opened = service.new_game(ctx, {"request_id": "fixture_new_0001", "mode": "pressure", "seed": 2024, "include_drafts": True})
    sid = opened["session_id"]
    narrator = FakeNarrator(2024)
    for index in range(turns):
        info = repo.load_session(ctx.db(), sid)
        commit = narrator.commit(info["state"], info["content"])
        service.commit_turn(ctx, dict(commit, session_id=sid, request_id="fixture_turn_%04d" % index, expected_revision=info["revision"]))
    info = repo.load_session(ctx.db(), sid)
    service.save_slot(ctx, {"session_id": sid, "request_id": "fixture_save_0001", "expected_revision": info["revision"], "name": "旧版本的存档"})
    ctx.close()
    for suffix in ("-wal", "-shm"):
        leftover = os.path.join(dest, "adult_tension.db" + suffix)
        if os.path.exists(leftover):
            raise SystemExit("WAL not checkpointed: %s" % leftover)
    print("schema %d fixture at %s (session %s, turn %d)" % (DB_SCHEMA_VERSION, dest, sid, info["turn"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
