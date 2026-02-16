#!/usr/bin/env python3
"""
Quick diagnostic to check server status and login
"""

import requests
import json

print("="*60)
print("SERVER DIAGNOSTIC")
print("="*60)
print()

# Check if servers are running
print("1. Checking if servers are running...")
print()

# Check Selective Security (Port 5001)
try:
    resp = requests.get('http://localhost:5001/api/health', timeout=2)
    print(f"✅ Selective Security (5001): Server is UP")
    print(f"   Response: {resp.status_code}")
    print(f"   Content: {resp.text[:100]}")
except requests.exceptions.RequestException as e:
    print(f"❌ Selective Security (5001): Server is DOWN")
    print(f"   Error: {e}")
    print()
    print("   → Start the server: cd selective-security && python app.py")

print()

# Check Blanket Security (Port 5002)
try:
    # Blanket requires auth, so we expect 401
    resp = requests.get('http://localhost:5002/api/health', timeout=2)
    print(f"✅ Blanket Security (5002): Server is UP")
    print(f"   Response: {resp.status_code}")
    print(f"   Content: {resp.text[:100]}")
except requests.exceptions.RequestException as e:
    print(f"❌ Blanket Security (5002): Server is DOWN")
    print(f"   Error: {e}")
    print()
    print("   → Start the server: cd blanket-security && python app.py")

print()
print("="*60)
print("2. Testing user registration and login...")
print("="*60)
print()

# Test registration and login on Selective Security
print("Testing Selective Security (5001):")
print()

# Try to login with test user
login_data = {
    'username': 'test_premium',
    'password': 'password123'
}

try:
    resp = requests.post(
        'http://localhost:5001/api/login',
        json=login_data,
        timeout=5
    )
    
    print(f"Login Status Code: {resp.status_code}")
    print(f"Login Response: {resp.text}")
    
    if resp.status_code == 200:
        data = resp.json()
        if 'token' in data:
            print(f"✅ Login successful! Token received.")
            token = data['token']
            print(f"   Token (first 50 chars): {token[:50]}...")
        else:
            print(f"❌ Login response missing 'token' field")
            print(f"   Available fields: {list(data.keys())}")
    else:
        print(f"❌ Login failed with status {resp.status_code}")
        
except Exception as e:
    print(f"❌ Login request failed: {e}")

print()
print("="*60)
print("DIAGNOSIS COMPLETE")
print("="*60)
print()
print("If servers are DOWN:")
print("  1. Open Terminal 1: cd selective-security && python app.py")
print("  2. Open Terminal 2: cd blanket-security && python app.py")
print("  3. Wait for servers to start (you'll see 'Running on...')")
print("  4. Then run: python test_performance.py")
print()