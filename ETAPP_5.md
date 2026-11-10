# Etapp 5: lÃµppkontroll, jÃµudlus ja dokumentatsiooni vastavus

29.10.2026. KÃµik viis etappi on lÃµpetatud. PÃµhijuhend on [README.md](README.md); seal on eraldi jaotised **„Andmemudel ja teisendus“**, **„Kontrollid ja pÃ¤ringud“** ning **„Lemmatiseerimine ja otsing kÃ¤surealt“**. See on Ã¼lesandes nÃµutud teisendamise, pÃ¤ringute ja kontrolli dokumentatsioon. Varasemad ETAPP_1â€“4 aruanded kirjeldavad nende etappide ajaloolisi kontrollkÃ¤ike, mitte kÃµiki lÃµppseisu mÃµÃµtmisi.

## Testide tulemused

Pärast POS-põhise skoorikorrektsiooni lisamist käivitati kogu testikomplekt uuesti: **56 testi läbisid**. Uus 10 000 sõna CLI päringumõõtmine andis mootoriaja mediaaniks 5,616 s, millest teksti analüüs võttis 4,341 s, kandidaadid 0,882 s, sobitamine 0,290 s ning järjestamine 0,071 s. See mõõdab uut järjestamist, kuid pole vana skooriga kontrollitud A/B-võrdlus. Kasutatud valem ja muudatuse detailid on allpool POS-jaotises ning README-s.

KÃ¤ivitatud kogu komplekt, kasutades `python -m examples.check_stage5`:

| Keskkond | Teste | LÃ¤bis | Vigu / lÃ¤bikukkumisi / vahele jÃ¤etud | SÃµltuvuste kontroll |
|---|---:|---:|---|---|
| Windows, Python 3.11.9 | 53 | 53 | 0 / 0 / 0 | `pip check` korras |
| Linux/WSL2 konteiner, Python 3.11.9 | 53 | 53 | 0 / 0 / 0 | `pip check` korras |
| TÃ¶Ã¶tav Docker/Uvicorni teenus, pÃ¤ris HTTP | 13 | 13 | 0 / 0 / 0 | eraldi integratsioonikontroll |

Masinloetavad testitulemused: [Windows](reports/etapp5_tests_windows.json), [Linux](reports/etapp5_tests_linux.json), [HTTP](reports/etapp5_http_checks.json). [Windowsi tÃ¤islogi](reports/etapp5_tests_windows.log) ja [Linuxi tÃ¤islogi](reports/etapp5_tests_linux.log) sisaldavad iga testi nime ja tulemust. Windowsi jooks kestis 28,96 s ja Linuxi jooks 30,28 s; need on kontrolli kestused, mitte eraldi platvormide kiirusvÃµrdlus.

Testid kasutavad vÃ¤ikseid kohalikke XML-e ja ei vaja kogu EMS-i allalaadimist. Katvus hÃµlmab korduvaid vÃ¤lju ja alamvÃ¤ljade jÃ¤rjekorda; puuduvat/korduvat ID-d ja kohustuslikku alamvÃ¤lja; indikaatoreid/keeli; sÃ¼nonÃ¼Ã¼me, kÃ¤Ã¤ndevorme, liitsÃµnu ja mitmesÃµnalisi termineid; lausepiire; sama vÃµtme mitut mÃµistet; tulemuste koondamist ja sageduse piiramist; NFD-nihkeid; vigast/tÃ¼hja/liiga suurt sisendit; baaside taaskasutust ja versioonikontrolli; nurjunud uuendamist/aktiveerimist; HTML-i paokoodimist ja privaatsust; jÃ¤rjestikust Ã¼henduse kasutust paralleelpÃ¤ringute korral ning kÃ¤ivituse/sulgemise lukku.

TestClienti lukustatud httpx/Starlette kombinatsioon vÃ¤ljastab aegumishoiatuse. See ei ole lÃ¤bikukkunud test ega tootmisserveri sÃµltuvusviga; tÃ¶Ã¶tav server ei kasuta TestClienti. SÃµltuvusi ei vahetatud uue kontrollimata versiooni vastu ainult hoiatuse eemaldamiseks.

