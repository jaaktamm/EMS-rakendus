"""Stream source to typed staging files, then bulk-load DuckDB, not row-by-row SQL."""
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
import re
import tempfile

from .schema import TABLES, RAW_CONSTRAINTS, SEMANTIC_SQL
from .xmlio import records, dumps, digest

ID_RE = re.compile(r'EMS[0-9]+\Z')
HEADINGS = {'148': 'temporal', '150': 'topical', '151': 'geographic', '155': 'genre_form'}
VARIANTS = ('448', '450', '451', '455')
RELATIONS = ('548', '550', '551', '555')


def stage_source(connection, xml_path, directory):
    counts = {name: Counter() for name in ('fields', 'subfields', 'indicators', 'leader_status', 'record_type')}
    field_id, issue_id, record_count = 0, 0, 0
    with tempfile.TemporaryDirectory(prefix='staging-', dir=directory) as temp, ExitStack() as stack:
        paths = {table: Path(temp) / (table + '.jsonl') for table in TABLES}
        writers = {table: stack.enter_context(path.open('w', encoding='utf-8', newline='\n'))
                   for table, path in paths.items()}

        def emit(table, row):
            writers[table].write(dumps(row) + '\n')

        def issue(severity, code, record_pk, field, detail):
            nonlocal issue_id
            issue_id += 1
            emit('validation_issue', dict(issue_id=issue_id, severity=severity, code=code,
                 record_pk=record_pk, field_id=field, detail=detail))

        for record_pk, record in records(xml_path):
            record_count += 1
            fields = record['fields']
            ids = [f['value'] for f in fields if f['kind'] == 'controlfield' and f['tag'] == '001']
            leaders = [f['value'] for f in fields if f['kind'] == 'leader']
            fixed = [f['value'] for f in fields if f['kind'] == 'controlfield' and f['tag'] == '008']
            rid = ids[0] if len(ids) == 1 else None
            leader = leaders[0] if len(leaders) == 1 else None
            status = leader[5:6] if leader else None
            rtype = fixed[0][9:10] if len(fixed) == 1 else None
            if rid is None or not ID_RE.fullmatch(rid):
                issue('error', 'invalid_id', record_pk, None, dumps(ids))
            if len(leaders) != 1 or len(leader or '') != 24:
                issue('error', 'invalid_leader', record_pk, None, dumps(leaders))
            if len(fixed) != 1 or len(fixed[0]) != 40:
                issue('warning', 'invalid_008_length', record_pk, None, dumps(fixed))
            if status not in ('n', 'c', 'a', 'd'):
                issue('error', 'unknown_status', record_pk, None, str(status))
            if rtype not in ('a', 'b', 'c'):
                issue('error', 'unknown_record_type', record_pk, None, str(rtype))
            if status == 'd':
                issue('warning', 'excluded_deleted', record_pk, None, 'Kustutatud kirje ainult toorkihis.')
            elif rtype != 'a':
                issue('warning', 'excluded_redirect', record_pk, None,
                      'Äraviitekirje säilib toorkihis; XML-esituse semantika pole EMS-i failiga kinnitatud.')
            headings = [f for f in fields if f['kind'] == 'datafield' and f['tag'] in HEADINGS]
            if status != 'd' and rtype == 'a' and len(headings) != 1:
                issue('error', 'invalid_heading_count', record_pk, None, str(len(headings)))
            counts['leader_status'][status or ''] += 1
            counts['record_type'][rtype or ''] += 1
            emit('marc_record', dict(record_pk=record_pk, ems_id_raw=rid, leader=leader,
                 record_status=status, record_type=rtype,
                 attributes_json=dumps(record['attributes']), raw_sha256=digest(record)))
            for pos, f in enumerate(fields, 1):
                field_id += 1
                tag = f['tag']
                counts['fields'][tag if tag is not None else f['kind']] += 1
                emit('marc_field', dict(field_id=field_id, record_pk=record_pk, field_pos=pos,
                     kind=f['kind'], tag=tag, ind1=f['ind1'], ind2=f['ind2'], value=f['value'],
                     attributes_json=dumps(f['attributes'])))
                if f['kind'] == 'leader':
                    continue
                if not tag or not re.fullmatch(r'[0-9]{3}', tag):
                    issue('error', 'invalid_tag', record_pk, field_id, str(tag))
                if f['kind'] != 'datafield':
                    continue
                counts['indicators'][f"{tag}|{f['ind1']}|{f['ind2']}"] += 1
                if any(v is None or len(v) != 1 for v in (f['ind1'], f['ind2'])):
                    issue('error', 'invalid_indicator', record_pk, field_id, dumps(f['attributes']))
                values = {}
                for subpos, sub in enumerate(f['subfields'], 1):
                    emit('marc_subfield', dict(field_id=field_id, subfield_pos=subpos,
                         code=sub['code'], value=sub['value'], attributes_json=dumps(sub['attributes'])))
                    counts['subfields'][str(tag) + '$' + str(sub['code'])] += 1
                    values.setdefault(sub['code'], []).append(sub['value'])
                    if sub['code'] is None or len(sub['code']) != 1:
                        issue('error', 'invalid_subfield_code', record_pk, field_id, str(sub['code']))
                required = []
                if tag in (*HEADINGS, *VARIANTS, *RELATIONS, '072', '670'):
                    required = ['a']
                elif tag == '680':
                    required = ['i']
                for code in required:
                    if len(values.get(code, [])) != 1:
                        issue('error', 'missing_or_repeated_required_subfield', record_pk, field_id, '$' + code)
                    elif not values[code][0].strip():
                        if tag in ('680', '670'):
                            issue('warning', 'blank_optional_note', record_pk, field_id,
                                  'Tühikutest koosnev märkus säilib muutmata.')
                        else:
                            issue('error', 'blank_required_subfield', record_pk, field_id, '$' + code)
                for code in ('w', '0', '2'):
                    if len(values.get(code, [])) > 1:
                        issue('error', 'repeated_single_subfield', record_pk, field_id, '$' + code)
                if tag in VARIANTS and f['ind2'] not in (' ', '9'):
                    issue('warning', 'unknown_label_language', record_pk, field_id, str(f['ind2']))
                if tag in RELATIONS and values.get('w', [''])[0] not in ('', 'g', 'h'):
                    issue('warning', 'unknown_relation_kind', record_pk, field_id, dumps(values.get('w')))
                if tag == '072' and (values.get('2') != ['ems'] or f['ind2'] != '7'):
                    issue('error', 'invalid_domain_scheme', record_pk, field_id, dumps(values))
        # Flush before DuckDB opens staging files; keep handles closed on Windows.
        stack.close()
        for table, columns in TABLES.items():
            ddl = ', '.join('"' + k + '" ' + v for k, v in columns.items())
            connection.execute(f'CREATE TABLE {table} ({ddl}{RAW_CONSTRAINTS[table]})')
            if paths[table].stat().st_size:
                types = '{' + ','.join("'" + k + "':'" + v + "'" for k, v in columns.items()) + '}'
                connection.execute(f'INSERT INTO {table} BY NAME SELECT * FROM read_json(?, format=\'newline_delimited\', columns={types})', [str(paths[table])])
    return {'records': record_count, **{name: dict(counter) for name, counter in counts.items()}}


