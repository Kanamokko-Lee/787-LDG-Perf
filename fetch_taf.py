import re
import json
import requests
from datetime import datetime, timezone

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

def extract_icao(raw):
    """RAWテキストから4文字ICAOコードを確実に抽出する"""
    # パターン: 4文字大文字 + 空白 + 6桁数字 + Z
    # 例: "TAF RJTT 191705Z", "TAF AMD RJTT 191705Z", "RJTT 191705Z"
    m = re.search(r'\b([A-Z]{4})\s+\d{6}Z\b', raw)
    if m:
        return m.group(1)
    return None

def fetch_taf():
    icao_list = list(IATA.keys())
    ids = ",".join(icao_list)
    url = f"https://aviationweather.gov/api/data/taf?ids={ids}&format=json&metar=false"
    headers = {"User-Agent": "787-LDG-Perf/1.0 github.com/Kanamokko-Lee/787-LDG-Perf"}
    r = requests.get(url, timeout=30, headers=headers)
    r.raise_for_status()
    items = r.json()
    print(f"Got {len(items)} items from API")

    result = {}
    for item in items:
        # RAWテキスト取得（複数フィールド名に対応）
        raw = ""
        for key in ("rawTAF", "raw_text", "text", "tafText"):
            raw = (item.get(key) or "").strip()
            if raw:
                break
        if not raw:
            print(f"  SKIP: no raw text in {list(item.keys())}")
            continue

        # ICAOコード抽出
        icao = extract_icao(raw)
        if not icao:
            print(f"  SKIP: cannot extract ICAO from: {raw[:50]}")
            continue

        iata = IATA.get(icao)
        if not iata:
            print(f"  SKIP: unknown ICAO {icao}")
            continue

        issued = (item.get("issueTime") or item.get("issue_time") or
                  item.get("reportTime") or "")
        result[iata] = {"icao": icao, "issued": issued, "raw": raw}
        print(f"  OK: {iata} ({icao}) {raw[:50]}...")

    return result

def fetch_temperatures(result):
    """open-meteoから気温・気圧を取得してresultにマージ"""
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

    for i, iata in enumerate(iatas):
        d = arr[i] if i < len(arr) else arr[0]
        cur = d.get("current", {})
        oat = round(cur.get("temperature_2m", 15))
        qnh = cur.get("pressure_msl", 1013)
        times = d.get("hourly", {}).get("time", [])
        oats  = d.get("hourly", {}).get("temperature_2m", [])
        start = next((j for j, t in enumerate(times) if t >= now_str), 0)
        hourly = [round(oats[start + h]) if (start + h) < len(oats) else oat
                  for h in range(24)]
        entry = result.get(iata, {"icao": "", "issued": "", "raw": ""})
        entry["oat"] = oat
        entry["qnh"] = qnh
        entry["hourly_oat"] = hourly
        result[iata] = entry
        print(f"  Temp {iata}: {oat}°C QNH:{qnh}")

def main():
    now = datetime.now(timezone.utc)
    print(f"=== fetch_taf.py start {now.isoformat()} ===")

    result = fetch_taf()
    print(f"TAF: got {len(result)} airports")

    try:
        fetch_temperatures(result)
        print("Temperatures: OK")
    except Exception as e:
        print(f"Temperatures FAILED: {e}")

    output = {
        "updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tafs": result
    }
    with open("taf.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"=== Saved {len(result)} entries to taf.json ===")

if __name__ == "__main__":
    main()
