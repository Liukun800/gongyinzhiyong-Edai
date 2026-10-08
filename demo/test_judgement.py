"""Adapter integration and failure tests. Doubles are not quality evidence."""
import copy
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app import Store, ApiError, create_server
from judgement import VersionedJudgement, specs, API_VERSION
from judgement_http import HttpJudgement
from judgement_service import create_judgement_server
from product_contract import build_handoff
from shadow_engine import ShadowEngine, QUESTIONS
from engine import ANSWERS


class BankDouble:
    def __init__(self):
        self.calls = []
        self.delay = 0
        self.fail = False

    def info(self):
        return {'name': 'integration-test-double', 'domain_validation': 'not_verified'}

    def decide_many(self, requests):
        self.calls.append(copy.deepcopy(requests))
        time.sleep(self.delay)
        if self.fail:
            raise RuntimeError('injected predictor failure')
        return [{'answer': c[0], 'score': .6, 'distribution': dict(zip(c, [.6, .25, .15])),
                 'candidate_paths': 3, 'input_path_tokens': 50, 'generated_tokens': 0,
                 'wall_ms': 1.0} for _, _, c in requests]


class JudgementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.predictor = BankDouble()
        self.token = 'unit-test-only-token-' + 'a' * 32
        self.server = create_judgement_server(self.predictor, self.token, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.client = HttpJudgement(self.url, self.token)
        self.store = Store(Path(self.tmp.name) / 'app.sqlite3', ShadowEngine(self.client))
        self.state = {'materials': [
            {'subject': '仿真企业', 'period': '2026年9月', 'paragraphs': ['营业材料A']},
            {'subject': '仿真企业', 'period': '2026年9月', 'paragraphs': ['营业材料B']} ]}

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.store.db.close()
        self.tmp.cleanup()

    def request(self, task='USE_MATCH'):
        return (self.state, QUESTIONS[task], ANSWERS[task])

    def post(self, body, headers=None):
        req = Request(self.url + '/api/judge', data=json.dumps(body).encode(), headers={
            'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json', **(headers or {})})
        return json.load(urlopen(req, timeout=2))

    def body(self):
        spec = specs()[0]
        return {'api_version': API_VERSION, 'id': 'test', 'questions': [{
            'id': spec['id'], 'version': spec['version'], 'question_sha256': spec['question_sha256'],
            'state': self.state}]}

    def test_local_and_http_preserve_outputs_batch_and_provenance(self):
        requests = [self.request('BIZ_CONFLICT'), self.request()]
        local = VersionedJudgement(self.predictor).decide_many(requests)
        remote = self.client.decide_many(requests)
        self.assertEqual(local, remote)
        self.assertEqual(len(self.predictor.calls[-1]), 2)
        self.assertEqual([r['decision_record']['spec_id'] for r in remote], ['BIZ_CONFLICT', 'USE_MATCH'])

    def test_service_rejects_labels_unknown_versions_and_duplicates_before_call(self):
        variants = []
        b = self.body(); b['questions'][0]['state']['label'] = '一致'; variants.append(b)
        # body() shares self.state; restore it after explicit leak test.
        self.state.pop('label')
        variants[0]['questions'][0]['state'] = {**self.state, 'label': '一致'}
        b = self.body(); b['questions'][0]['id'] = 'LOAN_APPROVE'; variants.append(b)
        b = self.body(); b['questions'][0]['version'] = '2.0.0'; variants.append(b)
        b = self.body(); b['questions'][0]['question_sha256'] = 'wrong'; variants.append(b)
        b = self.body(); b['questions'] *= 2; variants.append(b)
        b = self.body(); b['expected_answer'] = '一致'; variants.append(b)
        for body in variants:
            with self.subTest(body=body), self.assertRaises(HTTPError) as error:
                self.post(body)
            self.assertEqual(error.exception.code, 400)
        self.assertEqual(self.predictor.calls, [])

    def test_auth_origin_and_external_address_rejected(self):
        with self.assertRaises(HTTPError):
            HttpJudgement(self.url, 'x' * 32)
        with self.assertRaises(HTTPError):
            self.post(self.body(), {'Origin': 'http://unrelated.example'})
        for address in ['http://example.com:8148', self.url + '/other', 'http://localhost:8148']:
            with self.assertRaises(ValueError):
                HttpJudgement(address, self.token)
        self.assertEqual(self.predictor.calls, [])

    def test_batch_answer_order_can_change_without_swapping_tasks(self):
        original = self.client._request
        def reversed_answers(path, body=None):
            r = original(path, body)
            r['answers'].reverse()
            return r
        self.client._request = reversed_answers
        r = self.client.decide_many([self.request(), self.request('BIZ_CONFLICT')])
        self.assertEqual([p['decision_record']['spec_id'] for p in r], ['USE_MATCH', 'BIZ_CONFLICT'])

    def test_bad_responses_retain_human_tasks_no_fixture(self):
        original = self.client._request
        mutations = [
            lambda r: r.update(id='wrong'),
            lambda r: r['model'].update(name='different-checkpoint'),
            lambda r: r['answers'][0].update(version='old'),
            lambda r: r['answers'][0]['prediction'].update(score=.9),
            lambda r: r['answers'][0]['prediction']['distribution'].update({'一致': float('nan')}),
            lambda r: r['answers'][0]['prediction']['decision_record'].update(state_sha256='wrong'),
            lambda r: r['answers'][0]['prediction'].update(generated_tokens=5),
            lambda r: r.update(answers=[r['answers'][0], r['answers'][0]])]
        for mutate in mutations:
            def bad(path, body=None):
                r = original(path, body); mutate(r); return r
            self.client._request = bad
            with self.subTest(mutate=mutate), self.assertLogs(level='ERROR'):
                result = self.store.run('D01', {'revision': 1})
            self.assertTrue(all(t['answer'] is None and t['action'] == 'human' for t in result['tasks']))
            self.assertEqual(result['usage']['successful_model_requests'], 0)

    def test_input_guard_skips_service_and_only_clean_materials_are_sent(self):
        result = self.store.run('D03', {'revision': 1})
        self.assertEqual(result['tasks'][0]['source'], 'input_rule')
        self.assertEqual(len(self.predictor.calls), 1)
        self.assertEqual(len(self.predictor.calls[0]), 1)
        for state, _, _ in self.predictor.calls[0]:
            self.assertEqual(set(state), {'materials'})
            self.assertTrue(all(set(d) == {'subject', 'period', 'paragraphs'} for d in state['materials']))

    def test_predictor_failure_and_http_timeout_keep_unresolved_tasks(self):
        self.predictor.fail = True
        with self.assertLogs(level='ERROR'):
            r = self.store.run('D01', {'revision': 1})
        self.assertTrue(all(t['answer'] is None and t['action'] == 'human' for t in r['tasks']))
        self.predictor.fail = False
        self.predictor.delay = .1
        self.client.timeout = .02
        before = len(self.predictor.calls)
        with self.assertLogs(level='ERROR'):
            r = self.store.run('D01', {'revision': 1})
        self.assertEqual(len(self.predictor.calls), before + 1)  # no hidden retry
        self.assertEqual(r['usage']['failed_model_requests'], 2)
        self.assertEqual(len(build_handoff(self.store.detail('D01'))['unresolved_tasks']), 2)

    def test_service_disconnection_fails_to_human(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        with self.assertLogs(level='ERROR'):
            r = self.store.run('D01', {'revision': 1})
        self.assertTrue(all(t['answer'] is None and t['action'] == 'human' for t in r['tasks']))

    def test_supplement_revision_review_and_handoff_preserve_audit(self):
        old = self.store.run('D03', {'revision': 1})
        case = self.store.detail('D03')['case']
        self.store.material('D03', {'revision': 1, 'document': case['supplement']})
        new = self.store.run('D03', {'revision': 2})
        self.assertEqual(len(self.predictor.calls[-1]), 2)
        with self.assertRaises(ApiError):
            self.store.review(old['id'], {'revision': 2, 'task_id': 'BIZ_CONFLICT',
                                         'action': 'confirm', 'reason': 'stale'})
        self.store.review(new['id'], {'revision': 2, 'task_id': 'USE_MATCH', 'action': 'confirm',
                                     'reason': '人员核对仿真用途原文'})
        h = build_handoff(self.store.detail('D03'))
        self.assertEqual(h['decision_results'][0]['decision_record']['spec_version'], '1.0.0')
        self.assertIsNone(h['approval_decision'])
        self.assertEqual(len(build_handoff(self.store.detail('D03'), old['id'])['input_snapshot']['materials']), 3)
        saved = Store(Path(self.tmp.name) / 'app.sqlite3', ShadowEngine(self.client))
        try:
            self.assertEqual(saved.detail('D03')['runs'][0]['tasks'][0]['decision_record'],
                             new['tasks'][0]['decision_record'])
        finally:
            saved.db.close()

    def test_audit_storage_failure_rolls_back_run_and_does_not_return_suggestion(self):
        self.store.db.execute("CREATE TRIGGER audit_failure BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT, 'injected storage failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.run('D01', {'revision': 1})
        self.assertEqual(self.store.detail('D01')['runs'], [])
        self.assertEqual(self.store.detail('D01')['events'], [])

    def test_unknown_question_cannot_silently_use_existing_spec(self):
        with self.assertRaises(ValueError):
            self.client.decide(self.state, QUESTIONS['USE_MATCH'] + '额外要求', ANSWERS['USE_MATCH'])
        self.assertEqual(self.predictor.calls, [])

    def test_http_audit_failure_is_visible_and_never_delivers_suggestion(self):
        app = create_server(0, Path(self.tmp.name) / 'audit-http.sqlite3', ShadowEngine(self.client))
        app.store.db.execute("CREATE TRIGGER audit_failure BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT, 'injected'); END")
        thread = threading.Thread(target=app.serve_forever, daemon=True); thread.start()
        base = f'http://127.0.0.1:{app.server_port}'
        try:
            csrf = json.load(urlopen(base + '/api/health'))['csrf_token']
            req = Request(base + '/api/cases/D01/run', data=b'{"revision":1}',
                          headers={'X-Demo-Token': csrf, 'Content-Type': 'application/json'})
            with self.assertRaises(HTTPError) as error:
                urlopen(req)
            self.assertEqual(error.exception.code, 503)
            message = json.load(error.exception)
            self.assertIn('本次建议未采用', message['error'])
            self.assertEqual(app.store.detail('D01')['runs'], [])
        finally:
            app.shutdown(); app.server_close(); thread.join(); app.store.db.close()

    def test_handshake_rejects_changed_task_profile(self):
        from unittest.mock import patch
        bad = copy.deepcopy(self.client.identity)
        bad['decision_specs'][0]['capability'] = 'classify'
        with patch.object(HttpJudgement, '_request', return_value=bad), self.assertRaises(ValueError):
            HttpJudgement(self.url, self.token)


if __name__ == '__main__':
    unittest.main()
