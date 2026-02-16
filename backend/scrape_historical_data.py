#!/usr/bin/env python3
"""
Unified Lottery Data Scraper
Scrapes historical lottery data from multiple lottery types
"""

import sys
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import csv
import time
import re

# Setup directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# BACKEND_DIR = os.path.join(BASE_DIR, "backend")
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://california.lottonumbers.com/"
}


# ========================================
# POWERBALL SCRAPER (1992-2015)
# ========================================
def scrape_powerball():
    """Scrape Powerball historical data (1992-2015)"""
    print("\n" + "="*60)
    print("SCRAPING POWERBALL (1992-2015)")
    print("="*60)
    
    OUTPUT_FILE = os.path.join(DATA_DIR, "powerball_results.csv")
    base_url = "https://california.lottonumbers.com/powerball/past-numbers/{year}"
    all_data = []
    
    for year in range(1992, 2016):
        print(f"  Scraping Powerball {year}...")
        url = base_url.format(year=year)
        
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code != 200:
                print(f"    [WARN] Failed to fetch year {year}")
                continue
            
            soup = BeautifulSoup(response.content, "html.parser")
            rows = soup.select("table.past-results tbody tr")
            
            for row in rows:
                date_cell = row.select_one(".date-row")
                if not date_cell:
                    continue
                
                winning_numbers = [ball.text.strip() for ball in row.select("ul.balls .ball")]
                powerball_elem = row.select_one("ul.balls .powerball")
                powerball = powerball_elem.text.strip() if powerball_elem else ""
                
                jackpot_elem = row.select_one("[data-title='Jackpot']")
                jackpot = jackpot_elem.text.strip() if jackpot_elem else ""
                
                all_data.append([
                    date_cell.text.strip(),
                    ", ".join(winning_numbers),
                    powerball,
                    jackpot
                ])
            
            time.sleep(0.4)
            
        except Exception as e:
            print(f"    [ERROR] {e}")
    
    # Sort chronologically
    try:
        all_data.sort(key=lambda x: datetime.strptime(x[0], "%m/%d/%Y"))
        print(f"\n  ✓ Sorted {len(all_data)} draws chronologically")
        if all_data:
            print(f"  Date range: {all_data[0][0]} → {all_data[-1][0]}")
    except Exception as e:
        print(f"  Warning: Could not sort data: {e}")
    
    # Save CSV
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Winning Numbers", "Powerball", "Jackpot"])
        writer.writerows(all_data)
    
    print(f"\n  ✅ Saved {len(all_data)} Powerball draws to {OUTPUT_FILE}")
    return len(all_data)


# ========================================
# MEGA MILLIONS SCRAPER (2002-2012)
# ========================================
def scrape_megamillions():
    """Scrape Mega Millions historical data (2002-2012)"""
    print("\n" + "="*60)
    print("SCRAPING MEGA MILLIONS (2002-2012)")
    print("="*60)
    
    OUTPUT_FILE = os.path.join(DATA_DIR, "megamillions_results.csv")
    base_url = "https://california.lottonumbers.com/mega-millions/past-numbers/{year}"
    all_data = []
    
    for year in range(2002, 2013):
        print(f"  Scraping Mega Millions {year}...")
        url = base_url.format(year=year)
        
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                print(f"    [WARN] Failed to fetch year {year}")
                continue
            
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table", class_="past-results")
            
            if not table:
                print(f"    [WARN] No results table found for {year}")
                continue
            
            rows = table.find("tbody").find_all("tr")
            
            for row in rows:
                # Skip month headers
                if row.find("td", class_="monthRow"):
                    continue
                
                # Date
                date_cell = row.find("td", class_="date-row")
                if not date_cell:
                    continue
                date = date_cell.text.strip()
                
                # Balls
                balls_ul = row.find("ul", class_="balls")
                if not balls_ul:
                    continue
                
                # Exclude mega-ball AND megaplier when collecting main balls
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
                
                # Jackpot
                jackpot_cell = row.find("td", attrs={"data-title": "Jackpot"})
                jackpot = jackpot_cell.text.strip() if jackpot_cell else ""
                
                all_data.append([
                    date,
                    ", ".join(main_balls),
                    mega_ball,
                    jackpot
                ])
            
            time.sleep(0.4)
            
        except Exception as e:
            print(f"    [ERROR] {e}")
    
    # Sort chronologically
    try:
        all_data.sort(key=lambda x: datetime.strptime(x[0], '%m/%d/%Y'))
        print(f"\n  ✓ Sorted {len(all_data)} draws chronologically")
        if all_data:
            print(f"  Date range: {all_data[0][0]} → {all_data[-1][0]}")
    except Exception as e:
        print(f"  Warning: Could not sort data: {e}")
    
    # Save CSV
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Winning Numbers", "Mega Ball", "Jackpot"])
        writer.writerows(all_data)
    
    print(f"\n  ✅ Saved {len(all_data)} Mega Millions draws to {OUTPUT_FILE}")
    return len(all_data)


