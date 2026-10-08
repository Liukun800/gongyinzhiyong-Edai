"""Bounded judgement service; no agents, tools, lending decisions or cloud routes."""
import argparse
import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from judgement import API_VERSION, MAX_BYTES, VersionedJudgement, specs
from judgement_http import validate_token


def create_judgement_server(predictor, token, port=8148):
    judge = VersionedJudgement(predictor)
    token = validate_token(token)
    identity = {'api_version': API_VERSION, 'status': 'ready', 'model': predictor.info(),
                'decision_specs': specs(), 'adoption_policy': 'auxiliary_human_review'}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log bearer tokens or raw material contents.

        def send(self, result, code=200):
            raw = json.dumps(result, ensure_ascii=False, allow_nan=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass  # Client timeout; no adoption or retry here.

        def authorized(self):
            if (self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}'
                    or self.headers.get('Origin') is not None
                    or not secrets.compare_digest(self.headers.get('Authorization', '').encode('utf-8'),
                                                  ('Bearer ' + token).encode('utf-8'))):
                self.send({'error': 'Unauthorized local judgement request'}, 403)
                return False
            return True

        def do_GET(self):
            if not self.authorized():
                return
            if self.path != '/api/info':
                return self.send({'error': 'Unknown endpoint'}, 404)
            self.send(identity)

        def do_POST(self):
            if not self.authorized():
                return
            if self.path != '/api/judge':
                return self.send({'error': 'Unknown endpoint'}, 404)
            self.connection.settimeout(10)
            try:
                if self.headers.get('Transfer-Encoding') is not None:
                    raise ValueError('Unsupported body framing')
                length = int(self.headers.get('Content-Length', '-1'))
                if not 0 < length <= MAX_BYTES:
                    raise ValueError('Invalid body length')
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict) or set(body) != {'api_version', 'id', 'questions'}:
                    raise ValueError('Only version, request id and questions are accepted')
                if (body['api_version'] != API_VERSION or not isinstance(body['id'], str)
                        or not 1 <= len(body['id']) <= 64):
                    raise ValueError('Invalid request identity/version')
                questions = body['questions']
                if not isinstance(questions, list) or not 1 <= len(questions) <= 2:
                    raise ValueError('Expected one or two bank questions')
                registry = {s['id']: s for s in specs()}
                requests = []
                for q in questions:
                    if not isinstance(q, dict) or set(q) != {'id', 'version', 'question_sha256', 'state'}:
                        raise ValueError('Invalid task fields')
                    if not isinstance(q['id'], str) or q['id'] not in registry:
                        raise ValueError('Unknown bank task')
                    spec = registry[q['id']]
                    if q['version'] != spec['version'] or q['question_sha256'] != spec['question_sha256']:
                        raise ValueError('Task definition mismatch')
                    requests.append((q['state'], spec['question'], spec['options']))
                # All input validation occurs before the predictor is called.
                from judgement import clean_state, validate_state_for_spec
                if len({q['id'] for q in questions}) != len(questions):
                    raise ValueError('Duplicate bank task')
                for request, q in zip(requests, questions):
                    validate_state_for_spec(clean_state(request[0]), registry[q['id']])
            except (ValueError, TypeError, TimeoutError, KeyError, UnicodeDecodeError):
                return self.send({'error': 'Invalid bounded judgement request'}, 400)
            try:
                predictions = judge.decide_many(requests)
            except Exception:
                return self.send({'error': 'Judgement unavailable; retain human handling'}, 503)
            self.send({'api_version': API_VERSION, 'id': body['id'], 'model': identity['model'],
                       'answers': [{'id': q['id'], 'version': q['version'], 'prediction': p}
                                   for q, p in zip(questions, predictions)]})

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8148)
    parser.add_argument('--token-file', required=True)
    args = parser.parse_args()
    token_path = Path(args.token_file)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    if not token_path.exists():
        # Exclusive creation; token must stay in local runtime, outside audit records.
        with token_path.open('x', encoding='utf-8') as f:
            f.write(secrets.token_urlsafe(32))
    token = validate_token(token_path.read_text(encoding='utf-8').strip())
    from real_model import PublicDecisionModel
    server = create_judgement_server(PublicDecisionModel(), token, args.port)
    print(f'Local judgement ready: http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
