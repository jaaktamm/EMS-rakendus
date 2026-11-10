"""Versioned derived index: base generations remain immutable and reusable."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import uuid

import duckdb

from .linguistics import analyze_label, signature
from .storage import EMSDataError, current, data_lock, prepare, write_json
from .xmlio import digest, dumps

INDEX_VERSION = 3
SEARCH_COLUMNS = {
    'label_id':'BIGINT', 'ems_id':'VARCHAR', 'original_text':'VARCHAR',
    'language':'VARCHAR', 'role':'VARCHAR', 'normalized':'VARCHAR', 'surface_key':'VARCHAR',
    'lemmas':'VARCHAR[]', 'lemma_key':'VARCHAR', 'lemma_options':'VARCHAR[][]',
    'pos_options':'VARCHAR[][]',
    'token_count':'INTEGER', 'analysis_warnings':'VARCHAR[]',
}


def attach(connection, path, name):
    # Only fixed internal aliases; SQL literal quoting also handles apostrophes in paths.
    connection.execute("ATTACH '" + str(Path(path).resolve()).replace("'", "''") + f"' AS {name} (READ_ONLY)")


def index_current(root, base, allow_missing=False):
    path = Path(root) / 'search_current.json'
    if not path.exists():
        if allow_missing:
            return None
        raise EMSDataError('Otsingubaas puudub. Käivita python -m ems prepare-search.')
    try:
        manifest = json.loads(path.read_text(encoding='utf-8'))
        if manifest['source_run_id'] != base['run_id']:
            if allow_missing:
                return None
            raise EMSDataError('Otsingubaas kuulub varasemale EMS-i versioonile. Käivita prepare-search.')
        if manifest['index_version'] != INDEX_VERSION or manifest['analyzer_fingerprint'] != digest(signature()):
            raise EMSDataError('Otsingubaasi töötlusversioon või keeleressursid erinevad. '
                               'Käivita python -m ems prepare-search --rebuild.')
        directory = (Path(root) / manifest['directory']).resolve()
        if directory.parent != Path(root).resolve() / 'search_indexes':
            raise EMSDataError('Vigane otsingubaasi tee.')
        with duckdb.connect(str(directory/'search.duckdb'),read_only=True) as c:
            metadata = json.loads(c.execute('SELECT metadata_json FROM search_metadata').fetchone()[0])
            for k in ('index_version','source_run_id','analyzer_fingerprint','index_id'):
                if metadata[k] != manifest[k]:
                    raise EMSDataError('Otsingubaasi metaandmed ei vasta manifestile.')
        return manifest, directory
    except (KeyError, OSError, ValueError, duckdb.Error, TypeError) as exc:
        raise EMSDataError(f'Otsingubaas pole loetav: {exc}. Käivita prepare-search --rebuild.') from exc


def ensure_index(directory='data', rebuild=False, progress=False):
    # First use may prepare the base; a ready base never contacts the network.
    prepare(directory)
    with data_lock(directory) as root:
        base, generation = current(root)
        if not rebuild:
            existing = index_current(root,base,allow_missing=True)
            if existing:
                return {'action':'reused','manifest':existing[0], 'database':str(existing[1]/'search.duckdb')}
        index_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:12]
        target = root/'search_indexes'/index_id
        target.mkdir(parents=True)
        started = time.perf_counter()
        timings={'et_label_analysis_seconds':0.,'other_label_tokenization_seconds':0.}
        staging = target/'labels.jsonl'
        try:
            with duckdb.connect(str(target/'building.duckdb')) as c:
                c.execute("SET memory_limit='512MB'")
                c.execute('SET threads=2')
                attach(c,generation/'ems.duckdb','core')
                cursor=c.execute('SELECT label_id,ems_id,text,language,role FROM core.label ORDER BY language,text,label_id')
                count=0
                staging_started=time.perf_counter()
                with staging.open('w',encoding='utf-8',newline='\n') as stream:
                    while batch:=cursor.fetchmany(512):
                        for label_id, ems_id, text, language, role in batch:
                            analysis_started=time.perf_counter()
                            values=analyze_label(text,language)
                            timing_key='et_label_analysis_seconds' if language=='et' else 'other_label_tokenization_seconds'
                            timings[timing_key]+=time.perf_counter()-analysis_started
                            row=dict(label_id=label_id,ems_id=ems_id,original_text=text,language=language,role=role,**values)
                            stream.write(dumps(row)+'\n')
                            count+=1
                            if progress and count % 2000 == 0:
                                print(f'Otsingunimetusi töödeldud: {count}',file=sys.stderr,flush=True)
                timings['staging_total_seconds']=time.perf_counter()-staging_started
                bulk_started=time.perf_counter()
                types='{'+','.join("'"+name+"':'"+kind+"'" for name,kind in SEARCH_COLUMNS.items())+'}'
                ddl=', '.join('"'+name+'" '+kind for name,kind in SEARCH_COLUMNS.items())
                c.execute(f'CREATE TABLE search_label ({ddl}, PRIMARY KEY(label_id))')
                c.execute(f"INSERT INTO search_label BY NAME SELECT * FROM read_json(?,format='newline_delimited',columns={types})",[str(staging)])
                timings['bulk_load_seconds']=time.perf_counter()-bulk_started
                validation_started=time.perf_counter()
                bad=c.execute('''SELECT count(*) FROM search_label WHERE token_count<1
                    OR (language='et' AND (lemmas IS NULL OR array_length(lemmas)!=token_count OR lemma_key IS NULL
                        OR pos_options IS NULL OR array_length(pos_options)!=token_count))
                    OR (language!='et' AND (lemmas IS NOT NULL OR lemma_key IS NOT NULL OR pos_options IS NOT NULL))''').fetchone()[0]
                base_count=c.execute('SELECT count(*) FROM core.label').fetchone()[0]
                if bad or base_count!=count:
                    raise EMSDataError(f'Otsingubaasi kontroll nurjus: vigaseid nimetusi {bad}, lähtearv {base_count}, töödeldud {count}.')
                stats=[dict(zip(['language','role','count'],row)) for row in c.execute('SELECT language,role,count(*) FROM search_label GROUP BY 1,2 ORDER BY 1,2').fetchall()]
                metadata=dict(index_id=index_id,index_version=INDEX_VERSION,source_run_id=base['run_id'],
                    source_sha256=base['source_sha256'], analyzer_fingerprint=digest(signature()),
                    analyzer=signature(),label_count=count,label_counts=stats,
                    warning_labels=c.execute('SELECT count(*) FROM search_label WHERE array_length(analysis_warnings)>0').fetchone()[0],
                    et_phrase_lengths=[r[0] for r in c.execute("SELECT DISTINCT token_count FROM search_label WHERE language='et' ORDER BY 1").fetchall()],
                    seconds=time.perf_counter()-started,created_at_utc=datetime.now(timezone.utc).isoformat())
                timings['index_validation_seconds']=time.perf_counter()-validation_started
                metadata['timings']=timings
                c.execute('CREATE TABLE search_metadata(metadata_json VARCHAR)')
                c.execute('INSERT INTO search_metadata VALUES (?)',[dumps(metadata)])
                c.execute('CHECKPOINT')
            (target/'building.duckdb').rename(target/'search.duckdb')
            staging.unlink()
            write_json(target/'metadata.json',metadata)
            manifest={k:metadata[k] for k in ('index_id','index_version','source_run_id','analyzer_fingerprint')}
            manifest['directory']='search_indexes/'+index_id
            # Previous index pointer is not touched until this build is complete.
            write_json(root/'search_current.json',manifest)
            return {'action':'prepared','database':str(target/'search.duckdb'),'manifest':manifest,'metadata':metadata}
        except Exception as exc:
            write_json(target/'failure.json',{'error':str(exc),'activated':False})
            if isinstance(exc,EMSDataError):
                raise
            raise EMSDataError(f'Otsingubaasi loomine nurjus: {exc}. Eelmine otsingubaas säilis. Diagnostika: {target}') from exc
