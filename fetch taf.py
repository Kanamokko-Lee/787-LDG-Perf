import requests
import json
from datetime import datetime, timezone

# 対象空港のICAOコード
STATIONS = [
    "RJCC","RJAA","RJTT","RJGG","RJOO",
    "RJBB","RJFF","ROAH","RKSS","RCSS",
    "RCTP","ZBAA","ZSPD","ZSSS","ZYTL",
    "VHHH","ZGGG","VVNB","VVTS","VTBS",
    "WMKK","WSSS","WIII","PHNL"
]

# ICAOコード → IATA変換（表示用）
IATA = {
    "RJCC":"CTS","RJAA":"NRT","RJTT":"HND","RJGG":"NGO","RJOO":"ITM",
    "RJBB":"KIX","RJFF":"FUK","ROAH":"OKA","RKSS":"GMP","RCSS":"TSA",
    "RCTP":"TPE","ZBAA":"PEK","ZSPD":"PVG","ZSSS":"SHA","ZYTL":"DLC",
    "VHHH":"HKG","ZGGG":"CAN","VVNB":"HAN","VVTS":"SGN","VTBS":"BKK",
    "WMKK":"KUL","WSSS":"SIN","WIII":"CGK","PHNL":"HNL"
}

def fetch_taf(stations):
    ids = ",".join(stations)
    url = f"https://aviationweather.gov/api/data/taf?ids={ids}&format=json&metar=false"
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Error fetching TAF: {e}")
        return []

def main():
    print(f"Fetching TAF at {datetime.now(timezone.utc).isoformat()}")
    data = fetch_taf(STATIONS)
    
    result = {}
    for item in data:
        raw = item.get("rawTAF") or item.get("raw_text") or item.get("tafText") or ""
        raw = raw.strip()
        if not raw:
            continue
        icao = item.get("stationId") or item.get("station_id") or ""
        iata = IATA.get(icao, icao)
        issued = item.get("issueTime") or item.get("issue_time") or ""
        result[iata] = {
            "icao": icao,
            "issued": issued,
            "raw": raw
        }
        print(f"  Got TAF for {iata} ({icao}): {raw[:60]}...")
    
    output = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tafs": result
    }
    
    with open("taf.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"Saved {len(result)} TAFs to taf.json")

if __name__ == "__main__":
    main()
