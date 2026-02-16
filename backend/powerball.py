import requests
from bs4 import BeautifulSoup
from datetime import datetime   
import csv
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# go up to backend/

DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

OUTPUT_FILE = os.path.join(DATA_DIR, "powerball_results.csv")

# Base URL for Powerball results by year
base_url = "https://california.lottonumbers.com/powerball/past-numbers/{year}"

# Function to scrape data for a single year
def scrape_year(year):
    url = base_url.format(year=year)
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to fetch data for year {year}.")
        return []
    
    soup = BeautifulSoup(response.content, "html.parser")
    rows = soup.select("table.past-results tbody tr")
    
    year_data = []
    for row in rows:
        # Extract date
        date = row.select_one(".date-row")
        if not date:
            continue
        
        # Extract winning numbers
        winning_numbers = [ball.text for ball in row.select("ul.balls .ball")]
        powerball = row.select_one("ul.balls .powerball").text if row.select_one("ul.balls .powerball") else ""
        
        # Extract jackpot (optional)
        jackpot = row.select_one("[data-title='Jackpot']").text.strip() if row.select_one("[data-title='Jackpot']") else ""
        
        year_data.append([date.text.strip(), ", ".join(winning_numbers), powerball, jackpot])
    
    return year_data

# Iterate through years and scrape data
all_data = []

for year in range(1992, 2016):
    print(f"Scraping Powerball {year}...")
    year_data = scrape_year(year)
    all_data.extend(year_data)
    time.sleep(0.4)

# Final sort of all data to ensure chronological order
print("\nSorting all Powerball data chronologically...")
try:
    all_data.sort(key=lambda x: datetime.strptime(x[0], "%m/%d/%Y"))
    print(f"✓ All data sorted from {all_data[0][0]} to {all_data[-1][0]}")
except Exception as e:
    print(f"Warning: Could not sort all data: {e}")

# -------------------------------------------------------
# Save CSV
# -------------------------------------------------------
with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Date", "Winning Numbers", "Powerball", "Jackpot"])
    writer.writerows(all_data)

print(f"\n✅ Saved {len(all_data)} Powerball draws to {OUTPUT_FILE}")
print(f"   Date range: {all_data[0][0]} to {all_data[-1][0]}")
