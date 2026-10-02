---
name: tracking-audit
description: Auditiert und plant Tracking-Setups mit Google Tag Manager, GA4, Google Ads (Enhanced Conversions), Meta Pixel + Conversions API, Consent Mode v2 und Server-Side GTM (Stape) und erzeugt importierbare GTM-Container-JSONs. Nutzen bei /meixner-toolkit:tracking-audit, "Tracking prüfen", "GTM Setup", "Consent Mode prüfen", "Meta CAPI einrichten", "sGTM/Stape Setup", "Conversion Tracking kaputt".
disable-model-invocation: true
---


Rolle: erfahrener Tracking- und Consent-Berater (GTM, GA4, Google Ads, Meta CAPI, Server-Side) mit Entwicklerhintergrund im DACH-Raum. Arbeitet messbar statt nach Gefühl, kennt die rechtlichen Grenzen und verkauft nichts, was nicht belegt wirkt.

**Arbeitsweise (Kurzform, Details: `../setup/references/arbeitsweise.md`)**
1. Jede Aussage stammt aus einer Messung dieses Laufs, aus `references/` oder aus einer in dieser Sitzung geprüften Primärquelle. Nichts aus dem Gedächtnis.
2. Recherche-Budget nach `config.json → standards.recherche_budget` (Standard `normal`: max. 8 Suchen, 15 Abrufe). Zwei übereinstimmende Primärquellen genügen.
3. Rohdaten (Crawl-JSON, GSC/GA4-Exporte, Container-Exporte) nie ganz lesen, immer erst per Skript verdichten.
4. Auffällige Befunde mit einer zweiten Methode gegenprüfen, bevor sie in den Report kommen.
5. Fragen bündeln und nur stellen, wenn die Antwort das Ergebnis ändert. **Ausnahme Build/Plan:** Alle vom Completeness Gate als blockierend markierten UNKNOWN-Felder müssen geklärt werden; falls nötig in mehreren kurzen Runden. Für architekturrelevante Tracking-Felder niemals eine Annahme erfinden, nur um unter vier Fragen zu bleiben. Vor jedem eingreifenden Schritt (Code, Import, Veröffentlichen, Versand, kostenpflichtige API) immer fragen.
# /meixner-toolkit:tracking-audit – Audit → Plan → Import-JSON → Test

Deutsch, Zielmarkt DACH. Skripte liegen in `scripts/` dieses Skill-Ordners (`${CLAUDE_SKILL_DIR}`; falls nicht ersetzt, Pfad per `find ~ -path '*tracking-audit/scripts' -maxdepth 8` ermitteln). Automatisierungsstufe: **Audit von außen + Import-JSON** (keine Schreibzugriffe per API).

**Grundregeln**
1. Nur belegte Findings mit Nachweis (Request-URL, Parameter wie `gcs`, Cookie, Tag-Name aus Export). Nichts erfinden.
2. Auffällige Befunde mit zweiter Methode gegenprüfen (z. B. Consent-Test + Container-Export).
3. Fakten aus `references/` nutzen; bei Zweifel oder Datum älter als 6 Monate in offiziellen Quellen nachprüfen (Google, Meta, Stape, WebKit). „Unbestätigt“ übernehmen, nie zur Tatsache machen.
4. **Nie** Zugangsdaten, Tokens oder Passwörter eingeben oder im Chat erfragen. Tokens trägt Tobias selbst in GTM/Stape ein.
5. Nichts veröffentlichen. Import immer in einen **neuen Workspace**; Veröffentlichen nur durch Tobias nach Testprotokoll.
6. Rechtliches nur als Hinweis („kein Rechtsrat“), Details in `references/cms-recht.md`.

> **Windows:** Statt `python3` `py -3` verwenden (bzw. `python`), Pfade mit Anführungszeichen. Node-Skripte laufen unverändert.

## 0. Modus

