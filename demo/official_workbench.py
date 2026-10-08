"""Opt-in official workbench, isolated from existing Demo modes and databases."""
import argparse
from pathlib import Path
from urllib.parse import urlparse

from app import Handler, ROOT, create_server
from official_model import OfficialDecisionModel, OfficialShadowEngine
from typesafe_client import configuration


class OfficialHandler(Handler):
    def do_POST(self):
        if self.server.store.shadow_engine.info().get('offline_test_mode'):
            return self.respond({'error': '接入预览只读，不发起官方请求。'}, 403)
        return super().do_POST()

    def do_GET(self):
        path = urlparse(self.path).path
        if path not in ('/', '/official-ui.js', '/official.css'):
            return super().do_GET()
        try:
            self.check_host()
            if path == '/official-ui.js':
                return self.respond((ROOT / 'static/official-ui.js').read_bytes(),
                                    content_type='text/javascript; charset=utf-8')
            if path == '/official.css':
                return self.respond((ROOT / 'static/official.css').read_bytes(),
                                    content_type='text/css; charset=utf-8')
            html = (ROOT / 'static/index.html').read_text(encoding='utf-8')
            html = html.replace('</head>', '<link rel="stylesheet" href="/official.css"></head>')
            html = html.replace('</body>', '<script src="/official-ui.js" defer></script></body>')
            self.respond(html.encode('utf-8'), content_type='text/html; charset=utf-8')
        except Exception:
            self.respond({'error': 'Official view unavailable'}, 400)


def create_official_server(port=8771, db_path=None, predictor=None):
    if db_path is None:
        (ROOT / 'runtime').mkdir(exist_ok=True)
        db_path = ROOT / 'runtime/official-jev-demo.sqlite3'
    server = create_server(port, db_path, OfficialShadowEngine(predictor or OfficialDecisionModel()))
    server.RequestHandlerClass = OfficialHandler
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8771)
    parser.add_argument('--db', type=Path)
    parser.add_argument('--max-requests', type=int, default=20)
    parser.add_argument('--preview', action='store_true', help='Read-only view; no cloud requests')
    args = parser.parse_args()
    if args.preview:
        from typesafe_client import JevError
        def disabled(*args, **kwargs):
            raise JevError('preview_has_no_network_transport')
        predictor = OfficialDecisionModel(transport=disabled)
    else:
        configuration()
        predictor = OfficialDecisionModel(max_requests=args.max_requests)
    server = create_official_server(args.port, args.db, predictor)
    print(f'Official workbench: http://127.0.0.1:{server.server_port} | preview={args.preview}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        server.store.db.close()
