
Ehita selles repositooriumis tekstikaeve kodutöö jaoks toimiv kohalik EMS-i otsingu- ja märksõnastamise rakendus. Ära piirdu plaani või näidiskoodiga: realiseeri, käivita, kontrolli ja dokumenteeri lahendus.

## Eesmärk ja allikad

Kodutöö nõue:
„Laadige EMS-i MARCXML-andmed alla ja koostage toimiv kohalik otsingulahendus (nt CSV/SQLite). Dokumenteerige teisendamine, päringud ja kontroll; vältige aeglast päringut iga sõna kohta eraldi. Kui EMS-i semantiline otsing kasutab LLM-i, märkige see selgelt.”

Allikad:
- EMS-i MARCXML: https://ems.elnet.ee/temp/ems_marc_tais.xml
- EMS-i juhend: https://ems.elnet.ee/abi.php
- DuckDB XML-laiendus: https://duckdb.org/community_extensions/extensions/webbed

Rakendus peab võimaldama:
1. Otsida EMS-ist sõna või fraasi järgi.
2. Anda ette eestikeelne tekst ja saada kuni 10 põhjendatud normitud EMS-i märksõna.
3. Sisestada teksti tekstikasti või laadida üles UTF-8 `.txt` fail.
4. Esimesel käivitamisel valmistada EMS-i kohalik andmebaas automaatselt ette.
5. Järgmistel käivitamistel kasutada olemasolevat andmebaasi ilma uut allalaadimist või EMS-i lemmatiseerimist tegemata.

## Tehnilised valikud

- Python.
- DuckDB püsiva andmehoidlana.
- DuckDB `webbed` laiendus MARCXML-i lugemiseks.
- EstNLTK/Vabamorf eestikeelse teksti morfoloogiliseks analüüsiks ja lemmatiseerimiseks.
- FastAPI ning lihtne serveripoolne HTML-liides. Eraldi JavaScripti raamistikku pole vaja.
- Docker ja Docker Compose.
- Üks rakenduse protsess ja üks veebitööline esimeses versioonis.
- Püsiv andmemaht algfaili, andmebaasi ja metaandmete jaoks.
- Põhiversioon ei kasuta LLM-i, embedding-mudelit ega välist tekstianalüüsi API-t.

Kontrolli tööriistade praegust ametlikku dokumentatsiooni. Ära eelda API-de, XML-struktuuri ega laienduse parameetrite kuju mälu põhjal. Fikseeri töötavad sõltuvuste versioonid.

Kui `webbed` ei suuda EMS-i faili korrektselt töödelda, dokumenteeri konkreetne takistus ning kasuta impordiks voogpõhist Python XML-parserit. DuckDB peab jääma andmehoidlaks.

## Töökorraldus

Tee töö järgmistes etappides:
1. Allikate ja tehnilise teostatavuse kontroll.
2. Andmete import ja kontroll.
3. Keeleline eeltöötlus ning otsing.
4. Veebiliides ja Docker.
5. Testid, jõudlusmõõtmised ja dokumentatsioon.

Iga etapi järel esita lühidalt:
- mis valmis;
- kuidas seda kontrollisid;
- millised probleemid või piirangud jäid.

Vaikimisi jätka järgmise etapiga iseseisvalt. Kui annan eraldi korralduse peatuda kindla etapi järel, järgi seda. Küsi ainult küsimusi, mis päriselt takistavad töö jätkamist; muud valikud tee mõistlikult ja dokumenteeri.

## 1. Kontrolli tegelikku MARCXML-i

Laadi algfail alla ning uuri selle tegelikku struktuuri enne andmemudeli lõplikku tegemist.

Selgita välja:
- XML-i nimeruumid;
- kirje ID asukoht;
- eelistatud nimetuste ja eri märksõnatüüpide väljad;
- sünonüümide ja ingliskeelsete vastete eristamine;
- eraldi äraviitekirjete võimalik esitus;
- mõistetevahelised seosed ning nende siht-ID-d;
- valdkonnad ja selgitused;
- kustutatud või muude eristaatustega kirjete esitus, kui need failis esinevad.

