"""Evidence-bounded requests and shadow routing. Never reads fixture annotations."""
import logging
import math
import time

from engine import TASKS, ANSWERS, evidence

QUESTIONS = {
    'USE_MATCH': '核验同一申请、同一资金范围的用途说明与证明材料。仅选一个答案：一致＝有效材料支持同一用途（可同义表达）；存在明确矛盾＝有效材料对同一资金用途作出互斥陈述；信息不足＝无法确定对应关系或覆盖范围，不能凭缺少额外证明把已存在的明确冲突判成不足。只有明确已生效的更正才能替代原材料，未签草案不能更正。比较文字证据，不认定交易真实性。',
    'BIZ_CONFLICT': '核验同主体、同期间、同口径的两份经营陈述。发现明确矛盾＝两陈述不能同时成立；未发现明确矛盾＝可同时成立，包括双方均描述停业；无法比较＝主体、期间、口径或证据不足以比较。全月营业与整月停业互相矛盾；停业本身是经营状态，不等于材料之间有矛盾。仅依据有效原文判断。'
}


def task_documents(case, task_id):
    kind = 'purpose' if task_id == 'USE_MATCH' else 'business'
    return [d for d in case['documents'] if d['kind'] == kind]


def input_guard(documents, task_id):
    """Metadata checks only. Does not verify document authenticity or semantics."""
    insufficient = '信息不足' if task_id == 'USE_MATCH' else '无法比较'
    if len(documents) < 2:
        return insufficient, '当前任务少于两份材料，先补充可供交叉比较的原文；未调用模型。'
    if any(not d['subject'].strip() for d in documents):
        return insufficient, '材料主体字段缺失，先补充归属信息；未调用模型。'
    if len({d['subject'].strip() for d in documents}) != 1:
        return insufficient, '材料登记的主体不一致，需确认归属及关系；未调用模型。'
    if task_id == 'BIZ_CONFLICT' and any(not d['period'].strip() for d in documents):
        return insufficient, '经营材料期间字段缺失，先补充期间信息；未调用模型。'
    if task_id == 'BIZ_CONFLICT' and len({d['period'].strip() for d in documents}) != 1:
        return insufficient, '材料登记的期间不一致，需补充同期间记录；未调用模型。'
    return None


def model_state(documents):
    # Deliberately whitelist fields: labels, case IDs and annotation notes are excluded.
    return {'materials': [{'subject': d['subject'], 'period': d['period'],
                           'paragraphs': [p['text'] for p in d['paragraphs']]} for d in documents]}


def route_answer(answer):
    if answer in ('信息不足', '无法比较'):
        return '待补充', 'supplement'
    if answer in ('存在明确矛盾', '发现明确矛盾'):
        return '待人工核实', 'human'
    if answer in ('一致', '未发现明确矛盾'):
        return '待复核', 'review'
    return '待人工核实', 'human'


def validate_prediction(result, candidates):
    """Fail closed for malformed/inconsistent candidate distributions."""
    if not isinstance(result, dict) or result.get('answer') not in candidates:
        raise ValueError('Invalid candidate returned by predictor')
    distribution = result.get('distribution')
    if not isinstance(distribution, dict) or set(distribution) != set(candidates):
        raise ValueError('Invalid distribution keys')
    def finite_number(value):
        return type(value) in (int, float) and math.isfinite(value)
    if any(not finite_number(v) or not 0 <= v <= 1 for v in distribution.values()):
        raise ValueError('Invalid probability value')
    if abs(sum(distribution.values()) - 1) > 1e-5:
        raise ValueError('Distribution must sum to one')
    score = result.get('score')
    if (not finite_number(score) or abs(score - distribution[result['answer']]) > 1e-6
            or abs(score - max(distribution.values())) > 1e-6):
        raise ValueError('Answer and score disagree with distribution')
    for key in ('candidate_paths', 'input_path_tokens', 'generated_tokens'):
        if type(result.get(key)) is not int or result[key] < 0:
            raise ValueError('Invalid usage count')
    if result['candidate_paths'] != len(candidates):
        raise ValueError('Unexpected number of candidate paths')
    if not finite_number(result.get('wall_ms')) or result['wall_ms'] < 0:
        raise ValueError('Invalid latency')


