# EMS-i kohalik andmebaas

Realiseeritud on **etapid 1–5**: EMS-i MARCXML-i voogimport, püsiv DuckDB, teisendamise kontroll, eestikeelsete nimetuste lemmatiseerimine, partiiviisiline fraasiotsing, selgitatav järjestamine ning eestikeelne veebiliides faili üleslaadimise ja Dockeri esmakäivitusega. Lõppkontroll hõlmab teste, jõudlusmõõtmisi ja väikest termini-esinemiste arenduskogumit. LLM-i, embedding-mudelit ega välist tekstianalüüsi API-t ei kasutata.

**Ülesande nõue „Dokumenteerige teisendamine, päringud ja kontroll” on kirjeldatud selles README-s:**

| Nõue | Jaotis |
|---|---|
| MARCXML-i teisendamine, väljade tähendus ja andmemudel | [Andmemudel ja teisendus](#andmemudel-ja-teisendus) |
| Töötavad SQL-päringud ja impordi kontrollid | [Kontrollid ja päringud](#kontrollid-ja-päringud) |
| Tegelik partiiviisiline otsingupäring ja käsureakäsud | [Lemmatiseerimine ja otsing käsurealt](#lemmatiseerimine-ja-otsing-käsurealt) |
| Lõppkontroll, jõudlus ja hindamise piirangud | [Etapi 5 lõppkontroll](#etapi-5-lõppkontroll) |

Lõplik kontrollaruanne ja kõik mõõtmiste viited on [ETAPP_5.md](ETAPP_5.md). ETAPP_1–4 failid on vastavate etappide ajaloolised tulemused; praeguse teostuse põhijuhend on käesolev README.

Tegeliku täisimpordi tulemused ja kontrollide piirangud on [etapi 2 aruandes](ETAPP_2.md). Salvestatud kontrolltõendid asuvad [reports](reports) kaustas.

Otsingu näited, kontrollid ja mõõtmised on [etapi 3 aruandes](ETAPP_3.md).

## Kloonimine, seadistamine ja testimine

Juhised sobivad Windowsi PowerShellile. Rakenduse kõige lihtsamaks proovimiseks kasuta Dockerit; kui soovid käivitada teste või CLI-käske, loo kohalik Pythoni keskkond.

### 1. Klooni projekt

Loo GitHubis hoidla ja kopeeri selle HTTPS-aadress. Asenda allolevas käsus `OWNER/REPOSITORY` enda hoidla omaniku ja nimega:

```powershell
cd C:\TextMining\Ylesanded
git clone https://github.com/OWNER/REPOSITORY.git YL08_EMS-test
cd YL08_EMS-test
```

### 2. Loo virtuaalkeskkond ja paigalda sõltuvused

Vajalik on Python 3.11. Virtuaalkeskkond hoiab projekti sõltuvused muust Pythoni paigaldusest lahus:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -c stage1-requirements-windows.lock.txt
.\.venv\Scripts\python.exe -m nltk.downloader punkt_tab
```

### 3. Käivita testid

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Eduka käivituse lõpus kuvatakse `OK`. Testid kasutavad ajutisi andmebaase ega vaja EMS-i täisbaasi allalaadimist. Viimases kontrollis läbisid kõik 56 testi.

### 4. Käivita veebirakendus Dockeriga

Paigalda ja käivita Docker Desktop, seejärel projekti kaustas käivita:

```powershell
docker compose up -d --build
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/health
```

Kui `health` näitab `ready`, ava [http://127.0.0.1:8000](http://127.0.0.1:8000). Esimesel käivitusel laadib rakendus EMS-i andmestiku alla, impordib selle ja ehitab otsinguindeksi; see võib võtta mitu minutit. Edenemist näed käsuga `docker compose logs -f ems`. Lõpeta logivaade klahvikombinatsiooniga `Ctrl+C`; see ei peata konteinerit. Teenuse peatamiseks kasuta `docker compose down`.

Compose salvestab andmebaasi püsivasse Docker-mahtu, nii et tavaline `docker compose down` andmeid ei kustuta. Ära kasuta `docker compose down -v`, kui soovid seda andmemahtu alles hoida. Kui port 8000 on hõivatud, määra enne käivitust näiteks `$env:EMS_PORT=8001` ning kasuta seejärel aadressi `http://127.0.0.1:8001`.

## Veebirakenduse kiirkäivitus Dockeriga

```powershell
docker compose up --build
```

Ava **[http://127.0.0.1:8000](http://127.0.0.1:8000)**. Esimesel käivitusel valmistatakse andmed ette enne veebiserveri valmisolekut; siin kulus selleks ligikaudu kuus minutit. Logi lõpus peavad olema `EMS: valmis päringuteks` ja `Application startup complete`. Vahepeal näitab `docker compose ps` seisundit `health: starting`; valmimisel `healthy`. Taustal käivitamiseks kasuta `docker compose up -d --build`; logi näeb käsuga `docker compose logs -f ems`.

Kaks vaadet:

- **Otsi EMS-ist**: sõna/fraas, täpne/lemma-/prefiksiotsing, keele ja tulemuste arvu valik.
- **Leia tekstist märksõnad**: tekstikast või üks UTF-8 `.txt` fail, kuni 10 märksõna vaikimisi (1–50), töötlemise kestus, ametlikud nimetused, lingid, vasteliigid, sagedused, esiletõstetud katkendid ja skoori põhjendused. Seosed on eraldi lisainfo.

Esimesel käivitamisel laadib teenus ametliku EMS-i XML-i alla, kontrollib ja impordib selle ning lemmatiseerib eestikeelsed nimetused. Järgmistel käivitustel kasutatakse valmis baasi ja indeksit ilma EMS-i võrgukontrolli või korduva lemmatiseerimiseta. Keeleressursid ja paketid paigaldatakse image'i ehitamisel; EMS-i XML-i ega kohalikke kasutajaandmeid image'i ei kopeerita. Püsiv **`ems_data`** andmemaht hoiab `/data` all algfaili, baase ja metaandmeid. Compose lisab mahu nimele projektiprefiksi (siin `yl08_ems_ems_data`). Kohalik töökausta `data/` ja Dockeri nimeline andmemaht on eraldi.

Rakendus kasutab üht Uvicorni protsessi ja üht veebitöölist. Kõik otsingud ja DuckDB ühenduse kasutamine toimuvad järjestikku ühes taustalõimes, kuhu luuakse ka ühendus ja analüsaator. Server hoiab töö ajal andmekausta lukku. Valmisoleku kontroll on `GET /health`; see annab valmis rakenduses `{"status":"ready"}`. Teadlikult esimest ettevalmistust internetita teha ei saa, kui valmis andmeid pole; pärast edukat ettevalmistust töötab teenus offline, mida on kontrollitud.

Vaikimisi failipiir on 5 MiB ehk 5 242 880 baiti. Tühja, vigase kodeeringuga, vale laiendiga või liiga suure sisendi puhul kuvatakse eestikeelne viga. Tekstikasti ja faili üheaegne kasutamine lükatakse tagasi. HTML paokooditakse ka katkendites ja esiletõstmisel; üleslaaditud tekste ei salvestata püsivalt ega kirjutata päringulogisse. Aktsepteeritud failid parsitakse mälus ning suletakse kohe pärast päringut. Vormide vastuseid ei puhverdata brauseri vahemällu (`no-store`).

Seadistus PowerShellis enne Compose'i käivitamist:

```powershell
$env:EMS_PORT='8001'                 # Hostipordi muutmine; konteineris jääb 8000
$env:EMS_MAX_INPUT_BYTES='5242880'   # Teksti ja faili UTF-8 mahu ülempiir
docker compose up --build
```

HTTP kogupäringule lubatakse lisaks 64 KiB vormi päiseid ja muid multipart-andmeid. Piiri kontrollitakse ka `Content-Length`-ita voogedastatud päringul. Kogupäringu ületamine annab HTTP 413; vormi/faili kontrollvead HTTP 400.

Teenuse peatamine säilitab andmed:

```powershell
docker compose stop ems
# Hiljem:
docker compose up -d
```

Teadlik uuendamine toimub **peatatud teenusega**, sama püsiva andmemahu peal:

```powershell
docker compose stop ems
docker compose run --rm --no-deps ems python -m ems refresh
docker compose run --rm --no-deps ems python -m ems prepare-search
docker compose up -d
```

Valideerimiseks asenda hoolduskäsk käsuga `python -m ems validate`. Kui muudetud on ainult keeleressursse/töötlusversiooni, kasuta peatatud teenusega `python -m ems prepare-search --rebuild`. Töötava serveri ajal annavad samasse andmekausta suunatud hoolduskäsud lukuteate. Normaalsel sulgemisel lukk vabastatakse. Sunnitud katkestamise järel alles jäänud luku eemaldamise juhis on püsivuse jaotises; seda ei eemaldata pimesi automaatselt. Ebaõnnestunud ettevalmistus peatab käivitumise veaga, mitte ei paku poolikut baasi.

## Veebirakendus ilma Dockerita

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-web.txt -c stage1-requirements-windows.lock.txt
.\.venv\Scripts\python -m nltk.downloader punkt_tab
$env:EMS_DATA_DIR='data'
.\.venv\Scripts\python -m uvicorn ems.web:app --host 127.0.0.1 --port 8001 --workers 1 --no-access-log
```

Ava `http://127.0.0.1:8001`. Olemasolevat `.venv-stage1` keskkonda võib kasutada `.venv` asemel. Ka siin valmistab käivitus puuduva baasi ja indeksi automaatselt ette. Linuxis kasuta `.venv/bin/python` teed ja `stage1-requirements-linux.lock.txt` versioonipiiranguid. Valikuline `EMS_SOURCE_XML` määrab esmakordseks impordiks kohaliku XML-i tee ja `EMS_SOURCE_META` etapi 1 allikamanifesti tee; valmis baasi korral neid uuesti ei loeta.

Etapi 4 tulemused, Dockeri esma-/korduvkäivituse tõendid ja piirangud: [ETAPP_4.md](ETAPP_4.md).

## Käsurea andmebaasi käivitamine

Python 3.11; katsetatud DuckDB 1.5.5-ga Windows AMD64 ja Linux AMD64 keskkonnas. Etapi 2 jaoks piisavad `requirements.txt` paketid; EstNLTK-d ega veebiteeke importimiseks ei laadita.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m ems prepare
```

Esimesel korral laaditakse ametlik XML alla ja ehitatakse kohalik baas. Järgmisel korral sama `prepare` kasutab valmis baasi: allalaadimist, XML-i importi ega uut võrgukontrolli ei tehta. Versioonid kontrollitakse kohaliku manifesti ja baasi töötlusmetaandmete põhjal. Praeguses töökaustas on ka etapis 1 loodud `.venv-stage1`, mida saab samades käskudes kasutada.

Olemasolevast XML-ist ilma võrguta:

```powershell
.\.venv-stage1\Scripts\python -m ems prepare --xml ems_marc_tais.xml --source-meta stage1_source.json
.\.venv-stage1\Scripts\python -m ems status
.\.venv-stage1\Scripts\python -m ems validate
.\.venv-stage1\Scripts\python -m ems measure --runs 5
```

`--source-meta` on valikuline. Selle korral peab XML-i SHA-256 kattuma etapi 1 allalaadimise tõendiga. Ilma selleta märgitakse omandamisviisiks `local_copy`, säilitatakse kohalik päritolutee ja kopeerimisaeg ning jäetakse allalaadimisaeg ja võrguallikas teadmata. Aega ei oletata faili muutmisajast. Võrgust allalaadimisel säilitatakse URL, UTC allalaadimisaeg ja HTTP päised.

Linuxis on käsud samad, Pythoni tee on näiteks `.venv/bin/python`. Kõik käsud toetavad `--data-dir <kaust>` valikut; vaikimisi `data` suhtes jooksva töökaustaga. Edu annab väljumiskoodi 0, nurjumine 1. `validate` kirjutab täieliku aruande kausta `data/last_validation.json`.

## Püsivus, uuendamine ja taastamine

Iga õnnestunud import loob muutumatu tervikversiooni:

```text
data/
  current.json                 aktiivse versiooni manifest
  current.previous.json        eelmise versiooni manifest pärast edukat uuendamist
  generations/<run_id>/
    source.xml                 algfail baiditäpselt
    source.json                päritolu, HTTP-andmed, SHA-256
    ems.duckdb                 valmis andmebaas
    metadata.json              töötlusversioonid, keskkond, loendused, kestused
    validation.json            aktiveerimiseelne kontrollaruanne
```

Ettevalmistus kirjutab algul `source.xml.part` ja `building.duckdb` failidesse. Alla laaditakse ühenduse/lugemise ajalõpuga 20/180 sekundit, kuni kolm katset (vaheajad 1 ja 2 sekundit). MARCXML-i juur ja nimeruum kontrollitakse enne lähtefaili vastuvõtmist, seejärel parsitakse ja kontrollitakse kogu fail. HTML-vealeht, tühi XML, vigane XML ning DTD/olemitega dokument lükatakse tagasi. Katsebaas valideeritakse ja suletakse enne valmiks nimetamist. Viimase sammuna avaldatakse uus `current.json` atomaarse `os.replace` abil samal failisüsteemil. Manifest viitab korraga tervele versioonikaustale: XML, baas ja metaandmed ei saa eri versioonidest kokku sattuda.

Teadlik uuendamine, **pärast teiste EMS-protsesside peatamist**:

```powershell
.\.venv-stage1\Scripts\python -m ems refresh
# Või kohalikust algfailist:
.\.venv-stage1\Scripts\python -m ems refresh --xml ems_marc_tais.xml --source-meta stage1_source.json
```

Nurjumisel aktiivset manifesti ega vana baasi ei muudeta. Nurjunud versioonikausta jääb `failure.json`; struktuurikontrollini jõudnud impordi korral ka `validation.json`. Ka esmakordne nurjumine annab arusaadava vea ja valmis baasi ei avalda. Vanad versioonikaustad jäävad alles; neid automaatselt ei kustutata. Iga täisversioon vajab algfaili ja baasi jagu lisaruumi; ettevalmistusel lisanduvad ajutised JSONL-failid ja DuckDB tööfailid.

Kõik tööriista käsud ja `ems.storage.database()` kasutavad ühist `data/.ems.lock` lukku; selle ajal teine lugeja/importija ei käivitu. See on esimese versiooni tahtlikult lihtne protsessilukk. Välised otse DuckDB faili avavad programmid seda lukku ei kasuta: need tuleb enne uuendust ise peatada. Pärast protsessi krahhi võib lukk alles jääda. Eemalda **ainult `.ems.lock` fail**, kui oled kontrollinud, et ühtki seda kausta kasutavat EMS-protsessi ei tööta. Luku sees on PID ja loomise aeg.

Ühildumatu skeemi/importija versioon ei põhjusta vaikset ülekirjutamist. Peata protsessid, säilita vana andmekaust ning käivita `refresh --xml <varasema-versiooni/source.xml>` sobiva tarkvaraversiooniga. Eelmise valmis versiooni taastamiseks peata protsessid ja asenda `current.json` eelmise manifesti koopiaga; terve vana versioonikaust peab alles olema. Taastatud manifest peab vastama kasutatava tarkvara skeemile. Kontrolli tulemust käskudega `status` ja `validate`. Kui manifest ise on katki, taasta kõigepealt `current.previous.json` või kasuta uut `--data-dir` kausta ja impordi säilitatud XML uuesti.

## Andmemudel ja teisendus

[Etapi 1 aruanne](ETAPP_1.md) põhjendab `webbed`-i asemel Python XML-parseri kasutamist: testitud laienduse SAX-lugemine ebaõnnestus ja DOM-lugemine kärpis MARC-i fikseeritud pikkusega 008 välja. DuckDB jääb andmehoidlaks. `defusedxml.ElementTree.iterparse` hoiab mälus ühe kirje; töödeldud kirjed eemaldatakse juure alt. Vaheandmed kirjutatakse ketta JSONL-failidesse ja loetakse DuckDB-sse tüübistatud partiidena. SQL-i ei käivitata iga välja/alamvälja kohta eraldi. DuckDB mälupiir on 512 MiB ja töötlemislõimi kaks; see piir ei hõlma kogu Pythoni protsessi mälu.

| Kiht | Tabelid |
|---|---|
| Toorandmed | `marc_record`, `marc_field`, `marc_subfield` |
| Mõisted ja nimetused | `concept`, `label` |
| Seosed ja valdkonnad | `relation`, `relation_candidate`, `domain`, `concept_domain` |
| Selgitused ja allikaviited | `concept_note` |
| Tuvastatud eraldi äraviitekirjed | `redirect` |
| Päritolu ja kontroll | `source_snapshot`, `processing_run`, `validation_issue` |

ID-d ja koodid on tekstina, koos algsete nullidega. `record_pk` on kirje 1-põhine järjekord XML-is. `field_pos` ja `subfield_pos` säilitavad järjekorra, `field_id` määrab alamväljade ühise päritolu. Kontrollväljade teksti ega indikaatoreid ei kärbita. Säilivad ka MARC-elementide atribuudid. XML-prefiksite kirjapilt, atribuutide algjärjekord, kommentaarid ja elementidevaheline vormindus on baiditäpselt alles `source.xml` failis; relatsiooniline kiht säilitab MARC-andmesisu, mitte XML-i vormindusbaite.

- `001` → algne EMS ID. Numbrite arvu ei piirata kuuega: ekspordis on ka ID-d nagu `EMS155000444`. `024$0` ja 1XX `$0` URI-sid võrreldakse kirje ID-ga, erinevused raporteeritakse ning mõlemad algkujud säilivad.
- `148/150/151/155$a` → aja/teema/koha/vormi normitud nimetus. Selle välja ID on ka eelistatud nimetuse ID.
- `448/450/451/455$a`, ind2 tühik → eestikeelne sünonüüm; ind2 `9` → ingliskeelne vaste. Tundmatu indikaator annab keele `und` ja hoiatuse; toorandmed jäävad alles. `040$b` ei määratle nimetuse keelt.
- `548/550/551/555`: sama välja `$w=g` → `broad`, `$w=h` → `narrow`, puuduv/tühi `$w` → `related`. Tundmatu väärtus → `unknown` ja hoiatus. `$a` ja `$0` jäävad selle välja külge. URI-st eraldatud `target_id_raw` ei kirjuta üle lähtekirje ID-d; lahendatud `target_id` võib sellest erineda, kui andmestikus jagatakse URI-d.
- `072$a` + `$2=ems`, ind2 `7` → valdkonnakood ja mõiste kuuluvus. Valdkondade nimetused jäävad `NULL`-iks, sest neid XML-is ei ole. Korduvad kuuluvusväljad säilivad, `concept_domains_distinct` vaade annab loogilised kordumatud kuuluvused.
- `680$i` → selgitus; `670$a` → allikaviide. Need ei muutu sünonüümideks.
- Leaderi 05 `d` jätab kirje toorkihti ja märgib välistamise põhjuse. 008/09 `b/c` kirjed jäävad toorkihti ja lahendamata `redirect` tabelisse: eraldi äraviite XML-esitust pole EMS-i tegeliku ekspordi põhjal kinnitatud. Muid tundmatuid staatuseid/tüüpe ei muudeta oletuslikult mõisteteks.

Korduvad nimetusväljad jäävad eraldi ridadeks; nimetuse tekst pole unikaalne võti. Puuduvad/korduvad kohustuslikud alamväljad, ID-probleemid ja tundmatud kirjestaatused on vead: vigast kirjet semantilisse kihti ei võeta ja uut versiooni ei aktiveerita. Ainult tühikuid sisaldav olemasolev `680$i`/`670$a` märkus säilib muutmata ja annab hoiatuse. Kustutatud ning toorkihis säilitatavad äraviitekirjed on dokumenteeritud välistamised. Lahendamata seosed, URI ja kirje ID erinevused, sihtnimetuse erinevused ja hierarhia probleemid on hoiatused: lähteandmeid ei parandata automaatselt.

**Jagatud URI-d.** Tegelikus EMS-is on 1 254 URI-d, millest igaüks on kahe eri ID ja tüübiga mõiste juures. Näiteks `EMS155000444` on teema „kutsesobivustestid” ja `EMS000444` vorm „kutsesobivustestid (vormimärksõna)”, kuid mõlema deklareeritud URI on `https://ems.elnet.ee/id/EMS000444`. URI pole mõistete unikaalne võti. ID-del ei eemaldata prefiksit `155` ega muud osa.

`relation_candidate` säilitab iga seose võimalikud sihtmõisted ja tõendid: vastavus algsele ID-le või mõiste deklareeritud URI-le, seosevälja tüübile ning sihtnimetusele. Lahendamine valib ühe sobiva tüübiga kandidaadi (`548` aeg, `550` teema, `551` koht, `555` vorm); mitme sobiva tüübi korral valib ainult ühe täpse sihtnimetusega kandidaadi. Kui üldse on ainult üks kandidaat, säilib viide ka tüübi erinevuse korral koos hoiatusega. Muu mitmetähenduslikkus jääb `ambiguous`-olekusse; puuduva kandidaadiga viide `unresolved`-olekusse. `resolution_method` teeb valiku kontrollitavaks. Tulevane veebiliides peab arvestama, et kahe kohaliku mõiste veebilingiks võib olla sama lähte-URI.

## Kontrollid ja päringud

`prepare` ja `refresh` avaldavad baasi alles pärast järgmisi kontrolle:

- XML-i ja baasi kirjete, väljade, alamväljade, indikaatorite ja staatuste loenduste võrdlus.
- Iga kirje kogu toorsisu rekonstruktsioon tabelitest algses järjekorras ja selle SHA-256 võrdlus parsitud lähtekirje sõrmejäljega. Säilivad ka 008 lõputühikud.
- Algfaili SHA-256 kontroll ja valimkirjete sõltumatu uuesti parsimine XML-ist; valimis on eri märksõnatüübid, sünonüümid ja märkused.
- Puuduvad/korduvad ID-d, viidete lahendamine, tabelite terviklus ja eelistatud nimetuse olemasolu.
- Nimetuste ja mõistete arv liikide/keelte kaupa, välistatud kirjete põhjused, valdkondade arv.
- Laiemate/kitsamate viidete vastastikkus ning ühe võimaliku hierarhiatsükli leidmine. Kõiki tsükleid ei loendata.

Kontrollaruanne annab probleemide koguarvud ja kuni 100 näidet. Kirje- ja väljapõhised impordiprobleemid on `validation_issue` tabelis, kõik lahendamata viited `relation` ja `redirect` tabelites. Hierarhia vastastikkuse ja tsükli kontrollid on aruande `hierarchy` osas. `validate` ei kirjuta aktiveerimise algaruannet üle, vaid loob `last_validation.json`.

Baasi tee saab `status` käsust või Pythonis `ems.storage.database()` kontekstist. Näited:

```python
from ems.storage import database

with database('data') as (con, generation, manifest):
    print(con.execute('''
        SELECT language, role, count(*)
        FROM label GROUP BY language, role ORDER BY language, role
    ''').fetchall())
    print(con.execute('''
        SELECT c.ems_id, preferred.text, alternative.text
        FROM label alternative
        JOIN concept c USING (ems_id)
        JOIN label preferred ON preferred.label_id = c.preferred_label_id
        WHERE alternative.text = ?
    ''', ['biblioteegid']).fetchall())
```

Toorväljad ja alamväljad ühe kirje algses järjekorras:

```sql
SELECT r.ems_id_raw, f.field_pos, f.tag, f.ind1, f.ind2,
       f.value AS control_value, s.subfield_pos, s.code, s.value
FROM marc_record r
JOIN marc_field f USING (record_pk)
LEFT JOIN marc_subfield s USING (field_id)
WHERE r.ems_id_raw = 'EMS137472'
ORDER BY f.field_pos, s.subfield_pos;
```

`measure` on kerge baasi avamise ja nimetuste rühmituspäringu mõõtmine (esimene kord, kordused, mediaan, p95, keskkond), mitte tekstiotsingu benchmark. Tekstiotsingu, rakenduse käivituse, HTTP-vastuse ja kogu ettevalmistuse eraldi mõõtmiskäsud on etapi 5 jaotises. Uue ettevalmistuse metaandmetes on eraldi allalaadimine, XML-i toorkihti import ja semantilised tuletused; otsingumetaandmetes eesti nimetuste eeltöötlus, teiste keelte sõnestamine ja baasi laadimine. SQL-i indekseid pole otsingut oletades lisatud; primaar-/unikaalsed võtmed tagavad andmetervikluse.

## Testid

```powershell
.\.venv-stage1\Scripts\python -m unittest discover -s tests -v
```

Testid genereerivad väikesed kohalikud MARCXML-id ega laadi EMS-i. Kogu komplekti jaoks paigalda `requirements-dev.txt` koos oma platvormi versioonipiirangutega ning kohalik `punkt_tab` ressurss. Üksnes imporditeste saab ilma EstNLTK ja veebiteekideta käivitada käsuga `python -m unittest tests.test_import -v`. Imporditestid kontrollivad järjestust, korduvaid välju, puuduvaid alamvälju, indikaatoreid/keeli, sünonüümi seost normitud mõistega, ajamärksõnu, lahendamata viiteid, kustutatud/äraviitekirjete säilitamist, vigast sisendit, püsibaasi taaskasutust, versioonide ühilduvust, lukku ja ebaõnnestunud aktiveerimist. Otsingutestide sisu on kirjeldatud etapi 3 aruandes. Veebiliidese ja käivituse testid on `tests/test_web.py`; töötavat konteinerit saab kontrollida käsuga `python -m examples.check_stage4`. Täisandmestiku kontroll on eraldi `prepare --xml ...` / `validate` integratsioonikäik.

Impordibaasi `ready` tähendab etapi 2 valmimist. Etapi 3 otsingubaasi valmisolekut kontrollitakse eraldi, järgmises jaotises kirjeldatud manifestist.

## Lemmatiseerimine ja otsing käsurealt

**Otsingu ulatus.** Rakenduse EMS-otsing on leksikaalne ja lemmadel põhinev: see leiab algkuju-, käände- ja sünonüümivasteid. See ei kasuta vektoritel põhinevat tähendussarnasuse otsingut ega ennusta tekstis puuduvaid teemasid. LLM-i ei kasutata.

Paigalda lisaks EstNLTK ning enne offline-kasutust NLTK lausepiiriressurss. Olemasolevas `.venv-stage1` keskkonnas on need juba olemas. Täpsed transitiivsete pakettide versioonid on etapis 1 kontrollitud platvormilukkudes; `-c` piirab versioone ilma üleliigseid veebiteeke installimata.

```powershell
.\.venv\Scripts\python -m pip install -r requirements-search.txt -c stage1-requirements-windows.lock.txt
.\.venv\Scripts\python -m nltk.downloader punkt_tab
.\.venv\Scripts\python -m ems prepare-search
```

Linuxis kasuta `stage1-requirements-linux.lock.txt` piiranguid ja oma Pythoni teed. Puuduva kohaliku keeleressursi korral otsing ise internetist alla laadida ei proovi, vaid annab paigaldamisjuhise.

```powershell
.\.venv-stage1\Scripts\python -m ems search "raamatukogudes" --mode lemma
.\.venv-stage1\Scripts\python -m ems search "libraries" --language en --mode exact
.\.venv-stage1\Scripts\python -m ems search "raamatu" --mode prefix --limit 5
.\.venv-stage1\Scripts\python -m ems keywords --file examples/library.txt --limit 10
.\.venv-stage1\Scripts\python -m ems keywords --text "Mandibula on alalõualuu."
```

Käsud väljastavad UTF-8 JSON-i. `search` toetab keeli `all/et/en` ja režiime `all/exact/lemma/prefix`; `all` ühendab täpse algkuju ja lemmafraasi, mitte prefiksit. Inglise nimetustele ei tehta eesti lemmatiseerimist. `keywords` võtab kas `--text` või `--file`, mitte mõlemat. Fail peab olema UTF-8 või UTF-8 BOM; vaikimisi mahupiir 5 MiB, seadistatav `EMS_MAX_INPUT_BYTES` keskkonnamuutujaga. Tulemusi saab küsida 1–50, vaikimisi kuni 10. Puuduvaid vasteid ei täideta seotud mõistetega.

`search` ja `keywords` valmistavad puuduva otsingubaasi automaatselt ette. Olemasolev alusbaas ei põhjusta uut allalaadimist. Esmakordne `prepare-search` analüüsib 66 255 eestikeelset nimetust ja sõnestab 57 357 ingliskeelset vastet. Valmis tuletatud baas asub `data/search_indexes/<index_id>/search.duckdb`; `data/search_current.json` viitab aktiivsele versioonile. Impordi muutumatut `ems.duckdb` faili ei muudeta. Esimese ehituse aeg sõltub keskkonnast: etapi 3 Windowsi vaatluses umbes 199 s, etapi 4 Dockeri nimelisel mahul 227 s; need on ajaloolised üksikvaatlused, mitte samaväärsete keskkondade kiirusvõrdlus.

Uus otsingubaas avaldatakse alles pärast arvu- ja struktuurikontrolli. Nurjunud ehitus säilitab eelmise otsingumanifesti. Alusbaasi teadlik uuendamine muudab `source_run_id` väärtust ning järgmine otsing valmistab selle versiooni jaoks uue otsingubaasi. Normaliseerija, paketiversioonide või keeleressursside muutuse korral nõutakse teadlikku käsku `prepare-search --rebuild`. Ressursside SHA-256 väärtused on otsingubaasi metaandmetes. Tavaline korduvkäivitus neid nimetusi uuesti ei lemmatiseeri.

`search_label` sisaldab iga lähte-label_id kohta EMS-i ID-d, originaalteksti, keelt, rolli, tokenite järgi normaliseeritud algkuju, algkujuvõtit, järjestatud lemmade loendit, lemmavõtit, lemma-alternatiive, tokenite arvu ja analüüsihoiatusi. Vaid `label_id` on unikaalne; sama algkuju/lemmavõtme kõik eri mõisted säilivad. Inglise lemmaväljad on `NULL`. Võtmed on järjestatud sõnede kompaktne JSON-loend, mis väldib eraldajatega liitmise kokkupõrkeid.

Unicode NFC rakendatakse analüüsiks; tõst normaliseeritakse `casefold()` abil tokenitel. Grafeemide vastavuskaart säilitab nihked algtekstis ka siis, kui lahutatud diakriitik muutub üheks täheks. Õ, ä, ö ja ü säilivad. Üks protsess kasutab ühte EstNLTK resolverit ja Vabamorfi; `disambiguate=True`, `guess=True`, `propername=True`. Allesjäänud erinevad lemmad normaliseeritakse ja järjestatakse ning valitakse leksikograafiliselt esimene. Alternatiivid säilivad indeksis diagnostikaks; kombinatsioonide korrutist ei genereerita. See on deterministlik piirang, mitte väide keeleteaduslikult ainuõige lemma kohta. Analüüsita tokeni korral kasutatakse selle normaliseeritud algkuju.

Morfoloogiline märksõnaotsing säilitab lisaks tokeni sõnaliigi analüüsi. Ühe tokeniga kandidaati ei lisata, kui selle kõik allesjäänud POS-analüüsid on sidesõna (`J`). Mitmetähenduslikud ja analüüsita tokenid jäävad alles; mitmesõnalisi fraase see filter ei muuda. Nii eemaldub näiteks „või” sidesõnana, kuid nimisõnana või ebakindla POS-iga esinemine säilib. `surface` strateegia morfoloogiat ei käivita ja POS-filtrit ega POS-skoorimist ei rakenda. Filtreeritud üksiktokeni akende arv on diagnostikas `pos_filtered_occurrences`. Skoorimiseks talletab otsinguindeks tokenite POS-id; kontekstita üksiksõnaliste EMS-nimetuste võimalikud POS-id säilitatakse mitmetähenduslikkuse tuvastamiseks. POS-skoorimise kasutuselevõtt nõuab üks kord `prepare-search --rebuild` käsku, kuid EMS-i algandmeid uuesti importima ei pea.

Sisend analüüsitakse lause kontekstis. Fraasiaknad ei ületa lausepiiri; stoppsõnu ei eemaldata, liitsõnu ei lõhuta. Fraasipikkused võetakse tegelikust eestikeelsete nimetuste indeksist. Tokenite arv sisaldab vajadusel fraasi sisemist kirjavahemärki; kandidaadi algus/lõpp peab sisaldama tähte või numbrit. Sisendist moodustatakse kuni 2 miljonit fraasiakent; eraldi hoitakse kordumatuid võtmeid ja nende esinemiskohti.

Kõik kordumatud võtmed antakse DuckDB-le kahe seotud massiivina ühes käsus:

```sql
CREATE OR REPLACE TEMP TABLE candidate_keys AS
SELECT unnest(?::VARCHAR[]) AS kind,
       unnest(?::VARCHAR[]) AS match_key;

SELECT k.kind, k.match_key, s.label_id, s.ems_id
FROM candidate_keys k JOIN idx.search_label s ON k.match_key = s.surface_key
WHERE k.kind = 'exact' AND s.language = 'et'
UNION ALL
SELECT k.kind, k.match_key, s.label_id, s.ems_id
FROM candidate_keys k JOIN idx.search_label s ON k.match_key = s.lemma_key
WHERE k.kind = 'lemma' AND s.language = 'et';
```

Tegelik päring lisab valitud strateegia rollifiltri. Tulemuste detailid, seosed ja valdkonnad lisatakse kolme ühispäringuga ainult valitud mõistetele. Sobitamiseks ja detailideks tehakse kokku viis SQL-käsku sõltumata sõnade arvust; tühja tulemuse korral kaks. `--explain` lisab kuuenda käsuna `EXPLAIN ANALYZE` ja tagastab plaani. SQL-i indekseid otsinguvõtmetele ei lisatud: kontrollitud plaan kasutab hash-liitmisi ning praegustes mõõtmistes on põhikulu keeleanalüüsis.

Järjestus on reeglipõhine: parima vaste alus 100 (algkuju) või 80 (lemma), eelistatud nimetusele +8, iga lisatokeni eest +3 (kuni 7 lisatokenit), sagedusboonus `6 * min(5, log2(efektiivne sagedus + 1))` (ülempiir 30). POS-ilt üheselt sobiv tõend saab +2, üheselt vastuoluline -2 ja ebakindel 0; korrektsioon on tõendite keskmine. Ebakindel või vastuoluline tõend annab sagedusele 0,5 kaalu; üheselt sobiv või POS-ita strateegia 1. Üksiksõnalise funktsioon-POS-iga EMS-nimetuse POS loetakse konteksti puudumise tõttu ebakindlaks, et näiteks märksõna „või” nimisõnalist kasutust mitte karistada. Algne `frequency` jääb tegelikuks esinemiste arvuks, skoori põhjendus näitab ka kaalutud sagedust ja POS-korrektsiooni. Kui kõik POS-id sobivad, saab sama täpne eelistatud üksiksõna 30 esinemise korral 139,725 punkti; sobiva POS-iga üks kord leitud kahesõnaline fraas 119 punkti. Sama mõiste sama tekstikoht loetakse üks kord, ka täpse/lemmavaste või mitme sünonüümi korral. Sama mõiste pikema vaste sees olev lühem vaste koondatakse pikemasse. Täielikult pikemate fraaside sees olevad üksiksõnamõisted jäetakse välja; täielikult kaetud pikem fraas saab -20. Skoorivõrdse seisu lahendab EMS-i ID. Skoor ei ole tõenäosus ega protsent.

Tulemus sisaldab ametlikku nimetust, algset EMS-i ID-d ja lähte-URI-d, leitud teksti, nimetust/match_type'i, sagedust, skoori põhjendust ning kuni viit tõendit koos algteksti nihete ja katkenditega. Sagedus näitab kõiki koondatud esinemisi; tõendite arvu piir ei vähenda seda. Laiemad/kitsamad/seotud mõisted on eraldi `relations` lisainfo (kuni viis iga seoseliigi kohta koos koguarvuga), mitte tekstist leitud märksõnad. Jagatud URI-de eripärad jäävad kehtima.

Meetod otsib sõnastikupõhiseid termineid, mitte kõiki dokumendi põhiteemasid. Sage üldsõna võib otsese vaste tõttu järjestuda erialaterminist ettepoole. Morfoloogiline või mõisteline mitmetähenduslikkus jääb osaliselt alles ning võib anda valevaste: kontrollkogumi „Saavad.” võib lemmavõtme kaudu leida nimisõna „sai”. Samuti võib sünonüümi „lahkus” lemmatiseerimine põhjustada „lahkumata” sobitumise mõistega „headus”. Need pole dokumenditeemade õiged tuvastused. Kontrolli vasteliiki, algteksti katkendit ja ametlikku nimetust; skoor ei ole kindlus. Seda piirangut näidatakse ka liideses. Kasutaja sisendit ei kirjutata baasi ega logifaili; CLI vastus sisaldab nõutud katkendeid. `examples` skriptid salvestavad ainult repositooriumisse lisatud sünteetiliste näidiste vastuseid.

Kontrollimiseks ja võrdluseks:

```powershell
.\.venv-stage1\Scripts\python -m unittest discover -s tests -v
.\.venv-stage1\Scripts\python -m examples.check_stage3
.\.venv-stage1\Scripts\python -m examples.benchmark_stage3 --runs 5
.\.venv-stage1\Scripts\python -m ems keywords --file examples/library.txt --strategy surface
.\.venv-stage1\Scripts\python -m ems keywords --file examples/library.txt --strategy lemma
.\.venv-stage1\Scripts\python -m ems keywords --file examples/library.txt --strategy lemma-synonyms
```

Kolm strateegiat on vastavalt eelistatud nimetuste algkuju, eelistatud nimetuste algkuju+lemmad ja algkuju+lemmad koos eesti sünonüümidega. Näidised ja ootused on arenduskontrollid, mitte sõltumatu kullastandard. Etapi 5 lõplik 13 juhtumi ja 15 termini-esinemise kogum on `evaluation/cases.json`; selle päritolu ja ülevaatamise põhimõtted on [evaluation/README.md](evaluation/README.md). Sõltumatut inimeste annotatsiooniga dokumenditeemade hindamist ei ole tehtud ega väideta.

## Etapi 5 lõppkontroll

**56 testi läbisid Windowsis** pärast POS-filtri ja skoorikorrektsiooni lisamist. Eelmine 53 testi kontroll läbis nii Windowsis kui Linuxis; uuemate POS-muudatuste järel Linuxi testi ei korratud. Varasemate masinloetavate tulemuste failid: [Windows](reports/etapp5_tests_windows.json), [Linux](reports/etapp5_tests_linux.json), [HTTP](reports/etapp5_http_checks.json). Testide täislogid on samas kaustas `.log` laiendiga. Uus isoleeritud täisimport ja selle eraldi kordusvalideerimine kinnitasid 42 245 mõistet, 123 612 nimetust, 175 535 lahendatud seost ning kõigi toorkirjete sisu säilimise: [teisendamise lõppkontroll](reports/etapp5_validation.json). POS-filtri kontroll ja jõudluse võrdlus on [etapi 5 aruandes](ETAPP_5.md#pos-filtri-j%C3%A4relhindamine).

Värske Windowsi protsessi ja valmis andmete korral mõõdeti kuut juhtumit (korduvad ja mitmekesised sünteetilised sisendid, 100/1000/10 000 sõna). Iga juhtumi puhul üks esimene päring ja neli kordust. Mitmekesise 10 000 sõna korduste mediaan oli **8,50 s**, p95 **8,79 s**; 65 140 kordumatut võtit ja viis SQL-käsku. Esimene päring oli 8,31 s. See ei sisalda protsessi käivitamist. Tegeliku Uvicorni protsessi käivitamise mediaan kuni `/health` HTTP 200-ni oli **6,36 s** (5 protsessi, p95 6,67 s). OS-i failivahemälu ei tühjendatud.

Töötava Linuxi Dockeri teenuse mitmekesise 10 000 sõna HTTP POST-i koguaeg oli eraldi katses mediaanina **17,91 s**, p95 **28,26 s** (5 päringut juba soojendatud teenusele). Seda ei tohi võrrelda Windowsi CLI-ga kui ainult HTTP lisakulu: nii operatsioonisüsteem kui andmete asukoht ja protsessi olek erinevad. Kõik üksikvaatlused, etapid, päringuplaanid, mälutipp ja keskkonna kirjeldus on [ETAPP_5.md](ETAPP_5.md) kaudu kontrollitavad. Arvud ei ole läbilaskevõime ega suvalise dokumendi viivitusgarantii.

Termini-esinemiste arenduskogumi mikro-precision/recall olid: algkuju **1,000 / 0,467**, lemma **0,923 / 0,800**, lemma+sünonüümid **0,938 / 1,000**. Väike assistendi koostatud ja EMS-i väljadega kontrollitud kogum pole sõltumatu kullastandard; arvud ei tõenda üldist täpsust ega teemade tuvastamise headust. Valevastete juhtum jääb aruandes nähtavaks.

Lõppkontrolli taasesitamiseks projekti juurkaustas:

```powershell
.\.venv-stage1\Scripts\python -m examples.check_stage5
.\.venv-stage1\Scripts\python -m examples.evaluate_stage5
.\.venv-stage1\Scripts\python -m examples.benchmark_stage5 --runs 5
.\.venv-stage1\Scripts\python -m examples.check_stage4 --output reports/etapp5_http_checks.json
.\.venv-stage1\Scripts\python -m examples.benchmark_http_stage5 --runs 5
```

Paigaldus uude keskkonda: `pip install -r requirements-dev.txt -c stage1-requirements-windows.lock.txt` (Linuxis vastav Linuxi fail) ning `python -m nltk.downloader punkt_tab`. Käsurea benchmark kasutab vaikimisi kohalikku `data/` kausta, mitte elava Dockeri teenuse lukustatud `/data` mahtu. HTTP-mõõtmine kasutab töötavat teenust ja eelmise benchmark'i genereeritud faile. `--data-dir`/`--url` lubavad asukohta muuta.

Täieliku uue allalaadimise, impordi ja indeksi ettevalmistuse eraldi mõõtmiseks:

```powershell
.\.venv-stage1\Scripts\python -m examples.preparation_stage5 --data-dir .stage5-preparation-new
```

Vali iga sellise mõõtmise jaoks uus kaust: skript keeldub valmis baasi ülekirjutamisest. Mõõtmine vajab võrku ja lisakettaruumi ning ei uuenda töötava rakenduse baasi. Etapi 5 tegelik ettevalmistuse vaatlus tehti Linuxi konteineris Windowsi töökausta bind-mount'il (eraldi kaust), mitte tootmisliku nimelise mahu peal: [ettevalmistuse aruanne](reports/etapp5_preparation.json). Sellest ühest vaatlusest ei esitata ettevalmistuse p95 hinnangut.
