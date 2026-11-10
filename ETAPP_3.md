# Etapp 3: lemmatiseerimine, partiiviisiline otsing ja järjestamine

29.10.2026. Etapp 3 on realiseeritud olemasoleva etapi 2 alusbaasi peale. Veebiliidest ega Docker Compose'i rakendust ei tehtud.

## Valmis lahendus

- `ems/linguistics.py`: üks kord protsessi kohta loodav EstNLTK/Vabamorfi resolver, NFC ja casefold, tokenid/lemmad, laused ning algteksti positsioonikaart.
- `ems/search_index.py`: nimetuste püsiv ettevalmistus eraldi DuckDB otsingubaasi, lähteversiooni ja keeleressursside kontroll, atomaarne aktiveerimine ja taaskasutamine.
- `ems/search.py`: täpne/lemma-/prefiksiotsing, lausesisesed fraasikandidaadid, partiiliitmised ning ühised detailipäringud.
- `ems/ranking.py`: sama mõiste vastete koondamine, pikemate fraaside eelis, piiratud sagedusboonus ja skoori tekstiline põhjendus.
- Käsud `prepare-search`, `search`, `keywords`; UTF-8 teksti ja BOM-iga failide tugi, 1 MiB seadistatav sisendipiir ja 1–50 tulemuse piir.

Lähtebaas jäi muutmata. Tuletatud otsingubaas asub `data/search_indexes/<index_id>/search.duckdb`; aktiivne viit on `data/search_current.json`. Faili suurus on **12 070 912 baiti**. Ette valmistati **123 612 nimetust**: 42 245 eesti põhinimetust, 24 010 eesti sünonüümi ja 57 357 ingliskeelset vastet. Inglise lemmaväljad on `NULL`.

Ettevalmistus kestis ühel Windowsi katsel **198,84 sekundit**, hõlmates sõnestamist/lemmatiseerimist, vaheandmete kirjutamist, DuckDB laadimist ja kontrolli. See ei ole ainult lemmatiseerija puhta arvutusaja mõõtmine. **2 927 nimetusel** on vähemalt üks diagnostiline hoiatus (mitmene analüüs, algkujule tagasilangemine või mitu lauset); neid ei visata ära. Tegelikud eestikeelsete nimetuste tokenipikkused on **1–10 ja 12**. Inglise nimetusi Vabamorfiga ei analüüsitud.

Metaandmed koos paketiversioonide, morfoloogia seadete ja kaheksa keeleressursi SHA-256 väärtustega: [etapp3_index_metadata.json](reports/etapp3_index_metadata.json). EstNLTK ja estnltk-core on 1.7.5, NLTK 3.10.4, DuckDB 1.5.5, Python 3.11.9. Runtime'i paigalduskäsud ja platvormipõhised versioonipiirangud on [README-s](README.md).

## Käsurealt kontrollitud näited

```powershell
.\.venv-stage1\Scripts\python -m ems prepare-search
.\.venv-stage1\Scripts\python -m ems search "raamatukogudes" --mode lemma
.\.venv-stage1\Scripts\python -m ems search "libraries" --mode exact --language en
.\.venv-stage1\Scripts\python -m ems keywords --file examples/morphology.txt --limit 5
.\.venv-stage1\Scripts\python -m ems keywords --file examples/synonyms.txt --limit 5
.\.venv-stage1\Scripts\python -m examples.check_stage3
```

| Kontroll | Tegelik tulemus |
|---|---|
| `raamatukogudes`, lemmaotsing | `EMS003867`, „raamatukogud”, `match_type=lemma` |
| `libraries`, inglise täpne otsing | sama `EMS003867`, „raamatukogud”, `match_type=exact` |
| `raamatu`, prefiksiotsing | muu hulgas „raamatud”, „raamatuhoid”, „raamatuturg” |
| `loomuliku keele töötlust` näidistekstis | `EMS145464`, „loomuliku keele töötlus”, lemmafraas |
| „Mandibula on alalõualuu. Alalõualuu …” | üks koondatud `EMS145598`, „alalõualuu”, sagedus 3 |
| „Eesti. Keel. Roheline. Majandus.” | lauseüleseid „eesti keel” ega „roheline majandus” vasteid ei lisata |
| `xyzqwerty` | null tulemust |

Kõik kaheksa tegelikku CLI-kutset koos skooride, põhjenduste, positsioonide, katkendite ja seoste lisainfoga on salvestatud [etapp3_examples.json](reports/etapp3_examples.json). Skript kasutab ainult repositooriumi sünteetilisi näidistekste. Need on arenduskontrollid, mitte sõltumatu kullastandard ega dokumenditeemade kvaliteedimõõtmine.

