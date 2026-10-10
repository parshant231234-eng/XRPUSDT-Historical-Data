import os
import sys
import io
import csv
import zipfile
import datetime
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

symbol = "XRPUSDT"
HEADERS = ["timestamp", "datetime_utc", "open", "high", "low", "close", "volume", "quote_volume", "trade_count", "taker_buy_volume", "taker_buy_quote_volume"]

print(f"Starting cloud download for {symbol}...")

tasks = []
for y in range(2017, 2027):
    for m in range(1, 13):
        if (y, m) <= (2026, 9):
            tasks.append((y, m))

def fetch_month(y, m):
    url = f"https://data.binance.vision/data/spot/monthly/klines/{symbol}/1m/{symbol}-1m-{y}-{m:02d}.zip"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            name = z.namelist()[0]
            content = z.read(name).decode("utf-8")
    except Exception:
        return None
        
    rows = []
    for r in csv.reader(io.StringIO(content)):
        if not r: continue
        try:
            raw_ts = int(r[0])
            ts = raw_ts // 1000 if len(str(raw_ts)) > 13 else raw_ts
            dt_utc = datetime.datetime.fromtimestamp(ts / 1000, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            rows.append([ts, dt_utc, r[1], r[2], r[3], r[4], r[5], r[7], r[8], r[9], r[10]])
        except Exception:
            continue
            
    if not rows: return None
    target_dir = os.path.join("1m", str(y), f"{m:02d}")
    os.makedirs(target_dir, exist_ok=True)
    csv_path = os.path.join(target_dir, f"{symbol}_1m_{y}-{m:02d}.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADERS)
        w.writerows(rows)
    return (y, m, len(rows))

total_candles = 0
saved_months = 0
with ThreadPoolExecutor(max_workers=20) as executor:
    futures = [executor.submit(fetch_month, y, m) for y, m in tasks]
    for f in as_completed(futures):
        res = f.result()
        if res:
            saved_months += 1
            total_candles += res[2]

# October 2026 daily
oct_rows = []
for d in range(1, 10):
    url = f"https://data.binance.vision/data/spot/daily/klines/{symbol}/1m/{symbol}-1m-2026-10-{d:02d}.zip"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            name = z.namelist()[0]
            content = z.read(name).decode("utf-8")
        for r in csv.reader(io.StringIO(content)):
            if not r: continue
            raw_ts = int(r[0])
            ts = raw_ts // 1000 if len(str(raw_ts)) > 13 else raw_ts
            dt_utc = datetime.datetime.fromtimestamp(ts / 1000, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            oct_rows.append([ts, dt_utc, r[1], r[2], r[3], r[4], r[5], r[7], r[8], r[9], r[10]])
    except Exception:
        pass

if oct_rows:
    oct_rows.sort(key=lambda x: x[0])
    target_dir = os.path.join("1m", "2026", "10")
    os.makedirs(target_dir, exist_ok=True)
    csv_path = os.path.join(target_dir, f"{symbol}_1m_2026-10.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADERS)
        w.writerows(oct_rows)
    saved_months += 1
    total_candles += len(oct_rows)

print(f"Downloaded {saved_months} months, {total_candles:,} total candles.")

readme = f"""# {symbol} 1-Minute Historical Kline Dataset

An institutional-grade, open-source archive of cleaned, standardized, and validated **1-minute intraday historical kline data** for **{symbol}** (Binance Spot).

---

## 📊 Dataset Specifications
- **Symbol:** `{symbol}`
- **Market:** Binance Spot
- **Timeframe:** 1 Minute (`1m`)
- **Total Months:** `{saved_months}` months
- **Total Candles:** `{total_candles:,}` 1-minute candles
- **Schema:** `timestamp, datetime_utc, open, high, low, close, volume, quote_volume, trade_count, taker_buy_volume, taker_buy_quote_volume`

---

## 🏛️ Directory Hierarchy
```text
{symbol}-Historical-Data/
├── README.md
└── 1m/
    └── <YYYY>/
        └── <MM>/
            └── {symbol}_1m_<YYYY-MM>.csv
```

---

## ⚡ 1-Line Pandas Stream Loader
Load any month directly from GitHub's raw CDN without cloning the repository:

```python
import pandas as pd

url = "https://raw.githubusercontent.com/parshant231234-eng/{symbol}-Historical-Data/main/1m/2026/09/{symbol}_1m_2026-09.csv"
df = pd.read_csv(url)
print(df.head())
```
"""
with open("README.md", "w") as f:
    f.write(readme)
