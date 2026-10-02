# Changelog

## 0.7.17 — 02.10.2026

### Container-Einstellungen
- Festgehalten, dass GTM beim Import **keine** Container-Einstellungen uebernimmt. Der `container`-Block eines Exports beschreibt den Ursprungscontainer; `taggingServerUrls`, Name und Konto-IDs werden verworfen. Beobachtet an einem Import mit gesetzter `taggingServerUrls`: das Feld *Verwaltung → Container-Einstellungen → Server container URLs* war danach leer.
- `validate_container.py` gibt jetzt zusaetzlich zu den Fehlern die Schritte aus, die kein Import setzen kann: Server container URL eintragen, GA4-Tag anlegen, Vorschau vor dem Veroeffentlichen. Bei WEB stattdessen der Hinweis auf Kontoeinstellungen ausserhalb von GTM.
- `references/server-container.md` und der Warnblock in `SKILL.md` ergaenzt.

### Hygiene
- Eine echte Google-Ads-Conversion-ID war als Beispiel in CHANGELOG und Testfixture gelandet. Durch eine erkennbar erfundene Nummer ersetzt. Kundenwerte gehoeren nach `masters/REFERENCE-POLICY.md` nie in dieses Repository, auch nicht als Beispiel.

- Sechs Regressionstests; Gesamterwartung steigt von 248 auf 254.

## 0.7.16 — 02.10.2026

### Server-Container: drei Importfehler abgefangen
Beim ersten von Hand gebauten Server-Container traten nacheinander drei Fehler auf, die alle dieselbe Ursache hatten – Web-Konventionen wurden auf den Server-Container uebertragen:

1. Eingebauter Trigger `2147479553`/`2147479573` statt `2147479574`. GTM: *„Tag references an unknown trigger"*.
2. `conversionId` als `AW-12345678901` im `sgtmadsct`-Tag. GTM: *„File format is invalid / The value must be a positive integer or 0"*. Der Servertag will die nackte Zahl.
3. `tagId` und `triggerId` getrennt gezaehlt und dadurch kollidiert. GTM-Exporte vergeben alle IDs aus einem gemeinsamen Zaehlraum; syntaktisch faellt das nicht auf.

### Neu
- `scripts/validate_container.py` prueft einen beliebigen Container-Export vor dem Import: Trigger-Referenzen gegen den **richtigen** Container-Typ, Variablen-Referenzen, ID-Eindeutigkeit, Format von `conversionId`/`conversionLabel` je Tag-Typ, unersetzte Referenz-Platzhalter, Client-Pflicht im SERVER-Container.
- `references/server-container.md` haelt die belegten Werte und die drei Fallstricke fest, mit Herkunft je Wert.
- Der Build-Abschnitt in `SKILL.md` beginnt jetzt mit einem Warnblock dazu und macht den Pruefschritt vor jedem Import verbindlich – auch fuer generierte Dateien.
- Acht Regressionstests, je einer pro realem Fehler; Gesamterwartung steigt von 240 auf 248.

## 0.7.15 — 02.10.2026

### Build
- `build_web_container.py` kennt `timer_events`, z. B. `{"engagement_1min": 60}` (Eventname → Sekunden). Erzeugt je Schwelle ein `setTimeout` pro Seitenaufruf; bewusst kein GTM-TIMER-Trigger, damit jede Schwelle genau einmal feuert.
- Der Generator warnt dabei, dass Verweildauer ein Engagement-Signal ist und in Google Ads auf sekundaer gehoert. Die Entscheidung bleibt beim Nutzer, die Warnung steht aber in jeder Ausgabe.
- Abgelehnt werden Nicht-Objekte, Sekunden als Text, Werte ausserhalb 1–3600 und ungueltige Eventnamen.
- Sieben Regressionstests; Gesamterwartung steigt von 233 auf 240.

## 0.7.14 — 02.10.2026

### Build
- `build_web_container.py` kennt `link_listeners`, z. B. `{"tel": "click_to_call", "mailto": "contact_email"}`. Bisher liess sich fuer Telefon- und E-Mail-Klicks zwar ein Event im Plan anlegen, aber nichts im Container hat es je gepusht – die Trigger warteten auf dataLayer-Events ohne Absender. Fuer Lead-Websites ohne Shop ist der Telefonklick oft die wichtigste Conversion.
- Der erzeugte Listener delegiert auf `document` und nutzt `closest()`, erfasst also auch nachtraeglich eingefuegte Links; ohne jQuery-Abhaengigkeit.
- Unbekannte Schemata, Nicht-Objekte und ungueltige Eventnamen werden abgelehnt statt still ignoriert.
- Sechs Regressionstests; Gesamterwartung steigt von 227 auf 233.