## Uus tÃ¤isimport ja teisendamise kontroll

TÃ¶Ã¶tav teenus ja selle nimeline `/data` maht jÃ¤id alles. Uus ettevalmistus tehti eraldi `.stage5-preparation` kaustas Linuxi konteinerist Windowsi tÃ¶Ã¶kausta bind-mount'i kaudu. Tegelikult kasutati vÃ¤rsket allalaadimist, mitte kohaliku faili kopeerimist. MÃµÃµtmise kÃ¤sk oli:

```powershell
docker run --name ems-stage5-preparation -v C:/TextMining/Ylesanded/YL08_EMS:/work -w /work ems-local:stage4 python -m examples.preparation_stage5 --data-dir .stage5-preparation
```

Konteiner kasutas lukustatud image'i pakette ja `/work` alla seotud selle tÃ¶Ã¶ lÃµppkontrolli lÃ¤htekoodi. `examples/preparation_stage5.py` keeldub olemasoleva valmis baasi asendamisest. Katsekaust ei ole rakenduse aktiivne andmekaust; see on Gitist vÃ¤lja jÃ¤etud.

Allikas: `https://ems.elnet.ee/temp/ems_marc_tais.xml`, 86 053 763 baiti, SHA-256 `cc9bd08ab1a29a38d7d7e279b9ef051ea885ce5219ed5d42ae2cd8f5517e2081`. Kontrollsumma on sama mis varasemates etappides. KÃ¤ivitati aktiveerimiseelne kontroll ja pÃ¤rast baasi sulgemist veel sÃµltumatu `validate_current`.

| Kontroll | LÃµpptulemus |
|---|---:|
| XML-kirjeid / toorkirjeid / mÃµisteid | 42 245 / 42 245 / 42 245 |
| ToorvÃ¤lju / alamvÃ¤lju | 633 393 / 966 994 |
| Eesti pÃµhinimetusi / sÃ¼nonÃ¼Ã¼me | 42 245 / 24 010 |
| Inglise vasteid / kÃµiki nimetusi | 57 357 / 123 612 |
| Seoseid / lahendamata seoseid | 175 535 / 0 |
| Valdkondi / kuuluvusvÃ¤lju | 48 / 57 024 |
| Puuduvaid ID-sid / korduvaid ID-sid / vÃ¤listatud kirjeid | 0 / 0 / 0 |
| Rekonstrueeritud toorkirjeid / sisuerinevusi | 42 245 / 0 |

TÃ¤ielik vÃ¤rske [teisendamise kontrollaruanne](reports/etapp5_validation.json) sisaldab keelte/tÃ¼Ã¼pide jaotusi, indikaatoreid, vÃ¤ljade/alamvÃ¤ljade loendusi, valimkirjete vÃµrdlust, lahendamata viiteid ja vÃ¤listamise pÃµhjuseid. „SÃµltumatu“ tÃ¤hendab siin uut lugemist ja vÃµrdlust teises kontrollkÃ¤igus, mitte sÃµltumatut vÃ¤list hindajat ega teise parseriteegi kasutamist.

LÃ¤hteandmete eripÃ¤rad jÃ¤id samaks: 1 254 jagatud URI-paari, kaheksa tÃ¼hikutest koosnevat selgitust, kaks seosetÃ¼Ã¼bi erandit, 792 puuduva vastassuunaga hierarhiavÃ¤lja ning leitud tsÃ¼kli nÃ¤ide. Algkujusid ei parandata ega visata varjatult Ã¤ra. Eraldi Ã¤raviite- ja kustutatud kirjeid tegelikus failis ei esine; nende sÃ¤ilitamist/raporteerimist kontrollivad fixture-testid. TÃ¤ielikku XSD-valideerimist ei vÃ¤ideta.

## Ettevalmistuse ajad

