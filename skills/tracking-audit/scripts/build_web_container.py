#!/usr/bin/env python3
"""Erzeugt aus einem Tracking-Plan (JSON) eine importierbare GTM-Web-Container-Datei.

Nur eingebaute GTM-Typen, deren Export-Schlüssel an echten Exporten geprüft wurden:
googtag (Google Tag), gaawe (GA4-Event), awct (Google-Ads-Conversion), awud (User-Provided Data),
gclidw (Conversion Linker), html (Meta Pixel, Formular-Listener); Variablen v/c/jsm/awec.
Hinweis: In Custom-HTML-Tags werden {{Variablen}} ohne Anführungszeichen eingesetzt (Auflösung zur Laufzeit, Typ bleibt erhalten).
CMP-Tag (Cookiebot/Usercentrics) und Stape-Templates werden NICHT erzeugt -> aus der Galerie hinzufügen.

Aufruf:  python3 build_web_container.py plan.json -o gtm-web-import.json
Nur Standardbibliothek. Import in GTM: Verwaltung -> Container importieren -> neuer Workspace -> Zusammenführen.
"""
import argparse, json, math, os, re, sys, tempfile, datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lib.tracking_plan import assert_complete, assert_direct_build_supported

INIT_ALL_PAGES = "2147479573"  # eingebauter Trigger "Initialization - All Pages" (in Exporten belegt)
META_STANDARD = {"PageView", "ViewContent", "Search", "AddToCart", "AddToWishlist", "InitiateCheckout",
                 "AddPaymentInfo", "Purchase", "Lead", "CompleteRegistration", "Contact", "Schedule",
                 "SubmitApplication", "Subscribe", "StartTrial", "FindLocation", "CustomizeProduct", "Donate"}


# ---------- Validierung (Phase 4B/4E) ----------
CURRENCIES = {"EUR", "CHF", "USD", "GBP", "SEK", "NOK", "DKK", "PLN", "CZK", "HUF", "RON", "BGN"}
EVENT_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,39}$")
PIXEL_ID = re.compile(r"^[0-9]{6,20}$")
ADS_LABEL = re.compile(r"^[A-Za-z0-9_-]{5,40}$")
MEASUREMENT_ID = re.compile(r"^G-[A-Z0-9]{6,20}$")
ADS_ID = re.compile(r"^(AW-)?[0-9]{6,20}$")
CONSENT_MODES = {"basic", "advanced"}
ARCHITECTURES = {"browser", "server", "browser+server"}


class PlanError(Exception):
    pass


# Beispiel-IDs aus der eigenen Doku und den Beispielplaenen. Wer sie versehentlich
# stehen laesst, importiert einen Container, der Daten an ein fremdes Konto schickt
# oder gar nicht misst.
PLATZHALTER = {"G-XXXXXXXXXX", "AW-123456789", "AW-1", "ABCDEFGHIJK", "ABCDEFGHIJKLM",
               "123456789012345", "111111111111111", "G-TEST12345", "G-T1"}
PLATZHALTER_WORT = ("TODO", "REPLACE", "CHANGE_ME", "CHANGEME", "XXXX", "YOUR", "PLATZHALTER", "BEISPIEL")

# Data-Layer-Pfade, die nicht automatisch zu GTM-Variablen werden duerfen.
# Eine Variable auf dataLayer.email wuerde die Adresse an GA4/Meta weiterreichen.
PARAM_VERBOTEN = ("email", "mail", "phone", "telefon", "tel", "name", "vorname", "nachname",
                  "address", "adresse", "street", "strasse", "plz", "zip", "postal", "city",
                  "ort", "birth", "geburt", "iban", "card", "kreditkarte", "cvv", "password",
                  "passwort", "token", "session", "ssn", "steuer", "gender", "geschlecht")
PARAM_ERLAUBT = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){0,3}$")


def pruefe_platzhalter(feld, wert, erlaubt):
    w = str(wert).upper()
    if erlaubt:
        return wert
    if w in PLATZHALTER or any(x in w for x in PLATZHALTER_WORT):
        raise PlanError("%s enthaelt einen Platzhalter (%r). Echte ID eintragen oder "
                        "bewusst --allow-placeholder setzen." % (feld, wert))
    return wert


