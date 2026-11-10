# EMS: etapi 1 kontroll, täpsustatud andmemudel ja teostusplaan

Kontroll tehtud 28.–29.10.2026. Töö piirdub tehnilise eeluuringuga. Rakendust, püsivat EMS-i andmebaasi, kogu EMS-i lemmatiseerimist ega veebiliidest ei ole ehitatud. `prompt.md` lõpeb pooleli sõnadega „kontrolli- ja jõ”; puuduvat lõppu ei ole oletatud nõudena.

## Otsused

- Andmehoidla: DuckDB 1.5.5; Python 3.11.9 töötab Windows AMD64 ja Linux AMD64 keskkonnas.
- XML-i import: voogpõhine Python `xml.etree.ElementTree.iterparse`. `webbed` katsetati mõlemas keskkonnas; vaikimisi SAX-režiim ei loe seda faili ning DOM-režiim muudab algandmeid. See täidab promptis lubatud varutee kasutamise tingimuse.
- Keeleanalüüs: EstNLTK ja estnltk-core 1.7.5, Vabamorf. Docker image peab sisaldama NLTK `punkt_tab` ressursse. Pärast nende paigaldamist läbis Linuxi katse kontrollid ilma võrguühenduseta.
- Üks protsess ja üks Uvicorni tööline; uuendamine peatatud veebiprotsessiga. Esimeses versioonis pole LLM-i ega embedding-mudelit.

## Tegelik allikas ja XML