Lisati tÃ¤psemad ajavÃ¤ljad, muutmata andmemudelit, otsingu vÃµtmeid ega lemmatiseerimisreegleid. Vana metaandmevorming on loetav; ainult uued ettevalmistused sisaldavad uusi eraldi ajavÃ¤lju.

| Osa | Aeg | Vaatlusi |
|---|---:|---:|
| Allalaadimine `.part` faili | 2,15 s | 1 |
| Allika hankimine koos juure/kontrollsumma kontrolliga | 4,92 s | 1 |
| XML-i parsimine, JSONL-vahekiht ja toortabelite laadimine | 165,75 s | 1 |
| Semantilised mÃµisted/nimetused/seosed ja impordihoiatused | 74,36 s | 1 |
| Aktiveerimiseelne tÃ¤iskontroll | 41,70 s | 1 |
| Eesti nimetuste keeleline eeltÃ¶Ã¶tlus | 163,94 s | 1 |
| Muukeelsete nimetuste sÃµnestamine | 76,12 s | 1 |
| Otsinguindeksi kogu ettevalmistus | 249,58 s | 1 |
| Kogu uus ettevalmistus | 538,00 s | 1 |
| TÃ¤iendav kordusvalideerimine (vÃ¤ljaspool eelmist koguaega) | 34,12 s | 1 |

Tabelis on ka Ã¼ksteist sisaldavad mÃµÃµdikud: allalaadimine sisaldub allika hankimises ning keeleline tÃ¶Ã¶tlus sisaldub indeksi koguajas. Neid ridu ei tohi kÃµiki kokku liita. Eesti tÃ¶Ã¶tluse mÃµÃµdik sisaldab NFC/sÃµnestamise/Vabamorfi ja lemmavÃµtme moodustamise aega, mitte ainult native Vabamorfi CPU-aega. Label-cache'i tegelikud tabamused kuuluvad reaalse ettevalmistustee kulu sisse. JSONL-i kirjutamine ja baasi laadimine on eraldi koguaja osad; English/und nimetustele Vabamorfi ei kutsuta.

Keskkond: Linux 6.6.87.2 WSL2, glibc 2.36, AMD Ryzen 5 PRO 4650U, 12 nÃ¤htavat loogilist CPU-d, ligikaudu 15,2 GiB VM-mÃ¤lu, konteineri eraldi mÃ¤lulimiit `max`; DuckDB 512 MB ja kaks lÃµime. Protsessi mÃµÃµdetud tipp pÃ¤rast ettevalmistust oli umbes **637 MiB** (Python ja teegid lisanduvad DuckDB mÃ¤lupiirile). See tipp loeti enne tÃ¤iendavat kordusvalideerimist.

Ainult Ã¼he tÃ¤isettevalmistuse pÃµhjal p95-d ei esitata. Windowsi bind-mount'i I/O erineb etapi 4 Docker native-nimelisest mahust; selle katse 538 s ja etapi 4 ligikaudu 364 s ei ole sama salvestuskeskkonna kiirusvÃµrdlus. KÃµik tÃ¤psed vÃ¤Ã¤rtused, pakettide versioonid ja ressursside kontrollsummad on [ettevalmistuse JSON-is](reports/etapp5_preparation.json).

## PÃ¤ringu jÃµudlus: esimene ja kordused

KÃ¤ivitatud `python -m examples.benchmark_stage5 --runs 5`. Iga sisendi jaoks loodi **uus Python-protsess**. Seal tehti Ã¼ks esimene ja neli jÃ¤rjestikust korduspÃ¤ringut sama analÃ¼saatori/Ã¼hendusega. Esimene sisaldab analÃ¼saatori esmast tegelikku laadimist; seansi avamine on eraldi mÃµÃµdetud. OS-i failivahemÃ¤lu ei tÃ¼hjendatud. PÃ¤ringuid, ettevalmistust ja teste ei jooksutatud sama benchmark'i sees paralleelselt; masin ei olnud muude taustaprotsesside suhtes isoleeritud.

