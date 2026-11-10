"""Transparent direct-match ranking; related concepts never become text matches."""
from collections import defaultdict
import math

PHRASE_BONUS_PER_TOKEN = 3
MAX_EXTRA_TOKENS = 7
FREQUENCY_BONUS_PER_DOUBLING = 6
MAX_FREQUENCY_DOUBLINGS = 5
POS_MATCH_BONUS = 2
POS_CONFLICT_PENALTY = 2
UNCERTAIN_FREQUENCY_WEIGHT = 0.5
CONTEXTLESS_FUNCTION_POS = {'J','K','D','P'}


def pos_assessment(query_pos, label_pos, enabled=True):
    """Compare aligned, disambiguated POS readings conservatively."""
    if not enabled:
        return 'unavailable',0,1.0
    if not query_pos or not label_pos or len(query_pos)!=len(label_pos):
        return 'uncertain',0,UNCERTAIN_FREQUENCY_WEIGHT
    if len(label_pos)==1 and label_pos[0] and set(label_pos[0]).issubset(CONTEXTLESS_FUNCTION_POS):
        # An isolated EMS label such as "või" has too little context for a
        # reliable POS verdict; do not punish a noun use in the input.
        return 'uncertain',0,UNCERTAIN_FREQUENCY_WEIGHT
    if any(len(q)!=1 or len(l)!=1 for q,l in zip(query_pos,label_pos)):
        return 'uncertain',0,UNCERTAIN_FREQUENCY_WEIGHT
    if all(q[0]==l[0] for q,l in zip(query_pos,label_pos)):
        return 'match',POS_MATCH_BONUS,1.0
    return 'conflict',-POS_CONFLICT_PENALTY,UNCERTAIN_FREQUENCY_WEIGHT


def contained_spans(spans):
    covered = set()
    furthest = {}
    for sentence, start, end in sorted(set(spans),key=lambda x:(x[0],x[1],-x[2])):
        if furthest.get(sentence,-1) >= end:
            covered.add((sentence,start,end))
        furthest[sentence]=max(end,furthest.get(sentence,-1))
    return covered


def rank(matches, occurrences, pos_scoring=True):
    evidence = {}
    for match in matches:
        for occurrence in occurrences[(match['kind'],match['match_key'])]:
            item={k:v for k,v in occurrence.items() if not k.startswith('_')}
            item.update(label_id=match['label_id'],matched_label=match['original_text'],
                        role=match['role'],match_type=match['kind'],token_count=match['token_count'])
            status,delta,weight=pos_assessment(occurrence.get('_pos_options',()),
                                               match.get('pos_options') or [],pos_scoring)
            item.update(pos_status=status,pos_delta=delta,pos_frequency_weight=weight)
            identity=(match['ems_id'],item['sentence_id'],item['start'],item['end'])
            previous=evidence.get(identity)
            status_order={'match':2,'uncertain':1,'unavailable':1,'conflict':0}
            preference=lambda v:(v['match_type']=='exact',v['role']=='preferred',
                                 status_order[v['pos_status']],-v['label_id'])
            if previous is None or preference(item)>preference(previous):
                evidence[identity]=item
    groups=defaultdict(list)
    for (ems_id,_,__,___),item in evidence.items():
        groups[ems_id].append(item)
    # Count an overlapping short and long label of one concept only once.
    for ems_id,items in groups.items():
        covered=contained_spans((x['sentence_id'],x['start'],x['end']) for x in items)
        groups[ems_id]=[x for x in items if (x['sentence_id'],x['start'],x['end']) not in covered]
    global_covered=contained_spans((x['sentence_id'],x['start'],x['end']) for items in groups.values() for x in items)
    result=[]
    suppressed=0
    for ems_id,items in groups.items():
        uncovered=[x for x in items if (x['sentence_id'],x['start'],x['end']) not in global_covered]
        if not uncovered and all(x['token_count']==1 for x in items):
            suppressed+=1
            continue
        # Prefer the strongest individual evidence; capped frequency is separate.
        def base(item):
            return ((100 if item['match_type']=='exact' else 80)
                    +(8 if item['role']=='preferred' else 0)
                    +PHRASE_BONUS_PER_TOKEN*min(MAX_EXTRA_TOKENS,item['token_count']-1))
        best=max(items,key=lambda x:(base(x),-x['start'],-x['label_id']))
        frequency=len(items)
        effective_frequency=round(sum(x['pos_frequency_weight'] for x in items),3)
        bonus=round(FREQUENCY_BONUS_PER_DOUBLING*min(MAX_FREQUENCY_DOUBLINGS,math.log2(effective_frequency+1)),3)
        penalty=20 if not uncovered else 0
        pos_correction=round(sum(x['pos_delta'] for x in items)/frequency,3)
        score=round(base(best)+bonus+pos_correction-penalty,3)
        pos_counts={status:sum(x['pos_status']==status for x in items)
                    for status in ('match','uncertain','conflict','unavailable')}
        reasons=[f"{'Täpne algkuju' if best['match_type']=='exact' else 'Lemmafraas'}: {100 if best['match_type']=='exact' else 80}",
                 f"{'Eelistatud nimetus' if best['role']=='preferred' else 'Sünonüüm'}: {8 if best['role']=='preferred' else 0}",
                 f"Fraasipikkus {best['token_count']}: {PHRASE_BONUS_PER_TOKEN*min(MAX_EXTRA_TOKENS,best['token_count']-1)}",
                 f'POS: sobiv {pos_counts["match"]}, ebakindel {pos_counts["uncertain"]}, vastuolu {pos_counts["conflict"]}; korrektsioon {pos_correction:+g}',
                 f'Sagedus {frequency} (kaalutud {effective_frequency:g}), logaritmiline boonus (piir 30): {bonus}']
        if penalty:
            reasons.append('Kõik vasted pikemate fraaside sees: -20')
        result.append(dict(ems_id=ems_id,score=score,score_explanation='; '.join(reasons),
                           match_type=best['match_type'],matched_label=best['matched_label'],
                           matched_text=best['text'],frequency=frequency,
                           effective_frequency=effective_frequency,pos_correction=pos_correction,
                           pos_confidence=pos_counts,
                           evidence=sorted(items,key=lambda x:(-base(x),x['start']))))
    result.sort(key=lambda x:(-x['score'],x['ems_id']))
    return result,suppressed
