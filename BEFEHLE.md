# Abläufe & Befehle – meixner-toolkit

Stand 02.10.2026 · Plugin-Version 0.7.17 · Für Claude Code (Windows) und die Claude-Desktop-App

**Befehlsnamen:** Plugin-Skills werden hier ausschließlich in der kanonischen namespaced Form dokumentiert, z. B. `/meixner-toolkit:seogeo` und `/meixner-toolkit:setup`. Auf nicht dokumentierte Kurzformen ohne Plugin-Präfix wird bewusst nicht vertraut.

---

## Teil 1 – Die Abläufe, die du wirklich brauchst

Von oben nach unten: so läuft ein Kunde durch. Jeder Schritt ist ein Befehl; alles, was eingreift (Code ändern, Container importieren, Mail senden), passiert erst nach deiner Freigabe.

### 1. Kalter Lead – im Netz gefunden, noch kein Kontakt

1. Ordner anlegen, z. B. `C:\Kunden\schreinerei-mueller\`, Claude Code darin starten
2. `/meixner-toolkit:seogeo quick https://kunde.de` — nur Kritisch und Hoch, maximal 10 Punkte. Entscheidung: lohnt sich Ansprechen?
3. Wenn ja: `/meixner-toolkit:seogeo https://kunde.de` — Vollaudit mit Crawl, Technik, Inhalten, Local, KI-Sichtbarkeit
4. `/meixner-toolkit:kundenbericht` — HTML-Datei, alle Punkte aufklappbar, ohne Lösungen
5. „Schreib mir einen Mailentwurf dazu" — drei, vier persönliche Sätze; du liest gegen und schickst selbst

**Du gibst raus:** die HTML-Datei. **Du behältst:** `seo-audit.md` mit allen Details und Maßnahmen.

### 2. Lead hat geantwortet – Gespräch steht an

1. Nichts neu crawlen, die Daten von eben reichen
2. „Bereite mich auf das Gespräch mit <Kunde> vor" — die drei wichtigsten Punkte in Alltagssprache, Aufwand je Punkt, passende Leistung samt Preis
3. Schaltet er Anzeigen oder misst er Anfragen? Dann `/meixner-toolkit:tracking-audit https://kunde.de` als zweites Thema – das ist oft der größere Hebel
4. Nach dem Gespräch: Angebot aus `07-Vorlagen/Angebot_Vorlage_Meixner.docx`

### 3. Auftrag erteilt – Kunde anlegen

1. `/meixner-toolkit:setup kunde <name>` — Ansprechpartner, Domain, CMS, Konto-IDs. **Keine Passwörter, keine Tokens** in die Datei
2. Zugänge anfordern: Search Console, GA4, Google Ads, GTM, Hosting/CMS, bei Bedarf Meta Business
3. War bisher nur ein Quick-Check: jetzt `/meixner-toolkit:seogeo gruendlich https://kunde.de`
4. `/meixner-toolkit:kundenbericht --voll` — derselbe Bericht, diesmal mit „Was zu tun ist" je Punkt: dein Arbeitsplan und seine Übersicht

### 4. Punkte umsetzen

- Mit Zugriff auf den Code: `/meixner-toolkit:seogeo fix hoch` — arbeitet auf einem eigenen Git-Branch, zeigt jede Änderung vor dem Übernehmen
- Ohne Code-Zugriff: Punkte selbst oder mit dem Entwickler des Kunden abarbeiten
- Vier bis sechs Wochen später: `/meixner-toolkit:seogeo recheck` — dieselben Punkte erneut gemessen, Vorher/Nachher

### 5. Tracking einrichten (GTM, GA4, Ads, Meta, Consent)

1. `/meixner-toolkit:tracking-audit https://kunde.de` — was ist da, was feuert vor der Einwilligung, wo fehlen Conversions
2. `/meixner-toolkit:tracking-audit plan` — beantwortet Rückfragen (Events, Werte, Consent-Variante, Server-Side ja/nein), du gibst den Plan frei
3. `/meixner-toolkit:tracking-audit build` — fertige GTM-Import-Datei plus Anleitung
4. Import in einen **Test-Container**, prüfen, erst dann in den Live-Container. Das machst du selbst, ich fasse deine Konten nicht an
5. `/meixner-toolkit:tracking-audit test https://kunde.de` — Consent-Test in drei Szenarien, Protokoll für den Kunden

### 6. Website geht live oder zieht um

