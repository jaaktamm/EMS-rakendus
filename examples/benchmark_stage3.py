"""Synthetic repeatable search timing, not an independent keyword gold standard."""
import argparse
import json
import math
from pathlib import Path
import platform
import statistics
import time

from ems.search import search_session


def stats(values):
    return {'median':statistics.median(values),'p95':sorted(values)[math.ceil(len(values)*.95)-1]}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runs',type=int,default=5)
    parser.add_argument('--data-dir',default='data')
    args=parser.parse_args()
    if not 2<=args.runs<=100:
        parser.error('--runs must be between 2 and 100')
    output={'python':platform.python_version(),'platform':platform.platform(),'runs':args.runs,
            'description':'Synthetic repeated sentences, warm OS cache; no relevance accuracy claim.', 'measurements':[]}
    phrase='Eesti raamatukogudes kasutatakse tehisintellekti ja masinõppe meetodeid. Raamatukogud säilitavad vanu raamatuid.'.split()
    started=time.perf_counter()
    with search_session(args.data_dir) as engine:
        output['session_startup_seconds']=time.perf_counter()-started
        for size in (100,1000,10000):
            text=' '.join((phrase*(size//len(phrase)+1))[:size])
            measurements=[]
            for _ in range(args.runs):
                result=engine.keywords(text)
                measurements.append({'timings':result['timings'],'diagnostics':result['diagnostics']})
            item={'words_by_whitespace':size,'first':measurements[0], 'all_runs':measurements,
                  'summary':{k:stats([m['timings'][k] for m in measurements]) for k in measurements[0]['timings']},
                  'repeats_only':stats([m['timings']['total_seconds'] for m in measurements[1:]])}
            output['measurements'].append(item)
            print(json.dumps({'words':size,'total':item['summary']['total_seconds'],
                              'sql_calls':measurements[-1]['diagnostics']['sql_calls']},ensure_ascii=True),flush=True)
        planned=engine.keywords('Raamatukogudes kasutatakse tehisintellekti.',explain=True)
        output['query_plan']=planned['query_plan']
        output['plan_diagnostics']=planned['diagnostics']
        text=(Path('examples')/'library.txt').read_text(encoding='utf-8')
        output['strategy_comparison']={strategy:[
            {'ems_id':x['ems_id'],'preferred_label':x['preferred_label'],'match_type':x['match_type'],
             'matched_label':x['matched_label'],'score':x['score']}
            for x in engine.keywords(text,strategy=strategy)['results']]
            for strategy in ('surface','lemma','lemma-synonyms')}
    path=Path('reports')/'etapp3_benchmark.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