## 0.7.13 — 02.10.2026

### Build
- `build_web_container.py` kennt `--server-dns-pending`. Ist die sGTM-Custom-Domain beim Hoster beantragt, der CNAME aber noch nicht gesetzt, liess sich bisher kein Container bauen – ein in der Praxis haeufiger Fall, wenn der DNS-Zugang beim Kunden liegt. Der Schalter ueberspringt ausschliesslich die Namensaufloesung und erzeugt eine Warnung.
- Unveraendert streng bleiben: https-Pflicht, Verbot von Zugangsdaten in der URL, Hostpruefung und die Globalitaetspruefung bei literalen IP-Zielen. Fuer eine IP kann es keinen wartenden DNS-Eintrag geben, deshalb greift dort weiterhin der volle Schutz.
- Sechs Regressionstests sichern ab, dass der Schalter nur die Aufloesung lockert; die Gesamterwartung steigt von 221 auf 227.

## 0.7.12 — 02.10.2026

### Auslieferung an fremde Nutzer
- `skills/setup/examples/config.json` ist jetzt eine leere Vorlage. Vorher enthielt sie die Brandingdaten und Preise des Autors; eine Neuinstallation startete damit unter fremdem Namen, und ein ungeprueft erzeugter Kundenbericht konnte mit falschem Absender beim Kunden landen.
- `/setup init` belegt Angebotstexte und Preise nicht mehr vor. Beide kommen ausschliesslich vom Nutzer.
- Der Gestaltungsabschnitt des Kundenberichts beschreibt das Layout als Design-System des Plugins; die Absenderangaben stammen aus `config.json → branding`.
- Keine Verhaltensaenderung fuer bestehende Installationen: `--init` ueberschreibt eine vorhandene `config.json` nicht.

## 0.7.11 — 16.09.2026

### Fachwissen / Entscheidungsqualitaet
- GEO/AI Search um Googles weltweiten Generative-AI-Performance-Bericht in Search Console und OpenAI-Agent-Readiness ergaenzt. Prompt-Stichproben bleiben qualitative Zusatzmessung; ARIA/Agent-Readiness wird nicht als Rankingfaktor dargestellt.
- Tracking bekommt ein deterministisches Completeness Gate mit konkreter Evidenzpflicht. Offene architekturrelevante Fragen, ungeklaerte Eventquellen, Consent-, E-Commerce-, Enhanced-Conversions-, Cross-Domain- oder Serverentscheidungen blockieren den Build statt geraten zu werden.
- Zeitkritische Stape-Wissensbasis aktualisiert: Request-Dimensionierung, Pause-/Grace-Logik und Gateway-Preise werden nicht mehr mit veralteten festen Formeln/Werten beschrieben.

### GTM-Master / reale Produktionsreferenz
- Zwei reale, funktionierende Web-/Server-GTM-Exporte wurden ausschliesslich als Architekturquelle ausgewertet und vor Aufnahme vollstaendig sanitisiert. Originalexporte und Original-Secrets werden **nicht** ausgeliefert.
- Neue Schichten: `masters/production-reference/` (sanitisierte Strukturbelege), `masters/core/` (neutraler Web-/Server-Core als Candidate) und `masters/patterns/` (Eventmuster statt Kundenlogik).
- `reference_guard.py` blockiert bekannte Kundenwerte, secret-artige Konstanten und versehentlich als VERIFIED markierte Candidates.
- `sanitize_gtm_reference.py` und `build_reference_assets.py` erzeugen reproduzierbare, lesbar platzhalterisierte Referenzen/Core-Candidates.
- Core-Master erben **nie** Consent, Eventnamen, IDs, Domains, Labels, Waehrungen, CSS-Selektoren oder Businessentscheidungen des Referenzkunden. Scroll-/Engagement-Events werden insbesondere nicht automatisch zu Ads-/Meta-Conversions.
- Ein Master wird erst nach echtem GTM Import -> Preview -> Re-Export und semantischem Roundtrip mit `gtm_master_verify.py` als VERIFIED akzeptiert. Community-Template-/interne GTM-IDs duerfen sich dabei dynamisch aendern, semantische Aenderungen nicht.

