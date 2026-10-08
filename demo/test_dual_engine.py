import copy
import unittest

from dual_engine import DualEngine
from slow_model import validate_analysis, SlowAnalysisError
from test_review_remediation import AnswerPredictor, case


class TestSlow:
    def __init__(self, fail=False, invalid_reference=False):
        self.calls = []
        self.fail, self.invalid_reference = fail, invalid_reference

    def info(self): return {'name': 'test-double-not-a-real-model'}

    def analyze(self, task_id, documents):
        self.calls.append(copy.deepcopy(documents))
        usage = {'prompt_tokens': 20, 'completion_tokens': 10, 'wall_ms': 3}
        if self.fail: raise SlowAnalysisError('injected timeout', {'usage': usage})
        refs = ['m1:p1', 'm2:p1'] if not self.invalid_reference else ['missing:p1']
        result = validate_analysis({'answer': '一致', 'reason': '测试返回', 'evidence': refs}, task_id, documents)
        return {**result, 'model': self.info(), 'raw_output': 'test-only', 'usage': usage}


class DualEngineTests(unittest.TestCase):
    def test_real_guard_skips_both_models(self):
        value = case(); value['documents'].pop()
        slow = TestSlow()
        result = DualEngine(AnswerPredictor('信息不足'), slow).evaluate(value, ['USE_MATCH'])
        self.assertEqual(result['usage']['actual_model_requests'], 0)
        self.assertEqual(result['usage']['actual_complex_model_requests'], 0)
        self.assertEqual(slow.calls, [])

    def test_uncertain_answer_escalates_and_preserves_original(self):
        result = DualEngine(AnswerPredictor('信息不足'), TestSlow()).evaluate(case(), ['USE_MATCH'])
        task = result['tasks'][0]
        self.assertEqual(task['fast_decision']['answer'], '信息不足')
        self.assertEqual(task['answer'], '一致')
        self.assertEqual(task['action'], 'review')
        self.assertEqual(task['source'], 'real_slow_analysis')
        self.assertIsNone(task['score'])
        self.assertEqual(result['usage']['actual_complex_model_requests'], 1)
        self.assertEqual(result['usage']['complex_completion_tokens'], 10)

    def test_conflict_goes_directly_to_human_even_below_threshold(self):
        slow = TestSlow()
        result = DualEngine(AnswerPredictor('存在明确矛盾'), slow).evaluate(case(), ['USE_MATCH'])
        self.assertEqual(result['tasks'][0]['action'], 'human')
        self.assertEqual(slow.calls, [])

    def test_low_score_consistent_answer_escalates(self):
        result = DualEngine(AnswerPredictor('一致'), TestSlow()).evaluate(case(), ['USE_MATCH'])
        self.assertEqual(result['usage']['actual_complex_model_requests'], 1)

    def test_sufficient_raw_score_still_requires_review(self):
        result = DualEngine(AnswerPredictor('一致'), TestSlow(), threshold=.6).evaluate(case(), ['USE_MATCH'])
        self.assertEqual(result['usage']['actual_complex_model_requests'], 0)
        self.assertEqual(result['tasks'][0]['action'], 'review')

    def test_failed_slow_call_preserves_usage_and_does_not_accept_fast_answer(self):
        result = DualEngine(AnswerPredictor('信息不足'), TestSlow(fail=True)).evaluate(case(), ['USE_MATCH'])
        task = result['tasks'][0]
        self.assertIsNone(task['answer'])
        self.assertEqual(task['fast_decision']['answer'], '信息不足')
        self.assertEqual(task['action'], 'human')
        self.assertEqual(result['usage']['failed_complex_model_requests'], 1)
        self.assertEqual(result['usage']['complex_prompt_tokens'], 20)

    def test_fabricated_evidence_fails_closed(self):
        result = DualEngine(AnswerPredictor('信息不足'), TestSlow(invalid_reference=True)).evaluate(case(), ['USE_MATCH'])
        self.assertIsNone(result['tasks'][0]['answer'])
        self.assertEqual(result['tasks'][0]['source'], 'complex_model_error')

    def test_two_sources_and_valid_candidate_required(self):
        docs = case()['documents']
        for payload in [{'answer': '一致', 'reason': '说明', 'evidence': ['m1:p1']},
                        {'answer': '授信通过', 'reason': '说明', 'evidence': ['m1:p1', 'm2:p1']},
                        {'answer': '一致', 'reason': '说明', 'evidence': ['m1:p1', 'm1:p1']}]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                validate_analysis(payload, 'USE_MATCH', docs)


if __name__ == '__main__': unittest.main()
