# Etapp 4: veebiliides, üleslaadimine ja Dockeri esmakäivitus

29.10.2026. Rakendus on realiseeritud, image ehitatud ning käivitatud tühja püsiva andmemahuga. Käivitatud teenus on **http://127.0.0.1:8000**, konteineri olek `healthy`.

## Mis valmis

`ems/web.py` lisab FastAPI lifespan-käivituse ja kaks serveripoolset eestikeelset HTML-vaadet: „Otsi EMS-ist” ja „Leia tekstist märksõnad”. Mall on `ems/templates/page.html`, kohanduv stiil `ems/static/style.css`. Eraldi JavaScripti raamistikku ega brauseripoolset tekstianalüüsi ei ole.

Otsinguvorm toetab olemasolevat täpset, lemmatiseeritud ja prefiksiotsingut ning keele/tulemuste arvu valikut. Märksõnastamise vorm võtab teksti või ühe `.txt` faili, lubab valida 1–50 tulemust (vaikimisi 10) ja näitab kestust. Vastustes on normitud nimetus, EMS-i ID ja link, vasteliik, leitud väljend, sagedus, algteksti katkend koos esiletõstmisega ja skoori selgitus. Laiemad/kitsamad/seotud mõisted on eraldi kokkupandav lisainfo, mitte tekstist leitud märksõnad. Liides ütleb, et tegemist on sõnastikupõhise leidmisega, LLM-i ei kasutata ning skoor ei ole tõenäosus.

Liides renderdati ja vaadati üle headless Chrome'iga: [märksõnastamise vaate kuvatõmmis](reports/etapp4_keywords.png). Kontroll hõlmas töölaua paigutust; eraldi mobiilibrauseri ja ekraanilugeja täielikku auditit ei tehtud. Mobiilipaigutusele on CSS-i meediapäringud, väljad on siltidega ning klaviatuurifookus nähtav.

## Sisend ja privaatsus

Vaikimisi ülempiir on 1 048 576 baiti, seadistatav `EMS_MAX_INPUT_BYTES` abil. UTF-8 ja UTF-8 BOM on toetatud. Tekstikasti ja faili samaaegne kasutamine, tühi sisend/fail, vale laiend, vigane kodeering ja sobimatu tulemuste arv annavad eestikeelse HTML-vea HTTP 400-ga. Kogupäring on piiratud sisendipiiri ja 64 KiB vormi lisamahuga; ka `Content-Length`-ita voogedastuse ületamine peatatakse HTTP 413-ga enne vormi parsimist.

Vastu võetud päring ja fail hoitakse mälus. Multipart-parseri spoolimise piir on suurem kui kogu lubatud päring, nii et aktsepteeritud faile ei kirjutata ajutisele kettale; vorm/fail suletakse kohe pärast päringut. Kasutaja teksti ei kirjutata baasi ega päringulogisse. Vormid saadetakse POST-iga; Uvicorni access-log on käivituskäsus välja lülitatud. Vastustel on `Cache-Control: no-store` ja `Referrer-Policy: no-referrer`.

Jinja automaatne HTML-paokoodimine kehtib ka tekstikasti, failinime ja katkendite kohta. Esiletõstmine jagab katkendi enne/märgistatud/pärast osadeks ja paokoodib iga osa; kasutaja HTML-i ei märgita turvaliseks. Lähteandmetest pärit linke lubatakse ainult EMS-i HTTPS ID-aadressidele. CSP keelab skriptid ja objektid ning piirab vormid samale rakendusele. Testid kinnitavad, et `</textarea><script>…` ei muutu käivitatavaks HTML-iks ja `javascript:` URI ei muutu lingiks.

## Protsess, ühendus ja käivitus

Üks Uvicorni protsess ja üks tööline. Elutsükli ajal loob rakendus ühe `ThreadPoolExecutor(max_workers=1)` taustalõime. Samas lõimes toimub ettevalmistus, ühe otsinguseansi ja DuckDB ühenduse loomine, analüsaatori soojendus ning kõik järgnevad otsingud. Nii ei kasuta paralleelsed HTTP-päringud sama ühendust/ajutist tabelit samaaegselt. Testis saadeti kaks päringut korraga ning mõlema sõltumatud tulemused ja järjestikune töötlus kinnitati.

Käivitus valmistab puuduva alusbaasi ja otsinguindeksi ette ning kontrollib olemasolevate versioone. Veebiserver jõuab valmisolekuni pärast seda; `GET /health` annab siis `{"status":"ready"}`. Puudulikku baasi ei pakuta. Käivitusvea korral protsess ebaõnnestub selge teatega; varasemaid valmis andmeversioone ei kirjutata üle. Server hoiab andmekausta lukku kuni sulgemiseni. Normaalsel sulgemisel suletakse seanss samas lõimes ja lukk vabastatakse.

## Dockeriga tehtud tegelik kontroll

`Dockerfile` kasutab digestiga fikseeritud `python:3.11.9-slim` alust, lukustatud sõltuvusi, image'i ehitamisel paigaldatud NLTK `punkt_tab` ressursse ning Vabamorfi käivituskontrolli. `pip check` läbis. Runtime töötab kasutajana UID/GID 10001; täisandmestiku import õnnestus selle kasutajaga. `webbed` pole runtime-sõltuvus, sest etapis 1 kinnitatud imporditee kasutab Python XML-parserit.