Keskkond: Windows 10.0.26200 AMD64, sama AMD protsessor (Windowsi kirjeldus `AMD64 Family 23 Model 96`), 12 loogilist CPU-d, ligikaudu 31,2 GiB nÃ¤htavat mÃ¤lu. Python 3.11.9, DuckDB 1.5.5, EstNLTK/estnltk-core 1.7.5, NLTK 3.10.4, regex 2026.9.29; DuckDB piir 512 MB / kaks lÃµime. TÃ¤psed andmed on aruandes.

Korpused:

- **Korduv**: sama fikseeritud lausestik; vÃ¤ga hÃ¤sti deduplitseeruv optimistlik juhtum.
- **Mitmekesine**: deterministlikult segatud EMS-i eelistatud nimetustega sÃ¼nteetilised laused. Palju rohkem erinevaid vÃµtmeid ja sÃµnastikuvastete suur tihedus; see ei ole juhuslik loomulik korpus ega kvaliteedikullastandard.

Algtekstid on `reports/etapp5_inputs/`, nende SHA-256 vÃ¤Ã¤rtused ja genereerimise kood on kontrollitavad. SÃµnade maht loetakse tÃ¼hikute jÃ¤rgi; EstNLTK tokenite arv sisaldab kirjavahemÃ¤rke.

| Korpus | SÃµnu | Esimene pÃ¤ring | Nelja korduse mediaan | Nelja korduse p95 | Kordumatuid vÃµtmeid | SQL-kÃ¤ske |
|---|---:|---:|---:|---:|---:|---:|
| Korduv | 100 | 0,472 s | 0,293 s | 0,338 s | 75 | 5 |
| Korduv | 1 000 | 1,346 s | 1,137 s | 1,385 s | 75 | 5 |
| Korduv | 10 000 | 9,548 s | 9,813 s | 10,269 s | 75 | 5 |
| Mitmekesine | 100 | 0,392 s | 0,191 s | 0,322 s | 672 | 5 |
| Mitmekesine | 1 000 | 1,055 s | 0,933 s | 1,103 s | 6 523 | 5 |
| Mitmekesine | 10 000 | 8,311 s | 8,499 s | 8,789 s | 65 140 | 5 |

p95 meetod on nearest rank; nii vÃ¤ikese (4â€“5 vaatluse) puhul on p95 rÃ¼hma maksimum, mitte stabiilne sabaviivituse hinnang. Soe kordus ei pea igas vaatluses esimesest kiirem olema. Koguaeg ei sisalda protsessi kÃ¤ivitamist ega terminali JSON-vÃ¤ljundi kirjutamist.

Mitmekesise 10 000 sÃµna **korduste komponentide mediaanid**:

| Osa | Mediaan | p95 |
|---|---:|---:|
| KeeleanalÃ¼Ã¼s | 7,133 s | 7,385 s |
| Fraasikandidaadid | 0,901 s | 1,025 s |
| VÃµtmete sidumine ja sobitamine | 0,238 s | 0,302 s |
| Koondamine ja jÃ¤rjestamine | 0,106 s | 0,124 s |
| MÃµistete/seoste/valdkondade detailid | 0,071 s | 0,104 s |
| Kogu pÃ¤ring | 8,499 s | 8,789 s |

Komponentide mediaanide summa ei pea vÃµrduma kogumediaaniga. 10 000 sÃµna mitmekesisel sisendil tekkis 50 050 fraasiakent; algkuju- ja lemmavÃµtmeid hoiti eraldi ning deduplitseeriti enne SQL-i. SQL-kÃ¤skude arv jÃ¤i viiele (kaks sobitamiseks, kolm detailidele), mitte Ã¼hele iga sÃµna vÃµi fraasi kohta.

