"""Content gates: validator, fixed-seed openings, diversity, compiler determinism."""

import json
import os
import unittest

import _bootstrap  # noqa: F401
import compile_content
from adult_tension.domain import opening, opening_checks, worldpack
from helpers.cli import clean_env, run_cli
from helpers.domain import STORE
from helpers.fs import copy_skill, temp_dir

TAG_IDS = {t["id"] for t in STORE.tags()["tags"]}


def worlds():
    return [STORE.world(entry["id"]) for entry in STORE.index()["worlds"]]


class WorldPackTest(unittest.TestCase):
    def test_every_compiled_world_passes_the_validator(self):
        for pack in worlds():
            _normalized, problems = worldpack.validate_world(pack, tag_ids=TAG_IDS)
            self.assertEqual(problems, [], pack["id"])

    def test_underage_templates_are_rejected_with_their_path(self):
        import copy

        pack = copy.deepcopy(STORE.world("harbor_night_shift"))
        pack["character_templates"][2]["age_range"] = [16, 30]
        pack["background_cast"][0]["age_range"] = [17, 40]
        pack["player_identities"][1]["age_range"] = [15, 40]
        _normalized, problems = worldpack.validate_world(pack, tag_ids=TAG_IDS)
        paths = {p["path"] for p in problems if "小于 18" in p["reason"]}
        self.assertEqual(
            paths,
            {"$.character_templates[2].age_range", "$.background_cast[0].age_range", "$.player_identities[1].age_range"},
        )

    def test_fixed_seed_openings_come_from_one_world(self):
        for pack in worlds():
            count, failures = opening_checks.fixed_seed_openings(pack, range(1, 11))
            self.assertEqual(failures, [], pack["id"])
            self.assertEqual(count, 20)
            pools = pack["name_pools"]
            givens = set(pools["given_female"] + pools["given_male"] + pools["given_neutral"])
            for mode in ("daily", "pressure"):
                for seed in range(1, 11):
                    conditions = opening.normalize_conditions({"mode": mode, "locks": {"world_id": pack["id"]}})
                    state, _payload = opening.build(pack, seed, conditions, "t")
                    for char in state["characters"].values():
                        if char["family"]:
                            self.assertIn(char["family"], pools["family"])
                            self.assertIn(char["given"], givens)

    def test_diversity_gate(self):
        for pack in worlds():
            for mode in ("daily", "pressure"):
                for base in (1, 2, 3):
                    result = opening_checks.diversity(pack, mode, base)
                    self.assertTrue(result["pass"], json.dumps(result, ensure_ascii=False))

    def test_verify_content_command_passes(self):
        with temp_dir() as tmp:
            code, env, _raw = run_cli(["verify-content"], os.path.join(tmp, "d"))
            self.assertEqual(code, 0, json.dumps(env, ensure_ascii=False)[:2000])
            self.assertTrue(env["data"]["ok"])


class CompilerTest(unittest.TestCase):
    def test_compiled_files_are_current_and_deterministic(self):
        first, problems = compile_content.compile_all()
        self.assertEqual(problems, [])
        second, _ = compile_content.compile_all()
        self.assertEqual(first, second)
        for rel, data in first.items():
            with open(os.path.join(compile_content.OUT, rel), "rb") as handle:
                self.assertEqual(handle.read(), data, rel)


class ReverseVerificationTest(unittest.TestCase):
    """ACCEPTANCE.md 7: broken content must be caught and located."""

    def tamper(self, skill_dir, world_id, mutate):
        path = os.path.join(skill_dir, "content", "worlds", world_id + ".json")
        with open(path, encoding="utf-8") as handle:
            pack = json.load(handle)
        mutate(pack)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(pack, handle, ensure_ascii=False)

    def verify(self, skill_dir, tmp):
        entry = os.path.join(skill_dir, "scripts", "adult_tension.py")
        return run_cli(["verify-content", "--skip-diversity"], os.path.join(tmp, "d"), entry=entry, env=clean_env())

    def test_deleting_a_referenced_location_fails_with_its_location(self):
        with temp_dir() as tmp:
            skill = copy_skill(tmp)
            self.tamper(skill, "harbor_night_shift", lambda p: p.update(locations=[loc for loc in p["locations"] if loc["id"] != "tool_shed"]))
            code, env, _raw = self.verify(skill, tmp)
            self.assertEqual((code, env["error"]["code"]), (10, "CONTENT_ERROR"))
            hits = [d for d in env["error"]["details"] if "tool_shed" in d["reason"]]
            self.assertTrue(hits)
            self.assertEqual(hits[0]["world"], "harbor_night_shift")
            self.assertTrue(hits[0]["path"].startswith("$.locations["))

    def test_anachronistic_word_fails_the_era_scan(self):
        with temp_dir() as tmp:
            skill = copy_skill(tmp)

            def mutate(pack):
                pack["locations"][0]["name"] = "扫码取件点"

            self.tamper(skill, "harbor_night_shift", mutate)
            code, env, _raw = self.verify(skill, tmp)
            self.assertEqual(code, 10)
            hits = [d for d in env["error"]["details"] if "禁用词" in d["reason"]]
            self.assertEqual(hits[0]["path"], "$.locations[0].name")


if __name__ == "__main__":
    unittest.main()