# ========================================
# SUPERLOTTO PLUS SCRAPER (1986-2014)
# ========================================
def scrape_superlotto():
    """Scrape SuperLotto Plus historical data (1986-2014)"""
    print("\n" + "="*60)
    print("SCRAPING SUPERLOTTO PLUS (1986-2014)")
    print("="*60)
    
    OUTPUT_FILE = os.path.join(DATA_DIR, "superlotto_results.csv")
    base_url = "https://california.lottonumbers.com/superlotto-plus/past-numbers/{year}"
    all_data = []
    
    for year in range(1986, 2015):
        print(f"  Scraping SuperLotto Plus {year}...")
        url = base_url.format(year=year)
        
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                print(f"    [WARN] HTTP {resp.status_code} for {year}")
                continue
            
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.select_one("table.past-results")
            
            if not table:
                print(f"    [WARN] No results table for {year}")
                continue
            
            rows = table.select("tbody tr")
            
            for row in rows:
                date_cell = row.select_one("td.date-row")
                if not date_cell:
                    continue
                
                date = date_cell.get_text(strip=True)
                
                balls = [
                    li.get_text(strip=True)
                    for li in row.select("ul.balls li.ball")
                ]
                
                # Normalize rule differences (some years have 5 balls, some have 6)
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
                
                all_data.append([
                    date,
                    ", ".join(main_numbers),
                    mega if mega else "",
                    jackpot
                ])
            
            time.sleep(0.4)
            
        except Exception as e:
            print(f"    [ERROR] {e}")
    
    # Sort chronologically
    try:
        all_data.sort(key=lambda x: datetime.strptime(x[0], "%m/%d/%Y"))
        print(f"\n  ✓ Sorted {len(all_data)} draws chronologically")
        if all_data:
            print(f"  Date range: {all_data[0][0]} → {all_data[-1][0]}")
    except Exception as e:
        print(f"  Warning: Could not sort data: {e}")
    
    # Save CSV
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Winning Numbers", "Mega", "Jackpot"])
        writer.writerows(all_data)
    
    print(f"\n  ✅ Saved {len(all_data)} SuperLotto Plus draws to {OUTPUT_FILE}")
    return len(all_data)


# ========================================
# FANTASY 5 SCRAPER (2010-2019)
# ========================================
def scrape_fantasy5():
    """Scrape Fantasy 5 historical data (2010-2019)"""
    print("\n" + "="*60)
    print("SCRAPING FANTASY 5 (2010-2019)")
    print("="*60)
    
    OUTPUT_FILE = os.path.join(DATA_DIR, "fantasy5_results.csv")
    base_url = "https://california.lottonumbers.com/fantasy-5/past-numbers/{year}"
    all_data = []
    
    for year in range(2010, 2020):
        print(f"  Scraping Fantasy 5 {year}...")
        url = base_url.format(year=year)
        
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                print(f"    [WARN] HTTP {resp.status_code} for year {year}")
                continue
            
            # Detect Cloudflare / bot protection
            if "Checking your browser" in resp.text or "cloudflare" in resp.text.lower():
                print(f"    [BLOCKED] Cloudflare protection triggered for year {year}")
                continue
            
            soup = BeautifulSoup(resp.text, "html.parser")
            table = (
                soup.find("table", class_="past-results")
                or soup.find("table", class_="results-table")
            )
            
            if not table:
                print(f"    [WARN] No results table found for {year}")
                continue
            
            for row in table.select("tbody tr"):
                # Skip month headers
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
                
                all_data.append([
                    date,
                    ", ".join(balls),
                    jackpot
                ])
            
            time.sleep(0.4)
            
        except Exception as e:
            print(f"    [ERROR] {e}")
    
    # Sort chronologically
    try:
        all_data.sort(key=lambda x: datetime.strptime(x[0], "%m/%d/%Y"))
        print(f"\n  ✓ Sorted {len(all_data)} draws chronologically")
        if all_data:
            print(f"  Date range: {all_data[0][0]} → {all_data[-1][0]}")
    except Exception as e:
        print(f"  Warning: Could not sort data: {e}")
    
    # Save CSV
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Winning Numbers", "Jackpot"])
        writer.writerows(all_data)
    
    print(f"\n  ✅ Saved {len(all_data)} Fantasy 5 draws to {OUTPUT_FILE}")
    return len(all_data)


# ========================================
# MAIN PROGRAM
# ========================================
def main():
    """Main scraping orchestrator"""
    print("\n" + "="*60)
    print("LOTTERY ORACLE - HISTORICAL DATA SCRAPER")
    print("="*60)
    print(f"Data directory: {DATA_DIR}")
    
    if len(sys.argv) < 2:
        print("\nUsage: python scrape_historical_data.py <lottery_type>")
        print("\nOptions:")
        print("  all          - Scrape all lotteries (recommended)")
        print("  powerball    - Scrape Powerball only")
        print("  megamillions - Scrape Mega Millions only")
        print("  superlotto   - Scrape SuperLotto Plus only")
        print("  fantasy5     - Scrape Fantasy 5 only")
        sys.exit(1)
    
    lottery_type = sys.argv[1].lower()
    
    total_draws = 0
    start_time = time.time()
    
    if lottery_type == "all":
        total_draws += scrape_powerball()
        total_draws += scrape_megamillions()
        total_draws += scrape_superlotto()
        total_draws += scrape_fantasy5()
    elif lottery_type == "powerball":
        total_draws = scrape_powerball()
    elif lottery_type == "megamillions":
        total_draws = scrape_megamillions()
    elif lottery_type == "superlotto":
        total_draws = scrape_superlotto()
    elif lottery_type == "fantasy5":
        total_draws = scrape_fantasy5()
    else:
        print(f"\n❌ Unknown lottery type: {lottery_type}")
        print("\nValid options: all, powerball, megamillions, superlotto, fantasy5")
        sys.exit(1)
    
    elapsed = time.time() - start_time
    
    print("\n" + "="*60)
    print("SCRAPING COMPLETE")
    print("="*60)
    print(f"Total draws collected: {total_draws}")
    print(f"Time elapsed: {elapsed:.1f} seconds")
    print(f"Data saved to: {DATA_DIR}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()