KÃµigi kuue juhu pÃ¤ringuplaanid sisaldavad hash-liitmisi. OtsinguvÃµtmetele tÃ¤iendavaid indekseid ei lisatud. Kuna pÃµhikulu on keeleanalÃ¼Ã¼sis ja ka 65 140 vÃµtmega sobitamine vÃµtab ligikaudu 0,24 s, ei nÃ¤ita need mÃµÃµtmised praegu vajadust alternatiivse protsessis oleva fraasiindeksi ehitamiseks. Seda alternatiivi ei vÃ¤ideta mÃµÃµdetuks.

Protsesside tipud olid umbes 239â€“338 MiB, suurim mitmekesisel 10 000 sÃµna juhul. Tipp hÃµlmab importi, viit mÃµÃµdetud pÃ¤ringut ja eraldi diagnostilist sama sisendi `EXPLAIN ANALYZE` kutset; diagnostilise kutse aega ei lisata tabeli viie pÃ¤ringu hulka. Aruanne sisaldab kÃµiki vaatlusi, plaane, baasiversiooni, sisendite ja 12 rakenduse Python-faili SHA-256 vÃ¤Ã¤rtusi: [etapp5_benchmark.json](reports/etapp5_benchmark.json).

## Rakenduse kÃ¤ivitus ja pÃ¤ris HTTP

Viis eraldi uut Python-protsessi kÃ¤ivitasid pÃ¤ris Uvicorni serveri ajutisel loopback-pordil, ootasid `/health` HTTP 200-ni ja sulgusid seejÃ¤rel normaalselt. KÃµigil viiel korral olid `base_action=reused` ja `index_action=reused`.

| MÃµÃµdik | Vaatlusi | Mediaan | p95 |
|---|---:|---:|---:|
| Protsessi loomise algusest HTTP valmisolekuni, sh import | 5 | 6,357 s | 6,667 s |
| Uvicorni/app'i loomise algusest valmisolekuni, pÃ¤rast moodulite importi | 5 | 4,599 s | 4,956 s |

See mÃµÃµdab valmis andmetega korduvkÃ¤ivitust, mitte uut allalaadimist/importi. OS-i vahemÃ¤lu jÃ¤i alles.

Lisaks kÃ¤ivitati tÃ¶Ã¶taval **Linuxi Docker/Uvicorni teenusel** `python -m examples.benchmark_http_stage5 --runs 5`. Sama mitmekesine sisend saadeti pÃ¤ris POST-vormina ning mÃµÃµdeti aega kuni HTML-vastuse tÃ¤ieliku vastuvÃµtmiseni, kaasa arvatud vormi kodeerimine, transport ja renderdamine. Faili kohalik lugemine toimus enne ajamÃµÃµtmist. Teenus ja analÃ¼saator olid juba soojad; „esimene“ on selle HTTP-seeria esimene pÃ¤ring, mitte kÃ¼lm teenus.

| SÃµnu | HTTP-seeria esimene | KÃµigi 5 mediaan | KÃµigi 5 p95 | Nelja korduse mediaan |
|---:|---:|---:|---:|---:|
| 100 | 0,767 s | 0,427 s | 0,767 s | 0,394 s |
| 1 000 | 1,860 s | 1,860 s | 2,098 s | 1,942 s |
| 10 000 | 28,256 s | 17,915 s | 28,256 s | 16,653 s |

Serveri enda raporteeritud mootoriaja mediaan oli 10 000 sÃµna puhul 17,787 s. Seega pole Windowsi CLI ja Docker-HTTP arvude vahe Ã¼ksnes HTML-i/HTTP lisakulu: kÃ¤ivituskeskkond, andmete asukoht ja protsessi olek erinevad. Vahe tÃ¤pset pÃµhjust ei eraldatud. Ei vÃ¤ideta koormustesti ega suvalise dokumendi viivitusgarantiid. Toorvaatlused ja vastuse suurused: [etapp5_http_benchmark.json](reports/etapp5_http_benchmark.json).

## Termini-esinemiste kontrollkogum ja kvaliteedipiirangud

