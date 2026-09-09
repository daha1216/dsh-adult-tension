from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from material_inventory import read_yaml
from sync_governance import ORPHANS


class CleanupTests(unittest.TestCase):
    def test_orphan_templates_have_no_pool_or_framework_entry(self):
        pools = read_yaml(ROOT / "scripts/data/pools.yaml")
        templates = read_yaml(ROOT / "scripts/data/templates.yaml")
        self.assertFalse(ORPHANS & set(pools["处境侧"]))
        self.assertFalse(ORPHANS & templates["situation_beats"].keys())
        index = read_yaml(ROOT / "authoring/framework_index.yaml")
        for row in index["frameworks"]:
            material = read_yaml(ROOT / "authoring/frameworks" / f"{row['id']}.yaml")["material"]
            self.assertFalse(ORPHANS & material["pressures"].keys())


if __name__ == "__main__":
    unittest.main()
