"""Versioned bank task boundary. Model judgement never grants business authority.

Design reference: mu DecisionSpec/provider separation; independent Python code.
"""
import hashlib
import json
from copy import deepcopy

from engine import ANSWERS
from shadow_engine import QUESTIONS, validate_prediction

API_VERSION = 'credit.judgement.v1'
SPEC_VERSION = '1.0.0'
MAX_BYTES = 1_048_576


def digest(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(',', ':'), allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def specs():
    return [{'id': task, 'version': SPEC_VERSION, 'type': 'choice',
             'capability': 'relate', 'question': QUESTIONS[task],
             'options': list(ANSWERS[task]), 'policy': 'auxiliary_human_review',
             'fallback': 'human', 'question_sha256': digest(QUESTIONS[task])}
            for task in QUESTIONS]


def spec_for(question, candidates):
    for spec in specs():
        if question == spec['question'] and list(candidates) == spec['options']:
            return spec
    raise ValueError('Unknown task wording/options; register a new spec version first')


def clean_state(state):
    if not isinstance(state, dict) or set(state) != {'materials'}:
        raise ValueError('Only material state is accepted')
    docs = state['materials']
    if not isinstance(docs, list) or not 2 <= len(docs) <= 20:
        raise ValueError('Judgement requires 2 to 20 comparable materials')
    for doc in docs:
        if not isinstance(doc, dict) or set(doc) != {'subject', 'period', 'paragraphs'}:
            raise ValueError('Unexpected material fields')
        if any(not isinstance(doc[k], str) or len(doc[k]) > 160 for k in ('subject', 'period')):
            raise ValueError('Invalid material metadata')
        if not doc['subject'].strip():
            raise ValueError('Missing subject')
        paragraphs = doc['paragraphs']
        if (not isinstance(paragraphs, list) or not 1 <= len(paragraphs) <= 20
                or any(not isinstance(p, str) or not p.strip() or len(p) > 20000 for p in paragraphs)):
            raise ValueError('Invalid material paragraphs')
    raw = json.dumps(state, ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(raw) > MAX_BYTES:
        raise ValueError('Material state exceeds limit')
    return deepcopy(state)


def validate_state_for_spec(state, spec):
    docs = state['materials']
    if len({d['subject'].strip() for d in docs}) != 1:
        raise ValueError('Subjects must match before judgement')
    if spec['id'] == 'BIZ_CONFLICT' and (
            any(not d['period'].strip() for d in docs)
            or len({d['period'].strip() for d in docs}) != 1):
        raise ValueError('Business periods must match before judgement')


class VersionedJudgement:
    """Wrap any existing predictor; preserve its candidate inference and batching."""
    def __init__(self, predictor):
        self.predictor = predictor
        self.adapter = getattr(predictor, 'adapter', 'agentjev_public_shadow')
        self.calibration_note = getattr(predictor, 'calibration_note', '未经信贷领域校准')
        self.prediction_note = getattr(predictor, 'prediction_note', '结构化判断建议，提交人员复核。')

    def info(self):
        return {**self.predictor.info(), 'judgement_contract': API_VERSION,
                'decision_specs': specs(), 'adoption_policy': 'auxiliary_human_review'}

    def decide(self, state, question, candidates):
        return self.decide_many([(state, question, candidates)])[0]

    def decide_many(self, requests):
        if not 1 <= len(requests) <= 2:
            raise ValueError('Batch must contain one or two bank tasks')
        prepared, selected = [], []
        for state, question, candidates in requests:
            spec = spec_for(question, candidates)
            state = clean_state(state)
            validate_state_for_spec(state, spec)
            prepared.append((state, question, list(candidates)))
            selected.append(spec)
        if len({s['id'] for s in selected}) != len(selected):
            raise ValueError('Duplicate bank task')
        if hasattr(self.predictor, 'decide_many'):
            outputs = self.predictor.decide_many(prepared)
        else:
            outputs = [self.predictor.decide(*r) for r in prepared]
        if not isinstance(outputs, list) or len(outputs) != len(prepared):
            raise ValueError('Wrong judgement result count')
        model = self.predictor.info()
        results = []
        for output, request, spec in zip(outputs, prepared, selected):
            validate_prediction(output, spec['options'])
            if output['generated_tokens'] != 0:
                raise ValueError('This contract accepts judgement without text generation')
            record = {'spec_id': spec['id'], 'spec_version': spec['version'],
                      'question_sha256': spec['question_sha256'], 'state_sha256': digest(request[0]),
                      'provider': self.adapter, 'model': model,
                      'policy': spec['policy'], 'fallback': spec['fallback']}
            results.append({**output, 'decision_record': record})
        return results