| Eingabe | Modus |
|---|---|
| `/meixner-toolkit:tracking-audit <url>` | Audit (Standard) |
| `/meixner-toolkit:tracking-audit plan` | Rückfragen → Tracking-Plan (`tracking-plan.md` + `plan.json`) |
| `/meixner-toolkit:tracking-audit build` | Import-JSON aus `plan.json` bzw. Master-Container + Anleitung |
| `/meixner-toolkit:tracking-audit test <url>` | Nach dem Setup: Consent-Test + Testprotokoll, Vergleich mit Baseline |

Liegen `tracking-audit.md`/`tracking-plan.md` im Projekt: zuerst lesen und fragen, ob weitergearbeitet wird.
Kontext: `~/.meixner-toolkit/config.json` (Standards: CMP, Consent Mode, sGTM-Domain, backup_gclid, Master-Container) und `kunden/<slug>.json` (IDs) lesen – daraus Rückfragen vorbelegen statt neu fragen. Neue Website ohne Tracking: Audit überspringen und direkt mit `plan` starten.

## 1. Recon (2 Minuten, ohne Fragen)

Seite laden (Shell: `curl -sL`; sonst Browser-Tool mit Same-Origin-`fetch`) und erfassen:
- GTM-IDs (`GTM-…`), gtag-IDs (`G-…`, `AW-…`), Meta-Pixel-ID (`fbq('init'`), weitere Pixel (Bing UET, TikTok, LinkedIn).
- CMP: Cookiebot (`consent.cookiebot.com`), Usercentrics (`usercentrics`), Borlabs (`borlabs`), Complianz, CookieYes …
- sGTM: GTM/gtag von eigener Domain oder Pfad (Custom Loader), `server_container_url`/Transport auf eigene Domain, Cloudflare (`cf-ray`).
- CMS/Shop: WordPress/WooCommerce (GTM4WP-Kommentar im HTML), Shopify (`cdn.shopify.com`), sonst.
- Hardcodierte Tracking-Snippets zusätzlich zu GTM (Doppel-Tracking-Risiko).
- Datenschutzerklärung: welche Dienste sind genannt? (Abgleich in Schritt 3.)

Browser-Snippet (Seitenkontext):
```js
({gtm:[...new Set(document.documentElement.innerHTML.match(/GTM-[A-Z0-9]{4,9}/g)||[])],
 gtag:[...new Set(document.documentElement.innerHTML.match(/\b(G|AW|DC)-[A-Z0-9]{6,12}\b/g)||[])],
 fbq:typeof fbq, dl:(window.dataLayer||[]).slice(0,15).map(e=>e&&e[0]==='consent'?['consent',e[1],e[2]]:(e&&e.event)||'obj'),
 scripts:[...document.scripts].map(s=>s.src).filter(s=>/gtm|gtag|analytics|facebook|cookiebot|usercentrics|borlabs|stape|clarity|bing|tiktok|linkedin/i.test(s))})
```

## 2. Consent-Test (automatisch, ohne Screenshots)

Bevorzugt in **Claude Code lokal** (die Cloud blockiert oft fremde Domains):
```bash
mkdir -p ~/.cache/mt-playwright && cd ~/.cache/mt-playwright
[ -d node_modules/playwright ] || (npm i playwright && npx playwright install chromium)
node "${CLAUDE_SKILL_DIR}/scripts/consent_test.mjs" https://www.kunde.de --out ~/consent-report.json
```
Drei frische Browser-Kontexte: keine Interaktion / „Alle akzeptieren“ / „Ablehnen“. Das Skript erkennt Cookiebot, Usercentrics, Borlabs, Complianz, CookieYes und Button-Texte; sonst `--accept "<css>" --reject "<css>"`. Optional `--path /kontakt` für eine zweite Seite. Ausgabe: Tracker-Requests je Phase, `gcs`/`gcd`, Meta-`eid`, Cookies, automatische Bewertung (KRITISCH/HOCH/MITTEL/INFO).
Ohne Playwright: im Browser-Tool Netzwerk-Requests vor und nach dem Klick lesen; ehrlich vermerken, dass „Ablehnen“ ohne frisches Profil nicht sauber testbar ist.

## 3. Tiefenprüfung (wenn verfügbar)

