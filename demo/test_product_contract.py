import tempfile, unittest, copy
from pathlib import Path
from app import Store
from product_contract import build_handoff, development_summary
class HandoffTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=Store(Path(self.tmp.name)/'test.sqlite3')
 def tearDown(self):self.s.db.close();self.tmp.cleanup()
 def test_no_run_cannot_fabricate_handoff(self):
  with self.assertRaises(ValueError):build_handoff(self.s.detail('D01'))
 def test_normal_review_is_not_loan_approval(self):
  r=self.s.run('D01',{'revision':1})
  for t in r['tasks']:self.s.review(r['id'],{'revision':1,'task_id':t['id'],'action':'confirm','reason':'逐项核对原文与任务范围'})
  h=build_handoff(self.s.detail('D01'));self.assertEqual(h['unresolved_tasks'],[]);self.assertFalse(h['bank_connected']);self.assertIsNone(h['approval_decision']);self.assertIsNone(h['loan_amount'])
 def test_conflict_remains_business_issue_after_recording(self):
  r=self.s.run('D02',{'revision':1});self.s.review(r['id'],{'revision':1,'task_id':'BIZ_CONFLICT','action':'resolve','corrected_answer':'发现明确矛盾','reason':'确认材料冲突，须继续业务核实'})
  h=build_handoff(self.s.detail('D02'));t=next(t for t in h['decision_results'] if t['task_id']=='BIZ_CONFLICT');self.assertTrue(any('明确矛盾' in v for v in t['unresolved_reasons']))
 def test_historical_export_preserves_own_material_snapshot(self):
  old=self.s.run('D03',{'revision':1});c=self.s.detail('D03')['case'];self.s.material('D03',{'revision':1,'document':c['supplement']});self.s.run('D03',{'revision':2});h=build_handoff(self.s.detail('D03'),old['id']);self.assertFalse(h['application_context']['is_latest_run']);self.assertEqual(len(h['input_snapshot']['materials']),3);self.assertTrue(h['unresolved_tasks'])
 def test_effective_answer_and_original_remain_separate(self):
  r=self.s.run('D01',{'revision':1});self.s.review(r['id'],{'revision':1,'task_id':'USE_MATCH','action':'correct','corrected_answer':'信息不足','reason':'复核后发现需要额外用途证明'})
  t=build_handoff(self.s.detail('D01'))['decision_results'][0];self.assertEqual(t['original_answer'],'一致');self.assertEqual(t['effective_answer'],'信息不足');self.assertEqual(t['status'],'待补充')
 def test_development_summary_does_not_mix_prepared_and_tested(self):
  d=development_summary(Path(__file__).parent);self.assertEqual(d['evaluated_cases'],24);self.assertEqual(d['prepared_development_pool'],54);self.assertEqual([s['agreement'] for s in d['systems']],[6,8,17]);self.assertEqual(d['systems'][0]['abstained'],18);self.assertEqual(len(d['errors']),7);self.assertEqual(sum(d['actions'].values()),24);self.assertEqual(d['actual_complex_requests'],0)
if __name__=='__main__':unittest.main()

