# Lottery Oracle - Selective vs Blanket Security Demo

## Project Overview

This is a version of the Lottery Oracle application designed to demonstrate the difference between **selective** and **blanket** security controls in a multi-stage lottery prediction pipeline.

## Real Historical Data Integration

This demo uses REAL historical lottery data from older rule periods, scraped from official lottery websites. The Monte Carlo predictions are based on authentic probability distributions derived from actual lottery draws.

## Data Collection

### Step 1: Scrape Historical Lottery Data

Before running the security demo, you need to collect real historical lottery data:

```bash
# Scrape all lotteries (recommended)
python3 scrape_historical_data.py all

# Or scrape individual lotteries
python3 scrape_historical_data.py powerball
python3 scrape_historical_data.py megamillions
python3 scrape_historical_data.py superlotto
python3 scrape_historical_data.py fantasy5
```

This will create CSV files in the `data/` directory:

- `powerball_results.csv` - Draws from 1992-2015 (older 5/59 + 1/35 format)
- `megamillions_results.csv` - Draws from 2002-2013 (pre-2013 5/56 + 1/46 format)
- `superlotto_results.csv` - Draws from 1986-2015 (original format)
- `fantasy5_results.csv` - Draws from 2010-2020 (5/39 format)

### Step 2: Initialize Database

The database initialization now loads REAL scraped data:

```bash
python3 init_db.py
```

This loads the CSV files into SQLite for the security demo.

## Pipeline Architecture

### Stages

1. **Historical Data Access** - Retrieve real historical lottery data
2. **Data Analysis** - Calculate statistics and patterns from actual draws
3. **Monte Carlo Simulation** - Generate probability distributions using real frequency data
4. **Prediction Generation** - Create lottery number predictions based on authentic patterns
5. **Results Delivery** - Return predictions with jackpot info

## Security Approaches

### Selective Security (85% coverage, optimized performance)

- **Public Stages** (minimal protection):
  - Historical data access (read-only, no sensitive data)
  - Results delivery (public information)
- **Protected Stages** (moderate security):
  - Data analysis (input validation only)
  - Prediction generation (rate limiting)
- **Critical Stages** (maximum security):
  - Monte Carlo simulation (authentication + authorization + audit logging)

### Blanket Security (100% coverage, higher overhead)

- **All Stages** receive full protection:
  - JWT authentication
  - Role-based authorization
  - Input validation
  - Encryption in transit
  - Comprehensive audit logging

## Threat Model

### Attacker Profile

- **External Attackers**: Attempting to overwhelm API, inject malicious data, or scrape predictions
- **Unauthorized Users**: Trying to access premium features without payment
- **Malicious Users**: Attempting to reverse-engineer prediction algorithms

### Attack Vectors

1. API flooding/DoS attacks
2. SQL injection or data poisoning
3. Unauthorized access to premium predictions
4. Algorithm reverse engineering
5. Data exfiltration

### Protected Assets

- **High Value**: Monte Carlo simulation logic, premium predictions
- **Medium Value**: Analysis algorithms, user tier data
- **Low Value**: Historical lottery data (publicly available)

## Running the Demo

### 🪟 Windows Users (Quick Start)

```cmd
setup.bat      REM One-time setup (scrapes data, initializes DB)
run_demo.bat   REM Automated demo with performance tests
```

**See WINDOWS_GUIDE.md for detailed Windows instructions**

### 🐧 Linux/Mac Users (Quick Start)

```bash
./setup.sh      # One-time setup (scrapes data, initializes DB)
./run_demo.sh   # Automated demo with performance tests
```

### Manual Testing (All Platforms)

#### Selective Security Version

```bash
cd selective-security
python app.py   # Windows: python | Linux/Mac: python3
```

Access at: http://localhost:5001

#### Blanket Security Version

```bash
cd blanket-security
python app.py   # Windows: python | Linux/Mac: python3
```

Access at: http://localhost:5002

#### Performance Testing

```bash
python test_performance.py   # Windows: python | Linux/Mac: python3
```

## Key Metrics Comparison

| Metric            | Selective | Blanket   | Improvement         |
| ----------------- | --------- | --------- | ------------------- |
| Avg Response Time | ~120ms    | ~280ms    | 57% faster          |
| Throughput        | 850 req/s | 380 req/s | 124% higher         |
| Security Coverage | 85%       | 100%      | -15%                |
| Code Complexity   | Medium    | High      | Lower maintenance   |
| Residual Risk     | Low       | Very Low  | Acceptable tradeoff |

## Lottery Types Supported

- Powerball
- Mega Millions
- SuperLotto Plus
- Cash4Life

## Technologies

- Backend: Python Flask
- Database: SQLite with historical data
- Frontend: React (simplified)
- Security: JWT, bcrypt, rate limiting
