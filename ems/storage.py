"""Immutable generations and one atomic current.json pointer preserve the old DB."""
from contextlib import contextmanager
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import time
import uuid

import duckdb
import requests

from . import SCHEMA_VERSION, IMPORT_VERSION
from .importer import stage_source, derive
from .validation import validate, utcnow
from .xmlio import dumps, file_sha256

SOURCE_URL = 'https://ems.elnet.ee/temp/ems_marc_tais.xml'


class EMSDataError(RuntimeError):
    pass


def write_json(path, value):
    """Flush content before atomically publishing a small manifest/report."""
    path = Path(path)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('w', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def data_lock(directory):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / '.ems.lock'
    try:
        handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise EMSDataError(f'Andmekaust on kasutusel: {path}. Peata teine EMS-protsess. '
                           'Pärast krahhi eemalda lukk alles siis, kui ühtki EMS-protsessi ei tööta.') from exc
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            json.dump({'pid': os.getpid(), 'created_at_utc': utcnow()}, stream)
        yield directory
    finally:
        path.unlink(missing_ok=True)


def current(directory):
    directory = Path(directory).resolve()
    manifest_path = directory / 'current.json'
    if not manifest_path.exists():
        raise EMSDataError('Valmis andmebaas puudub. Käivita: python -m ems prepare')
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest['schema_version'] != SCHEMA_VERSION or manifest['import_version'] != IMPORT_VERSION:
            raise EMSDataError('Andmebaasi skeemi või importija versioon ei ühildu. Peata EMS-protsessid '
                               'ja käivita python -m ems refresh --xml <säilitatud-source.xml>. Vana versioon jääb alles.')
        generation = (directory / manifest['generation']).resolve()
        if generation.parent != directory / 'generations':
            raise EMSDataError('Vigane andmebaasi versioonitee manifestis.')
        for filename in ('ems.duckdb', 'source.xml', 'source.json', 'metadata.json', 'validation.json'):
            if not (generation / filename).is_file():
                raise EMSDataError(f'Andmebaasi versioon on poolik: {generation / filename}. Taasta varasem manifest või käivita refresh.')
        with duckdb.connect(str(generation / 'ems.duckdb'), read_only=True) as c:
            row = c.execute('SELECT schema_version,import_version,status,run_id FROM processing_run').fetchall()
            if row != [(SCHEMA_VERSION, IMPORT_VERSION, 'ready', manifest['run_id'])]:
                raise EMSDataError('Andmebaasi töötlusmetaandmed ei ühildu manifestiga. Taasta varasem manifest või käivita refresh.')
        return manifest, generation
    except (KeyError, ValueError, OSError, duckdb.Error) as exc:
        raise EMSDataError(f'Andmebaasi ei saa avada: {exc}. Taasta current.previous.json või käivita refresh.') from exc


@contextmanager
def database(directory='data'):
    """Use this context for CLI/future application readers and refresh exclusion."""
    with data_lock(directory) as root:
        manifest, generation = current(root)
        with duckdb.connect(str(generation / 'ems.duckdb'), read_only=True) as c:
            yield c, generation, manifest


def acquire(destination, xml=None, source_metadata=None, url=SOURCE_URL):
    temporary = destination.with_suffix('.xml.part')
    acquired = utcnow()
    download_seconds=None
    if xml:
        path = Path(xml).resolve()
        shutil.copyfile(path, temporary)
        meta = dict(source_url=None, downloaded_at_utc=None, acquired_at_utc=acquired,
                    acquisition='local_copy', original_path=str(path), http_metadata={})
        if source_metadata:
            evidence = json.loads(Path(source_metadata).read_text(encoding='utf-8'))
            if evidence['sha256'] != file_sha256(temporary):
                raise EMSDataError('Kohaliku XML-i kontrollsumma ei vasta allika metaandmetele.')
            meta.update(source_url=evidence.get('url'), downloaded_at_utc=evidence.get('downloaded_at'),
                        http_metadata=evidence.get('headers', {}))
    else:
        if source_metadata:
            raise EMSDataError('--source-meta sobib ainult koos --xml valikuga.')
        last_error = None
        download_started=time.perf_counter()
        for attempt in range(3):
            try:
                with requests.get(url, stream=True, timeout=(20, 180)) as response:
                    response.raise_for_status()
                    with temporary.open('wb') as stream:
                        for chunk in response.iter_content(1024 * 1024):
                            stream.write(chunk)
                        stream.flush()
                        os.fsync(stream.fileno())
                    meta = dict(source_url=url, downloaded_at_utc=utcnow(), acquired_at_utc=acquired,
                                acquisition='download', original_path=None, http_metadata=dict(response.headers))
                break
            except requests.RequestException as exc:
                last_error = exc
                temporary.unlink(missing_ok=True)
                if attempt < 2:
                    time.sleep(attempt + 1)
        else:
            raise EMSDataError(f'EMS-i allalaadimine ebaõnnestus pärast 3 katset: {last_error}')
        download_seconds=time.perf_counter()-download_started
    # Parse/check root BEFORE promoting the acquired file. Full parsing follows.
    from .xmlio import records
    iterator = records(temporary)
    try:
        next(iterator)
    finally:
        iterator.close()
    meta.update(sha256=file_sha256(temporary), byte_count=temporary.stat().st_size)
    meta['download_seconds']=download_seconds
    os.replace(temporary, destination)
    return meta


def prepare(directory='data', xml=None, source_metadata=None, refresh=False, url=SOURCE_URL):
    with data_lock(directory) as root:
        if not refresh and (root / 'current.json').exists():
            manifest, generation = current(root)
            return {'action': 'reused', 'database': str(generation / 'ems.duckdb'), 'manifest': manifest}
        started = utcnow()
        run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:12]
        generation = root / 'generations' / run_id
        generation.mkdir(parents=True)
        timings = {}
        temporary_db = generation / 'building.duckdb'
        try:
            begin = time.perf_counter()
            source = acquire(generation / 'source.xml', xml, source_metadata, url)
            timings['source_acquisition_seconds'] = time.perf_counter() - begin
            timings['download_seconds']=source.get('download_seconds')
            write_json(generation / 'source.json', source)
            env = {'python': platform.python_version(), 'platform': platform.platform(),
                   'packages': {name: importlib.metadata.version(name) for name in ('duckdb','requests','defusedxml')}}
            begin = time.perf_counter()
            with duckdb.connect(str(temporary_db)) as c:
                c.execute("SET memory_limit='512MB'")
                c.execute('SET threads=2')
                counts = stage_source(c, generation / 'source.xml', generation)
                timings['xml_import_seconds']=time.perf_counter()-begin
                derivation_started=time.perf_counter()
                derive(c)
                timings['semantic_derivation_seconds']=time.perf_counter()-derivation_started
                timings['xml_import_and_derivation_seconds'] = time.perf_counter() - begin
                c.execute('INSERT INTO source_snapshot VALUES (?,?,?,?,?,?,?,?,?)', [
                    run_id, source['source_url'], source['acquired_at_utc'], source['downloaded_at_utc'],
                    source['acquisition'], source['original_path'], source['sha256'], source['byte_count'], dumps(source['http_metadata'])])
                c.execute('INSERT INTO processing_run VALUES (?,?,?,?,?,?,?,?,?,?)', [
                    run_id, run_id, SCHEMA_VERSION, IMPORT_VERSION, started, None, 'validating', dumps(env), dumps(counts), '{}'])
                begin = time.perf_counter()
                report = validate(c, generation / 'source.xml', source, counts)
                timings['validation_seconds'] = time.perf_counter() - begin
                report.update(run_id=run_id, schema_version=SCHEMA_VERSION, import_version=IMPORT_VERSION,
                              environment=env, timings=timings)
                write_json(generation / 'validation.json', report)
                if not report['ok']:
                    raise EMSDataError(f'Andmete kontroll ebaõnnestus; vana baas jäi alles. Aruanne: {generation / "validation.json"}')
                completed = utcnow()
                c.execute("UPDATE processing_run SET status='ready',completed_at_utc=?,timings_json=?",
                          [completed, dumps(timings)])
                c.execute('CHECKPOINT')
            os.replace(temporary_db, generation / 'ems.duckdb')
            metadata = dict(run_id=run_id, schema_version=SCHEMA_VERSION, import_version=IMPORT_VERSION,
                            started_at_utc=started, completed_at_utc=completed, status='ready',
                            source=source, source_counts=counts, environment=env, timings=timings)
            write_json(generation / 'metadata.json', metadata)
            manifest = dict(run_id=run_id, generation='generations/' + run_id,
                            schema_version=SCHEMA_VERSION, import_version=IMPORT_VERSION,
                            source_sha256=source['sha256'], activated_at_utc=utcnow())
            if (root / 'current.json').exists():
                # The last known pointer is backed up only AFTER a successful build.
                old = json.loads((root / 'current.json').read_text(encoding='utf-8'))
                write_json(root / 'current.previous.json', old)
            write_json(root / 'current.json', manifest)
            return {'action': 'refreshed' if refresh else 'prepared', 'database': str(generation / 'ems.duckdb'),
                    'report': str(generation / 'validation.json'), 'manifest': manifest,
                    'concepts': report['concepts'], 'timings': timings}
        except Exception as exc:
            write_json(generation / 'failure.json', {'failed_at_utc': utcnow(), 'error': str(exc),
                       'run_id': run_id, 'activated': False})
            if isinstance(exc, EMSDataError):
                raise
            raise EMSDataError(f'Ettevalmistus nurjus: {exc}. Aktiivset baasi ei muudetud. Diagnostika: {generation}') from exc


def validate_current(directory='data'):
    with database(directory) as (c, generation, manifest):
        source = json.loads((generation / 'source.json').read_text(encoding='utf-8'))
        if manifest['source_sha256'] != source['sha256']:
            raise EMSDataError('Aktiivse manifesti ja allika metaandmete SHA-256 ei kattu.')
        counts = json.loads(c.execute('SELECT source_counts_json FROM processing_run').fetchone()[0])
        begin = time.perf_counter()
        report = validate(c, generation / 'source.xml', source, counts)
        report.update(run_id=manifest['run_id'], validation_seconds=time.perf_counter() - begin)
        # Original activation report stays immutable. This is the latest recheck.
        write_json(Path(directory) / 'last_validation.json', report)
        return report
