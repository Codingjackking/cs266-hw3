
import sqlite3
import jwt
import bcrypt
import time
import random
import hashlib
import json
import sys
import os
import random as rand

from collections import Counter
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS
from monte_carlo import predict_next_draw, get_lottery_config

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = 'lottery-selective-demo-key'

# Database connection
def get_db():
    conn = sqlite3.connect('lottery_data.db')
    conn.row_factory = sqlite3.Row
    return conn

# ============================================================================
# SELECTIVE SECURITY: Only critical endpoints have security
# ============================================================================

# Minimal logging for CRITICAL endpoints only
def log_request_critical(endpoint, user_id=None, status=200, duration=0):
    """Audit logging only for critical operations"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO api_logs (timestamp, endpoint, user_id, status_code, response_time_ms)
        VALUES (?, ?, ?, ?, ?)
    ''', (datetime.now().isoformat(), endpoint, user_id, status, duration))
    
    conn.commit()
    conn.close()

# Rate limiting only on CRITICAL endpoints
request_counts = {}
def rate_limit_critical(max_requests=10, window=60):
    """Rate limiting only for critical operations"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            ip = request.remote_addr
            now = time.time()
            
            if ip not in request_counts:
                request_counts[ip] = []
            
            # Clean old requests
            request_counts[ip] = [t for t in request_counts[ip] if now - t < window]
            
            if len(request_counts[ip]) >= max_requests:
                log_request_critical(request.path, None, 429, 0)
                return jsonify({'error': 'Rate limit exceeded'}), 429
            
            request_counts[ip].append(now)
            return f(*args, **kwargs)
        return wrapper
    return decorator

# Authentication required only for PREMIUM features
def require_auth_premium(f):
    """JWT authentication only on premium endpoints"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            log_request_critical(request.path, None, 401, 0)
            return jsonify({'error': 'Authentication required'}), 401
        
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            request.user_id = payload['user_id']
            request.user_tier = payload['tier']
            return f(*args, **kwargs)
        except jwt.InvalidTokenError:
            log_request_critical(request.path, None, 401, 0)
            return jsonify({'error': 'Invalid token'}), 401
    
    return wrapper

# Input validation only for CRITICAL endpoints
def validate_critical(f):
    """Input validation only on critical operations"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        # Validate content type for POST requests
        if request.method == 'POST':
            if not request.is_json:
                return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        # Basic sanitization on critical path parameters
        for key, value in kwargs.items():
            if isinstance(value, str):
                # Check for obvious SQL injection
                if "'" in value or '"' in value or ';' in value:
                    return jsonify({'error': 'Invalid input'}), 400
        
        return f(*args, **kwargs)
    return wrapper

# ============================================================================
# PUBLIC ENDPOINTS - No Security (Fast)
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health():
    """
    SELECTIVE SECURITY: Public endpoint - NO authentication
    Security Stack: None (maximum performance)
    """
    return jsonify({'status': 'healthy', 'version': 'selective-1.0'}), 200

