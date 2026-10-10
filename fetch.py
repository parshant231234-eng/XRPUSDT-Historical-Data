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

now = datetime.datetime.now(datetime.timezone.utc)
current_year = now.year
current_month = now.month
current_day = now.day

print(f"=== Dynamic Ingestion Runner for {symbol} (UTC Now: {now.strftime('%Y-%m-%d %H:%M:%S')}) ===")

# 1. Closed Past Months (from 2017 to last month)
past_month_tasks = []
for y in range(2017, current_year + 1):
    for m in range(1, 13):
        # Only months strictly before the current month
        if (y < current_year) or (y == current_year and m < current_month):
            target_path = os.path.join("1m", str(y), f"{m:02d}", f"{symbol}_1m_{y}-{m:02d}.csv")
            # Only download if not already saved!
            if not os.path.exists(target_path):
                past_month_tasks.append((y, m))

def fetch_monthly_archive(y, m):
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

if past_month_tasks:
    print(f"Fetching {len(past_month_tasks)} missing past monthly archives with 10 parallel workers...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_monthly_archive, y, m) for y, m in past_month_tasks]
        for f in as_completed(futures):
            res = f.result()
            if res:
                print(f"Saved completed month: {res[0]}-{res[1]:02d} ({res[2]:,} candles)")
else:
    print("All past months up to last month are already archived on disk!")

# 2. Current Month Daily Klines (Day 1 up to yesterday)
print(f"Checking current active month daily archives ({current_year}-{current_month:02d}, days 1 to {current_day - 1})...")
current_month_file = os.path.join("1m", str(current_year), f"{current_month:02d}", f"{symbol}_1m_{current_year}-{current_month:02d}.csv")
existing_rows = {}

# Load existing current month candles if file already exists
if os.path.exists(current_month_file):
    with open(current_month_file, "r") as f:
        reader = csv.reader(f)
        next(reader, None) # skip header
        for r in reader:
            if len(r) >= len(HEADERS):
                existing_rows[int(r[0])] = r

new_days_fetched = 0
for d in range(1, current_day):
    url = f"https://data.binance.vision/data/spot/daily/klines/{symbol}/1m/{symbol}-1m-{current_year}-{current_month:02d}-{d:02d}.zip"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            name = z.namelist()[0]
            content = z.read(name).decode("utf-8")
        day_candle_count = 0
        for r in csv.reader(io.StringIO(content)):
            if not r: continue
            raw_ts = int(r[0])
            ts = raw_ts // 1000 if len(str(raw_ts)) > 13 else raw_ts
            dt_utc = datetime.datetime.fromtimestamp(ts / 1000, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            existing_rows[ts] = [ts, dt_utc, r[1], r[2], r[3], r[4], r[5], r[7], r[8], r[9], r[10]]
            day_candle_count += 1
        new_days_fetched += 1
    except Exception:
        pass

if existing_rows:
    target_dir = os.path.join("1m", str(current_year), f"{current_month:02d}")
    os.makedirs(target_dir, exist_ok=True)
    all_sorted = [existing_rows[ts] for ts in sorted(existing_rows.keys())]
    with open(current_month_file, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADERS)
        w.writerows(all_sorted)
    print(f"Current month {current_year}-{current_month:02d} updated with {len(all_sorted):,} total candles.")

# 3. Dynamic README Statistics Calculation
all_csvs = []
total_candle_count = 0
for root, dirs, files in os.walk("1m"):
    for f in files:
        if f.endswith(".csv"):
            all_csvs.append(os.path.join(root, f))
            # Fast count lines without loading whole file
            with open(os.path.join(root, f), "r") as fl:
                total_candle_count += max(0, sum(1 for _ in fl) - 1)

all_csvs.sort()
print(f"Repository Summary: {len(all_csvs)} monthly/daily files, {total_candle_count:,} total candles.")

readme = f"""# {symbol} 1-Minute Historical Kline Dataset

An institutional-grade, open-source archive of cleaned, standardized, and validated **1-minute intraday historical kline data** for **{symbol}** (Binance Spot).

---

## 📊 Dataset Specifications
- **Symbol:** `{symbol}`
- **Market:** Binance Spot
- **Timeframe:** 1 Minute (`1m`)
- **Total Archived Files:** `{len(all_csvs)}` files
- **Total Candles:** `{total_candle_count:,}` 1-minute candles
- **Last Updated:** `{now.strftime('%Y-%m-%d %H:%M:%S')} UTC`
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

---

## 🔄 Automated Ingestion Pipeline
This repository automatically runs a weekly GitHub Actions workflow every Sunday midnight (UTC) to append newly closed daily candles and archive completed months.
"""

with open("README.md", "w") as f:
    f.write(readme)

print("Dynamic sync complete!")
