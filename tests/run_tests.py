#!/usr/bin/env python3
"""Regressionstests fuer meixner-toolkit.

Aufruf:  python3 tests/run_tests.py
         oder python3 tests/run_tests.py --phase1 / --phase2
Erwartet: CLAUDE_PLUGIN_ROOT gesetzt oder Aufruf aus dem Plugin-Wurzelverzeichnis.

Bewusst ohne Testframework - eine Datei, Standardbibliothek, laeuft ueberall.
Jeder Test deckt einen Vertrag oder eine Sicherheitsgrenze ab, nicht Implementierungsdetails.
"""
import http.server
import importlib.util
import json
import os
import socketserver
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[1]))
os.environ["CLAUDE_PLUGIN_ROOT"] = str(ROOT)
ERGEBNISSE = []


def pruefe(name, bedingung, detail=""):
    ERGEBNISSE.append((name, bool(bedingung), detail))
    print("  %-52s %s%s" % (name, "PASS" if bedingung else "FAIL",
                            "" if bedingung else "  <- " + str(detail)[:90]))


def modul(pfad, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / pfad)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---------------------------------------------------------------- Fixture-Server
class Fixture(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/robots.txt":
            b, ct = b"User-agent: *\nAllow: /\nSitemap: http://127.0.0.1:8097/sitemap.xml\n", "text/plain"
        elif self.path == "/sitemap.xml":
            b, ct = (b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                     b'<url><loc>http://127.0.0.1:8097/</loc></url></urlset>'), "application/xml"
        elif self.path == "/noindex":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("x-robots-tag", "noindex")
            b = b"<html><head><title>x</title></head><body></body></html>"
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
            return
        else:
            b, ct = (b'<html><head><title>Fixture</title><meta name="description" content="d">'
                     b'</head><body><h1>Hallo</h1></body></html>'), "text/html"
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    do_HEAD = do_GET


def starte_fixture(port=8097):
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", port), Fixture)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


# ---------------------------------------------------------------- A: Launch-Check
def test_launch():
    print("\nA. Launch-Check")
    lc = modul("skills/launch/scripts/launch_check.py", "lc")
    pruefe("add() ist definiert", callable(getattr(lc, "add", None)),
           "P0-A: fehlte in 0.7.5, jeder Lauf endete im NameError")

    lc.checks.clear()
    lc.add("HOCH", "TEST", "Titel", "Detail https://x.de/a?token=geheim")
    eintrag = lc.checks[-1]
    pruefe("Befund-Datenmodell level/id/titel/detail",
           set(eintrag) == {"level", "id", "titel", "detail"}, eintrag)
    pruefe("add() redigiert URLs im Detailtext", "geheim" not in eintrag["detail"], eintrag["detail"])

    srv = starte_fixture()
    try:
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, str(ROOT / "skills/launch/scripts/launch_check.py"),
                                "http://127.0.0.1:8097/", "--out", d + "/lr.json"],
                               capture_output=True, text=True, timeout=120)
            pruefe("Lauf gegen Fixture ohne NameError", "NameError" not in r.stderr,
                   (r.stderr or "")[-160:])
            pruefe("Prozess terminiert regulaer", r.returncode in (0, 1, 2), r.returncode)
            ok = Path(d + "/lr.json").exists()
            pruefe("Report wird geschrieben", ok)
            if ok:
                rep = json.loads(Path(d + "/lr.json").read_text(encoding="utf-8"))
                pruefe("Report enthaelt Befunde im Vertrag",
                       isinstance(rep.get("checks"), list) and
                       all({"level", "id", "titel"} <= set(c) for c in rep["checks"]),
                       list(rep)[:6])
    finally:
        srv.shutdown()
        srv.server_close()

    # Vollstaendiger, hermetischer Erfolgspfad: Netzwerk/SSL werden injiziert,
    # die produktive SSRF-Policy wird fuer Tests nicht aufgeweicht.
    lc.checks.clear(); lc.ALLOWED_HOSTS.clear()
    home = (b'<html><head><title>Fixture</title></head><body>'
            b'<a href="/impressum">Impressum</a><a href="/datenschutz">Datenschutz</a></body></html>')
    def fake_chain(u, *a, **k):
        return ([{"url": "https://example.test/", "status": 200}],
                {"Strict-Transport-Security": "max-age=31536000"}, home)
    def fake_fetch(u, *a, **k):
        if u.endswith("/robots.txt"):
            return 200, {}, b"User-agent: *\nAllow: /\nSitemap: https://example.test/sitemap.xml\n"
        if u.endswith("/sitemap.xml"):
            return 200, {}, b'<urlset><url><loc>https://example.test/</loc></url></urlset>'
        if u.endswith("-mt404"):
            return 404, {}, b""
        return 200, {}, home
    class _Sock:
        def __enter__(self): return self
        def __exit__(self, *a): return False
    class _SSock(_Sock):
        def getpeercert(self): return {"notAfter": "Jan 01 00:00:00 2099 GMT"}
    class _Ctx:
        def wrap_socket(self, *a, **k): return _SSock()
    import ipaddress
    old = (lc.chain, lc.fetch, lc.socket.create_connection, lc.ssl.create_default_context, lc.time.sleep,
           lc.guard.RESOLVER, list(sys.argv))
    ssl_targets = []
    try:
        lc.chain, lc.fetch = fake_chain, fake_fetch
        lc.guard.RESOLVER = lambda host: [ipaddress.ip_address("93.184.216.34")]
        lc.socket.create_connection = lambda target, *a, **k: (ssl_targets.append(target) or _Sock())
        lc.ssl.create_default_context = lambda: _Ctx()
        lc.time.sleep = lambda *_: None
        with tempfile.TemporaryDirectory() as d:
            out = str(Path(d) / "launch.json")
            sys.argv = ["launch_check.py", "https://example.test/", "--out", out]
            try:
                lc.main()
                rc = 0
            except SystemExit as e:
                rc = int(e.code or 0)
            pruefe("Launch-Erfolgspfad hermetisch komplett", rc == 0 and Path(out).exists(), rc)
            if Path(out).exists():
                rep = json.loads(Path(out).read_text(encoding="utf-8"))
                pruefe("Launch-Erfolgspfad prueft Sitemap-URL", rep.get("sitemap_urls_geprueft") == 1, rep)
                pruefe("Launch-SSL verbindet zur verifizierten IP statt erneut zum Hostnamen",
                       bool(ssl_targets) and ssl_targets[0][0] == "93.184.216.34", ssl_targets)
    finally:
        (lc.chain, lc.fetch, lc.socket.create_connection, lc.ssl.create_default_context, lc.time.sleep,
         lc.guard.RESOLVER, sys.argv) = old


# ---------------------------------------------------------------- B: URL-Guard
def test_urlguard():
    print("\nB. URL-Guard")
    g = modul("lib/urlguard.py", "urlguard")
    verboten = ["http://127.0.0.1/", "http://localhost/", "http://10.0.0.1/",
                "http://172.16.0.1/", "http://192.168.1.1/", "http://169.254.1.1/",
                "http://100.64.0.1/", "http://198.18.0.1/", "http://192.0.2.1/",
                "http://[::1]/", "http://[::ffff:7f00:1]/", "http://[2002:7f00:1::]/",
                "http://[64:ff9b::7f00:1]/", "file:///etc/passwd", "ftp://example.com/",
                "data:text/html,x", "javascript:alert(1)",
                "http://user:pw@example.com/", "http://example.com:22/"]
    for u in verboten:
        try:
            g.pruefe(u)
            pruefe("blockiert: " + u[:40], False, "wurde durchgelassen")
        except g.Blocked:
            pruefe("blockiert: " + u[:40], True)
        except Exception as e:
            pruefe("blockiert: " + u[:40], False, "falsche Ausnahme %s" % type(e).__name__)
    # Hermetisch: der Resolver wird injiziert. Vorher loeste der Test echtes DNS auf
    # und schlug in Umgebungen ohne Internet fehl - ein Test darf davon nicht abhaengen.
    import ipaddress
    g.RESOLVER = lambda host: [ipaddress.ip_address("93.184.216.34")]   # oeffentlich
    try:
        g.pruefe("https://irgendeine-domain.test/")
        pruefe("erlaubt: oeffentliche IP (Resolver injiziert)", True)
    except g.Blocked as e:
        pruefe("erlaubt: oeffentliche IP (Resolver injiziert)", False, e)
    g.RESOLVER = lambda host: [ipaddress.ip_address("10.1.2.3")]        # DNS zeigt intern
    try:
        g.pruefe("https://sieht-oeffentlich-aus.test/")
        pruefe("blockiert: Hostname loest auf private IP auf", False, "durchgelassen")
    except g.Blocked:
        pruefe("blockiert: Hostname loest auf private IP auf", True)
    g.RESOLVER = lambda host: [ipaddress.ip_address("fd00::1")]         # privates IPv6
    try:
        g.pruefe("https://ipv6.test/")
        pruefe("blockiert: privates IPv6 aus DNS", False, "durchgelassen")
    except g.Blocked:
        pruefe("blockiert: privates IPv6 aus DNS", True)
    g.RESOLVER = None
    r = g.redigiere("https://a.de/x?gclid=ABC&email=max@test.de&page=2")
    pruefe("Redaction entfernt gclid und email", "ABC" not in r and "max@test.de" not in r, r)
    pruefe("Redaction behaelt unverfaengliche Parameter", "page=2" in r, r)


