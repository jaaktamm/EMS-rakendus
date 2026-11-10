# Väike termini-esinemiste arenduskogum

`cases.json` sisaldab 13 assistendi koostatud sünteetilist juhtumit ja 15 oodatud termini-esinemist (EMS ID + algteksti tähevahemik). Juhtumid vaadati selles tööetapis ükshaaval üle ja kontrolliti EMS-i põhinimetuste/sünonüümide vastu. See ei ole sõltumatu inimannotatsioon, juhuslik valim ega kullastandard. Järjestuse kaale ja lemmatiseerimisreeglit ei kohandatud nende tulemuste järgi.

Juhtumid katavad algkuju, käändevormi, sünonüümi, käänatud sünonüümi, mitmesõnalise termini, stoppsõna fraasis, lausepiiri, korduva mõiste eri algkujud, liitsõna, Unicode NFD, tundmatu sõna ja tegusõna/nimisõna mitmetähenduslikkuse. `Saavad.` on teadlik negatiivne morfoloogiajuhtum: see ei tähenda toiduainet „sai”, kuigi sama lemmavõti võib anda selle eksliku vaste. Seda viga ei muudeta annotatsioonis õigeks vastuseks.

Esimese ülevaatuse käigus täpsustati pesastatud fraasi annotatsiooni: „Loomuliku keele töötlust” sisaldab lisaks `EMS145464` terminile ka EMS-i terminit `EMS010646` „loomulik keel” vahemikus „Loomuliku keele”. Termini-esinemiste hindamisel on mõlemad kehtivad; spetsiifilisema dokumenditeema hindamisel võiks eelistada pikemat. Sellest täpsustusest ei järeldu reeglite muutmist ega sõltumatut annotatsiooni. Lõplik fail ja selle SHA-256 on hindamisaruandega seotud.

Võrdlus kasutab samu lõplikke juhtumeid ja kuni 50 tulemust kõigi kolme strateegia puhul:

1. `surface`: eelistatud nimetuste normaliseeritud algkujud.
2. `lemma`: eelistatud nimetuste algkujud ja lemmafraasid.
3. `lemma-synonyms`: algkujud ja lemmafraasid koos eestikeelsete sünonüümidega.

TP/FP/FN arvutatakse mõiste ID ja esinemiskoha ühise võtme järgi, mitte üksnes tulemuste nimekirja pikkuse järgi. Kahe sama mõiste esinemise leidmine loetakse kaheks õigeks esinemiseks. Võrreldakse esiletõstmise nihkeid algtekstis, sh NFD kujul. Kogum on piisavalt väike, et tulemuste tõendite piir (5 ühe mõiste kohta) ja 50 tulemuse ülempiir ei kärbi hindamist.

`topic_probe` on eraldi kvalitatiivne näide. Illustratiivne „Raamatukoguteenused” ei ole inimese kinnitatud teema ega oodatud otsene termin. Sellele ei arvutata precision/recall väärtusi. Väljund näitab, millised terminid leiti ja kus võivad morfoloogilised seosed eksida; see ei mõõda dokumendi põhiteemade tuvastamise headust.

Käivitus projekti juurkaustast:

```powershell
.\.venv-stage1\Scripts\python -m examples.evaluate_stage5
```

Tulemused on `reports/etapp5_evaluation.json`; kõik üksikjuhtumite ennustused ja oodatud vahemikud jäävad kontrollitavaks.
