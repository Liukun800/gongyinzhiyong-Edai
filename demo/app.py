"""Local-only workflow demo. Python standard library; no external model calls."""
import argparse
import json
import secrets
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from engine import ANSWERS, TASKS, evaluate
from product_contract import build_handoff, development_summary

ROOT = Path(__file__).resolve().parent
APP_REVISION = '2026-10-02-pm12-showcase'


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ApiError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status


class Store:
    def __init__(self, db_path, shadow_engine=None):
        self.lock = threading.RLock()
        self.shadow_engine = shadow_engine
        self.db = sqlite3.connect(str(db_path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.fixtures = json.loads((ROOT / "data/cases.json").read_text(encoding="utf-8"))
        self.annotations = {} if shadow_engine else json.loads((ROOT / "data/annotations.json").read_text(encoding="utf-8"))
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, case_id TEXT, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT, body TEXT NOT NULL);
        """)
        with self.db:
            for item in self.fixtures:
                case = {**item, "revision": 1}
                self.db.execute("INSERT OR IGNORE INTO cases VALUES (?,?)", (case["id"], self.dumps(case)))

    @staticmethod
    def dumps(value):
        return json.dumps(value, ensure_ascii=False)

    def _case(self, key):
        row = self.db.execute("SELECT body FROM cases WHERE id=?", (key,)).fetchone()
        if not row:
            raise ApiError("样例不存在", 404)
        return json.loads(row[0])

    def _event(self, key, kind, message, **fields):
        event = {"time": now(), "kind": kind, "message": message, **fields}
        self.db.execute("INSERT INTO events(case_id,body) VALUES (?,?)", (key, self.dumps(event)))

    def _save_case(self, case):
        self.db.execute("UPDATE cases SET body=? WHERE id=?", (self.dumps(case), case["id"]))

    def _revision(self, case, body):
        if body.get("revision") != case["revision"]:
            raise ApiError("材料版本已变化，请刷新后重试。", 409)

    def list_cases(self):
        with self.lock:
            return [{k: c[k] for k in ("id", "title", "description", "revision")}
                    for c in (json.loads(r[0]) for r in self.db.execute("SELECT body FROM cases ORDER BY id"))]

    def detail(self, key):
        with self.lock:
            case = self._case(key)
            runs = [json.loads(r[0]) for r in self.db.execute("SELECT body FROM runs WHERE case_id=? ORDER BY rowid DESC", (key,))]
            events = [json.loads(r[0]) for r in self.db.execute("SELECT body FROM events WHERE case_id=? ORDER BY seq DESC", (key,))]
            return {"case": case, "runs": runs, "events": events}

    def create_case(self, body):
        if set(body) != {'title', 'description', 'documents', 'data_classification'}:
            raise ApiError('申请仅接受名称、说明、材料与仿真数据声明，不接受标签或预期答案')
        if body['data_classification'] != 'synthetic':
            raise ApiError('本地原型仅接受仿真材料')
        for field, limit in [('title', 100), ('description', 600)]:
            if not isinstance(body[field], str) or not body[field].strip() or len(body[field]) > limit:
                raise ApiError('申请名称或说明为空或过长')
        docs = body['documents']
        if not isinstance(docs, list) or not 1 <= len(docs) <= 20:
            raise ApiError('请提交1至20份仿真材料')
        for document in docs:
            self.validate_document(document)
            if set(document) != {'id', 'title', 'subject', 'period', 'kind', 'paragraphs'}:
                raise ApiError('材料只能包含登记字段和原文，不接受参考答案')
            if any(set(p) != {'id', 'text'} for p in document['paragraphs']):
                raise ApiError('段落只接受编号与原文')
        if len({d['id'] for d in docs}) != len(docs):
            raise ApiError('材料编号重复')
        case = {'id': 'S-' + uuid.uuid4().hex[:12], 'title': body['title'].strip(),
                'description': body['description'].strip(), 'documents': docs, 'revision': 1,
                'origin': 'custom_intake', 'data_classification': 'synthetic', 'created_at': now()}
        with self.lock, self.db:
            self.db.execute('INSERT INTO cases VALUES (?,?)', (case['id'], self.dumps(case)))
            self._event(case['id'], 'intake', '已建立自定义仿真申请', revision=1)
        return case

    def queue(self):
        with self.lock:
            rows = []
            for c in self.list_cases():
                d = self.detail(c['id']); latest = d['runs'][0] if d['runs'] else None
                state, unresolved, model_requests = '未运行', 2, 0
                if latest:
                    model_requests = latest['usage']['actual_model_requests']
                    if latest['revision'] != c['revision']:
                        state = '待重跑'
                    else:
                        h = build_handoff(d)
                        unresolved = len(h['unresolved_tasks'])
                        state = '待处理' if unresolved else '辅助核验已复核'
                rows.append({**c, 'state': state, 'unresolved_tasks': unresolved,
                             'actual_model_requests': model_requests,
                             'origin': d['case'].get('origin', 'preset_fixture')})
            return {'scope': '本地辅助核验待办，不表示审批结果', 'items': rows,
                    'counts': {s: sum(r['state'] == s for r in rows)
                               for s in ['未运行', '待重跑', '待处理', '辅助核验已复核']}}

    def run(self, key, body):
        # Snapshot under the lock, infer without holding the database lock, then persist.
        # Reads, queue refreshes and edits for other applications remain available.
        with self.lock:
            case = self._case(key)
            self._revision(case, body)
            case = json.loads(self.dumps(case))
            annotation = self.annotations.get(key)
        result = self.shadow_engine.evaluate(case) if self.shadow_engine else evaluate(case, annotation)
        with self.lock, self.db:
            result.update(id=uuid.uuid4().hex, created_at=now(), material_snapshot=case["documents"])
            self.db.execute("INSERT INTO runs VALUES (?,?,?)", (result["id"], key, self.dumps(result)))
            self._event(key, "run", "完成真实模型影子判断" if self.shadow_engine else "完成流程模拟，保留两项任务结果", revision=case["revision"], run_id=result["id"],
                        actual_model_requests=result['usage']['actual_model_requests'], simulated_analysis_requests=result["usage"]["simulated_analysis_requests"])
            return result

    @staticmethod
    def validate_document(doc):
        if not isinstance(doc, dict):
            raise ApiError("材料必须为对象")
        for key in ("id", "title", "subject", "period", "kind"):
            if not isinstance(doc.get(key), str) or not doc[key].strip() or len(doc[key]) > 160:
                raise ApiError(f"材料字段 {key} 不能为空或过长")
        if doc['kind'] not in ('purpose', 'business'):
            raise ApiError('材料类型只支持purpose或business')
        paragraphs = doc.get("paragraphs")
        if not isinstance(paragraphs, list) or not 1 <= len(paragraphs) <= 20:
            raise ApiError("材料需要1至20个段落")
        ids = set()
        for p in paragraphs:
            if not isinstance(p, dict) or not isinstance(p.get("id"), str) or not p["id"] or p["id"] in ids:
                raise ApiError("段落编号为空或重复")
            if not isinstance(p.get("text"), str) or not p["text"].strip() or len(p["text"]) > 20000:
                raise ApiError("段落内容不能为空或过长")
            ids.add(p["id"])

    def shadow_probe(self, body):
        """Transient experiment request: accepts materials and task IDs only, no labels."""
        if not self.shadow_engine:
            raise ApiError('当前未加载真实模型', 409)
        if set(body) != {'documents', 'task_ids'}:
            raise ApiError('实验接口只接受documents与task_ids；不接受标签或预期结果')
        docs, task_ids = body['documents'], body['task_ids']
        if not isinstance(docs, list) or not 1 <= len(docs) <= 20:
            raise ApiError('实验请求需包含1至20份材料')
        if (not isinstance(task_ids, list) or not 1 <= len(task_ids) <= 2
                or any(not isinstance(t, str) or t not in TASKS for t in task_ids)
                or len(set(task_ids)) != len(task_ids)):
            raise ApiError('任务编号无效或重复')
        for doc in docs:
            self.validate_document(doc)
        if len({d['id'] for d in docs}) != len(docs):
            raise ApiError('材料编号重复')
        clean = [{k: d[k] for k in ('id', 'title', 'subject', 'period', 'kind', 'paragraphs')} for d in docs]
        return self.shadow_engine.evaluate({'id': 'transient', 'revision': 1, 'documents': clean}, task_ids)

    def material(self, key, body):
        doc = body.get("document")
        self.validate_document(doc)
        with self.lock, self.db:
            case = self._case(key)
            self._revision(case, body)
            old = next((i for i, d in enumerate(case["documents"]) if d["id"] == doc["id"]), None)
            if old is None:
                if len(case["documents"]) >= 20:
                    raise ApiError("演示材料最多20份")
                case["documents"].append(doc)
            else:
                case["documents"][old] = doc
            case["revision"] += 1
            self._save_case(case)
            self._event(key, "material", "材料已更新，旧结果保留；当前版本需要重跑", revision=case["revision"], document_id=doc["id"])
            return case

    def reset(self, key, body):
        with self.lock, self.db:
            current = self._case(key)
            self._revision(current, body)
            original = next((c for c in self.fixtures if c["id"] == key), None)
            if original is None:
                raise ApiError('自建申请无预设材料；请编辑材料后重跑', 409)
            case = {**original, "revision": current["revision"] + 1}
            self._save_case(case)
            self._event(key, "reset", "恢复预设材料为新版本；未删除历史运行与复核记录", revision=case["revision"])
            return case

    def review(self, run_id, body):
        with self.lock, self.db:
            row = self.db.execute("SELECT body FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                raise ApiError("运行记录不存在", 404)
            run = json.loads(row[0])
            case = self._case(run["case_id"])
            self._revision(case, body)
            latest = self.db.execute("SELECT id FROM runs WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case["id"],)).fetchone()[0]
            if run["revision"] != case["revision"] or latest != run_id:
                raise ApiError("只能复核当前材料版本的最新运行，请重新运行。", 409)
            task = next((t for t in run["tasks"] if t["id"] == body.get("task_id")), None)
            if not task:
                raise ApiError("核验任务不存在")
            reason = body.get("reason", "")
            if not isinstance(reason, str) or len(reason.strip()) < 4 or len(reason) > 2000:
                raise ApiError("请填写4至2000字的复核依据")
            action = body.get("action")
            if action not in ("confirm", "resolve", "supplement", "refer", "correct"):
                raise ApiError("未知复核动作")
            effective_status = task['review']['status'] if task.get('review') else task['status']
            if action == "confirm" and effective_status != "待复核":
                raise ApiError("该任务不能直接确认，请补充材料或记录人工核实结论")
            if action == "resolve" and effective_status != "待人工核实":
                raise ApiError("此动作仅用于人工核实任务")
            corrected = body.get("corrected_answer")
            if action in ("resolve", "correct") and corrected not in ANSWERS[task["id"]]:
                raise ApiError("请选择有效的人工判断")
            effective_answer = task['review']['answer'] if task.get('review') else task['answer']
            answer = corrected if action in ("resolve", "correct") else effective_answer
            incomplete = answer in ("信息不足", "无法比较")
            status = {"confirm": "人工复核完成", "resolve": "人工核实已记录", "supplement": "待补充",
                      "refer": "待人工核实", "correct": "人工纠正已记录"}[action]
            if action in ("resolve", "correct") and incomplete:
                status = "待补充"
            review = {"time": now(), "action": action, "reason": reason.strip(), "answer": answer,
                      "status": status, "actor": "本地演示操作者（未认证）"}
            task["review"] = review
            self.db.execute("UPDATE runs SET body=? WHERE id=?", (self.dumps(run), run_id))
            self._event(case["id"], "review", status, run_id=run_id, task_id=task["id"], revision=case["revision"], review=review)
            return run


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def respond(self, value, status=200, content_type="application/json; charset=utf-8"):
        data = json.dumps(value, ensure_ascii=False).encode() if content_type.startswith("application/json") else value
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)

    def check_host(self):
        if self.headers.get("Host") not in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"):
            raise ApiError("仅允许本地访问", 403)

    def do_GET(self):
        try:
            self.check_host()
            path = urlparse(self.path).path
            if path == "/favicon.ico":
                return self.respond(b"", 204, "image/x-icon")
            if path == "/api/health":
                shadow = self.server.store.shadow_engine
                return self.respond({"app": "jev-credit-demo", "status": "ok", "mode": ("真实快慢协同实验" if shadow.info().get("dual_system") else "真实模型影子") if shadow else "流程模拟",
                                     "app_revision": APP_REVISION,
                                     "model_loaded": bool(shadow), "model": shadow.info() if shadow else None, "csrf_token": self.server.token})
            if path == "/api/development":
                return self.respond(development_summary(ROOT))
            if path == "/api/cases":
                return self.respond(self.server.store.list_cases())
            if path == '/api/queue':
                return self.respond(self.server.store.queue())
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[:2] == ["api", "cases"] and parts[3] == "handoff":
                try:
                    query = parse_qs(urlparse(self.path).query)
                    return self.respond(build_handoff(self.server.store.detail(parts[2]), query.get('run_id', [None])[0]))
                except ValueError as exc:
                    raise ApiError(str(exc), 409)
            if len(parts) == 3 and parts[:2] == ["api", "cases"]:
                return self.respond(self.server.store.detail(parts[2]))
            assets = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/style.css": ("style.css", "text/css; charset=utf-8")}
            assets.update({"/showcase.js": ("showcase.js", "text/javascript; charset=utf-8"),
                           "/showcase.css": ("showcase.css", "text/css; charset=utf-8"),
                           "/product.js": ("product.js", "text/javascript; charset=utf-8"),
                           "/intake.js": ("intake.js", "text/javascript; charset=utf-8"),
                           "/blue.css": ("blue.css", "text/css; charset=utf-8"),
                           "/product.css": ("product.css", "text/css; charset=utf-8"),
                           "/ecosystem.svg": ("ecosystem.svg", "image/svg+xml"),
                           "/pm15-relations.svg": ("pm15-relations.svg", "image/svg+xml"),
                           "/pm15-handoff.svg": ("pm15-handoff.svg", "image/svg+xml")})
            if path not in assets:
                raise ApiError("页面不存在", 404)
            name, mime = assets[path]
            self.respond((ROOT / "static" / name).read_bytes(), content_type=mime)
        except ApiError as exc:
            self.respond({"error": exc.message}, exc.status)

    def do_POST(self):
        try:
            self.check_host()
            if self.headers.get("X-Demo-Token") != self.server.token:
                raise ApiError("页面会话失效，请刷新", 403)
            origin = self.headers.get("Origin")
            if origin and origin not in (f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"):
                raise ApiError("不接受其他站点的写入请求", 403)
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise ApiError("请求长度无效")
            if not 0 < length <= 300000:
                raise ApiError("请求为空或超过演示容量", 413)
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ApiError("请求需要JSON对象")
            parts = urlparse(self.path).path.strip("/").split("/")
            if parts == ['api', 'cases']:
                result = self.server.store.create_case(body)
            elif parts == ['api', 'shadow', 'evaluate']:
                result = self.server.store.shadow_probe(body)
            elif len(parts) == 4 and parts[:2] == ["api", "cases"] and parts[3] in ("run", "material", "reset"):
                result = getattr(self.server.store, parts[3])(parts[2], body)
            elif len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "review":
                result = self.server.store.review(parts[2], body)
            else:
                raise ApiError("接口不存在", 404)
            self.respond(result)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.respond({"error": "JSON格式错误"}, 400)
        except ApiError as exc:
            self.respond({"error": exc.message}, exc.status)
        except sqlite3.Error:
            self.respond({"error": "核验记录保存失败，本次建议未采用。请保留材料，按原业务流程人工处理。"}, 503)
        except Exception:
            self.respond({"error": "处理失败，未能完成本次操作。"}, 500)


def create_server(port=8765, db_path=None, shadow_engine=None):
    if db_path is None:
        (ROOT / "runtime").mkdir(exist_ok=True)
        db_path = ROOT / ('runtime/real-demo.sqlite3' if shadow_engine else 'runtime/demo.sqlite3')
    store = Store(db_path, shadow_engine)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.store, server.token = store, secrets.token_urlsafe(32)
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", default=None)
    parser.add_argument("--mode", choices=['simulation', 'shadow', 'dual'], default='simulation')
    parser.add_argument('--model-backend', choices=['local', 'upstream', 'service'], default='local')
    parser.add_argument('--jev-url', default='http://127.0.0.1:8149')
    parser.add_argument('--judge-url', default='http://127.0.0.1:8148')
    parser.add_argument('--judge-token-file', default=None)
    args = parser.parse_args()
    shadow = None
    if args.mode in ('shadow', 'dual'):
        from shadow_engine import ShadowEngine
        if args.model_backend == 'service':
            from judgement_http import HttpJudgement
            if not args.judge_token_file:
                parser.error('--model-backend service requires --judge-token-file')
            predictor = HttpJudgement(args.judge_url, Path(args.judge_token_file).read_text(encoding='utf-8').strip())
            shadow = ShadowEngine(predictor)
        elif args.model_backend == 'upstream':
            from upstream_model import UpstreamDecisionModel
            shadow = ShadowEngine(UpstreamDecisionModel(args.jev_url))
        else:
            from real_model import PublicDecisionModel
            from judgement import VersionedJudgement
            shadow = ShadowEngine(VersionedJudgement(PublicDecisionModel()))
        if args.mode == 'dual':
            from dual_engine import DualEngine
            from slow_model import LocalSlowModel
            shadow = DualEngine(shadow.predictor, LocalSlowModel())
    server = create_server(args.port, args.db, shadow)
    print(f"Demo: http://127.0.0.1:{server.server_port} | {args.mode}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        server.store.db.close()