# ---------------------------------------------------------------- C: Kundenbericht
def test_bericht():
    print("\nC. Kundenbericht")
    renderer = ROOT / "skills/kundenbericht/scripts/render_report.mjs"
    def report_env(root):
        env = os.environ.copy(); env["MEIXNER_TOOLKIT_HOME"] = str(root); return env
    beispiele = list((ROOT / "skills/kundenbericht/examples").glob("*.json"))
    pruefe("mindestens ein offizielles Beispiel vorhanden", bool(beispiele))
    for b in beispiele:
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run(["node", str(renderer), str(b), "--out", d + "/r.html"],
                               capture_output=True, text=True, timeout=120, cwd=d, env=report_env(d))
            html = Path(d + "/r.html").read_text(encoding="utf-8") if Path(d + "/r.html").exists() else ""
            pruefe("Beispiel rendert: " + b.name, r.returncode == 0 and len(html) > 500,
                   (r.stdout + r.stderr).strip()[:150])
            if html:
                pruefe("HTML enthaelt den Kundennamen",
                       json.loads(b.read_text(encoding="utf-8")).get("kunde", "") in html)

    def rendere(audit, extra=None):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.json"
            f.write_text(json.dumps(audit), encoding="utf-8")
            r = subprocess.run(["node", str(renderer), str(f), "--out", d + "/r.html"] + (extra or []),
                               capture_output=True, text=True, timeout=60, cwd=d, env=report_env(d))
            html = Path(d + "/r.html").read_text(encoding="utf-8") if Path(d + "/r.html").exists() else ""
            return r, html

    basis = {"typ": "seogeo", "kunde": "K", "domain": "a.de", "scorecard": [], "findings": []}
    r, _ = rendere({**basis, "typ": "quatsch"})
    pruefe("unbekannter typ wird abgelehnt", r.returncode != 0)
    r, _ = rendere({**basis, "scorecard": [{"bereich": "T", "status": "unsinn"}]})
    pruefe("unbekannter status wird abgelehnt", r.returncode != 0)
    r, _ = rendere({**basis, "findings": [{"titel": "x", "prioritaet": "ultra"}]})
    pruefe("unbekannte prioritaet wird abgelehnt", r.returncode != 0)
    r, _ = rendere({k: v for k, v in basis.items() if k != "domain"})
    pruefe("fehlende domain wird abgelehnt", r.returncode != 0)
    r, _ = rendere({k: v for k, v in basis.items() if k != "kunde"})
    pruefe("fehlender kunde wird abgelehnt", r.returncode != 0)

    _, html = rendere({**basis, "scorecard": [{"bereich": "T", "status": "gut",
                                              "anzahl": "3</td><script>alert(1)</script>"}]})
    pruefe("HTML-Injection ueber scorecard.anzahl neutralisiert",
           "<script>alert(1)</script>" not in html)
    _, html = rendere({**basis, "findings": [{"titel": "<img src=x onerror=alert(1)>",
                                             "prioritaet": "hoch", "bereich": "T"}]})
    pruefe("HTML-Injection ueber findings.titel escapt",
           "<img src=x onerror=" not in html and "&lt;img" in html)

    # Ein vorbereitetes .part-Symlink darf nie verfolgt oder geloescht werden.
    if os.name != "nt":
        with tempfile.TemporaryDirectory() as d:
            cwd = Path(d) / "work"; cwd.mkdir()
            outside = Path(d) / "outside"; outside.mkdir()
            audit = cwd / "a.json"; audit.write_text(json.dumps(basis), encoding="utf-8")
            victim = outside / "victim.txt"; victim.write_text("UNVERAENDERT", encoding="utf-8")
            os.symlink(victim, cwd / "r.html.part")
            r = subprocess.run(["node", str(renderer), str(audit), "--out", str(cwd / "r.html")],
                               capture_output=True, text=True, timeout=60, cwd=cwd, env=report_env(cwd))
            pruefe("Report folgt keinem vorbereiteten .part-Symlink",
                   r.returncode != 0 and victim.read_text(encoding="utf-8") == "UNVERAENDERT",
                   (r.stdout + r.stderr)[-180:])
            pruefe("fremder .part-Symlink bleibt bei Abbruch unangetastet", (cwd / "r.html.part").is_symlink())

        with tempfile.TemporaryDirectory() as d:
            cwd = Path(d) / "work"; cwd.mkdir()
            outside = Path(d) / "outside"; outside.mkdir()
            audit = cwd / "a.json"; audit.write_text(json.dumps(basis), encoding="utf-8")
            os.symlink(outside, cwd / "link")
            r = subprocess.run(["node", str(renderer), str(audit), "--out", str(cwd / "link" / "r.html")],
                               capture_output=True, text=True, timeout=60, cwd=cwd, env=report_env(cwd))
            pruefe("Report schreibt nicht durch symlinkten Ausgabeordner nach ausserhalb",
                   r.returncode != 0 and not (outside / "r.html").exists(), (r.stdout + r.stderr)[-180:])

    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "a.json"; f.write_text(json.dumps(basis), encoding="utf-8")
        cfg = Path(d) / "c.json"
        cfg.write_text(json.dumps({"branding": {"logo": "http://127.0.0.1/logo.png"}}), encoding="utf-8")
        r = subprocess.run(["node", str(renderer), str(f), "--out", str(Path(d)/"r.html"),
                            "--config", str(cfg), "--remote-logo"],
                           capture_output=True, text=True, timeout=60, cwd=d, env=report_env(d))
        html = (Path(d)/"r.html").read_text(encoding="utf-8") if (Path(d)/"r.html").exists() else ""
        pruefe("privates Remote-Logo wird trotz Opt-in nicht eingebettet",
               r.returncode == 0 and "127.0.0.1/logo.png" not in html and "Netzwerkpolicy" in r.stderr,
               (r.stdout + r.stderr)[-180:])


