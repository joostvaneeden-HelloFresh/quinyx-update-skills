#!/usr/bin/env python3
"""Voeg een skill toe aan chauffeurs in Quinyx via de FlexForce SOAP API (bulk).

Leest badgenummers uit een CSV-bestand in de projectmap en stuurt per badgenummer
een wsdlUpdateEmployeeSkills-aanroep. Alleen badgeNo verandert per aanroep.

Vereist: environment variable QUINYX_API_KEY.

Voorbeelden:
    python3 add_skills.py --dry-run                 # toon het eerste request, verstuur niets
    python3 add_skills.py                           # verstuur voor alle badgenummers
    python3 add_skills.py --csv badges.csv --kolom badgeNo --yes
"""

import argparse
import csv
import os
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from xml.sax.saxutils import escape

PROJECTMAP = os.path.dirname(os.path.abspath(__file__))

ENDPOINT = "https://api.quinyx.com/soap/FlexForce"
SKILL_ID = 88298
SKILL_EXPIRES = 0
SKILL_EXPIRING_DATE = "2024-01-01T00:00:00Z"

SOAP_FAULT = "{http://schemas.xmlsoap.org/soap/envelope/}Fault"

TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:tns="https://api.quinyx.com/soap/FlexForce">
  <soap:Body>
    <tns:wsdlUpdateEmployeeSkills>
    <apiKey xsi:type="xsd:string">{api_key}</apiKey>
    <skills xsi:type="SOAP-ENC:Array" SOAP-ENC:arrayType="tns:UpdateEmployeeSkill[1]">
      <item xsi:type="tns:UpdateEmployeeSkill">
        <persId xsi:type="xsd:int">0</persId>
        <badgeNo xsi:type="xsd:string">{badge}</badgeNo>
        <addSkills xsi:type="xsd:int">1</addSkills>
        <jobSkills xsi:type="SOAP-ENC:Array" SOAP-ENC:arrayType="tns:JobSkill[1]">
          <item xsi:type="tns:JobSkill">
            <skillId xsi:type="xsd:int">{skill_id}</skillId>
            <skillExpires xsi:type="xsd:int">{skill_expires}</skillExpires>
            <skillExpiringDate xsi:type="xsd:dateTime">{skill_expiring_date}</skillExpiringDate>
          </item>
        </jobSkills>
      </item>
    </skills>
    </tns:wsdlUpdateEmployeeSkills>
  </soap:Body>
</soap:Envelope>
"""


def bouw_envelop(api_key, badge):
    """Vul de SOAP-template in. Waarden worden ge-escaped zodat ze geldige XML blijven."""
    return TEMPLATE.format(
        api_key=escape(api_key),
        badge=escape(badge),
        skill_id=SKILL_ID,
        skill_expires=SKILL_EXPIRES,
        skill_expiring_date=SKILL_EXPIRING_DATE,
    ).encode("utf-8")


def lees_badgenummers(pad, kolom):
    """Lees unieke badgenummers uit de CSV. Kolomnaam is hoofdletterongevoelig."""
    if not os.path.isfile(pad):
        raise SystemExit(f"CSV-bestand niet gevonden: {pad}")

    with open(pad, newline="", encoding="utf-8-sig") as f:
        monster = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(monster, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel  # standaard komma
        rijen = list(csv.reader(f, dialect))

    if not rijen:
        raise SystemExit(f"CSV-bestand is leeg: {pad}")

    koppen = [k.strip() for k in rijen[0]]
    gezocht = kolom.strip().lower()
    idx = next((i for i, k in enumerate(koppen) if k.lower() == gezocht), None)
    if idx is None:
        raise SystemExit(
            f"Kolom '{kolom}' niet gevonden in {pad}. Gevonden koppen: {koppen}. "
            f"Gebruik --kolom om de juiste kolom op te geven."
        )

    badges, gezien = [], set()
    for rij in rijen[1:]:
        if idx >= len(rij):
            continue
        badge = rij[idx].strip()
        if not badge or badge in gezien:
            continue
        gezien.add(badge)
        badges.append(badge)
    return badges


def soap_fout(raw):
    """Geef een foutmelding terug als het antwoord een SOAP Fault is of geen XML, anders None."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return f"onverwacht antwoord: {raw[:200]!r}"
    fault = root.find(f".//{SOAP_FAULT}")
    if fault is None:
        return None
    tekst = (fault.findtext("faultstring") or "onbekende SOAP fault").strip()
    return f"SOAP fault: {tekst}"