class ShadowEngine:
    def __init__(self, predictor, questions=None):
        self.predictor = predictor
        # Candidate task wording is opt-in; the presentation default stays unchanged.
        self.questions = dict(QUESTIONS if questions is None else questions)
        if (set(self.questions) != set(QUESTIONS)
                or any(not isinstance(q, str) or not q.strip() for q in self.questions.values())):
            raise ValueError('Questions must define both supported tasks with nonempty text')

    def info(self):
        return self.predictor.info()

    def evaluate(self, case, task_ids=None):
        started = time.perf_counter()
        tasks, requests, successes, paths, tokens = [], 0, 0, 0, 0
        selected = list(TASKS) if task_ids is None else task_ids
        if not selected or len(set(selected)) != len(selected) or any(t not in TASKS for t in selected):
            raise ValueError('Unknown or duplicate task ID')
        model_requests = []
        prepared_tasks = []
        for task_id in selected:
            name = TASKS[task_id]
            documents = task_documents(case, task_id)
            t = {'id': task_id, 'name': name, 'answer': None, 'score': None,
                 'distribution': None, 'calibration': getattr(self.predictor, 'calibration_note', '未经信贷领域校准；不使用上游温度'),
                 'status': '待人工核实', 'action': 'human', 'reason': '',
                 'evidence': evidence(documents, [d['id'] for d in documents]),
                 'evidence_semantics': '本次输入原文，定位已检查；语义支持关系待人员核实',
                 'simulated_analysis_requests': 0, 'analysis': None, 'review': None,
                 'source': 'input_rule', 'model_usage': None}
            guard = input_guard(documents, task_id)
            if guard:
                t.update(answer=guard[0], status='待补充', action='supplement', reason=guard[1])
            else:
                # No case IDs, fixture answers, scenarios, sources or review feedback enter the model.
                state = model_state(documents)
                requests += 1
                model_requests.append((state, self.questions[task_id], ANSWERS[task_id]))
                prepared_tasks.append(t)
            tasks.append(t)

        if model_requests:
            try:
                if hasattr(self.predictor, 'decide_many'):
                    predictions = self.predictor.decide_many(model_requests)
                else:
                    predictions = [self.predictor.decide(*request) for request in model_requests]
                if len(predictions) != len(model_requests):
                    raise ValueError('Predictor returned a different number of task results')
            except Exception as exc:
                logging.exception('Batched shadow model request failed')
                predictions = [exc] * len(model_requests)
            for t, result in zip(prepared_tasks, predictions):
                if isinstance(result, Exception):
                    t.update(source='model_error', reason=f'真实判断未完成（{type(result).__name__}），转人工；未回退到预设答案。')
                    continue
                try:
                    validate_prediction(result, ANSWERS[t['id']])
                    successes += 1
                    paths += result['candidate_paths']
                    tokens += result['input_path_tokens']
                    t.update(answer=result['answer'], score=result['score'], distribution=result['distribution'],
                             source=getattr(self.predictor, 'adapter', 'agentjev_public_shadow'), model_usage={k:result[k] for k in ('wall_ms','candidate_paths','input_path_tokens','generated_tokens')},
                             status='待复核', action='review', reason=getattr(self.predictor, 'prediction_note', '真实公开模型返回候选分布；尚未信贷微调或验证接受条件，保留为影子建议。'))
                    if 'decision_record' in result:
                        t['decision_record'] = result['decision_record']
                    if result['answer'] in ('信息不足', '无法比较'):
                        t.update(status='待人工核实', action='human', reason='材料已通过输入检查，但模型语义判断不确定；先核实是否存在矛盾或确需补件，不直接发出补件要求。', routing_reason='semantic_uncertainty')
                    elif result['answer'] in ('存在明确矛盾', '发现明确矛盾'):
                        t.update(status='待人工核实', action='human', reason='模型提示矛盾，按原型规则转人工核实；请对照原文验证是否为误报。')
                except Exception as exc:
                    logging.exception('Shadow model request failed')
                    t.update(source='model_error', reason=f'真实判断未完成（{type(exc).__name__}），转人工；未回退到预设答案。')
        return {'case_id': case['id'], 'revision': case['revision'], 'mode': '真实模型影子',
                'adapter': getattr(self.predictor, 'adapter', 'agentjev_public_shadow'), 'model': self.info(), 'tasks': tasks,
                'usage': {'actual_model_requests': requests, 'successful_model_requests': successes,
                          'failed_model_requests': requests-successes, 'simulated_analysis_requests': 0,
                          'actual_complex_model_requests': 0, 'candidate_paths': paths,
                          'input_path_tokens': tokens, 'generated_tokens': 0,
                          'workflow_ms': round((time.perf_counter()-started)*1000, 2)},
                'scope': '影子建议，无自动完成阈值；复杂分析模型尚未接入。'}
