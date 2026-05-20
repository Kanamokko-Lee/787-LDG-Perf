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

HEADERS = {"User-Agent": "787-LDG-Perf/1.0 github.com/Kanamokko-Lee/787-LDG-Perf"}

def extract_icao(raw):
    m = re.search(r'\b([A-Z]{4})\s+\d{6}Z\b', raw)
    return m.group(1) if m else None

def parse_wind(raw):
    """RAWテキストから風向・風速を抽出"""
    m = re.search(r'\b(VRB|(\d{3}))(\d{2,3})(G\d{2,3})?KT\b', raw)
    if not m:
        return None, None
    if m.group(1) == 'VRB':
        return 'VRB', int(m.group(3))
    return int(m.group(2)), int(m.group(3))

def parse_qnh(raw):
    """METARからQNH(hPa)を抽出"""
    m = re.search(r'\bQ(\d{4})\b', raw)
    if m:
        return int(m.group(1))
    m = re.search(r'\bA(\d{4})\b', raw)
    if m:
        return round(int(m.group(1)) * 0.0338639 * 100) / 100 * 33.8639
    return None

def parse_temp(raw):
    """METARから気温を抽出"""
    m = re.search(r'\b(M?)(\d{2})/(M?)(\d{2})\b', raw)
    if m:
        t = int(m.group(2))
        if m.group(1) == 'M':
            t = -t
        return t
    return None

def fetch_taf_data():
    ids = ",".join(IATA.keys())
    url = f"https://aviationweather.gov/api/data/taf?ids={ids}&format=json&metar=false"
    r = requests.get(url, timeout=30, headers=HEADERS)
    r.raise_for_status()
    return r.json()

def fetch_metar_data():
    ids = ",".join(IATA.keys())
    url = f"https://aviationweather.gov/api/data/metar?ids={ids}&format=json&hours=2"
    r = requests.get(url, timeout=30, headers=HEADERS)
    r.raise_for_status()
    return r.json()

def fetch_temperatures():
    iatas = list(APTS.keys())
    lats = ",".join(str(APTS[k][0]) for k in iatas)
    lons = ",".join(str(APTS[k][1]) for k in iatas)
    url = (f"https://api.open-meteo.com/v1/forecast"
           f"?latitude={lats}&longitude={lons}"
           f"&current=temperature_2m,pressure_msl"
           f"&hourly=temperature_2m&forecast_days=2&timezone=UTC")
    r = requests.get(url, timeout=30, headers=HEADERS)
    r.raise_for_status()
    data = r.json()
    arr = data if isinstance(data, list) else [data]
    now_utc = datetime.now(timezone.utc)
    now_str = now_utc.strftime("%Y-%m-%dT%H:00")
    result = {}
    for i, iata in enumerate(iatas):
        d = arr[i] if i < len(arr) else arr[0]
        cur = d.get("current", {})
        oat = round(cur.get("temperature_2m", 15))
        qnh = round(cur.get("pressure_msl", 1013))
        times = d.get("hourly", {}).get("time", [])
        oats  = d.get("hourly", {}).get("temperature_2m", [])
        start = next((j for j, t in enumerate(times) if t >= now_str), 0)
        hourly_oat = [round(oats[start + h]) if (start + h) < len(oats) else oat
                      for h in range(25)]
        result[iata] = {"oat": oat, "qnh": qnh, "hourly_oat": hourly_oat}
    return result

def build_taf_groups(raw, now_utc):
    """
    TAFのRAWテキストを解析し、時間ごとのグループを作成。
    各グループに開始時刻(UTC hour offset from now)と風情報を付与。
    """
    # FM/BECMG/TEMPO/PROBで分割
    sections = re.split(r'\s+(?=FM\d{6}|BECMG\s+\d{4}/\d{4}|TEMPO\s+\d{4}/\d{4}|PROB\d{2})', raw.strip())
    groups = []
    now_day  = now_utc.day
    now_hour = now_utc.hour

    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue

        # 開始時刻を取得
        start_day, start_hour = None, None

        # FM: FM2006xx
        fm = re.match(r'FM(\d{2})(\d{2})\d{2}', sec)
        if fm:
            start_day  = int(fm.group(1))
            start_hour = int(fm.group(2))

        # ヘッダー行: ICAO DDHHMMZ DDHH/DDHH
        hdr = re.search(r'\b[A-Z]{4}\s+\d{6}Z\s+(\d{2})(\d{2})/\d{4}', sec)
        if hdr and start_day is None:
            start_day  = int(hdr.group(1))
            start_hour = int(hdr.group(2))

        # BECMG/TEMPO: DDDD/DDDD
        bt = re.match(r'(?:BECMG|TEMPO)\s+(\d{2})(\d{2})/\d{4}', sec)
        if bt and start_day is None:
            start_day  = int(bt.group(1))
            start_hour = int(bt.group(2))

        # UTC offset時間を計算
        if start_day is not None and start_hour is not None:
            day_diff = start_day - now_day
            if day_diff < -15: day_diff += 30  # 月末跨ぎ
            offset_h = day_diff * 24 + (start_hour - now_hour)
        else:
            offset_h = 0

        # 風情報
        wdir, wspd = parse_wind(sec)

        groups.append({
            "text": sec,
            "offset_h": offset_h,  # nowからの時間オフセット
            "wdir": wdir,
            "wspd": wspd
        })

    return groups

