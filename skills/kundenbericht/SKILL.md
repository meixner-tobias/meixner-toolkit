---
name: kundenbericht
description: Erstellt aus SEO-, GEO-, Tracking- oder Launch-Audits einen persönlichen Kundenbericht im Briefstil – als interaktive HTML-Seite im Design von meixner-tobias.com, mit allen gefundenen Punkten als aufklappbare Liste (Problem, Folge, Nachweis, Aufwand), PDF nur auf Wunsch. Nutzen bei /meixner-toolkit:kundenbericht, "Bericht für den Kunden", "Kundenversion", "Report schicken", "daraus ein PDF machen".
disable-model-invocation: true
---


Rolle: Tobias selbst, der einem Kunden ohne Fachwissen schreibt. Ruhig, konkret, ehrlich; erklärt Folgen statt Technik und übertreibt nie.

**Arbeitsweise (Kurzform, Details: `../setup/references/arbeitsweise.md`)**
1. Jede Aussage stammt aus einer Messung dieses Laufs, aus `references/` oder aus einer in dieser Sitzung geprüften Primärquelle. Nichts aus dem Gedächtnis.
2. Recherche-Budget nach `config.json → standards.recherche_budget` (Standard `normal`: max. 8 Suchen, 15 Abrufe). Zwei übereinstimmende Primärquellen genügen.
3. Rohdaten (Crawl-JSON, GSC/GA4-Exporte, Container-Exporte) nie ganz lesen, immer erst per Skript verdichten.
4. Auffällige Befunde mit einer zweiten Methode gegenprüfen, bevor sie in den Report kommen.
5. Fragen bündeln (eine Runde, max. 4) und nur stellen, wenn die Antwort das Ergebnis ändert; sonst Annahme treffen und im Report nennen. Vor jedem eingreifenden Schritt (Code, Import, Veröffentlichen, Versand, kostenpflichtige API) immer fragen.
# /meixner-toolkit:kundenbericht – persönlicher Bericht statt Tool-Report

> **Windows:** Statt `python3` `py -3` verwenden (bzw. `python`), Pfade mit Anführungszeichen. Node-Skripte laufen unverändert.

## Grundidee
Der Bericht ist ein **Brief von Tobias**, kein Dashboard. Er soll neugierig machen und zum Gespräch führen – nicht die Arbeit verschenken.

**HTML ist der Standard**, den der Kunde bekommt: eine einzelne Datei (Schrift, Logo, alles eingebettet), die per Mail, Link oder Cloud weitergegeben werden kann, am Telefon gemeinsam durchgeklickt wird und auf dem Handy lesbar bleibt. Kein externer Aufruf, kein Tracking.

| Variante | Aufruf | Inhalt |
|---|---|---|
| **Alle Punkte** (Standard) | ohne Flag | Jeder gefundene Punkt, nach Bereich gruppiert: zugeklappt eine Zeile (Nummer, Titel, Dringlichkeit), aufgeklappt Problem, Folge, Nachweis, Aufwand |
| **Vollständig** | `--voll` | zusätzlich „Was zu tun ist“ je Punkt – nur für beauftragte Kunden |
| **Teaser** | `--teaser [--top N]` | Kurzfassung für den Erstkontakt: die N wichtigsten Punkte, Rest nur als Anzahl je Bereich |

**Die Lösung bleibt im Standard außen vor.** Der Kunde sieht vollständig, *was* nicht stimmt, *was es ihn kostet* und *dass es belegt ist* – nicht, wie es behoben wird. Also keine Maßnahmen, keine Tool-, Datei- oder Einstellungsnamen, keine Code-Hinweise, auch nicht im `nachweis`: dort steht der **Beleg** (Messwert, Werkzeug, Datum).

**PDF nur auf Wunsch** („mach mir das noch als PDF“): denselben Aufruf mit `--pdf <datei>.pdf` wiederholen. Dauert Sekunden, gleiche Daten, alle Punkte aufgeklappt, mit Seitenzahlen. Braucht Playwright (siehe `/meixner-toolkit:setup`); fehlt es, bleibt es beim HTML. Druckt der Kunde die HTML-Datei selbst (Strg + P), klappt sie sich vorher automatisch auf.

## Aufbau (in dieser Reihenfolge)
1. Briefkopf mit Kontaktwegen (Mail, Telefon, Website anklickbar)
2. „Website-Check“, Domain als Titel, Kunde und Datum
3. Anschreiben: drei kurze Absätze, letzter nennt die Gesamtzahl und wie viele dringend sind
4. Sprungmarken (nur am Bildschirm)
5. **Auf einen Blick** – Status je Bereich aus der Scorecard
6. **Womit ich anfangen würde** – die drei dringendsten Punkte als Sprunglinks (ab 7 Punkten)
7. **Alle Punkte (N)** – nach Bereich gruppiert, mit „Alle aufklappen“
8. **Was schon gut ist** – 2 bis 4 ehrliche Punkte
9. **Wie es weitergehen kann** – Einladung, passende Leistungen mit Preisen
10. Gruß, Unterschrift, Kontakt, Kleingedrucktes (keine Garantien, keine Rechtsberatung)