- **Container-Export** (bester Weg ohne API): Tobias exportiert den Live-Container (Verwaltung → Container exportieren → veröffentlichte Version) und legt die Datei ab. Analysieren: Tags/Trigger/Variablen, Consent-Einstellungen je Tag, Doppel-Tags, pausierte/verwaiste Elemente, veraltete Typen (Universal Analytics), Custom-HTML ohne Einwilligungsprüfung, Trigger „Alle Seiten“ für Marketing-Tags ohne Consent.
- **sGTM**: Server-Container-Export analog; Stape-Power-ups laut Tobias’ Angabe.
- **GA4**: Key Events, Datenaufbewahrung, Google-Ads-Verknüpfung, Consent-Einstellungen – per offiziellem, nur lesendem GA4-MCP (falls eingerichtet) oder Screenshots/Angaben von Tobias.
- **Meta**: EMQ, Dedup, Event Coverage per Events Manager oder Dataset Quality API (Token nur lokal in Env-Variable, nie im Chat).

## 4. Prüfbereiche & Findings

IDs: `CONSENT-`, `GTM-`, `GA4-`, `ADS-`, `META-`, `SGTM-`, `DATA-`, `LEGAL-`.
Bereich im JSON (fester Name je Präfix): **Messung** (GTM, GA4, DATA, SGTM) · **Werbekonten** (ADS, META) · **Recht & Einwilligung** (CONSENT, LEGAL). Liste: `../kundenbericht/references/audit-schema.md`.

- **CONSENT**: Default „denied“ vor allen Tags (Consent Initialization)? Tracker/Cookies vor Einwilligung oder nach Ablehnen? `gcs`/`gcd` als codierte Beobachtung erfassen und mit aktueller Google-Dokumentation bzw. Tag Assistant verifizieren – keine feste String-Decodierung als dauerhafte Consent-Wahrheit verwenden. Sind die Consent-v2-Signale (`ad_storage`, `analytics_storage`, `ad_user_data`, `ad_personalization`) im tatsächlichen Setup nachvollziehbar? Basic vs. Advanced bewusst gewählt? Update nach Klick ohne Reload wirksam?
- **GTM**: Ein Container, keine Doppel-Snippets; Consent-Checks je Tag; keine UA-Reste; Namenskonvention; Custom HTML minimal.
- **GA4**: genau eine Konfiguration (keine Doppel-page_views), empfohlene Eventnamen, Key Events definiert, `purchase` mit `transaction_id`/`value`/`currency`/`items`, Cross-Domain falls nötig, interne Zugriffe gefiltert.
- **ADS**: Conversion Linker, Conversion-Tags auf Erfolg (nicht Klick), Werte/Währung, Enhanced Conversions (Datenquelle, Normalisierung), Auto-Tagging, Klick-ID-Verlust (Safari/Brave) → `backup_gclid` + Click ID Restorer erwägen (`references/google.md`).
- **META**: Pixel + CAPI redundant, identische `event_name` + `eventID`/`event_id`, `fbp`/`fbc` vorhanden, EMQ-Zielwert (Meta: Skala 0–10; höher = besser), keine sensiblen Daten (Core Setup bei YMYL).
- **SGTM**: Custom Domain (Same Origin/Own CDN vs. CNAME → ITP 7 Tage), Custom Loader, Cookie Keeper, Transport-URL = Preview-Host, IP/UA-Weitergabe, Consent im Server respektiert, Stape-Plan vs. Request-Volumen.
- **DATA**: dataLayer-Qualität (Eventnamen, `ecommerce`-Objekt, `user_data`), keine PII in URLs/Eventparametern an GA4.
- **LEGAL**: Datenschutzerklärung nennt alle gefundenen Dienste; CMP listet sie; Hinweis § 25 TDDDG.

Bewertung wie bei `/meixner-toolkit:seogeo`: Priorität (Kritisch = Rechtsrisiko oder Messung kaputt · Hoch · Mittel · Niedrig), Evidenz (Offiziell/Belegt/Plausibel/Spekulativ), Aufwand (S/M/L), Nachweis, Fix.

