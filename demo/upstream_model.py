"""Strict local adapter for the pinned XiaokeAILabs AgentJev HTTP contract.

Contract checks are not model-quality evaluation. No labels are transmitted.
"""
import json
import re
import uuid
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Jev service redirects are not accepted')


class UpstreamDecisionModel:
    adapter = 'agentjev_upstream_shadow'
    calibration_note = '上游温度由服务提供；信贷领域校准效果尚未验证'
    prediction_note = 'Jev服务返回候选分布；领域效果与接受条件待验证，保留为影子建议。'
    version = 'agentjev.decision.v1'

    def __init__(self, base_url='http://127.0.0.1:8149', timeout=45):
        parts = urlsplit(base_url)
        if (parts.scheme != 'http' or parts.hostname != '127.0.0.1'
                or parts.username or parts.password or parts.path not in ('', '/')
                or parts.query or parts.fragment or not parts.port):
            raise ValueError('Use an explicit http://127.0.0.1:PORT Jev service')
        self.base_url, self.timeout = base_url.rstrip('/'), timeout
        self.opener = build_opener(ProxyHandler({}), NoRedirect())
        info = self._request('/api/info')
        if (info.get('api_version') != self.version or info.get('status') != 'ready'
                or 'choice' not in info.get('types', [])
                or info.get('output_token_decoding') is not False
                or not re.fullmatch(r'[a-fA-F0-9]{64}', info.get('checkpoint_sha256', ''))):
            raise ValueError('Jev service identity or capabilities mismatch')
        self.service_info = info

    def _request(self, path, body=None):
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode('utf-8')
        req = Request(self.base_url + path, data=data, headers={'Content-Type': 'application/json'})
        with self.opener.open(req, timeout=self.timeout) as response:
            raw = response.read(1_048_577)
        if len(raw) > 1_048_576:
            raise ValueError('Jev response exceeds limit')
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError('Jev response must be an object')
        return result

    def info(self):
        s = self.service_info
        return {'name': s.get('model', 'AgentJev service'), 'backend': 'upstream_http',
                'api_version': self.version, 'checkpoint': s.get('checkpoint'),
                'weight_sha256': s['checkpoint_sha256'], 'device': 'service-managed',
                'encoder': s.get('encoder'), 'shared_prefix_compute': s.get('shared_prefix_compute'),
                'max_path_tokens': s.get('max_path_tokens'), 'temperatures': s.get('temperatures'),
                'domain_validation': 'not_verified', 'auto_completion_enabled': False,
                'bank_domain_trained': False, 'bank_domain_calibrated': False,
                'checkpoint_card_scope': 'configured local service; credit-domain validation required'}

    def decide(self, state, question, candidates):
        from shadow_engine import validate_prediction
        if not isinstance(state, dict) or set(state) != {'materials'}:
            raise ValueError('Only whitelisted material state is accepted')
        rid = uuid.uuid4().hex
        body = {'id': rid, 'state': state, 'questions': [
            {'id': 'decision', 'type': 'choice', 'question': question, 'options': list(candidates)}]}
        response = self._request('/api/evaluate', body)
        if response.get('api_version') != self.version:
            raise ValueError('Jev API version changed')
        results = response.get('results', [])
        if len(results) != 1 or results[0].get('id') != rid:
            raise ValueError('Jev request identity mismatch')
        answers = results[0].get('answers', [])
        if (len(answers) != 1 or answers[0].get('id') != 'decision'
                or answers[0].get('type') != 'choice'):
            raise ValueError('Jev question identity mismatch')
        answer = answers[0]
        keys = [str(i) for i in range(len(candidates))]
        distribution = answer.get('distribution', {})
        if set(distribution) != set(keys) or answer.get('value') not in keys:
            raise ValueError('Jev candidate keys mismatch')
        usage = response.get('usage', {})
        if usage.get('generated_tokens') != 0 or usage.get('truncated_inputs') != 0:
            raise ValueError('Generated or truncated input is not accepted')
        result = {'answer': candidates[int(answer['value'])],
                  'score': answer.get('top_probability'),
                  'distribution': {text: distribution[k] for k, text in zip(keys, candidates)},
                  **{k: usage.get(k) for k in ('wall_ms', 'candidate_paths', 'input_path_tokens', 'generated_tokens')}}
        validate_prediction(result, candidates)
        return result
