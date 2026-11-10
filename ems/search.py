"""Sentence-local candidates, one batch join, shared detail queries, no text storage."""
from collections import defaultdict
from contextlib import contextmanager
import json
import os
from pathlib import Path
import time

import duckdb

from .linguistics import analyzer, key
from .ranking import rank
from .search_index import attach, ensure_index, index_current
from .storage import EMSDataError, current, data_lock
from .validation import rows

STRATEGIES=('surface','lemma','lemma-synonyms')
MAX_CANDIDATES=2_000_000
# Only reject an unambiguous conjunction as a standalone keyword. Other POS
# values and unresolved cases stay eligible; conjunctions inside phrases stay.
STANDALONE_FUNCTION_POS={'J'}

def validate_text(text):
    maximum=int(os.environ.get('EMS_MAX_INPUT_BYTES','5242880'))
    if not isinstance(text,str) or not text.strip():
        raise EMSDataError('Sisendtekst on tühi.')
    if len(text.encode('utf-8'))>maximum:
        raise EMSDataError(f'Sisend ületab lubatud UTF-8 mahu ({maximum} baiti).')


def read_text_file(path):
    maximum=int(os.environ.get('EMS_MAX_INPUT_BYTES','5242880'))
    with Path(path).open('rb') as stream:
        data=stream.read(maximum+1)
    if len(data)>maximum:
        raise EMSDataError(f'Fail ületab lubatud mahu ({maximum} baiti).')
    try:
        text=data.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise EMSDataError('Fail peab olema UTF-8 või UTF-8 BOM kodeeringus.') from exc
    validate_text(text)
    return text


def check_limit(limit):
    if not isinstance(limit,int) or not 1<=limit<=50:
        raise EMSDataError('Tulemuste ülempiir peab olema 1 kuni 50.')


def candidates(analysis,lengths,use_lemmas=True):
    occurrences=defaultdict(list)
    window_count=0
    pos_filtered_count=0
    for sentence_id,tokens in enumerate(analysis.sentences):
        surfaces=[t.surface for t in tokens]
        lemmas=[t.lemma for t in tokens]
        for length in lengths:
            for start in range(len(tokens)-length+1):
                end=start+length
                if not tokens[start].lexical or not tokens[end-1].lexical:
                    continue
                window_count+=1
                if window_count>MAX_CANDIDATES:
                    raise EMSDataError('Liiga palju fraasikandidaate; lühenda sisendit.')
                if (length==1 and tokens[start].pos_options
                        and set(tokens[start].pos_options).issubset(STANDALONE_FUNCTION_POS)):
                    pos_filtered_count+=1
                    continue
                occurrence=dict(sentence_id=sentence_id,start=tokens[start].start,end=tokens[end-1].end,
                                _pos_options=tuple(t.pos_options for t in tokens[start:end]))
                occurrences[('exact',key(surfaces[start:end]))].append(occurrence)
                if use_lemmas:
                    occurrences[('lemma',key(lemmas[start:end]))].append(occurrence)
    return occurrences,window_count,pos_filtered_count


def match_sql(strategy):
    roles="('preferred','alternative')" if strategy=='lemma-synonyms' else "('preferred')"
    fields='k.kind,k.match_key,s.label_id,s.ems_id,s.original_text,s.role,s.language,s.token_count,s.pos_options'
    sql=f'''SELECT {fields} FROM candidate_keys k JOIN idx.search_label s
            ON k.match_key=s.surface_key WHERE k.kind='exact' AND s.language='et' AND s.role IN {roles}'''
    if strategy!='surface':
        sql+=f''' UNION ALL SELECT {fields} FROM candidate_keys k JOIN idx.search_label s
            ON k.match_key=s.lemma_key WHERE k.kind='lemma' AND s.language='et' AND s.role IN {roles}'''
    return sql


