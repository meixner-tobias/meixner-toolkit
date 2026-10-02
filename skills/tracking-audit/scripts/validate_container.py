#!/usr/bin/env python3
"""Prueft einen exportierten GTM-Container (WEB oder SERVER) vor dem Import.

Faengt Fehler ab, die GTM erst beim Import meldet - und solche, die GTM gar nicht
meldet, weil sie syntaktisch gueltig sind und erst in den Daten auffallen.

Gedacht fuer jeden Container, der nicht aus build_web_container.py stammt: von Hand
gebaute Server-Container, aus Mastern befuellte Exporte, fremde Dateien.

  python3 validate_container.py gtm-server-import.json
  python3 validate_container.py gtm-web-import.json --json
"""
import argparse
import json
import re
import sys

# Eingebaute Trigger je Container-Typ. Werte aus echten Exporten belegt:
# WEB    2147479573  "Initialization - All Pages" (build_web_container.py INIT_ALL_PAGES)
# SERVER 2147479574  "All Events" (production-reference + core-candidate, uebereinstimmend)
BUILTIN_TRIGGER = {"WEB": {"2147479573"}, "SERVER": {"2147479574"}}

# Ads-Conversion-Tags: der Browser-Tag will die gtag-Schreibweise mit Praefix,
# der Servertag die nackte Konto-Nummer. Verwechslung ist der haeufigste Fehler.
ADS_CONVERSION_ID = {
    "awct":      (re.compile(r"^AW-\d+$"), "AW-123456789 (Browser-Tag: mit AW--Praefix)"),
    "sgtmadsct": (re.compile(r"^\d+$"),    "123456789 (Servertag: nur Ziffern, kein AW-)"),
}
LABEL = re.compile(r"^[A-Za-z0-9_-]+$")
PLATZHALTER = re.compile(r"__[A-Z][A-Z0-9_]*__|GTM-REFERENCE")


def pruefe(export):
    f = []
    if export.get("exportFormatVersion") != 2:
        f.append("exportFormatVersion fehlt oder ist nicht 2.")
    cv = export.get("containerVersion")
    if not isinstance(cv, dict):
        return f + ["containerVersion fehlt."]

    ctx_liste = (cv.get("container") or {}).get("usageContext") or []
    ctx = (ctx_liste[0] if ctx_liste else "").upper()
    if ctx not in BUILTIN_TRIGGER:
        return f + ["container.usageContext muss WEB oder SERVER sein (erhalten: %r)." % ctx_liste]

    tags = cv.get("tag") or []
    trigger = cv.get("trigger") or []
    variablen = cv.get("variable") or []

    ids = ([t.get("tagId") for t in tags] + [t.get("triggerId") for t in trigger]
           + [v.get("variableId") for v in variablen])
    ids = [i for i in ids if i is not None]
    doppelt = sorted({i for i in ids if ids.count(i) > 1})
    if doppelt:
        f.append("Doppelte IDs: %s" % ", ".join(map(str, doppelt)))

    eigene = {t.get("triggerId") for t in trigger}
    erlaubt = eigene | BUILTIN_TRIGGER[ctx]
    fremde = set().union(*BUILTIN_TRIGGER.values()) - BUILTIN_TRIGGER[ctx]
    for t in tags:
        for key in ("firingTriggerId", "blockingTriggerId"):
            for tid in t.get(key) or []:
                if tid in erlaubt:
                    continue
                if tid in fremde:
                    f.append("Tag %r nutzt den eingebauten Trigger %s eines anderen "
                             "Container-Typs. In %s gilt %s."
                             % (t.get("name"), tid, ctx,
                                ", ".join(sorted(BUILTIN_TRIGGER[ctx]))))
                else:
                    f.append("Tag %r verweist auf unbekannten Trigger %s."
                             % (t.get("name"), tid))

    namen = {v.get("name") for v in variablen}
    roh = json.dumps(cv, ensure_ascii=False)
    for ref in sorted(set(re.findall(r"\{\{([^}]+)\}\}", roh))):
        if ref not in namen and not ref.startswith("_"):
            f.append("Variable {{%s}} wird verwendet, ist aber nicht definiert." % ref)

    for t in tags:
        typ = t.get("type")
        ps = {p.get("key"): p.get("value") for p in t.get("parameter") or []}
        if typ in ADS_CONVERSION_ID:
            muster, beispiel = ADS_CONVERSION_ID[typ]
            cid = ps.get("conversionId")
            if cid is None:
                f.append("Tag %r (%s) hat keine conversionId." % (t.get("name"), typ))
            elif not muster.match(str(cid)):
                f.append("Tag %r (%s): conversionId %r hat das falsche Format. Erwartet: %s."
                         % (t.get("name"), typ, cid, beispiel))
            lab = ps.get("conversionLabel")
            if lab is not None and not LABEL.match(str(lab)):
                f.append("Tag %r: conversionLabel %r enthaelt unerlaubte Zeichen." % (t.get("name"), lab))

    treffer = sorted(set(PLATZHALTER.findall(roh)))
    if treffer:
        f.append("Unersetzte Referenz-Platzhalter: %s" % ", ".join(treffer))

    if ctx == "SERVER" and not (cv.get("client") or []):
        f.append("SERVER-Container ohne Client: eingehende Requests werden von niemandem angenommen.")

    return f