[evaluation/cases.json](evaluation/cases.json) on 13 assistendi koostatud sÃ¼nteetilise juhtumi ja 15 eeldatud termini-esinemisega arenduskogum. Juhtumid kontrolliti Ã¼kshaaval EMS-i pÃµhinimetuste/sÃ¼nonÃ¼Ã¼mide vastu; Ã¼levaatuse pÃµhjendused on [evaluation/README.md](evaluation/README.md). See ei ole sÃµltumatu inimannotatsioon ega kullastandard. Meetodi kaale/lemmavalikut ei hÃ¤Ã¤lestatud tulemuste jÃ¤rgi.

Esinemine on **EMS ID + algteksti algus/lÃµpp**, mitte lihtsalt leitud mÃµistete arv. Kehtiv pesastatud mitmesÃµnaline termin on samuti positiivne esinemine; selle madalam jÃ¤rjestus ei tee seda automaatselt valeks. Kogum sisaldab ka negatiivset tundmatut sÃµna ja tegusÃµna mitmetÃ¤henduslikkuse juhtumit. Kasutati Ã¼lempiiri 50, nii et top-10 lÃµikamine ei kÃ¤rbi seda vÃ¤ikest vÃµrdlust.

| Strateegia | TP | FP | FN | Mikro-precision | Mikro-recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Eelistatud nimetuse algkuju | 7 | 0 | 8 | 1,000 | 0,467 | 0,636 |
| Eelistatud nimetuse algkuju + lemma | 12 | 1 | 3 | 0,923 | 0,800 | 0,857 |
| Algkuju + lemma + eesti sÃ¼nonÃ¼Ã¼mid | 15 | 1 | 0 | 0,938 | 1,000 | 0,968 |

Precision = TP/(TP+FP), recall = TP/(TP+FN). Arvud kehtivad Ã¼ksnes nende 13 teadlikult valitud juhtumi kohta. Need ei tÃ¤henda 93,8% Ã¼ldist kindlust ega sobi kasutajale iga tulemuse tÃµenÃ¤osuseks.

NÃ¤htav valevaste on `Saavad.` â†’ `EMS019059`, „sai“. Vabamorfi analÃ¼Ã¼s ja sama deterministlik lemmavÃµti vÃµivad kokku viia tegusÃµna ja kontekstita analÃ¼Ã¼situd normitud nimisÃµna. Seda ei peideta annotatsiooni muutmise ega skoorilÃ¤vega. Eraldi kvalitatiivses teemaproovis vÃµib sÃ¼nonÃ¼Ã¼m „lahkus“ anda „lahkumata“ kaudu eksliku mÃµiste „headus“. Liides ja README hoiatavad nÃ¼Ã¼d konkreetse morfoloogilise mitmetÃ¤henduslikkuse eest ning paluvad katkendeid kontrollida.

Dokumenditeemade hindamine on hoitud lahus: `topic_probe` illustratiivsele raamatukoguteenuste teemale pole sÃµltumatut inimhinnangut ega precision/recall mÃµÃµdikut. Otsese termini leidmine ja Ã¼ldteema tuvastamine on eri Ã¼lesanded. LLM-i/embeddinguid ei kasutata. KÃµik Ã¼ksikjuhtumite eeldused ja ennustused: [etapp5_evaluation.json](reports/etapp5_evaluation.json).

## Dokumentatsioon ja taasesitamine

README viidi lÃµppseisuga kooskÃµlla: kÃµik viis etappi, Ã¼ks protsess/tÃ¶Ã¶line, andmemahud, hoidla/otsinguindeksi eristus, taaskasutamine, uuendamine/taastamine, MARC-teisendus, mitmetÃ¤henduslik lemmatiseerimine, tegelikud partiipÃ¤ringud, skoor, sisendipiir, testid, vÃ¤rsked mÃµÃµtmised ja nende piirangud. README alguses on nÃ¼Ã¼d otselingid Ã¼lesande nÃµutud kolmele dokumentatsiooniosale. Varasema etapi Ã¼ksikmÃµÃµtmisi ei esitata uusimate benchmark'ide asemel.

