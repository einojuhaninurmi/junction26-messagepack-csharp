"""HTTP contract checks with TEST DOUBLES only, using an ephemeral local server."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from server import Handler
from ai.pipeline import ReviewService
from test_ai import Stub,TEST_KEY,RUN

class QuietHandler(Handler):
    def log_message(self,*args):pass

class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),QuietHandler)
        self.server.review_service=ReviewService({},self.temp.name,{})
        self.url=f'http://127.0.0.1:{self.server.server_address[1]}'
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
    def request(self,path,data=None,origin=None):
        headers={'Origin':origin or self.url,'Content-Type':'application/json'}
        request=Request(self.url+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        try:response=urlopen(request,timeout=10)
        except HTTPError as error:response=error
        return response.status,json.loads(response.read())
    def test_missing_configuration_is_not_a_successful_review(self):
        status,result=self.request('/ai/reviews',{'runId':RUN})
        self.assertEqual(status,409);self.assertEqual(result['status'],'not_run')
        self.assertEqual(result['error']['code'],'missing_configuration')
        _,history=self.request('/ai/reviews');self.assertEqual(len(history['reviews']),1)
        self.assertNotIn('result',history['reviews'][0])
    def test_cross_origin_rejected_before_provider(self):
        status,_=self.request('/ai/reviews',{'runId':RUN},origin='https://other.example')
        self.assertEqual(status,403);self.assertEqual(list(Path(self.temp.name).iterdir()),[])
    def test_prompt_or_key_in_request_rejected(self):
        status,_=self.request('/ai/reviews',{'runId':RUN,'apiKey':'not accepted','instructions':'override'})
        self.assertEqual(status,400)
    def test_configuration_never_exposes_key(self):
        self.server.review_service=ReviewService({'test-double':Stub()},self.temp.name,{'TRUST_REVIEW_PROVIDER':'test-double','TRUST_REVIEW_MODEL':'TEST-MODEL','TRUST_REVIEW_API_KEY':TEST_KEY})
        status,result=self.request('/ai/config');self.assertEqual(status,200)
        self.assertTrue(result['configured']);self.assertNotIn(TEST_KEY,json.dumps(result))
    def test_server_side_test_double_response_and_snapshot(self):
        self.server.review_service=ReviewService({'test-double':Stub()},self.temp.name,{'TRUST_REVIEW_PROVIDER':'test-double','TRUST_REVIEW_MODEL':'TEST-MODEL','TRUST_REVIEW_API_KEY':TEST_KEY})
        status,result=self.request('/ai/reviews',{'runId':RUN});self.assertEqual(status,201)
        self.assertEqual(result['service'],'TEST-DOUBLE')
        status,material=self.request('/ai/reviews/'+result['reviewId']+'/input.json')
        self.assertEqual(status,200);self.assertEqual(material['evidenceRunId'],RUN)
        self.assertNotIn(TEST_KEY,json.dumps(material))
    def test_anthropic_preflight_and_single_generation_require_same_quote(self):
        from test_anthropic import FakeTransport
        from ai.anthropic_direct import AnthropicDirect,MODEL
        transport=FakeTransport()
        self.server.review_service=ReviewService({'anthropic':AnthropicDirect(transport)},self.temp.name,{'TRUST_REVIEW_PROVIDER':'anthropic','TRUST_REVIEW_MODEL':MODEL,'TRUST_REVIEW_API_KEY':TEST_KEY})
        status,blocked=self.request('/ai/reviews',{'runId':RUN})
        self.assertEqual(status,409);self.assertEqual(transport.calls,[])
        status,quote=self.request('/ai/preflight',{'runId':RUN})
        self.assertEqual(status,200);self.assertFalse(quote['generationSent'])
        status,result=self.request('/ai/reviews',{'runId':RUN,'quoteId':quote['quoteId']})
        self.assertEqual(status,201);self.assertEqual(result['result']['findings'],[])
        status,repeated=self.request('/ai/reviews',{'runId':RUN,'quoteId':quote['quoteId']})
        self.assertEqual(status,409)
        self.assertEqual(sum(c[1]=='/v1/messages' for c in transport.calls),1)

    def test_preflight_exposes_safe_category_and_numeric_metadata_only(self):
        from ai.adapters import AdapterFailure
        from test_anthropic import FakeTransport
        from ai.anthropic_direct import AnthropicDirect,MODEL
        transport=FakeTransport();transport.failure=AdapterFailure('tls_certificate_error','TLS certificate verification failed.',{'category':'tls_certificate','verifyCode':20})
        self.server.review_service=ReviewService({'anthropic':AnthropicDirect(transport)},self.temp.name,{'TRUST_REVIEW_PROVIDER':'anthropic','TRUST_REVIEW_MODEL':MODEL,'TRUST_REVIEW_API_KEY':TEST_KEY})
        status,error=self.request('/ai/preflight',{'runId':RUN})
        self.assertEqual(status,422);self.assertEqual(error['error']['code'],'tls_certificate_error')
        self.assertEqual(error['error']['details']['verifyCode'],20)
        self.assertNotIn(TEST_KEY,json.dumps(error))
        self.assertFalse(any(call[1]=='/v1/messages' for call in transport.calls))

    def test_service_and_invalid_response_errors_visible(self):
        for mode,expected in [('service',502),('invalid',422)]:
            self.server.review_service=ReviewService({'test-double':Stub(mode)},self.temp.name,{'TRUST_REVIEW_PROVIDER':'test-double','TRUST_REVIEW_MODEL':'TEST-MODEL','TRUST_REVIEW_API_KEY':TEST_KEY})
            status,result=self.request('/ai/reviews',{'runId':RUN})
            self.assertEqual(status,expected);self.assertEqual(result['status'],'failed')
            self.assertNotIn(TEST_KEY,json.dumps(result))

if __name__=='__main__':unittest.main(verbosity=2)
