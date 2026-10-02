#!/usr/bin/env python3
"""Erzeugt aus einem Tracking-Plan (JSON) eine importierbare GTM-SERVER-Container-Datei.

Gegenstueck zu build_web_container.py. Nur Tag-Typen, deren Export-Schluessel an echten
Server-Exporten belegt sind:
  gaaw_client  GA4-Client (nimmt Requests an)
  sgtmgaaw     GA4-Tag (reicht an GA4 weiter)
  sgtmadscl    Server Conversion Linker
  sgtmadsct    Google-Ads-Conversion serverseitig

Nicht erzeugt werden Community-Templates (cvt_*): ihre IDs gelten nur im
Ursprungscontainer. Meta CAPI, Stape-Power-ups und Transformationen deshalb in GTM
ergaenzen.

  python3 build_server_container.py plan.json -o gtm-server-import.json

Container-Einstellungen uebernimmt GTM beim Import NICHT. Die Tagging-Server-URL muss
nach dem Import unter Verwaltung -> Container-Einstellungen eingetragen werden.
"""
import argparse
import datetime
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_container import pruefe as container_pruefen, hinweise  # noqa: E402

ALL_EVENTS = "2147479574"          # eingebauter Trigger im SERVER-Container
EVENT_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,39}$")
MEASUREMENT_ID = re.compile(r"^G-[A-Z0-9]{6,12}$")
ADS_ID = re.compile(r"^(?:AW-)?(\d{6,15})$")
ADS_LABEL = re.compile(r"^[A-Za-z0-9_-]{10,40}$")


class PlanError(Exception):
    pass


def T(key, value):
    return {"type": "TEMPLATE", "key": key, "value": str(value)}


def B(key, value):
    return {"type": "BOOLEAN", "key": key, "value": "true" if value else "false"}


