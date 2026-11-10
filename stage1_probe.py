"""Stage 1 only: inspect source XML without constructing an application/database."""
import collections as C
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

p = Path('ems_marc_tais.xml')
ns = '{http://www.loc.gov/MARC21/slim}'
counts, indicators, codes, statuses, patterns = (C.Counter() for _ in range(5))
ids, refs, examples, headings, redirects = [], [], {}, C.Counter(), []
wvalues, domains, repeats = C.Counter(), C.Counter(), C.Counter()
record_types = C.Counter()
missing = 0
for event, r in ET.iterparse(p, events=['end']):
    if r.tag != ns+'record':
        continue
    rid = r.findtext(ns+"controlfield[@tag='001']")
    ids.append(rid)
    leader = r.findtext(ns+'leader') or ''
    statuses[leader[5:6]] += 1
    fixed = r.findtext(ns+"controlfield[@tag='008']") or ''
    record_types[fixed[9:10]] += 1
    hs = []
    local_counts = C.Counter(f.get('tag') for f in r)
    repeats.update(k for k,v in local_counts.items() if k and v>1)
    for f in r:
        tag = f.get('tag', f.tag.removeprefix(ns))
        counts[tag] += 1
        if f.tag != ns+'datafield':
            continue
        indicators[f"{tag}|{f.get('ind1')}|{f.get('ind2')}"] += 1
        subs = [(s.get('code'), s.text or '') for s in f]
        for code,value in subs:
            if code == 'w':
                wvalues[value] += 1
            if tag == '072' and code == 'a':
                domains[value] += 1
        for code, value in subs:
            codes[tag+'$'+code] += 1
            if code == '0' and tag.startswith(('5','7')):
                refs.append((rid, tag, value))
        if tag.startswith('1'):
            hs.append(tag)
        key = tag+'|'+str(f.get('ind2'))
        examples.setdefault(key, {'id':rid, 'xml':ET.tostring(f,encoding='unicode')})
    headings['+'.join(hs) or 'NONE'] += 1
    if not hs:
        redirects.append({'id':rid,'xml':ET.tostring(r,encoding='unicode')})
    r.clear()
idset = set(ids)
out = dict(bytes=p.stat().st_size,sha256=hashlib.file_digest(p.open('rb'),'sha256').hexdigest(),
           records=len(ids),missing_ids=ids.count(None),duplicate_ids=[k for k,v in C.Counter(ids).items() if v>1],
           fields=dict(counts),indicators=dict(indicators),subfields=dict(codes),leader_status=dict(statuses),
           heading_patterns=dict(headings),references=len(refs),
           relation_w=dict(wvalues),domains=dict(domains),records_with_repeated_tag=dict(repeats),
           record_type_008_09=dict(record_types),
           unresolved=[x for x in refs if x[2].rsplit('/',1)[-1] not in idset],
           examples=examples,redirect_examples=redirects[:8])
Path('stage1_xml_findings.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k not in ['examples','redirect_examples','unresolved']},ensure_ascii=False,indent=2))
print('unresolved',len(out['unresolved']))