# ---------------------------------------------------------------- D: Tracking-Builder
def test_builder():
    print("\nD. Tracking-Builder")
    gen = ROOT / "skills/tracking-audit/scripts/build_web_container.py"
    gen_mod = modul("skills/tracking-audit/scripts/build_web_container.py", "builder_tests")

    # Genau ein echter CLI-Smoke-Test prueft Argumente, JSON-Ein/Ausgabe und Exitcode.
    # Die vielen Negativfaelle laufen danach direkt gegen dieselbe Produktlogik. Das
    # vermeidet dutzende kurzlebige Python-Subprozesse, die auf manchen CI-/Sandbox-
    # Hosts sporadisch beim Prozess-Spawn/communicate festhingen, obwohl der Builder
    # selbst den identischen Plan einzeln korrekt ablehnte.
    def baue_cli(plan, extra=None):
        with tempfile.TemporaryDirectory() as d:
            Path(d + "/p.json").write_text(json.dumps(plan, default=str), encoding="utf-8")
            r = subprocess.run([sys.executable, str(gen), d + "/p.json", "-o", d + "/o.json"] + (extra or []),
                               capture_output=True, text=True, timeout=30)
            out = json.loads(Path(d + "/o.json").read_text(encoding="utf-8")) if Path(d + "/o.json").exists() else None
            return r, out

    def baue_direkt(plan, allow_placeholder=False):
        try:
            gen_mod.assert_complete(plan)
            gen_mod.assert_direct_build_supported(plan)
            b = gen_mod.Builder(
                plan,
                consent_settings=True,
                allow_placeholder=allow_placeholder,
                # Hermetisch: falls ein Test spaeter eine gueltige sGTM-URL erreicht,
                # wird niemals echtes DNS benoetigt.
                server_resolver=lambda host: ["93.184.216.34"],
            )
            out = b.build()
            errs = gen_mod.validate(out)
            if errs:
                return False, None, "\n".join(errs)
            return True, out, ""
        except (ValueError, gen_mod.PlanError, KeyError, TypeError, AttributeError) as e:
            return False, None, "%s: %s" % (type(e).__name__, e)

    req_browser = {"gate_version": 1, "open_questions": [], "site_type": "mpa",
                   "primary_domain": "www.kunde.de", "event_source": "dataLayer",
                   "event_source_verified": True, "conversion_success_verified": True,
                   "consent_strategy_verified": True, "cross_domain": "not_required",
                   "internal_traffic": "filter",
                   "evidence": {
                       "event_source": "GTM Preview: dataLayer Event am Testpfad beobachtet",
                       "conversion_success": "GTM Preview: Erfolgsereignis am Testpfad beobachtet",
                       "consent_strategy": "Consent-Test und CMP-Konfiguration verifiziert"
                   },
                   "event_evidence": {
                       "generate_lead": "GTM Preview: generate_lead beobachtet"
                   }}
    gueltig = {"ga4": {"measurement_id": "G-ABCDE12345"},
               "consent": {"mode": "advanced", "update_event": "cookie_consent_update"},
               "meta": {"pixel_id": "987654321098765", "browser_pixel": True},
               "events": [{"name": "generate_lead", "meta_event": "Lead", "value": 50, "currency": "EUR"}],
               "requirements": req_browser}
    r, out = baue_cli(gueltig)
    pruefe("gueltiger Browser-Plan baut", r.returncode == 0 and out is not None,
           (r.stdout + r.stderr)[:140])
    if out:
        tags = out["containerVersion"]["tag"]
        basis = [t for t in tags if "Base" in t["name"]]
        trig = {t["triggerId"]: t for t in out["containerVersion"]["trigger"]}
        pruefe("Meta-Basis-Tag haengt am Consent-Ereignis",
               bool(basis) and any(trig.get(i, {}).get("type") == "CUSTOM_EVENT"
                                   for i in basis[0]["firingTriggerId"]))
        pruefe("Meta-Basis-Tag feuert hoechstens einmal je Seite",
               bool(basis) and basis[0]["tagFiringOption"] == "ONCE_PER_LOAD")
        html = " ".join(p["value"] for t in tags if t["type"] == "html"
                        for p in t["parameter"] if p["key"] == "html")
        pruefe("Ereignis-ID fuer Deduplizierung gesetzt", "eventID" in html)

    server_req = json.loads(json.dumps(req_browser))
    server_req["server_strategy_verified"] = True
    server_req["evidence"]["server_strategy"] = "sGTM-Ziel und Server-Zustaendigkeit im Testplan verifiziert"
    server_req["event_evidence"] = {"purchase": "GTM Preview: purchase am Testpfad beobachtet"}
    server_plan = {**gueltig, "requirements": server_req,
                   "architecture": "server", "server_container_url": "https://sgtm.example.test/metrics",
                   "google_ads": {"conversion_id": "AW-987654321"},
                   "events": [{"name": "purchase", "meta_event": "Purchase",
                               "ads_label": "XyZaBcDeFgH", "value": 9, "currency": "EUR"}]}
    try:
        b = gen_mod.Builder(server_plan, server_resolver=lambda host: ["93.184.216.34"])
        out = b.build(); errs = gen_mod.validate(out)
        pruefe("architecture=server baut hermetisch erfolgreich", not errs and out is not None, errs)
        pruefe("architecture=server erzeugt keine Browser-Ads-Conversion",
               not [t for t in out["containerVersion"]["tag"] if t["type"] == "awct"])
    except Exception as e:
        pruefe("architecture=server baut hermetisch erfolgreich", False, repr(e))

    try:
        gen_mod.pruefe_server_url("https://sgtm.example.test/x", resolver=lambda host: ["100.64.0.1"])
        pruefe("sGTM Shared Address Space wird abgelehnt", False, "100.64.0.1 wurde akzeptiert")
    except gen_mod.PlanError:
        pruefe("sGTM Shared Address Space wird abgelehnt", True)

    # --server-dns-pending: nur die Namensaufloesung entfaellt, sonst nichts.
    def _kein_dns(host):
        raise OSError("nodename nor servname provided")

    try:
        gen_mod.pruefe_server_url("https://next.example.test/", resolver=_kein_dns)
        pruefe("ohne dns_pending blockiert ein nicht aufloesbarer Host", False, "wurde akzeptiert")
    except gen_mod.PlanError:
        pruefe("ohne dns_pending blockiert ein nicht aufloesbarer Host", True)

    try:
        r = gen_mod.pruefe_server_url("https://next.example.test/", resolver=_kein_dns, dns_pending=True)
        pruefe("dns_pending laesst einen noch nicht gesetzten CNAME zu", r == "https://next.example.test/")
    except gen_mod.PlanError as e:
        pruefe("dns_pending laesst einen noch nicht gesetzten CNAME zu", False, repr(e))

    try:
        gen_mod.pruefe_server_url("http://next.example.test/", resolver=_kein_dns, dns_pending=True)
        pruefe("dns_pending hebt die https-Pflicht nicht auf", False, "http wurde akzeptiert")
    except gen_mod.PlanError:
        pruefe("dns_pending hebt die https-Pflicht nicht auf", True)

    try:
        gen_mod.pruefe_server_url("https://10.0.0.5/", dns_pending=True)
        pruefe("dns_pending erlaubt keine private IP als Ziel", False, "10.0.0.5 wurde akzeptiert")
    except gen_mod.PlanError:
        pruefe("dns_pending erlaubt keine private IP als Ziel", True)

    try:
        gen_mod.pruefe_server_url("https://u:p@next.example.test/", resolver=_kein_dns, dns_pending=True)
        pruefe("dns_pending erlaubt keine Zugangsdaten in der URL", False, "akzeptiert")
    except gen_mod.PlanError:
        pruefe("dns_pending erlaubt keine Zugangsdaten in der URL", True)

    pruefe("--server-dns-pending ist als CLI-Schalter dokumentiert",
           "--server-dns-pending" in (ROOT / "skills/tracking-audit/scripts/build_web_container.py").read_text(encoding="utf-8"))

    # link_listeners: tel:/mailto:-Klicks werden zu dataLayer-Events.
    ll_plan = {"ga4": {"measurement_id": "G-ABCDEF1234"},
               "consent": {"mode": "basic"},
               "link_listeners": {"tel": "click_to_call", "mailto": "contact_email"},
               "events": [{"name": "click_to_call"}, {"name": "contact_email"}]}
    try:
        out = gen_mod.Builder(ll_plan).build()
        tags = [x for x in out["containerVersion"]["tag"] if x["name"] == "Listener - Kontaktlinks"]
        htm = ""
        if tags:
            htm = [p2["value"] for p2 in tags[0]["parameter"] if p2["key"] == "html"][0]
        pruefe("link_listeners erzeugt genau ein Listener-Tag", len(tags) == 1, len(tags))
        pruefe("link_listeners pusht beide Eventnamen",
               '"click_to_call"' in htm and '"contact_email"' in htm)
        pruefe("link_listeners delegiert auf document statt auf einzelne Links",
               "addEventListener('click'" in htm and ".closest(" in htm)
    except Exception as e:
        pruefe("link_listeners erzeugt genau ein Listener-Tag", False, repr(e))

    for fall, wert in [("kein Objekt", ["tel"]), ("unbekanntes Schema", {"sms": "x"}),
                       ("ungueltiger Eventname", {"tel": "nicht gueltig!"})]:
        try:
            gen_mod.Builder({"ga4": {"measurement_id": "G-ABCDEF1234"},
                             "consent": {"mode": "basic"},
                             "link_listeners": wert, "events": []}).build()
            pruefe("link_listeners lehnt ab: " + fall, False, "akzeptiert")
        except gen_mod.PlanError:
            pruefe("link_listeners lehnt ab: " + fall, True)

    # timer_events: Verweildauer-Schwellen als dataLayer-Events.
    te_plan = {"ga4": {"measurement_id": "G-ABCDEF1234"}, "consent": {"mode": "basic"},
               "timer_events": {"engagement_1min": 60, "engagement_3min": 180},
               "events": [{"name": "engagement_1min"}, {"name": "engagement_3min"}]}
    try:
        b = gen_mod.Builder(te_plan); out = b.build()
        tags = [x for x in out["containerVersion"]["tag"] if x["name"] == "Listener - Verweildauer"]
        htm = [p2["value"] for p2 in tags[0]["parameter"] if p2["key"] == "html"][0] if tags else ""
        pruefe("timer_events erzeugt genau ein Listener-Tag", len(tags) == 1, len(tags))
        pruefe("timer_events rechnet Sekunden in Millisekunden um",
               "60000" in htm and "180000" in htm, htm[:80])
        pruefe("timer_events warnt vor Engagement als Conversion",
               any("Engagement-Signal" in w for w in b.warnings), b.warnings)
    except Exception as e:
        pruefe("timer_events erzeugt genau ein Listener-Tag", False, repr(e))

    for fall, wert in [("kein Objekt", [60]), ("Sekunden als Text", {"e_x": "60"}),
                       ("Sekunden ausserhalb des Bereichs", {"e_x": 99999}),
                       ("ungueltiger Eventname", {"nicht gueltig!": 60})]:
        try:
            gen_mod.Builder({"ga4": {"measurement_id": "G-ABCDEF1234"},
                             "consent": {"mode": "basic"},
                             "timer_events": wert, "events": []}).build()
            pruefe("timer_events lehnt ab: " + fall, False, "akzeptiert")
        except gen_mod.PlanError:
            pruefe("timer_events lehnt ab: " + fall, True)

    # ---- validate_container.py: die drei real aufgetretenen Importfehler ----
    vc = modul("skills/tracking-audit/scripts/validate_container.py", "validate_container")

    def server(tags=None, trigger=None, client=True):
        return {"exportFormatVersion": 2, "containerVersion": {
            "container": {"usageContext": ["SERVER"]},
            "client": ([{"clientId": "1", "type": "gaaw_client", "name": "GA4"}] if client else []),
            "tag": tags or [], "trigger": trigger or [], "variable": []}}

    def ads(tagid, trig, cid="18326974194"):
        return {"tagId": tagid, "name": "Ads", "type": "sgtmadsct",
                "parameter": [{"key": "conversionId", "value": cid},
                              {"key": "conversionLabel", "value": "AbC_123-x"}],
                "firingTriggerId": [trig]}

    linker = {"tagId": "1", "name": "Linker", "type": "sgtmadscl",
              "parameter": [], "firingTriggerId": ["2147479573"]}
    f = vc.pruefe(server(tags=[linker]))
    pruefe("validate_container erkennt den WEB-Trigger im SERVER-Container",
           any("anderen Container-Typs" in x for x in f), f)

    f = vc.pruefe(server(tags=[ads("2", "5", cid="AW-18326974194")],
                         trigger=[{"triggerId": "5", "name": "CE"}]))
    pruefe("validate_container erkennt AW--Praefix im Servertag",
           any("falsche Format" in x for x in f), f)

    f = vc.pruefe(server(tags=[ads("4", "4")], trigger=[{"triggerId": "4", "name": "CE"}]))
    pruefe("validate_container erkennt kollidierende tagId/triggerId",
           any("Doppelte IDs" in x for x in f), f)

    f = vc.pruefe(server(tags=[ads("2", "5")], trigger=[{"triggerId": "5", "name": "CE"}], client=False))
    pruefe("validate_container erkennt SERVER-Container ohne Client",
           any("ohne Client" in x for x in f), f)

    f = vc.pruefe(server(tags=[ads("2", "5")], trigger=[{"triggerId": "5", "name": "CE"}]))
    pruefe("validate_container meldet einen korrekten SERVER-Container als sauber", f == [], f)

    web_ok = {"exportFormatVersion": 2, "containerVersion": {
        "container": {"usageContext": ["WEB"]},
        "tag": [{"tagId": "1", "name": "Ads", "type": "awct",
                 "parameter": [{"key": "conversionId", "value": "AW-18326974194"},
                               {"key": "conversionLabel", "value": "AbC_123"}],
                 "firingTriggerId": ["2147479573"]}],
        "trigger": [], "variable": []}}
    pruefe("validate_container meldet einen korrekten WEB-Container als sauber",
           vc.pruefe(web_ok) == [], vc.pruefe(web_ok))

    web_bad = json.loads(json.dumps(web_ok))
    web_bad["containerVersion"]["tag"][0]["parameter"][0]["value"] = "18326974194"
    pruefe("validate_container erkennt fehlendes AW- im Browser-Tag",
           any("falsche Format" in x for x in vc.pruefe(web_bad)))

    bad_ph = server(tags=[ads("2", "5", cid="18326974194")], trigger=[{"triggerId": "5", "name": "__REFERENCE_X__"}])
    pruefe("validate_container erkennt unersetzte Referenz-Platzhalter",
           any("Platzhalter" in x for x in vc.pruefe(bad_ph)))

    boese = [
        ("meta_event mit Code", {"events": [{"name": "e", "meta_event": "L'); alert(1); //"}]}),
        ("value als JS-Ausdruck", {"events": [{"name": "e", "meta_event": "Lead", "value": "1;alert(1)"}]}),
        ("value NaN", {"events": [{"name": "e", "meta_event": "Lead", "value": float("nan")}]}),
        ("ungueltige Waehrung", {"events": [{"name": "e", "meta_event": "Lead", "value": 1, "currency": "XXX"}]}),
        ("Platzhalter-ID", {"ga4": {"measurement_id": "G-XXXXXXXXXX"}}),
        ("browser + server_container_url", {"architecture": "browser",
                                            "server_container_url": "https://s.example.com/m"}),
        ("sGTM ohne https", {"architecture": "server", "server_container_url": "http://s.example.com/m"}),
        ("params mit E-Mail", {"events": [{"name": "e", "params": {"m": "user.email"}}]}),
        ("consent.mode fehlt", {"consent": {}}),
    ]
    for label, patch in boese:
        plan = json.loads(json.dumps(gueltig, default=str))
        plan.update(patch)
        ok, out, err = baue_direkt(plan)
        pruefe("abgelehnt: " + label, not ok and out is None, err)
        pruefe("  ohne Traceback: " + label, "Traceback" not in err, err)


