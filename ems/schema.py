"""Explicit types prevent XML identifiers and domain codes becoming numbers."""

TABLES = {
    'marc_record': {
        'record_pk': 'BIGINT', 'ems_id_raw': 'VARCHAR', 'leader': 'VARCHAR',
        'record_status': 'VARCHAR', 'record_type': 'VARCHAR',
        'attributes_json': 'VARCHAR', 'raw_sha256': 'VARCHAR',
    },
    'marc_field': {
        'field_id': 'BIGINT', 'record_pk': 'BIGINT', 'field_pos': 'INTEGER',
        'kind': 'VARCHAR', 'tag': 'VARCHAR', 'ind1': 'VARCHAR', 'ind2': 'VARCHAR',
        'value': 'VARCHAR', 'attributes_json': 'VARCHAR',
    },
    'marc_subfield': {
        'field_id': 'BIGINT', 'subfield_pos': 'INTEGER', 'code': 'VARCHAR',
        'value': 'VARCHAR', 'attributes_json': 'VARCHAR',
    },
    'validation_issue': {
        'issue_id': 'BIGINT', 'severity': 'VARCHAR', 'code': 'VARCHAR',
        'record_pk': 'BIGINT', 'field_id': 'BIGINT', 'detail': 'VARCHAR',
    },
}

RAW_CONSTRAINTS = {
    'marc_record': ', PRIMARY KEY(record_pk)',
    'marc_field': ', PRIMARY KEY(field_id), UNIQUE(record_pk, field_pos)',
    'marc_subfield': ', PRIMARY KEY(field_id, subfield_pos)',
    'validation_issue': ', PRIMARY KEY(issue_id)',
}

SEMANTIC_SQL = """
CREATE TABLE concept (
    ems_id VARCHAR PRIMARY KEY, record_pk BIGINT UNIQUE REFERENCES marc_record(record_pk),
    preferred_label_id BIGINT, concept_type VARCHAR, uri VARCHAR, status VARCHAR);
CREATE TABLE label (
    label_id BIGINT PRIMARY KEY, ems_id VARCHAR REFERENCES concept(ems_id),
    field_id BIGINT REFERENCES marc_field(field_id), text VARCHAR,
    language VARCHAR, role VARCHAR, marc_tag VARCHAR);
CREATE TABLE relation (
    relation_id BIGINT PRIMARY KEY, ems_id VARCHAR REFERENCES concept(ems_id),
    field_id BIGINT REFERENCES marc_field(field_id), kind VARCHAR, w_raw VARCHAR,
    target_uri_raw VARCHAR, target_id_raw VARCHAR,
    target_id VARCHAR REFERENCES concept(ems_id), target_label_raw VARCHAR, resolution VARCHAR,
    resolution_method VARCHAR);
CREATE TABLE relation_candidate (
    relation_id BIGINT REFERENCES relation(relation_id), ems_id VARCHAR REFERENCES concept(ems_id),
    match_origin VARCHAR, type_matches BOOLEAN, label_matches BOOLEAN,
    PRIMARY KEY(relation_id, ems_id));
CREATE TABLE domain (domain_code VARCHAR PRIMARY KEY, scheme VARCHAR, name VARCHAR);
CREATE TABLE concept_domain (
    ems_id VARCHAR REFERENCES concept(ems_id), domain_code VARCHAR REFERENCES domain(domain_code),
    field_id BIGINT PRIMARY KEY REFERENCES marc_field(field_id));
CREATE TABLE concept_note (
    note_id BIGINT PRIMARY KEY, ems_id VARCHAR REFERENCES concept(ems_id),
    field_id BIGINT REFERENCES marc_field(field_id), kind VARCHAR, text VARCHAR);
CREATE TABLE redirect (
    record_pk BIGINT PRIMARY KEY REFERENCES marc_record(record_pk),
    target_uri_raw VARCHAR, target_id_raw VARCHAR, target_id VARCHAR,
    resolution VARCHAR);
CREATE TABLE source_snapshot (
    snapshot_id VARCHAR PRIMARY KEY, source_url VARCHAR, acquired_at_utc VARCHAR,
    downloaded_at_utc VARCHAR, acquisition VARCHAR, original_path VARCHAR,
    sha256 VARCHAR, byte_count BIGINT, http_metadata_json VARCHAR);
CREATE TABLE processing_run (
    run_id VARCHAR PRIMARY KEY, snapshot_id VARCHAR REFERENCES source_snapshot(snapshot_id),
    schema_version INTEGER, import_version VARCHAR, started_at_utc VARCHAR,
    completed_at_utc VARCHAR, status VARCHAR, environment_json VARCHAR,
    source_counts_json VARCHAR, timings_json VARCHAR);
CREATE VIEW concept_domains_distinct AS SELECT DISTINCT ems_id, domain_code FROM concept_domain;
"""
