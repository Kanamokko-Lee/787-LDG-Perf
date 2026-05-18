import requests
import json
from datetime import datetime, timezone

STATIONS = [
    "RJCC","RJAA","RJTT","RJGG","RJOO",
    "RJBB","RJFF","ROAH","RKSS","RCSS",
    "RCTP","ZBAA","ZSPD","ZSSS","ZYTL",
    "VHHH","ZGGG","VVNB","VVTS","VTBS",
    "WMKK","WSSS","WIII","PHNL"
]

IATA = {
    "RJCC":"CTS","RJAA":"NRT","RJTT":"HND","RJGG":"NGO","RJOO":"ITM",
    "RJBB":"KIX","RJFF":"FUK","ROAH":"OKA","RKSS":"GMP","RCSS":"TSA",
    "RCTP":"TPE","ZBAA":"PEK","ZSPD":"PVG","ZSSS":"SHA","ZYTL":"DLC",
    "VHHH":"HKG","ZGGG":"CAN","VVNB":"HAN","VVTS":"SGN","VTBS":"BKK",
    "WMKK":"KUL","WSSS":"SIN","WIII":"CGK","PHNL":"HNL"
}

def main():
    ids = ",".join(STATIONS)
    url = f"https://aviationweather.gov/api/data/taf?ids={ids}&format=json&metar=false"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()

    result = {}
    for item in data:
        raw = (item.get("rawTAF") or item.get("raw_text") or "").strip()
        if not raw:
            continue
        icao = item.get("stationId") or item.get("station_id") or ""
        iata = IATA.get(icao, icao)
        result[iata] = {
            "icao": icao,
            "issued": item.get("issueTime") or item.get("issue_time") or "",
            "raw": raw
        }
        print(f"Got {iata}: {raw[:50]}")

    output = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tafs": result
    }
    with open("taf.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"Saved {len(result)} TAFs")

if __name__ == "__main__":
    main()
