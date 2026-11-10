"""Final reproducible measurements: fresh-process first queries and warm repeats."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess
import sys
import time

from examples.measurement import environment,peak_rss_bytes,stats


def query_worker(args):
    from ems.search import search_session
    text=args.input.read_text(encoding='utf-8')
    began=time.perf_counter()
    with search_session(args.data_dir) as engine:
        startup=time.perf_counter()-began
        index_manifest=engine.manifest
        observations=[]
        for i in range(args.runs):
            result=engine.keywords(text)
            observations.append({'timings':result['timings'],'diagnostics':result['diagnostics'],
                                 'result_ids':[r['ems_id'] for r in result['results']]})
        assert all(x['result_ids']==observations[0]['result_ids'] for x in observations)
        planned=engine.keywords(text,explain=True)
    payload={'session_startup_seconds':startup,'environment':environment(),'index_manifest':index_manifest,
             'input_sha256':hashlib.sha256(text.encode('utf-8')).hexdigest(),
             'words_by_whitespace':len(text.split()),'unique_surface_words':len(set(text.casefold().split())),
             'utf8_bytes':len(text.encode('utf-8')),'observations':observations,
             'first':observations[0],
             'all_runs_summary':{k:stats(x['timings'][k] for x in observations) for k in observations[0]['timings']},
             'repeats_summary':{k:stats(x['timings'][k] for x in observations[1:]) for k in observations[0]['timings']},
             'peak_rss_bytes':peak_rss_bytes(),'query_plan':planned['query_plan']}
    print(json.dumps(payload,ensure_ascii=True),flush=True)


def startup_worker(args):
    import threading
    import urllib.request
    import uvicorn
    from ems.web import create_app,Settings
    started=time.perf_counter()
    app=create_app(Settings(Path(args.data_dir)))
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=0,workers=1,access_log=False,log_level='warning'))
    thread=threading.Thread(target=server.run)
    thread.start()
    try:
        while not server.started:
            if not thread.is_alive() or time.perf_counter()-started>90:
                raise RuntimeError('Uvicorn ei jõudnud valmisolekuni.')
            time.sleep(.01)
        port=server.servers[0].sockets[0].getsockname()[1]
        health=json.loads(urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=5).read())
        assert health=={'status':'ready'}
        print(json.dumps({'uvicorn_to_ready_seconds':time.perf_counter()-started,'actions':app.state.startup,
                          'health':health,'peak_rss_bytes':peak_rss_bytes()}),flush=True)
    finally:
        server.should_exit=True
        thread.join(timeout=60)


def inputs(data_dir,output_dir):
    from ems.storage import database
    from ems.xmlio import file_sha256
    output_dir.mkdir(parents=True,exist_ok=True)
    with database(data_dir) as (c,_,manifest):
        terms=[r[0] for r in c.execute("SELECT text FROM label WHERE role='preferred' AND language='et' ORDER BY label_id").fetchall()]
    terms=[t for t in terms if re.fullmatch(r'[a-zõäöüšž]+(?: [a-zõäöüšž]+){0,2}',t)]
    random.Random(20261029).shuffle(terms)
    varied=[]
    for a,b in zip(terms[::2],terms[1::2]):
        varied.extend(f'Uurijad käsitlevad teemat „{a}” ning võrdlevad tulemusi valdkonnaga „{b}”.'.split())
        if len(varied)>11000:
            break
    repeated='Eesti raamatukogudes kasutatakse tehisintellekti ja masinõppe meetodeid. Raamatukogud säilitavad vanu raamatuid.'.split()
    cases=[]
    for kind,pool in [('repeated',repeated),('varied',varied)]:
        for size in (100,1000,10000):
            text=' '.join((pool*(size//len(pool)+1))[:size])
            path=output_dir/f'{kind}_{size}.txt'
            path.write_text(text,encoding='utf-8')
            cases.append({'corpus':kind,'words':size,'path':str(path),'sha256':file_sha256(path)})
    return cases,manifest


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir',default='data')
    parser.add_argument('--runs',type=int,default=5,help='includes one first query and runs-1 warm repeats')
    parser.add_argument('--output',type=Path,default=Path('reports/etapp5_benchmark.json'))
    parser.add_argument('--worker',choices=('query','startup'))
    parser.add_argument('--input',type=Path)
    args=parser.parse_args()
    if args.runs<2:
        parser.error('--runs must be at least 2')
    if args.worker=='query':
        query_worker(args)
        return
    if args.worker=='startup':
        startup_worker(args)
        return
    report={'environment':environment(),'runs_per_case':args.runs,'measurements':[],
            'corpus_notes':{'repeated':'Repeated fixed sentences; highly deduplicated optimistic case.',
                            'varied':'Deterministic synthetic sentences containing shuffled EMS preferred terms; high dictionary-match density, not natural prose.'}}
    report['source_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path('ems').glob('*.py'))}
    cases,manifest=inputs(args.data_dir,Path('reports/etapp5_inputs'))
    report['base_manifest']=manifest
    # Each case is an independent Python process. No other benchmark is run concurrently.
    for case in cases:
        completed=subprocess.run([sys.executable,'-m','examples.benchmark_stage5','--worker','query',
            '--input',case['path'],'--data-dir',str(args.data_dir),'--runs',str(args.runs)],
            text=True,capture_output=True,encoding='utf-8',check=True)
        item={**case,**json.loads(completed.stdout)}
        report['measurements'].append(item)
        print(json.dumps({'case':case['corpus'],'words':case['words'],'first_seconds':item['first']['timings']['total_seconds'],
                          'repeats':item['repeats_summary']['total_seconds']},ensure_ascii=True),flush=True)
    startups=[]
    for _ in range(args.runs):
        started=time.perf_counter()
        process=subprocess.Popen([sys.executable,'-m','examples.benchmark_stage5','--worker','startup',
            '--data-dir',str(args.data_dir)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
        line=process.stdout.readline()
        ready_seconds=time.perf_counter()-started
        rest,error=process.communicate(timeout=60)
        if process.returncode:
            raise RuntimeError(error)
        item=json.loads(line)
        assert item['actions']=={'base_action':'reused','index_action':'reused'}
        item['process_to_ready_seconds']=ready_seconds
        startups.append(item)
    report['application_startup']={'observations':startups,'scope':'fresh Python process to real Uvicorn /health HTTP 200, with ephemeral loopback TCP port and graceful shutdown',
        'process_summary':stats(x['process_to_ready_seconds'] for x in startups),
        'uvicorn_summary':stats(x['uvicorn_to_ready_seconds'] for x in startups)}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
