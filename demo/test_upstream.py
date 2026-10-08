"""HTTP contract tests use a fake server, not model-quality evidence."""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from upstream_model import UpstreamDecisionModel


class ContractTests(unittest.TestCase):
    def setUp(self):
        owner = self
        self.mutate = lambda r: None
        self.seen = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def send(self, obj):
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps(obj).encode())
            def do_GET(self):
                self.send({'status':'ready','api_version':'agentjev.decision.v1','types':['choice'],
                           'output_token_decoding':False,'checkpoint_sha256':'a'*64,'checkpoint':'test'})
            def do_POST(self):
                b = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.seen.append(b)
                r = {'api_version':'agentjev.decision.v1','results':[{'id':b['id'],'answers':[
                    {'id':'decision','type':'choice','value':'0','top_probability':0.7,
                     'distribution':{'0':0.7,'1':0.2,'2':0.1}}]}],
                     'usage':{'generated_tokens':0,'truncated_inputs':0,'candidate_paths':3,
                              'input_path_tokens':123,'wall_ms':7}}
                owner.mutate(r); self.send(r)
        self.server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.model = UpstreamDecisionModel(f'http://127.0.0.1:{self.server.server_port}')
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
    def predict(self): return self.model.decide({'materials':[]},'判断', ['一致','矛盾','不足'])
    def test_real_http_contract_maps_candidate_keys(self):
        p = self.predict()
        self.assertEqual(p['answer'],'一致'); self.assertEqual(p['input_path_tokens'],123)
        self.assertEqual(set(self.seen[0]),{'id','state','questions'})
        self.assertFalse(self.model.info()['auto_completion_enabled'])
    def test_identity_mismatch_rejected(self):
        self.mutate = lambda r:r['results'][0].update(id='wrong')
        with self.assertRaises(ValueError): self.predict()
    def test_truncation_and_bad_distribution_rejected(self):
        self.mutate = lambda r:r['usage'].update(truncated_inputs=1)
        with self.assertRaises(ValueError): self.predict()
        self.mutate = lambda r:r['results'][0]['answers'][0].update(top_probability=0.9)
        with self.assertRaises(ValueError): self.predict()
    def test_remote_url_and_label_state_rejected(self):
        with self.assertRaises(ValueError): UpstreamDecisionModel('http://example.com:8149')
        with self.assertRaises(ValueError): self.model.decide({'materials':[],'label':'一致'},'判断',['一致'])

if __name__ == '__main__': unittest.main()