@app.route('/api/history/<lottery_type>', methods=['GET'])
def get_history(lottery_type):
    """
    SELECTIVE SECURITY: Public historical data - NO authentication
    Security Stack: None
    Historical lottery data is public information, no protection needed
    """
    valid_types = {
        'powerball': 'powerball_history',
        'megamillions': 'megamillions_history',
        'superlotto': 'superlotto_history',
        'cash4life': 'cash4life_history'
    }
    
    if lottery_type not in valid_types:
        return jsonify({'error': 'Invalid lottery type'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    query = f'SELECT * FROM {valid_types[lottery_type]} ORDER BY draw_date DESC LIMIT 20'
    cursor.execute(query)
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(results), 200

@app.route('/api/jackpots', methods=['GET'])
def get_jackpots():
    """
    SELECTIVE SECURITY: Public jackpot info - NO authentication
    Security Stack: None
    """
    conn = get_db()
    cursor = conn.cursor()
    
    jackpots = {}
    for lottery, table in [
        ('powerball', 'powerball_history'),
        ('megamillions', 'megamillions_history'),
        ('superlotto', 'superlotto_history'),
        ('cash4life', 'cash4life_history')
    ]:
        cursor.execute(f'SELECT jackpot_amount FROM {table} ORDER BY draw_date DESC LIMIT 1')
        result = cursor.fetchone()
        jackpots[lottery] = result[0] if result else 0
    
    conn.close()
    
    return jsonify(jackpots), 200

# ============================================================================
# PROTECTED ENDPOINTS - Moderate Security
# ============================================================================

@app.route('/api/analyze/<lottery_type>', methods=['GET'])
@validate_critical
def analyze_lottery(lottery_type):
    """
    SELECTIVE SECURITY: Analysis has input validation only
    Security Stack: Validation only (no auth, no rate limiting)
    Medium value operation - light protection
    """
    valid_types = ['powerball', 'megamillions', 'superlotto', 'cash4life']
    if lottery_type not in valid_types:
        return jsonify({'error': 'Invalid lottery type'}), 400
    
    table_map = {
        'powerball': 'powerball_history',
        'megamillions': 'megamillions_history',
        'superlotto': 'superlotto_history',
        'cash4life': 'cash4life_history'
    }
    
    conn = get_db()
    cursor = conn.cursor()
    
    table = table_map[lottery_type]
    cursor.execute(f'SELECT numbers FROM {table} ORDER BY draw_date DESC LIMIT 100')
    rows = cursor.fetchall()
    
    all_numbers = []
    for row in rows:
        numbers = [int(n) for n in row[0].split(',')]
        all_numbers.extend(numbers)
    
    frequency = Counter(all_numbers)
    most_common = frequency.most_common(10)
    
    conn.close()
    
    response_data = {
        'lottery_type': lottery_type,
        'most_frequent': [{'number': n, 'count': c} for n, c in most_common],
        'total_draws_analyzed': len(rows)
    }
    
    return jsonify(response_data), 200

# ============================================================================
# CRITICAL ENDPOINTS - Full Security Stack
# ============================================================================

@app.route('/api/predict/<lottery_type>', methods=['POST'])
@rate_limit_critical(max_requests=10, window=60)
@require_auth_premium
@validate_critical
def predict_numbers(lottery_type):
    """
    SELECTIVE SECURITY: Prediction is CRITICAL - full security
    Security Stack: Auth + Authorization + Rate Limit + Validation + Logging
    High value operation - maximum protection
    """
    start = time.time()
    
    # Authorization
    if request.user_tier == 'free':
        log_request_critical(f'/api/predict/{lottery_type}', request.user_id, 403, 0)
        return jsonify({'error': 'Premium feature required'}), 403
    
    # Validation
    valid_types = ['powerball', 'megamillions', 'superlotto', 'cash4life']
    if lottery_type not in valid_types:
        log_request_critical(f'/api/predict/{lottery_type}', request.user_id, 400, 0)
        return jsonify({'error': 'Invalid lottery type'}), 400
    
    data = request.get_json()
    num_tickets = data.get('num_tickets', 1)
    
    if not isinstance(num_tickets, int) or num_tickets < 1 or num_tickets > 10:
        log_request_critical(f'/api/predict/{lottery_type}', request.user_id, 400, 0)
        return jsonify({'error': 'num_tickets must be between 1 and 10'}), 400
    
    # Monte Carlo simulation
    predictions = run_monte_carlo_simulation(lottery_type, num_tickets)
    
    duration = (time.time() - start) * 1000
    log_request_critical(f'/api/predict/{lottery_type}', request.user_id, 200, duration)
    
    response_data = {
        'lottery_type': lottery_type,
        'predictions': predictions,
        'generated_at': datetime.now().isoformat(),
        'computation_time_ms': duration
    }
    
    return jsonify(response_data), 200

def run_monte_carlo_simulation(lottery_type, num_tickets):
    """Monte Carlo simulation using real historical data - no extra security overhead"""
    
    # Add parent directory to path to import monte_carlo
    backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
    sys.path.insert(0, backend_dir)
    
    # Map internal lottery names to monte_carlo names
    lottery_map = {
        'powerball': 'powerball',
        'megamillions': 'megamillions',
        'superlotto': 'superlotto',
        'cash4life': 'fantasy5'  # Use fantasy5 as substitute for cash4life
    }
    
    mc_lottery_type = lottery_map.get(lottery_type, 'powerball')
    
    # Get jackpot from database
    conn = get_db()
    cursor = conn.cursor()
    
    table_map = {
        'powerball': 'powerball_history',
        'megamillions': 'megamillions_history',
        'superlotto': 'superlotto_history',
        'cash4life': 'cash4life_history'
    }
    
    table = table_map.get(lottery_type, 'powerball_history')
    cursor.execute(f'SELECT jackpot_amount FROM {table} ORDER BY draw_date DESC LIMIT 1')
    result = cursor.fetchone()
    jackpot = result[0] * 1_000_000 if result else 100_000_000  # Convert to actual amount
    conn.close()
    
    # Run Monte Carlo simulation
    simulations = predict_next_draw(
        upcoming_jackpot=jackpot,
        draw_date=datetime.now().strftime('%Y-%m-%d'),
        lottery_type=mc_lottery_type,
        n_simulations=num_tickets * 100,  # Generate pool
        window_years=5,
        random_seed=None
    )
    
    # Sample tickets from simulation results
    selected = rand.sample(simulations, min(num_tickets, len(simulations)))
    
    tickets = []
    for main_nums, special in selected:
        tickets.append({
            'numbers': list(main_nums),
            'special': special
        })
    
    return tickets

# ============================================================================
# AUTHENTICATION ENDPOINTS - Moderate Security
# ============================================================================

@app.route('/api/register', methods=['POST'])
@rate_limit_critical(max_requests=10, window=60)
@validate_critical
def register():
    """User registration with moderate security"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO users (username, password_hash, tier)
            VALUES (?, ?, ?)
        ''', (username, password_hash, 'free'))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        
        return jsonify({'message': 'User registered', 'user_id': user_id}), 201
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Username exists'}), 400

@app.route('/api/login', methods=['POST'])
@rate_limit_critical(max_requests=10, window=60)
@validate_critical
def login():
    """User login with moderate security"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, password_hash, tier FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401
    
    if not bcrypt.checkpw(password.encode(), user[1].encode()):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    token = jwt.encode({
        'user_id': user[0],
        'tier': user[2],
        'exp': datetime.now(timezone.utc) + timedelta(days=7)
    }, app.config['SECRET_KEY'], algorithm='HS256')
    
    response_data = {
        'token': token,
        'user_id': user[0],
        'tier': user[2]
    }
    
    return jsonify(response_data), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)