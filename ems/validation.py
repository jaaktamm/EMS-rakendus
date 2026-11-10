"""Source-to-database checks, including exact ordered raw MARC reconstruction."""
from collections import Counter
from datetime import datetime, timezone
import json
from xml.etree.ElementTree import ParseError

from defusedxml.common import DefusedXmlException

from .xmlio import digest, records, file_sha256


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def rows(connection, sql, parameters=None):
    cursor = connection.execute(sql) if parameters is None else connection.execute(sql, parameters)
    names = [item[0] for item in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def reconstructed(connection):
    """One ordered scan, bounded Python memory; no SQL query per word/record."""
    cursor = connection.execute('''
        SELECT r.record_pk, r.raw_sha256, r.attributes_json,
               f.field_id, f.kind, f.tag, f.ind1, f.ind2, f.value, f.attributes_json,
               s.subfield_pos, s.code, s.value, s.attributes_json
        FROM marc_record r LEFT JOIN marc_field f USING(record_pk)
        LEFT JOIN marc_subfield s USING(field_id)
        ORDER BY r.record_pk, f.field_pos, s.subfield_pos
    ''')
    current_pk, field_id, record, expected = None, None, None, None
    while batch := cursor.fetchmany(4096):
        for row in batch:
            pk, wanted, attrs, fid, kind, tag, ind1, ind2, value, fattrs, spos, code, text, sattrs = row
            if pk != current_pk:
                if record is not None:
                    yield current_pk, expected, record
                current_pk, expected, field_id = pk, wanted, None
                record = {'attributes': json.loads(attrs), 'fields': []}
            if fid is not None and fid != field_id:
                field_id = fid
                record['fields'].append(dict(kind=kind, tag=tag, ind1=ind1, ind2=ind2,
                    value=value, attributes=json.loads(fattrs), subfields=[]))
            if spos is not None:
                record['fields'][-1]['subfields'].append(dict(code=code, value=text, attributes=json.loads(sattrs)))
    if record is not None:
        yield current_pk, expected, record


def cycle_example(edges):
    graph = {}
    for source, target in edges:
        graph.setdefault(source, set()).add(target)
    visited, active = set(), set()
    for start in sorted(graph):
        if start in visited:
            continue
        path = [start]
        active.add(start)
        stack = [iter(sorted(graph.get(start, ())))]
        while stack:
            node = next(stack[-1], None)
            if node is None:
                visited.add(path[-1])
                active.remove(path.pop())
                stack.pop()
            elif node in active:
                return path[path.index(node):] + [node]
            elif node not in visited:
                path.append(node)
                active.add(node)
                stack.append(iter(sorted(graph.get(node, ()))))
    return []


def validate(connection, xml_path, source_meta, source_counts):
    errors = []
    actual_sha = file_sha256(xml_path)
    if actual_sha != source_meta['sha256']:
        errors.append('Säilitatud XML-i SHA-256 erineb imporditud allika kontrollsummast.')
    stored = connection.execute('SELECT sha256,byte_count FROM source_snapshot').fetchall()
    if stored != [(source_meta['sha256'], source_meta['byte_count'])]:
        errors.append('Allika JSON-metaandmed erinevad andmebaasi päritolutabelist.')
    actual = {
        'records': connection.execute('SELECT count(*) FROM marc_record').fetchone()[0],
        'fields': dict(connection.execute("SELECT coalesce(tag,kind),count(*) FROM marc_field GROUP BY 1").fetchall()),
        'subfields': dict(connection.execute('''SELECT f.tag || '$' || s.code,count(*)
            FROM marc_subfield s JOIN marc_field f USING(field_id) GROUP BY 1''').fetchall()),
        'indicators': dict(connection.execute("""SELECT tag || '|' || ind1 || '|' || ind2,count(*)
            FROM marc_field WHERE kind='datafield' GROUP BY 1""").fetchall()),
        'leader_status': dict(connection.execute("SELECT coalesce(record_status,''),count(*) FROM marc_record GROUP BY 1").fetchall()),
        'record_type': dict(connection.execute("SELECT coalesce(record_type,''),count(*) FROM marc_record GROUP BY 1").fetchall()),
    }
    for key, expected in source_counts.items():
        if expected != actual[key]:
            errors.append(f'Algfaili ja andmebaasi loendused erinevad: {key}.')
    total = actual['records']
    sample_ids = set(range(1, min(total, 5) + 1)) | {max(1, total // 2), total}
    sample_ids.update(row[0] for row in connection.execute('SELECT min(record_pk) FROM concept GROUP BY concept_type').fetchall())
    sample_ids.update(row[0] for row in connection.execute("""SELECT min(record_pk) FROM marc_field
        WHERE tag IN ('680','670','448','455') GROUP BY tag""").fetchall())
    for sql in (
        'SELECT min(record_pk) FROM marc_record WHERE length(ems_id_raw)>9',
        "SELECT min(f.record_pk) FROM marc_field f JOIN marc_subfield s USING(field_id) WHERE f.tag='680' AND trim(s.value)=''",
        "SELECT min(record_pk) FROM (SELECT record_pk FROM marc_field WHERE tag='450' GROUP BY 1 HAVING count(*)>1)",
    ):
        pk = connection.execute(sql).fetchone()[0]
        if pk is not None:
            sample_ids.add(pk)
    samples, mismatches, reconstructed_count = {}, [], 0
    for pk, expected, record in reconstructed(connection):
        reconstructed_count += 1
        if digest(record) != expected:
            if len(mismatches) < 100:
                mismatches.append(pk)
        if pk in sample_ids:
            samples[pk] = record
    if mismatches or reconstructed_count != total:
        errors.append('Toorväljade rekonstruktsioon erineb impordi sõrmejäljest või kirjete arvust.')
    sample_checks = []
    source_records = 0
    # Independent second parse checks selected real records and source count.
    try:
        for pk, record in records(xml_path):
            source_records += 1
            if pk in sample_ids:
                equal = samples.get(pk) == record
                sample_checks.append({'record_pk': pk, 'equal': equal, 'sha256': digest(record),
                                      'field_count': len(record['fields'])})
                if not equal:
                    errors.append(f'XML-valimkirje {pk} erineb baasi väljadest.')
    except (ParseError, DefusedXmlException, ValueError) as exc:
        errors.append(f'Säilitatud XML-i parsimine ebaõnnestus: {exc}')
    if source_records != total:
        errors.append('Sõltumatul ülelugemisel erineb XML-i ja andmebaasi kirjete arv.')
    issues = rows(connection, 'SELECT severity,code,count(*) AS count FROM validation_issue GROUP BY 1,2 ORDER BY 1,2')
    if any(item['severity'] == 'error' for item in issues):
        errors.append('Impordi kontrolltabelis esineb aktiveerimist takistavaid vigu.')
    duplicate_ids = rows(connection, '''SELECT ems_id_raw,count(*) AS count FROM marc_record
        GROUP BY 1 HAVING count(*)>1 ORDER BY 1''')
    missing_ids = connection.execute("SELECT count(*) FROM marc_record WHERE ems_id_raw IS NULL OR ems_id_raw=''").fetchone()[0]
    orphan_sql = {
        'fields_without_record': 'SELECT count(*) FROM marc_field f ANTI JOIN marc_record r USING(record_pk)',
        'subfields_without_field': 'SELECT count(*) FROM marc_subfield s ANTI JOIN marc_field f USING(field_id)',
        'missing_preferred_label': '''SELECT count(*) FROM concept c LEFT JOIN label l
            ON c.preferred_label_id=l.label_id AND c.ems_id=l.ems_id AND l.role='preferred' WHERE l.label_id IS NULL''',
    }
    integrity = {key: connection.execute(sql).fetchone()[0] for key, sql in orphan_sql.items()}
    if any(integrity.values()):
        errors.append('Tabelite tervikluskontroll ebaõnnestus.')
    unresolved_count = connection.execute("SELECT count(*) FROM relation WHERE target_id IS NULL").fetchone()[0]
    missing_reverse = rows(connection, '''SELECT r.ems_id, r.kind, r.target_id FROM relation r
        WHERE r.kind IN ('broad','narrow') AND r.target_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM relation back WHERE back.ems_id=r.target_id AND back.target_id=r.ems_id
                AND back.kind=CASE r.kind WHEN 'broad' THEN 'narrow' ELSE 'broad' END)
        ORDER BY 1,2,3''')
    edges = connection.execute("SELECT DISTINCT ems_id,target_id FROM relation WHERE kind='broad' AND target_id IS NOT NULL").fetchall()
    cycle = cycle_example(edges)
    return {
        'validated_at_utc': utcnow(), 'ok': not errors, 'errors': errors,
        'source_sha256': actual_sha, 'source_counts': source_counts, 'imported_counts': actual,
        'concepts': connection.execute('SELECT count(*) FROM concept').fetchone()[0],
        'labels': rows(connection, 'SELECT language,role,count(*) AS count FROM label GROUP BY 1,2 ORDER BY 1,2'),
        'concept_types': rows(connection, 'SELECT concept_type,count(*) AS count FROM concept GROUP BY 1 ORDER BY 1'),
        'relations': rows(connection, 'SELECT kind,resolution,count(*) AS count FROM relation GROUP BY 1,2 ORDER BY 1,2'),
        'relation_resolution_methods': rows(connection, 'SELECT resolution_method,count(*) AS count FROM relation GROUP BY 1 ORDER BY 1'),
        'shared_uri_count': connection.execute('SELECT count(*) FROM (SELECT uri FROM concept GROUP BY 1 HAVING count(*)>1)').fetchone()[0],
        'shared_uri_examples': rows(connection, 'SELECT uri,list(ems_id ORDER BY ems_id) AS record_ids FROM concept GROUP BY 1 HAVING count(*)>1 ORDER BY 1 LIMIT 20'),
        'domains': connection.execute('SELECT count(*) FROM domain').fetchone()[0],
        'domain_memberships': connection.execute('SELECT count(*) FROM concept_domain').fetchone()[0],
        'notes': rows(connection, 'SELECT kind,count(*) AS count FROM concept_note GROUP BY 1 ORDER BY 1'),
        'missing_ids': missing_ids, 'duplicate_ids': duplicate_ids,
        'id_lengths': rows(connection, 'SELECT length(ems_id_raw) AS length,count(*) AS count FROM marc_record GROUP BY 1 ORDER BY 1'),
        'unresolved_relation_count': unresolved_count,
        'unresolved_relation_examples': rows(connection, "SELECT * FROM relation WHERE target_id IS NULL ORDER BY relation_id LIMIT 100"),
        'redirects': rows(connection, 'SELECT * FROM redirect ORDER BY record_pk LIMIT 100'),
        'unresolved_redirect_count': connection.execute('SELECT count(*) FROM redirect WHERE target_id IS NULL').fetchone()[0],
        'excluded_records': rows(connection, '''SELECT r.record_pk,r.ems_id_raw,r.record_status,r.record_type,
            list(DISTINCT v.code ORDER BY v.code) AS reasons FROM marc_record r
            LEFT JOIN validation_issue v USING(record_pk)
            WHERE NOT EXISTS(SELECT 1 FROM concept c WHERE c.record_pk=r.record_pk)
            GROUP BY 1,2,3,4 ORDER BY 1'''),
        'issues': issues, 'issue_examples': rows(connection, 'SELECT * FROM validation_issue ORDER BY issue_id LIMIT 100'),
        'integrity': integrity, 'raw_fidelity': {'records_checked': reconstructed_count, 'mismatch_examples': mismatches},
        'source_sample_checks': sample_checks,
        'hierarchy': {'missing_reverse_count': len(missing_reverse), 'missing_reverse_examples': missing_reverse[:100],
                      'cycle_example': cycle, 'cycles_exhaustively_enumerated': False},
        'limitations': ['Eraldi äraviitekirjete semantiline teisendamine pole EMS-i tegeliku XML-näitega kinnitatud.',
                       'Hierarhia vastastikkuse erinevused, tsüklid ja nimeteksti erinevused on hoiatused; algseoseid ei muudeta.',
                       'Lemmatiseerimine ja otsinguindeks kuuluvad etappi 3.'],
    }