Uued kÃ¤sud projekti juurkaustas:

```powershell
python -m examples.check_stage5
python -m examples.evaluate_stage5
python -m examples.benchmark_stage5 --runs 5
python -m examples.check_stage4 --output reports/etapp5_http_checks.json
python -m examples.benchmark_http_stage5 --runs 5
python -m examples.preparation_stage5 --data-dir .stage5-preparation-new
```

Kasuta paigaldatud keskkonna Pythoni teed (`.venv-stage1\Scripts\python` selles tÃ¶Ã¶kaustas). SÃµltuvused ja keeleressursi paigaldus on README-s. Ettevalmistuse kaust peab olema uus; HTTP-test vajab kÃ¤ivitatud teenust; CLI benchmark'i `data/` ei tohi olla samal ajal teise protsessi poolt lukustatud. Ettevalmistuse mÃµÃµtmine ei tohi uuendada elava veebiserveri andmemahtu.

Alles jÃ¤Ã¤vad kontrollipiirangud: sÃµltumatut inimeste koostatud hindamiskorpust, tÃ¤ielikku XSD- ega ligipÃ¤Ã¤setavusauditit, eri riistvarade vÃµrdlust, OS-i kÃ¼lma kettavahemÃ¤lu katset vÃµi paralleelse koormuse benchmark'i ei tehtud. Need pole esitatud tehtud tÃ¶Ã¶na. Praegune lahendus ja dokumenteeritud kontrollid tÃ¤idavad kohaliku sÃµnastikupÃµhise otsingu tÃ¶Ã¶ulatuse.

**Etapp 5 on lÃµpetatud. Teenus jÃ¤Ã¤b tÃ¶Ã¶le aadressil http://127.0.0.1:8000.**

## POS-filtri jÃ¤relhindamine

Lisati pÃ¤ringupÃµhine POS-filter. Morfoloogilise otsingu korral jÃ¤etakse Ã¼ksiktokeni kandidaadist vaste Ã¤ra ainult siis, kui EstNLTK-i allesjÃ¤Ã¤nud sÃµnaliigid on kÃµik sidesÃµna (`J`). MitmetÃ¤henduslikud ja analÃ¼Ã¼sita juhud jÃ¤Ã¤vad alles ning fraaside sees olevaid sidesÃµnu ei eemaldata. `surface` strateegia morfoloogiat ei kÃ¤ivita ja filtrit ei kasuta. Filtreeritud akende arv tagastatakse diagnostikas vÃ¤ljal `pos_filtered_occurrences`. Filtri lisamine ei nÃµudnud indeksi uuendamist; hilisem skoorikorrektsioon tÃµi indeksiskeemi POS-andmed.

Filter kontrolliti sÃ¼nteetiliste nÃ¤idetega: „A vÃµi B“ ei anna Ã¼ksiksÃµna `vÃµi`; „Kasuta vÃµid vÃµi margariini“ sÃ¤ilitab nimisÃµnalise vaste tekstile `vÃµid`; „kala vÃµi liha“ fraasivaste sÃ¤ilib. POS-filtri jÃ¤rel lÃ¤bis **54 automaattesti**; skoorikorrektsiooni jÃ¤rel 55 ning kontekstita mitmetÃ¤hendusliku labeli kontrolli lisamise jÃ¤rel **56 automaattesti**.

