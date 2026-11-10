"""Development mention-level ablation; explicitly not an independent gold standard."""
import argparse
import json
from pathlib import Path

from ems.search import search_session
from ems.xmlio import file_sha256


def metrics(tp,fp,fn):
    return {'tp':tp,'fp':fp,'fn':fn,'precision':tp/(tp+fp) if tp+fp else None,
            'recall':tp/(tp+fn) if tp+fn else None,
            'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir',default='data')
    parser.add_argument('--cases',type=Path,default=Path('evaluation/cases.json'))
    parser.add_argument('--output',type=Path,default=Path('reports/etapp5_evaluation.json'))
    args=parser.parse_args()
    corpus=json.loads(args.cases.read_text(encoding='utf-8'))
    report={'provenance':corpus['provenance'],'scope':corpus['scope'],'cases_sha256':file_sha256(args.cases),
            'strategies':{},'case_count':len(corpus['cases'])}
    with search_session(args.data_dir) as engine:
        for strategy in ('surface','lemma','lemma-synonyms'):
            totals=[0,0,0]
            observations=[]
            for case in corpus['cases']:
                text=case['text']
                expected=set()
                for mention in case['mentions']:
                    start=text.index(mention['surface'])
                    expected.add((mention['ems_id'],start,start+len(mention['surface'])))
                response=engine.keywords(text,limit=50,strategy=strategy)
                actual={(r['ems_id'],e['start'],e['end']) for r in response['results'] for e in r['evidence']}
                assert all(text[e['start']:e['end']]==e['text'] for r in response['results'] for e in r['evidence'])
                tp,fp,fn=len(expected&actual),len(actual-expected),len(expected-actual)
                totals=[a+b for a,b in zip(totals,(tp,fp,fn))]
                observations.append({'id':case['id'],'metrics':metrics(tp,fp,fn),
                    'expected_mentions':sorted(expected),'predicted_mentions':sorted(actual),
                    'result_ids':[r['ems_id'] for r in response['results']]})
            report['strategies'][strategy]={'micro':metrics(*totals),'cases':observations}
        probe=corpus['topic_probe']
        report['topic_probe']={**probe,'predicted_direct_terms':[
            {'ems_id':r['ems_id'],'label':r['preferred_label'],'matched_text':r['matched_text']}
            for r in engine.keywords(probe['text'])['results']],
            'relevance_metrics':None}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v['micro'] for k,v in report['strategies'].items()},ensure_ascii=True,indent=2))


if __name__=='__main__':
    main()
