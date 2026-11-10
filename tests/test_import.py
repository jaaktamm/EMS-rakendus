import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
import xml.etree.ElementTree as ET

import duckdb
import requests

from ems.storage import prepare, database, validate_current, EMSDataError, current, data_lock, acquire
from ems.validation import reconstructed, cycle_example
from ems.xmlio import NS, Q, records


def field(tag, subs, ind2=' ', ind1=' '):
    f = ET.Element(Q+'datafield', tag=tag, ind1=ind1, ind2=ind2)
    for code, value in subs:
        ET.SubElement(f, Q+'subfield', code=code).text = value
    return f


def record(rid, title, tag='150', status='n', rtype='a', extra=()):
    r = ET.Element(Q+'record')
    leader = list('00408nz  a2200145n  4500')
    leader[5] = status
    ET.SubElement(r, Q+'leader').text = ''.join(leader)
    ET.SubElement(r, Q+'controlfield', tag='001').text = rid
    r.append(field('072', [('a','00'),('2','ems')], ind2='7'))
    ET.SubElement(r, Q+'controlfield', tag='003').text = 'ErEMS'
    fixed = list('090101|n|annnnbabn           | |n|      ')
    fixed[9] = rtype
    ET.SubElement(r, Q+'controlfield', tag='008').text = ''.join(fixed)
    r.append(field(tag, [('a',title),('0','https://ems.elnet.ee/id/'+rid)]))
    for f in extra:
        r.append(f)
    return r


