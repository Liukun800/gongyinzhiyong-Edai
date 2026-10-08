"""Report integrity tests use synthetic fixture files, never network requests."""
import json
import tempfile
import unittest
from pathlib import Path

from run_minimum import CASES
from summarize_minimum import validate_run


class MinimumReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.stage = Path(self.temp.name)
        self.run = self.stage / 'run_fixture'
        self.run.mkdir()
        self.write(self.stage / 'cases.json', [{k: v for k, v in c.items() if k != 'reference'} for c in CASES])
        self.write(self.stage / 'references.json', {c['case_id']: c['reference'] for c in CASES})
        records = []
        for case in CASES:
            options = list(case['question']['criteria'])
            choice = case['reference']
            answer = {'type': 'choice', 'choice': choice, 'confidence': .7,
                      'probabilities': {option: .8 if option == choice else .1 for option in options}}
            record = {'case_id': case['case_id'], 'task_id': case['task_id'], 'status': 'measured',
                      'model': 'jev-1.13.0', 'answers': {case['task_id']: answer},
                      'usage': {'input_tokens': 10, 'output_tokens': 0}, 'latency_ms': 150,
                      'reference_agreement': True, 'routing_action': 'human_review', 'auto_approval': False}
            self.write(self.run / (case['case_id'] + '.request.json'),
                       {'state': case['state'], 'questions': {case['task_id']: case['question']}, 'model': 'jev-1.13.0'})
            records.append(record)
        self.summary = {'records': records, 'attempted_requests': 2, 'successful_requests': 2,
                        'reported_input_tokens': 20, 'reported_output_tokens': 0, 'bank_connected': False}
        self.save()

    def write(self, path, value):
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')

    def save(self):
        for record in self.summary['records']:
            self.write(self.run / (record['case_id'] + '.response.redacted.json'), record)
        self.write(self.run / 'usage_summary.json', self.summary)

    def test_valid_protocol_does_not_accept_domain_quality(self):
        report = validate_run(self.run, self.stage)
        self.assertEqual(report['status'], 'protocol_passed')
        self.assertFalse(report['domain_quality_accepted'])
        self.assertFalse(report['bank_connected'])

    def test_incorrect_token_total_rejected(self):
        self.summary['reported_input_tokens'] = 999
        self.save()
        with self.assertRaisesRegex(ValueError, 'usage_or_count_mismatch'):
            validate_run(self.run, self.stage)

    def test_reference_agreement_recomputed(self):
        self.summary['records'][0]['reference_agreement'] = False
        self.save()
        with self.assertRaisesRegex(ValueError, 'reference_agreement_mismatch'):
            validate_run(self.run, self.stage)

    def test_modified_request_rejected(self):
        self.write(self.run / (CASES[0]['case_id'] + '.request.json'), {'state': {}, 'questions': {}})
        with self.assertRaisesRegex(ValueError, 'frozen_request_mismatch'):
            validate_run(self.run, self.stage)

    def test_failure_has_no_placeholder_answer(self):
        self.summary['records'] = [{'case_id': CASES[0]['case_id'], 'task_id': CASES[0]['task_id'],
                                   'status': 'failed', 'error_type': 'rate_limited', 'routing_action': 'human_review'}]
        self.summary.update(attempted_requests=1, successful_requests=0,
                            reported_input_tokens=0, reported_output_tokens=0)
        self.save()
        report = validate_run(self.run, self.stage)
        self.assertEqual(report['status'], 'failed_or_incomplete')
        self.assertNotIn('choice', report['rows'][0])


if __name__ == '__main__':
    unittest.main()
