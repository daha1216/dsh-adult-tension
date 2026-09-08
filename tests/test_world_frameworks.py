from __future__ import annotations
import importlib.util
import unittest
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
B=load('framework_build','scripts/build_opening.py')
R=load('framework_roll','scripts/roll_opening.py')
F=load('framework_fill','scripts/fill_opening.py')
V=load('framework_validate','scripts/validate_state.py')
class WorldFrameworkTests(unittest.TestCase):
 def test_all_frameworks_support_daily_and_pressure(self):
  pools=R.load_pools(); tables=F.load_tables()
  self.assertGreaterEqual(len(pools['世界框架']), 43)
  for name in pools['世界框架']:
   for mode in ('daily','pressure'):
    roll=B.build_roll(17,{}, {},False,False,mode,name)
    state=F.fill_opening(B.build_skeleton(roll),roll,tables)
    self.assertEqual([],V.validate_data(state,'opening'),(name,mode))
    self.assertEqual(name,state['world']['framework']['name'])
 def test_auto_can_select_framework_and_legacy_is_unchanged(self):
  auto=B.build_roll(1,{}, {},False,False,'daily','auto')
  if auto.get('世界框架'):
   self.assertIn(auto['世界框架'],R.load_pools()['世界框架'])
  legacy=B.build_roll(1,{}, {},False,False,'daily','legacy')
  self.assertIsNone(legacy.get('世界框架'))
 def test_framework_rejects_incompatible_lock(self):
  with patch.object(B, 'load_roll_opening', return_value=R), self.assertRaisesRegex(R.AnchorError, "世界框架"):
   B.build_roll(1,{'地点':'写字楼'}, {},False,False,'daily','仙门山下百业镇')
if __name__=='__main__': unittest.main()
