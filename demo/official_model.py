"""Official Jev adapter: model judgement, evidence and bank action stay separate."""
from copy import deepcopy
import threading

from judgement import API_VERSION, clean_state, digest, spec_for, specs, validate_state_for_spec
from shadow_engine import ShadowEngine, validate_prediction
from typesafe_client import JevError, MODEL, evaluate, parse_response

CRITERIA = {
    'USE_MATCH': {
        '一致': '有效且可比的材料支持同一申请、同一资金范围的相同用途，可同义表达。',
        '存在明确矛盾': '有效材料对同一申请、同一资金范围的用途作出互斥陈述，不能同时成立。',
        '信息不足': '资金归属、用途信息或覆盖范围不足，不能确定对应关系；已有明确冲突不因缺少额外证明变成不足。'},
    'BIZ_CONFLICT': {
        '发现明确矛盾': '同主体、同期间、同口径的有效陈述不能同时成立。',
        '未发现明确矛盾': '可比陈述能同时成立，包括双方均描述停业；经营状态不好本身不代表材料矛盾。',
        '无法比较': '主体、期间、口径或证据不足以比较。'}
}


def official_question(spec):
    return {'type': 'choice', 'instructions': spec['question'],
            'criteria': deepcopy(CRITERIA[spec['id']])}


class OfficialDecisionModel:
    adapter = 'typesafe_official_jev'
    calibration_note = '官方候选概率与服务置信度分别记录；未经本项目信贷领域校准'
    prediction_note = '官方Jev返回限定候选判断；原文与任务范围由工作台呈现，建议交人员复核。'

    def __init__(self, max_requests=20, transport=None):
        if type(max_requests) is not int or not 1 <= max_requests <= 100:
            raise ValueError('Request limit must be 1 to 100')
        self.max_requests = max_requests
        self.transport = transport or evaluate
        self.offline_test = transport is not None
        self.lock = threading.RLock()
        self.events = []

    def info(self):
        return {'name': 'TypeSafe official Jev ' + MODEL, 'backend': 'typesafe_official',
                'revision': MODEL, 'judgement_contract': API_VERSION,
                'official_protocol': 'state + questions; Choice', 'decision_specs': specs(),
                'auto_completion_enabled': False, 'bank_domain_calibrated': False,
                'bank_domain_trained': False, 'adoption_policy': 'auxiliary_human_review',
                'free_text_generation': False, 'offline_test_mode': self.offline_test,
                'readiness_scope': 'configured provider; successful calls are recorded per task',
                'request_limit': self.max_requests,
                'token_semantics': 'official input/output usage, separate from local candidate-path tokens'}

    def snapshot(self):
        with self.lock:
            return deepcopy(self.events)

    def decide(self, state, question, candidates):
        result = self.decide_many([(state, question, candidates)])[0]
        if isinstance(result, Exception):
            raise result
        return result

    def decide_many(self, requests):
        if not 1 <= len(requests) <= 2:
            raise ValueError('Expected one or two bank tasks')
        prepared = []
        for state, question, candidates in requests:
            spec = spec_for(question, candidates)
            state = clean_state(state)
            validate_state_for_spec(state, spec)
            prepared.append((state, spec))
        if len({spec['id'] for _, spec in prepared}) != len(prepared):
            raise ValueError('Duplicate bank task')
        results = []
        with self.lock:
            for state, spec in prepared:
                if len(self.events) >= self.max_requests:
                    results.append(JevError('session_request_limit'))
                    continue
                event = {'task_id': spec['id'], 'status': 'attempted', 'usage': None}
                self.events.append(event)
                questions = {spec['id']: official_question(spec)}
                try:
                    _, returned = self.transport(state, questions, model=MODEL)
                    parsed = parse_response(returned, questions, MODEL)
                    latency = returned['latency_ms']
                    answer = parsed['answers'][spec['id']]
                    output = {'answer': answer['choice'], 'score': answer['probabilities'][answer['choice']],
                              'distribution': answer['probabilities'], 'candidate_paths': len(spec['options']),
                              'input_path_tokens': 0, 'generated_tokens': 0, 'wall_ms': latency,
                              'official_usage': parsed['usage'], 'service_confidence': answer['confidence'],
                              'usage_semantics': 'generated_tokens counts free text only; structured API output tokens retained in official_usage',
                              'decision_record': {'spec_id': spec['id'], 'spec_version': spec['version'],
                                  'question_sha256': spec['question_sha256'], 'state_sha256': digest(state),
                                  'provider': self.adapter, 'model': self.info(), 'policy': spec['policy'],
                                  'fallback': 'human', 'official_model': parsed['model'],
                                  'official_question_sha256': digest(questions),
                                  'service_confidence': answer['confidence'], 'official_usage': parsed['usage'],
                                  'offline_test_mode': self.offline_test}}
                    validate_prediction(output, spec['options'])
                    event.update(status='measured', model=parsed['model'], usage=parsed['usage'], latency_ms=latency)
                    results.append(output)
                except Exception as exc:
                    # Persist only a known error category; no upstream body or secret.
                    kind = exc.kind if isinstance(exc, JevError) else 'invalid_official_result'
                    event.update(status='failed', error_type=kind)
                    results.append(JevError(kind))
        return results


class OfficialShadowEngine(ShadowEngine):
    def evaluate(self, case, task_ids=None):
        with self.predictor.lock:
            before = len(self.predictor.events)
            result = super().evaluate(case, task_ids)
            events = self.predictor.snapshot()[before:]
        successful = [event for event in events if event['status'] == 'measured']
        result['mode'] = '官方Jev辅助核验'
        logical_tasks = result['usage']['actual_model_requests']
        result['usage'].update(actual_model_requests=len(events),
                               failed_model_requests=len(events)-len(successful),
                               unattempted_model_tasks=logical_tasks-len(events),
                               official_task_attempts=len(events),
                               official_successful_tasks=len(successful),
                               official_input_tokens=sum(e['usage']['input_tokens'] for e in successful),
                               official_output_tokens=sum(e['usage']['output_tokens'] for e in successful),
                               official_failed_usage='unknown',
                               usage_semantics='official usage is separate; candidate_paths is option count, not server compute')
        result['official_events'] = events
        result['scope'] = '官方结构化判断；全部建议交人员复核，复杂分析按独立模式验证。'
        return result
