from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from ems.search_index import ensure_index
from ems.storage import prepare,EMSDataError
from ems.web import create_app,Settings
from ems.xmlio import Q
from tests.test_import import record,field,xmlfile


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.root=Path(cls.temp.name)
        cls.data=cls.root/'data'
        unsafe=record('EMS000003','õun')
        unsafe.find(Q+"datafield[@tag='150']/"+Q+"subfield[@code='0']").text='javascript:alert(1)'
        cls.xml=xmlfile(cls.root/'source.xml',
            record('EMS000001','raamatukogud',extra=[field('450',[('a','libraries')],ind2='9')]),
            record('EMS000002','tehisintellekt'),unsafe)
        prepare(cls.data,cls.xml)
        ensure_index(cls.data)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.app=create_app(Settings(self.data))
        self.client=TestClient(self.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None,None,None)

    def test_pages_navigation_and_health(self):
        self.assertEqual(self.client.get('/').url.path,'/search')
        for path,label in [('/search','Otsi EMS-ist'),('/keywords','Leia tekstist märksõnad')]:
            response=self.client.get(path)
            self.assertEqual(response.status_code,200)
            soup=BeautifulSoup(response.text,'html.parser')
            self.assertEqual(soup.html['lang'],'et')
            self.assertEqual(soup.select_one('[aria-current="page"]').get_text(),label)
            self.assertIn('LLM-i ei kasutata',response.text)
        self.assertEqual(self.client.get('/health').json(),{'status':'ready'})
        self.assertEqual(self.client.get('/static/style.css').status_code,200)

    def test_lookup_lemma_and_english(self):
        response=self.client.post('/search',data={'query':'raamatukogudes','mode':'lemma','language':'et','limit':'5'})
        self.assertEqual(response.status_code,200)
        self.assertIn('raamatukogud',response.text)
        self.assertIn('Lemmafraas',response.text)
        response=self.client.post('/search',data={'query':'libraries','language':'en','mode':'exact','limit':'1'})
        self.assertIn('EMS000001',response.text)
        self.assertIn('Täpne algkuju',response.text)

    def test_text_and_file_results_agree(self):
        text='Raamatukogudes kasutatakse tehisintellekti.'
        typed=self.client.post('/keywords',data={'text':text,'limit':'5'})
        uploaded=self.client.post('/keywords',data={'limit':'5'},files={'file':('tekst.txt',text.encode('utf-8'),'text/plain')})
        for response in (typed,uploaded):
            self.assertEqual(response.status_code,200)
            soup=BeautifulSoup(response.text,'html.parser')
            self.assertEqual(len(soup.select('.result-card')),2)
            self.assertIn('Töötlus',response.text)
            self.assertIn('Skoori põhjendus',response.text)
        self.assertIn('Fail: tekst.txt',uploaded.text)

    def test_bom_and_empty_browser_file_selection(self):
        response=self.client.post('/keywords',data={'limit':'1'},files={'file':('tekst.txt',b'\xef\xbb\xbf'+ 'Raamatukogud.'.encode('utf-8'))})
        self.assertEqual(response.status_code,200)
        response=self.client.post('/keywords',data={'text':'Raamatukogud.','limit':'1'},files={'file':('',b'','application/octet-stream')})
        self.assertEqual(response.status_code,200)

    def test_both_inputs_rejected(self):
        with patch.object(self.app.state.runtime,'keywords',side_effect=AssertionError('Ei tohi töödelda')):
            response=self.client.post('/keywords',data={'text':'Raamatukogud.','limit':'10'},files={'file':('a.txt',b'text')})
        self.assertEqual(response.status_code,400)
        self.assertIn('mitte mõlemad',response.text)

    def test_invalid_encoding_extension_empty_and_limit(self):
        for filename,body,message in [('a.txt',b'\xff\xfe','UTF-8'),('a.pdf',b'text','.txt'),('a.txt',b'  ','tühi')]:
            with self.subTest(filename=filename,body=body):
                response=self.client.post('/keywords',data={'limit':'10'},files={'file':(filename,body)})
                self.assertEqual(response.status_code,400)
                self.assertIn(message,response.text)
        for limit in ('0','51','x'):
            response=self.client.post('/keywords',data={'text':'Raamatukogud','limit':limit})
            self.assertEqual(response.status_code,400)
        self.assertEqual(self.client.post('/keywords',data={'text':' '}).status_code,400)

    def test_xss_escaped_in_textarea_and_snippets_and_query(self):
        payload='</textarea><script>alert(1)</script> Raamatukogud.'
        response=self.client.post('/keywords',data={'text':payload,'limit':'5'})
        self.assertEqual(response.status_code,200)
        soup=BeautifulSoup(response.text,'html.parser')
        self.assertIsNone(soup.find('script'))
        self.assertEqual(soup.find('textarea').text,payload)
        self.assertIn('&lt;script&gt;',response.text)
        self.assertTrue(soup.find('mark'))
        response=self.client.post('/search',data={'query':payload,'mode':'exact','limit':'1'})
        self.assertIsNone(BeautifulSoup(response.text,'html.parser').find('script'))

    def test_source_uri_cannot_be_javascript_link(self):
        response=self.client.post('/keywords',data={'text':'õun','limit':'1'})
        self.assertEqual(response.status_code,200)
        soup=BeautifulSoup(response.text,'html.parser')
        self.assertTrue(soup.select_one('.result-card'))
        self.assertFalse(soup.select('[href^="javascript:"]'))

    def test_privacy_headers_and_no_user_text_persisted(self):
        before={str(p.relative_to(self.data)):p.stat().st_size for p in self.data.rglob('*') if p.is_file()}
        with self.assertNoLogs('uvicorn.error',level='INFO'):
            response=self.client.post('/keywords',data={'text':'Raamatukogud. ErilineSalajaneTekstQWERTY','limit':'1'})
        self.assertEqual(response.headers['cache-control'],'no-store')
        self.assertIn("script-src 'none'",response.headers['content-security-policy'])
        self.assertEqual(response.headers['referrer-policy'],'no-referrer')
        after={str(p.relative_to(self.data)):p.stat().st_size for p in self.data.rglob('*') if p.is_file()}
        self.assertEqual(before,after)

    def test_concurrent_requests_serialized_and_do_not_mix_results(self):
        original=self.app.state.runtime.keywords
        active=0
        maximum=0
        threads=set()
        def wrapped(*args):
            nonlocal active,maximum
            active+=1
            maximum=max(maximum,active)
            threads.add(threading.get_ident())
            try:
                time.sleep(.03)
                return original(*args)
            finally:
                active-=1
        with patch.object(self.app.state.runtime,'keywords',side_effect=wrapped),ThreadPoolExecutor(max_workers=2) as callers:
            jobs=[callers.submit(self.client.post,'/keywords',data={'text':text,'limit':'1'}) for text in ('Raamatukogud.','Tehisintellekt.')]
            responses=[job.result() for job in jobs]
        self.assertEqual(maximum,1)
        self.assertEqual(len(threads),1)
        self.assertIn('EMS000001',responses[0].text)
        self.assertIn('EMS000002',responses[1].text)

    def test_uploads_stay_in_memory(self):
        with patch('tempfile.SpooledTemporaryFile.rollover',side_effect=AssertionError('Ei kirjuta kettale')):
            response=self.client.post('/keywords',data={'limit':'1'},files={'file':('a.txt',b'Raamatukogud.')})
        self.assertEqual(response.status_code,200)