def derive(connection):
    connection.execute(SEMANTIC_SQL)
    # Aggregate ONLY within one field. Repeated fields retain independent IDs.
    connection.execute("""
        CREATE TEMP TABLE field_values AS
        SELECT f.*, a.a, a.i, a.zero, a.w, a.scheme
        FROM marc_field f LEFT JOIN (
            SELECT field_id,
                first(value ORDER BY subfield_pos) FILTER(WHERE code='a') AS a,
                first(value ORDER BY subfield_pos) FILTER(WHERE code='i') AS i,
                first(value ORDER BY subfield_pos) FILTER(WHERE code='0') AS zero,
                first(value ORDER BY subfield_pos) FILTER(WHERE code='w') AS w,
                first(value ORDER BY subfield_pos) FILTER(WHERE code='2') AS scheme
            FROM marc_subfield GROUP BY field_id
        ) a USING(field_id);
        CREATE TEMP TABLE eligible AS
        SELECT r.* FROM marc_record r
        WHERE r.record_status IN ('n','c','a') AND r.record_type='a'
          AND (SELECT count(*) FROM marc_record d WHERE d.ems_id_raw=r.ems_id_raw)=1
          AND (SELECT count(*) FROM marc_field f WHERE f.record_pk=r.record_pk AND f.tag IN ('148','150','151','155'))=1
          AND NOT EXISTS(SELECT 1 FROM validation_issue v WHERE v.record_pk=r.record_pk AND v.severity='error');
        INSERT INTO concept
        SELECT r.ems_id_raw, r.record_pk, f.field_id,
            CASE f.tag WHEN '148' THEN 'temporal' WHEN '150' THEN 'topical'
                       WHEN '151' THEN 'geographic' ELSE 'genre_form' END,
            coalesce(f.zero, 'https://ems.elnet.ee/id/' || r.ems_id_raw), 'active'
        FROM eligible r JOIN field_values f USING(record_pk)
        WHERE f.tag IN ('148','150','151','155');
        INSERT INTO label
        SELECT f.field_id, c.ems_id, f.field_id, f.a,
            CASE WHEN f.tag IN ('148','150','151','155') OR f.ind2=' ' THEN 'et'
                 WHEN f.ind2='9' THEN 'en' ELSE 'und' END,
            CASE WHEN f.tag IN ('148','150','151','155') THEN 'preferred'
                 WHEN f.ind2='9' THEN 'english_equivalent' ELSE 'alternative' END, f.tag
        FROM field_values f JOIN concept c USING(record_pk)
        WHERE f.tag IN ('148','150','151','155','448','450','451','455') AND f.a IS NOT NULL;
        INSERT INTO relation
        SELECT f.field_id, c.ems_id, f.field_id,
            CASE WHEN f.w='g' THEN 'broad' WHEN f.w='h' THEN 'narrow'
                 WHEN coalesce(f.w,'')='' THEN 'related' ELSE 'unknown' END,
            f.w, f.zero,
            CASE WHEN regexp_full_match(f.zero, 'https://ems[.]elnet[.]ee/id/EMS[0-9]+')
                 THEN regexp_extract(f.zero, '/(EMS[0-9]+)$', 1) END,
            NULL, f.a, 'unresolved', NULL
        FROM field_values f JOIN concept c USING(record_pk)
        WHERE f.tag IN ('548','550','551','555');
        CREATE TEMP TABLE candidate_staging AS
        SELECT r.relation_id, target.ems_id,
            CASE WHEN target.uri=r.target_uri_raw AND target.ems_id=r.target_id_raw THEN 'id_and_declared_uri'
                 WHEN target.uri=r.target_uri_raw THEN 'declared_uri' ELSE 'record_id' END AS match_origin,
            target.concept_type=CASE f.tag WHEN '548' THEN 'temporal' WHEN '550' THEN 'topical'
                                          WHEN '551' THEN 'geographic' ELSE 'genre_form' END AS type_matches,
            preferred.text=r.target_label_raw AS label_matches
        FROM relation r JOIN marc_field f USING(field_id)
        JOIN (
            SELECT r.relation_id,c.ems_id FROM relation r JOIN concept c ON c.uri=r.target_uri_raw
            UNION
            SELECT r.relation_id,c.ems_id FROM relation r JOIN concept c ON c.ems_id=r.target_id_raw
        ) pair ON pair.relation_id=r.relation_id
        JOIN concept target ON target.ems_id=pair.ems_id
        JOIN label preferred ON preferred.label_id=target.preferred_label_id;
        CREATE TEMP TABLE resolved_candidates AS
        SELECT relation_id,
            CASE WHEN count(*) FILTER(WHERE type_matches)=1 THEN min(ems_id) FILTER(WHERE type_matches)
                 WHEN count(*) FILTER(WHERE type_matches AND label_matches)=1
                    THEN min(ems_id) FILTER(WHERE type_matches AND label_matches)
                 WHEN count(*)=1 THEN min(ems_id) END AS chosen,
            CASE WHEN count(*) FILTER(WHERE type_matches)=1 THEN 'unique_type'
                 WHEN count(*) FILTER(WHERE type_matches AND label_matches)=1 THEN 'unique_type_and_label'
                 WHEN count(*)=1 THEN 'unique_candidate_type_warning' ELSE 'ambiguous' END AS method
        FROM candidate_staging GROUP BY relation_id;
        UPDATE relation SET target_id=x.chosen, resolution=CASE WHEN x.chosen IS NULL THEN 'ambiguous' ELSE 'resolved' END,
                            resolution_method=x.method
        FROM resolved_candidates x WHERE relation.relation_id=x.relation_id;
        INSERT INTO relation_candidate SELECT * FROM candidate_staging;
        INSERT INTO domain
        SELECT DISTINCT f.a, f.scheme, NULL FROM field_values f JOIN concept c USING(record_pk)
        WHERE f.tag='072' AND f.a IS NOT NULL;
        INSERT INTO concept_domain
        SELECT c.ems_id, f.a, f.field_id FROM field_values f JOIN concept c USING(record_pk)
        WHERE f.tag='072' AND f.a IS NOT NULL;
        INSERT INTO concept_note
        SELECT f.field_id, c.ems_id, f.field_id,
            CASE WHEN f.tag='680' THEN 'scope' ELSE 'source' END,
            CASE WHEN f.tag='680' THEN f.i ELSE f.a END
        FROM field_values f JOIN concept c USING(record_pk) WHERE f.tag IN ('680','670');
        INSERT INTO redirect
        SELECT record_pk, NULL, NULL, NULL, 'unverified_representation'
        FROM marc_record WHERE record_type IN ('b','c') AND record_status != 'd';
    """)
    next_issue = connection.execute('SELECT coalesce(max(issue_id),0) FROM validation_issue').fetchone()[0]

    def issues(sql, code, severity='warning'):
        nonlocal next_issue
        rows = connection.execute(sql).fetchall()
        if rows:
            connection.executemany('INSERT INTO validation_issue VALUES (?,?,?,?,?,?)',
                [(next_issue+i, severity, code, *row) for i, row in enumerate(rows, 1)])
            next_issue += len(rows)

    issues("""SELECT record_pk, NULL, ems_id_raw FROM marc_record
               WHERE ems_id_raw IN (SELECT ems_id_raw FROM marc_record GROUP BY 1 HAVING count(*)>1)""", 'duplicate_id', 'error')
    issues("""SELECT c.record_pk, r.field_id, coalesce(r.target_uri_raw, 'Puuduv $0')
               FROM relation r JOIN concept c USING(ems_id) WHERE r.target_id IS NULL""", 'unresolved_relation')
    issues("""SELECT c.record_pk, r.field_id, r.target_label_raw || ' != ' || l.text
               FROM relation r JOIN concept c USING(ems_id)
               JOIN concept target ON target.ems_id=r.target_id JOIN label l ON l.label_id=target.preferred_label_id
               WHERE r.target_label_raw != l.text""", 'target_label_mismatch')
    issues("""SELECT record_pk, preferred_label_id, uri FROM concept
               WHERE uri != 'https://ems.elnet.ee/id/' || ems_id""", 'heading_uri_differs_from_record_id')
    issues("""SELECT c.record_pk, f.field_id, f.zero FROM concept c JOIN field_values f USING(record_pk)
               WHERE f.tag='024' AND f.zero != 'https://ems.elnet.ee/id/' || c.ems_id""", 'record_uri_differs_from_record_id')
    issues("""SELECT c.record_pk,r.field_id,r.target_uri_raw
               FROM relation r JOIN concept c USING(ems_id)
               WHERE r.resolution_method='unique_candidate_type_warning'""", 'relation_target_type_mismatch')
    issues("""SELECT record_pk, NULL, coalesce(ems_id_raw,'Puuduv ID') FROM marc_record r
               WHERE NOT EXISTS(SELECT 1 FROM concept c WHERE c.record_pk=r.record_pk)
                 AND record_status != 'd' AND coalesce(record_type,'') NOT IN ('b','c')""", 'excluded_invalid_record', 'error')
    connection.execute('DROP TABLE field_values; DROP TABLE eligible; DROP TABLE resolved_candidates; DROP TABLE candidate_staging;')
