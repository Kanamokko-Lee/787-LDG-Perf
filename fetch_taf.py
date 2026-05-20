import requests
import json
from datetime import datetime, timezone, timedelta

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

APTS = {
    "CTS":(42.77,141.69),"NRT":(35.76,140.38),"HND":(35.54,139.78),
    "NGO":(34.86,136.81),"ITM":(34.78,135.44),"KIX":(34.43,135.23),
    "FUK":(33.58,130.45),"OKA":(26.20,127.64),"GMP":(37.55,126.79),
    "TSA":(25.07,121.55),"TPE":(25.07,121.23),"PEK":(40.07,116.59),
    "PVG":(31.14,121.80),"SHA":(31.19,121.33),"DLC":(38.97,121.54),
    "HKG":(22.30,113.91),"CAN":(23.39,113.29),"HAN":(21.22,105.80),
    "SGN":(10.81,106.65),"BKK":(13.69,100.75),"KUL":(2.74,101.70),
    "SIN":(1.36,103.99),"CGK":(-6.12,106.65),"HNL":(21.31,-157.92)
}

def fetch_taf_data():
    ids = ",".join(STATIONS)
    url = f"https://aviationweather.gov/api/data/taf?ids={ids}&format=json&metar=false"
    headers = {"User-Agent": "787-LDG-Perf/1.0 github.com/Kanamokko-Lee/787-LDG-Perf"}
    r = requests.get(url, timeout=30, headers=headers)
    r.raise_for_status()
    return r.json()

def fetch_temperatures():
    """open-meteoから全空港の気温予報を取得"""
    iatas = list(APTS.keys())
    lats = ",".join(str(APTS[k][0]) for k in iatas)
    lons = ",".join(str(APTS[k][1]) for k in iatas)
    url = (f"https://api.open-meteo.com/v1/forecast"
           f"?latitude={lats}&longitude={lons}"
           f"&current=temperature_2m,pressure_msl"
           f"&hourly=temperature_2m&forecast_days=2&timezone=UTC")
    headers = {"User-Agent": "787-LDG-Perf/1.0 github.com/Kanamokko-Lee/787-LDG-Perf"}
    r = requests.get(url, timeout=30, headers=headers)
    r.raise_for_status()
    data = r.json()
    arr = data if isinstance(data, list) else [data]

    now_utc = datetime.now(timezone.utc)
    now_str = now_utc.strftime("%Y-%m-%dT%H:00")

    result = {}
    for i, iata in enumerate(iatas):
        d = arr[i] if i < len(arr) else arr[0]
        # 現況気温・気圧
        cur_oat = round(d.get("current", {}).get("temperature_2m", 15))
        cur_qnh = d.get("current", {}).get("pressure_msl", 1013)
        # 時間別気温（現在から24時間分）
        times = d.get("hourly", {}).get("time", [])
        oats  = d.get("hourly", {}).get("temperature_2m", [])
        start = next((j for j, t in enumerate(times) if t >= now_str), 0)
        hourly = [round(oats[start + h]) if (start + h) < len(oats) else cur_oat
                  for h in range(24)]
        result[iata] = {
            "oat": cur_oat,
            "qnh": cur_qnh,
            "hourly_oat": hourly  # index 0=now, 1=+1h, ...
        }
        print(f"  Temp {iata}: {cur_oat}°C, QNH: {cur_qnh}hPa")
    return result

def main():
    now = datetime.now(timezone.utc)
    print(f"Fetching TAF + temperatures at {now.isoformat()}")

    # TAF取得
    taf_data = fetch_taf_data()
    print(f"  Got {len(taf_data)} TAF records")
    if taf_data:
        print(f"  First record keys: {list(taf_data[0].keys())}")
    result = {}
    for item in taf_data:
        # 複数のフィールド名に対応
        raw = (item.get("rawTAF") or item.get("raw_text") or item.get("text") or "").strip()
        if not raw:
            print(f"  SKIP (no raw): {list(item.keys())}")
            continue
        # ICAOコード取得：フィールドから取れない場合はRAWテキストの先頭から抽出
        icao = (item.get("stationId") or item.get("station_id") or
                item.get("icaoId") or item.get("icao_id") or "").strip()
        if not icao:
            # "TAF RJTT 191705Z..." または "RJTT 191705Z..." の形式から抽出
            import re
            m = re.match(r'^(?:TAF\s+)?([A-Z]{4})\s+\d{6}Z', raw)
            if m:
                icao = m.group(1)
        iata = IATA.get(icao, icao)
        issued = item.get("issueTime") or item.get("issue_time") or item.get("reportTime") or ""
        result[iata] = {"icao": icao, "issued": issued, "raw": raw}
        print(f"  TAF {iata} ({icao}): {raw[:60]}...")

    # 気温取得してマージ
    try:
        temps = fetch_temperatures()
        for iata, t in temps.items():
            if iata in result:
                result[iata]["oat"]        = t["oat"]
                result[iata]["qnh"]        = t["qnh"]
                result[iata]["hourly_oat"] = t["hourly_oat"]
            else:
                # TAFがない空港も気温だけ保存
                result[iata] = {
                    "icao": "",
                    "issued": "",
                    "raw": "",
                    "oat": t["oat"],
                    "qnh": t["qnh"],
                    "hourly_oat": t["hourly_oat"]
                }
    except Exception as e:
        print(f"Temperature fetch failed: {e}")

    output = {
        "updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tafs": result
    }
    with open("taf.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(result)} entries to taf.json")

if __name__ == "__main__":
    main()