def xmlfile(path, *items):
    root = ET.Element(Q+'collection')
    root.extend(items)
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)
    return path


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root/'data'
        self.xml = xmlfile(self.root/'small.xml',
            record('EMS000001', 'raamatukogud', extra=[
                field('450',[('a','biblioteegid')]),
                field('450',[('a','libraries')],ind2='9'),
                field('450',[('a','biblioteegid')]),
                field('550',[('w','g'),('a','asutused'),('0','https://ems.elnet.ee/id/EMS000002')]),
                field('550',[('a','puuduv'),('0','https://ems.elnet.ee/id/EMS999999')]),
                field('072',[('a','01'),('2','ems')],ind2='7'),
                field('680',[('i','  Selgitus õäöü  ')]),
                field('670',[('a','allikas')]),
            ]), record('EMS000002','asutused',extra=[
                field('550',[('w','h'),('a','raamatukogud'),('0','https://ems.elnet.ee/id/EMS000001')])]),
            record('EMS000003','20. sajand', tag='148',extra=[field('448',[('a','20th century')],ind2='9')]))

    def build(self):
        return prepare(self.data, self.xml)

    def test_roundtrip_and_semantics(self):
        self.build()
        with database(self.data) as (c, generation, manifest):
            source = dict(records(self.xml))
            actual = {pk:r for pk, _, r in reconstructed(c)}
            self.assertEqual(source, actual)
            self.assertEqual(c.execute("SELECT length(value) FROM marc_field WHERE tag='008' LIMIT 1").fetchone()[0],40)
            self.assertEqual(c.execute("SELECT count(*) FROM label WHERE text='biblioteegid'").fetchone()[0],2)
            self.assertEqual(c.execute("SELECT language,role FROM label WHERE text='libraries'").fetchone(),('en','english_equivalent'))
            self.assertEqual(c.execute("SELECT l.text FROM label alt JOIN concept c USING(ems_id) JOIN label l ON l.label_id=c.preferred_label_id WHERE alt.text='biblioteegid' LIMIT 1").fetchone()[0],'raamatukogud')
            self.assertEqual(c.execute('SELECT domain_code FROM domain ORDER BY 1').fetchall(),[('00',),('01',)])
            self.assertEqual(c.execute("SELECT kind,target_id,target_label_raw FROM relation WHERE kind='broad'").fetchone(),('broad','EMS000002','asutused'))
            self.assertEqual(c.execute("SELECT text FROM concept_note WHERE kind='scope'").fetchone()[0],'  Selgitus õäöü  ')
            self.assertEqual(c.execute("SELECT count(*) FROM validation_issue WHERE code='unresolved_relation'").fetchone()[0],1)
            self.assertEqual(c.execute("SELECT concept_type FROM concept WHERE ems_id='EMS000003'").fetchone()[0],'temporal')
        report = validate_current(self.data)
        self.assertTrue(report['ok'], report['errors'])
        self.assertEqual(report['unresolved_relation_count'],1)
        self.assertTrue(all(x['equal'] for x in report['source_sample_checks']))

    def test_ready_database_is_reused_without_network_or_source(self):
        first = self.build()
        with patch('ems.storage.requests.get',side_effect=AssertionError('Võrku ei tohi kasutada')), patch('ems.storage.acquire',side_effect=AssertionError('Ei tohi importida')):
            second = prepare(self.data, self.root/'does-not-exist.xml')
        self.assertEqual(second['action'],'reused')
        self.assertEqual(second['manifest'], first['manifest'])

    def test_failed_refresh_keeps_old_database(self):
        first = self.build()
        old_manifest = (self.data/'current.json').read_bytes()
        old_hash = hashlib.sha256(Path(first['database']).read_bytes()).hexdigest()
        bad = self.root/'bad.xml'
        bad.write_text('<html>Server error</html>',encoding='utf-8')
        with self.assertRaises(EMSDataError):
            prepare(self.data,bad,refresh=True)
        self.assertEqual((self.data/'current.json').read_bytes(),old_manifest)
        self.assertEqual(hashlib.sha256(Path(first['database']).read_bytes()).hexdigest(),old_hash)
        self.assertEqual(prepare(self.data)['action'],'reused')

    def test_failed_first_prepare_does_not_activate(self):
        self.xml.write_text('<html/>',encoding='utf-8')
        with self.assertRaises(EMSDataError):
            self.build()
        self.assertFalse((self.data/'current.json').exists())
        self.assertTrue(list((self.data/'generations').glob('*/failure.json')))

    def test_missing_subfield_blocks_activation_and_reports_field(self):
        xmlfile(self.xml, record('EMS000001','a',extra=[field('450',[('0','some-reference')])]))
        with self.assertRaises(EMSDataError):
            self.build()
        report = json.loads(next((self.data/'generations').glob('*/validation.json')).read_text(encoding='utf-8'))
        self.assertFalse(report['ok'])
        self.assertTrue(any(x['code']=='missing_or_repeated_required_subfield' and x['field_id'] for x in report['issue_examples']))

    def test_duplicate_and_missing_ids_block(self):
        xmlfile(self.xml,record('EMS000001','a'),record('EMS000001','b'),record('','c'))
        with self.assertRaises(EMSDataError):
            self.build()
        report=json.loads(next((self.data/'generations').glob('*/validation.json')).read_text(encoding='utf-8'))
        self.assertEqual(report['missing_ids'],1)
        self.assertEqual(report['duplicate_ids'],[{'ems_id_raw':'EMS000001','count':2}])

    def test_deleted_and_redirect_records_stay_in_raw_layer(self):
        xmlfile(self.xml, record('EMS000001','a'), record('EMS000002','vana',status='d'),record('EMS000003','viide',rtype='b'))
        self.build()
        report=validate_current(self.data)
        self.assertEqual(report['concepts'],1)
        self.assertEqual(len(report['excluded_records']),2)
        self.assertEqual(report['unresolved_redirect_count'],1)
        self.assertEqual(report['raw_fidelity']['records_checked'],3)

    def test_successful_refresh_keeps_previous_generation(self):
        first=self.build()
        second=prepare(self.data,self.xml,refresh=True)
        self.assertNotEqual(first['manifest']['run_id'],second['manifest']['run_id'])
        self.assertEqual(json.loads((self.data/'current.previous.json').read_text())['run_id'],first['manifest']['run_id'])
        self.assertTrue(Path(first['database']).is_file())

    def test_incompatible_version_is_not_silently_rebuilt(self):
        self.build()
        manifest=json.loads((self.data/'current.json').read_text())
        manifest['schema_version']=999
        (self.data/'current.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(EMSDataError,'refresh'):
            prepare(self.data,self.xml)

    def test_writer_and_reader_lock(self):
        self.build()
        with data_lock(self.data):
            with self.assertRaisesRegex(EMSDataError,'kasutusel'):
                prepare(self.data,self.xml,refresh=True)

    def test_source_corruption_detected(self):
        result=self.build()
        source=Path(result['database']).parent/'source.xml'
        source.write_bytes(source.read_bytes()+b'\n')
        self.assertFalse(validate_current(self.data)['ok'])

    def test_raw_database_corruption_detected(self):
        result=self.build()
        with duckdb.connect(result['database']) as c:
            c.execute("UPDATE marc_field SET value='changed' WHERE tag='008'")
        report=validate_current(self.data)
        self.assertFalse(report['ok'])
        self.assertTrue(report['raw_fidelity']['mismatch_examples'])

    def test_missing_id_field_is_reported(self):
        r=record('EMS000001','a')
        r.remove(r.find(Q+"controlfield[@tag='001']"))
        xmlfile(self.xml,r)
        with self.assertRaises(EMSDataError):
            self.build()
        report=json.loads(next((self.data/'generations').glob('*/validation.json')).read_text(encoding='utf-8'))
        self.assertEqual(report['missing_ids'],1)
        self.assertFalse(report['ok'])

    def test_atomic_pointer_failure_keeps_current(self):
        self.build()
        previous=(self.data/'current.json').read_bytes()
        import os
        real_replace=os.replace
        def replace(src,dst):
            if Path(dst).name=='current.json':
                raise OSError('simulated publish failure')
            return real_replace(src,dst)
        with patch('ems.storage.os.replace',side_effect=replace):
            with self.assertRaises(EMSDataError):
                prepare(self.data,self.xml,refresh=True)
        self.assertEqual((self.data/'current.json').read_bytes(),previous)

    def test_download_timeout_retries_and_rejects_html(self):
        with patch('ems.storage.requests.get',side_effect=requests.Timeout('timeout')) as get, patch('ems.storage.time.sleep'):
            with self.assertRaisesRegex(EMSDataError,'3 katset'):
                acquire(self.root/'download.xml')
            self.assertEqual(get.call_count,3)
            self.assertEqual(get.call_args.kwargs['timeout'],(20,180))
        response=Mock()
        response.__enter__=Mock(return_value=response)
        response.__exit__=Mock(return_value=False)
        response.iter_content.return_value=iter([b'<html>not xml data</html>'])
        response.headers={'Content-Type':'text/html'}
        with patch('ems.storage.requests.get',return_value=response):
            with self.assertRaisesRegex(ValueError,'collection'):
                acquire(self.root/'download.xml')

    def test_empty_and_malformed_xml(self):
        for value in ('', '<collection xmlns="'+NS+'"/>', '<collection xmlns="'+NS+'"><record>'):
            with self.subTest(value=value):
                self.xml.write_text(value)
                with self.assertRaises(EMSDataError):
                    prepare(self.data,self.xml,refresh=True)

    def test_dtd_is_rejected(self):
        self.xml.write_text('<!DOCTYPE collection [<!ENTITY x "test">]><collection xmlns="'+NS+'"/>')
        with self.assertRaises(EMSDataError):
            self.build()

    def test_cycle_detection(self):
        self.assertEqual(cycle_example([('a','b'),('b','c')]),[])
        self.assertEqual(cycle_example([('a','b'),('b','a')]),['a','b','a'])

    def test_long_ids_and_blank_optional_notes_preserved(self):
        xmlfile(self.xml,record('EMS155000444','vorm', tag='155',extra=[
            field('680',[('i','   ')]),
            field('555',[('a','teine vorm'),('0','https://ems.elnet.ee/id/EMS155000460')])]),
            record('EMS155000460','teine vorm',tag='155'))
        self.build()
        with database(self.data) as (c, _, __):
            self.assertEqual(c.execute('SELECT target_id_raw,target_id FROM relation').fetchone(),('EMS155000460','EMS155000460'))
            self.assertEqual(c.execute('SELECT text FROM concept_note').fetchone()[0],'   ')
        report=validate_current(self.data)
        self.assertTrue(report['ok'])
        self.assertEqual(report['concepts'],2)
        self.assertEqual(report['unresolved_relation_count'],0)
        self.assertEqual(report['issues'],[{'severity':'warning','code':'blank_optional_note','count':1}])

    def test_shared_uri_targets_resolve_by_type_without_overwriting_ids(self):
        long=record('EMS155000001','sama nimetus')
        long.find(Q+"datafield[@tag='150']/"+Q+"subfield[@code='0']").text='https://ems.elnet.ee/id/EMS000001'
        xmlfile(self.xml, long,record('EMS000001','sama nimetus (vormimärksõna)',tag='155'),
            record('EMS000002','lähte',extra=[
                field('550',[('a','sama nimetus'),('0','https://ems.elnet.ee/id/EMS000001')]),
                field('555',[('a','sama nimetus (vormimärksõna)'),('0','https://ems.elnet.ee/id/EMS000001')])]))
        self.build()
        with database(self.data) as (c,_,__):
            results=c.execute('SELECT f.tag,r.target_id_raw,r.target_id,r.resolution_method FROM relation r JOIN marc_field f USING(field_id) ORDER BY f.tag').fetchall()
            self.assertEqual(results,[('550','EMS000001','EMS155000001','unique_type'),('555','EMS000001','EMS000001','unique_type')])
            self.assertEqual(c.execute('SELECT count(*) FROM relation_candidate').fetchone()[0],4)
        report=validate_current(self.data)
        self.assertTrue(report['ok'])
        self.assertEqual(report['shared_uri_count'],1)

    def test_ambiguous_same_type_targets_remain_unresolved(self):
        one=record('EMS000001','a')
        two=record('EMS000002','b')
        two.find(Q+"datafield[@tag='150']/"+Q+"subfield[@code='0']").text='https://ems.elnet.ee/id/EMS000001'
        xmlfile(self.xml, one, two,record('EMS000003','c',extra=[
            field('550',[('a','ei erista'),('0','https://ems.elnet.ee/id/EMS000001')])]))
        self.build()
        with database(self.data) as (c,_,__):
            self.assertEqual(c.execute('SELECT target_id,resolution FROM relation').fetchone(),(None,'ambiguous'))


if __name__=='__main__':
    unittest.main()