# ---------------------------------------------------------------- E: fill_template
def test_template():
    print("\nE. GTM-Master / fill_template")
    ft = ROOT / "skills/tracking-audit/scripts/fill_template.py"
    master = {"containerVersion": {"container": {"usageContext": ["SERVER"]}, "tag": [
        {"name": "Boese", "type": "html", "parameter": [
            {"key": "html", "value": "<script>eval(atob('eA=='))</script>"}]}], "variable": [
        {"name": "C - Meta CAPI Access Token", "type": "c",
         "parameter": [{"key": "value", "value": "EAAG-GEHEIM"}]},
        {"name": "C - GA4 Measurement ID", "type": "c",
         "parameter": [{"key": "value", "value": "G-ALT9999999"}]}]}}
    with tempfile.TemporaryDirectory() as d:
        m = Path(d) / "m.json"
        m.write_text(json.dumps(master), encoding="utf-8")
        r = subprocess.run([sys.executable, str(ft), str(m), "--list"],
                           capture_output=True, text=True, timeout=60)
        pruefe("--list zeigt keinen Tokenwert", "EAAG-GEHEIM" not in r.stdout + r.stderr)
        pruefe("--list markiert Geheimnisse als redigiert", "<redigiert>" in r.stdout)
        pruefe("verdaechtiges Custom-HTML wird gemeldet",
               "eval(" in r.stderr or "atob(" in r.stderr or "WARNUNG" in r.stderr)
        v = Path(d) / "v.json"
        v.write_text(json.dumps({"C - GA4 Measurement ID": "G-NEU1234567"}), encoding="utf-8")
        r = subprocess.run([sys.executable, str(ft), str(m), str(v), "-o", d + "/out.json", "--candidate-only"],
                           capture_output=True, text=True, timeout=60)
        pruefe("Befuellen bricht bei nicht ersetztem Token ab", r.returncode != 0)
        pruefe("bei Abbruch wird nichts geschrieben", not Path(d + "/out.json").exists())


# ---------------------------------------------------------------- F: SiteOne
def test_siteone():
    print("\nF. SiteOne-Wrapper")
    so = ROOT / "skills/seogeo/scripts/siteone.py"
    with tempfile.TemporaryDirectory() as d:
        fake = Path(d) / "fake"
        fake.write_text("#!/bin/sh\nexit 3\n", encoding="utf-8")
        fake.chmod(0o755)
        r = subprocess.run([sys.executable, str(so), "http://127.0.0.1/x", "--bin", str(fake)],
                           capture_output=True, text=True, timeout=60)
        pruefe("interne Ziel-URL wird abgelehnt", r.returncode != 0 and "intern" in (r.stdout + r.stderr))
        for arg, wert in (("--workers", "99"), ("--rps", "-5"), ("--timeout", "9999")):
            r = subprocess.run([sys.executable, str(so), "https://127.0.0.1", "--bin", str(fake), arg, wert],
                               capture_output=True, text=True, timeout=60)
            pruefe("Wertebereich erzwungen: %s %s" % (arg, wert), r.returncode != 0)
        # ACHTUNG: --crawler-arg MUSS mit "=" uebergeben werden. Mit Leerzeichen bricht
        # argparse vorher ab - in 0.7.6 hat genau das drei Tests scheinbestehen lassen.
        def crawl(*extra):
            return subprocess.run([sys.executable, str(so), "https://93.184.216.34", "--bin", str(fake)]
                                  + list(extra), capture_output=True, text=True, timeout=60)

        r = crawl("--crawler-arg=--allowed-domain-for-crawling=*")
        pruefe("Wildcard im Crawl-Scope abgelehnt",
               r.returncode != 0 and "Wildcard" in (r.stdout + r.stderr), (r.stdout + r.stderr)[-120:])
        r = crawl("--crawler-arg=--allowed-domain-for-crawling=fremde-domain.test")
        pruefe("fremde Zusatzdomain -> REVIEW_REQUIRED",
               r.returncode != 0 and "REVIEW_REQUIRED" in (r.stdout + r.stderr), (r.stdout + r.stderr)[-120:])
        # Scope-Logik hermetisch direkt testen; kein echter Resolver-Aufruf.
        so_mod = modul("skills/seogeo/scripts/siteone.py", "siteone_scope")
        seen = []
        got = so_mod.pruefe_crawl_domain("shop.kunde.test", "kunde.test", [],
                                         guard_fn=lambda u: seen.append(u))
        pruefe("Subdomain passiert die Scope-Pruefung hermetisch",
               got == "shop.kunde.test" and seen == ["https://shop.kunde.test"], (got, seen))
        r = crawl("--crawler-arg=--allowed-domain-for-crawling=192.168.1.5")
        pruefe("private Adresse als Crawl-Domain abgelehnt", r.returncode != 0)
        sichtbar = so_mod.redigiere_cmd(["siteone", "--http-auth=admin:geheim123", "--url=https://kunde.test"])
        aus = " ".join(sichtbar)
        pruefe("Zugangsdaten erscheinen nicht in der Ausgabe", "geheim123" not in aus, aus)
        pruefe("Zugangsdaten werden als [REDACTED] gezeigt", "--http-auth=[REDACTED]" in aus, aus)

        # Google definiert keine harte Zeichenobergrenze fuer Title/Description.
        # Lange Snippets duerfen daher nicht als SEO-Fehler klassifiziert werden.
        synth = {"tables": {"seo": {"rows": [{
            "urlPathAndQuery": "/lang",
            "title": "T" * 80,
            "description": "D" * 180,
            "h1": "Saubere H1",
            "robotsIndex": "index",
            "indexing": "index",
            "deniedByRobotsTxt": False,
        }]}}}
        dig = so_mod.digest(synth, 20)
        pruefe("lange Title/Descriptions sind keine harten SEO-Fehler",
               dig.get("seo_auffaellig") == [], dig.get("seo_auffaellig"))
        hints = dig.get("snippet_darstellungsheuristiken") or []
        pruefe("lange Snippets werden nur als Darstellungsheuristik markiert",
               len(hints) == 1 and "kein Google-Grenzwert" in hints[0].get("einordnung", ""), hints)