def pruefe_param(pfad):
    if not isinstance(pfad, str) or not PARAM_ERLAUBT.match(pfad):
        raise PlanError("events[].params: %r ist kein zulaessiger dataLayer-Pfad "
                        "(Kleinbuchstaben, Ziffern, Unterstrich, max. 4 Ebenen)." % (pfad,))
    tief = pfad.lower()
    treffer = [w for w in PARAM_VERBOTEN if w in tief]
    if treffer:
        raise PlanError("events[].params: %r sieht nach personenbezogenen Daten aus (%s). "
                        "Solche Felder gehoeren nicht automatisch in eine GTM-Variable."
                        % (pfad, ", ".join(treffer)))
    return pfad


def pruefe_server_url(url, resolver=None, dns_pending=False):
    """server_container_url: nur https und global erreichbare Zieladressen.

    ``resolver`` ist fuer hermetische Tests injizierbar und liefert IP-Strings bzw.
    ``ipaddress``-Objekte. Im Produktivpfad wird ``socket.getaddrinfo`` verwendet.

    ``dns_pending=True`` ueberspringt ausschliesslich die Namensaufloesung, fuer den Fall
    dass die Custom Domain beim Hoster beantragt, der CNAME aber noch nicht gesetzt ist.
    Schema-, Zugangsdaten- und Hostpruefung bleiben aktiv. Ein literales IP-Ziel wird
    weiterhin auf globale Erreichbarkeit geprueft - dafuer kann es keinen wartenden
    DNS-Eintrag geben.
    """
    import ipaddress
    import socket
    import urllib.parse
    t = urllib.parse.urlsplit(url)
    if t.scheme != "https":
        raise PlanError("server_container_url muss https sein (erhalten: %s)." % (t.scheme or "kein Schema"))
    if t.username or t.password:
        raise PlanError("server_container_url darf keine Zugangsdaten enthalten.")
    host = (t.hostname or "").lower()
    if not host:
        raise PlanError("server_container_url hat keinen Host.")
    try:
        try:
            direkt = ipaddress.ip_address(host)
            raw_ips = [direkt]
        except ValueError:
            if dns_pending:
                return url
            raw_ips = (resolver(host) if resolver is not None
                       else [ai[4][0] for ai in socket.getaddrinfo(host, None)])
        ips = {ip if isinstance(ip, (ipaddress.IPv4Address, ipaddress.IPv6Address))
               else ipaddress.ip_address(str(ip)) for ip in raw_ips}
    except (OSError, ValueError) as e:
        raise PlanError("server_container_url: DNS/IP-Pruefung von %s fehlgeschlagen (%s)." % (host, e))
    if not ips:
        raise PlanError("server_container_url: keine Adresse fuer %s gefunden." % host)
    for ip in ips:
        mapped = getattr(ip, "ipv4_mapped", None)
        global_ok = mapped.is_global if mapped is not None else ip.is_global
        if not global_ok:
            raise PlanError("server_container_url zeigt nicht auf eine global erreichbare Adresse (%s → %s)." % (host, ip))
    return url


def js(value):
    """Serialisiert einen Wert als JavaScript-Literal. Nie Stringverkettung.

    json.dumps liefert gueltiges JS fuer Strings, endliche Zahlen, Bool und None.
    </script> wird zusaetzlich zerlegt, damit der HTML-Parser den Tag nicht vorzeitig schliesst
    (OWASP XSS Prevention Cheat Sheet, Regel 3.1: Kontext JavaScript-String).
    """
    if isinstance(value, float) and not math.isfinite(value):
        raise PlanError("Nicht endlicher Zahlenwert (NaN/Infinity) ist nicht zulaessig.")
    if isinstance(value, (dict, list)):
        raise PlanError("Zusammengesetzter Wert an einer Stelle, die einen Skalar erwartet: %r" % (value,))
    out = json.dumps(value, ensure_ascii=False)
    return out.replace("</", "<\\/")


def need_str(plan_path, value, pattern, hint):
    if not isinstance(value, str) or not pattern.match(value):
        raise PlanError("%s ist ungueltig (%r). Erwartet: %s" % (plan_path, value, hint))
    return value


