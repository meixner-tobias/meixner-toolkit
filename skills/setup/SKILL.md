---
name: setup
description: Richtet meixner-toolkit ein und prüft die Umgebung (Konfiguration, Branding, Kundenliste, PageSpeed-Key, Playwright, Master-Container). Nutzen bei /meixner-toolkit:setup, "Toolkit einrichten", "prüfe mein Setup", "neuen Kunden anlegen", "Kunde bearbeiten".
disable-model-invocation: true
---

# /meixner-toolkit:setup – Einrichtung, Check & Kundenliste

Speicherort: `$MEIXNER_TOOLKIT_HOME`, sonst `~/.meixner-toolkit/` mit
- `config.json` – Branding, Angebot, Standards (inkl. `recherche_budget`: `sparsam` | `normal` | `gruendlich`), Master-Container (Vorlage: `examples/config.json`)
- `kunden/<slug>.json` – ein Kunde je Datei (Vorlage: `examples/kunde.json`); **nur IDs, keine Passwörter/Tokens**
- `audits/<slug>/` – Audit-Ergebnisse (`.md` + `.json`)
- `master/` – exportierte GTM-Master plus `.verified.json`-Roundtrip-Manifeste; ein Container ohne Manifest ist nur Candidate

Läuft die Session in Cowork ohne Home-Verzeichnis-Zugriff: nach einem verbundenen Ordner fragen und dort `meixner-toolkit/` anlegen; Pfad dem Nutzer nennen.

> **Windows:** Statt `python3` `py -3` verwenden (bzw. `python`), Pfade mit Anführungszeichen. Node-Skripte laufen unverändert.

## Modi

| Eingabe | Aktion |
|---|---|
| `/meixner-toolkit:setup` | Check ausführen, Probleme mit konkreten Lösungsschritten zeigen |
| `/meixner-toolkit:setup init` | Ordner + `config.json` anlegen, Branding und Standards abfragen |
| `/meixner-toolkit:setup kunde <name>` | Kunde anlegen/bearbeiten |

## Check
`python3 "${CLAUDE_SKILL_DIR}/scripts/doctor.py" --online` prüft Konfiguration, Kundenliste, PSI-Key, Playwright, SiteOne Crawler und Master-Container (ohne `--online`, wenn kein Netz). Ergebnis als ✅/⚠️/❌-Liste zeigen; nur ❌ und für den geplanten Auftrag relevante ⚠️ ansprechen.

## Init
1. `doctor.py --init` legt Ordner und `config.json` an (überschreibt nichts).
2. Per AskUserQuestion abfragen, was fehlt: Branding (Name, Firma, Website, E-Mail, Telefon, Farbe als Hex, Logo-Pfad/URL), Angebotstexte, Standards (CMP, Consent Mode Basic/Advanced, sGTM-Hosting, Domain-Variante, backup_gclid ja/nein). Angebotstexte und Preise kommen ausschließlich vom Nutzer – nie vorbelegen, nie aus dem Gedächtnis ergänzen; `examples/config.json` ist eine leere Vorlage. Vor dem Speichern alles bestätigen lassen.
3. Werte mit einem kleinen Python-Schreibvorgang in `config.json` speichern (JSON gültig halten), danach Check erneut.

## Kunde
- Slug = Name in Kleinbuchstaben mit Bindestrichen. Vorhandene Datei erst lesen, dann ergänzen.
- Felder: Name, Domain, alte Domains, CMS, Zielmarkt, IDs (GTM Web/Server, GA4, Google Ads, Meta-Pixel, Stape-Domain), CMP, Betreuungsvertrag, Notizen, `audits` (Liste mit Datum, Typ, Datei).
- IDs aus vorhandenen Audits übernehmen statt neu zu fragen. Tokens, Passwörter, API-Keys niemals speichern.

## Regeln für alle Skills des Plugins
- Arbeitsweise (Fakten, Budgets, Rückfragen, Gegenprüfung): `references/arbeitsweise.md` – dort steht die verbindliche Langform.
- Zu Beginn `config.json` und – wenn eine Domain/ein Kunde erkennbar ist – `kunden/<slug>.json` lesen; bekannte Angaben nicht erneut erfragen.
- Nach jedem Audit Ergebnis unter `audits/<slug>/<JJJJ-MM-TT>-<typ>.md/.json` ablegen und in `kunden/<slug>.json → audits` eintragen.
