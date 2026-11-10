import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
import requests
url='https://ems.elnet.ee/temp/ems_marc_tais.xml'
p=Path('stage1_download.xml.part')
with requests.get(url,stream=True,timeout=(20,180)) as r:
    r.raise_for_status()
    with p.open('wb') as f:
        for chunk in r.iter_content(1024*1024):
            f.write(chunk)
    meta={'url':url,'downloaded_at':datetime.now(timezone.utc).isoformat(),'headers':dict(r.headers),'bytes':p.stat().st_size,'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest()}
meta['matches_existing']=meta['sha256']==hashlib.file_digest(Path('ems_marc_tais.xml').open('rb'),'sha256').hexdigest()
p.rename('stage1_download.xml')
Path('stage1_source.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
print(json.dumps(meta,indent=2))