def verstuur(endpoint, api_key, badge, timeout):
    """Stuur één request. Geeft (True, '') of (False, foutmelding) terug."""
    req = urllib.request.Request(
        endpoint,
        data=bouw_envelop(api_key, badge),
        method="POST",
        headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": '""'},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        raw = e.read()
        return False, soap_fout(raw) or f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, f"verbindingsfout: {e.reason}"

    fout = soap_fout(raw)
    return (fout is None), (fout or "")


def main():
    p = argparse.ArgumentParser(description="Voeg skill %d toe aan badgenummers uit een CSV." % SKILL_ID)
    p.add_argument("--csv", default=os.path.join(PROJECTMAP, "badges.csv"),
                   help="CSV met badgenummers (standaard: badges.csv in de projectmap)")
    p.add_argument("--kolom", default="badgeNo", help="kolomnaam met badgenummers (standaard: badgeNo)")
    p.add_argument("--endpoint", default=ENDPOINT, help="SOAP-endpoint")
    p.add_argument("--pauze", type=float, default=0.2, help="seconden tussen aanroepen (standaard: 0.2)")
    p.add_argument("--timeout", type=float, default=30, help="timeout per aanroep in seconden")
    p.add_argument("--dry-run", action="store_true", help="toon het eerste request, verstuur niets")
    p.add_argument("--yes", action="store_true", help="sla de bevestigingsvraag over")
    args = p.parse_args()

    badges = lees_badgenummers(args.csv, args.kolom)
    print(f"{len(badges)} unieke badgenummers gevonden in {args.csv}")
    if not badges:
        raise SystemExit("Niets te doen.")

    if args.dry_run:
        print("\nDry run, eerste request (er is niets verstuurd):\n")
        print(bouw_envelop("QUINYX_API_KEY", badges[0]).decode("utf-8"))
        return

    api_key = os.environ.get("QUINYX_API_KEY")
    if not api_key:
        raise SystemExit("Zet eerst de environment variable QUINYX_API_KEY.")

    if not args.yes:
        antwoord = input(f"Skill {SKILL_ID} toevoegen aan {len(badges)} badgenummers? (ja/nee): ")
        if antwoord.strip().lower() not in ("ja", "j", "y", "yes"):
            raise SystemExit("Afgebroken.")

    resultaten = []
    try:
        for i, badge in enumerate(badges, 1):
            ok, melding = verstuur(args.endpoint, api_key, badge, args.timeout)
            resultaten.append((badge, "OK" if ok else "FOUT", melding))
            print(f"[{i}/{len(badges)}] {badge}: {'OK' if ok else 'FOUT - ' + melding}")
            time.sleep(args.pauze)
    except KeyboardInterrupt:
        print("\nOnderbroken door gebruiker.")
    finally:
        # Schrijf altijd het resultaat weg, ook bij een onderbreking.
        uitvoer = os.path.join(PROJECTMAP, f"resultaat_{datetime.now():%Y%m%d_%H%M%S}.csv")
        with open(uitvoer, "w", newline="", encoding="utf-8") as f:
            schrijver = csv.writer(f)
            schrijver.writerow(["badgeNo", "status", "melding"])
            schrijver.writerows(resultaten)

        aantal_ok = sum(1 for r in resultaten if r[1] == "OK")
        print(f"\nKlaar: {aantal_ok} OK, {len(resultaten) - aantal_ok} FOUT, "
              f"{len(badges) - len(resultaten)} niet verwerkt.")
        print(f"Resultaat weggeschreven naar {uitvoer}")


if __name__ == "__main__":
    main()