Sama sünonüümikatse puhul on koondatud ka eri nimetuste ja eri vasteliikide tõendid. Tulemuse parim tõend võib olla ametlik nimetus, kuid `evidence` loend sisaldab ka „Mandibula” kaudu leitud sünonüümivastet. Kasutaja teksti ei salvestata andmebaasi ega vaikimisi logidesse.

## Partiiviisilisus ja järjestus

Iga päring analüüsib teksti ühe tervikuna lause kontekstis. Fraasiaknaid moodustatakse ainult tegelike EMS-i tokenipikkuste järgi ja lause sees. Stoppsõnu ei eemaldata, liitsõnu ei lõhuta. Kordumatud algkuju- ja lemmavõtmed saadetakse kahe sama pikkusega massiivina DuckDB ajutisse tabelisse; positsioonid ja sagedused jäävad eraldi mälustruktuuri. Kaks võtmetüüpi liidetakse `UNION ALL` abil nimetustega. SQL-i ei käivitata iga sõna ega fraasi kohta.

Tulemuste korral tehakse **5 SQL-käsku**: kandidaatide ajutine tabel, ühine sobitamine ning kolm valitud mõistete detailide/seoste/valdkondade partiipäringut. Nullvaste korral tehakse kaks. Seansi avamise metaandme- ja fraasipikkuste kontrollid on eraldi käivituskulu. `--explain` lisab ühe diagnostilise käsu. Salvestatud `EXPLAIN ANALYZE` kasutab **HASH_JOIN** liitmisi. Otsinguvõtmetele indekseid ei lisatud; primaarvõti on nimetuse ID-l ja võtmekokkupõrked ei kirjuta ridu üle.

Skoor: algkuju 100 või lemma 80, eelistatud nimetus +8, lisatokeni eest +12 (kuni seitse lisatokenit), sagedusboonus kuni +12. Sagedusboonus on `3 × min(4, log2(sagedus+1))`. Sama mõiste sama tekstikoht on üks esinemine ka mitme nimetuse/vasteliigi korral. Pikem sama mõiste fraas koondab sisemise lühema; täielikult pikemate vastete sees olev üksiksõnamõiste jäetakse välja. Täielikult kaetud mitmesõnaline mõiste saab -20. Võrdse skoori lahendab EMS-i ID. Kõik komponendid on vastuses nähtavad; skoor ei ole protsent ega tõenäosus.

Laiemad, kitsamad ja seotud mõisted on eraldi `relations` väljal, mitte uute tekstivastetena. Jagatud URI-de korral säilivad lähtebaasi originaal-ID ja deklareeritud URI; neid ei samastata otsingus üheks mõisteks.

## Tegelikud mõõtmised

Käivitatud `python -m examples.benchmark_stage3 --runs 5`. Windows AMD64 / Python 3.11.9 / DuckDB 1.5.5, DuckDB piir 512 MiB ja kaks lõime. Kõigi kolme sisendi puhul viis päringut samas seansis. Sisend on korratud sünteetiline lausestik, mahuarvestus tühikutega eraldatud sõnade järgi; tokenite arv sisaldab kirjavahemärke ja on suurem. Failivahemälu ei tühjendatud ning masin polnud eraldatud võrdlusmasin; osa automaatkontrolle jooksis samal ajal. p95 on viie vaatluspunkti nearest-rank väärtus ehk maksimum.

| Sõnu | Esimene päring | Koguaeg, mediaan | Koguaeg, p95 | Sobitamine, mediaan | SQL-käske |
|---:|---:|---:|---:|---:|---:|
| 100 | 0,506 s | 0,202 s | 0,506 s | 0,0245 s | 5 |
| 1 000 | 0,829 s | 0,970 s | 1,146 s | 0,0243 s | 5 |
| 10 000 | 9,473 s | 8,260 s | 10,117 s | 0,0242 s | 5 |

Seansi avamine koos sõltuvuste/ressursside ja manifestide kontrolliga kestis 5,26 s. Analüsaatori esmane tegelik käivitumine kuulub 100 sõna esimese päringu aega; suuremate sisendite „esimene” päring kasutas juba laaditud analüsaatorit. 10 000 sõna mediaanist kulus analüüsile 7,62 s, kandidaatidele 0,367 s, sobitamisele 0,024 s, järjestamisele 0,094 s ning detailidele 0,095 s. Komponentide mediaanide summa ei pea võrduma kogukestuse mediaaniga.