def main():
    now = datetime.now(timezone.utc)
    print(f"=== fetch_taf.py {now.isoformat()} ===")

    # TAF取得
    taf_items = fetch_taf_data()
    print(f"TAF: {len(taf_items)} items")

    result = {}
    for item in taf_items:
        raw = ""
        for key in ("rawTAF", "raw_text", "text", "tafText"):
            raw = (item.get(key) or "").strip()
            if raw:
                break
        if not raw:
            continue
        icao = extract_icao(raw)
        if not icao or icao not in IATA:
            continue
        iata = IATA[icao]
        issued = item.get("issueTime") or item.get("issue_time") or ""
        groups = build_taf_groups(raw, now)
        result[iata] = {
            "icao": icao, "issued": issued, "raw": raw,
            "groups": groups
        }
        print(f"  TAF {iata}: {len(groups)} groups")

    # METAR取得（現況wind/oat/qnh）
    try:
        metar_items = fetch_metar_data()
        print(f"METAR: {len(metar_items)} items")
        # 最新METARのみ使用（station_idでまとめて最新を選ぶ）
        metar_latest = {}
        for m in metar_items:
            raw_m = (m.get("rawOb") or m.get("raw_text") or "").strip()
            if not raw_m:
                continue
            icao = extract_icao(raw_m)
            if not icao or icao not in IATA:
                continue
            iata = IATA[icao]
            # observationTimeで最新を選ぶ
            obs_time = m.get("observationTime") or m.get("observation_time") or ""
            if iata not in metar_latest or obs_time > metar_latest[iata]["obs_time"]:
                wdir, wspd = parse_wind(raw_m)
                oat  = parse_temp(raw_m)
                qnh  = parse_qnh(raw_m)
                metar_latest[iata] = {
                    "raw": raw_m, "obs_time": obs_time,
                    "wdir": wdir, "wspd": wspd,
                    "oat": oat, "qnh": qnh
                }
        for iata, mv in metar_latest.items():
            if iata in result:
                result[iata]["metar_wdir"] = mv["wdir"]
                result[iata]["metar_wspd"] = mv["wspd"]
                result[iata]["metar_oat"]  = mv["oat"]
                result[iata]["metar_qnh"]  = mv["qnh"]
                result[iata]["metar_raw"]  = mv["raw"]
            print(f"  METAR {iata}: wind={mv['wdir']}/{mv['wspd']} oat={mv['oat']} qnh={mv['qnh']}")
    except Exception as e:
        print(f"METAR FAILED: {e}")

    # 気温予報（open-meteo）
    try:
        temps = fetch_temperatures()
        for iata, t in temps.items():
            if iata in result:
                result[iata]["hourly_oat"] = t["hourly_oat"]
            else:
                result[iata] = {"icao":"","issued":"","raw":"","groups":[],
                                "hourly_oat": t["hourly_oat"]}
            # METARのoat/qnhがない場合のフォールバック
            if iata in result and result[iata].get("metar_oat") is None:
                result[iata]["metar_oat"] = t["oat"]
            if iata in result and result[iata].get("metar_qnh") is None:
                result[iata]["metar_qnh"] = t["qnh"]
        print("Temperatures: OK")
    except Exception as e:
        print(f"Temperatures FAILED: {e}")

    output = {"updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "tafs": result}
    with open("taf.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"=== Saved {len(result)} entries ===")

if __name__ == "__main__":
    main()