def need_number(plan_path, value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlanError("%s muss eine Zahl sein, ist aber %r." % (plan_path, value))
    if not math.isfinite(float(value)):
        raise PlanError("%s muss endlich sein, ist aber %r." % (plan_path, value))
    return value


def need_currency(plan_path, value):
    if value not in CURRENCIES:
        raise PlanError("%s: unbekannte Waehrung %r. Erlaubt: %s"
                        % (plan_path, value, ", ".join(sorted(CURRENCIES))))
    return value


def T(key, value):
    return {"type": "TEMPLATE", "key": key, "value": str(value)}


def B(key, value):
    return {"type": "BOOLEAN", "key": key, "value": "true" if value else "false"}


def table(key, rows, kname="parameter", vname="parameterValue"):
    return {"type": "LIST", "key": key, "list": [
        {"type": "MAP", "map": [T(kname, k), T(vname, v)]} for k, v in rows]}


class Builder:
    def __init__(self, plan, consent_settings=True, allow_placeholder=False, server_resolver=None,
                 server_dns_pending=False):
        self.allow_placeholder = allow_placeholder
        self.server_resolver = server_resolver
        self.server_dns_pending = server_dns_pending
        self.plan, self.cs = plan, consent_settings
        self.tags, self.triggers, self.vars = [], [], []
        self._id = 10
        self._trig_by_event, self._var_by_name = {}, {}
        self.warnings = []

    def nid(self):
        self._id += 1
        return str(self._id)

    # ---------- Variablen ----------
    def var(self, name, vtype, params):
        if name in self._var_by_name:
            return "{{%s}}" % name
        self.vars.append({"variableId": self.nid(), "name": name, "type": vtype, "parameter": params})
        self._var_by_name[name] = True
        return "{{%s}}" % name

    def const(self, name, value):
        return self.var(name, "c", [T("value", value)])

    def dlv(self, path):
        return self.var("DLV - " + path, "v", [T("dataLayerVersion", 2), B("setDefaultValue", False), T("name", path)])

    def event_id_var(self):
        # ES5 (GTM-kompatibel): gleiche ID für alle Tags desselben dataLayer-Events, bevorzugt event_id aus dem dataLayer
        js = ("function() {\n  var fromDL = {{DLV - event_id}};\n  if (fromDL) return fromDL;\n"
              "  var uid = {{DLV - gtm.uniqueEventId}};\n  window.__mtEventIds = window.__mtEventIds || {};\n"
              "  if (!window.__mtEventIds[uid]) {\n"
              "    window.__mtEventIds[uid] = new Date().getTime() + '.' + Math.random().toString(36).slice(2, 10);\n  }\n"
              "  return window.__mtEventIds[uid];\n}")
        self.dlv("event_id"); self.dlv("gtm.uniqueEventId")
        return self.var("CJS - Event ID", "jsm", [T("javascript", js)])

    # ---------- Trigger ----------
    def custom_event_trigger(self, event):
        if event in self._trig_by_event:
            return self._trig_by_event[event]
        tid = self.nid()
        self.triggers.append({"triggerId": tid, "name": "CE - " + event, "type": "CUSTOM_EVENT",
                              "customEventFilter": [{"type": "EQUALS", "parameter": [
                                  T("arg0", "{{_event}}"), T("arg1", event)]}]})
        self._trig_by_event[event] = tid
        return tid

    def pageview_trigger(self):
        if "__pageview" not in self._trig_by_event:
            tid = self.nid()
            self.triggers.append({"triggerId": tid, "name": "PV - Alle Seiten", "type": "PAGEVIEW"})
            self._trig_by_event["__pageview"] = tid
        return self._trig_by_event["__pageview"]

    def consent_update_trigger(self, event_name):
        """Trigger auf das Consent-Update-Ereignis der CMP.

        Ein spaeteres Consent-Update loest den Pageview-Trigger NICHT erneut aus
        (Google: Tag feuert nur, wenn die Einwilligung im Moment der Ausloesung vorliegt;
        Cookiebot: 'All Pages' durch den cookie_consent_update-Trigger ersetzen).
        """
        return self.custom_event_trigger(event_name)

    def domready_trigger(self):
        if "__domready" not in self._trig_by_event:
            tid = self.nid()
            self.triggers.append({"triggerId": tid, "name": "DOM Ready - Alle Seiten", "type": "DOM_READY"})
            self._trig_by_event["__domready"] = tid
        return self._trig_by_event["__domready"]

    # ---------- Tags ----------
    def tag(self, name, ttype, params, triggers, consent=None, firing="ONCE_PER_EVENT"):
        t = {"tagId": self.nid(), "name": name, "type": ttype, "parameter": params,
             "firingTriggerId": triggers, "tagFiringOption": firing,
             "monitoringMetadata": {"type": "MAP"}, "consentSettings": {"consentStatus": "NOT_SET"}}
        if consent and self.cs:
            # Zusätzliche Einwilligungsprüfung (Struktur aus der GTM-API abgeleitet -> nach Import prüfen)
            t["consentSettings"] = {"consentStatus": "NEEDED", "consentType": {
                "type": "LIST", "list": [{"type": "TEMPLATE", "value": c} for c in consent]}}
        self.tags.append(t)

    def build(self):
        p = self.plan
        ga4 = (p.get("ga4") or {}).get("measurement_id")
        ads = p.get("google_ads") or {}
        meta = p.get("meta") or {}
        sgtm = p.get("server_container_url")
        events = p.get("events") or []
        currency = need_currency("default_currency", p.get("default_currency", "EUR"))

        # --- Architekturentscheidung (Phase 4D) ---
        arch = p.get("architecture")
        if sgtm and not arch:
            raise PlanError(
                "server_container_url ist gesetzt, aber 'architecture' fehlt.\n"
                "Erlaubt: browser | server | browser+server.\n"
                "Ohne diese Angabe wuerden Browser- UND Server-Conversions erzeugt "
                "und Google Ads zaehlte doppelt.")
        if arch and arch not in ARCHITECTURES:
            raise PlanError("architecture muss eines von %s sein." % sorted(ARCHITECTURES))
        arch = arch or "browser"
        if arch in ("server", "browser+server") and not sgtm:
            raise PlanError("architecture=%s verlangt server_container_url." % arch)
        if arch == "browser" and sgtm:
            raise PlanError(
                "Widerspruch: architecture='browser', aber server_container_url ist gesetzt.\n"
                "Entweder server_container_url entfernen oder architecture auf "
                "'server' bzw. 'browser+server' setzen.")
        if sgtm:
            pruefe_server_url(sgtm, self.server_resolver, dns_pending=self.server_dns_pending)
            if self.server_dns_pending:
                self.warnings.append(
                    "server_container_url %s wurde NICHT aufgeloest (--server-dns-pending). "
                    "Vor dem Veroeffentlichen pruefen, dass der CNAME steht und der "
                    "Server-Container antwortet." % sgtm)
        self.arch = arch

        # --- Consent-Modus (Phase 4E) ---
        consent_cfg = p.get("consent") or {}
        mode = consent_cfg.get("mode")
        if mode not in CONSENT_MODES:
            raise PlanError(
                "consent.mode fehlt oder ist ungueltig (%r). Erlaubt: basic | advanced.\n"
                "basic  = auch Google-Tags feuern erst nach Einwilligung\n"
                "advanced = Google-Tags feuern mit cookielosen Pings vor der Einwilligung" % mode)
        upd = consent_cfg.get("update_event")
        if not upd and meta.get("pixel_id") and meta.get("browser_pixel", True):
            raise PlanError(
                "consent.update_event fehlt. Ohne dieses Ereignis wird der Meta-Basis-Tag "
                "nach nachtraeglicher Zustimmung nie initialisiert und alle spaeteren "
                "Meta-Events verpuffen.\n"
                "Cookiebot: \"cookie_consent_update\". Bei anderen CMPs den dort "
                "dokumentierten dataLayer-Ereignisnamen eintragen.")
        if upd:
            need_str("consent.update_event", upd, EVENT_NAME, "Ereignisname")
        self.consent_mode, self.consent_event = mode, upd

        if ga4:
            need_str("ga4.measurement_id", ga4, MEASUREMENT_ID, "G-XXXXXXXXXX")
            pruefe_platzhalter("ga4.measurement_id", ga4, self.allow_placeholder)
            mid = self.const("C - GA4 Measurement ID", ga4)
            cfg = [("send_page_view", "true")]
            if sgtm:
                cfg.append(("server_container_url", self.const("C - Server Container URL", sgtm)))
            # Basic Consent Mode: Google-Tags duerfen erst nach Einwilligung laden.
            ga4_consent = ["analytics_storage"] if self.consent_mode == "basic" else None
            ga4_trigger = [self.consent_update_trigger(self.consent_event)] if (
                self.consent_mode == "basic" and self.consent_event) else [INIT_ALL_PAGES]
            self.tag("Google Tag - GA4", "googtag", [T("tagId", mid), table("configSettingsTable", cfg)],
                     ga4_trigger, consent=ga4_consent, firing="ONCE_PER_LOAD")

        need_eid = bool(meta.get("pixel_id")) or bool(sgtm)
        eid = self.event_id_var() if need_eid else None

        if ads.get("conversion_id"):
            need_str("google_ads.conversion_id", str(ads["conversion_id"]), ADS_ID, "AW-123456789")
            pruefe_platzhalter("google_ads.conversion_id", ads["conversion_id"], self.allow_placeholder)
            cid = self.const("C - Google Ads Conversion ID", re.sub(r"^AW-", "", str(ads["conversion_id"])))
            # Der Conversion Linker schreibt _gcl_*-Cookies, haengt also an ad_storage.
            # Als Google-Tag hat er eine eingebaute Einwilligungspruefung - im Basic Mode
            # soll er aber gar nicht erst vor der Entscheidung laufen.
            if self.consent_mode == "basic" and self.consent_event:
                self.tag("Conversion Linker", "gclidw", [],
                         [self.consent_update_trigger(self.consent_event)],
                         consent=["ad_storage"], firing="ONCE_PER_LOAD")
            else:
                self.tag("Conversion Linker", "gclidw", [], [INIT_ALL_PAGES], firing="ONCE_PER_LOAD")
            if ads.get("enhanced_conversions"):
                self.var("UPD - User-Provided Data", "awec", [T("mode", "CODE"), T("dataSource", self.dlv("user_data"))])

        if meta.get("pixel_id") and meta.get("browser_pixel", True):
            need_str("meta.pixel_id", str(meta["pixel_id"]), PIXEL_ID, "15-stellige Zahl")
            pruefe_platzhalter("meta.pixel_id", meta["pixel_id"], self.allow_placeholder)
            pid = self.const("C - Meta Pixel ID", str(meta["pixel_id"]))
            # Die Pixel-ID ist geprueft (nur Ziffern); GTM setzt {{Variablen}} ohne
            # Anfuehrungszeichen ein, deshalb steht sie hier bewusst ohne Quotes.
            base = ("<script>\n!function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?\n"
                    "n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;\n"
                    "n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;\n"
                    "t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,\n"
                    "document,'script','https://connect.facebook.net/en_US/fbevents.js');\n"
                    "if (!window.__mtFbqInit) { window.__mtFbqInit = 1;\n"
                    "  fbq('init', " + pid + ");\n"
                    "  fbq('track', 'PageView', {}, {eventID: " + eid + "});\n}\n</script>")
            # Consent-Update-Trigger statt Pageview: ein spaeteres "Akzeptieren" loest
            # den Pageview nicht erneut aus, das Consent-Ereignis dagegen schon -
            # und es feuert auch beim naechsten Besuch mit gespeicherter Entscheidung.
            self.tag("Meta Pixel - Base + PageView", "html", [T("html", base), B("supportDocumentWrite", False)],
                     [self.consent_update_trigger(self.consent_event)], consent=["ad_storage"],
                     firing="ONCE_PER_LOAD")

        for ev in events:
            name = need_str("events[].name", ev.get("name"), EVENT_NAME, "Buchstaben, Ziffern, Unterstrich")
            trig = self.custom_event_trigger(ev.get("trigger_event", name))
            ecommerce = ev.get("ecommerce", False)
            if ga4 and ev.get("ga4", True):
                params = [B("sendEcommerceData", ecommerce)]
                if ecommerce:
                    params.append(T("getEcommerceDataFrom", "dataLayer"))
                _pars = ev.get("params")
                if _pars is not None:
                    if not isinstance(_pars, dict):
                        raise PlanError("events[].params muss ein Objekt sein, ist aber %r." % type(_pars).__name__)
                    for _pfad in _pars.values():
                        pruefe_param(_pfad)
                params += [B("enhancedUserId", False), T("eventName", name), T("measurementIdOverride", "{{C - GA4 Measurement ID}}")]
                rows = [(k, self.dlv(v) if isinstance(v, str) and not v.startswith("{{") else v) for k, v in (ev.get("params") or {}).items()]
                if eid:
                    rows.append(("event_id", eid))
                if rows:
                    params.append(table("eventSettingsTable", rows))
                self.tag("GA4 - " + name, "gaawe", params, [trig])
            if ads.get("conversion_id") and ev.get("ads_label") and self.arch != "server":
                need_str("events[].ads_label", ev["ads_label"], ADS_LABEL, "Label aus Google Ads")
                pruefe_platzhalter("events[].ads_label", ev["ads_label"], self.allow_placeholder)
                ap = [T("conversionId", "{{C - Google Ads Conversion ID}}"), T("conversionLabel", ev["ads_label"]),
                      B("enableConversionLinker", True)]
                if ecommerce:
                    ap += [T("conversionValue", self.dlv("ecommerce.value")), T("currencyCode", self.dlv("ecommerce.currency")),
                           T("orderId", self.dlv("ecommerce.transaction_id"))]
                elif ev.get("value") is not None:
                    ap += [T("conversionValue", need_number("events[].value", ev["value"])),
                           T("currencyCode", need_currency("events[].currency", ev.get("currency", currency)))]
                self.tag("Google Ads - Conversion - " + name, "awct", ap, [trig])
                if ads.get("enhanced_conversions"):
                    self.tag("Google Ads - User-Provided Data - " + name, "awud",
                             [T("userDataVariable", "{{UPD - User-Provided Data}}"), B("enableConversionLinker", True),
                              T("conversionId", "{{C - Google Ads Conversion ID}}")], [trig])
            mev = ev.get("meta_event")
            if meta.get("pixel_id") and meta.get("browser_pixel", True) and mev:
                need_str("events[].meta_event", mev, EVENT_NAME, "Buchstaben, Ziffern, Unterstrich")
                method = "track" if mev in META_STANDARD else "trackCustom"
                if ecommerce:
                    data = "{value: {{DLV - ecommerce.value}}, currency: {{DLV - ecommerce.currency}}}"
                    self.dlv("ecommerce.value"); self.dlv("ecommerce.currency")
                elif ev.get("value") is not None:
                    val = need_number("events[].value", ev["value"])
                    cur = need_currency("events[].currency", ev.get("currency", currency))
                    data = "{value: %s, currency: %s}" % (js(val), js(cur))
                else:
                    data = "{}"
                html = ("<script>\nif (window.fbq) { fbq(%s, %s, %s, {eventID: %s}); }\n</script>"
                        % (js(method), js(mev), data, eid))
                self.tag("Meta Pixel - " + mev, "html", [T("html", html), B("supportDocumentWrite", False)], [trig], consent=["ad_storage"])

        listeners = p.get("form_listeners") or []
        lead_event = need_str("lead_event", p.get("lead_event", "generate_lead"),
                              EVENT_NAME, "Buchstaben, Ziffern, Unterstrich")
        snippets = {
            "cf7": "document.addEventListener('wpcf7mailsent', function(e) {\n  window.dataLayer.push({event: %s, form_id: 'cf7-' + (e.detail && e.detail.contactFormId)});\n});",
            "elementor": "if (window.jQuery) { jQuery(document).on('submit_success', function(e) {\n  window.dataLayer.push({event: %s, form_id: 'elementor'});\n}); }",
            "wpforms": "if (window.jQuery) { jQuery(document).on('wpformsAjaxSubmitSuccess', function(e) {\n  window.dataLayer.push({event: %s, form_id: 'wpforms-' + (e.target && e.target.id)});\n}); }",
        }
        body = "\n".join(snippets[l] % js(lead_event) for l in listeners if l in snippets)
        unknown = [l for l in listeners if l not in snippets]
        if unknown:
            self.warnings.append("Unbekannte Formular-Listener ignoriert: %s" % unknown)
        if body:
            html = "<script>\nwindow.dataLayer = window.dataLayer || [];\n" + body + "\n</script>"
            self.tag("Listener - Formular-Erfolg -> " + lead_event, "html", [T("html", html), B("supportDocumentWrite", False)],
                     [self.domready_trigger()])

        # Link-Listener: tel:/mailto:-Klicks als dataLayer-Events.
        # Delegiert auf document, damit auch nachtraeglich eingefuegte Links greifen.
        link_listeners = p.get("link_listeners") or {}
        if link_listeners:
            if not isinstance(link_listeners, dict):
                raise PlanError(
                    "link_listeners muss ein Objekt sein, z. B. "
                    '{"tel": "click_to_call", "mailto": "contact_email"}.')
            erlaubt = {"tel", "mailto"}
            unbekannt = sorted(set(link_listeners) - erlaubt)
            if unbekannt:
                raise PlanError("link_listeners kennt nur %s (erhalten: %s)."
                                % (", ".join(sorted(erlaubt)), ", ".join(unbekannt)))
            paare = []
            for schema in sorted(link_listeners):
                ev = need_str("link_listeners.%s" % schema, link_listeners[schema],
                              EVENT_NAME, "Buchstaben, Ziffern, Unterstrich")
                paare.append("    if (h.indexOf(%s) === 0) { push(%s, h); return; }"
                             % (js(schema + ":"), js(ev)))
            sel = ", ".join('a[href^="%s:"]' % s for s in sorted(link_listeners))
            html = (
                "<script>\n"
                "window.dataLayer = window.dataLayer || [];\n"
                "(function () {\n"
                "  function push(ev, href) { window.dataLayer.push({event: ev, link_url: href}); }\n"
                "  document.addEventListener('click', function (e) {\n"
                "    var t = e.target;\n"
                "    if (!t || !t.closest) { return; }\n"
                "    var a = t.closest(%s);\n"
                "    if (!a) { return; }\n"
                "    var h = a.getAttribute('href') || '';\n"
                "%s\n"
                "  }, true);\n"
                "})();\n"
                "</script>" % (js(sel), "\n".join(paare)))
            self.tag("Listener - Kontaktlinks", "html",
                     [T("html", html), B("supportDocumentWrite", False)],
                     [self.domready_trigger()])

        # Verweildauer-Events: pro Seitenaufruf ein setTimeout je Schwelle.
        # Bewusst kein GTM-TIMER-Trigger, damit die Schwelle genau einmal feuert.
        timer_events = p.get("timer_events") or {}
        if timer_events:
            if not isinstance(timer_events, dict):
                raise PlanError(
                    'timer_events muss ein Objekt sein, z. B. {"engagement_1min": 60}. '
                    "Schluessel = Eventname, Wert = Sekunden.")
            zeilen = []
            for ev in sorted(timer_events):
                name = need_str("timer_events-Eventname", ev, EVENT_NAME,
                                "Buchstaben, Ziffern, Unterstrich")
                sek = timer_events[ev]
                if not isinstance(sek, int) or isinstance(sek, bool) or not 1 <= sek <= 3600:
                    raise PlanError(
                        "timer_events[%s]: Sekunden muessen eine ganze Zahl zwischen 1 und 3600 "
                        "sein (erhalten: %r)." % (name, sek))
                zeilen.append("  window.setTimeout(function () { push(%s); }, %d);"
                              % (js(name), sek * 1000))
            html = ("<script>\n"
                    "window.dataLayer = window.dataLayer || [];\n"
                    "(function () {\n"
                    "  function push(ev) { window.dataLayer.push({event: ev}); }\n"
                    + "\n".join(zeilen) + "\n"
                    "})();\n"
                    "</script>")
            self.tag("Listener - Verweildauer", "html",
                     [T("html", html), B("supportDocumentWrite", False)],
                     [self.domready_trigger()])
            self.warnings.append(
                "timer_events erzeugt Verweildauer-Events (%s). Verweildauer ist ein "
                "Engagement-Signal, keine Conversion: in Google Ads auf sekundaer lassen, "
                "sonst optimiert Smart Bidding auf Verweildauer statt auf Anfragen."
                % ", ".join(sorted(timer_events)))

        return {
            "exportFormatVersion": 2,
            "exportTime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "containerVersion": {
                "accountId": "0", "containerId": "0", "containerVersionId": "0",
                "container": {"accountId": "0", "containerId": "0", "name": p.get("container_name", "meixner-toolkit Import"),
                              "usageContext": ["WEB"]},
                "tag": self.tags, "trigger": self.triggers, "variable": self.vars,
                "builtInVariable": [{"accountId": "0", "containerId": "0", "type": "EVENT", "name": "Event"}],
            },
        }


