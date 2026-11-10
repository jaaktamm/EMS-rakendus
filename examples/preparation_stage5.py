"""One explicitly fresh full preparation; never replaces the application's data."""
import argparse
import json
from pathlib import Path
import time

from ems.search_index import ensure_index
from ems.storage import prepare,validate_current,write_json
from examples.measurement import environment,peak_rss_bytes


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('reports/etapp5_preparation.json'))
    args=parser.parse_args()
    if (args.data_dir/'current.json').exists():
        parser.error('Mõõtmine nõuab uut andmekausta; olemasolevaid andmeid ei asendata.')
    result={'environment':environment(),'runs':1,'scope':'fresh download, import and linguistic index; no preparation percentiles claimed from one run'}
    began=time.perf_counter()
    base=prepare(args.data_dir)
    print('Alusbaas valmis.',flush=True)
    index=ensure_index(args.data_dir,progress=True)
    result['total_preparation_seconds']=time.perf_counter()-began
    meta=json.loads((Path(base['database']).parent/'metadata.json').read_text(encoding='utf-8'))
    result.update(base_metadata=meta,index_metadata=index['metadata'],peak_rss_bytes=peak_rss_bytes())
    report=validate_current(args.data_dir)
    result['independent_revalidation']={'ok':report['ok'],'concepts':report['concepts'],
        'raw_fidelity':report['raw_fidelity'],'unresolved_relations':report['unresolved_relation_count'],
        'seconds':report['validation_seconds']}
    if not report['ok']:
        raise RuntimeError('Täisimpordi sõltumatu kontroll ebaõnnestus.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    write_json(args.output,result)
    print(json.dumps({'report':str(args.output),'timings':meta['timings'],
                      'index_timings':index['metadata']['timings'],'total':result['total_preparation_seconds']},ensure_ascii=True),flush=True)


if __name__=='__main__':
    main()
