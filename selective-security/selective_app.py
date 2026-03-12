import os
import sqlite3
import sys
import jwt
import bcrypt
import time
import numpy as np
import logging

from collections import Counter
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS

backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
sys.path.insert(0, backend_dir)
from monte_carlo import predict_next_draw, get_lottery_config, sanitize_predictions, run_simulation

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = 'lottery-selective-demo-key'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('selective_security.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def convert_numpy(obj):
    if isinstance(obj, dict):
        return {k: convert_numpy(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy(i) for i in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_numpy(i) for i in obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    else:
        return obj

# Database connection
def get_db():
    conn = sqlite3.connect('lottery_data.db')
    conn.row_factory = sqlite3.Row
    return conn

# ============================================================================
# SECURITY ENHANCEMENTS: Result Caching
# ============================================================================

# SECURITY: Cache to prevent computation abuse and reduce load
prediction_cache = {}
CACHE_TTL = 300  # 5 minutes

def get_cached_or_compute(lottery_type, num_tickets, user_id, cache_ttl=CACHE_TTL):
    """
    Cache predictions to prevent computation abuse

    This protects against:
    - Excessive computation requests
    - Algorithm reverse engineering through repeated queries
    - Resource exhaustion attacks
    """
    cache_window = int(time.time() // cache_ttl)
    cache_key = f"{lottery_type}_{num_tickets}_{cache_window}"

    if cache_key in prediction_cache:
        logger.info(f"Cache hit: lottery_type={lottery_type}, user_id={user_id}")
        return prediction_cache[cache_key], True

    logger.info(f"Cache miss: lottery_type={lottery_type}, user_id={user_id}")
    return None, False

def cache_predictions(lottery_type, num_tickets, predictions, cache_ttl=CACHE_TTL):
    """Store predictions in cache"""
    cache_window = int(time.time() // cache_ttl)
    cache_key = f"{lottery_type}_{num_tickets}_{cache_window}"
    prediction_cache[cache_key] = predictions

    # Clean old cache entries (older than 2x TTL)
    current_time = time.time()
    keys_to_delete = []
    for key in list(prediction_cache.keys()):
        try:
            key_time = int(key.split('_')[-1]) * cache_ttl
            if current_time - key_time > cache_ttl * 2:
                keys_to_delete.append(key)
        except Exception:
            pass

    for key in keys_to_delete:
        del prediction_cache[key]

# ============================================================================
# SELECTIVE SECURITY: Only critical endpoints have security
# ============================================================================

def log_request_critical(endpoint, user_id=None, status=200, duration=0, details=None):
    """Audit logging only for critical operations"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO api_logs (timestamp, endpoint, user_id, status_code, response_time_ms)
        VALUES (?, ?, ?, ?, ?)
    ''', (datetime.now().isoformat(), endpoint, user_id, status, duration))

    conn.commit()
    conn.close()

    logger.info(f"Critical endpoint access: endpoint={endpoint}, user_id={user_id}, status={status}, duration_ms={duration:.2f}, details={details}")

# Rate limiting only on CRITICAL endpoints - per user (falls back to IP for unauthenticated endpoints)
request_counts = {}
def rate_limit_critical(max_requests=10, window=60):
    """Rate limiting only for critical operations, keyed per user ID (or IP for auth endpoints)"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Use user_id if already set by require_auth_premium, otherwise fall back to IP
            key = getattr(request, 'user_id', None) or request.remote_addr
            now = time.time()

            if key not in request_counts:
                request_counts[key] = []

            # Clean old requests
            request_counts[key] = [t for t in request_counts[key] if now - t < window]

            if len(request_counts[key]) >= max_requests:
                log_request_critical(request.path, None, 429, 0, f"Rate limit exceeded for key: {key}")
                return jsonify({'error': 'Rate limit exceeded'}), 429

            request_counts[key].append(now)
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
            log_request_critical(request.path, None, 401, 0, "Missing authentication token")
            return jsonify({'error': 'Authentication required'}), 401

        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            request.user_id = payload['user_id']
            request.user_tier = payload['tier']
            return f(*args, **kwargs)
        except jwt.InvalidTokenError as e:
            log_request_critical(request.path, None, 401, 0, f"Invalid token: {str(e)}")
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
                if "'" in value or '"' in value or ';' in value:
                    return jsonify({'error': 'Invalid input'}), 400

        return f(*args, **kwargs)
    return wrapper

# ============================================================================
# PUBLIC ENDPOINTS - No Security 
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health():
    """
    SELECTIVE SECURITY: Public endpoint - NO authentication
    Security Stack: None (maximum performance)
    """
    return jsonify({'status': 'healthy', 'version': 'selective-1.0-enhanced'}), 200

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
        'fantasy5': 'fantasy5_history'
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
        ('fantasy5', 'fantasy5_history')
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
    valid_types = ['powerball', 'megamillions', 'superlotto', 'fantasy5']
    if lottery_type not in valid_types:
        return jsonify({'error': 'Invalid lottery type'}), 400

    table_map = {
        'powerball': 'powerball_history',
        'megamillions': 'megamillions_history',
        'superlotto': 'superlotto_history',
        'fantasy5': 'fantasy5_history'
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
@require_auth_premium
@rate_limit_critical(max_requests=10, window=60)
@validate_critical
def predict_numbers(lottery_type):
    """
    SELECTIVE SECURITY: Prediction is CRITICAL - full security stack applied

    Protection Features:
    - Authentication & Authorization
    - Rate Limiting (per user)
    - Input Validation
    - Differential Privacy (ε=0.1)
    - Output Sanitization
    - Audit Logging
    - Result Caching
    """
    start = time.time()

    # Authorization
    if request.user_tier == 'free':
        log_request_critical(f'/api/predict/{lottery_type}', request.user_id, 403, 0, "Free tier access denied")
        return jsonify({'error': 'Premium feature required'}), 403

    # Validation
    valid_types = ['powerball', 'megamillions', 'superlotto', 'fantasy5']
    if lottery_type not in valid_types:
        log_request_critical(f'/api/predict/{lottery_type}', request.user_id, 400, 0, "Invalid lottery type")
        return jsonify({'error': 'Invalid lottery type'}), 400

    data = request.get_json()
    num_tickets = data.get('num_tickets', 1)

    if not isinstance(num_tickets, int) or num_tickets < 1 or num_tickets > 10:
        log_request_critical(f'/api/predict/{lottery_type}', request.user_id, 400, 0, "Invalid num_tickets")
        return jsonify({'error': 'num_tickets must be between 1 and 10'}), 400

    # Check cache first to prevent computation abuse
    cached_result, is_cached = get_cached_or_compute(lottery_type, num_tickets, request.user_id)

    if is_cached:
        duration = (time.time() - start) * 1000
        log_request_critical(f'/api/predict/{lottery_type}', request.user_id, 200, duration, "Cache hit")

        response_data = {
            'lottery_type': lottery_type,
            'predictions': cached_result,
            'generated_at': datetime.now().isoformat(),
            'computation_time_ms': duration,
            'cached': True
        }

        return jsonify(convert_numpy(response_data)), 200

    predictions = run_monte_carlo_simulation_secure(
        lottery_type,
        num_tickets,
        user_id=request.user_id
    )

    # SECURITY: Cache the results
    cache_predictions(lottery_type, num_tickets, predictions)

    duration = (time.time() - start) * 1000
    log_request_critical(f'/api/predict/{lottery_type}', request.user_id, 200, duration, f"Predictions generated: {num_tickets} tickets")

    response_data = {
        'lottery_type': lottery_type,
        'predictions': predictions,
        'generated_at': datetime.now().isoformat(),
        'computation_time_ms': duration,
        'cached': False,
        'security': {
            'differential_privacy': True,
            'epsilon': 0.1,
            'sanitized': True
        }
    }

    response_data = convert_numpy(response_data)
    return jsonify(response_data), 200

def run_monte_carlo_simulation_secure(lottery_type, num_tickets, user_id=None):
    """Monte Carlo simulation — delegates to shared run_simulation in monte_carlo.py"""
    table_map = {
        'powerball': 'powerball_history',
        'megamillions': 'megamillions_history',
        'superlotto': 'superlotto_history',
        'fantasy5': 'fantasy5_history'
    }

    conn = get_db()
    cursor = conn.cursor()
    table = table_map.get(lottery_type, 'powerball_history')
    cursor.execute(f'SELECT jackpot_amount FROM {table} ORDER BY draw_date DESC LIMIT 1')
    result = cursor.fetchone()
    jackpot = result[0] * 1_000_000 if result else 100_000_000
    conn.close()

    return run_simulation(lottery_type, num_tickets, jackpot, user_id=user_id)

# ============================================================================
# AUTHENTICATION ENDPOINTS - Moderate Security (IP-based rate limit, no user yet)
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

        logger.info(f"User registered: user_id={user_id}, username={username}")

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

    logger.info(f"User logged in: user_id={user[0]}, username={username}, tier={user[2]}")

    response_data = {
        'token': token,
        'user_id': user[0],
        'tier': user[2]
    }

    return jsonify(response_data), 200

if __name__ == '__main__':
    logger.info("Starting Selective Security API")
    app.run(host='0.0.0.0', port=5001, debug=True)