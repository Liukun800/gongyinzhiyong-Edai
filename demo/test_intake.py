import copy
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from app import Store, ApiError, create_server
from product_contract import build_handoff

def payload():
    return {'title':'独立仿真申请', 'description':'验证用途与经营材料的完整操作过程',
            'data_classification':'synthetic',
            'documents':[{'id':'material1','title':'仿真用途说明','subject':'仿真主体甲',
                          'period':'2026-08','kind':'purpose','paragraphs':[{'id':'p1','text':'资金用于采购生产用铜材。'}]}]}

class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)/'test.sqlite3';self.store=Store(self.path)
    def tearDown(self):
        self.store.db.close();self.tmp.cleanup()
    def row(self,key):
        return next(x for x in self.store.queue()['items'] if x['id']==key)
    def test_create_persist_and_never_reuse_fixture_predictions(self):
        c=self.store.create_case(payload()); self.assertEqual(self.row(c['id'])['state'],'未运行')
        r=self.store.run(c['id'],{'revision':1})
        self.assertTrue(all(t['answer'] is None for t in r['tasks']))
        self.assertEqual(r['usage']['actual_model_requests'],0)
        other=Store(self.path)
        try:self.assertEqual(other.detail(c['id'])['case']['documents'],payload()['documents'])
        finally:other.db.close()
    def test_reject_labels_real_data_duplicate_materials(self):
        variants=[]
        p=payload();p['expected_answer']='一致';variants.append(p)
        p=payload();p['data_classification']='bank';variants.append(p)
        p=payload();p['documents'][0]['label']='一致';variants.append(p)
        p=payload();p['documents'].append(copy.deepcopy(p['documents'][0]));variants.append(p)
        p=payload();p['documents'][0]['paragraphs'][0]['label']='一致';variants.append(p)
        for p in variants:
            with self.subTest(p=p),self.assertRaises(ApiError):self.store.create_case(p)
    def test_custom_reset_is_explicit_error(self):
        c=self.store.create_case(payload())
        with self.assertRaises(ApiError) as e:self.store.reset(c['id'],{'revision':1})
        self.assertEqual(e.exception.status,409)
    def test_queue_review_and_new_material_require_rerun(self):
        c=self.store.create_case(payload());r=self.store.run(c['id'],{'revision':1})
        for task,answer in [('USE_MATCH','一致'),('BIZ_CONFLICT','未发现明确矛盾')]:
            self.store.review(r['id'],{'revision':1,'task_id':task,'action':'resolve','corrected_answer':answer,'reason':'测试人员记录人工核实依据'})
        self.assertEqual(self.row(c['id'])['state'],'辅助核验已复核')
        document=copy.deepcopy(c['documents'][0]);document['paragraphs'][0]['text']='更正后的仿真用途说明'
        self.store.material(c['id'],{'revision':1,'document':document})
        self.assertEqual(self.row(c['id'])['state'],'待重跑')
        h=build_handoff(self.store.detail(c['id']))
        self.assertFalse(h['application_context']['is_latest_run']);self.assertEqual(len(h['unresolved_tasks']),2)
        self.assertIsNone(h['approval_decision'])
    def test_reviewed_conflict_remains_a_pending_business_issue(self):
        r=self.store.run('D02',{'revision':1})
        self.store.review(r['id'],{'revision':1,'task_id':'USE_MATCH','action':'confirm','reason':'已经核对申请用途原文'})
        self.store.review(r['id'],{'revision':1,'task_id':'BIZ_CONFLICT','action':'resolve','corrected_answer':'发现明确矛盾','reason':'人工核实确认仍存在材料矛盾'})
        self.assertEqual(self.row('D02')['state'],'待处理');self.assertEqual(self.row('D02')['unresolved_tasks'],1)
    def test_custom_case_uses_supplied_model_adapter(self):
        class Adapter:
            def evaluate(_,case):
                from engine import evaluate
                result=evaluate(case,None);result['adapter']='test_spy';return result
        c=self.store.create_case(payload());self.store.shadow_engine=Adapter()
        self.assertEqual(self.store.run(c['id'],{'revision':1})['adapter'],'test_spy')
    def test_http_intake_and_queue_require_local_write_token(self):
        server=create_server(0,Path(self.tmp.name)/'http.sqlite3');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            base=f'http://127.0.0.1:{server.server_port}';h=json.load(urllib.request.urlopen(base+'/api/health'))
            req=urllib.request.Request(base+'/api/cases',data=json.dumps(payload()).encode(),headers={'Content-Type':'application/json'})
            with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
            self.assertEqual(e.exception.code,403);req.add_header('X-Demo-Token',h['csrf_token'])
            created=json.load(urllib.request.urlopen(req));q=json.load(urllib.request.urlopen(base+'/api/queue'))
            self.assertIn(created['id'],[r['id'] for r in q['items']])
        finally:
            server.shutdown();server.server_close();thread.join(3);server.store.db.close()

if __name__=='__main__':unittest.main()
