"""End-to-end POST latency on a running, already warm web server."""
import argparse
import json
from pathlib import Path
import re
import time

import requests

from examples.measurement import stats


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:8000')
    parser.add_argument('--runs',type=int,default=5)
    parser.add_argument('--output',type=Path,default=Path('reports/etapp5_http_benchmark.json'))
    args=parser.parse_args()
    if args.runs<2:
        parser.error('--runs must be at least 2')
    session=requests.Session()
    report={'url':args.url,'runs':args.runs,'scope':'HTTP POST to HTML response; server already running with warm analyzer; no concurrent load',
            'measurements':[]}
    for size in (100,1000,10000):
        path=Path(f'reports/etapp5_inputs/varied_{size}.txt')
        text=path.read_text(encoding='utf-8')
        observations=[]
        for _ in range(args.runs):
            started=time.perf_counter()
            response=session.post(args.url.rstrip('/')+'/keywords',data={'text':text,'limit':'10'},timeout=180)
            elapsed=time.perf_counter()-started
            response.raise_for_status()
            duration=re.search(r'Töötlus ([0-9.]+) s',response.text)
            assert duration and '<article class="result-card">' in response.text
            observations.append({'http_seconds':elapsed,'server_reported_seconds_rounded':float(duration.group(1)),
                                 'response_bytes':len(response.content)})
        item={'words_by_whitespace':size,'input_path':str(path),'observations':observations,
              'first_in_series':observations[0], 'all_runs':stats(x['http_seconds'] for x in observations),
              'repeats':stats(x['http_seconds'] for x in observations[1:])}
        report['measurements'].append(item)
        print(json.dumps({'words':size,'http':item['all_runs']},ensure_ascii=True),flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