def test_doctor():
    print("\nG. Doctor / Versionspruefung")
    d = modul("skills/setup/scripts/doctor.py", "doctor")
    pruefe("Mindestversionen zentral definiert",
           d.MIN_NODE == (20, 0) and d.MIN_PYTHON == (3, 10), (d.MIN_NODE, d.MIN_PYTHON))
    for text, erwartet in [("v18.20.4", False), ("v19.9.0", False), ("v20.0.0", True),
                           ("v20.11.1", True), ("v22.22.2", True), ("", False), ("kaputt", False)]:
        got = d.version_ok(d.parse_node_version(text), d.MIN_NODE)
        pruefe("Node %-12s -> %s" % (text or "(leer)", "ok" if erwartet else "zu alt"),
               got == erwartet, "erhalten %s" % got)
    for ver, erwartet in [((3, 9, 18), False), ((3, 10, 0), True), ((3, 12, 3), True), (None, False)]:
        got = d.version_ok(ver, d.MIN_PYTHON)
        pruefe("Python %-12s -> %s" % (str(ver), "ok" if erwartet else "zu alt"),
               got == erwartet, "erhalten %s" % got)
    pruefe("SiteOne-Version wird aus der Ausgabe gelesen",
           d.parse_siteone_version("SiteOne Crawler v2.5.1 (build 3)") == "2.5.1")
    pruefe("unlesbare SiteOne-Ausgabe ergibt None",
           d.parse_siteone_version("kein Versionsstring") is None)
    pruefe("Playwright-Pin gesetzt", bool(d.PLAYWRIGHT_VERSION))
    roots = d.playwright_roots({"CLAUDE_PLUGIN_ROOT": "/tmp/plugin", "MT_PLAYWRIGHT_DIR": "/tmp/pw"})
    pruefe("Doctor prueft MT_PLAYWRIGHT_DIR und CLAUDE_PLUGIN_ROOT",
           Path("/tmp/pw") in roots and Path("/tmp/plugin") in roots, roots)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "plugin"
        (root / "node_modules/playwright").mkdir(parents=True)
        (root / "node_modules/playwright/package.json").write_text("{}", encoding="utf-8")
        found = d.find_playwright_root({"CLAUDE_PLUGIN_ROOT": str(root)})
        pruefe("Doctor findet Playwright im Plugin-Root", found == root, found)


def test_dokumentation():
    print("\nH. Dokumentation gegen Code")
    import re as _re
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    d = modul("skills/setup/scripts/doctor.py", "doctor2")
    pruefe("README nennt dieselbe Node-Mindestversion wie doctor.py",
           "Node ≥ %d" % d.MIN_NODE[0] in readme, d.MIN_NODE)
    pruefe("README nennt dieselbe Python-Mindestversion",
           "Python ≥ %d.%d" % d.MIN_PYTHON in readme, d.MIN_PYTHON)
    pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    pruefe("package.json engines.node passt zu MIN_NODE",
           str(d.MIN_NODE[0]) in pkg.get("engines", {}).get("node", ""), pkg.get("engines"))
    pruefe("Playwright-Pin in package.json == doctor.py",
           pkg["dependencies"]["playwright"] == d.PLAYWRIGHT_VERSION)
    versionen = {json.loads((ROOT / f).read_text(encoding="utf-8"))["version"]
                 for f in (".claude-plugin/plugin.json", "package.json", "package-lock.json")}
    pruefe("eine einzige Versionsnummer in allen Metadaten", len(versionen) == 1, versionen)
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    fehlend = [m for m in _re.findall(r"`(docs/[^`]+)`", changelog) if not (ROOT / m).exists()]
    pruefe("CHANGELOG verweist auf keine fehlende Datei", not fehlend, fehlend)
    pruefe("keine unbelegten PageSpeed-Quoten mehr",
           "25.000" not in readme and "ohne Limit" not in readme)
    tracking_skill = (ROOT / "skills/tracking-audit/SKILL.md").read_text(encoding="utf-8")
    google_ref = (ROOT / "skills/tracking-audit/references/google.md").read_text(encoding="utf-8")
    pruefe("alte harte gcs!=G100-Regel aus Skill und Referenz entfernt",
           "gcs≠G100" not in tracking_skill and "gcs≠G100" not in google_ref
           and "G111 alles erteilt" not in google_ref)
    meta_stape = (ROOT / "skills/tracking-audit/references/meta-stape.md").read_text(encoding="utf-8")
    decisions = (ROOT / "skills/tracking-audit/references/entscheidungen.md").read_text(encoding="utf-8")
    pruefe("alte Stape-Requestformel entfernt",
           "Pageviews × (1 + Events pro Seite)" not in meta_stape and
           "Seitenaufrufe + Events" not in decisions)
    pruefe("kein veralteter fixer Meta-CAPI-Gateway-Preis",
           "$10/Pixel" not in meta_stape and "$10/Pixel" not in decisions)
    pruefe("Stape-Kapazitaet verweist auf aktuelle Quelle/Calculator",
           "× 10" in meta_stape and "Pricing Calculator" in meta_stape)
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    pruefe("eingebettetes Stape-Template ist mit Apache-2.0 attribuiert",
           "stape-io/facebook-tag" in notices and
           (ROOT / "THIRD_PARTY_LICENSES/Apache-2.0.txt").exists())
    arbeitsweise = (ROOT / "skills/setup/references/arbeitsweise.md").read_text(encoding="utf-8")
    pruefe("Completeness Gate darf alle blockierenden Rueckfragen stellen",
           "Alle vom Completeness Gate als blockierend markierten UNKNOWN-Felder" in tracking_skill and
           "blockierende UNKNOWN-Felder werden vollständig geklärt" in arbeitsweise)