### Security / Release-Integritaet
- `fill_template.py` erkennt die neuen `__PLACEHOLDER__`-Tokens und blockiert Core-Candidates ohne Verified-Manifest oder bewussten Candidate-Bootstrap.
- Meta-CAPI-Access-Tokens werden in Referenzartefakten nie als reale Werte gespeichert; das Toolkit fordert Tokens weiterhin nicht im Chat/Git an.
- `gtm_master_verify.py` schreibt Verified-Manifeste exklusiv und folgt keinem vorbereiteten Symlink; der Schreibpfad ist direkt regressionsgetestet.
- Die Regression wurde auf 15 isolierbare Testblöcke A–O gehärtet. Python-Negativtests prüfen die Produktlogik direkt und behalten gezielte CLI-Smokes; dadurch entfallen flakey Ketten vieler kurzlebiger Child-Prozesse.
- **221/221 Regressionstests** sind in den isolierten Blöcken grün; Python-/Node-Syntax, 15 JSON-Dateien und Reference Guard sind grün. Ein echter Chromium-Lauf bleibt zusätzlich CI-Pflicht.
- Sanitisierungs-/Referenztests, Golden-Master-Tests und Dokumentationsregressionen wurden erweitert.
- Hardening-Nachweise unter `docs/hardening-0.7.11/`.

## 0.7.10 — 15.09.2026

### Security
- Kundenbericht schreibt HTML/PDF jetzt ueber exklusiv erzeugte `.part`-Dateien (`wx`) und prueft den realen Ausgabeordner. Vorbereitete `.part`-Symlinks bzw. symlinkte Ausgabeordner koennen nicht mehr auf fremde Dateien umleiten.
- Remote-Logos laufen auch bei explizitem `--remote-logo` durch die zentrale Public-Network-Policy; der PDF-Browser nutzt dieselbe Netzpolicy.
- Launch-SSL verbindet nicht mehr erneut per Hostname, sondern pinnt den TLS-Socket auf eine unmittelbar zuvor durch `urlguard.py` verifizierte IP; SNI/Zertifikatspruefung bleibt auf dem Originalhost.
- Browser-Netzpolicy blockiert zusaetzlich 6to4 (`2002::/16`) konservativ als Transition-Mechanismus.
- `doctor.py --init` setzt neue Toolkit-Verzeichnisse auf POSIX best-effort auf `0700` und `config.json` auf `0600`.

### Correctness
- Consent-Szenarien initialisieren jetzt alle Summary-Felder (`hits`, `cookies_after`, Storage etc.) bereits vor der Navigation. Fruehe Abbrueche wie `CMP_BUTTON_NICHT_GEFUNDEN` koennen die Abschlussausgabe daher nicht mehr mit `TypeError` abbrechen.
- Alte harte `gcs≠G100`/`G111`-Decodierungsregeln wurden auch aus Skill und Google-Referenz entfernt; Runtime und Wissensbasis behandeln `gcs`/`gcd` konsistent als codierte Evidenz.
- `server_container_url` akzeptiert nur global erreichbare IPs; Shared Address Space (`100.64.0.0/10`) und andere nicht globale Ziele werden abgelehnt. Resolver ist fuer hermetische Tests injizierbar.

### Tests / Release-Integritaet
- 164 → **178 Kern-Regressionstests**, inklusive `.part`-Symlink-Overwrite, symlinktem Ausgabeordner, privatem Remote-Logo, Consent-Szenariovertrag, 6to4, TLS-IP-Pinning und echtem hermetischem `architecture=server`-Build.
- Korrektur zum 0.7.9-Testbericht: Der damalige Tracking-Builder-Test enthielt trotz `Q1 CLOSED` noch einen realen DNS-Pfad und konnte bei `out=None` ohne Assertion gruen bleiben. Der Erfolgspfad wird jetzt direkt mit injiziertem Resolver gebaut und zwingend asserted.
- Chromium-E2E bleibt Teil der CI. In der lokalen Build-Sandbox konnte `npm ci` wegen fehlendem Registry-/Netzzugriff nicht abgeschlossen werden; der Browserlauf ist deshalb lokal weiterhin `NOT_VERIFIED`.
- Hardening-Nachweise unter `docs/hardening-0.7.10/`.

## 0.7.9 — 15.09.2026

