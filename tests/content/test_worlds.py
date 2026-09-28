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

    def test_a_twist_names_only_the_characters_it_requires(self):
        import copy

        pack = copy.deepcopy(STORE.world("harbor_night_shift"))
        other = next(t["id"] for t in pack["character_templates"] if t["id"] not in pack["twists"][0]["requires"])
        pack["twists"][0]["text"] = "{%s.name}在签到簿上多写了一行字" % other
        _normalized, problems = worldpack.validate_world(pack, tag_ids=TAG_IDS)
        hits = [p for p in problems if p["path"] == "$.twists[0].text"]
        self.assertEqual(len(hits), 1, problems)
        self.assertIn(other, hits[0]["hint"])
        pack["twists"][0]["requires"] = pack["twists"][0]["requires"] + [other]
        _normalized, problems = worldpack.validate_world(pack, tag_ids=TAG_IDS)
        self.assertEqual([p for p in problems if p["path"].startswith("$.twists[0]")], [])

    def test_fields_shown_as_written_take_no_placeholders(self):
        import copy

        pack = copy.deepcopy(STORE.world("harbor_night_shift"))
        pack["character_templates"][0]["adult_context"] = "成年人，{npc.ta}持证上岗"
        pack["background_cast"][0]["role"] = "{npc.name}的老搭档"
        pack["daily_activities"][0]["title"] = "{player.name}的宵夜"
        _normalized, problems = worldpack.validate_world(pack, tag_ids=TAG_IDS)
        hits = {p["path"]: p for p in problems if "无法解析" in p["reason"]}
        self.assertEqual(
            set(hits),
            {"$.character_templates[0].adult_context", "$.background_cast[0].role", "$.daily_activities[0].title"},
        )
        self.assertTrue(all("原样显示" in p["hint"] for p in hits.values()))

    def test_fixed_seed_openings_come_from_one_world(self):
        for pack in worlds():
            count, failures = opening_checks.fixed_seed_openings(pack, range(1, 11))
            self.assertEqual(failures, [], pack["id"])
            self.assertEqual(count, 20)
            pools = pack["name_pools"]
            givens = set(pools["given_female"] + pools["given_male"] + pools["given_neutral"])
            entries = {
                "combo_id": {c["id"] for c in pack["cast_combos"]},
                "hook_id": {h["id"] for h in pack["hooks"]},
                "identity_id": {i["id"] for i in pack["player_identities"]},
                "activity_id": {a["id"] for a in pack["daily_activities"]},
                "pressure_id": {p["id"] for p in pack["pressures"]},
                "location_id": {loc["id"] for loc in pack["locations"]},
            }
            for mode in ("daily", "pressure"):
                for seed in range(1, 11):
                    conditions = opening.normalize_conditions({"mode": mode, "locks": {"world_id": pack["id"]}})
                    state, payload = opening.build(pack, seed, conditions, "t")
                    for char in state["characters"].values():
                        if char["family"]:
                            self.assertIn(char["family"], pools["family"])
                            self.assertIn(char["given"], givens)
                    for key, ids in entries.items():
                        if state["opening"].get(key):
                            self.assertIn(state["opening"][key], ids, (pack["id"], mode, seed, key))
                    # Era: nothing the world forbids appears anywhere in what the player is shown.
                    text = json.dumps(payload, ensure_ascii=False)
                    self.assertEqual([t for t in pack["forbidden_terms"] if t in text], [], (pack["id"], mode, seed))
                    self.assertEqual(payload["world"]["era"], pack["era"])

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


class CrossWorldTest(unittest.TestCase):
    """CONTENT_BIBLE 6: near duplicates across packs, the generic layer against every list."""

    def packs(self):
        import copy

        return {w["id"]: copy.deepcopy(w) for w in worlds()}

    def test_a_near_copy_in_another_world_is_reported_at_the_copy(self):
        packs = self.packs()
        source = packs["harbor_night_shift"]["rules"][0]["text"]
        copy_text = source[:-1] + ("了" if source[-1] != "了" else "的")
        packs["winter_shelter"]["rules"][2]["text"] = copy_text
        problems = worldpack.cross_checks(packs, [])
        hits = [p for p in problems if "高度相似" in p["reason"]]
        self.assertEqual(len(hits), 1, hits)
        hit = hits[0]
        self.assertEqual((hit["world"], hit["path"], hit["item"]), ("winter_shelter", "$.rules[2].text", packs["winter_shelter"]["rules"][2]["id"]))
        self.assertIn("harbor_night_shift $.rules[0].text", hit["reason"])

    def test_released_packs_have_no_near_duplicates_or_generic_clashes(self):
        from adult_tension.domain import structure as ST

        generic = ST.generic_strings() + [t["label"] for t in STORE.tags()["tags"]]
        self.assertEqual(worldpack.cross_checks(self.packs(), generic), [])

    def test_a_forbidden_term_in_the_generic_layer_is_reported(self):
        from adult_tension.domain import structure as ST

        packs = self.packs()
        packs["bakumatsu_machiya"]["forbidden_terms"].append("试探")
        problems = worldpack.cross_checks(packs, ST.generic_strings())
        hits = [p for p in problems if p["world"] == "generic"]
        self.assertTrue(hits)
        self.assertIn("bakumatsu_machiya", hits[0]["reason"])


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
            # The entry is named by id as well as by path.
            index = int(hits[0]["path"].split("[", 1)[1].split("]", 1)[0])
            pack = STORE.world("harbor_night_shift")
            remaining = [loc for loc in pack["locations"] if loc["id"] != "tool_shed"]
            self.assertEqual(hits[0]["item"], remaining[index]["id"])

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