1. Direkt nach dem Livegang: `/meixner-toolkit:launch https://kunde.de` — Weiterleitungen der alten Adressen, noindex-Reste, robots.txt, Sitemap, 404, SSL, Rechtsseiten
2. Gefundene Fehler beheben, `/meixner-toolkit:launch` wiederholen, bis alles grün ist
3. `/meixner-toolkit:tracking-audit test https://kunde.de` — hat die Messung den Umzug überlebt?
4. `/meixner-toolkit:kundenbericht --voll` — als Abnahmeprotokoll für den Kunden

### 7. Laufende Betreuung (Sorglos-Paket)

- Monatlich: `/meixner-toolkit:seogeo recheck`, bei Änderungen zusätzlich `/meixner-toolkit:launch https://kunde.de`
- Daraus `/meixner-toolkit:kundenbericht --voll` als Monatsbericht
- Einmal im Monat für dich selbst: `/meixner-toolkit:wissen-update` — prüft, was sich bei Google, Meta, Stape, in den Browsern und im Recht geändert hat

### 8. Kunde meldet ein Problem

| Er sagt | Du tippst |
|---|---|
| „Es kommen keine Anfragen an" / „Conversions fehlen" | `/meixner-toolkit:tracking-audit https://kunde.de` |
| „Wir sind bei Google verschwunden" | `/meixner-toolkit:seogeo quick https://kunde.de`, bei kürzlichem Umzug zusätzlich `/meixner-toolkit:launch https://kunde.de` |
| „Die Seite ist langsam" | `/meixner-toolkit:seogeo seo https://kunde.de` |
| „Taucht ChatGPT uns auf?" | `/meixner-toolkit:seogeo geo https://kunde.de` |

### 9. Unklar oder gemischt

`/meixner-toolkit:start` — fragt Kunde, Module und Tiefe ab, zeigt einen Ablaufplan und arbeitet ihn ab. Wenn du nicht weißt, welcher Befehl passt, ist das immer der richtige Einstieg.

---

## Teil 2 – Wo arbeite ich?

| Aufgabe | Wo | Warum |
|---|---|---|
| Crawl, Vollaudit, Quick-Check | **Claude Code (Windows)** | hunderte Abrufe, SiteOne, PageSpeed – braucht echten Netzzugang von deinem Rechner |
| Consent-Test, GTM-Import bauen, Go-Live-Abnahme | **Claude Code** | braucht Playwright und Dateien lokal |
| Kundenbericht rendern, PDF daraus | **Claude Code** | Skript und Schriften liegen im Plugin auf deinem Rechner |
| Einzelne Seite ansehen, Recherche, Texte, Mailentwurf, Bericht durchsprechen | **Desktop-App** | öffnet Seiten über den eingebauten Browser |
| Unterwegs nachfragen, entscheiden, Stand prüfen | **Desktop-App** | Zugriff vom Handy. Laut Anthropic-Dokumentation (geprüft 15.09.2026) laufen Cowork-Aufgaben standardmäßig in einer isolierten Cloud-Umgebung auf Anthropic-Servern; lokale Dateien können über Claude Desktop eingebunden werden. Vor sensiblen Kundendaten die aktuellen Produkt-/Datenschutzeinstellungen prüfen |

Claude Code braucht **keinen Code vom Kunden**. Der Ordner ist nur dein Arbeitsplatz – dort landen Crawl-Daten, Audit-JSON und Bericht.

---

## Teil 3 – Alle Befehle

### Täglich

| Befehl | Wann | Was passiert |
|---|---|---|
| `/meixner-toolkit:start` | Auftrag gemischt oder unklar | Fragt Kunde, Module und Tiefe ab, zeigt einen Ablaufplan und arbeitet ihn ab |
| `/meixner-toolkit:seogeo https://kunde.de` | Standard-SEO-Auftrag | Vollaudit: Crawl, Technik, Inhalte, Local, KI-Sichtbarkeit → `seo-audit.md` + `.json` |
| `/meixner-toolkit:seogeo quick https://kunde.de` | Schneller Blick, Erstgespräch | Nur Kritisch/Hoch, max. 10 Punkte |
| `/meixner-toolkit:seogeo gruendlich https://kunde.de` | Neukunde, Recht, Migration | Wie Vollaudit mit größerem Recherche-Budget |
| `/meixner-toolkit:tracking-audit https://kunde.de` | Tracking prüfen | GTM, GA4, Ads, Meta, Consent Mode; Consent-Test in drei Szenarien |
| `/meixner-toolkit:kundenbericht` | Ergebnis soll zum Kunden | Brief im Design deiner Website als HTML: alle Punkte nach Bereich gruppiert, jeder zum Aufklappen |

