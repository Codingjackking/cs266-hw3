import requests
from bs4 import BeautifulSoup
from datetime import datetime
import csv
import time
import re
import os
import time
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# go up to backend/
# BACKEND_DIR = os.path.dirname(os.path.dirname(BASE_DIR))

DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_FILE = os.path.join(DATA_DIR, "superlotto_results.csv")

BASE_URL = "https://california.lottonumbers.com/superlotto-plus/past-numbers/{year}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://california.lottonumbers.com/"
}

def scrape_year(year):
    url = BASE_URL.format(year=year)
    resp = requests.get(url, headers=HEADERS, timeout=15)

    if resp.status_code != 200:
        print(f"[WARN] HTTP {resp.status_code} for {year}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.select_one("table.past-results")

    if not table:
        print(f"[WARN] No results table for {year}")
        return []

    rows = table.select("tbody tr")
    results = []

    for row in rows:
        date_cell = row.select_one("td.date-row")
        if not date_cell:
            continue

        date = date_cell.get_text(strip=True)

        balls = [
            li.get_text(strip=True)
            for li in row.select("ul.balls li.ball")
        ]

        # ---------------------------
        # Normalize rule differences
        # ---------------------------
        if len(balls) == 6:
            main_numbers = balls[:5]
            mega = balls[5]
        elif len(balls) == 5:
            main_numbers = balls
            mega = None
        else:
            continue

        jackpot_cell = row.select_one('td[data-title="Jackpot"]')
        jackpot = ""
        if jackpot_cell:
            m = re.search(r"\$\s*[\d,]+", jackpot_cell.get_text())
            if m:
                jackpot = m.group(0)

        results.append([
            date,
            ", ".join(main_numbers),
            mega,
            jackpot
        ])

    return results

# ------------------------------
# Scrape all years
# ------------------------------
all_data = []

for year in range(1986, 2015):
    print(f"Scraping SuperLotto Plus {year}...")
    year_data = scrape_year(year)
    all_data.extend(year_data)
    time.sleep(0.4)

# ------------------------------
# Final chronological sort
# ------------------------------
print("\nSorting all SuperLotto Plus data chronologically...")

try:
    all_data.sort(key=lambda x: datetime.strptime(x[0], "%m/%d/%Y"))
    
    if all_data:
        print(f"✓ Date range: {all_data[0][0]} → {all_data[-1][0]}")
    else:
        print("⚠ No data collected to sort.")
        
except Exception as e:
    print(f"Warning: Could not sort data: {e}")

# ------------------------------
# Save CSV
# ------------------------------
with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Date", "Winning Numbers", "Mega", "Jackpot"])
    writer.writerows(all_data)

print(f"\n✅ Saved {len(all_data)} SuperLotto Plus draws to {OUTPUT_FILE}")