class SearchEngine:
    def __init__(self,connection,manifest):
        self.c=connection
        self.manifest=manifest
        self.lengths=[r[0] for r in connection.execute("SELECT DISTINCT token_count FROM idx.search_label WHERE language='et' ORDER BY 1").fetchall()]

    def _details(self,ids):
        if not ids:
            return {}
        details={r['ems_id']:dict(r,relations=[],domains=[]) for r in rows(self.c, '''
            SELECT c.ems_id,l.text AS preferred_label,c.concept_type,c.uri
            FROM core.concept c JOIN core.label l ON l.label_id=c.preferred_label_id
            WHERE c.ems_id IN (SELECT unnest(?::VARCHAR[]))''', [ids])}
        # Array arguments are bound, never interpolated, in both shared queries.
        relation_cursor=self.c.execute('''SELECT r.ems_id,r.kind,r.target_id,r.target_label_raw,
                t.text AS target_preferred_label,coalesce(c.uri,r.target_uri_raw) AS uri,r.resolution,
                count(*) OVER(PARTITION BY r.ems_id,r.kind) AS kind_total
            FROM core.relation r LEFT JOIN core.concept c ON c.ems_id=r.target_id
            LEFT JOIN core.label t ON t.label_id=c.preferred_label_id
            WHERE r.ems_id IN (SELECT unnest(?::VARCHAR[]))
            QUALIFY row_number() OVER(PARTITION BY r.ems_id,r.kind ORDER BY r.target_id,r.relation_id)<=5
            ORDER BY r.ems_id,r.kind,r.target_id''',[ids])
        names=[x[0] for x in relation_cursor.description]
        for row in relation_cursor.fetchall():
            item=dict(zip(names,row))
            details[item.pop('ems_id')]['relations'].append(item)
        for ems_id,code in self.c.execute('''SELECT DISTINCT ems_id,domain_code FROM core.concept_domain
            WHERE ems_id IN (SELECT unnest(?::VARCHAR[])) ORDER BY 1,2''',[ids]).fetchall():
            details[ems_id]['domains'].append(code)
        return details

    def keywords(self,text,limit=10,strategy='lemma-synonyms',explain=False):
        validate_text(text)
        check_limit(limit)
        if strategy not in STRATEGIES:
            raise EMSDataError('Tundmatu sobitamisstrateegia.')
        begin=time.perf_counter()
        a=analyzer().analyze(text,morphology=strategy!='surface')
        after_analysis=time.perf_counter()
        occurrences,window_count,pos_filtered_count=candidates(a,self.lengths,strategy!='surface')
        # Keep original positions/frequencies in Python, bind each distinct key once.
        keys=list(occurrences)
        after_candidates=time.perf_counter()
        self.c.execute('''CREATE OR REPLACE TEMP TABLE candidate_keys AS
            SELECT unnest(?::VARCHAR[]) AS kind,unnest(?::VARCHAR[]) AS match_key''',
            [[k[0] for k in keys],[k[1] for k in keys]])
        sql=match_sql(strategy)
        matches=rows(self.c,sql)
        after_match=time.perf_counter()
        for values in occurrences.values():
            for item in values:
                item['text']=text[item['start']:item['end']]
        ranked,suppressed=rank(matches,occurrences,pos_scoring=strategy!='surface')
        selected=ranked[:limit]
        after_rank=time.perf_counter()
        details=self._details([item['ems_id'] for item in selected])
        for item in selected:
            item.update(details[item['ems_id']])
            item['evidence_total']=len(item['evidence'])
            item['evidence']=item['evidence'][:5]
            for evidence in item['evidence']:
                low=max(0,evidence['start']-70)
                high=min(len(text),evidence['end']+70)
                evidence.update(snippet=text[low:high],snippet_start=low,
                                highlight_start=evidence['start']-low,highlight_end=evidence['end']-low)
        end=time.perf_counter()
        result=dict(results=selected,strategy=strategy,limit=limit,
            explanation='Sõnastikupõhised otsesed vasted; skoor ei ole tõenäosus. LLM-i ei kasutata.',
            diagnostics=dict(sentences=len(a.sentences),tokens=len(a.tokens),ambiguous_tokens=a.ambiguous_tokens,
                fallback_tokens=a.fallback_tokens,candidate_occurrences=window_count,unique_keys=len(keys),
                pos_filtered_occurrences=pos_filtered_count,
                matched_label_keys=len(matches),suppressed_nested_concepts=suppressed,
                sql_calls=2+(3 if selected else 0)),
            timings=dict(analysis_seconds=after_analysis-begin,candidates_seconds=after_candidates-after_analysis,
                matching_seconds=after_match-after_candidates,ranking_seconds=after_rank-after_match,
                details_seconds=end-after_rank,total_seconds=end-begin))
        if explain:
            result['query_plan']=self.c.execute('EXPLAIN ANALYZE '+sql).fetchone()[1]
            result['diagnostics']['sql_calls']+=1
        return result

    def lookup(self,query,mode='all',language='all',limit=10):
        validate_text(query)
        check_limit(limit)
        if mode not in ('all','exact','lemma','prefix') or language not in ('all','et','en'):
            raise EMSDataError('Sobimatu otsingu liik või keel.')
        begin=time.perf_counter()
        use_morph=mode in ('all','lemma') and language!='en'
        a=analyzer().analyze(query,morphology=use_morph)
        if len(a.sentences)!=1:
            raise EMSDataError('Otsi ühe sõna või fraasiga, mitte mitme lausega.')
        tokens=a.tokens
        parameters=[key(t.surface for t in tokens),key(t.lemma for t in tokens) if use_morph else None,
                    ' '.join(t.surface for t in tokens),language,language,mode,mode,mode,limit]
        cursor=self.c.execute('''WITH found AS (
            SELECT *,CASE WHEN surface_key=$1 THEN 'exact'
                WHEN language='et' AND lemma_key=$2 THEN 'lemma' ELSE 'prefix' END AS match_type
            FROM idx.search_label WHERE ($4='all' OR language=$5) AND (
                ($6 IN ('all','exact') AND surface_key=$1) OR
                ($7 IN ('all','lemma') AND language='et' AND lemma_key=$2) OR
                ($8='prefix' AND starts_with(normalized,$3)))
        ), ranked AS (
            SELECT *,CASE match_type WHEN 'exact' THEN 0 WHEN 'lemma' THEN 1 ELSE 2 END AS match_order,
                CASE WHEN role='preferred' THEN 0 ELSE 1 END AS role_order FROM found)
        SELECT ems_id,label_id,original_text AS matched_label,language,role,match_type
        FROM ranked QUALIFY row_number() OVER(PARTITION BY ems_id ORDER BY match_order,role_order,label_id)=1
        ORDER BY match_order,role_order,length(normalized),ems_id LIMIT $9''',parameters)
        names=[x[0] for x in cursor.description]
        found=[dict(zip(names,r)) for r in cursor.fetchall()]
        details=self._details([r['ems_id'] for r in found])
        return {'query':query,'mode':mode,'language':language,
                'results':[{**r,**details[r['ems_id']]} for r in found],
                'total_seconds':time.perf_counter()-begin}


@contextmanager
def search_session(directory='data'):
    ensure_index(directory)
    with data_lock(directory) as root:
        base,generation=current(root)
        manifest,index_dir=index_current(root,base)
        with duckdb.connect() as c:
            c.execute("SET memory_limit='512MB'")
            c.execute('SET threads=2')
            attach(c,generation/'ems.duckdb','core')
            attach(c,index_dir/'search.duckdb','idx')
            yield SearchEngine(c,manifest)