EMS-i juhendi väljakirjeldus on lähtekoht, kuid kontrolli seda failist.

Säilita korduvad väljad, indikaatorid, alamväljade järjekord ja nende kuuluvus konkreetse välja alla. Ära moodusta sõltumatuid loendeid, mille kokkupanekul võivad nimetused ja viited nihkesse minna.

Hoia EMS-i ID-sid tekstina ja säilita algkujud.

## 2. Esmakäivitus ja püsivus

Rakenduse käivitamisel:
- kui sobiv valmis andmebaas on olemas, kasuta seda;
- kui andmebaasi pole, käivita ettevalmistus;
- ära kontrolli iga käivitusega võrgust uut EMS-i versiooni;
- ühildumatu skeemi või töötlusversiooni korral anna arusaadav teade ning selge taastamise juhis.

Ettevalmistus peab:
1. Laadima XML-i ajutisse faili, kasutades ajalõppu ja piiratud korduskatseid.
2. Kontrollima, et vastus on oodatud XML, mitte HTML-vealeht.
3. Salvestama algfaili, allalaadimise aja, allika URL-i ja SHA-256 kontrollsumma.
4. Ehitama andmebaasi ajutise failina.
5. Tegema andmete kontrolli.
6. Võtma valmis andmebaasi kasutusele alles pärast edukat kontrolli.

Ebaõnnestunud uuendamine peab säilitama eelmise toimiva andmebaasi. Esmakordne ebaõnnestumine peab lõppema selge veateatega.

Paku dokumenteeritud käsureakäsud:
- andmete ettevalmistamine;
- andmete teadlik uuendamine;
- andmete valideerimine;
- jõudluse mõõtmine.

Uuendamine toimub töötava veebiprotsessi peatamise ajal, et vältida faililukke ja andmebaasi vahetamise probleeme.

## 3. Andmemudel

Hoia eraldi:
- imporditud MARC-väljade kontrollitav algandmekiht;
- mõisted;
- nimetused ja sünonüümid;
- mõistetevahelised seosed;
- valdkonnad ja nende seosed mõistetega;
- otsinguks ettevalmistatud nimetused;
- allika ja töötluse metaandmed.

Otsingunimetuse juures säilita vähemalt:
- nimetuse ID;
- mõiste EMS ID;
- algtekst;
- keel;
- nimetuse liik;
- normaliseeritud algkuju;
- järjestatud lemmad;
- lemmade järjestusest üheselt moodustatud võti;
- sõnede arv.

Üks normaliseeritud nimetus või lemmavõti võib viidata mitmele mõistele. Ära kirjuta neid vasteid üksteisega üle.

Lahendamata äraviited ja seoseviited peavad olema kontrollaruandes nähtavad.

## 4. Keeleline eeltöötlus

Lemmatiseeri EMS-i eestikeelsed nimetused ja sünonüümid ettevalmistuse ajal ühe korra ning salvesta tulemused.

Kasuta EMS-i ja kasutaja teksti jaoks sama normaliseerimist:
- Unicode’i normaliseerimine;
- ühtne tõstukäsitlus;
- kooskõlaline sõnestamine;
- kooskõlaline lemmaesitus.

Säilita õ, ä, ö ja ü. Ära kasuta inglise Porter-tüvestajat eesti lemmatiseerimise asemel.

Mitmesõnalisi termineid töötle fraasidena ja säilita sõnajärg. Kasutaja teksti analüüsi lause kontekstis. Fraasivasted ei tohi ulatuda üle lausepiiri.

Ära eemalda stoppsõnu enne fraasisobitamist. Ära lõhu liitsõnu vaikimisi eraldi märksõnadeks.

