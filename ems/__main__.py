import argparse
import json
import math
import platform
from pathlib import Path
import statistics
import sys
import time

import duckdb

from .storage import EMSDataError, database, prepare, validate_current, write_json


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='EMS-i kohalik import, otsing ja märksõnastamine.')
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('prepare', 'refresh', 'validate', 'status', 'measure','prepare-search','search','keywords'):
        p = sub.add_parser(command)
        p.add_argument('--data-dir', type=Path, default=Path('data'))
        if command in ('prepare','refresh'):
            p.add_argument('--xml', type=Path, help='Kohalik XML; puudumisel laadi ametlikust EMS-ist.')
            p.add_argument('--source-meta', type=Path, help='Etapi 1 allalaadimise JSON-metaandmed; kontrollsumma peab kattuma.')
        if command == 'measure':
            p.add_argument('--runs', type=int, default=5)
        if command == 'prepare-search':
            p.add_argument('--rebuild',action='store_true')
        if command == 'search':
            p.add_argument('query')
            p.add_argument('--mode',choices=('all','exact','lemma','prefix'),default='all')
            p.add_argument('--language',choices=('all','et','en'),default='all')
        if command == 'keywords':
            source=p.add_mutually_exclusive_group(required=True)
            source.add_argument('--text')
            source.add_argument('--file',type=Path)
            p.add_argument('--strategy',choices=('surface','lemma','lemma-synonyms'),default='lemma-synonyms')
            p.add_argument('--explain',action='store_true')
        if command in ('search','keywords'):
            p.add_argument('--limit',type=int,default=10)
    args = parser.parse_args(argv)
    try:
        if args.command in ('prepare','refresh'):
            result = prepare(args.data_dir, args.xml, args.source_meta, refresh=args.command=='refresh')
        elif args.command=='prepare-search':
            from .search_index import ensure_index
            result=ensure_index(args.data_dir,rebuild=args.rebuild,progress=True)
        elif args.command in ('search','keywords'):
            from .search import search_session,read_text_file,validate_text,check_limit
            check_limit(args.limit)
            if args.command=='keywords':
                text=read_text_file(args.file) if args.file else args.text
                validate_text(text)
            else:
                validate_text(args.query)
            started=time.perf_counter()
            with search_session(args.data_dir) as engine:
                startup=time.perf_counter()-started
                if args.command=='search':
                    result=engine.lookup(args.query,args.mode,args.language,args.limit)
                else:
                    result=engine.keywords(text,args.limit,args.strategy,args.explain)
                result['session_startup_seconds']=startup
        elif args.command == 'validate':
            report = validate_current(args.data_dir)
            result = {'ok': report['ok'], 'concepts': report['concepts'], 'errors': report['errors'],
                      'issues': report['issues'], 'raw_fidelity': report['raw_fidelity'],
                      'report': str(args.data_dir / 'last_validation.json'), 'seconds': report['validation_seconds']}
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if report['ok'] else 1
        elif args.command == 'status':
            with database(args.data_dir) as (c, generation, manifest):
                result = {'manifest': manifest, 'database': str(generation / 'ems.duckdb'),
                          'concepts': c.execute('SELECT count(*) FROM concept').fetchone()[0],
                          'labels': c.execute('SELECT count(*) FROM label').fetchone()[0]}
        else:
            if not 2 <= args.runs <= 100:
                raise EMSDataError('--runs peab olema 2 kuni 100.')
            times = []
            for _ in range(args.runs):
                begin = time.perf_counter()
                with database(args.data_dir) as (c, generation, manifest):
                    c.execute('SELECT language,role,count(*) FROM label GROUP BY 1,2').fetchall()
                times.append(time.perf_counter() - begin)
            result = {'measurement': 'DB avamine + nimetuste rühmitus; ei mõõda tekstiotsingut',
                      'runs': args.runs, 'seconds': times, 'first_seconds': times[0],
                      'median_seconds': statistics.median(times),
                      'p95_seconds': sorted(times)[math.ceil(len(times)*.95)-1],
                      'repeat_median_seconds': statistics.median(times[1:]),
                      'python': platform.python_version(), 'platform': platform.platform()}
            write_json(args.data_dir / 'measurement.json', result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (EMSDataError, OSError, ValueError, duckdb.Error) as exc:
        print(f'Viga: {exc}', file=sys.stderr)
        return 1
    except ImportError as exc:
        print(f'Viga: otsingu sõltuvus puudub ({exc}). Paigalda requirements-search.txt paketid.',file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