10 000 sõna andis 34 543 fraasiakent, kuid korduva lausestiku tõttu ainult 75 kordumatut võtme/vaste-liigi paari. See näitab deduplitseerimise toimimist, mitte loomuliku mitmekesise korpuse halvima juhu jõudlust. Kuna sobitamise osa on väike, ei ehitatud alternatiivset protsessi mälus fraasiindeksit. Toorvaatlused, esimeste/korduvate päringute statistika, kõik etapid ja päringuplaan on [etapp3_benchmark.json](reports/etapp3_benchmark.json).

Samal raamatukogude näidisel võrdles skript kolme strateegiat: eelistatud nimetuste algkujupõhine leidmine andis 2 mõistet, lemma lisamine 8 ning sünonüümide lisamine samuti 8. Sellest ei järeldata, et sünonüümid on tarbetud: eraldi „Mandibula” näide ja sünonüümitest kinnitavad nende toimimist. Precision/recall väärtusi ega teemade tuvastamise täpsust neist enda koostatud näidetest ei arvutatud.

## Automaattestid ja offline-kontroll

Kokku **40 automaattesti** läbivad Windowsis: 21 imporditesti ja 19 otsingutesti. Linuxi võrguühenduseta katsekonteineris läbis esmalt 38 testi sisaldanud komplekt ja seejärel mõlemad lisatud testid. Kontrollitud on muu hulgas:

- käändevormid, sünonüüm → ametlik nimetus, sama algkuju/lemmavõtme mitu mõistet;
- mitmesõnaline termin, fraasi sees olev stoppsõna, liitsõna säilimine ja lausepiiri kaitse;
- sama mõiste koondamine, sagedusboonuse piir ning seotud mõiste eristamine tekstivastest;
- algteksti nihked ja esiletõstmise vahemik pärast NFC-teisendust koos lahutatud `Õ` ja emoji-kontekstiga;
- inglise nimetuste ainult algkujupõhine indeks, UTF-8 BOM, vigane kodeering, tühi/liiga suur sisend ja tulemuste piir;
- sama protsessianalüsaatori taaskasutus, valmis indeksi taaskasutus ilma uue analüüsita, ebaõnnestunud rebuild'i korral vana indeksi säilimine;
- lähteversiooni muutumisel uus tuletatud indeks ning ühildumatu töötlusversiooni korral selge rebuild'i nõue;
- 100 kordusega teksti korral konstantne SQL-käskude arv ja hash-liitmine.

Samuti avati **Windowsis loodud tegelik täisotsingubaas Linuxis ilma võrguühenduseta**, ilma ümberehituseta: `ensure_index()` tagastas `reused`, `libraries` leidis „raamatukogud” ning `Raamatukogudes.` andis sama mõiste lemmavaste. Tegemist oli ajutise testikonteineriga; rakenduse Docker image'i/Compose'i veel ei loodud.

## Piirangud ja järgmine peatumiskoht

Vabamorfi ühestamine võib jätta mitu lemmat. Pärast normaliseerimist valitakse neist leksikograafiliselt esimene, teised säilivad nimetuse diagnostikas; piiramatut kombinatsioonide laiendamist ei tehta. Lühikese EMS-i nimetuse kontekst ja dokumendi lausekontekst võivad anda eri lemma. Algkujupõhine tee jääb alles. See valik on deterministlik, kuid võib osa käändevastetest kaotada.

Otsene üldsõnavaste võib järjestuda erialaterminist ettepoole. Näiteks morfoloogia näites on „teadlased” ja „õpilased” täpsed nimetused; nende skoor võib ületada ühe sõna lemmavaste oma. Reeglid on selgitatavad, kuid ei ole veel käsitsi hinnatud dokumenditeemade mudel. Tõendite väljund piirdub viie katkendiga mõiste kohta; esinemissagedus arvestab kõiki koondatud kohti.

Keeleressursid peavad olema enne offline-kasutust olemas. Nende muutumine nõuab teadlikku otsingubaasi ümberehitust; uued resource hash'id ei käivita märkamatut vana indeksi kasutamist. Sõnaosaotsingut, suvalise sisu semantilist otsingut ega LLM-i ei lisatud.

Kontrollitud ametlikud API allikad: [EstNLTK resolver](https://github.com/estnltk/estnltk/blob/main/estnltk/estnltk/default_resolver.py) ja [Vabamorfi tagger](https://github.com/estnltk/estnltk/blob/main/estnltk/estnltk/taggers/standard/morph_analysis/morf.py); kasutatud parameetrid ja `Text.tag_layer(..., resolver=...)` kontrolliti ka paigaldatud 1.7.5 lähtekoodist ja tegeliku käivitusega.

**Etapp 3 on lõpetatud. Etappi 4 ei alustatud.**