def hinweise(export):
    """Schritte, die kein Import setzen kann und die deshalb leicht vergessen werden."""
    cv = export.get("containerVersion") or {}
    ctx = ((cv.get("container") or {}).get("usageContext") or [""])[0].upper()
    h = []
    if ctx == "SERVER":
        urls = (cv.get("container") or {}).get("taggingServerUrls") or []
        h.append("Verwaltung -> Container-Einstellungen -> Server container URLs eintragen"
                 + (" (im Export steht: %s)" % ", ".join(urls) if urls else "")
                 + ". Container-Einstellungen werden beim Import NICHT uebernommen.")
        typen = {t.get("type") for t in cv.get("tag") or []}
        if not (typen & {"sgtmgaaw", "gaaw"}):
            h.append("Kein GA4-Tag im Container: der Client nimmt Requests an, weiterleiten "
                     "muss ein Tag. In GTM anlegen ueber Tag -> Google Analytics: GA4, "
                     "Ausloeser 'Alle Events'.")
    if ctx == "WEB":
        h.append("Kontoeinstellungen liegen ausserhalb von GTM: Ads-Kundendatenbedingungen, "
                 "GA4 Key Events, Datenfilter, unerwuenschte Verweise.")
    h.append("Nach dem Import: Vorschau pruefen, erst danach veroeffentlichen.")
    return h


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("container")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        export = json.load(open(a.container, encoding="utf-8"))
    except (OSError, ValueError) as e:
        sys.exit("Datei nicht lesbar: %s" % e)

    fehler = pruefe(export)
    tipps = hinweise(export)
    cv = export.get("containerVersion") or {}
    ctx = ((cv.get("container") or {}).get("usageContext") or ["?"])[0]
    if a.json:
        print(json.dumps({"ok": not fehler, "usageContext": ctx, "fehler": fehler,
                          "hinweise": tipps}, ensure_ascii=False, indent=2))
    else:
        print("%s: %s, %d Tags, %d Trigger, %d Variablen"
              % (a.container, ctx, len(cv.get("tag") or []),
                 len(cv.get("trigger") or []), len(cv.get("variable") or [])))
        if fehler:
            print("\nFEHLER:")
            for x in fehler:
                print("  - " + x)
        else:
            print("OK: keine Befunde.")
        if tipps:
            print("\nNACH DEM IMPORT:")
            for x in tipps:
                print("  - " + x)
    sys.exit(2 if fehler else 0)


if __name__ == "__main__":
    main()
