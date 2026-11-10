"""HTTP smoke check against the running app, using repository example text only."""
import argparse
import json
from pathlib import Path
import requests


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:8000')
parser.add_argument('--max-input-bytes',type=int,default=5242880)
    parser.add_argument('--output',type=Path,default=Path('reports/etapp4_http_checks.json'))
    args=parser.parse_args()
    base=args.url.rstrip('/')
    checks=[]
    session=requests.Session()
    def check(name,response,status,required=()):
        assert response.status_code==status,(name,response.status_code,response.text[:200])
        for value in required:
            assert value in response.text,(name,value)
        assert response.headers.get('Cache-Control')=='no-store'
        checks.append({'name':name,'status':response.status_code,'ok':True})
    check('health',session.get(base+'/health',timeout=15),200,['ready'])
    check('search_form',session.get(base+'/search',timeout=15),200,['Otsi EMS-ist','lang="et"'])
    check('keywords_form',session.get(base+'/keywords',timeout=15),200,['Leia tekstist märksõnad'])
    check('lemma_lookup',session.post(base+'/search',data={'query':'raamatukogudes','mode':'lemma','language':'et','limit':'3'},timeout=60),200,['EMS003867','Lemmafraas'])
    text=Path('examples/library.txt').read_text(encoding='utf-8')
    check('textarea',session.post(base+'/keywords',data={'text':text,'limit':'5'},timeout=60),200,['EMS003867','<mark>','Skoori põhjendus'])
    check('utf8_bom_upload',session.post(base+'/keywords',data={'limit':'5'},files={'file':('näide.txt',b'\xef\xbb\xbf'+text.encode('utf-8'),'text/plain')},timeout=60),200,['EMS003867','Fail: näide.txt'])
    check('both_inputs',session.post(base+'/keywords',data={'text':'Raamatukogud.','limit':'1'},files={'file':('a.txt',b'text')},timeout=15),400,['mitte mõlemad'])
    check('bad_encoding',session.post(base+'/keywords',data={'limit':'1'},files={'file':('a.txt',b'\xff\xfe')},timeout=15),400,['UTF-8'])
    check('empty_text',session.post(base+'/keywords',data={'text':' ','limit':'1'},timeout=15),400,['tühi'])
    check('wrong_extension',session.post(base+'/keywords',files={'file':('a.pdf',b'text')},timeout=15),400,['.txt'])
    check('oversized_file',session.post(base+'/keywords',files={'file':('a.txt',b'x'*(args.max_input_bytes+1))},timeout=15),400,['ületab'])
    response=session.post(base+'/keywords',data={'text':'</textarea><script>window.alert(1)</script> Raamatukogud.','limit':'1'},timeout=60)
    check('escaped_html',response,200,['&lt;script&gt;','EMS003867'])
    assert '<script>' not in response.text
    assert "script-src 'none'" in response.headers['Content-Security-Policy']
    fresh=session.get(base+'/keywords',timeout=15)
    check('fresh_form_has_no_previous_text',fresh,200)
    assert 'window.alert' not in fresh.text
    output={'url':base,'checks':checks,'all_ok':True}
    path=args.output
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(output,ensure_ascii=True,indent=2))


if __name__=='__main__':
    main()
