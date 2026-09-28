"""Content tools (CONTENT_BIBLE 8.2): new-world, verify-content --file, preview-openings."""

import contextlib
import io
import json
import os
import unittest

import _bootstrap  # noqa: F401
import new_world
import preview_openings
from adult_tension.application import service
from helpers.cli import REPO_ROOT, run_cli
from helpers.domain import STORE
from helpers.fs import temp_dir
from helpers.service import Ids, app

EXAMPLE = os.path.join(REPO_ROOT, "content-src", "examples", "custom_world.json")
POOLS = ("family", "given_female", "given_male", "given_neutral", "nickname_patterns")


def quiet(func, *args):
    with contextlib.redirect_stdout(io.StringIO()) as out:
        code = func(*args)
    return code, out.getvalue()


def described(payload, row_key):
    """The preview's one-line rendering of a new-game payload part."""
    if row_key == "player":
        p = payload["player"]
        return "%s（%s，%d 岁，%s）" % (p["name"], p["role"], p["age"], p["social_position"])
    return ["%s（%s，%d 岁，%s）" % (n["name"], n["role"], n["age"], n["gender"]) for n in payload["npcs"]]


class NewWorldTest(unittest.TestCase):
    def test_a_skeleton_fails_verification_only_for_missing_content(self):
        with temp_dir() as tmp:
            args = ["demo_world", "--title", "演示", "--era", "当代", "--region", "某城", "--dir", tmp]
            self.assertEqual(quiet(new_world.main, args)[0], 0)
            path = os.path.join(tmp, "demo_world.json")
            code, env, _raw = run_cli(["verify-content", "--file", path], os.path.join(tmp, "d"))
            self.assertEqual((code, env["error"]["code"]), (10, "CONTENT_ERROR"))
            allowed = {"$." + f for f in new_world.LIST_FIELDS} | {"$.name_pools." + k for k in POOLS}
            details = env["error"]["details"]
            self.assertTrue(details)
            for d in details:
                self.assertIn(d["path"], allowed, d)
                self.assertTrue(any(w in d["reason"] for w in ("数量不足", "覆盖", "至少")), d)
                self.assertEqual(d["world"], "demo_world")
            # No overwrite without --force; ids are checked.
            self.assertEqual(quiet(new_world.main, args)[0], 2)
            self.assertEqual(quiet(new_world.main, args + ["--force"])[0], 0)
            self.assertEqual(quiet(new_world.main, ["Demo-World"] + args[1:])[0], 2)


class VerifyFileTest(unittest.TestCase):
    def test_the_custom_example_verifies_with_its_openings(self):
        with temp_dir() as tmp:
            code, env, _raw = run_cli(["verify-content", "--file", EXAMPLE], os.path.join(tmp, "d"))
            self.assertEqual(code, 0, json.dumps(env, ensure_ascii=False)[:1500])
            self.assertEqual(env["data"]["world"], "custom_guesthouse")
            self.assertEqual(env["data"]["fixed_seed_openings"], {"count": 20, "failures": []})

    def test_a_broken_file_is_reported_with_paths_and_a_missing_file_is_named(self):
        with open(EXAMPLE, encoding="utf-8") as handle:
            world = json.load(handle)
        world["locations"][1]["exits"] = ["cellar"]
        world["character_templates"][0]["age_range"] = [17, 30]
        with temp_dir() as tmp:
            path = os.path.join(tmp, "broken.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(world, handle, ensure_ascii=False)
            code, env, _raw = run_cli(["verify-content", "--file", path], os.path.join(tmp, "d"))
            self.assertEqual((code, env["error"]["code"]), (10, "CONTENT_ERROR"))
            found = {d["path"] for d in env["error"]["details"]}
            self.assertTrue({"$.locations[1].exits[0]", "$.character_templates[0].age_range"} <= found, found)
            code, env, _raw = run_cli(["verify-content", "--file", os.path.join(tmp, "nope.json")], os.path.join(tmp, "d"))
            self.assertEqual((code, env["error"]["details"][0]["path"]), (10, "$.file"))


class PreviewTest(unittest.TestCase):
    def test_preview_shows_what_new_game_opens_with_the_same_seed(self):
        pack = STORE.world("harbor_night_shift")
        version = STORE.index()["content_version"]
        with open(EXAMPLE, encoding="utf-8") as handle:
            custom = json.load(handle)
        custom_pack, _version = preview_openings.load_pack(None, EXAMPLE)
        with app() as ctx:
            ids = Ids()
            for mode in ("daily", "pressure"):
                for seed in (1, 2, 3):
                    row = preview_openings.preview(pack, version, mode, seed)
                    out = service.new_game(ctx, {"request_id": ids(), "mode": mode, "seed": seed, "include_drafts": True, "locks": {"world_id": pack["id"]}})
                    self.check(row, out["opening"])
                    row = preview_openings.preview(custom_pack, version, mode, seed)
                    out = service.new_game(ctx, {"request_id": ids(), "mode": mode, "seed": seed, "custom_world": custom})
                    self.check(row, out["opening"])

    def check(self, row, payload):
        self.assertEqual(row["signature"], payload["signature"])
        self.assertEqual(row["location"], payload["scene"]["location"])
        self.assertEqual(row["player"], described(payload, "player"))
        self.assertEqual(row["npcs"], described(payload, "npcs"))
        self.assertEqual(row["hook"], "%s：%s" % (payload["hook"]["kind"], payload["hook"]["text"]))

    def test_the_command_line_prints_each_seed(self):
        code, text = quiet(preview_openings.main, ["--world", "harbor_night_shift", "--mode", "pressure", "--seeds", "2", "--start", "5"])
        self.assertEqual(code, 0)
        self.assertEqual([line.split()[1] for line in text.splitlines() if line.startswith("种子")], ["5", "6"])
        code, text = quiet(preview_openings.main, ["--world", "x", "--mode", "daily", "--file", EXAMPLE, "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(text)), 5)


if __name__ == "__main__":
    unittest.main()
