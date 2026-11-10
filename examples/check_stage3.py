"""Reproducible CLI examples; saves only these repository-owned example texts."""
import json
from pathlib import Path
import subprocess
import sys


def main():
    root=Path(__file__).resolve().parents[1]
    reports=[]
    commands=[['keywords','--file',str(root/'examples'/name),'--limit','5'] for name in
              ('library.txt','morphology.txt','synonyms.txt','boundary.txt','unknown.txt')]
    commands += [['search','raamatukogudes','--mode','lemma','--limit','3'],
                 ['search','libraries','--language','en','--mode','exact','--limit','3'],
                 ['search','raamatu','--mode','prefix','--limit','3']]
    for arguments in commands:
        result=subprocess.run([sys.executable,'-m','ems',*arguments],cwd=root,
                              capture_output=True,text=True,encoding='utf-8',check=True)
        body=json.loads(result.stdout)
        reports.append({'arguments':arguments,'response':body})
        print(json.dumps({'command':arguments[:2], 'top':[
            {'ems_id':r['ems_id'],'label':r['preferred_label'],'type':r['match_type'],
             'score':r.get('score'),'frequency':r.get('frequency')}
            for r in body['results']]},ensure_ascii=True),flush=True)
    (root/'reports').mkdir(exist_ok=True)
    (root/'reports'/'etapp3_examples.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
