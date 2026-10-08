"""Offline checks for frozen inputs and reporting; no provider calls."""
import copy
import json
import unittest

import run_comparison as runner


class ComparisonIntegrityTests(unittest.TestCase):
    def test_frozen_sources_and_population(self):
        protocol = runner.freeze()
        inputs = json.loads((runner.STAGE / 'inputs.json').read_text(encoding='utf-8'))
        references = json.loads((runner.STAGE / 'references.json').read_text(encoding='utf-8'))
        self.assertEqual(protocol['max_http_calls'], 47)
        self.assertEqual(len(inputs), 54)
        self.assertEqual(len({row['case_id'] for row in inputs}), 54)
        self.assertEqual(set(references), {row['case_id'] for row in inputs})
        for row in inputs:
            self.assertEqual(set(row), {'case_id', 'task_id', 'state', 'rule_answer', 'question'})
            self.assertNotIn('lineage_group', row['state'])
            self.assertNotIn('reference_answer', row['state'])
            self.assertEqual(len(row['question']['criteria']), 3)

    def test_partial_failure_cannot_be_complete_or_hidden(self):
        references = {'a': {'answer': '存在明确矛盾'}, 'b': {'answer': '一致'}}
        rows = [{'case_id': 'a', 'source': 'typesafe_official_jev', 'status': 'failed', 'answer': None},
                {'case_id': 'b', 'source': 'input_rule', 'status': 'rule_handled', 'answer': '一致'}]
        result = runner.summarize(rows, references)
        self.assertFalse(result['complete'])
        self.assertEqual(result['agreement_n'], 1)
        self.assertEqual(result['conflict_nonidentification_ids'], ['a'])
        self.assertIsNone(result['client_latency_median_ms'])

    def test_structured_output_tokens_are_retained(self):
        refs = {'a': {'answer': '一致'}, 'b': {'answer': '存在明确矛盾'}}
        rows = [{'case_id': 'a', 'source': 'typesafe_official_jev', 'status': 'measured',
                 'answer': '一致', 'wall_ms': 100,
                 'official_usage': {'input_tokens': 20, 'output_tokens': 7}},
                {'case_id': 'b', 'source': 'typesafe_official_jev', 'status': 'measured',
                 'answer': '一致', 'wall_ms': 300,
                 'official_usage': {'input_tokens': 30, 'output_tokens': 9}}]
        before = copy.deepcopy(rows)
        result = runner.summarize(rows, refs)
        self.assertEqual(result['reported_output_tokens'], 16)
        self.assertEqual(result['reported_input_tokens'], 50)
        self.assertEqual(result['client_latency_median_ms'], 200)
        self.assertEqual(result['conflict_nonidentification_ids'], ['b'])
        self.assertEqual(rows, before)


if __name__ == '__main__':
    unittest.main()