### Security
- Browser-Netzpolicy gegen IPv4-mapped IPv6 und weitere nicht-global routbare/special-use Netze gehärtet; WebSockets werden über `routeWebSocket()` geprüft, Service Worker im Consent-Audit für die Request-Interception blockiert.
- `start` und `wissen-update` sind wie die übrigen Workflow-Skills user-only (`disable-model-invocation: true`).
- Consent- und SiteOne-Rohoutputs werden auf POSIX restriktiver geschrieben/nachgehärtet.

### Correctness
- Consent-Audit lässt Tracking-Libraries laden und blockiert im sicheren Standardmodus nur Collection-Requests. Dadurch sabotiert das Audit nicht mehr GTM/gtag/Meta-Library-Ausführung.
- Browser-/CMP-Fehler (`status: unknown`) werden nicht mehr fachlich ausgewertet.
- Harte `gcs`-String-Decodierung entfernt; Google-Consent-Parameter werden als codierte Beobachtung behandelt.
- LocalStorage, SessionStorage und IndexedDB werden vor/nach Consent unterschieden und als Delta bewertet.
- Doctor findet Playwright auch im Claude-Plugin-Root.
- CSR-only ist kein pauschales `kritisch` mehr; Bewertung ist bot-/evidenzspezifisch.

### Tests / CI
- 137 → **164 Kern-Regressionstests**, inklusive mapped IPv6, Special-Use-Netzen, Consent-Pure-Logic, Storage, Doctor-Plugin-Root, vollständigem gemocktem Launch-Erfolgspfad und SiteOne-Scope.
- Neuer echter Chromium-Test `tests/browser_security.mjs`; CI installiert Chromium und prüft HTTP-/mapped-IPv6-/WebSocket-Blockaden.
- Hardening-Nachweise unter `docs/hardening-0.7.9/`.

## 0.7.8 — 15.09.2026

### Security
- **Browser-Netzwerkgrenze tatsächlich implementiert.** `lib/netpolicy.mjs` prüft Schema, Port, Zugangsdaten, IPv4- und IPv6-Bereiche, lokale Namen und löst Hostnamen auf. Zwei Schichten: Start-URL vor `page.goto()`, danach `context.route("**/*")` für Navigation, Subressourcen, XHR/fetch und Frames. **Korrektur in 0.7.9:** Der damalige Tracker-Blocker blockierte auch Loader wie `gtm.js`/`fbevents.js`; vollständige Messbarkeit war daher noch nicht gegeben.
- **Mutierende Skills sind user-only.** `seogeo`, `tracking-audit`, `launch`, `kundenbericht` und `setup` tragen `disable-model-invocation: true`.

### Fixed
- **Die 0.7.7-Sicherheitsdokumentation beschrieb eine `ctx.route()`-Sperre, die es im Code nicht gab.** Ein Patch-Anker aus der 0.7.5-Runde hatte nie gegriffen, das Ergebnis wurde nicht geprüft, die Maßnahme trotzdem als erledigt dokumentiert.
- SiteOne-Test war eine Attrappe: Er prüfte nur, dass ein Fehlertext *fehlt*, während der Prozess an der DNS-Auflösung starb. Jetzt wird belegt, an welcher Stelle der Abbruch erfolgt.

### Tests
- 94 → **137 Tests**. Neu: 23 für die Netzwerk-Policy (hermetisch, ohne Browser), 15 für Skill-Invocation, plus die reparierten SiteOne-Tests.
- Abschnitt I prüft den Quelltext von `consent_test.mjs` darauf, dass die Policy aufgerufen wird **und vor der ersten Navigation steht** — die Gegenmaßnahme gegen Patches, die nie greifen.
- `05-TEST-REPORT.md` wird aus dem echten Lauf erzeugt statt von Hand gepflegt.

### Documentation
- `docs/hardening-0.7.8/` mit sieben Berichten. `CLOSED` steht nur noch dort, wo Code, Test und grüner Lauf vorliegen; alles andere heißt `OPEN` oder `PARTIALLY_FIXED`.
- Offen und so benannt: Consent-Interpretation, Storage-Bewertung, Browser-Tests in CI, Launch-Integrationstest, Dateirechte, CSR-Regeln, Cowork, Playwright-Upstream.

## 0.7.7 — 15.09.2026

### Fixed
- `doctor.py` prüfte Versionen nicht: Python bekam ✅ unabhängig von der Version, der Hinweistext nannte „Node ≥ 18" gegen `engines: >=20`. Mindestversionen stehen jetzt zentral als `MIN_NODE`/`MIN_PYTHON`, die Parser sind testbar, Playwright ist in vier getrennte Prüfungen zerlegt, die SiteOne-Version wird ausgelesen. **Der in 0.7.5 gemeldete Fix für diesen Punkt war nie eingebaut worden.**

