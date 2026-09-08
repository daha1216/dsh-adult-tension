from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MaterialPairingTests(unittest.TestCase):
    def test_repository_pairing_check(self):
        result = subprocess.run([sys.executable, "-X", "utf8", "scripts/check_material_compatibility.py", "--summary"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, result.returncode, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(0, summary["errors"])
        self.assertGreater(summary["declared_pairings"], 0)
        self.assertEqual(summary["legacy_pool_items"], sum(summary["legacy_pool_status"].values()))
        self.assertGreater(summary["legacy_pool_status"].get("UNMAPPED", 0), 0)

    def test_false_provenance_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "data"
            shutil.copytree(ROOT / "scripts/data", data)
            code = """
import json,sys,yaml
from pathlib import Path
sys.path.insert(0, 'scripts')
from check_material_compatibility import audit
p=Path(sys.argv[1])/'world_frameworks.yaml'
d=yaml.safe_load(p.read_text(encoding='utf-8'))
row=next(iter(d['frameworks'].values()))
row.setdefault('legacy_sources', {})['places']=['not-a-real-place']
p.write_text(yaml.safe_dump(d,allow_unicode=True,sort_keys=False),encoding='utf-8')
r=audit(Path(sys.argv[1]))
print(json.dumps(r['errors']))
"""
            result = subprocess.run([sys.executable, "-X", "utf8", "-c", code, str(data)], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(any("not-a-real-place" in error for error in json.loads(result.stdout)))


if __name__ == "__main__":
    unittest.main()
