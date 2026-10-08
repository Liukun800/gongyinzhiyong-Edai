"""Regression tests for material-missing versus semantic-uncertainty routing."""
import copy
import unittest

from shadow_engine import ShadowEngine, input_guard, QUESTIONS
from test_shadow import FakePredictor


def case(subject='演示主体', period='2026-08'):
    return {'id': 'independent-input', 'revision': 1, 'documents': [
        {'id': f'm{i}', 'kind': 'purpose', 'title': '用途材料', 'subject': subject,
         'period': period, 'paragraphs': [{'id': 'p1', 'text': text}]}
        for i, text in enumerate(['申请材料原文', '证明材料原文'], 1)]}


class AnswerPredictor(FakePredictor):
    def __init__(self, answer):
        super().__init__()
        self.answer = answer

    def decide(self, state, question, candidates):
        result = super().decide(state, question, candidates)
        result.update(answer=self.answer, score=.7,
                      distribution={c: .7 if c == self.answer else .15 for c in candidates})
        return result


class RemediationRoutingTests(unittest.TestCase):
    def test_semantic_insufficiency_is_not_material_missing(self):
        result = ShadowEngine(AnswerPredictor('信息不足')).evaluate(case(), ['USE_MATCH'])
        task = result['tasks'][0]
        self.assertEqual(task['answer'], '信息不足')
        self.assertEqual(task['action'], 'human')
        self.assertEqual(task['routing_reason'], 'semantic_uncertainty')
        self.assertEqual(result['usage']['actual_model_requests'], 1)

    def test_true_missing_material_still_requests_supplement(self):
        value = case(); value['documents'].pop()
        result = ShadowEngine(AnswerPredictor('一致')).evaluate(value, ['USE_MATCH'])
        self.assertEqual(result['tasks'][0]['action'], 'supplement')
        self.assertEqual(result['tasks'][0]['source'], 'input_rule')
        self.assertEqual(result['usage']['actual_model_requests'], 0)

    def test_explicit_conflict_requires_human(self):
        result = ShadowEngine(AnswerPredictor('存在明确矛盾')).evaluate(case(), ['USE_MATCH'])
        self.assertEqual(result['tasks'][0]['action'], 'human')
        self.assertEqual(result['tasks'][0]['answer'], '存在明确矛盾')

    def test_blank_subject_does_not_pass_equality_guard(self):
        self.assertIsNotNone(input_guard(case(subject=' ')['documents'], 'USE_MATCH'))

    def test_blank_business_period_does_not_pass_equality_guard(self):
        self.assertIsNotNone(input_guard(case(period='')['documents'], 'BIZ_CONFLICT'))

    def test_input_unchanged_and_no_fixture_answers(self):
        value = case(); before = copy.deepcopy(value)
        model = AnswerPredictor('一致')
        ShadowEngine(model).evaluate(value, ['USE_MATCH'])
        self.assertEqual(value, before)
        self.assertNotIn('independent-input', str(model.calls))
        self.assertEqual(set(model.calls[0][0]), {'materials'})

    def test_candidate_questions_are_opt_in_and_copied(self):
        configured = dict(QUESTIONS)
        configured['USE_MATCH'] = '仅按明确材料关系核验。'
        predictor = AnswerPredictor('一致')
        engine = ShadowEngine(predictor, questions=configured)
        configured['USE_MATCH'] = '构造后外部修改不生效'
        engine.evaluate(case(), ['USE_MATCH'])
        self.assertEqual(predictor.calls[0][1], '仅按明确材料关系核验。')
        default = AnswerPredictor('一致')
        ShadowEngine(default).evaluate(case(), ['USE_MATCH'])
        self.assertEqual(default.calls[0][1], QUESTIONS['USE_MATCH'])
        self.assertNotIn('仅按明确材料关系核验。', str(default.calls))

    def test_invalid_task_configuration_rejected(self):
        for config in ({}, {'USE_MATCH': '说明'}, dict(QUESTIONS, BIZ_CONFLICT=' '),
                       dict(QUESTIONS, USE_MATCH=None), dict(QUESTIONS, UNKNOWN='说明')):
            with self.subTest(config=config), self.assertRaises(ValueError):
                ShadowEngine(AnswerPredictor('一致'), questions=config)


if __name__ == '__main__':
    unittest.main()
