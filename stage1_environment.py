import importlib.metadata as M
import json
import platform
from pathlib import Path
import duckdb
from estnltk import Text
from fastapi import FastAPI, Form, UploadFile, File
from fastapi.testclient import TestClient
from jinja2 import Environment

t=Text('Õpilased lugesid raamatuid. Eesti raamatukogudes on vanad raamatud.')
t.tag_layer(['morph_analysis'])
app=FastAPI()
@app.post('/probe')
async def probe(text: str = Form(), file: UploadFile = File()):
    return {'text':text,'file':(await file.read()).decode('utf-8-sig')}
with TestClient(app) as client:
    r=client.post('/probe',data={'text':'õäöü'},files={'file':('test.txt','raamatud'.encode(),'text/plain')})
    assert r.status_code == 200, r.text
    assert r.json()=={'text':'õäöü','file':'raamatud'}
assert Environment(autoescape=True).from_string('{{ text }}').render(text='<script>')=='&lt;script&gt;'
c=duckdb.connect()
c.execute('create table probe(id varchar, lemmas varchar[])')
c.execute('insert into probe values (?, ?)', ['EMS000001',['vana','raamat']])
assert c.execute('select * from probe').fetchone()==('EMS000001',['vana','raamat'])
out={'versions':{n:M.version(n) for n in ['duckdb','estnltk','estnltk-core','fastapi','starlette','pydantic','uvicorn','jinja2','python-multipart','httpx','numpy','pandas','nltk']},
     'morphology':[{'text':w.text,'start':w.start,'end':w.end,'lemmas':list(w.lemma)} for w in t.morph_analysis],
     'multipart_test':'passed','html_escape_test':'passed','duckdb_list_test':'passed'}
out['platform']=platform.platform()
out['python']=platform.python_version()
Path('stage1_environment_'+platform.system().lower()+'.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=True,indent=2))