def validate(export):
    """Selbstprüfung: IDs eindeutig, Trigger-Referenzen und Variablen-Referenzen auflösbar."""
    cv = export["containerVersion"]
    errs = []
    ids = [t["tagId"] for t in cv["tag"]] + [t["triggerId"] for t in cv["trigger"]] + [v["variableId"] for v in cv["variable"]]
    if len(ids) != len(set(ids)):
        errs.append("Doppelte IDs")
    trig_ids = {t["triggerId"] for t in cv["trigger"]} | {INIT_ALL_PAGES}
    for t in cv["tag"]:
        for fid in t["firingTriggerId"]:
            if fid not in trig_ids:
                errs.append("Tag '%s' verweist auf unbekannten Trigger %s" % (t["name"], fid))
    names = {v["name"] for v in cv["variable"]} | {"_event", "Event"}
    for ref in set(re.findall(r"\{\{([^}]+)\}\}", json.dumps(export))):
        if ref not in names:
            errs.append("Unbekannte Variable {{%s}}" % ref)
    return errs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan")
    ap.add_argument("-o", "--out", default="gtm-web-import.json")
    ap.add_argument("--allow-placeholder", action="store_true",
                    help="Beispiel-IDs wie G-XXXXXXXXXX zulassen (nur fuer Tests)")
    ap.add_argument("--no-consent-settings", action="store_true", help="keine zusätzlichen Einwilligungsprüfungen an Meta-Tags setzen")
    ap.add_argument("--server-dns-pending", action="store_true",
                    help="Namensaufloesung der server_container_url ueberspringen, wenn die "
                         "Custom Domain beantragt, der CNAME aber noch nicht gesetzt ist. "
                         "Erzeugt eine Warnung; vor dem Veroeffentlichen pruefen.")
    a = ap.parse_args()
    plan = json.load(open(a.plan, encoding="utf-8"))
    try:
        assert_complete(plan)
        assert_direct_build_supported(plan)
    except ValueError as e:
        sys.exit(str(e))
    b = Builder(plan, consent_settings=not a.no_consent_settings,
                allow_placeholder=a.allow_placeholder,
                server_dns_pending=a.server_dns_pending)
    req = plan.get("requirements") or {}
    if req.get("internal_traffic") == "filter":
        b.warnings.append("GA4 Internal-Traffic-Definition/Data-Filter ist eine GA4-Admin-Einstellung und nicht Bestandteil dieses GTM-JSON.")
    pay = req.get("payment_referrals")
    if isinstance(pay, list) and pay:
        b.warnings.append("GA4 Unwanted Referrals fuer Payment-Domains (%s) in GA4 Admin konfigurieren; nicht Bestandteil dieses GTM-JSON." % ", ".join(pay))
    if req.get("refund_strategy") == "manual":
        b.warnings.append("Refunds/Stornos sind als manuell dokumentiert und werden von diesem Container nicht automatisch erfasst.")
    try:
        export = b.build()
    except PlanError as e:
        sys.exit("PLAN UNGUELTIG: %s" % e)
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        sys.exit("PLAN UNGUELTIG: unerwarteter Aufbau (%s: %s).\n"
                 "Aufbau siehe references/gtm-json.md." % (type(e).__name__, e))
    errs = validate(export)
    if errs:
        print("FEHLER:\n- " + "\n- ".join(errs), file=sys.stderr)
        sys.exit(1)
    if os.path.exists(a.out):
        sys.exit("FEHLER: %s existiert bereits. Anderen Namen mit -o waehlen." % a.out)
    d = os.path.dirname(os.path.abspath(a.out)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".part")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(export, f, ensure_ascii=False, indent=2)
    os.replace(tmp, a.out)
    cv = export["containerVersion"]
    print("OK: %s  (%d Tags, %d Trigger, %d Variablen) – Architektur: %s, Consent Mode: %s"
          % (a.out, len(cv["tag"]), len(cv["trigger"]), len(cv["variable"]), b.arch, b.consent_mode))
    for t in cv["tag"]:
        print("  TAG  %-6s %s" % (t["type"], t["name"]))
    for w in b.warnings:
        print("WARNUNG: " + w)


if __name__ == "__main__":
    main()