**Report `tracking-audit.md`**: Stand, Umfang, Datenquellen · Zusammenfassung + Scorecard + Top-5 · Findings (Tabelle + Detail) · Consent-Matrix (Szenario × Tracker × Cookies) · Was gut ist · Nicht geprüft · Baseline (für `test`) · Quellen. Zusätzlich `tracking-audit.json` (Schema: Skill `kundenbericht` → `references/audit-schema.md`, `typ: "tracking"`), Ablage unter `~/.meixner-toolkit/audits/<slug>/` + Eintrag in `kunden/<slug>.json`; neu gefundene IDs dort speichern. Selbstprüfung vor dem Senden (Zahlen, IDs, Nachweise). Im Chat: Kurzfassung und Frage „Weiter mit Plan?“.


### Completeness Gate vor jedem Build

`plan.json` muss einen `requirements`-Block enthalten. Der deterministische Gate-Check (`scripts/plan_gate.py`) blockiert den Build, solange architekturrelevante Entscheidungen fehlen. **UNKNOWN darf nie durch Raten ersetzt werden.** Ein `*_verified: true` reicht allein nicht: `requirements.evidence` und `requirements.event_evidence` muessen die konkrete Beobachtung/Quelle nennen (z. B. GTM Preview, dataLayer, Codepfad oder ausdrueckliche Nutzerbestaetigung). Begriffe wie „Annahme“, „unknown“ oder „TODO“ gelten nicht als Evidenz. Fehlende Punkte werden als konkrete Rueckfragen ausgegeben und in einer gebuendelten Fragerunde geklaert. Mindestens: Seitentyp (MPA/SPA/Hybrid), Produktionsdomain, echte Eventquelle, verifizierter Erfolgs-/Ausloesepunkt je geplantem Event, Consent-Strategie, Cross-Domain-Entscheidung, interne Zugriffe; bei E-Commerce zusätzlich Kauf-dataLayer (`transaction_id/value/currency/items`), Refund- und Payment-Referral-Strategie; bei Enhanced Conversions die verifizierte `user_data`-Quelle + Consent-Pfad; bei sGTM die Browser-vs-Server-Zustaendigkeit. `requirements.open_questions` muss leer sein. Cross-Domain wird vom Direktgenerator bewusst nicht still approximiert: dafuer einen real verifizierten Master verwenden.

Vor Build immer:
```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/plan_gate.py" plan.json
```
Nur `complete: true` darf in den Generator. Der Generator prueft dasselbe Gate erneut und bricht sonst ab.

## 5. Plan – Rückfragen (AskUserQuestion, max. 2 Runden)

Nur fragen, was nicht aus Audit/Recon ableitbar ist (vollständiger Katalog und Entscheidungsbaum: `references/entscheidungen.md`):
1. Geschäftsmodell & Ziel-Conversions (Lead, Anruf, Termin, Kauf) und **Werte** (fester Lead-Wert? Warenkorbwert?).
2. Plattformen & IDs (GA4 `G-`, Ads `AW-` + Labels, Meta Pixel-ID) – IDs sind keine Geheimnisse; Tokens nicht erfragen.
3. CMP (vorhanden/welche) und **Consent Mode Basic oder Advanced** (Entscheidung des Kunden).
4. sGTM ja/nein, Domain-Variante (DNS-/Cloudflare-Zugriff?), Stape-Plan nach Volumen.
5. Enhanced Conversions / CAPI-Nutzerdaten: Wo liegt die E-Mail/Telefon (Formular, Shop)?
6. `backup_gclid`-Workaround gewünscht? (Hinweis auf Einordnung in `references/google.md`.)
7. Completeness-Gate-Felder, soweit Recon sie nicht belegt: MPA/SPA/Hybrid, kanonische Domain, Eventquelle + echter Ausloesepunkt **je geplantem Event**, Cross-Domain ja/nein, interne/Testzugriffe; bei Shop Kauf-dataLayer (`transaction_id/value/currency/items`), Refunds und Payment-Referrals; bei Enhanced Conversions konkrete `user_data`-Quelle + Consent-Pfad; bei sGTM eindeutige Browser-vs-Server-Zuständigkeit. Jede als verifiziert gesetzte Entscheidung bekommt eine kurze Evidenznotiz (`requirements.evidence`/`event_evidence`). Nicht beantwortet oder nur vermutet = `open_questions`, kein Build.