def build(plan):
    ga4 = (plan.get("ga4") or {}).get("measurement_id") or ""
    if not MEASUREMENT_ID.match(ga4):
        raise PlanError("ga4.measurement_id fehlt oder ist ungueltig (%r). Erwartet: G-XXXXXXXXXX." % ga4)

    ads_cfg = plan.get("google_ads") or {}
    roh_id = str(ads_cfg.get("conversion_id") or "")
    ads_id = ""
    if roh_id:
        m = ADS_ID.match(roh_id.strip())
        if not m:
            raise PlanError("google_ads.conversion_id ist ungueltig (%r)." % roh_id)
        # Der Servertag will die nackte Nummer; AW- ist die Browser-Schreibweise.
        ads_id = m.group(1)
    labels = ads_cfg.get("labels") or {}

    events = [e for e in (plan.get("events") or []) if isinstance(e, dict)]
    ads_events = []
    for e in events:
        name = e.get("name")
        if not (isinstance(name, str) and EVENT_NAME.match(name)):
            raise PlanError("Ungueltiger Eventname: %r" % name)
        if not e.get("google_ads"):
            continue
        label = labels.get(name)
        if not label:
            raise PlanError(
                "Event %r ist fuer Google Ads vorgesehen, aber google_ads.labels[%r] fehlt. "
                "Ohne Conversion-Label laesst sich kein Tag bauen." % (name, name))
        if not ADS_LABEL.match(str(label)):
            raise PlanError("google_ads.labels[%r] = %r sieht nicht nach einem Label aus." % (name, label))
        if not ads_id:
            raise PlanError("Es gibt Ads-Events, aber google_ads.conversion_id fehlt.")
        # Tagname: der Conversion-Name aus dem Ads-Konto, sonst der Eventname.
        # Die Beschreibung aus dem Plan ist dafuer zu lang.
        titel = (ads_cfg.get("conversion_names") or {}).get(name) or name
        ads_events.append((name, str(label), str(titel)))

    # Gemeinsamer Zaehlraum fuer Tags, Trigger und Clients - wie in echten Exporten.
    zaehler = iter(range(1, 10000))
    def nid():
        return str(next(zaehler))

    client = {"clientId": nid(), "name": "GA4 Client", "type": "gaaw_client", "parameter": [
        T("cookieDomain", "auto"), T("cookieMaxAgeInSec", "63072000"),
        B("activateDefaultPaths", True), T("cookiePath", "/"),
        T("cookieManagement", "server"), T("cookieName", "FPID")]}

    tags = [
        {"tagId": nid(), "name": "GA4 - alle Events", "type": "sgtmgaaw", "parameter": [
            B("redactVisitorIp", False), T("epToIncludeDropdown", "all"),
            B("isMeasurementIdMandatory", True), T("upToIncludeDropdown", "all"),
            T("measurementId", ga4)],
         "firingTriggerId": [ALL_EVENTS], "tagFiringOption": "ONCE_PER_EVENT",
         "monitoringMetadata": {"type": "MAP"}, "consentSettings": {"consentStatus": "NOT_SET"}},
        {"tagId": nid(), "name": "Server Conversion Linker", "type": "sgtmadscl", "parameter": [
            B("enableLinkerParams", True), B("enableCookieOverrides", False)],
         "firingTriggerId": [ALL_EVENTS], "tagFiringOption": "ONCE_PER_EVENT",
         "monitoringMetadata": {"type": "MAP"}, "consentSettings": {"consentStatus": "NOT_SET"}},
    ]

    trigger = []
    for name, label, titel in ads_events:
        tid = nid()
        trigger.append({"triggerId": tid, "name": "CE - " + name, "type": "CUSTOM_EVENT",
                        "customEventFilter": [{"type": "EQUALS", "parameter": [
                            T("arg0", "{{_event}}"), T("arg1", name)]}]})
        tags.append({"tagId": nid(), "name": "Google Ads Conversion - " + titel, "type": "sgtmadsct",
                     "parameter": [B("enableNewCustomerReporting", False),
                                   B("enableConversionLinker", True),
                                   B("enableProductReporting", False),
                                   T("conversionId", ads_id), T("conversionLabel", label),
                                   B("rdp", False)],
                     "firingTriggerId": [tid],
                     "consentSettings": {"consentStatus": "NOT_SET"}})

    kunde = plan.get("kunde") or plan.get("slug") or "Kunde"
    sgtm = plan.get("server_container_url") or ""
    container = {"name": "%s || Server" % kunde, "publicId": "GTM-SERVER",
                 "usageContext": ["SERVER"], "fingerprint": "0",
                 "tagManagerUrl": "https://tagmanager.google.com/"}
    if sgtm:
        container["taggingServerUrls"] = [sgtm]

    return {"exportFormatVersion": 2,
            "exportTime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "containerVersion": {"containerVersionId": "0", "container": container,
                                 "builtInVariable": [{"type": "EVENT_NAME", "name": "Event Name"}],
                                 "client": [client], "tag": tags, "trigger": trigger}}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan")
    ap.add_argument("-o", "--out", default="gtm-server-import.json")
    a = ap.parse_args()
    try:
        plan = json.load(open(a.plan, encoding="utf-8"))
    except (OSError, ValueError) as e:
        sys.exit("Plan nicht lesbar: %s" % e)
    try:
        export = build(plan)
    except PlanError as e:
        sys.exit("PLAN UNGUELTIG: %s" % e)

    fehler = container_pruefen(export)
    if fehler:
        print("FEHLER:\n- " + "\n- ".join(fehler), file=sys.stderr)
        sys.exit(1)
    if os.path.exists(a.out):
        sys.exit("FEHLER: %s existiert bereits. Anderen Namen mit -o waehlen." % a.out)
    d = os.path.dirname(os.path.abspath(a.out)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".part")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(export, f, ensure_ascii=False, indent=2)
    os.replace(tmp, a.out)
    cv = export["containerVersion"]
    print("OK: %s  (%d Tags, %d Trigger, %d Client)"
          % (a.out, len(cv["tag"]), len(cv["trigger"]), len(cv["client"])))
    for t in cv["tag"]:
        print("  TAG  %-10s %s" % (t["type"], t["name"]))
    print("\nNACH DEM IMPORT:")
    for h in hinweise(export):
        print("  - " + h)


if __name__ == "__main__":
    main()