### Security
- `siteone.py`: `--allowed-domain-for-crawling=` akzeptierte jeden Wert. Jetzt Hostname-Syntax, kein Wildcard, keine Zugangsdaten, keine privaten Adressen; eine fremde Domain endet mit `REVIEW_REQUIRED` und muss über `--zusatz-domain` freigegeben werden. Argumentprüfung läuft vor jeder DNS-Auflösung.
- `consent_test.mjs`: Der fest verdrahtete macOS-User-Agent „Chrome/128.0" ist entfernt. Er passte weder zur Chromium-Version noch zum Betriebssystem und konnte Messergebnisse verfälschen.

### Documentation
- Unbelegte Aussagen zurückgezogen: PageSpeed-Kontingente („ohne Limit", „25.000/Tag"), SiteOne „Stand 2.6.1", Cowork „läuft auf deinem Rechner, nicht in der Cloud". Die Kurzform `/seogeo` wird nicht mehr als garantiert beschrieben.
- Sieben Hardening-Berichte erstmals tatsächlich im Paket (in 0.7.6 war das Verzeichnis leer). Die Berichte sind in 0.7.8 durch eine überarbeitete Fassung ersetzt worden, weil einer davon eine Maßnahme als erledigt beschrieb, die im Code fehlte.

### Tests
- 66 → **94 Tests**. Neu: Doctor-Versionslogik (15), Dokumentation gegen Code (7), Crawl-Scope (4), DNS-Fälle mit injiziertem Resolver (3).
- Damalige Zielsetzung: Testsuite hermetisch ohne Internet/DNS. **Korrektur in 0.7.9:** einzelne SiteOne-Pfade verwendeten weiterhin den echten Resolver; diese wurden erst in 0.7.9 vollständig aus den Success-Tests entfernt.
- Zwei Scheinbeweise aus 0.7.6 repariert: drei SiteOne-Tests bestanden, weil argparse vorher abbrach, nicht weil die Prüfung griff.

### CI
- `.github/workflows/test.yml`: Python 3.10, Node 20, `npm ci`, Syntaxprüfungen, Regressionstests, `npm audit` als Informationssignal. Keine Secrets, keine externen APIs.

## 0.7.6 — 15.09.2026

### Fixed
- `launch_check.py`: `add()` war in 0.7.5 beim Umbau auf den zentralen URL-Validator verlorengegangen. Jeder Lauf endete in `NameError: name 'add' is not defined`. Die Funktion ist wiederhergestellt, das Datenmodell (`level`/`id`/`titel`/`detail`) unverändert. Regressionstest gegen lokalen Fixture-Server.
- `render_report.mjs`: Die in 0.7.5 eingeführten Enum-Listen waren erfunden und widersprachen `references/audit-schema.md` sowie der Anzeigelogik derselben Datei. Das mitgelieferte `beispiel-seogeo.json` wurde dadurch abgelehnt. Die Listen stammen jetzt wörtlich aus dem Schema: `typ` seogeo/seo/geo/tracking/launch, `status` gut/mittel/kritisch/nicht_geprueft, `prioritaet` kritisch/hoch/mittel/niedrig.
- `siteone.py`: `--max-depth 0` (der Standardwert, Bedeutung „unbegrenzt") wurde von der neuen Wertebereichsprüfung abgelehnt.

### Security
- `siteone.py`: Der Kommandodruck gab `--http-auth=user:pass` im Klartext aus. Argumente mit `--http-auth`, `--password`, `--token` und `--key` werden jetzt als `[REDACTED]` ausgegeben.
- `fill_template.py`: Der Scan auf auffälliges Custom-HTML im Master läuft jetzt bei jedem Aufruf, auch bei `--list` — vorher erst beim Befüllen und damit zu spät.

### Tests
- Neue Testsuite `tests/run_tests.py`: 66 Tests über Launch-Check, URL-Guard, Kundenbericht, Tracking-Builder, GTM-Master und SiteOne-Wrapper. Standardbibliothek, kein Framework, lokaler Fixture-Server.

### Documentation
- Für 0.7.6 waren Hardening-Berichte angekündigt, aber **nie ausgeliefert** – das Verzeichnis war leer und überlebte das Packen nicht. Nachgeholt in 0.7.7.

## 0.7.5 und früher
Siehe die Auditberichte zu 0.7.2 bis 0.7.5.
