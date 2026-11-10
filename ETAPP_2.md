# Etapp 2: realiseeritud import ja püsiv andmebaas

29.10.2026. Valmis on käsurealt kasutatav voogimport, püsiv DuckDB, allika/töötluse metaandmed, kontrollaruanne ja ohutu versioonivahetus. Veebiliidest, lemmatiseerimist ega tekstiotsingut ei ehitatud.

## Teostus ja kasutamine

Kood on paketis `ems`: `xmlio.py` loeb ja vabastab kirjed voogpõhiselt; `importer.py` salvestab toorandmed partiidena ning tuletab mõisted, nimetused ja seosed; `validation.py` kontrollib teisendust; `storage.py` haldab allikaid, versioone, lukku ja avaldamist; `__main__.py` pakub käsurea.

Käivitati edukalt:

```powershell
.\.venv-stage1\Scripts\python -m ems prepare --xml ems_marc_tais.xml --source-meta stage1_source.json
.\.venv-stage1\Scripts\python -m ems prepare
.\.venv-stage1\Scripts\python -m ems status
.\.venv-stage1\Scripts\python -m ems validate
.\.venv-stage1\Scripts\python -m ems measure --runs 5
```

Teine `prepare` tagastas `action: reused` ilma uut allikat hankimata. Baas avati uuesti eraldi protsessides. Aktiivne manifest on `data/current.json`; tegelik püsifail on `data/generations/20261028T222627Z-73b1935b3360/ems.duckdb` (168 833 024 baiti). Versioon sisaldab oma XML-i, metaandmeid ja aktiveerimiseelset aruannet. Andmekaust on Gitist välja jäetud; kood, testid ja aruannete koopiad jäävad eraldi kontrollitavaks.

Allikas on etapis 1 ametlikust EMS-ist laaditud fail. Kohaliku koopia SHA-256 kontrolliti allalaadimise metaandmete vastu: `cc9bd08ab1a29a38d7d7e279b9ef051ea885ce5219ed5d42ae2cd8f5517e2081`. Etapi 2 täisimport ei teinud uut võrguallalaadimist ega lemmatiseerimist. Kohaliku kopeerimise aega ei esitata allalaadimise mõõtmisena.

## Täisandmestiku kontroll

| Kontroll | Tulemus |
|---|---:|
| Lähtekirjeid / toorkirjeid / mõisteid | 42 245 / 42 245 / 42 245 |
| Toorvälju, sh leader | 633 393 |
| Alamvälju | 966 994 |
| Normitud eestikeelseid nimetusi | 42 245 |
| Eestikeelseid sünonüüme | 24 010 |
| Ingliskeelseid vasteid | 57 357 |
| Nimetusi kokku | 123 612 |
| Seoseid / lahendamata seoseid | 175 535 / 0 |
| Valdkondi / kuuluvusvälju | 48 / 57 024 |
| Selgitusvälju / allikaviiteid | 12 329 / 11 423 |
| Puuduvaid / korduvaid ID-sid | 0 / 0 |
| Välistatud kirjeid / eraldi äraviitekirjeid | 0 / 0 |

Kõik 42 245 kirjet rekonstrueeriti toortabelitest ja võrreldi parsitud lähtekirje sõrmejäljega: erinevusi ei leitud. Kontroll hõlmab väljade ühist järjekorda, kordusi, indikaatoreid, alamväljade kuuluvust/järjekorda, atribuute ja teksti täpset sisu, sealhulgas 008 välja lõputühikuid. Algfaili kontrollsumma kattus. Eraldi `validate` käigus võrreldi lisaks 12 valimkirjet uuesti XML-ist parsitud andmetega; kõik kattusid. Valim katab eri tüübid, pikad ID-d, korduvad nimetused ja tühja selgituse.

Täpsemad tulemused: [etapp2_validation.json](reports/etapp2_validation.json). Aruandes on ka keelte, märksõnatüüpide, seoseliikide ja staatuste jaotused ning probleemide näited. Kõik kirje-/väljapõhised hoiatused säilivad andmebaasi `validation_issue` tabelis.

## Tegeliku ekspordi eripärad ja mudeli täpsustus

**ID-d ja URI-d pole samastatavad.** 40 991 ID kogupikkus on 9 märki, 1 254 ID kogupikkus 12 märki. Samal ajal on 1 254 URI-d kahe eri mõiste juures. Näiteks teemamõiste `EMS155000444` ja vormimõiste `EMS000444` jagavad URI-d `https://ems.elnet.ee/id/EMS000444`; nende ametlikud nimetused on vastavalt „kutsesobivustestid” ja „kutsesobivustestid (vormimärksõna)”. Mõlemad kohalikud ID-d ja URI algkuju säilivad. URI pole mõistetabelis unikaalne võti ning URI erinevus `001` ID-st annab hoiatuse, mitte andmekao ega automaatse ID-paranduse.

Etapi 1 kavandit täiendati tabeliga `relation_candidate`. See säilitab viite kõik ID/URI-põhised kandidaadid ning tüübile ja nimetusele vastamise. `relation.target_id_raw` sisaldab URI-st loetud ID-d; `target_id` on põhjendatult lahendatud kohaliku mõiste ID. Need võivad erineda. `resolution_method` teeb valiku nähtavaks.