Skoor kasutab nÃ¼Ã¼d samuti POS-kindlust. Iga Ã¼heselt sobiv tÃµend annab `+2`, vastuolu `-2` ja ebakindel analÃ¼Ã¼s `0`; nende korrektsioonide keskmine lisatakse mÃµiste skoorile. Sagedusboonuses kaalub Ã¼heselt sobiv tÃµend `1`, ebakindel vÃµi vastuoluline `0,5`. POS-ita `surface`-strateegia sagedus jÃ¤Ã¤b tÃ¤iskaaluga. Algne `frequency` nÃ¤itab jÃ¤tkuvalt tegelikku arvu; vastus lisab `effective_frequency`, `pos_confidence` ning `pos_correction`. ÃœksiksÃµnalise EMS-nimetuse kÃµik vÃµimalikud POS-id sÃ¤ilitatakse ilma morfoloogilise Ã¼hestamiseta; kui neid on mitu, jÃ¤Ã¤b skoor ebakindlaks. NÃ¤iteks `sai` labeli V/S mitmetÃ¤henduslikkus ei anna ekslikku positiivset boonust lausele „Saavad“. Indeksi versioon tÃµusis versioonile 3; olemasolevat EMS-i baasi ei muudetud, aga otsinguindeks tuleb Ã¼ks kord uuesti ehitada. Windowsi kohaliku indeksi kordusehitus kestis 156,548 s (120,296 s eesti nimetuste analüüs ja 33,003 s muukeelsete nimetuste sõnestamine); uuendatud Dockeri mahu indeksi kordusehitus kestis 163,918 s (128,780 s ja 31,403 s).

JÃµudlust vÃµrreldi Ã¼he kÃ¤iguga enne ja pÃ¤rast samal 1 100 812-baidisel UTF-8 nÃ¤itefailil (200 593 tokenit; 1 080 487 kandidaadiakent). MÃµlemal pÃ¤ringul jÃ¤i SQL-kÃ¤skude arv viieks.

| Etapp | Enne | PÃ¤rast |
|---|---:|---:|
| Kogu pÃ¤ring | 209,47 s | 162,27 s |
| KeeleanalÃ¼Ã¼s | 180,49 s | 135,89 s |
| Kandidaadid | 21,03 s | 18,78 s |
| Sobitamine | 6,01 s | 5,85 s |
| JÃ¤rjestamine | 1,81 s | 1,68 s |

Need Ã¼ksikmÃµÃµtmised ei tÃµenda, et filter pÃ¤ringut kiirendas: suurim erinevus tekkis keeleanalÃ¼Ã¼si ajas, mida POS-filter ei muuda. Filtri jÃ¤rel loendati 13 227 POS-i tÃµttu kÃµrvale jÃ¤etud Ã¼ksiktokeni akent; kordumatute vÃµtmete arv muutus 1 731 239-lt 1 731 222-le. EMS-i mÃµiste `EMS000882` („vÃµi“, butter) sagedus nÃ¤itefailis langes 866-lt 115-le. See on kooskÃµlas sidesÃµnaesinemiste eemaldamisega, kuid hindamine pole sÃµltumatu tÃ¤psusmÃµÃµdik ja Ã¼lejÃ¤Ã¤nud vastete hulgas vÃµib olla POS-analÃ¼Ã¼si vigu. MÃµÃµtmine nÃ¤itab, et selle faili puhul ei ilmnenud filtrist tulenevat lisaviivitust; tÃ¤pse vÃ¤ikese lisakulu hindamiseks on vaja kordusmÃµÃµtmisi kontrollitud keskkonnas.

Filtri tingimuse lisakulu eraldamiseks mÃµÃµdeti samas protsessis sama faili esimesi 10 000 sÃµna: Ã¼ks soojenduspÃ¤ring, seejÃ¤rel kolm filtriga ja kolm filtrita pÃ¤ringut vahelduvas jÃ¤rjekorras. Koguaja mediaan oli filtriga **5,804 s** ja filtrita **5,846 s**; kandidaadietapi mediaan vastavalt **0,769 s** ja **0,771 s**. Filtrita variandis oli POS-analÃ¼Ã¼s endiselt lubatud, seega see vÃµrdlus eraldab kandidaadi POS-kontrolli kulu, mitte POS-vÃ¤lja kogumise kulu. Alla Ã¼he protsendi vahe jÃ¤Ã¤b mÃµÃµtmiskÃµikumise sisse; mÃµÃµdetavat aeglustumist ei ilmnenud.

