import json
import time
import platform
from pathlib import Path
import duckdb

Path('.stage1-extensions').mkdir(exist_ok=True)
c = duckdb.connect(config={'extension_directory':str(Path('.stage1-extensions').resolve())})
c.execute('INSTALL webbed FROM community')
c.execute('LOAD webbed')
print(c.execute("select extension_name,extension_version from duckdb_extensions() where extension_name='webbed'").fetchall(),flush=True)
queries = [
    "DESCRIBE SELECT * FROM read_xml('ems_marc_tais.xml', record_element := 'record', all_varchar := true)",
    "SELECT count(*) FROM read_xml('ems_marc_tais.xml', record_element := 'record', all_varchar := true)",
    "SELECT * FROM read_xml('ems_marc_tais.xml', record_element := 'record', all_varchar := true) LIMIT 1",
    "DESCRIBE SELECT * FROM read_xml('ems_marc_tais.xml', record_element := 'record', all_varchar := true, streaming := false, maximum_file_size := 100000000)",
    "SELECT count(*) FROM read_xml('ems_marc_tais.xml', record_element := 'record', all_varchar := true, streaming := false, maximum_file_size := 100000000)",
    "SELECT * FROM read_xml('ems_marc_tais.xml', record_element := 'record', all_varchar := true, streaming := false, maximum_file_size := 100000000) LIMIT 1",
]
results=[]
for q in queries:
    t=time.perf_counter()
    try:
        rows=c.execute(q).fetchall()
        item=dict(sql=q,seconds=time.perf_counter()-t,rows=rows)
    except Exception as e:
        item=dict(sql=q,error=str(e))
    results.append(item)
    print(json.dumps(item,ensure_ascii=False,default=str),flush=True)
Path('stage1_webbed_'+platform.system().lower()+'.json').write_text(json.dumps(results,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
