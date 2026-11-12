#!/usr/bin/env python3
"""Voeg skill 88298 toe aan alle badgenummers in badges.csv (kolom A, vanaf rij 2).

Gebruik:
    export QUINYX_API_KEY="jouw-api-key"
    python3 add_skills.py
"""

import csv
import os
import urllib.request
from xml.sax.saxutils import escape

BESTAND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "badges.csv")
ENDPOINT = "https://api.quinyx.com/soap/FlexForce"
API_KEY = os.environ["QUINYX_API_KEY"]
SKILL_ID = 88298

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
            <skillExpires xsi:type="xsd:int">0</skillExpires>
            <skillExpiringDate xsi:type="xsd:dateTime">2024-01-01T00:00:00Z</skillExpiringDate>
          </item>
        </jobSkills>
      </item>
    </skills>
    </tns:wsdlUpdateEmployeeSkills>
  </soap:Body>
</soap:Envelope>
"""


def stuur(badge):
    body = TEMPLATE.format(api_key=escape(API_KEY), badge=escape(badge), skill_id=SKILL_ID).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": '""'},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def main():
    with open(BESTAND, newline="", encoding="utf-8-sig") as f:
        scheiding = ";" if ";" in f.readline() else ","
        f.seek(0)
        rijen = list(csv.reader(f, delimiter=scheiding))

    badges = []
    for rij in rijen:
        if not rij or not rij[0].strip():
            continue  # lege regels overslaan
        waarde = rij[0].strip()
        if waarde.lower() == "badge no.":
            continue  # de kopregel overslaan
        badges.append(waarde)
    print(f"{len(badges)} badgenummers gevonden.")

    for i, badge in enumerate(badges, 1):
        try:
            antwoord = stuur(badge)
            status = "FOUT (SOAP fault)" if "Fault" in antwoord else "OK"
        except Exception as e:
            status = f"FOUT ({e})"
        print(f"[{i}/{len(badges)}] {badge}: {status}")


if __name__ == "__main__":
    main()
