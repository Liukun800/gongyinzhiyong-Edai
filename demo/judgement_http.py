"""Explicit authenticated loopback transport for versioned bank judgement."""
import json
import math
import uuid
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler

from upstream_model import NoRedirect
from judgement import (API_VERSION, MAX_BYTES, specs, spec_for, clean_state,
                       validate_state_for_spec, digest)
from shadow_engine import validate_prediction


def validate_token(token):
    if (not isinstance(token, str) or len(token) < 32 or len(token) > 256
            or any(not (c.isascii() and (c.isalnum() or c in '-_')) for c in token)):
        raise ValueError('A 32+ character service token is required')
    return token


class HttpJudgement:
    adapter = 'credit_judgement_http_shadow'
    calibration_note = '判断服务的候选分数；信贷校准未验证'
    prediction_note = '版本化判断服务返回辅助建议，核验依据与处理责任保留在工作台。'

    def __init__(self, base_url, token, timeout=45):
        parts = urlsplit(base_url)
        if (parts.scheme != 'http' or parts.hostname != '127.0.0.1'
                or parts.username or parts.password or parts.path not in ('', '/')
                or parts.query or parts.fragment or not parts.port):
            raise ValueError('Use explicit http://127.0.0.1:PORT')
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 120:
            raise ValueError('Invalid request timeout')
        self.base_url = base_url.rstrip('/')
        self.token, self.timeout = validate_token(token), timeout
        self.opener = build_opener(ProxyHandler({}), NoRedirect())
        info = self._request('/api/info')
        if (info.get('api_version') != API_VERSION or info.get('status') != 'ready'
                or info.get('decision_specs') != specs()
                or info.get('adoption_policy') != 'auxiliary_human_review'
                or not isinstance(info.get('model'), dict)):
            raise ValueError('Service task/capability identity mismatch')
        self.identity = info

    def _request(self, path, body=None):
        raw = None if body is None else json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
        if raw is not None and len(raw) > MAX_BYTES:
            raise ValueError('Judgement request exceeds limit')
        req = Request(self.base_url + path, data=raw,
                      headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.token})
        with self.opener.open(req, timeout=self.timeout) as response:
            data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError('Judgement response exceeds limit')
        result = json.loads(data)
        if not isinstance(result, dict):
            raise ValueError('Expected response object')
        return result

    def info(self):
        return {**self.identity['model'], 'backend': 'versioned_local_http',
                'judgement_contract': API_VERSION, 'decision_specs': specs(),
                'adoption_policy': 'auxiliary_human_review', 'auto_completion_enabled': False,
                'readiness_scope': 'identity checked at startup; runtime errors go to human'}

    def decide(self, state, question, candidates):
        return self.decide_many([(state, question, candidates)])[0]

    def decide_many(self, requests):
        if not 1 <= len(requests) <= 2:
            raise ValueError('Expected one or two judgement requests')
        items, selected = [], []
        for state, question, candidates in requests:
            spec = spec_for(question, candidates)
            state = clean_state(state)
            validate_state_for_spec(state, spec)
            selected.append(spec)
            items.append({'id': spec['id'], 'version': spec['version'],
                          'question_sha256': spec['question_sha256'], 'state': state})
        if len({i['id'] for i in items}) != len(items):
            raise ValueError('Duplicate judgement task')
        rid = uuid.uuid4().hex
        response = self._request('/api/judge', {'api_version': API_VERSION, 'id': rid, 'questions': items})
        if (response.get('api_version') != API_VERSION or response.get('id') != rid
                or response.get('model') != self.identity['model']):
            raise ValueError('Service/request identity changed')
        answers = response.get('answers')
        if not isinstance(answers, list) or len(answers) != len(items):
            raise ValueError('Wrong result count')
        if any(not isinstance(a, dict) for a in answers):
            raise ValueError('Malformed answer')
        by_id = {a.get('id'): a for a in answers}
        if set(by_id) != {i['id'] for i in items}:
            raise ValueError('Wrong/duplicate task identity')
        outputs = []
        for item, spec in zip(items, selected):
            answer = by_id[item['id']]
            if answer.get('version') != spec['version']:
                raise ValueError('Task version changed')
            result = answer.get('prediction')
            validate_prediction(result, spec['options'])
            record = result.get('decision_record', {})
            if (record.get('spec_id') != spec['id'] or record.get('spec_version') != spec['version']
                    or record.get('question_sha256') != spec['question_sha256']
                    or record.get('state_sha256') != digest(item['state'])
                    or record.get('model') != self.identity['model']
                    or record.get('policy') != spec['policy'] or record.get('fallback') != 'human'
                    or not isinstance(record.get('provider'), str) or not record['provider']
                    or result['generated_tokens'] != 0):
                raise ValueError('Invalid provenance or output type')
            outputs.append(result)
        return outputs