Ametlikust [EMS-i ekspordist](https://ems.elnet.ee/temp/ems_marc_tais.xml) laaditi uus koopia. Selle kontrollsumma kattus kaustas juba olnud failiga. `stage1_source.json` sisaldab URL-i, UTC allalaadimisaega ja HTTP päiseid. Vastuse Content-Type oli `application/xml`; kogu kohalik fail parsiti edukalt.

- Suurus: **86 053 763 baiti**.
- SHA-256: `cc9bd08ab1a29a38d7d7e279b9ef051ea885ce5219ed5d42ae2cd8f5517e2081`.
- Juur: `collection`; vaikimisi nimeruum `http://www.loc.gov/MARC21/slim`.
- Deklareeritud `xsi`: `http://www.w3.org/2001/XMLSchema-instance`; `xsi:schemaLocation` osutab MARC21slim.xsd-le. Täielikku XSD-valideerimist ei tehtud.
- Kirje: `collection/record`; ID: `controlfield[@tag='001']`. ID on tekst, nt `EMS137472`. `003` on `ErEMS`; `024$0` sisaldab URI-d.
- Kirjeid **42 245**, puuduvaid ID-sid **0**, korduvaid ID-sid **0**. Igas kirjes on täpselt üks alljärgnev 1XX nimetus.

| Märksõnatüüp | Normitud nimetus | Kirjeid | Sünonüüm / ingliskeelne vaste | Seoseväli |
|---|---|---:|---|---|
| Aeg | `148$a` | 121 | `448$a` | `548` |
| Teema | `150$a` | 33 717 | `450$a` | `550` |
| Koht | `151$a` | 7 130 | `451$a` | `551` |
| Vorm/žanr | `155$a` | 1 277 | `455$a` | `555` |

4XX puhul määrab **teine indikaator** keele ja rolli: tühik tähendab selles ekspordis eestikeelset sünonüümi, `9` ingliskeelset vastet. `040$b=est` kirjeldab kataloogimiskeelt, mitte kõigi nimetuste keelt. Tühja indikaatorit ei tohi teisendada `NULL`-iks enne toorandmete säilitamist. Väljanumber tuleb säilitada ka siis, kui selle tüüp erineb kirje põhinimetuse tüübist.

| Nimetused | Arv |
|---|---:|
| Eesti normitud nimetused | 42 245 |
| Eesti sünonüümid: 450 / 451 / 455 | 19 922 / 3 497 / 591 |
| Eesti sünonüüme kokku | 24 010 |
| Inglise vasted: 448 / 450 / 451 / 455 | 121 / 47 184 / 8 358 / 1 694 |
| Inglise vasteid kokku | 57 357 |
| Kõiki nimetusvälju kokku | 123 612 |

Need on väljade esinemiste arvud, mitte kordumatute tekstide arvud. Sama tekst võib kuuluda mitmele mõistele või esineda sama mõiste juures eri rollides.

Seosed paiknevad **konkreetse 5XX välja sees**: `$a` on sihtnimetus, `$0` siht-URI ning `$w=g` laiem, `$w=h` kitsam, puuduva `$w` korral seotud mõiste. Kokku on 175 535 seosevälja: 548 — 215, 550 — 150 713, 551 — 19 226, 555 — 5 381. Kõigil neil on `$a` ja `$0`. Laiema viiteid on 50 542, kitsama viiteid 50 500 ja ilma `$w`-ta seoseid 74 493. **Lahendamata siht-ID-sid on 0.** Vastassuunaliste hierarhiaviidete arvud erinevad: vastastikkust ei tohi eeldada ega importimisel puuduvaid seoseid märkamatult juurde luua. Tsükleid, vastastikkust ja sihtnimetuste kooskõla ID-ga kontrollitakse etapis 2.

Valdkonnad on `072` (ind2 `7`), `$a` kood ja `$2=ems`. Esineb **48 eri koodi**, **57 024 kuuluvusvälja**; 12 332 kirjel kordub 072. Koodid `00`, `01` jne jäävad tekstiks. Valdkondade nimetusi XML ei sisalda: tabelis jääb nimetus esialgu tühjaks või lisatakse hiljem EMS-i veebiloendist eraldi päritoluga. Numbrite tähendusi ei tuletata märksõnadest.

Selgitus on `680$i` (12 329 välja), allikaviide `670$a` (11 423 välja). Neid ei kasutata automaatselt sünonüümidena. Toorkihis säilitatakse kõik väljad, sealhulgas 008 täpne sisu.

Eraldi äraviitekirjeid selles failis ei leitud: kõik kirjed sisaldavad üht 148/150/151/155 välja; 4XX nimetused kuuluvad normitud mõiste kirje sisse. Kõigi kirjete leaderi positsioon 05 on `n`; kustutatud staatust `d` ei esine. [EMS-i juhend](https://ems.elnet.ee/abi.php) kirjeldab veebis ka eraldi äraviiteid ja kustutatud kirjeid. Sellest ei järeldu nende XML-kuju selles ekspordis: see jäi vaatlemata. Tulevase tundmatu kirjetüübi puhul säilitatakse toorkirje ja lisatakse kontrollprobleem; seda ei muudeta oletuslikult tavaliseks mõisteks.

Kõigi kirjete 008 positsioon 09 on `a`. Korduvad väljad on tavapärased: näiteks 26 531 kirjel kordub 550 ning 16 314 kirjel 450. Alamväljade eraldi globaalsete loendite kokkupakkimine ei ole lubatav. Täielik väljade, alamväljade ja indikaatorite loendus ning näited on `stage1_xml_findings.json` failis.

## webbed: tegelik katse ja piirang

Kontrolliti [DuckDB laienduse kataloogi](https://duckdb.org/community_extensions/extensions/webbed) ja [webbed API kirjeldust](https://duckdb-webbed.readthedocs.io/en/latest/functions/file_reading.html). Paigaldus: `INSTALL webbed FROM community; LOAD webbed;`. DuckDB 1.5.5 jaoks laaditud laiendus raporteeris versiooni **`4b70396`** nii Windowsis kui Linuxis. Laienduse veebidokumentatsiooni versiooninumber ei asenda binaari tegelikku versiooni.

Tegeliku faili päring:

```sql
SELECT count(*)
FROM read_xml('ems_marc_tais.xml',
              record_element := 'record', all_varchar := true);
```

Tulemus mõlemas keskkonnas: `IO Error: SAX parsing error`. Sama viga tuli `DESCRIBE` ja esimese rea lugemise korral. Fail ise on Python XML-parseriga tervikuna loetav. Vea sisemist põhjust ei ole tõendatud.

DOM-variante prooviti samuti. `streaming := false` üksi põrkub 16 MiB piiranguga. Koos `maximum_file_size := 100000000` õnnestub:

```sql
SELECT *
FROM read_xml('ems_marc_tais.xml', record_element := 'record',
              all_varchar := true, streaming := false,
              maximum_file_size := 100000000);
```

See tagastab 42 245 rida. Skeem sisaldab `leader VARCHAR`, `controlfield STRUCT(...)[]` ja `datafield STRUCT(tag, ind1, ind2, subfield STRUCT(...)[])[]`. Korduvate datafield- ja subfield-elementide kuuluvus säilib esimeses vaadeldud kirjes. Piirangud:

1. Esimese kirje 008 on XML-is 40 märki, tulemuses 34 märki: kuus lõputühikut kaovad ka `all_varchar := true` korral. MARC-i fikseeritud pikkusega välja jaoks on see andmete muutmine.
2. XML-i järjekord `001,072,072,003,008,...` jagatakse kaheks sõltumatuks controlfield/datafield loendiks. Väljade ühine algjärjekord ei ole sellest tulemusest taastatav.
3. DOM laeb suure dokumendi mällu. Üksik loenduspäring kestis Windowsis umbes 16,18 s ja Linuxis 15,21 s; need on eeluuringu üksikvaatlused, mitte jõudlusbenchmark ega mälukasutuse mõõtmine.

**Valik:** etapis 2 kasutada voogparserit, mis väljastab iga kirje kõik väljad ja alamväljad koos positsioonidega ning jätab teksti toorkihis kärpimata. Täielik algfail säilib baiditäpse allikana. `webbed` võib jääda diagnostikavahendiks; otsingu käitamine ei sõltu laienduse paigaldamisest. Teisi võimalikke webbed-i kaudu raw XML-i lugemise ja välise parsimise kombinatsioone ei ole ammendavalt välistatud, kuid need ei kõrvalda selle kontrollitud otsese imporditee puudusi.

Tõendid: `stage1_webbed_findings.json` (Windows), `stage1_webbed_linux.json`, `stage1_webbed_fidelity.json`. Katsekäsud on failides `stage1_webbed.py` ja `stage1_webbed_fidelity.py`.

## Sõltuvuste ühilduvus

Katsekeskkonnad: Windows Python **3.11.9** eraldatud `.venv-stage1` keskkonnas ning Docker `python:3.11.9-slim`, Linux AMD64, glibc 2.36. Image digest: `sha256:8fb099199b9f2d70342674bd9dbccd3ed03a258f26bbd1d556822c6dfc60c317`. ARM64, muud Pythoni versioonid ja Alpine/musl jäid kontrollimata. Esialgseks rakenduseks valida sama Debian-põhine platvorm.

| Pakett | Kontrollitud versioon |
|---|---|
| duckdb | 1.5.5 |
| estnltk / estnltk-core | 1.7.5 / 1.7.5 |
| fastapi / starlette | 0.162.0 / 1.10.0 |
| pydantic | 2.14.1 |
| uvicorn | 0.54.0 |
| jinja2 | 3.1.6 |
| python-multipart | 0.0.32 |
| httpx (katseks) | 0.28.1 |
| nltk / numpy / pandas | 3.10.4 / 2.4.6 / 3.1.0 |

Otsevalikud: `stage1-requirements.txt`; täielikud lahendatud sõltuvused: `stage1-requirements-windows.lock.txt` ja `stage1-requirements-linux.lock.txt`. Need on etapi 1 keskkonnalukud, mitte veel hashidega tootmispaigalduse lukud. Mõlemas keskkonnas andis `pip check` tulemuse `No broken requirements found`.

Käivitati `stage1_environment.py`: EstNLTK `Text(...).tag_layer(['morph_analysis'])`, DuckDB tekst-ID ja `VARCHAR[]` salvestus mälubaasi, FastAPI multipart-vormi ja UTF-8 faili saatmine TestClientiga ning Jinja HTML-pao kontroll. Näiteks `raamatuid → raamat`, `raamatukogudes → raamatukogu`, `vanad → vana`; algteksti positsioonid säilivad. See kinnitab põhiteekide koostööd, mitte veel otsingu kvaliteeti ega kogu rakenduse valmisolekut.

Puhas Linuxi keskkond **ei töötanud alguses offline**: puudus `tokenizers/punkt_tab/estonian`. Paigaldati `python -m nltk.downloader -d /usr/local/share/nltk_data punkt_tab`, katkestati konteineri võrguühendus ning käivitati sama kontroll edukalt uuesti. Järelikult tuleb see ressurss image'i ehitamise ajal alla laadida ja olemasolu kontrollida. Vabamorfi põhiressursid tulid selles kombinatsioonis paketiga kaasa; neural-paketti ei paigaldatud. Ressursi failide kontrollsummad tuleb tootmise build-manifestis samuti fikseerida.

Starlette väljastab hoiatuse, et httpx kasutamine TestClientiga on aegunud ning eelistatud on httpx2. Katse töötab; hoiatus puudutab testiklienti. Järgmisel etapil tuleb enne testikomplekti lõplikku lukustamist valida ja kontrollida uus testikliendi sõltuvus või jääda ajutiselt dokumenteeritud töötava kombinatsiooni juurde.

Kontrollitud allikad: [EstNLTK ametlik repositoorium](https://github.com/estnltk/estnltk), [paketi metaandmed](https://pypi.org/project/estnltk/), paigaldatud 1.7.5 lähtekoodi `default_resolver.make_resolver` signatuur ning [FastAPI vormide ja failide dokumentatsioon](https://fastapi.tiangolo.com/tutorial/request-forms-and-files/). EstNLTK resolver toetab `disambiguate`, `guess`, `propername` jm seadeid; tegelik lihtkatse tehti vaikeseadetega. Vabamorfi mitmene analüüs võib alles jääda ka pärast ühestamist: näites oli `on` kohta kaks sama lemma `olema` analüüsi.

## Täpsustatud andmemudel (kavand, mitte veel loodud skeem)

Kõik EMS-i ID-d, valdkonnakoodid, tag'id ja alamväljakoodid on `VARCHAR`. Järjekorranumbrid on täisarvud. Viited ei asenda toor-URI-sid. ID-de puudumist/kordumist peab saama toorkihis kirjeldada enne semantilise kihi piirangute rakendamist.

| Tabel | Põhiväljad ja seosed |
|---|---|
| `source_snapshot` | `snapshot_id` PK, URL, allalaadimisaeg UTC, SHA-256, baidid, failitee, HTTP metadata |
| `processing_run` | `run_id` PK, snapshot FK, skeemi/importija/normaliseerija versioonid, paketid ja ressursid, algus/lõpp, olek, kontrolli kokkuvõte |
| `marc_record` | `record_pk` PK, run FK, kirje järjekord failis, `ems_id_raw` nullable, leader täistekst, tuvastatud staatus ja kirjetüüp. EMS-ID ei ole siin ainus võti |
| `marc_field` | `field_id` PK, record FK, `field_pos`, liik (leader/control/data), tag, ind1, ind2, kontrollvälja täistekst. `UNIQUE(record_pk, field_pos)` |
| `marc_subfield` | field FK, `subfield_pos`, code, tekst. PK `(field_id, subfield_pos)`. Puudumine erineb tühjast väärtusest |
| `concept` | `ems_id` PK, record FK, preferred label FK, tüüp (temporal/topical/geographic/genre_form), URI, staatus. Üks rida aktsepteeritud mõiste kohta |
| `label` | `label_id` PK, concept FK, source field FK, täistekst, keel `et/en/und`, roll preferred/alternative/english_equivalent, algne MARC tag. Samanimelisi ridu ei kirjutata üle |
| `relation` | `relation_id` PK, lähteconcept FK, source field FK, broad/narrow/related/unknown, raw `$w`, siht-URI raw, tuletatud `target_id_raw`, lahendatud target FK nullable, sihtnimetus raw, lahendusolek |
| `domain` | `domain_code` PK, scheme, nimetus nullable, nimetuse allika metadata nullable |
| `concept_domain` | concept FK, domain FK, source field FK. Üks rida lähtevälja kohta; eraldi DISTINCT-vaade loogilisteks kuuluvusteks |
| `concept_note` | note PK, concept FK, source field FK, liik scope/source/other, tekst. Toorvälja alamväljad jäävad eraldi alles |
| `redirect` | reserveeritud eraldi äraviitekirjetele: source record FK, lähtenimetus, siht-ID/URI raw, resolved target FK nullable, tõend ja olek. Praegusest ekspordist 0 rida; tundmatu esitus läheb kontrolli, mitte oletuslikku teisendusse |
| `search_label` | label FK, concept FK, originaaltekst, keel ja roll, normaliseeritud algkuju, `lemmas VARCHAR[]`, üheselt serialiseeritud lemmavõti, tokenite arv, normaliseerija versioon ja analüüsi hoiatus. PK label ID (esialgu üks deterministlik lemmajada) |
| `validation_issue` | issue PK, run FK, raskus, kood, record/field FK nullable, detailid, raw sihtviide. Säilitab lahendamata seosed ja äraviited ning välistamise põhjused |

Toorkiht säilitab tühikud ja kõik positsioonid. XML-prefiksite kirjapildi ja atribuutide baitjärjekorra taastamise allikas on säilitatud XML-fail; parseri taasseriaalimine ei ole baiditäpne koopia. Otsingu tuletatud kihis on normaliseerimine lubatud.

`label.normalized` ega `search_label.lemma_key` **ei ole UNIQUE**. Lemmajada võti moodustada näiteks kompaktse JSON-stringina (`ensure_ascii=False`), mitte mitmetähendusliku eraldajaga liitmisena. Iga semantiline rida viitab algväljale. Ühe seose `$w/$a/$0` võetakse alati sama field_id alt. Andmebaas sisaldab korraga üht aktiivset töötlust; varasemad tervikversioonid jäävad vajadusel eraldi failidena.

Kasutaja teksti esinemiskohad on päringu mälustruktuuris: sentence ID, algsed start/end nihked, label/concept ID, vasteliik ja esinemiste loend. Kasutaja tekste ega katkendeid püsitabelitesse vaikimisi ei salvestata.

## Teostusplaan järgmiseks tööks

**Etapp 2 — import ja kontroll.** Luua eraldi `prepare`, `refresh`, `validate` käsud. Allalaadimisel ühendus-/lugemisajalõpp, kuni kolm katset, ajutine fail, XML-juure/nimeruumi ja kirjete kontroll ning SHA-256 manifest. Importida `iterparse` abil partiidena ajutisse DuckDB faili; vabastada töödeldud XML-elemendid. Säilitada väljade ja alamväljade järjekord ning puutumatu toortekst. Tundmatud keeled, staatuse-/viitetüübid ja puuduvad vajalikud alamväljad lähevad kontrollaruandesse.

Etapi vastuvõtt: lähte- ja toorkirjete arv kattub; praeguse snapshoti korral 42 245 mõistet ja 123 612 nimetusvälja; ID-de unikaalsus, URI-de kooskõla, kõik sihtviited, puuduvad/korduvad alamväljad, valdkonnad, hierarhia vastassuunad ja tsüklid on kontrollitud. Võrrelda mitut kirjet XML-iga, sh ajamärksõna, inglise vaste ja korduvad seosed. Lubamatud vead takistavad aktiveerimist. Alles pärast kontrolli sulgeda ühendused ja asendada valmis DB samal andmemahul atomaarse failivahetusega. Nurjumisel säilib vana DB; valmis DB käivitamisel võrku ei kasutata. Ühildumatu töötlemisversioon annab taastamisjuhise, mitte vaikset automaatset rebuild'i.

**Etapp 3 — keeletöötlus ja otsing.** Ühine NFC + casefold normaliseerimine tokenite peal, üks protsessis taaskasutatav EstNLTK resolver. Tekst analüüsida algkujul, nihked võtta algtekstist; normaliseerimist ei tehta nii, et algteksti positsioonid muutuvad. EMS-i eestikeelsed nimetused töödelda üks kord, inglise omad ainult algkujupõhisesse otsingusse. Esialgu kasutada ühestatud analüüside kordumatute lemmade hulgast deterministlikult esimest; dokumenteerida sortimisreegel, puuduv analüüs ja allesjäänud mitmesus. Säilitada analüüsialternatiivid diagnostikaks. See piiratud valik võib vasteid kaotada; mõõta seda hindamiskogumil, mitte genereerida kõiki kombinatsioone.

Fraasikandidaadid moodustada lausesiseselt ainult andmestikus tegelikult esinevate tokenipikkuste järgi; stoppsõnu enne seda mitte eemaldada, liitsõnu mitte lõhkuda. Kandidatuuride kordumatud algkuju-/lemmavõtmed viia ühe ajutise tabelina DuckDB-sse. Teha partiiliitmised, säilitades kõik sama võtme mõisted; detailid tuua ühispäringutega. Kontrollida `EXPLAIN ANALYZE`; indekseid lisada vaid mõõdetud vajadusel. Käsitsi otsingus täpne algkuju, lemmafraas ja piiratud prefiksiotsing, igaühel nähtav vasteliik.

Järjestus: täpne vaste enne lemmafraasi, eelistatud nimetus enne sünonüümi, pikema täieliku fraasi eelis kattuva üksiksõna ees, piiratud sagedusboonus ning stabiilne ID-põhine viikide lahendus. Koondada sama mõiste vasted, säilitada põhjendus ja algteksti katkendid. Seotud mõisted jäävad lisainfoks. Skoor ei ole tõenäosus. Esialgne maksimum 10, seadistatav kuni 50; nõrku vasteid täiteks ei lisata.

**Etapp 4 — liides ja Docker.** FastAPI lifespan kontrollib lokaalset manifesti ning alustab vajadusel ettevalmistust. Keeleanalüüs laaditakse üks kord; CPU-töö ja DuckDB ühenduste kasutus serialiseeritakse esimeses versioonis, et mitu HTTP-päringut ei kasutaks sama ühendust korraga. Kaks eestikeelset HTML-vaadet, Jinja autoescape, UTF-8/UTF-8 BOM failid, tekstikasti ja faili vastastikune välistamine. Esialgne seadistatav piir 1 MiB; vigased/tühjad sisendid saavad selge teate. Image'i ehitamisel lukustatud paketid ja punkt_tab; püsimahtu XML, DB ja manifest. Uvicorn üks tööline. Kontrollida esma- ja korduvkäivitust ning päringut ilma võrguta. `docker compose up --build` ja kohalik Python-käivitus dokumenteerida alles reaalselt toimivate käskudena.

**Etapp 5 — kvaliteet ja jõudlus.** Väiksed kohalikud XML-fixture'id katavad kordused, puuduva alamvälja, indikaatori 9, 148/448/548, lahendamata viite, tundmatu staatuse ja 008 tühikud. Otsingutestid katavad käänded, mitmesõnalisuse, lausepiiri, sama lemmavõtme mitu mõistet ja koondamise. Elutsüklitestid katavad DB taaskasutuse ning nurjunud uuenduse. Täisandmete integratsioonikontroll eraldi.

Luua käsitsi ülevaadatav hindamiskogum ja võrrelda algkuju, lemmat ning lemmat+sünonüüme; enda koostatud ootusi ei nimetata sõltumatuks kullastandardiks. 100/1000/10 000 sõna korral mõõta eraldi analüüs, kandidaadid, sobitamine ja koguaeg; esimene ja korduv päring, korduste arv, mediaan ja p95. Ettevalmistuses eraldi allalaadimine, import ja EMS-i lemmatiseerimine. Vajadusel võrrelda protsessi mälus fraasiindeksit sama sisendi ja kvaliteediga. README koondab ainult teostatud ja kontrollitud käitumise.

## Mis jäi lahtiseks

- webbed SAX-vea sisemine põhjus; DOM-i ja voogparseri tegelik tippmälukasutus.
- Eraldi äraviite- ja kustutatud kirjete XML-esitus, sest neid selles failis ei ole. Nende jaoks on vaja hiljem kontrollitud näidist; tänast importi see ei takista.
- Valdkondade nimede eraldi allikas, hierarhia terviklikkus, lemmavõtmete kokkulangevused ja morfoloogia kvaliteet täisandmetel.
- Kogu rakenduse offline-töö, DB failivahetus, sisendipiirid ja jõudlus on tulevaste etappide kontrollid. Etapi 1 offline-katse hõlmab sõltuvuste põhifunktsioone.
- Docker Compose'i rakendust ei loodud. Katsekonteiner on ajutine, mitte rakenduse juurutus.

**Peatumiskoht: etapp 1 valmis. Etappe 2–5 ei alustatud.**
