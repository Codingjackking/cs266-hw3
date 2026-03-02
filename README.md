# CS 266 - HW3: Selective vs. Blanket Security in Multi-Stage API Pipelines

**Naing Htet | CS 266 Information Security | 2026-03-01**

Full implementation, experimental data, and performance results for the CS 266 HW3 final report comparing selective and blanket security enforcement strategies in a multi-stage lottery prediction API.

---

## Overview

This project implements a five-stage lottery prediction pipeline in Flask and compares two security enforcement strategies:

- **Design A (Selective Security)** - Full security stack applied only to the high-risk Monte Carlo prediction endpoint (~57% endpoint coverage)
- **Design B (Blanket Security)** - Identical full security stack uniformly enforced across all 7 endpoints (100% coverage)

Both applications share the same Monte Carlo simulation logic (10,000 iterations), the same SQLite lottery dataset, and the same security stack components. All measured differences are attributable solely to the security policy.

---

## Key Results

| Metric                  | Selective   | Blanket     | Delta           |
| ----------------------- | ----------- | ----------- | --------------- |
| Avg mean latency        | 2,052 ms    | 2,081 ms    | 1.4% faster     |
| Avg std deviation       | 26.9 ms     | 117.7 ms    | 77% more stable |
| Throughput @ 10 users   | 4.60 req/s  | 4.33 req/s  | +10%            |
| Throughput @ 100 users  | 39.95 req/s | 15.33 req/s | +161%           |
| Public endpoint success | 100%        | 73-74%      | -               |

The throughput gap grows with concurrency because blanket security applies JWT verification and response encryption to every request, including public endpoints that carry no sensitive data. This compounds into a structural scalability plateau near 15 req/s at 100 users that cannot be resolved through configuration changes alone.

> **Note on Stage 2 results:** The original Stage 2 experiments reported a 281% throughput gap and a complete blanket collapse to 0 req/s at 25+ users. This was a testing artifact: all concurrent workers shared the same localhost IP, causing the per-IP rate limiter to treat 25-100 simulated users as a single user exhausting one 10 req/60s bucket. The final experiments correct this by switching to per-user rate limiting and provisioning 100 unique test accounts.

---

## Pipeline Architecture

![Pipeline Architecture](/outputs/pipeline_architecture.png)

**Full security stack** includes: JWT authentication, premium-tier authorization, rate limiting (10 req/60s per user), input validation, response encryption, audit logging, differential privacy (epsilon=0.1), and output sanitization.

---

## Repository Structure

```
cs266-hw3/
├── selective-security/        # Design A - Flask app on port 5001
│   └── app.py
├── blanket-security/          # Design B - Flask app on port 5002
│   └── app.py
├── backend/
│   ├── monte_carlo.py         # Shared simulation logic (identical in both apps)
│   ├── powerball.py           # Historical data scraper
│   ├── megamillions.py
│   ├── superlottoplus.py
│   └── data/                  # SQLite database + CSV files
├── test_performance.py        # Full performance test harness
├── outputs/                   # Generated graphs and reports
│   ├── latency_1_mean.png
│   ├── latency_2_distribution.png
│   ├── latency_3_std_dev.png
│   ├── latency_4_cv.png
│   ├── throughput_1_comparison.png
│   ├── throughput_2_scalability.png
│   ├── throughput_3_error_rate.png
│   ├── throughput_4_success_rate.png
│   └── comprehensive_performance_report.txt
├── setup.sh                   # Linux/Mac setup script
├── setup.bat                  # Windows setup script
└── init_db.py                 # Database initializer
```

---

## Setup and Running

### Step 1: Collect Historical Data

```bash
# Scrape all lotteries (recommended - takes a few minutes)
python3 scrape_historical_data.py all

# Or individually
python3 scrape_historical_data.py powerball      # 1992-2015
python3 scrape_historical_data.py megamillions   # 2002-2013
python3 scrape_historical_data.py superlotto     # 1986-2015
python3 scrape_historical_data.py fantasy5       # 2010-2020
```

### Step 2: Initialize the Database

```bash
python3 init_db.py
```

### Step 3: Run Both Apps

```bash
# Terminal 1 - Selective Security
cd selective-security
python3 app.py        # http://localhost:5001

# Terminal 2 - Blanket Security
cd blanket-security
python3 app.py        # http://localhost:5002
```

### Step 4: Run Performance Tests

```bash
python3 test_performance.py
```

Results and graphs are written to the `outputs/` directory.

**Windows users:** Use `setup.bat` for one-command setup. See `WINDOWS_GUIDE.md` for full instructions.

---

## Endpoints

| Endpoint                  | Selective             | Blanket    |
| ------------------------- | --------------------- | ---------- |
| `GET /health`             | No auth               | Full stack |
| `GET /history/<lottery>`  | No auth               | Full stack |
| `GET /jackpots`           | No auth               | Full stack |
| `GET /analyze/<lottery>`  | Input validation only | Full stack |
| `POST /predict/<lottery>` | **Full stack**        | Full stack |
| `POST /register`          | Open                  | Open       |
| `POST /login`             | Open                  | Open       |

---

## Test Harness Details

The performance test (`test_performance.py`) runs:

- **Latency tests:** 100 sequential requests per endpoint with 10 ms inter-request delay, measuring mean, P95, standard deviation, and coefficient of variation
- **Scalability tests:** `/jackpots` endpoint at 5 concurrency levels (10, 25, 50, 75, 100 users) sustained for 15 seconds each
- **Per-user token pool:** 100 unique accounts (`scale_user_000` through `scale_user_099`) provisioned so each concurrent worker operates with its own independent JWT and rate-limit bucket

Hardware used: HP Envy x360, 16 GB RAM, localhost loopback (no network latency).

---

## Threat Model

| Asset                        | Sensitivity | Protection                        |
| ---------------------------- | ----------- | --------------------------------- |
| Monte Carlo simulation logic | High        | Full stack + differential privacy |
| Premium predictions          | High        | JWT + premium-tier authorization  |
| Analysis algorithms          | Medium      | Input validation                  |
| Historical lottery data      | Low         | None (publicly available)         |

**Attack vectors addressed:** API flooding/DoS, SQL injection, unauthorized premium access, algorithm reverse-engineering via output pattern analysis, data exfiltration.

Differential privacy (epsilon=0.1) on prediction outputs ensures that even unauthenticated access to public endpoints cannot be used to reverse-engineer the Monte Carlo model from response patterns.

---

## Lottery Data Sources

| Lottery         | Period    | Format      |
| --------------- | --------- | ----------- |
| Powerball       | 1992-2015 | 5/59 + 1/35 |
| Mega Millions   | 2002-2013 | 5/56 + 1/46 |
| SuperLotto Plus | 1986-2015 | 5/47 + 1/27 |
| Fantasy 5       | 2010-2020 | 5/39        |

Data is scraped from official historical result archives and stored in SQLite. Monte Carlo predictions use authentic frequency distributions derived from actual draws.

---

## Technologies

- **Backend:** Python Flask (development server)
- **Database:** SQLite
- **Security:** PyJWT, bcrypt, Flask-Limiter, cryptography
- **Testing:** Python threading + requests library
- **Visualization:** matplotlib, numpy

---

## Report

The full final report (HW3_Final.docx) with all experimental results, trade-off analysis, and discussion of methodology corrections is included in the repository.