class WebLifecycleTests(unittest.TestCase):
    def test_first_start_reuse_shutdown_lock_and_failed_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            xml=xmlfile(root/'small.xml',record('EMS000001','raamatukogud'))
            settings=Settings(root/'data',source_xml=xml)
            app=create_app(settings)
            with TestClient(app) as client:
                self.assertEqual(client.get('/health').status_code,200)
                self.assertEqual(app.state.startup,{'base_action':'prepared','index_action':'prepared'})
                self.assertTrue((settings.data_dir/'.ems.lock').exists())
            self.assertFalse((settings.data_dir/'.ems.lock').exists())
            with patch('ems.storage.acquire',side_effect=AssertionError('Ei hangi andmeid')),patch('ems.search_index.analyze_label',side_effect=AssertionError('Ei lemmatiseeri')):
                with TestClient(create_app(settings)) as client:
                    self.assertEqual(client.app.state.startup,{'base_action':'reused','index_action':'reused'})
            broken=root/'broken.xml'
            broken.write_text('<html/>')
            with self.assertRaises(EMSDataError),TestClient(create_app(Settings(root/'bad-data',source_xml=broken))):
                pass
            self.assertFalse((root/'bad-data'/'.ems.lock').exists())
            self.assertFalse((root/'bad-data'/'current.json').exists())

    def test_file_limit_and_streamed_body_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            xml=xmlfile(root/'small.xml',record('EMS000001','raamatukogud'))
            app=create_app(Settings(root/'data',32,source_xml=xml))
            with TestClient(app) as client:
                response=client.post('/keywords',data={'limit':'1'},files={'file':('a.txt',b'x'*33)})
                self.assertEqual(response.status_code,400)
                self.assertIn('ületab',response.text)
                response=client.post('/keywords',data={'text':'x'*33,'limit':'1'})
                self.assertEqual(response.status_code,400)
                response=client.post('/keywords',content=(b'x'*40000 for _ in range(2)),headers={'Content-Type':'application/octet-stream'})
                self.assertEqual(response.status_code,413)
                self.assertIn('liiga suur',response.text)


if __name__=='__main__':
    unittest.main()