175 533 seost lahendati ühe märksõnatüübile vastava kandidaadi kaudu. Kahel seosel osutab `550` koha „Lottemaa (teemapark)” ainsale kandidaadile. Need säilitati viidetena koos tüübihoiatusena; lähteseose välja ei muudeta. Sama tüübi eristamatute kandidaatide korral jätab importija viite mitmetähenduslikuks, mitte ei vali esimest rida. Seda haru kontrollivad väikesed automaattestid; praeguses täisfailis seda ei esinenud.

Lähtefailis on kaheksa ainult tühikutest koosnevat `680$i` selgitust. Need säilitatakse täpselt ning märgitakse hoiatusega. Mõistet ega kogu andmestikku selle tõttu ei välistata.

Aruande hoiatused: 8 tühja märkust, 1 254 põhinimetuse URI erinevust kirje ID-st, 1 254 välja 024 URI erinevust kirje ID-st ja 2 seose sihttüübi erinevust. Viimased kaks URI-hoiatuste rühma kirjeldavad samu 1 254 kirjet eri lähteväljadel, mitte 2 508 eri mõistet.

Hierarhiakontroll leidis 792 laiemat/kitsamat seosevälja, millele pole vastassuunalist vastet, ning ühe tsükli näite `EMS147780 → EMS151719 → EMS005246 → EMS147780`. Kõiki tsükleid ei loendatud. Need on lähteandmete piirangud: importija ei lisa vastassuunalisi seoseid ega eemalda tsükleid. Hilisem otsing ei tohi eeldada, et hierarhia on puu.

## Püsivuse ja vigade kontroll

Tavapärane testikäsk:

```powershell
.\.venv-stage1\Scripts\python -m unittest discover -s tests -v
```

**21 testi läbivad** Windowsis (Python 3.11.9) ja Linuxis (`python:3.11.9-slim`, AMD64). Need kasutavad väikseid kohapeal loodud XML-e, mitte võrku ega täisandmestikku. Testid hõlmavad:

- MARC-sisu täpset säilimist, korduvaid välju, indikaatoreid, keeli, ajamärksõnu ja sünonüümilt normitud mõistele liikumist;
- pikki ID-sid, jagatud URI-de tüübipõhist lahendamist ja mitmetähenduslikkuse säilitamist;
- puuduvaid/korduvaid ID-sid ja kohustuslikke alamvälju, tühja/katkist XML-i, HTML-vastust ja DTD tagasilükkamist;
- lahendamata seoseid, kustutatud/äraviitekirjete säilitamist, hierarhiatsükli leidmist;
- valmis baasi taaskasutamist ilma allalaadimise/impordita, skeemiversiooni kontrolli ja protsessilukku;
- nurjunud esmaimporti, nurjunud uuendamist ja simuleeritud atomaarse avaldamise viga: vana manifest ja baas säilivad;
- lähtefaili ning toortabelite rikkumise avastamist;
- kolme allalaadimiskatset koos ajalõppudega (võrgukutsed on testis asendatud).

Uuendamise jaoks ehitatakse uus versioon eraldi. Aktiivne manifest vahetatakse alles pärast kontrolli ja baasi sulgemist. Täpsemad uuendamis-/taastamiskäsud ja aegunud luku käsitlemine on [README-s](README.md). Veebiprotsessi pole veel olemas; tulevane rakendus peab kasutama sama lukustusliidest ning uuendamise ajaks peatuma.

## Mõõdetud kestused ja piirangud

Üks õnnestunud täisimport Windowsis, Python 3.11.9 / DuckDB 1.5.5, DuckDB mälupiir 512 MiB, 2 lõime:

| Osa | Aeg |
|---|---:|
| Kohaliku lähtefaili kopeerimine ja kontrollsumma | 0,89 s |
| XML-i import ja semantiliste tabelite tuletamine | 166,72 s |
| Aktiveerimiseelne kontroll | 21,41 s |
| Eraldi uus valideerimine | 27,05 s |

Need on üksikvaatlused, mitte kordustega impordi jõudlusvõrdlus. Mõõdetud impordikeskkond ja lähteallika metaandmed: [etapp2_metadata.json](reports/etapp2_metadata.json).

`measure --runs 5` mõõtis eraldi protsessis baasi avamist ja nimetuste rühmitust: esimene 0,0648 s, viie korra mediaan 0,0678 s, p95 (nearest rank) 0,0697 s; korduste mediaan esimese korra järel 0,0685 s. OS-i failivahemälu ei tühjendatud; „esimene” ei tähenda külma ketast. Kõik viis tulemust ja keskkond on [etapp2_measurement.json](reports/etapp2_measurement.json).

Tippmälukasutust ei mõõdetud. Etapp 3 peab eraldi mõõtma lemmatiseerimist ja partiiviisilist tekstiotsingut. Valdkondade nimetusi XML ei sisalda ning need on baasis `NULL`. Eraldi äraviitekirjete semantilise XML-esituse jaoks pole endiselt EMS-i tegelikku valimit; need säilitataks lahendamata toorkirjetena.

**Etapp 2 on lõpetatud. Etappe 3 ja 4 ei alustatud.**
