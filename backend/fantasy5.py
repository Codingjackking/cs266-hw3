import requests
from bs4 import BeautifulSoup
import csv
import time
import re
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# go up to backend/
# BACKEND_DIR = os.path.dirname(os.path.dirname(BASE_DIR))

DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_FILE = os.path.join(DATA_DIR, "fantasy5_results.csv")


BASE_URL = "https://california.lottonumbers.com/fantasy-5/past-numbers/{year}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Referer": "https://california.lottonumbers.com/"
}

def scrape_year(year):
    url = BASE_URL.format(year=year)
    resp = requests.get(url, headers=HEADERS, timeout=15)

    if resp.status_code != 200:
        print(f"[WARN] HTTP {resp.status_code} for year {year}")
        return []

    # Detect Cloudflare / bot protection
    if "Checking your browser" in resp.text or "cloudflare" in resp.text.lower():
        print(f"[BLOCKED] Cloudflare protection triggered for year {year}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    table = (
        soup.find("table", class_="past-results")
        or soup.find("table", class_="results-table")
    )

    if not table:
        print(f"[WARN] No results table found for {year}")
        return []

    results = []

    for row in table.select("tbody tr"):
        # Skip month headers explicitly
        if row.find("td", class_="monthRow"):
            continue

        # Date
        date_cell = row.find("td", class_="date-row")
        if not date_cell:
            continue
        date = date_cell.get_text(strip=True)

        # Balls
        balls = [
            li.get_text(strip=True)
            for li in row.select("ul.balls li.ball")
        ]

        if len(balls) != 5:
            continue

        # Jackpot (extract $ amount only)
        jackpot_cell = row.find("td", attrs={"data-title": "Jackpot"})
        jackpot = ""
        if jackpot_cell:
            match = re.search(r"\$\s*[\d,]+", jackpot_cell.get_text())
            if match:
                jackpot = match.group(0)

        results.append([
            date,
            ", ".join(balls),
            jackpot
        ])

    return results


# -------------------------------------------------------
# Scrape all years
# -------------------------------------------------------
all_data = []

for year in range(2010, 2020):
    print(f"Scraping Fantasy 5 {year}...")
    year_data = scrape_year(year)
    all_data.extend(year_data)
    time.sleep(0.4)

# -------------------------------------------------------
# Save CSV
# -------------------------------------------------------
with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Date", "Winning Numbers", "Jackpot"])
    writer.writerows(all_data)

print(f"\n✅ Saved {len(all_data)} Fantasy 5 draws to {OUTPUT_FILE}")
