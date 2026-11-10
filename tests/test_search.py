import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch, Mock

from ems.linguistics import analyzer, signature, key, analyze_label
from ems.ranking import rank
from ems.search import search_session, read_text_file
from ems.search_index import ensure_index
from ems.storage import prepare, EMSDataError
from tests.test_import import record,field,xmlfile


class SearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.root=Path(cls.temp.name)
        cls.data=cls.root/'data'
        cls.source=xmlfile(cls.root/'terms.xml',
            record('EMS000001','raamatukogud',extra=[field('450',[('a','biblioteegid')]),field('450',[('a','libraries')],ind2='9')]),
            record('EMS000002','raamatukogu'),
            record('EMS000003','vanad raamatud'),
            record('EMS000004','raamat'),
            record('EMS000005','eesti keel'),
            record('EMS000006','eesti'),
            record('EMS000007','keel'),
            record('EMS000008','roheline õun'),
            record('EMS000009','õun'),
            record('EMS000010','mõte ja tegu'),
            record('EMS000011','infotehnoloogia',extra=[
                field('550',[('a','kala'),('0','https://ems.elnet.ee/id/EMS000013')])]),
            record('EMS000012','tehnoloogia'),
            record('EMS000013','kala'),record('EMS000014','kala'),
            record('EMS000015','v\u00f5i'),record('EMS000016','kala v\u00f5i liha'),
            record('EMS000017','sai'))
        prepare(cls.data,cls.source)
        ensure_index(cls.data)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def extract(self,text,**kwargs):
        with search_session(self.data) as engine:
            return engine.keywords(text,**kwargs)

    def test_inflected_words_and_same_lemma_multiple_concepts(self):
        result=self.extract('Raamatukogudes töötatakse.')
        ids={r['ems_id'] for r in result['results']}
        self.assertTrue({'EMS000001','EMS000002'}<=ids)
        self.assertTrue(all(r['match_type']=='lemma' for r in result['results'] if r['ems_id'] in ids))

    def test_synonym_and_official_name(self):
        result=self.extract('Biblioteegid on avatud.')
        item=next(x for x in result['results'] if x['ems_id']=='EMS000001')
        self.assertEqual(item['preferred_label'],'raamatukogud')
        self.assertEqual(item['matched_label'],'biblioteegid')
        self.assertEqual(item['match_type'],'exact')
        self.assertEqual(self.extract('Biblioteegid on avatud.',strategy='lemma')['results'],[])

    def test_phrase_beats_nested_single_word(self):
        results=self.extract('Vanu raamatuid loeti.')['results']
        self.assertEqual(results[0]['ems_id'],'EMS000003')
        self.assertNotIn('EMS000004',[r['ems_id'] for r in results])

    def test_sentence_boundary_blocks_phrase(self):
        results=self.extract('Roheline. Õun.')['results']
        self.assertNotIn('EMS000008',[r['ems_id'] for r in results])
        self.assertIn('EMS000009',[r['ems_id'] for r in results])

    def test_phrase_with_stopword(self):
        self.assertIn('EMS000010',[r['ems_id'] for r in self.extract('Mõte ja tegu.')['results']])

    def test_pos_filter_removes_standalone_conjunction_but_keeps_noun_and_phrase(self):
        conjunction=self.extract('A v\u00f5i B.')
        self.assertNotIn('EMS000015',[r['ems_id'] for r in conjunction['results']])
        self.assertGreater(conjunction['diagnostics']['pos_filtered_occurrences'],0)

        noun=self.extract('Kasuta v\u00f5id v\u00f5i margariini.')
        item=next(r for r in noun['results'] if r['ems_id']=='EMS000015')
        self.assertEqual(item['frequency'],1)
        self.assertEqual(item['evidence'][0]['text'],'v\u00f5id')

        phrase=self.extract('Kala v\u00f5i liha.')
        self.assertIn('EMS000016',[r['ems_id'] for r in phrase['results']])

    def test_pos_confidence_adjusts_score_and_uncertainty_weight(self):
        match=dict(kind='lemma',match_key='["kala"]',label_id=1,ems_id='EMS000099',
                   original_text='kala',role='preferred',token_count=1,pos_options=[['S']])
        def score(query_pos):
            occurrence=dict(sentence_id=0,start=0,end=4,text='kala',_pos_options=(query_pos,))
            results,_=rank([match],{('lemma','["kala"]'):[occurrence]})
            return results[0]

        aligned=score(('S',))
        self.assertEqual(aligned['pos_correction'],2)
        self.assertEqual(aligned['effective_frequency'],1)
        self.assertEqual(aligned['pos_confidence']['match'],1)

        uncertain=score(('S','V'))
        self.assertEqual(uncertain['pos_correction'],0)
        self.assertEqual(uncertain['effective_frequency'],0.5)
        self.assertEqual(uncertain['pos_confidence']['uncertain'],1)

        conflict=score(('V',))
        self.assertEqual(conflict['pos_correction'],-2)
        self.assertEqual(conflict['effective_frequency'],0.5)
        self.assertEqual(conflict['pos_confidence']['conflict'],1)

    def test_polysemous_contextless_label_does_not_get_false_pos_bonus(self):
        options=analyze_label('sai','et')['pos_options'][0]
        self.assertEqual(set(options),{'S','V'})
        item=next(r for r in self.extract('Saavad.')['results'] if r['ems_id']=='EMS000017')
        self.assertEqual(item['pos_correction'],0)
        self.assertEqual(item['effective_frequency'],0.5)
        self.assertEqual(item['pos_confidence']['uncertain'],1)

    def test_compounds_are_not_split(self):
        results=self.extract('Infotehnoloogias töötatakse.')['results']
        self.assertIn('EMS000011',[r['ems_id'] for r in results])
        self.assertNotIn('EMS000012',[r['ems_id'] for r in results])

    def test_related_concepts_are_information_not_text_matches(self):
        result=self.extract('Infotehnoloogia.')['results']
        self.assertEqual([r['ems_id'] for r in result],['EMS000011'])
        self.assertEqual(result[0]['relations'][0]['target_id'],'EMS000013')

    def test_same_surface_multiple_concepts_survive(self):
        result=self.extract('Kala.')['results']
        self.assertEqual({r['ems_id'] for r in result},{'EMS000013','EMS000014'})

    def test_concept_merge_and_capped_frequency(self):
        results=self.extract('Raamatukogud ja biblioteegid. Raamatukogud.')['results']
        item=next(r for r in results if r['ems_id']=='EMS000001')
        self.assertEqual(item['frequency'],3)
        self.assertEqual(sum(r['ems_id']=='EMS000001' for r in results),1)
        many=next(r for r in self.extract('Raamatukogud. '*100)['results'] if r['ems_id']=='EMS000001')
        self.assertEqual(many['score']-item['score'],18.0)

    def test_original_offsets_after_unicode_normalization(self):
        text='🍏 O\u0303UN!'
        result=self.extract(text)['results']
        item=next(r for r in result if r['ems_id']=='EMS000009')
        e=item['evidence'][0]
        self.assertEqual(e['text'],'O\u0303UN')
        self.assertEqual(text[e['start']:e['end']],e['text'])
        self.assertEqual(e['snippet'][e['highlight_start']:e['highlight_end']],e['text'])

    def test_lookup_exact_lemma_prefix_and_english(self):
        with search_session(self.data) as engine:
            self.assertTrue(engine.lookup('Raamatukogud',mode='exact')['results'])
            self.assertTrue(engine.lookup('raamatukogudes',mode='lemma')['results'])
            self.assertTrue(engine.lookup('raamatu',mode='prefix')['results'])
            result=engine.lookup('libraries',language='en')['results']
            self.assertEqual(result[0]['preferred_label'],'raamatukogud')
            self.assertEqual(result[0]['language'],'en')
            self.assertEqual(engine.c.execute("SELECT count(*) FROM idx.search_label WHERE language='en' AND lemmas IS NOT NULL").fetchone()[0],0)

    def test_batch_join_uses_constant_sql_calls(self):
        with search_session(self.data) as engine:
            original=engine.c
            engine.c=Mock(wraps=original)
            result=engine.keywords('Raamatukogud. '*100,explain=True)
            self.assertEqual(engine.c.execute.call_count,6)
            self.assertEqual(result['diagnostics']['sql_calls'],6)
            self.assertIn('HASH_JOIN',result['query_plan'])
            self.assertLess(result['diagnostics']['unique_keys'],result['diagnostics']['candidate_occurrences'])

    def test_empty_invalid_limit_and_zero_match(self):
        for text in ('',' \n'):
            with self.assertRaises(EMSDataError):
                self.extract(text)
        for limit in (0,51):
            with self.assertRaises(EMSDataError):
                self.extract('kala',limit=limit)
        self.assertEqual(self.extract('xyzqwerty')['results'],[])
        with patch.dict(os.environ,{'EMS_MAX_INPUT_BYTES':'3'}):
            with self.assertRaises(EMSDataError):
                self.extract('raamat')

    def test_bom_and_invalid_encoding(self):
        path=self.root/'input.txt'
        path.write_bytes(b'\xef\xbb\xbf'+ 'õun'.encode('utf-8'))
        self.assertEqual(read_text_file(path),'õun')
        path.write_bytes(b'\xff\xfe\x00')
        with self.assertRaisesRegex(EMSDataError,'UTF-8'):
            read_text_file(path)

    def test_index_reuse_does_not_lemmatize_again(self):
        with patch('ems.search_index.analyze_label',side_effect=AssertionError('Uuesti ei analüüsi')):
            self.assertEqual(ensure_index(self.data)['action'],'reused')

    def test_failed_index_rebuild_preserves_old_index(self):
        before=(self.data/'search_current.json').read_bytes()
        with patch('ems.search_index.analyze_label',side_effect=RuntimeError('Simuleeritud tõrge')):
            with self.assertRaises(EMSDataError):
                ensure_index(self.data,rebuild=True)
        self.assertEqual((self.data/'search_current.json').read_bytes(),before)
        self.assertTrue(self.extract('kala')['results'])

    def test_stale_index_version_requires_explicit_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp:
            copied=Path(tmp)/'data'
            shutil.copytree(self.data,copied)
            p=copied/'search_current.json'
            m=json.loads(p.read_text(encoding='utf-8'))
            m['index_version']=999
            p.write_text(json.dumps(m),encoding='utf-8')
            with self.assertRaisesRegex(EMSDataError,'rebuild'):
                ensure_index(copied)

    def test_source_refresh_rebuilds_derived_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            copied=Path(tmp)/'data'
            shutil.copytree(self.data,copied)
            before=json.loads((copied/'search_current.json').read_text(encoding='utf-8'))
            base=prepare(copied,self.source,refresh=True)
            result=ensure_index(copied)
            self.assertEqual(result['action'],'prepared')
            self.assertNotEqual(before['source_run_id'],result['manifest']['source_run_id'])
            self.assertEqual(result['manifest']['source_run_id'],base['manifest']['run_id'])

    def test_analyzer_is_reused_and_lemma_options_bounded(self):
        self.assertIs(analyzer(),analyzer())
        a=analyzer().analyze('Tee on laual.')
        for token in a.tokens:
            self.assertEqual(token.lemma,token.options[0] if token.options else token.surface)
        self.assertEqual(key(['a b','c']), '["a b","c"]')
        self.assertNotEqual(key(['a b','c']),key(['a','b c']))


if __name__=='__main__':
    unittest.main()
