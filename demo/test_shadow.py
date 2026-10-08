import copy
import json
import logging
import tempfile
import threading
import time
import unittest
from pathlib import Path

from app import Store, ApiError
from shadow_engine import ShadowEngine


class FakePredictor:
    """Test double only, not shipped as model output."""
    def __init__(self, fail=False):
        self.calls=[]
        self.fail=fail
        self.batch_calls=[]
        self.started=threading.Event()
        self.release=threading.Event()
        self.pause=0

    def info(self):
        return {'name':'unit-test-double'}

    def decide(self, state, question, candidates):
        self.calls.append((copy.deepcopy(state),question,list(candidates)))
        if self.pause:
            self.started.set()
            self.release.wait(3)
            time.sleep(self.pause)
        if self.fail:
            raise RuntimeError('test injected failure')
        return {'answer':candidates[0], 'score':.6, 'distribution':dict(zip(candidates,[.6,.25,.15])),
                'candidate_paths':3,'input_path_tokens':50,'generated_tokens':0,'wall_ms':1.}

    def decide_many(self, requests):
        self.batch_calls.append(len(requests))
        return [self.decide(*request) for request in requests]


class ShadowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.predictor=FakePredictor()
        self.store=Store(Path(self.temp.name)/'test.sqlite3',ShadowEngine(self.predictor))

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def test_annotations_are_not_read_and_ids_not_sent(self):
        self.store.annotations={}
        r=self.store.run('D01',{'revision':1})
        self.assertEqual(r['usage']['actual_model_requests'],2)
        self.assertEqual(r['usage']['successful_model_requests'],2)
        for state,_,_ in self.predictor.calls:
            self.assertEqual(set(state),{'materials'})
            self.assertEqual(set(state['materials'][0]),{'subject','period','paragraphs'})
            self.assertNotIn('fixture',json.dumps(state))
        self.assertTrue(all(t['status']!='已完成核验' for t in r['tasks']))
        self.assertEqual(self.predictor.batch_calls,[2])

    def test_input_checks_skip_model(self):
        r=self.store.run('D03',{'revision':1})
        self.assertEqual(r['tasks'][0]['source'],'input_rule')
        self.assertEqual(r['usage']['actual_model_requests'],1)

    def test_slow_inference_does_not_hold_store_lock_or_interrupt_other_case(self):
        self.predictor.pause=.15
        errors=[]
        worker=threading.Thread(target=lambda: self._run_catching(errors),daemon=True)
        worker.start()
        self.assertTrue(self.predictor.started.wait(2))
        started=time.perf_counter()
        other=self.store.detail('D02')
        changed=copy.deepcopy(other['case']['documents'][0])
        changed['paragraphs'][0]['text']='另一申请的安全编辑可在推理期间完成。'
        updated=self.store.material('D02',{'revision':1,'document':changed})
        elapsed=time.perf_counter()-started
        self.assertEqual(updated['revision'],2)
        self.assertLess(elapsed,.15)
        self.predictor.release.set()
        worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors,[])
        self.assertEqual(self.store.detail('D01')['runs'][0]['revision'],1)
        self.assertEqual(self.store.detail('D02')['case']['revision'],2)

    def _run_catching(self, errors):
        try:
            self.store.run('D01',{'revision':1})
        except Exception as exc:
            errors.append(exc)
        r=self.store.run('D04',{'revision':1})
        self.assertEqual(r['tasks'][1]['answer'],'无法比较')
        self.assertEqual(r['usage']['actual_model_requests'],1)

    def test_changed_material_is_sent_to_predictor(self):
        c=self.store.detail('D01')['case'];d=copy.deepcopy(c['documents'][0])
        d['paragraphs'][0]['text']='新的申请用途：购置运输车辆。'
        self.store.material('D01',{'revision':1,'document':d})
        r=self.store.run('D01',{'revision':2})
        self.assertEqual(r['tasks'][0]['source'],'agentjev_public_shadow')
        self.assertIn('购置运输车辆',json.dumps(self.predictor.calls[0][0],ensure_ascii=False))

    def test_model_failure_never_falls_back_to_fixture(self):
        self.predictor.fail=True
        with self.assertLogs(level='ERROR'):
            r=self.store.run('D01',{'revision':1})
        self.assertEqual(r['usage']['failed_model_requests'],2)
        self.assertTrue(all(t['answer'] is None and t['source']=='model_error' for t in r['tasks']))

    def test_same_material_different_case_does_not_force_scenario(self):
        a=self.store.run('D05',{'revision':1});b=self.store.run('D06',{'revision':1})
        self.assertEqual([t['answer'] for t in a['tasks']],[t['answer'] for t in b['tasks']])
        self.assertEqual(a['usage']['simulated_analysis_requests'],0)
        self.assertEqual(b['usage']['simulated_analysis_requests'],0)

    def test_latest_manual_state_controls_next_action(self):
        r=self.store.run('D01',{'revision':1})
        self.store.review(r['id'],{'revision':1,'task_id':'USE_MATCH','action':'supplement','reason':'仍需要其他证明材料'})
        with self.assertRaises(ApiError):
            self.store.review(r['id'],{'revision':1,'task_id':'USE_MATCH','action':'confirm','reason':'不能跳过待补充状态'})

    def test_manual_answer_survives_referral(self):
        r = self.store.run('D01', {'revision': 1})
        self.store.review(r['id'], {'revision': 1, 'task_id': 'USE_MATCH', 'action': 'correct',
                                  'corrected_answer': '存在明确矛盾', 'reason': '人工核对原文发现矛盾'})
        r = self.store.review(r['id'], {'revision': 1, 'task_id': 'USE_MATCH', 'action': 'refer',
                                       'reason': '转交人员进一步核实'})
        self.assertEqual(r['tasks'][0]['review']['answer'], '存在明确矛盾')
        self.assertEqual(r['tasks'][0]['answer'], '一致')

    def test_invalid_material_kind_is_rejected(self):
        d = copy.deepcopy(self.store.detail('D01')['case']['documents'][0])
        d['kind'] = 'purpoes'
        with self.assertRaises(ApiError):
            self.store.material('D01', {'revision': 1, 'document': d})

    def test_malformed_prediction_fails_closed(self):
        original = self.predictor.decide
        for distribution in ({'一致': float('nan'), '存在明确矛盾': .25, '信息不足': .15},
                             {'一致': .8, '存在明确矛盾': .25, '信息不足': .15},
                             {'一致': .1, '存在明确矛盾': .75, '信息不足': .15}):
            with self.subTest(distribution=distribution):
                def corrupt(state, question, candidates):
                    result = original(state, question, candidates)
                    result['distribution'] = distribution
                    return result
                self.predictor.decide = corrupt
                with self.assertLogs(level='ERROR'):
                    r = self.store.run('D01', {'revision': 1})
                self.assertTrue(all(t['answer'] is None and t['action'] == 'human' for t in r['tasks']))
                self.assertEqual(r['usage']['successful_model_requests'], 0)

    def test_probe_is_label_free_and_does_not_modify_workstation(self):
        before = self.store.detail('D01')
        body = {'documents': before['case']['documents'], 'task_ids': ['BIZ_CONFLICT']}
        result = self.store.shadow_probe(body)
        self.assertEqual(len(result['tasks']), 1)
        self.assertEqual(result['tasks'][0]['id'], 'BIZ_CONFLICT')
        self.assertEqual(self.store.detail('D01'), before)
        with self.assertRaises(ApiError):
            self.store.shadow_probe({**body, 'expected_answer': '发现明确矛盾'})
        with self.assertRaises(ApiError):
            self.store.shadow_probe({**body, 'task_ids': ['INVALID']})
        with self.assertRaises(ApiError):
            self.store.shadow_probe({**body, 'documents': [body['documents'][0]] * 2})


if __name__=='__main__':
    unittest.main(verbosity=2)
