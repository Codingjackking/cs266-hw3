#!/usr/bin/env python3
"""
Database Initialization Script
Creates the lottery_data.db SQLite database with all required tables
"""

import sqlite3
import os
import csv
from datetime import datetime

DB_FILE = 'lottery_data.db'
DATA_DIR = os.path.join('backend', 'data')

def create_database():
    """Create database and all required tables"""
    print("="*60)
    print("LOTTERY ORACLE - DATABASE INITIALIZATION")
    print("="*60)
    print()
    
    # Remove existing database if it exists
    if os.path.exists(DB_FILE):
        print(f"⚠️  Removing existing database: {DB_FILE}")
        os.remove(DB_FILE)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    print("📋 Creating tables...")
    
    # ========================================
    # 1. USERS TABLE (for authentication)
    # ========================================
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            tier TEXT NOT NULL DEFAULT 'free',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("  ✅ users table created")
    
    # ========================================
    # 2. API LOGS TABLE (for audit logging)
    # ========================================
    cursor.execute('''
        CREATE TABLE api_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            user_id INTEGER,
            status_code INTEGER NOT NULL,
            response_time_ms REAL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    print("  ✅ api_logs table created")
    
    # ========================================
    # 3. LOTTERY HISTORY TABLES
    # ========================================
    
    # Powerball
    cursor.execute('''
        CREATE TABLE powerball_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw_date TEXT NOT NULL,
            numbers TEXT NOT NULL,
            powerball TEXT NOT NULL,
            jackpot_amount REAL
        )
    ''')
    print("  ✅ powerball_history table created")
    
    # Mega Millions
    cursor.execute('''
        CREATE TABLE megamillions_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw_date TEXT NOT NULL,
            numbers TEXT NOT NULL,
            mega_ball TEXT NOT NULL,
            jackpot_amount REAL
        )
    ''')
    print("  ✅ megamillions_history table created")
    
    # SuperLotto Plus
    cursor.execute('''
        CREATE TABLE superlotto_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw_date TEXT NOT NULL,
            numbers TEXT NOT NULL,
            mega TEXT,
            jackpot_amount REAL
        )
    ''')
    print("  ✅ superlotto_history table created")
    
    # fantasy5 (using Fantasy5 data as substitute)
    cursor.execute('''
        CREATE TABLE fantasy5_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw_date TEXT NOT NULL,
            numbers TEXT NOT NULL,
            jackpot_amount REAL
        )
    ''')
    print("  ✅ fantasy5_history table created")
    
    conn.commit()
    conn.close()
    
    print()
    print("✅ All tables created successfully")
    print()


def load_csv_data():
    """Load historical lottery data from CSV files"""
    print("📊 Loading historical data from CSV files...")
    print()
    
    if not os.path.exists(DATA_DIR):
        print(f"⚠️  Data directory not found: {DATA_DIR}")
        print("   Run: python scrape_historical_data.py all")
        print()
        return
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # ========================================
    # Load Powerball Data
    # ========================================
    powerball_file = os.path.join(DATA_DIR, 'powerball_results.csv')
    if os.path.exists(powerball_file):
        print(f"  Loading Powerball data from {powerball_file}...")
        with open(powerball_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                # Parse jackpot amount
                jackpot_str = row.get('Jackpot', '$0')
                jackpot_amount = parse_jackpot(jackpot_str)
                
                cursor.execute('''
                    INSERT INTO powerball_history (draw_date, numbers, powerball, jackpot_amount)
                    VALUES (?, ?, ?, ?)
                ''', (
                    row['Date'],
                    row['Winning Numbers'],
                    row['Powerball'],
                    jackpot_amount
                ))
                count += 1
            
            conn.commit()
            print(f"    ✅ Loaded {count} Powerball draws")
    else:
        print(f"    ⚠️  Powerball data not found: {powerball_file}")
    
    # ========================================
    # Load Mega Millions Data
    # ========================================
    megamillions_file = os.path.join(DATA_DIR, 'megamillions_results.csv')
    if os.path.exists(megamillions_file):
        print(f"  Loading Mega Millions data from {megamillions_file}...")
        with open(megamillions_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                jackpot_str = row.get('Jackpot', '$0')
                jackpot_amount = parse_jackpot(jackpot_str)
                
                cursor.execute('''
                    INSERT INTO megamillions_history (draw_date, numbers, mega_ball, jackpot_amount)
                    VALUES (?, ?, ?, ?)
                ''', (
                    row['Date'],
                    row['Winning Numbers'],
                    row['Mega Ball'],
                    jackpot_amount
                ))
                count += 1
            
            conn.commit()
            print(f"    ✅ Loaded {count} Mega Millions draws")
    else:
        print(f"    ⚠️  Mega Millions data not found: {megamillions_file}")
    
    # ========================================
    # Load SuperLotto Plus Data
    # ========================================
    superlotto_file = os.path.join(DATA_DIR, 'superlotto_results.csv')
    if os.path.exists(superlotto_file):
        print(f"  Loading SuperLotto Plus data from {superlotto_file}...")
        with open(superlotto_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                jackpot_str = row.get('Jackpot', '$0')
                jackpot_amount = parse_jackpot(jackpot_str)
                
                cursor.execute('''
                    INSERT INTO superlotto_history (draw_date, numbers, mega, jackpot_amount)
                    VALUES (?, ?, ?, ?)
                ''', (
                    row['Date'],
                    row['Winning Numbers'],
                    row.get('Mega', ''),
                    jackpot_amount
                ))
                count += 1
            
            conn.commit()
            print(f"    ✅ Loaded {count} SuperLotto Plus draws")
    else:
        print(f"    ⚠️  SuperLotto Plus data not found: {superlotto_file}")
    
    # ========================================
    # Load Fantasy5 Data (as fantasy5 substitute)
    # ========================================
    fantasy5_file = os.path.join(DATA_DIR, 'fantasy5_results.csv')
    if os.path.exists(fantasy5_file):
        print(f"  Loading Fantasy 5 data (as fantasy5) from {fantasy5_file}...")
        with open(fantasy5_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                jackpot_str = row.get('Jackpot', '$0')
                jackpot_amount = parse_jackpot(jackpot_str)
                
                cursor.execute('''
                    INSERT INTO fantasy5_history (draw_date, numbers, jackpot_amount)
                    VALUES (?, ?, ?)
                ''', (
                    row['Date'],
                    row['Winning Numbers'],
                    jackpot_amount if jackpot_amount > 0 else 1.0  # Default to $1M
                ))
                count += 1
            
            conn.commit()
            print(f"    ✅ Loaded {count} Fantasy 5 draws (as fantasy5)")
    else:
        print(f"    ⚠️  Fantasy 5 data not found: {fantasy5_file}")
    
    conn.close()
    print()
    print("✅ Historical data loaded successfully")
    print()


def parse_jackpot(jackpot_str):
    """Parse jackpot string to numeric value in millions"""
    if not jackpot_str or jackpot_str.strip() == '':
        return 0.0
    
    # Remove $ and commas
    cleaned = jackpot_str.replace('$', '').replace(',', '').strip()
    
    # Handle "Winner" text
    if 'Winner' in cleaned or 'winner' in cleaned.lower():
        # Extract just the number part
        import re
        match = re.search(r'[\d,]+', cleaned)
        if match:
            cleaned = match.group(0).replace(',', '')
        else:
            return 0.0
    
    try:
        amount = float(cleaned)
        # Convert to millions
        if amount > 1_000_000:
            return amount / 1_000_000
        else:
            return amount
    except (ValueError, AttributeError):
        return 0.0


def create_test_users():
    """Create test users for the demo"""
    print("👥 Creating test users...")
    
    import bcrypt
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create free tier user
    password_hash = bcrypt.hashpw('password123'.encode(), bcrypt.gensalt()).decode()
    cursor.execute('''
        INSERT INTO users (username, password_hash, tier)
        VALUES (?, ?, ?)
    ''', ('test_free', password_hash, 'free'))
    
    # Create premium tier user
    password_hash = bcrypt.hashpw('password123'.encode(), bcrypt.gensalt()).decode()
    cursor.execute('''
        INSERT INTO users (username, password_hash, tier)
        VALUES (?, ?, ?)
    ''', ('test_premium', password_hash, 'premium'))
    
    conn.commit()
    conn.close()
    
    print("  ✅ Created test users:")
    print("     - test_free / password123 (free tier)")
    print("     - test_premium / password123 (premium tier)")
    print()


def main():
    """Main initialization function"""
    create_database()
    load_csv_data()
    create_test_users()
    
    print("="*60)
    print("DATABASE INITIALIZATION COMPLETE")
    print("="*60)
    print()
    print(f"Database file: {DB_FILE}")
    print()
    print("Next steps:")
    print("  1. Copy database to security implementations:")
    print("     cp lottery_data.db selective-security/")
    print("     cp lottery_data.db blanket-security/")
    print()
    print("  2. Run the demo:")
    print("     ./run_demo.bat (Windows) or ./run_demo.sh (Linux/Mac)")
    print()


if __name__ == '__main__':
    main()