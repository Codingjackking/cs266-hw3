import requests
from bs4 import BeautifulSoup
import csv
import time
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_FILE = os.path.join(DATA_DIR, "megamillions_results.csv")

# Create data directory if it doesn't exist
os.makedirs(DATA_DIR, exist_ok=True)

BASE_URL = "https://california.lottonumbers.com/mega-millions/past-numbers/{year}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def scrape_year(year):
    url = BASE_URL.format(year=year)
    resp = requests.get(url, headers=HEADERS, timeout=10)

    if resp.status_code != 200:
        print(f"[WARN] Failed to fetch year {year}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_="past-results")

    if not table:
        print(f"[WARN] No results table found for {year}")
        return []

    rows = table.find("tbody").find_all("tr")
    results = []

    for row in rows:
        # Skip month headers
        if row.find("td", class_="monthRow"):
            continue
        
        # ---- Date ----
        date_cell = row.find("td", class_="date-row")
        if not date_cell:
            continue
        date = date_cell.text.strip()

        # ---- Balls ----
        balls_ul = row.find("ul", class_="balls")
        if not balls_ul:
            continue

        # FIX: Exclude both mega-ball AND megaplier when collecting main balls
        main_balls = [
            li.text.strip()
            for li in balls_ul.find_all("li", class_="ball")
            if "mega-ball" not in li.get("class", []) 
            and "megaplier" not in li.get("class", [])
        ]

        mega_ball_el = balls_ul.find("li", class_="mega-ball")
        if len(main_balls) != 5 or not mega_ball_el:
            continue

        mega_ball = mega_ball_el.text.strip()

        # ---- Jackpot ----
        jackpot_cell = row.find("td", attrs={"data-title": "Jackpot"})
        jackpot = jackpot_cell.text.strip() if jackpot_cell else ""

        results.append([
            date,
            ", ".join(main_balls),
            mega_ball,
            jackpot
        ])
    
    # Sort by date (earliest to latest) - website shows newest first
    try:
        results.sort(key=lambda x: datetime.strptime(x[0], '%m/%d/%Y'))
        print(f"  Sorted {len(results)} draws by date (earliest to latest)")
    except Exception as e:
        print(f"  Warning: Could not sort by date: {e}")
    
    return results


# -------------------------------------------------------
# Scrape all years
# -------------------------------------------------------
all_data = []

for year in range(2002, 2013):
    print(f"Scraping Mega Millions {year}...")
    year_data = scrape_year(year)
    all_data.extend(year_data)
    time.sleep(0.4)

# Final sort of all data to ensure chronological order
print("\nSorting all data chronologically...")
try:
    all_data.sort(key=lambda x: datetime.strptime(x[0], '%m/%d/%Y'))
    print(f"✓ All data sorted from {all_data[0][0]} to {all_data[-1][0]}")
except Exception as e:
    print(f"Warning: Could not sort all data: {e}")

# -------------------------------------------------------
# Save CSV
# -------------------------------------------------------
with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Date", "Winning Numbers", "Mega Ball", "Jackpot"])
    writer.writerows(all_data)

print(f"\n✅ Saved {len(all_data)} Mega Millions draws to {OUTPUT_FILE}")
print(f"   Date range: {all_data[0][0]} to {all_data[-1][0]}")