Ära lemmatiseeri ingliskeelseid nimetusi eesti analüsaatoriga. Ingliskeelsed vasted võivad olla EMS-i otsingus leitavad normaliseeritud algkuju järgi, kuid automaatne märksõnastamine keskendub eestikeelsele tekstile.

Määra ja dokumenteeri mitmese morfoloogilise analüüsi käsitlus. Väldi kõigi võimalike lemmakombinatsioonide piiramatut genereerimist. Säilita ka algkujupõhine sobitamine.

Laadi analüsaator protsessi jooksul üks kord ning taaskasuta seda.

## 5. Efektiivne otsing

Ära tee iga tekstisõna või fraasikandidaadi kohta eraldi SQL- ega võrgupäringut.

Esialgne lahendus:
1. Analüüsi sisendtekst.
2. Moodusta lausesisesed järjestikused fraasikandidaadid.
3. Kasuta EMS-is tegelikult esinevaid fraasipikkusi.
4. Eemalda korduvad otsinguvõtmed, säilitades esinemiskohad ja sagedused eraldi.
5. Anna kandidaadid DuckDB-le ühe ajutise tabeli või registreeritud tabelina.
6. Ühenda need otsingunimetustega partiiviisiliselt.
7. Lisa leitud mõistete detailid ühiste päringutega.

Kontrolli päringuplaani ja mõõda aega. Ära lisa indekseid automaatselt: põhjenda neid konkreetsete päringutega.

Kui mõõtmine näitab vajadust, kasuta alternatiivina protsessi käivitamisel laaditavat mälus olevat fraasiindeksit. Võrdle seda sama sisendi peal partiiviisilise DuckDB-lahendusega.

Käsitsi otsing peab toetama vähemalt normaliseeritud täpset ja lemmatiseeritud fraasivastet. Prefiksiotsing on soovitatav; sõnaosaotsing võib olla lisavõimalus. Näita kasutajale otsingu liiki.

## 6. Märksõnade valimine ja selgitatavus

Tagasta kuni 10 eri EMS-i mõistet; tulemuste arvu peab saama muuta mõistliku ülempiirini.

Ära täida nimekirja nõrkade tulemustega ainult selleks, et saada kümme vastet. Ühesõnalise sisendi puhul võib tulemuseks olla üks vaste või null vastet.

Kasuta läbipaistvat reeglipõhist järjestamist, arvestades:
- täpset algkujupõhist fraasivastet;
- lemmatiseeritud fraasivastet;
- eelistatud nimetuse või sünonüümi kaudu leidmist;
- täieliku pikema fraasi eelistamist selle sees olevale üldisele üksiksõnale;
- esinemissagedust, vältides piiramatut korduste mõju.

Koonda sama mõiste eri nimetuste kaudu leitud vasted.

Iga tulemuse juures näita:
- ametlikku EMS-i nimetust;
- EMS ID-d ja linki;
- tekstist leitud väljendit;
- vasteliiki;
- esinemiste arvu;
- vähemalt ühte algteksti katkendit;
- skoori lühikest põhjendust.

Ära esita reeglipõhist skoori tõenäosuse või protsentuaalse kindlusena.

Säilita algteksti positsioonid nii, et katkend ja esiletõstmine viitaksid õigele kohale ka normaliseerimise järel.

Laiemad, kitsamad ja seotud mõisted kuva eraldi lisainfona. Ära nimeta neid tekstist leitud vasteteks, kui otsest vastet pole.

Selgita liideses, et lahendus leiab sõnastikupõhiseid termineid ega taga dokumendi kõigi põhiteemade tuvastamist. Märgi selgelt, et LLM-i ei kasutata.

## 7. Veebiliides ja sisendid

Loo lihtne eestikeelne liides kahe vaatega:
- „Otsi EMS-ist”
- „Leia tekstist märksõnad”

Märksõnastamise vaates:
- tekstikast;
- `.txt` faili valimine;
- tulemuste ülempiiri valik, vaikimisi 10;
- töötluse kestus;
- tulemused koos põhjendustega.