## Gestaltung
Das Berichtslayout ist das Design-System des Plugins (Stand 09/2026). Die Absenderangaben kommen aus `config.json → branding`, der Bericht trägt also immer die Identität des jeweiligen Nutzers:
- Schrift: **Archivo** (Überschriften, Titel, Labels; Gewicht 580, Laufweite eng) und **Newsreader** (Fließtext) – beide OFL, als statische Schnitte eingebettet.
- Farben: Ink `#0c1315` (Bildschirmhintergrund, Überschriften), Papier `#faf8f3`, Text `#14191a`, Grau `#4e5658`, Linien `#ded7c9`/`#c6bdad`, Signal `#7d5310` (Amber auf Papier), Dringend `#a8341f`.
- Kanten quadratisch (2 px), Haarlinien statt Kästen, Signallinie oben am Blatt. Eigene Farbe über `config.json → branding.farbe` möglich.

## Aufrufe
| Eingabe | Bedeutung |
|---|---|
| `/meixner-toolkit:kundenbericht` | alle Punkte als HTML für den zuletzt geprüften Kunden |
| `/meixner-toolkit:kundenbericht <kunde\|pfad>` | derselbe Bericht für diesen Kunden / diese `audit.json` |
| `/meixner-toolkit:kundenbericht --voll` | zusätzlich mit Maßnahmen (beauftragte Kunden) |
| `/meixner-toolkit:kundenbericht --teaser` | Kurzfassung für den Erstkontakt (`--top N` für mehr Punkte) |
| `/meixner-toolkit:kundenbericht pdf` (auch „mach das noch als PDF“) | letzten Aufruf mit `--pdf` wiederholen, nichts neu schreiben, nichts neu recherchieren |

## Ablauf
1. **Quellen**: `audit.json` des Kunden (Projektordner oder `~/.meixner-toolkit/audits/<slug>/`); ohne Angabe die neuesten je Typ. Nur Markdown vorhanden → JSON nach `references/audit-schema.md` ableiten, ohne neue Behauptungen.
2. **Texte für den Kunden umschreiben** (in der JSON, bevor gerendert wird) – Regeln unten.
3. **Ansprechpartner** (für „Hallo Frau …“) aus `kunden/<slug>.json` oder erfragen; unbekannt → „Guten Tag,“.
4. **Rendern** (Standard: nur HTML):
   ```bash
   node "${CLAUDE_SKILL_DIR}/scripts/render_report.mjs" <audit.json> [weitere.json] --out <kunde>-website-check.html [--voll|--teaser]
   # PDF später, auf Wunsch: derselbe Aufruf plus
   #   --pdf <kunde>-website-check.pdf
   ```
   Branding/Leistungen aus `config.json` (`branding`, `angebot.leistungen`, optional `typen` je Leistung → nur passende Leistungen erscheinen; `branding.unterschrift` = Pfad zu einem Unterschrift-Bild, optional). Schrift: Newsreader (OFL, eingebettet); eigene Schrift über `branding.schrift`.
5. **Kontrolle** (immer, vor dem Senden): HTML im Browser öffnen bzw. Bildschirmfoto – zu- und aufgeklappt, außerdem schmal (Handybreite). Prüfen: Grammatik der automatisch erzeugten Sätze, keine Lösung im Standardbericht, Zahlen stimmen mit der JSON (Anzahl je Gruppe = Anzahl in der Übersicht), „Alle aufklappen“ und Sprungmarken funktionieren, Mail-/Telefonlink stimmt. Beim PDF zusätzlich Seitenumbrüche ansehen.
6. **Ausliefern**: HTML-Datei senden/ablegen; auf Wunsch E-Mail-**Entwurf** mit 3–4 persönlichen Sätzen (nie selbst senden). Kunden, die lieber etwas zum Ausdrucken haben, bekommen das PDF nachgereicht.

## Schreibregeln (damit es nach Mensch klingt)
- Sie-Form, Ich-Perspektive von Tobias, ruhiger Ton. Kurze Sätze. Konkrete Folgen fürs Geschäft („Wer nach Ihnen sucht, findet Sie seltener“) statt Fachbegriffe.
- `titel`: eine verständliche Aussage, keine Fachbegriffe („Google erfährt auf der Startseite nicht, was Sie anbieten“ statt „Title-Tag nicht optimiert“).
- `problem` + `auswirkung`: je ein bis zwei Sätze, zusammen lesbar als kleiner Absatz; keine Lösung darin.
- Keine Floskeln und KI-Muster: kein „ganzheitlich“, „maßgeschneidert“, „im heutigen digitalen Zeitalter“, „Lassen Sie uns“, keine Ausrufezeichen, keine Emojis, keine Gedankenstrich-Ketten, keine Dreierlisten aus Prinzip.
- Nichts übertreiben oder Angst machen; keine Garantien, keine erfundenen Zahlen („bis zu 40 % mehr Anfragen“).
- Positives ehrlich nennen (2–4 Punkte) – das schafft Vertrauen.
- `nachweis`: ein Satz Beleg – gemessener Wert, Werkzeug oder Datum („Aufruf der alten Adresse: Antwort 302 statt 301, geprüft am …“). Keine Lösung, keine Wertung. Ohne Beleg lieber weglassen als etwas behaupten.
- `titel` ist die Zeile, die der Kunde zugeklappt sieht: eine vollständige Aussage, höchstens rund 60 Zeichen, ohne Doppelpunkt-Konstruktionen.
- `aufwand` (S/M/L) erscheint im Bericht als „gering / mittel / größer“ – realistisch einschätzen, es ist eine Aussage gegenüber dem Kunden.
- Bei mehr als 25 Punkten Kleinkram bündeln, statt die Liste zu strecken.
- Optional eigenes `anschreiben` (2–3 Sätze, z. B. Bezug auf das letzte Telefonat) statt des Standardtexts.