`.dockerignore` jätab kohaliku XML-i, `data/`, keskkonnad, aruanded ja muud kõrvalfailid ehituskontekstist välja. Image'i kopeeritakse rakenduskood ja sõltuvuste failid, mitte valmis EMS-i baas. `compose.yaml` seob kohaliku pordi 8000 ja nimelise `ems_data` mahu `/data` külge. Välisvõrgu liidestele porti ei avaldata: hosti sidumine on `127.0.0.1`. `EMS_PORT` lubab hostipordi muuta.

Käivitatud käsud:

```powershell
docker compose build
docker compose up -d --build
docker compose ps
.\.venv-stage1\Scripts\python -m examples.check_stage4
```

Compose lõi uue mahu `yl08_ems_ems_data`. Rakendus laadis ametliku EMS-i XML-i alla, ehitas ja valideeris 42 245 mõistega alusbaasi ning valmistas ette 123 612 otsingunimetust. Allika SHA-256 on `cc9bd08ab1a29a38d7d7e279b9ef051ea885ce5219ed5d42ae2cd8f5517e2081`; see kattub varasemate etappide kontrollitud allikaga. Mahus on XML, valmis baasid, allika-/töötlusmetaandmed ja kontrollaruanne.

| Esmakäivituse osa | Mõõdetud kestus |
|---|---:|
| Allalaadimine ja lähtefaili kontrollsumma | 1,34 s |
| XML-import ja semantiliste tabelite tuletamine | 112,38 s |
| Impordi kontroll | 22,40 s |
| Otsinguindeksi ettevalmistus, sh lemmatiseerimine | 227,46 s |

Koos vahetoimingutega kulus andmete ettevalmistusele umbes **364 sekundit**. Image'i ehitamise aeg sellesse ei kuulu. Need on ühe esmakäivituse tegelikud vaatlused, mitte statistiline jõudlusvõrdlus. Docker Engine 29.9.2, Linux AMD64 / glibc 2.36 / Python 3.11.9.

Tõendid: [alusbaasi metaandmed](reports/etapp4_base_metadata.json), [otsinguindeksi metaandmed](reports/etapp4_index_metadata.json) ja [täisimpordi kontrollaruanne](reports/etapp4_validation.json).

## Korduvkäivitus ilma võrguta

Valmis konteiner eemaldati Docker bridge-võrgust ja käivitati uuesti. Ühtegi väljaminevat võrgumarsruuti polnud. Käivituslogi sisaldas `alusbaas reused` ja `otsingubaas reused`; alusbaasi ja indeksi ID-d jäid samaks. Konteineri loopback-aadressil töötasid nii `/health` kui HTTP POST märksõnastamine: „Raamatukogudes.” leidis `EMS003867`.

Tõend: [etapp4_offline_restart.json](reports/etapp4_offline_restart.json). Selle `routes` sisaldab ainult päiserida ning baas/indeks vastavad esmakäivituse metaandmetele. Pärast katset taastati bridge-võrk ja hosti veebiliides; uus HTTP-kontroll läbis ning teenus jäi olekusse `healthy`.

Offline-katse tõendab päringute ja korduvkäivituse toimimist kohalike pakettide/andmetega. Esmakordne ametliku EMS-i allalaadimine vajab võrku või ette antud kohalikku algfaili. EMS-i välislingid ja juhendi link viivad välisveebi; nende avanemine offline pole kohaliku otsingu eeltingimus.

## Testid ja lõppseis

Windowsis läbib **53 automaattesti**: varasemad 40 ning 13 uut veebiliidese/elutsükli testi. Uued 13 läbivad ka Linuxis. Need kontrollivad tekstisisendit ja UTF-8/BOM faili, valideerimisteateid, tegelikku failipiiri ja voogedastuse limiiti, HTML-i paokoodimist, linkide ohutust, privaatsuspäiseid, ketta spoolimise puudumist, paralleelpäringute järjestust, puuduva baasi esmakäivitust, korduvkäivitusel impordi/lemmatiseerimise vahelejätmist ning luku vabastamist ka käivitusvea korral.

Lisaks läbib töötava Dockeri täisandmestikuga teenus **13 päris HTTP-kontrolli**, sh 1 MiB piiri ületav üleslaadimine: [etapp4_http_checks.json](reports/etapp4_http_checks.json). Need on eraldi väikeste kohalike fixture'itega automaattestidest. Script on käivitatav käsuga `python -m examples.check_stage4`; teise pordi korral lisa `--url` ja muudetud mahu korral `--max-input-bytes`.

Testide paigaldamiseks on `requirements-dev.txt`; tootmis-image kasutab ainult `requirements-web.txt`. TestClient väljastab selles lukustatud kombinatsioonis httpx-i aegumishoiatuse; see ei mõjuta testi tulemust ega veebiserveri päringutöötlust. Rakenduse esmakäivituse ja offline-kontrollid tehti päris Uvicorni/Dockeri teenusega.

Käivitamise, peatamise, uuendamise ja ilma Dockerita töö juhised on [README-s](README.md). Uuendamiseks tuleb server peatada, sest elus server hoiab andmekausta lukku. Sunnitud protsessikatkestuse järel võib vajada käsitsi vana luku eemaldamist pärast protsesside kontrolli; seda varasemate etappide taastamisreeglit ei muudeta automaatseks.

Kontrollitud API allikad: [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/), [Jinja mallid FastAPI-s](https://fastapi.tiangolo.com/advanced/templates/) ja [FastAPI Dockeris](https://fastapi.tiangolo.com/deployment/docker/). Multipart-parseri mahu/spoolimise käitumine kontrolliti paigaldatud Starlette 1.10.0 lähtekoodist ning tegelike päringutega.

**Etapp 4 on lõpetatud. Teenus töötab; etapi 5 eraldi lõpphindamist ja täielikku kasutatavusauditit ei tehtud.**
