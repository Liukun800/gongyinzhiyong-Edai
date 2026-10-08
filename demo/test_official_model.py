"""Offline official-provider integration tests; no model-quality claims."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import Store
from engine import ANSWERS
from judgement import digest, spec_for
from official_model import OfficialDecisionModel, OfficialShadowEngine
from official_workbench import create_official_server
from product_contract import build_handoff
from shadow_engine import QUESTIONS
from typesafe_client import JevError, MODEL, configuration, parse_response


class TransportFixture:
    def __init__(self, fail_at=None):
        self.calls = []
        self.fail_at = fail_at

    def __call__(self, state, questions, **kwargs):
        self.calls.append((copy.deepcopy(state), copy.deepcopy(questions)))
        if self.fail_at == len(self.calls):
            raise JevError('rate_limited', 429)
        task_id = next(iter(questions))
        options = list(questions[task_id]['criteria'])
        return {}, {'model': MODEL,
                    'answers': {task_id: {'type': 'choice', 'choice': options[0], 'confidence': .73,
                                        'probabilities': dict(zip(options, [.8, .1, .1]))}},
                    'usage': {'input_tokens': 100, 'output_tokens': 13}, 'latency_ms': 123.4}


class OfficialAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.transport = TransportFixture()
        self.model = OfficialDecisionModel(transport=self.transport)
        self.store = Store(Path(self.temp.name) / 'test.sqlite3', OfficialShadowEngine(self.model))
        self.addCleanup(self.store.db.close)

    def run_case(self, case_id='D01'):
        return self.store.run(case_id, {'revision': 1})

    def test_official_receipts_survive_business_handoff(self):
        result = self.run_case()
        self.assertEqual(result['usage']['official_input_tokens'], 200)
        self.assertEqual(result['usage']['official_output_tokens'], 26)
        self.assertEqual(result['usage']['generated_tokens'], 0)
        self.assertEqual(len(self.transport.calls), 2)
        task = result['tasks'][0]
        self.assertEqual(task['score'], .8)
        self.assertEqual(task['decision_record']['service_confidence'], .73)
        self.assertEqual(task['decision_record']['official_model'], MODEL)
        handoff = build_handoff(self.store.detail('D01'))
        self.assertEqual(handoff['decision_results'][0]['decision_record']['official_usage']['output_tokens'], 13)
        self.assertIsNone(handoff['approval_decision'])
        self.assertFalse(handoff['bank_connected'])

    def test_rules_block_cloud_call_on_missing_material(self):
        result = self.run_case('D03')
        self.assertEqual(len(self.transport.calls), 1)
        rule = next(task for task in result['tasks'] if task['id'] == 'USE_MATCH')
        self.assertEqual(rule['source'], 'input_rule')
        self.assertEqual(rule['action'], 'supplement')

    def test_one_task_failure_does_not_erase_other_result(self):
        self.transport.fail_at = 2
        result = self.run_case()
        self.assertEqual(result['tasks'][0]['source'], 'typesafe_official_jev')
        self.assertEqual(result['tasks'][1]['source'], 'model_error')
        self.assertIsNone(result['tasks'][1]['answer'])
        self.assertEqual(result['tasks'][1]['action'], 'human')
        self.assertEqual(result['usage']['official_input_tokens'], 100)

    def test_request_cap_stops_further_transport(self):
        self.model.max_requests = 1
        result = self.run_case()
        self.assertEqual(len(self.transport.calls), 1)
        self.assertEqual(result['usage']['actual_model_requests'], 1)
        self.assertEqual(result['usage']['unattempted_model_tasks'], 1)
        self.assertIsNone(result['tasks'][1]['answer'])

    def test_labels_and_reviews_do_not_enter_official_request(self):
        self.run_case()
        state, questions = self.transport.calls[0]
        self.assertEqual(set(state), {'materials'})
        self.assertEqual(set(state['materials'][0]), {'subject', 'period', 'paragraphs'})
        self.assertEqual(questions['USE_MATCH']['instructions'], QUESTIONS['USE_MATCH'])
        self.assertEqual(set(questions['USE_MATCH']['criteria']), set(ANSWERS['USE_MATCH']))

    def test_bad_materials_rejected_before_any_transport(self):
        state = {'materials': [{'subject': '甲', 'period': '9月', 'paragraphs': ['A']},
                               {'subject': '乙', 'period': '9月', 'paragraphs': ['B']}]}
        with self.assertRaises(ValueError):
            self.model.decide(state, QUESTIONS['BIZ_CONFLICT'], ANSWERS['BIZ_CONFLICT'])
        self.assertEqual(len(self.transport.calls), 0)

    def test_changed_model_identity_is_not_adopted(self):
        def changed(state, questions, **kwargs):
            payload, response = self.transport(state, questions, **kwargs)
            response['model'] = 'jev-9.9.9'
            return payload, response
        self.model.transport = changed
        result = self.run_case()
        self.assertTrue(all(task['answer'] is None for task in result['tasks']))
        self.assertEqual(result['usage']['official_successful_tasks'], 0)

    def test_revision_rerun_keeps_prior_identity(self):
        first = self.run_case()
        body = self.store.detail('D01')
        document = copy.deepcopy(body['case']['documents'][0])
        document['paragraphs'][0]['text'] += '补充：用途范围不变。'
        self.store.material('D01', {'revision': 1, 'document': document})
        second = self.store.run('D01', {'revision': 2})
        body = self.store.detail('D01')
        self.assertEqual(second['revision'], 2)
        self.assertEqual(len(body['runs']), 2)
        old = next(run for run in body['runs'] if run['revision'] == 1)
        self.assertEqual(old['tasks'][0]['decision_record']['official_model'], MODEL)
        self.assertEqual(first['revision'], 1)
        self.assertNotEqual(old['material_snapshot'], body['case']['documents'])
        self.assertEqual(second['material_snapshot'], body['case']['documents'])

    def test_official_service_is_opt_in(self):
        server = create_official_server(0, Path(self.temp.name) / 'server.sqlite3', self.model)
        self.addCleanup(server.store.db.close)
        self.addCleanup(server.server_close)
        self.assertEqual(server.store.shadow_engine.info()['backend'], 'typesafe_official')
        self.assertTrue(server.store.shadow_engine.info()['offline_test_mode'])

    def test_unsafe_endpoint_rejected_without_disclosing_key(self):
        with patch.dict(os.environ, {'JEV_API_KEY': 'offline-test-secret',
                                     'JEV_API_BASE_URL': 'https://example.com/v1/systemone'}, clear=True):
            with self.assertRaisesRegex(JevError, 'official_endpoint_required'):
                configuration()


if __name__ == '__main__':
    unittest.main()
