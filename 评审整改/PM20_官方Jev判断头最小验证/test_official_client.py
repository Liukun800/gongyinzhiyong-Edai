import copy
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from official_client import JevError, NoRedirect, configuration, evaluate, parse_response

QUESTIONS = {'USE_MATCH': {'type': 'choice', 'instructions': 'Compare materials',
                          'criteria': {'一致': 'match', '存在明确矛盾': 'conflict', '信息不足': 'missing'}}}
BODY = {'model': 'jev-1.13.0', 'answers': {'USE_MATCH': {
    'type': 'choice', 'choice': '一致',
    'probabilities': {'一致': 0.8, '存在明确矛盾': 0.1, '信息不足': 0.1}, 'confidence': 0.7}},
    'usage': {'input_tokens': 100, 'output_tokens': 12}}


class FakeOpener:
    def __init__(self, body=BODY, error=None):
        self.body, self.error, self.calls = body, error, 0

    def open(self, request, timeout):
        self.calls += 1
        if self.error:
            raise self.error
        return io.BytesIO(json.dumps(self.body, ensure_ascii=False).encode('utf-8'))


class OfficialClientTests(unittest.TestCase):
    def test_missing_config_does_not_call(self):
        opener = FakeOpener()
        with patch.dict('os.environ', {}, clear=True), self.assertRaises(JevError):
            evaluate({}, QUESTIONS, opener=opener)
        self.assertEqual(opener.calls, 0)

    def test_endpoint_aliases(self):
        for base in ('https://api.typesafe.ai', 'https://api.typesafe.ai/v1', 'https://api.typesafe.ai/v1/systemone/'):
            with patch.dict('os.environ', {'JEV_API_KEY':'test-secret', 'JEV_API_BASE_URL':base}, clear=True):
                self.assertEqual(configuration()[1], 'https://api.typesafe.ai/v1/systemone')

    def test_foreign_and_insecure_endpoints_rejected(self):
        for base in ('http://api.typesafe.ai/v1/systemone', 'https://api.typesafe.ai.evil.test/v1/systemone',
                     'https://api.typesafe.ai/v1/chat/completions', 'https://user:password@api.typesafe.ai/v1/systemone',
                     'https://api.typesafe.ai/v1/systemone?key=test', 'https://api.typesafe.ai:444/v1/systemone'):
            with patch.dict('os.environ', {'JEV_API_KEY':'test-secret', 'JEV_API_BASE_URL':base}, clear=True):
                with self.assertRaises(JevError):
                    configuration()

    def test_redirect_rejected(self):
        with self.assertRaises(JevError):
            NoRedirect().redirect_request(None,None,302,'Found',{},'https://example.test')

    def test_structured_success_keeps_no_reason_or_secret(self):
        body = copy.deepcopy(BODY)
        body['debug'] = 'test-secret'
        body['answers']['USE_MATCH']['reason'] = 'not an allowed field'
        opener = FakeOpener(body)
        with patch.dict('os.environ', {'JEV_API_KEY':'test-secret'}, clear=True):
            request, result = evaluate({'materials':[]}, QUESTIONS, opener=opener)
        self.assertEqual(opener.calls,1)
        self.assertEqual(request['questions'],QUESTIONS)
        self.assertNotIn('test-secret',json.dumps(result))
        self.assertNotIn('reason',result['answers']['USE_MATCH'])
        self.assertEqual(result['model'],'jev-1.13.0')

    def test_bad_distributions_rejected(self):
        variants = [ {'一致':1.0}, {'一致':0.4,'存在明确矛盾':0.1,'信息不足':0.1},
                     {'一致':float('nan'),'存在明确矛盾':0.1,'信息不足':0.1},
                     {'一致':True,'存在明确矛盾':0.0,'信息不足':0.0},
                     {'一致':1.1,'存在明确矛盾':-0.1,'信息不足':0.0} ]
        for dist in variants:
            body=copy.deepcopy(BODY)
            body['answers']['USE_MATCH']['probabilities']=dist
            with self.assertRaises(JevError):
                parse_response(body,QUESTIONS)

    def test_wrong_identity_choice_and_confidence_rejected(self):
        changes=[('type','score'),('choice','unknown'),('choice','信息不足'),('confidence',2),('confidence',True)]
        for field,value in changes:
            body=copy.deepcopy(BODY)
            body['answers']['USE_MATCH'][field]=value
            with self.assertRaises(JevError):
                parse_response(body,QUESTIONS)
        for model in ('jev-latest','other-model','test-secret'):
            body=copy.deepcopy(BODY);body['model']=model
            with self.assertRaises(JevError):
                parse_response(body,QUESTIONS)

    def test_bad_usage_and_task_identity_rejected(self):
        for value in (-1,True,None):
            body=copy.deepcopy(BODY);body['usage']['input_tokens']=value
            with self.assertRaises(JevError):
                parse_response(body,QUESTIONS)
        body=copy.deepcopy(BODY);body['answers']['unknown']=body['answers'].pop('USE_MATCH')
        with self.assertRaises(JevError):
            parse_response(body,QUESTIONS)

    def test_failure_is_classified_without_response_body_or_retry(self):
        for code,kind in ((401,'auth'),(402,'payment_required'),(429,'rate_limited'),(529,'overloaded')):
            opener=FakeOpener(error=HTTPError('https://api.typesafe.ai',code,'test-secret',{},io.BytesIO(b'test-secret')))
            with patch.dict('os.environ',{'JEV_API_KEY':'test-secret'},clear=True):
                with self.assertRaises(JevError) as context:
                    evaluate({},QUESTIONS,opener=opener)
            self.assertEqual(context.exception.kind,kind)
            self.assertNotIn('test-secret',str(context.exception))
            self.assertEqual(opener.calls,1)

    def test_network_failure_no_retry(self):
        opener=FakeOpener(error=URLError('test-secret'))
        with patch.dict('os.environ',{'JEV_API_KEY':'test-secret'},clear=True):
            with self.assertRaises(JevError) as context:
                evaluate({},QUESTIONS,opener=opener)
        self.assertNotIn('test-secret',str(context.exception))
        self.assertEqual(opener.calls,1)


if __name__ == '__main__':
    unittest.main()
