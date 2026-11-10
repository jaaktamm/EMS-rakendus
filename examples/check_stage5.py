"""Save fresh full test results and dependency check as reproducible artifacts."""
import argparse
from datetime import datetime,timezone
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import unittest


def identities(suite):
    for test in suite:
        if isinstance(test,unittest.TestSuite):
            yield from identities(test)
        else:
            yield test.id()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('reports/etapp5_tests_windows.json'))
    args=parser.parse_args()
    suite=unittest.defaultTestLoader.discover('tests')
    test_ids=list(identities(suite))
    stream=io.StringIO()
    started=time.perf_counter()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    seconds=time.perf_counter()-started
    deps=subprocess.run([sys.executable,'-m','pip','check'],text=True,capture_output=True,encoding='utf-8')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    log=args.output.with_suffix('.log')
    log.write_text(stream.getvalue(),encoding='utf-8')
    report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),
            'platform':platform.platform(),'count':result.testsRun,'successful':result.wasSuccessful(),
            'failures':[t.id() for t,_ in result.failures],'errors':[t.id() for t,_ in result.errors],
            'skipped':[t.id() for t,_ in result.skipped],'seconds':seconds,'test_ids':test_ids,
            'dependency_check':{'exit_code':deps.returncode,'output':deps.stdout.strip(),'stderr':deps.stderr.strip()},
            'log':str(log)}
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('count','successful','seconds','dependency_check')},ensure_ascii=True),flush=True)
    raise SystemExit(0 if result.wasSuccessful() and deps.returncode==0 else 1)


if __name__=='__main__':
    main()