### Je nach Auftrag

| Befehl | Wann | Was passiert |
|---|---|---|
| `/meixner-toolkit:seogeo seo https://kunde.de` | Kunde will nur Google | Wie Vollaudit, ohne GEO-Teil |
| `/meixner-toolkit:seogeo geo https://kunde.de` | Thema KI-Sichtbarkeit | Bot-Zugang, Rendering, Entität, Stichprobe in KI-Antworten |
| `/meixner-toolkit:seogeo geo <Markenname>` | Nur die Frage „werde ich in KI-Antworten genannt?" | Reine Stichprobe ohne Crawl |
| `/meixner-toolkit:seogeo fix hoch` | Nach dem Audit, mit Code-Zugriff | Setzt freigegebene Punkte um, eigener Git-Branch |
| `/meixner-toolkit:seogeo recheck` | 4–6 Wochen später | Misst dieselben Punkte erneut, Vorher/Nachher |
| `/meixner-toolkit:tracking-audit plan` | Neue Seite oder Umbau | Rückfragen → Tracking-Plan zum Absegnen |
| `/meixner-toolkit:tracking-audit build` | Plan ist freigegeben | GTM-Import-Datei und Anleitung |
| `/meixner-toolkit:tracking-audit test https://kunde.de` | Nach dem Einbau | Testprotokoll und Consent-Test gegen die Baseline |
| `/meixner-toolkit:launch https://kunde.de` | Website geht live oder ist umgezogen | Weiterleitungen, noindex, robots, Sitemap, 404, SSL, Rechtsseiten |
| `/meixner-toolkit:kundenbericht --voll` | Kunde hat beauftragt | Bericht inklusive „Was zu tun ist" je Punkt |
| `/meixner-toolkit:kundenbericht --teaser` | Kalter Erstkontakt | Kurzfassung: nur die drei wichtigsten Punkte, Rest als Anzahl je Bereich |
| `/meixner-toolkit:kundenbericht pdf` | Kunde will etwas zum Ausdrucken | Wandelt den letzten Bericht in Sekunden in ein PDF |

### Selten

| Befehl | Wann |
|---|---|
| `/meixner-toolkit:setup` | Umgebung prüfen (PageSpeed-Key, Playwright, SiteOne Crawler, Konfiguration) |
| `/meixner-toolkit:setup init` | Einmalig: Ordner, Branding, Standards anlegen |
| `/meixner-toolkit:setup kunde <name>` | Kundendaten anlegen oder ändern |
| `/meixner-toolkit:wissen-update` | Prüfen, was sich bei Google, Meta, Stape oder im Recht geändert hat |

---

## Teil 4 – Einmal einrichten und Spielregeln

**Einrichten:** Claude Code auf Windows installieren, Plugin `meixner-toolkit` einspielen, `/meixner-toolkit:setup init` ausführen. Danach sagt dir `/meixner-toolkit:setup`, was noch fehlt (Node, Python, Playwright, SiteOne Crawler, PageSpeed-Key).

**Spielregeln, an die sich die Skills halten:**

> Diese Regeln stehen als Anweisung in den Skill-Dateien. Sie sind **keine technische Sperre**:
> Berechtigungen setzt Claude Code durch, nicht das Modell. Wer sie erzwingen will, hinterlegt
> `deny`-Regeln unter `/permissions` oder einen `PreToolUse`-Hook. Im Modus `auto` oder
> `bypassPermissions` greifen die Regeln unten nicht mehr zuverlässig.


- Keine Behauptung ohne Beleg: jede Aussage stammt aus einer Messung dieses Laufs, aus den Wissensdateien oder aus einer frisch geprüften Primärquelle – nichts aus dem Gedächtnis.
- Nichts wird ohne deine Freigabe geändert, importiert, veröffentlicht oder versendet.
- Passwörter und Tokens gehören nicht in die Kundendateien; die Zugänge legst du selbst an.
- Was der Kunde bekommt, zeigt jeden Punkt, aber keine Lösung. Die steht erst in `--voll`.

**Noch offen:** Laufzeiten pro Befehl sind hier bewusst nicht angegeben – die tragen wir nach den ersten echten Durchläufen mit gemessenen Werten nach.
