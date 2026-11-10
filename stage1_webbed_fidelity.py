import json
from pathlib import Path
import xml.etree.ElementTree as ET
import duckdb
ns='{http://www.loc.gov/MARC21/slim}'
first=next(r for _,r in ET.iterparse('ems_marc_tais.xml',events=['end']) if r.tag==ns+'record')
c=duckdb.connect(config={'extension_directory':str(Path('.stage1-extensions').resolve())})
c.execute('load webbed')
row=c.execute("select * from read_xml('ems_marc_tais.xml', record_element := 'record', all_varchar := true, streaming := false, maximum_file_size := 100000000) limit 1").fetchone()
raw=first.findtext(ns+"controlfield[@tag='008']")
parsed=next(f['#text'] for f in row[1] if f['tag']=='008')
out={'xml_008':raw,'webbed_008':parsed,'xml_008_length':len(raw),'webbed_008_length':len(parsed),
     'exact_equal':raw==parsed,'source_field_order':[f.get('tag', 'leader') for f in first],
     'webbed_columns':[d[0] for d in c.description],
     'extension':c.execute("select extension_version from duckdb_extensions() where extension_name='webbed'").fetchone()[0]}
Path('stage1_webbed_fidelity.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