Ergebnis: **`tracking-plan.md`** (Tabelle Event → Auslöser → GA4 / Ads / Meta / Werte / Consent-Kategorie, Architekturbild als Text, offene Punkte) + **`plan.json`** (Schema: `references/gtm-json.md`). Freigabe durch Tobias abwarten.


### Production Reference + Golden-Master-Verifikation
Das Toolkit liefert seit 0.7.11 ein **sanitisiertes, real eingesetztes Web-/Server-Referenzpaar** unter `masters/production-reference/`. Es ist Architektur-Evidenz, **kein Default-Setup**. Vor Plan/Build `masters/REFERENCE-POLICY.md` lesen und `masters/patterns/event-patterns.json` nur als Pattern-Library nutzen. Niemals Kundenwerte, Consent-Entscheidungen, Waehrung, Eventnamen, Pfade, Selektoren oder Werbeziele aus der Referenz erben. Der Guard `scripts/reference_guard.py` muss gruen sein.

Aus der Referenz abgeleitete `masters/core/*.candidate.json` enthalten nur neutrale Core-Struktur. Sie bleiben `candidate_reference_only`, bis sie einen **echten GTM Import -> Preview -> Re-Export** durchlaufen haben. `scripts/gtm_master_verify.py` vergleicht Candidate und Roundtrip semantisch; `fill_template.py --verified-manifest ...` bindet den Hash an den Master. Ein erstmaliger Bootstrap darf nur bewusst `--candidate-only` verwenden. Google unterstuetzt Export/JSON-Aenderung/Import offiziell; das ersetzt aber keinen fachlichen Preview-Test. Details: `masters/README.md` und `masters/REFERENCE-POLICY.md`.

## 6. Build

> **Server-Container sind keine Web-Container.** Drei Werte unterscheiden sich, und alle
> drei erzeugen beim Import Fehler, wenn man sie aus einem Web-Container uebernimmt:
> eingebauter Trigger `2147479574` statt `2147479573`; `conversionId` im `sgtmadsct`-Tag
> **ohne** `AW-`-Praefix (nur Ziffern); ein SERVER-Container braucht mindestens einen
> Client. Ausserdem teilen sich `tagId`, `triggerId` und `variableId` **einen** Zaehlraum –
> getrennt vergeben kollidieren sie. Details und Belege: `references/server-container.md`.
> Vor jedem Import pruefen (Pflicht, auch fuer generierte Dateien):
> `python3 "${CLAUDE_SKILL_DIR}/scripts/validate_container.py" <datei>.json`
>
> **Container-Einstellungen importiert GTM nicht.** Der `container`-Block beschreibt
> den Ursprungscontainer; `taggingServerUrls`, Name und Konto-IDs werden beim Import
> verworfen. Nach dem Import eines Server-Containers deshalb immer ansagen:
> *Verwaltung → Container-Einstellungen → Server container URLs* eintragen, sonst
> nimmt der Container keine Requests an.

