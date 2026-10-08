"""Official TypeSafe System One transport; no free-text generation or retries."""
import json
import math
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ENDPOINT = 'https://api.typesafe.ai/v1/systemone'
MODEL = 'jev-1.13.0'
MAX_BYTES = 65536


class JevError(RuntimeError):
    def __init__(self, kind, status=None):
        self.kind, self.status = kind, status
        super().__init__(kind)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise JevError('redirect_rejected', code)


def configuration():
    key = os.environ.get('JEV_API_KEY') or os.environ.get('TYPESAFE_API_KEY')
    if not key:
        raise JevError('credential_missing_in_this_process')
    endpoint = os.environ.get('JEV_API_BASE_URL') or ENDPOINT
    parts = urlsplit(endpoint)
    if (parts.scheme != 'https' or parts.hostname != 'api.typesafe.ai'
            or parts.port not in (None, 443) or parts.username or parts.password
            or parts.query or parts.fragment):
        raise JevError('official_endpoint_required')
    if parts.path.rstrip('/') not in ('', '/v1', '/v1/systemone'):
        raise JevError('systemone_path_required')
    return key, ENDPOINT


def probability(value):
    return type(value) in (float, int) and math.isfinite(value) and 0 <= value <= 1


def parse_response(body, questions, expected_model=MODEL):
    if not isinstance(body, dict) or body.get('model') != expected_model:
        raise JevError('invalid_model_identity')
    answers, usage = body.get('answers'), body.get('usage')
    if not isinstance(answers, dict) or set(answers) != set(questions):
        raise JevError('invalid_answer_identity')
    if not isinstance(usage, dict) or any(type(usage.get(k)) is not int or usage[k] < 0
                                        for k in ('input_tokens', 'output_tokens')):
        raise JevError('invalid_usage')
    clean = {}
    for task_id, question in questions.items():
        answer = answers[task_id]
        if not isinstance(answer, dict) or answer.get('type') != 'choice':
            raise JevError('invalid_answer_type')
        options, distribution = set(question['criteria']), answer.get('probabilities')
        if (not isinstance(distribution, dict) or set(distribution) != options
                or not all(probability(v) for v in distribution.values())
                or abs(sum(distribution.values()) - 1) > 1e-5):
            raise JevError('invalid_distribution')
        choice = answer.get('choice')
        if choice not in options or distribution[choice] < max(distribution.values()) - 1e-6:
            raise JevError('invalid_choice')
        if not probability(answer.get('confidence')):
            raise JevError('invalid_confidence')
        clean[task_id] = {k: answer[k] for k in ('type', 'choice', 'probabilities', 'confidence')}
    return {'model': body['model'], 'answers': clean,
            'usage': {k: usage[k] for k in ('input_tokens', 'output_tokens')}}


def evaluate(state, questions, *, timeout=45, opener=None, model=MODEL):
    key, endpoint = configuration()
    if not re.fullmatch(r'jev-\d+\.\d+\.\d+', model):
        raise JevError('pinned_model_required')
    if not isinstance(questions, dict) or len(questions) != 1:
        raise JevError('one_task_per_request_required')
    for question in questions.values():
        if (not isinstance(question, dict) or question.get('type') != 'choice'
                or not isinstance(question.get('criteria'), dict) or len(question['criteria']) != 3):
            raise JevError('three_candidate_choice_required')
    payload = {'model': model, 'state': state, 'questions': questions}
    raw = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(raw) > 12000:
        raise JevError('synthetic_experiment_input_limit')
    request = Request(endpoint, data=raw, method='POST',
                      headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    started = time.perf_counter()
    try:
        with (opener or build_opener(NoRedirect())).open(request, timeout=timeout) as response:
            data = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        exc.close()
        kinds = {401: 'auth', 402: 'payment_required', 403: 'forbidden', 422: 'validation',
                 429: 'rate_limited', 529: 'overloaded'}
        raise JevError(kinds.get(exc.code, 'http_error'), exc.code) from None
    except JevError:
        raise
    except (URLError, TimeoutError, OSError):
        raise JevError('network_or_timeout') from None
    latency = round((time.perf_counter() - started) * 1000, 2)
    if len(data) > MAX_BYTES:
        raise JevError('response_too_large')
    try:
        body = json.loads(data)
    except (ValueError, UnicodeError):
        raise JevError('invalid_json') from None
    result = parse_response(body, questions, model)
    result['latency_ms'] = latency
    return payload, result