Kui tekstikast ja fail on mõlemad täidetud, anna selge valideerimisteade.

Toeta UTF-8 ja UTF-8 BOM-iga faile. Vigase kodeeringu, tühja sisendi ja liiga suure faili korral näita arusaadavat teadet. Sea dokumenteeritud ja seadistatav sisendisuuruse piir.

Ära salvesta kasutaja tekste vaikimisi püsivalt ega kirjuta nende sisu logidesse. Kuva kasutaja sisestatud tekst HTML-is turvaliselt.

## 8. Docker ja korratavus

Tavapärane käivitamine peab olema võimalik käsuga:
`docker compose up --build`

Esimesel käivitusel teeb rakendus andmete ettevalmistuse; järgmistel kasutab püsivat andmemahtu.

Paigalda DuckDB laiendus ja vajalikud keeleressursid võimaluse korral image’i ehitamisel. EMS-i andmestik laadi esmasel käivitamisel püsivasse andmemahtu.

Pärast edukat ettevalmistust peab otsing töötama internetiühenduseta.

Paku ka ilma Dockerita käivitamise juhised.

## 9. Kontroll ja testid

Lisa sisulised automaattestid:
- korduvad MARC-väljad ja puuduvad alamväljad;
- indikaatorite ja keelte eristamine;
- sünonüümilt normitud mõistele jõudmine;
- käändevormide sobitamine;
- mitmesõnalise termini sobitamine;
- lausepiiri ületava valevaste vältimine;
- mitme mõiste säilimine sama lemmavõtme korral;
- tulemuste koondamine;
- vigane ja tühi sisend;
- valmis andmebaasi taaskasutamine;
- ebaõnnestunud uuendamise korral vana andmebaasi säilimine.

Tavapärased testid peavad kasutama väikseid kohalikke näidisandmeid ega tohi nõuda kogu EMS-i allalaadimist. Hoia pärisandmestiku integratsioonikontroll eraldi.

Koosta teisendamise kontrollaruanne:
- lähtekirjete ja imporditud kirjete arv;
- mõistete ja nimetuste arv liikide ning keelte kaupa;
- puuduvad või korduvad ID-d;
- lahendamata viited;
- välistatud kirjete põhjused;
- valimkirjete võrdlus algse XML-iga.

Koosta väike käsitsi üle vaadatud hindamiskogum ja võrdle:
1. normaliseeritud algkujupõhist sobitamist;
2. lemmatiseeritud sobitamist;
3. lemmatiseeritud sobitamist koos sünonüümidega.

Erista tekstis esineva termini leidmise hindamine dokumendi teemade hindamisest. Ära esita enda genereeritud ootusi sõltumatu kullastandardina.

## 10. Jõudlus

Mõõda eraldi:
- allalaadimine;
- XML-i import;
- EMS-i lemmatiseerimine;
- rakenduse käivitus;
- sisendteksti keeleanalüüs;
- kandidaatide moodustamine;
- sobitamine ja andmebaasipäringud;
- kogu päringu kestus.

Kasuta ligikaudu 100, 1000 ja 10 000 sõnaga sisendeid. Mõõda esimest ja korduvaid päringuid eraldi. Raporteeri korduste arv, mediaan, p95 ning testkeskkond.

Ära mõtle mõõtmistulemusi välja. Kui mõni kontroll ei ole keskkonnas võimalik, ütle täpselt, mis jäi kontrollimata.

## 11. Dokumentatsioon ja valmiskriteeriumid

README peab sisaldama:
- lahenduse eesmärki ja piiranguid;
- arhitektuuri ning andmemudelit;
- esmakäivituse ja korduvkäivituse käitumist;
- Dockeriga ja Dockerita käivitamist;
- uuendamist ning taastamist;
- MARCXML-i teisendusreegleid;
- lemmatiseerimise ja mitmetähenduslikkuse käsitlust;
- tegelikult kasutatavate partiipäringute näiteid;
- järjestamisreegleid;
- kontrolli- ja jõ