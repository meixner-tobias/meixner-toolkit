# Server-Container: belegte Werte und Fallstricke

Stand 02.10.2026. Alle Werte stammen aus echten Exporten im Plugin
(`masters/production-reference/server-reference.sanitized.json`,
`masters/core/server-core.candidate.json`) oder aus Fehlermeldungen des
GTM-Imports – nicht aus Analogie zum Web-Container.

## Der Kernfehler: Web-Konventionen uebertragen

Web- und Server-Container sehen im JSON fast gleich aus. Sie sind es nicht.
Drei Stellen unterscheiden sich, und alle drei faellt man beim Abschreiben
aus einem Web-Container hinein.

| | WEB | SERVER |
|---|---|---|
| Eingebauter Trigger | `2147479573` „Initialization – All Pages" | `2147479574` „All Events" |
| Ads-Conversion-Tag | Typ `awct`, `conversionId` = `AW-123456789` | Typ `sgtmadsct`, `conversionId` = `123456789` |
| Client | keiner | mindestens einer, sonst nimmt niemand Requests an |

**Falscher Trigger** → GTM meldet beim Import *„Tag references an unknown trigger"*.

**Falsches ID-Format** → GTM meldet *„File format is invalid"* und
*„The value must be a positive integer or 0"*. Das `AW-`-Praefix gehoert in
gtag- und Browser-Tags, nie in den Servertag.

## ID-Vergabe: ein gemeinsamer Zaehlraum

`tagId`, `triggerId` und `variableId` kommen in echten Exporten aus **einem**
Zaehler. Vergibt man Tags und Trigger getrennt ab 1 bzw. 4, kollidieren sie.
Das ist syntaktisch unauffaellig und faellt ohne Pruefung nicht auf.

Richtig: durchzaehlen ueber alle drei Arten hinweg.

## Verifizierte Tag-Typen

| Typ | Zweck | Belegt in |
|---|---|---|
| `gaaw_client` | GA4-Client, nimmt Requests an | core-candidate |
| `sgtmadscl` | Server Conversion Linker | core-candidate + production-reference |
| `sgtmadsct` | Google-Ads-Conversion serverseitig | production-reference (6x) |

Parameter von `sgtmadsct`: `conversionId`, `conversionLabel`, `conversionValue`,
`currencyCode`, `enableConversionLinker`, `enableNewCustomerReporting`,
`enableProductReporting`, `rdp`.

**Nicht belegt und deshalb nicht generierbar:** der GA4-Tag, der die Requests vom
Client an GA4 weiterreicht. In GTM von Hand anlegen über *Tag → Google Analytics:
GA4*, Auslöser „Alle Events". Keinen Typschluessel dafuer erfinden.

`cvt_*`-Typen aus der production-reference sind Community-Templates. Ihre IDs
gelten nur im Ursprungscontainer und duerfen nie uebernommen werden.

## Pflichtschritt vor jedem Import

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/validate_container.py" <datei>.json
```

Prueft Trigger-Referenzen gegen den richtigen Container-Typ, Variablen-Referenzen,
ID-Eindeutigkeit, das Format von `conversionId`/`conversionLabel`, unersetzte
Referenz-Platzhalter und ob ein SERVER-Container einen Client hat.