def test_netzpolicy():
    print("\nI. Browser-Netzpolicy (ohne Browser, hermetisch)")
    skript = r"""
    import("%s/lib/netpolicy.mjs").then(async m => {
      const res = {};
      const oeff = async () => ["93.184.216.34"];
      for (const u of ["http://127.0.0.1/","http://localhost/","http://10.0.0.1/",
                       "http://172.16.5.5/","http://192.168.1.1/","http://169.254.169.254/",
                       "http://[::1]/","http://[fd00::1]/","http://[fe80::1]/",
                       "http://[::ffff:7f00:1]/","http://[::ffff:a00:1]/","http://[::ffff:c0a8:101]/",
                       "http://[::ffff:a9fe:a9fe]/","http://[::ffff:ac10:1]/",
                       "http://100.64.0.1/","http://198.18.0.1/","http://192.0.2.1/",
                       "http://198.51.100.1/","http://203.0.113.1/",
                       "http://[2002:7f00:1::]/","http://[2002:a00:1::]/",
                       "http://user:pw@a.example/","http://a.example:22/","file:///etc/passwd",
                       "http://metadata.google.internal/"]) {
        res[u] = (await m.pruefeZiel(u, oeff)).erlaubt;
      }
      res["OEFFENTLICH"] = (await m.pruefeZiel("https://www.google-analytics.com/g/collect", oeff)).erlaubt;
      res["CDN"] = (await m.pruefeZiel("https://cdn.example/x.js", oeff)).erlaubt;
      res["DNS_PRIVAT"] = (await m.pruefeZiel("https://x.example/", async () => ["10.1.2.3"])).erlaubt;
      res["DNS_V6_PRIVAT"] = (await m.pruefeZiel("https://y.example/", async () => ["fd00::5"])).erlaubt;
      res["172_32_OEFFENTLICH"] = (await m.pruefeZiel("http://172.32.0.1/", oeff)).erlaubt;
      console.log(JSON.stringify(res));
    });
    """ % ROOT
    r = subprocess.run(["node", "-e", skript], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        pruefe("Netzpolicy laedt", False, (r.stderr or "")[-160:])
        return
    res = json.loads(r.stdout.strip().splitlines()[-1])
    pruefe("Netzpolicy laedt und antwortet", True)
    for u, erlaubt in res.items():
        if u in ("OEFFENTLICH", "CDN", "172_32_OEFFENTLICH"):
            pruefe("durchgelassen: %s" % u, erlaubt is True, erlaubt)
        else:
            pruefe("blockiert: %s" % u[:38], erlaubt is False, erlaubt)

    quelle = (ROOT / "skills/tracking-audit/scripts/consent_test.mjs").read_text(encoding="utf-8")
    pruefe("consent_test prueft die Start-URL vor der Navigation", "await pruefeZiel(url)" in quelle)
    pruefe("consent_test haengt die Policy an den Context", "installiereNetzPolicy(ctx" in quelle)
    pruefe("Consent-Context blockiert Service Worker fuer Request-Interception", 'serviceWorkers: "block"' in quelle)
    netq = (ROOT / "lib/netpolicy.mjs").read_text(encoding="utf-8")
    pruefe("Netzpolicy routet WebSockets", "routeWebSocket" in netq and "connectToServer" in netq)
    pruefe("consent_test blockiert Collection statt Tracker-Loader",
           "shouldBlockTrackerDelivery" in quelle and "trackerAbbrechen" in quelle)
    pos_policy = quelle.index("installiereNetzPolicy(ctx")
    pos_goto = quelle.index("page.goto(url")
    pruefe("Policy wird vor der ersten Navigation gesetzt", pos_policy < pos_goto)


def test_skill_invocation():
    print("\nJ. Skill-Invocation")
    import re as _re
    MUTIEREND = {"seogeo", "tracking-audit", "launch", "kundenbericht", "setup", "start", "wissen-update"}
    for d in sorted((ROOT / "skills").iterdir()):
        if not (d / "SKILL.md").is_file():
            continue
        kopf = _re.match(r"^---\n(.*?)\n---", (d / "SKILL.md").read_text(encoding="utf-8"), _re.S)
        pruefe("Frontmatter lesbar: %s" % d.name, bool(kopf))
        if not kopf:
            continue
        felder = dict(_re.findall(r"^([a-z-]+):\s*(.*)$", kopf.group(1), _re.M))
        pruefe("  name == Verzeichnis: %s" % d.name, felder.get("name") == d.name, felder.get("name"))
        if d.name in MUTIEREND:
            pruefe("  mutierender Skill ist user-only: %s" % d.name,
                   felder.get("disable-model-invocation") == "true",
                   felder.get("disable-model-invocation", "(fehlt)"))



def test_consent_logic():
    print("\nK. Consent-Analyse (hermetisch)")
    skript = r"""
    import("%s/skills/tracking-audit/scripts/consent_logic.mjs").then(m => {
      const site = "https://kunde.test/";
      const out = {};
      out.gtmRole = m.requestRole("https://www.googletagmanager.com/gtm.js?id=GTM-X", "script", site);
      out.metaLoaderRole = m.requestRole("https://connect.facebook.net/en_US/fbevents.js", "script", site);
      out.metaPixelRole = m.requestRole("https://www.facebook.com/tr?id=1&ev=PageView", "image", site);
      out.blockLoader = m.shouldBlockTrackerDelivery("https://connect.facebook.net/en_US/fbevents.js", {resourceType:()=>"script"}, site);
      out.blockPixel = m.shouldBlockTrackerDelivery("https://www.facebook.com/tr?id=1&ev=PageView", {resourceType:()=>"image"}, site);
      out.delta = m.storageDelta({localStorage:["a"],sessionStorage:[],indexedDB:{databases:[]}},
                                 {localStorage:["a","_fbp"],sessionStorage:["_ga"],indexedDB:{databases:["analytics"]}});
      out.empty = m.emptyScenario("ablehnen");
      const bad = {scenario:"keine_interaktion",status:"unknown",abbruch:"BROWSER_FEHLER",errors:["x"],hits:[],cookies_after:[]};
      const ok = {scenario:"akzeptieren",status:"geprueft",abbruch:null,errors:[],hits:[],cookies_after:[],datalayer_consent:[]};
      const rej = {scenario:"ablehnen",status:"unknown",abbruch:"CMP_BUTTON_NICHT_GEFUNDEN",errors:["x"],hits:[],cookies_after:[]};
      out.findings = m.assess([bad,ok,rej]);
      console.log(JSON.stringify(out));
    });
    """ % ROOT
    r = subprocess.run(["node", "-e", skript], capture_output=True, text=True, timeout=60)
    pruefe("Consent-Logik laedt", r.returncode == 0, r.stderr[-160:])
    if r.returncode != 0:
        return
    x = json.loads(r.stdout.strip().splitlines()[-1])
    pruefe("GTM-Loader wird als Loader erkannt", x["gtmRole"] == "loader", x["gtmRole"])
    pruefe("Meta-Library wird nicht als Collection blockiert", x["metaLoaderRole"] == "loader" and x["blockLoader"] is False, x)
    pruefe("Meta-Pixel-Beacon wird als Collection blockiert", x["metaPixelRole"] == "collection" and x["blockPixel"] is True, x)
    pruefe("Storage-Delta erfasst neue Keys/DB", x["delta"]["localStorage_new"] == ["_fbp"] and x["delta"]["indexedDB_new"] == ["analytics"], x["delta"])
    pruefe("Consent-Szenario-Vertrag initialisiert Summary-Felder immer",
           x["empty"]["cookies_after"] == [] and x["empty"]["hits"] == []
           and x["empty"]["errors"] == [] and x["empty"]["status"] == "unknown", x["empty"])
    pruefe("Browserfehler wird nicht fachlich ausgewertet",
           any(v.startswith("NICHT GEPRUEFT (keine_interaktion)") for v in x["findings"])
           and not any("KRITISCH" in v for v in x["findings"]), x["findings"])


def test_geo_agent_readiness():
    print("\nL. GEO / Agent Readiness")
    ar = modul("skills/seogeo/scripts/agent_readiness.py", "agent_readiness")
    bad = '<html><body><main><button></button><a href="/x"></a><input id="e" type="email"></main></body></html>'
    good = '<html lang="de"><body><main><button aria-label="Menue oeffnen"></button><a href="/x">Start</a><label for="e">E-Mail</label><input id="e" type="email"><label>Telefon<input type="tel"></label><a href="/home"><img src="x.png" alt="Startseite"></a></main></body></html>'
    rb, rg = ar.audit_html(bad), ar.audit_html(good)
    pruefe("Agent-Check erkennt unbenannte Controls", len(rb["unnamed_controls"]) == 3, rb)
    pruefe("Agent-Check akzeptiert for-/Wrapper-Label und Bild-Alt", rg["unnamed_controls"] == [], rg)
    pruefe("Agent-Check behauptet keinen Rankingfaktor", "kein behaupteter Rankingfaktor" in rg["interpretation"], rg["interpretation"])
    ref = (ROOT / "skills/seogeo/references/generative-ai.md").read_text(encoding="utf-8")
    skill = (ROOT / "skills/seogeo/SKILL.md").read_text(encoding="utf-8")
    pruefe("GEO kennt Search-Console-Generative-AI-Report", "31.08.2026" in ref and "Generative-AI-Performance" in skill)
    pruefe("GEO trennt Agent Readiness von Ranking", "Agent Readiness" in skill and "Rankingfaktor" in ref)


def test_plan_completeness_gate():
    print("\nM. Tracking Completeness Gate")
    gate = modul("lib/tracking_plan.py", "tracking_plan")
    shop = json.loads((ROOT / "skills/tracking-audit/examples/plan-shop.json").read_text(encoding="utf-8"))
    pruefe("Shop-Beispiel ist vollstaendig", gate.missing_requirements(shop) == [], gate.missing_requirements(shop))
    broken = json.loads(json.dumps(shop))
    broken["requirements"]["open_questions"] = ["Checkout-Erfolgspunkt unklar"]
    miss = gate.missing_requirements(broken)
    pruefe("offene Frage blockiert Gate", any(x["field"] == "requirements.open_questions" for x in miss), miss)
    broken = json.loads(json.dumps(shop)); broken["requirements"].pop("ecommerce_contract_verified")
    miss = gate.missing_requirements(broken)
    pruefe("E-Commerce-Vertrag ist Pflicht", any(x["field"] == "requirements.ecommerce_contract_verified" for x in miss), miss)
    broken = json.loads(json.dumps(shop)); broken["requirements"].pop("enhanced_conversions_source")
    miss = gate.missing_requirements(broken)
    pruefe("Enhanced-Conversion-Quelle ist Pflicht", any(x["field"] == "requirements.enhanced_conversions_source" for x in miss), miss)
    broken = json.loads(json.dumps(shop)); broken["requirements"]["evidence"].pop("consent_strategy")
    miss = gate.missing_requirements(broken)
    pruefe("verifiziert=true ohne Evidenz blockiert", any(x["field"] == "requirements.evidence.consent_strategy" for x in miss), miss)
    broken = json.loads(json.dumps(shop)); broken["requirements"]["event_evidence"].pop("purchase")
    miss = gate.missing_requirements(broken)
    pruefe("jedes geplante Event braucht Evidenz", any(x["field"] == "requirements.event_evidence.purchase" for x in miss), miss)
    idn = json.loads(json.dumps(shop)); idn["requirements"]["primary_domain"] = "www.müller.de"
    pruefe("IDN-Produktionsdomain wird sauber validiert", gate.missing_requirements(idn) == [], gate.missing_requirements(idn))
    cross = json.loads(json.dumps(shop)); cross["requirements"]["cross_domain"] = ["shop.de", "checkout.shop.de"]; cross["requirements"]["cross_domain_implementation"] = "verified_master"
    pruefe("Cross-Domain kann als verifizierter Master geplant werden", gate.missing_requirements(cross) == [], gate.missing_requirements(cross))
    try:
        gate.assert_direct_build_supported(cross)
        pruefe("Direktgenerator blockiert Cross-Domain statt es zu ignorieren", False, "durchgelassen")
    except ValueError:
        pruefe("Direktgenerator blockiert Cross-Domain statt es zu ignorieren", True)
    gen = ROOT / "skills/tracking-audit/scripts/build_web_container.py"
    with tempfile.TemporaryDirectory() as d:
        pp = Path(d) / "p.json"; pp.write_text(json.dumps(broken), encoding="utf-8")
        r = subprocess.run([sys.executable, str(gen), str(pp), "--allow-placeholder", "-o", str(Path(d)/"x.json")], capture_output=True, text=True, timeout=30)
        pruefe("Builder selbst erzwingt Completeness Gate", r.returncode != 0 and "TRACKING-PLAN UNVOLLSTAENDIG" in r.stdout + r.stderr, r.stdout + r.stderr)


def test_gtm_golden_master():
    print("\nN. GTM Golden Master / Roundtrip")
    verify_mod = modul("skills/tracking-audit/scripts/gtm_master_verify.py", "gtm_verify_tests")
    ft = ROOT / "skills/tracking-audit/scripts/fill_template.py"
    candidate = {"exportFormatVersion": 2, "containerVersion": {"container": {"usageContext": ["WEB"]},
                 "trigger": [{"triggerId":"1","name":"CE - lead","type":"CUSTOM_EVENT"}],
                 "tag": [{"tagId":"2","name":"GA4 - lead","type":"gaawe","parameter":[],"firingTriggerId":["1"]}],
                 "variable": []}}
    roundtrip = json.loads(json.dumps(candidate)); roundtrip["containerVersion"]["trigger"][0]["triggerId"]="901"; roundtrip["containerVersion"]["tag"][0]["tagId"]="902"; roundtrip["containerVersion"]["tag"][0]["firingTriggerId"]=["901"]
    with tempfile.TemporaryDirectory() as d:
        c=Path(d)/"c.json"; r=Path(d)/"r.json"; m=Path(d)/"m.verified.json"
        c.write_text(json.dumps(candidate),encoding="utf-8"); r.write_text(json.dumps(roundtrip),encoding="utf-8")
        problems, typ, snap = verify_mod.verify(str(c), str(r), "web")
        pruefe("GTM Roundtrip toleriert nur dynamische IDs", problems == [] and typ == "web", problems)
        bad=json.loads(json.dumps(roundtrip)); bad["containerVersion"]["tag"][0]["name"]="CHANGED"; r.write_text(json.dumps(bad),encoding="utf-8")
        problems, _, _ = verify_mod.verify(str(c), str(r), "web")
        pruefe("GTM Roundtrip lehnt semantische Aenderung ab", bool(problems), problems)

        # Fill-Template CLI bleibt hier absichtlich als echter Smoke-Test erhalten.
        server={"exportFormatVersion":2,"containerVersion":{"container":{"usageContext":["SERVER"]},"tag":[],"trigger":[],"variable":[],"client":[]}}
        sm=Path(d)/"server.json"; vals=Path(d)/"vals.json"; out=Path(d)/"server-out.json"; sm.write_text(json.dumps(server)); vals.write_text("{}")
        p=subprocess.run([sys.executable,str(ft),str(sm),str(vals),"-o",str(out),"--erwarteter-typ","server"],capture_output=True,text=True,timeout=30)
        pruefe("Server-Master ohne Verified-Manifest wird blockiert", p.returncode != 0 and "Verified-Manifest" in p.stdout+p.stderr, p.stdout+p.stderr)
        p=subprocess.run([sys.executable,str(ft),str(sm),str(vals),"-o",str(out),"--erwarteter-typ","server","--candidate-only"],capture_output=True,text=True,timeout=30)
        pruefe("erster Server-Candidate ist bewusst bootstrapbar", p.returncode == 0 and out.exists(), p.stdout+p.stderr)

        # Community-/Custom-Template-IDs duerfen beim echten GTM-Roundtrip wechseln,
        # ohne dass das semantisch als anderes Template gilt.
        cc={"exportFormatVersion":2,"containerVersion":{"container":{"usageContext":["SERVER"]},
            "customTemplate":[{"templateId":"10","name":"Meta CAPI","templateData":"abc"}],
            "tag":[{"tagId":"20","name":"Meta - Purchase","type":"cvt_123_10","parameter":[]}],
            "trigger":[],"variable":[],"client":[]}}
        rr=json.loads(json.dumps(cc)); rr["containerVersion"]["customTemplate"][0]["templateId"]="999"; rr["containerVersion"]["tag"][0]["tagId"]="888"; rr["containerVersion"]["tag"][0]["type"]="cvt_777_999"
        c2=Path(d)/"cc.json"; r2=Path(d)/"rr.json"; m2=Path(d)/"server.verified.json"
        c2.write_text(json.dumps(cc),encoding="utf-8"); r2.write_text(json.dumps(rr),encoding="utf-8")
        problems, _, _ = verify_mod.verify(str(c2), str(r2), "server")
        pruefe("Roundtrip toleriert dynamische Community-Template-IDs", problems == [], problems)
        if os.name != "nt":
            victim=Path(d)/"victim.txt"; victim.write_text("SAFE",encoding="utf-8")
            symlink=Path(d)/"manifest-link.json"; os.symlink(victim, symlink)
            try:
                verify_mod.write_manifest_exclusive(symlink, {"status":"test"})
                blocked = False
            except FileExistsError:
                blocked = True
            pruefe("Verified-Manifest folgt keinem vorbereiteten Symlink", blocked and victim.read_text(encoding="utf-8") == "SAFE", symlink)
    reg=json.loads((ROOT / "skills/tracking-audit/masters/registry.json").read_text(encoding="utf-8"))
    pruefe("keine erfundenen verified Masters ausgeliefert", reg.get("verified_masters") == [], reg)



def test_reference_assets():
    print("\nO. Sanitized Production Reference / Core / Patterns")
    masters = ROOT / "skills/tracking-audit/masters"
    guard_mod = modul("skills/tracking-audit/scripts/reference_guard.py", "reference_guard_tests")
    guard_problems = []
    for gp in sorted(masters.rglob("*.json")):
        for problem in guard_mod.check_file(gp):
            guard_problems.append("%s: %s" % (gp.relative_to(masters), problem))
    required_assets = [
        masters / "REFERENCE-POLICY.md",
        masters / "production-reference/web-reference.sanitized.json",
        masters / "production-reference/server-reference.sanitized.json",
        masters / "core/web-core.candidate.json",
        masters / "core/server-core.candidate.json",
        masters / "patterns/event-patterns.json",
    ]
    guard_problems += ["required asset missing: %s" % x for x in required_assets if not x.exists()]
    pruefe("Reference Guard ist gruen", guard_problems == [], guard_problems)

    registry = json.loads((masters / "registry.json").read_text(encoding="utf-8"))
    pruefe("keine Referenz ist faelschlich VERIFIED", registry.get("verified_masters") == [], registry)
    pruefe("Web+Server Core als Candidates registriert",
           {x.get("container_type") for x in registry.get("candidate_masters", [])} == {"web", "server"}, registry)

    web = json.loads((masters / "production-reference/web-reference.sanitized.json").read_text(encoding="utf-8"))
    server = json.loads((masters / "production-reference/server-reference.sanitized.json").read_text(encoding="utf-8"))
    raw = json.dumps([web, server], ensure_ascii=False)
    pruefe("Referenzen tragen expliziten Sanitized-Marker",
           web.get("_meixnerReference", {}).get("sanitized") is True and
           server.get("_meixnerReference", {}).get("sanitized") is True)

    svars = {v.get("name"): next((p.get("value") for p in v.get("parameter", []) if p.get("key") == "value"), None)
             for v in server["containerVersion"].get("variable", []) if v.get("type") == "c"}
    pruefe("Meta Token ist nur lesbarer Platzhalter", svars.get("Const - Meta Access Token") == "__META_CAPI_ACCESS_TOKEN__", svars)
    pruefe("Meta Pixel ist nur lesbarer Platzhalter", svars.get("Const - Meta Pixel ID") == "__META_PIXEL_ID__", svars)

    wcore = json.loads((masters / "core/web-core.candidate.json").read_text(encoding="utf-8"))
    score = json.loads((masters / "core/server-core.candidate.json").read_text(encoding="utf-8"))
    pruefe("Web-Core enthaelt nur Infrastruktur-Tags",
           {t.get("type") for t in wcore["containerVersion"].get("tag", [])} == {"gclidw", "googtag"},
           [t.get("type") for t in wcore["containerVersion"].get("tag", [])])
    pruefe("Server-Core enthaelt GA4 Client + Conversion Linker",
           any(c.get("type") == "gaaw_client" for c in score["containerVersion"].get("client", [])) and
           {t.get("type") for t in score["containerVersion"].get("tag", [])} == {"sgtmadscl"},
           score.get("containerVersion", {}).keys())
    pruefe("Core-Candidates bleiben explizit unverifiziert",
           wcore.get("_meixnerMaster", {}).get("verified") is False and score.get("_meixnerMaster", {}).get("verified") is False,
           [wcore.get("_meixnerMaster"), score.get("_meixnerMaster")])

    patterns = json.loads((masters / "patterns/event-patterns.json").read_text(encoding="utf-8"))
    pruefe("Pattern Library trennt Purchase/Lead/Engagement",
           all(k in patterns.get("patterns", {}) for k in ("purchase", "lead_or_booking", "scroll_50")), patterns.keys())
    pruefe("Scroll wird nicht standardmaessig Ads/Meta Conversion",
           "Google Ads conversion" in patterns["patterns"]["scroll_50"].get("do_not_default", []) and
           "Meta conversion/CAPI" in patterns["patterns"]["scroll_50"].get("do_not_default", []),
           patterns["patterns"]["scroll_50"])
    pruefe("Production Reference Policy verbietet Consent-/Kundenwert-Erbe",
           "Consent nie erben" in (masters / "REFERENCE-POLICY.md").read_text(encoding="utf-8") and
           "Keine Kundenwerte erben" in (masters / "REFERENCE-POLICY.md").read_text(encoding="utf-8"))

    # Sanitizer: controlled fixture with a real-looking token/domain must not survive.
    sanitizer_mod = modul("skills/tracking-audit/scripts/sanitize_gtm_reference.py", "sanitize_reference_tests")
    fixture = {
      "exportFormatVersion":2, "exportTime":"x",
      "containerVersion": {
        "accountId":"1234567890", "containerId":"987654321",
        "container":{"accountId":"1234567890","containerId":"987654321","name":"customer-example.test || Server",
                     "publicId":"GTM-ABCDEF1","usageContext":["SERVER"],"taggingServerUrls":["https://metrics.customer-example.test"]},
        "tag":[], "trigger":[],
        "variable":[{"name":"Const - Meta Access Token","type":"c","parameter":[{"key":"value","value":"EAA" + "Z"*100}]}]
      }}
    sanitized_obj, sanitized_type = sanitizer_mod.sanitize(fixture)
    sanitized = json.dumps(sanitized_obj, ensure_ascii=False)
    pruefe("Sanitizer entfernt kontrollierten Token+Kundendomain",
           sanitized_type == "server" and "customer-example" not in sanitized and
           ("EAA"+"Z"*100) not in sanitized and "GTM-ABCDEF1" not in sanitized,
           sanitized[:180])

    # Candidate core must not silently be treated as verified master.
    ft = ROOT / "skills/tracking-audit/scripts/fill_template.py"
    with tempfile.TemporaryDirectory() as d:
        vals=Path(d)/"vals.json"; vals.write_text(json.dumps({"Const - Google Mess ID":"G-ABC1234567", "Const - sGTM URL":"https://metrics.example.com"}), encoding="utf-8")
        rr=subprocess.run([sys.executable,str(ft),str(masters/"core/web-core.candidate.json"),str(vals),"-o",str(Path(d)/"x.json")],capture_output=True,text=True,timeout=30)
        pruefe("Core-Candidate braucht Verified-Manifest oder bewussten Bootstrap", rr.returncode != 0 and "candidate_reference_only" in rr.stdout+rr.stderr, rr.stdout+rr.stderr)

PHASE1_CASES = (test_launch, test_urlguard, test_bericht, test_builder, test_template)
PHASE2_CASES = (
    test_siteone, test_doctor, test_dokumentation,
    test_netzpolicy, test_skill_invocation, test_consent_logic,
    test_geo_agent_readiness, test_plan_completeness_gate, test_gtm_golden_master,
    test_reference_assets,
)


def _run_cases(cases):
    for fn in cases:
        try:
            fn()
        except Exception as e:
            pruefe("%s ABGEBROCHEN" % fn.__name__, False, "%s: %s" % (type(e).__name__, e))
    passed = sum(1 for _, ok, _ in ERGEBNISSE if ok)
    failed = len(ERGEBNISSE) - passed
    print("\n%d Tests, %d bestanden, %d fehlgeschlagen" % (len(ERGEBNISSE), passed, failed))
    if os.environ.get("MT_DEBUG_THREADS") == "1":
        print("THREADS:", [(t.name, t.daemon, t.is_alive()) for t in threading.enumerate()], flush=True)
    result_file = os.environ.get("MT_RESULT_FILE")
    if result_file:
        Path(result_file).write_text(json.dumps({"tests": len(ERGEBNISSE), "passed": passed, "failed": failed}), encoding="utf-8")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    ALL_CASES = PHASE1_CASES + PHASE2_CASES
    CASES = {fn.__name__: fn for fn in ALL_CASES}
    args = sys.argv[1:]
    mode = args[0] if args else "--orchestrate"
    print("meixner-toolkit Regressionstests")
    print("Plugin-Wurzel: %s\n" % ROOT)

    if mode == "--case":
        if len(args) != 2 or args[1] not in CASES:
            print("Unbekannter Testfall. Erlaubt: %s" % ", ".join(sorted(CASES)), file=sys.stderr)
            sys.exit(2)
        sys.exit(_run_cases((CASES[args[1]],)))

    # Rueckwaertskompatibel fuer gezielte lokale Laeufe.
    if mode == "--phase1":
        sys.exit(_run_cases(PHASE1_CASES))
    if mode == "--phase2":
        sys.exit(_run_cases(PHASE2_CASES))

    if mode == "--orchestrate":
        # Jeder Testblock A-O laeuft in einem frischen Interpreter. So koennen weder
        # Monkeypatches/importierte Module noch viele interne CLI-Subprozesse Zustand
        # oder offene Handles in den naechsten Block tragen. Der Parent sammelt nur
        # kleine JSON-Ergebnisdateien; stdout/stderr der Kinder bleiben direkt sichtbar.
        total = passed = failed = 0
        env_base = os.environ.copy()
        env_base["PYTHONDONTWRITEBYTECODE"] = "1"
        env_base["CLAUDE_PLUGIN_ROOT"] = str(ROOT)
        with tempfile.TemporaryDirectory(prefix="mt-regression-") as d:
            for i, fn in enumerate(ALL_CASES, 1):
                result = Path(d) / ("%02d-%s.json" % (i, fn.__name__))
                env = env_base.copy(); env["MT_RESULT_FILE"] = str(result)
                rc = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--case", fn.__name__], env=env).returncode
                if result.exists():
                    data = json.loads(result.read_text(encoding="utf-8"))
                    total += int(data.get("tests", 0)); passed += int(data.get("passed", 0)); failed += int(data.get("failed", 0))
                else:
                    failed += 1
                if rc != 0:
                    print("\nABBRUCH: Testblock %s fehlgeschlagen." % fn.__name__, file=sys.stderr)
                    sys.exit(rc or 1)
        print("\nFull regression: %d/%d bestanden, %d fehlgeschlagen." % (passed, total, failed))
        if total != 248:
            print("ABBRUCH: Erwartet wurden 248 Regressionstests, erhalten: %d." % total, file=sys.stderr)
            sys.exit(3)
        sys.exit(0 if failed == 0 and passed == total else 1)

    print("Aufruf: python3 tests/run_tests.py [--case NAME|--phase1|--phase2]", file=sys.stderr)
    sys.exit(2)