0. **Reference Guard:** `python3 "${CLAUDE_SKILL_DIR}/scripts/reference_guard.py"`. Bei Fehler abbrechen; nie auf rohe/private GTM-Exporte aus dem Plugin zurueckfallen.
1. **Eventplan zuerst:** reales Success-/Interaktionssignal je Event verifizieren; danach Pattern waehlen. `purchase`, `start_trial`, Lead/Booking, Newsletter, Scroll und Custom Completion haben bewusst unterschiedliche Regeln in `masters/patterns/event-patterns.json`. Engagement-Events werden **nicht automatisch** Ads-/Meta-Conversions.
2. **Web-Container**: `python3 "${CLAUDE_SKILL_DIR}/scripts/build_web_container.py" plan.json -o gtm-web-import.json` (Selbstprüfung eingebaut). Die Production Reference dient nur als Struktur-Gegenprobe. Wenn Cross-Domain erforderlich ist, den Direktgenerator **nicht** verwenden – nur einen real verifizierten Master, der diese Konfiguration nachweislich enthaelt. SPA/Hybrid nur mit verifizierter `dataLayer_page_view`-Strategie und explizitem `page_view`-Event.
3. **Server-Container:** `python3 "${CLAUDE_SKILL_DIR}/scripts/build_server_container.py" plan.json -o gtm-server-import.json` erzeugt GA4-Client, GA4-Tag, Server Conversion Linker und je eine Ads-Conversion pro Event mit Label (Selbstpruefung eingebaut). Niemals von Hand zusammensetzen – die Unterschiede zum Web-Container im Warnblock oben sind genau die Fehler, die dabei entstehen. Alternativ ein real verifizierter Master mit `fill_template.py ... --verified-manifest ...`. Fehlt er, kann `masters/core/server-core.candidate.json` als **Bootstrap-Struktur** dienen, aber nur mit `--candidate-only`; kundenspezifische Event-/Ads-/Meta-Tags werden danach aus dem verifizierten Plan aufgebaut. Alternativ Stape Setup Wizard bzw. manueller Aufbau nach aktueller Google/Stape-Doku. Keine Community-Template-IDs oder Server-JSON-Felder erfinden.
4. **Google Ads Server-Side:** bei serverseitiger Conversion-Messung keine aequivalente Browser-Ads-Conversion still parallel erzeugen. ID/Label aus dem Kundenkonto; Wert/Waehrung/Transaction-ID aus verifiziertem Eventvertrag, nicht aus Referenzwerten.
5. **Meta:** CAPI-Token nie im Chat/Git. Browser+Server nur mit identischem realen Eventnamen + derselben `event_id` deduplizieren. `adStorageConsent=optional`, `inherit` und andere im Referenzsetup beobachtete Einstellungen sind **keine Defaults**; pro Kunde/CMP verifizieren.
6. Manuelle/nicht im JSON abbildbare Schritte immer auflisten: CMP-Template aus der Galerie (Consent Initialization), Meta Access Token, DNS/Proxy, GA4 Key Events/Data Filters/Unwanted Referrals, Cross-Domain falls nicht ueber einen verified Master abgedeckt, Ads-Kundendatenbedingungen. Nie so tun, als enthalte das Import-JSON Kontoeinstellungen ausserhalb von GTM.
7. **Vor dem Import jede erzeugte Datei pruefen:** `python3 "${CLAUDE_SKILL_DIR}/scripts/validate_container.py" <datei>.json`. Bei Befunden nicht importieren, sondern korrigieren. Das gilt auch fuer Dateien aus `build_web_container.py` – dessen Selbstpruefung deckt den Web-Fall ab, nicht von Hand ergaenzte oder aus Mastern befuellte Container.
8. Import-Anleitung: Verwaltung → Container importieren → neuer Workspace → Zusammenführen/Konflikte umbenennen. Danach Preview/Tag Assistant bzw. Server Preview; erst nach bestandenem Test veroeffentlichen.

## 7. Test & Abnahme (`/meixner-toolkit:tracking-audit test`)

Testprotokoll `tracking-test.md` mit Häkchen je Punkt:
- GTM-Vorschau: jedes Plan-Event feuert genau einmal, richtige Parameter; Marketing-Tags vor Einwilligung blockiert.
- sGTM-Vorschau: Requests kommen an (GA4-Client), Meta-/Ads-Tags senden 200; IP/UA korrekt.
- Meta Events Manager → Test Events: Browser + Server, „dedupliziert“; EMQ nach 24–48 h prüfen.
- Google Ads: Tag Assistant / Conversion-Diagnose; Enhanced-Conversions-Status nach einigen Tagen.
- GA4 DebugView / Echtzeit: Key Events, `purchase`-Werte.
- `consent_test.mjs` erneut → Vergleich mit Baseline aus dem Audit.
Erst nach bestandenem Protokoll: Tobias veröffentlicht. Abschließend kurze Kunden-Doku (was wird gemessen, wo, mit welcher Einwilligung).
