import hashlib
import sqlite3
import sys
import jwt
import bcrypt
import time
import numpy as np
import logging
import os

from collections import Counter
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, json, request, jsonify
from flask_cors import CORS

backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
sys.path.insert(0, backend_dir)
from monte_carlo import predict_next_draw, get_lottery_config, sanitize_predictions, run_simulation

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = 'lottery-blanket-demo-key'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('blanket_security.log'),
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
# BLANKET SECURITY: All endpoints have full security stack
# ============================================================================

# Comprehensive logging for ALL requests
def log_request(endpoint, user_id=None, status=200, duration=0, details=None):
    """Full audit logging for every request - DB + application log"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO api_logs (timestamp, endpoint, user_id, status_code, response_time_ms)
        VALUES (?, ?, ?, ?, ?)
    ''', (datetime.now().isoformat(), endpoint, user_id, status, duration))
    
    conn.commit()
    conn.close()

    # SECURITY: Enhanced application logging 
    logger.info(f"Blanket endpoint access: endpoint={endpoint}, user_id={user_id}, status={status}, duration_ms={duration:.2f}, details={details}")

# Rate limiting on ALL endpoints
request_counts = {}
def rate_limit_all(max_requests=20, window=60):
    """Rate limiting applied to every endpoint"""
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
                log_request(request.path, None, 429, 0)
                return jsonify({'error': 'Rate limit exceeded'}), 429
            
            request_counts[ip].append(now)
            return f(*args, **kwargs)
        return wrapper
    return decorator

# Authentication required for ALL endpoints
def require_auth_all(f):
    """JWT authentication on every endpoint"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            log_request(request.path, None, 401, 0)
            return jsonify({'error': 'Authentication required'}), 401
        
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            request.user_id = payload['user_id']
            request.user_tier = payload['tier']
            return f(*args, **kwargs)
        except jwt.InvalidTokenError:
            log_request(request.path, None, 401, 0)
            return jsonify({'error': 'Invalid token'}), 401
    
    return wrapper

# Input validation and sanitization for ALL endpoints
def validate_and_sanitize(f):
    """Comprehensive input validation on all requests"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        # Validate content type for POST requests
        if request.method == 'POST':
            if not request.is_json:
                return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        # Sanitize path parameters
        for key, value in kwargs.items():
            if isinstance(value, str):
                # Check for SQL injection patterns
                dangerous_patterns = ["'", '"', ';', '--', '/*', '*/', 'DROP', 'DELETE']
                for pattern in dangerous_patterns:
                    if pattern.lower() in value.lower():
                        log_request(request.path, None, 400, 0)
                        return jsonify({'error': 'Invalid input detected'}), 400
        
        return f(*args, **kwargs)
    return wrapper

# ============================================================================
# SECURITY ENHANCEMENTS: Result Caching
# ============================================================================

# SECURITY: Cache to prevent computation abuse and reduce load
prediction_cache = {}
CACHE_TTL = 300  # 5 minutes

def get_cached_or_compute(lottery_type, num_tickets, user_id, cache_ttl=CACHE_TTL):
    """
    Cache predictions to prevent computation abuse.
    Protects against excessive computation requests, algorithm reverse engineering
    through repeated queries, and resource exhaustion attacks.
    """
    cache_window = int(time.time() // cache_ttl)
    cache_key = f"{lottery_type}_{num_tickets}_{cache_window}"

    if cache_key in prediction_cache:
        logger.info(f"Cache hit: lottery_type={lottery_type}, user_id={user_id}")
        return prediction_cache[cache_key], True

    logger.info(f"Cache miss: lottery_type={lottery_type}, user_id={user_id}")
    return None, False

def cache_predictions(lottery_type, num_tickets, predictions, cache_ttl=CACHE_TTL):
    """Store predictions in cache and evict stale entries"""
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

# Encryption simulation (adds overhead)
def encrypt_response(data):
    """Simulate response encryption overhead"""
    # In production, this would be TLS/SSL encryption
    # Simulating encryption delay
    json_data = json.dumps(data)
    hash_obj = hashlib.sha256(json_data.encode())
    _ = hash_obj.hexdigest()
    time.sleep(0.01)  # Simulate encryption overhead
    return data

# ============================================================================
# ALL ENDPOINTS - Full Security Stack
# ============================================================================

@app.route('/api/health', methods=['GET'])
@rate_limit_all(max_requests=30, window=60)
@require_auth_all
@validate_and_sanitize
def health():
    """
    BLANKET SECURITY: Even health check requires authentication
    Security Stack: Auth + Rate Limit + Validation + Logging + Encryption
    """
    start = time.time()
    
    response_data = {'status': 'healthy', 'version': 'blanket-1.0'}

    duration = (time.time() - start) * 1000
    log_request('/api/health', request.user_id, 200, duration)
    return jsonify(encrypt_response(response_data)), 200

@app.route('/api/history/<lottery_type>', methods=['GET'])
@rate_limit_all(max_requests=20, window=60)
@require_auth_all
@validate_and_sanitize
def get_history(lottery_type):
    """
    BLANKET SECURITY: Historical data requires full authentication
    Security Stack: Auth + Rate Limit + Validation + Logging + Encryption
    Even though data is public, blanket approach protects everything
    """
    start = time.time()
    
    valid_types = {
        'powerball': 'powerball_history',
        'megamillions': 'megamillions_history',
        'superlotto': 'superlotto_history',
        'fantasy5': 'fantasy5_history'
    }
    
    if lottery_type not in valid_types:
        log_request(f'/api/history/{lottery_type}', request.user_id, 400, 0)
        return jsonify({'error': 'Invalid lottery type'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    query = f'SELECT * FROM {valid_types[lottery_type]} ORDER BY draw_date DESC LIMIT 20'
    cursor.execute(query)
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    duration = (time.time() - start) * 1000
    log_request(f'/api/history/{lottery_type}', request.user_id, 200, duration)
    
    return jsonify(encrypt_response(results)), 200

@app.route('/api/jackpots', methods=['GET'])
@rate_limit_all(max_requests=20, window=60)
@require_auth_all
@validate_and_sanitize
def get_jackpots():
    """
    BLANKET SECURITY: Jackpot data requires full authentication
    Security Stack: Auth + Rate Limit + Validation + Logging + Encryption
    """
    start = time.time()
    
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
    
    duration = (time.time() - start) * 1000
    log_request('/api/jackpots', request.user_id, 200, duration)
    
    return jsonify(encrypt_response(jackpots)), 200

@app.route('/api/analyze/<lottery_type>', methods=['GET'])
@rate_limit_all(max_requests=15, window=60)
@require_auth_all
@validate_and_sanitize
def analyze_lottery(lottery_type):
    """
    BLANKET SECURITY: Analysis requires full authentication
    Security Stack: Auth + Authorization + Rate Limit + Validation + Logging + Encryption
    """
    start = time.time()
    
    # Authorization check
    if request.user_tier == 'free':
        log_request(f'/api/analyze/{lottery_type}', request.user_id, 403, 0)
        return jsonify({'error': 'Premium feature required'}), 403
    
    valid_types = ['powerball', 'megamillions', 'superlotto', 'fantasy5']
    if lottery_type not in valid_types:
        log_request(f'/api/analyze/{lottery_type}', request.user_id, 400, 0)
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
    
    duration = (time.time() - start) * 1000
    log_request(f'/api/analyze/{lottery_type}', request.user_id, 200, duration)
    
    response_data = {
        'lottery_type': lottery_type,
        'most_frequent': [{'number': n, 'count': c} for n, c in most_common],
        'total_draws_analyzed': len(rows)
    }
    
    return jsonify(encrypt_response(response_data)), 200

@app.route('/api/predict/<lottery_type>', methods=['POST'])
@rate_limit_all(max_requests=5, window=60)
@require_auth_all
@validate_and_sanitize
def predict_numbers(lottery_type):
    """
    BLANKET SECURITY: Prediction requires full authentication
    Security Stack: Auth + Authorization + Rate Limit + Validation + Logging + Encryption
    """
    start = time.time()
    
    # Authorization
    if request.user_tier == 'free':
        log_request(f'/api/predict/{lottery_type}', request.user_id, 403, 0)
        return jsonify({'error': 'Premium feature required'}), 403
    
    # Validation
    valid_types = ['powerball', 'megamillions', 'superlotto', 'fantasy5']
    if lottery_type not in valid_types:
        log_request(f'/api/predict/{lottery_type}', request.user_id, 400, 0)
        return jsonify({'error': 'Invalid lottery type'}), 400
    
    data = request.get_json()
    num_tickets = data.get('num_tickets', 1)
    
    if not isinstance(num_tickets, int) or num_tickets < 1 or num_tickets > 10:
        log_request(f'/api/predict/{lottery_type}', request.user_id, 400, 0)
        return jsonify({'error': 'num_tickets must be between 1 and 10'}), 400
    
    # SECURITY: Check cache first to prevent computation abuse
    cached_result, is_cached = get_cached_or_compute(lottery_type, num_tickets, request.user_id)

    if is_cached:
        duration = (time.time() - start) * 1000
        log_request(f'/api/predict/{lottery_type}', request.user_id, 200, duration, "Cache hit")

        response_data = {
            'lottery_type': lottery_type,
            'predictions': cached_result,
            'generated_at': datetime.now().isoformat(),
            'computation_time_ms': duration,
            'cached': True
        }
        response_data = convert_numpy(response_data)
        return jsonify(encrypt_response(response_data)), 200

    # Monte Carlo simulation
    predictions = run_monte_carlo_simulation(lottery_type, num_tickets, user_id=request.user_id)

    # SECURITY: Cache the results
    cache_predictions(lottery_type, num_tickets, predictions)
    
    duration = (time.time() - start) * 1000
    log_request(f'/api/predict/{lottery_type}', request.user_id, 200, duration, f"Predictions generated: {num_tickets} tickets")
    
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
    return jsonify(encrypt_response(response_data)), 200

def run_monte_carlo_simulation(lottery_type, num_tickets, user_id=None):
    """Monte Carlo simulation with blanket security overhead"""
    # Simulate additional blanket security check overhead
    time.sleep(0.02)

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
# AUTHENTICATION ENDPOINTS (Also with blanket security)
# ============================================================================

@app.route('/api/register', methods=['POST'])
@rate_limit_all(max_requests=10, window=60)
@validate_and_sanitize
def register():
    """User registration with full security"""
    start = time.time()
    
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        log_request('/api/register', None, 400, 0)
        return jsonify({'error': 'Username and password required'}), 400
    
    if len(password) < 6:
        log_request('/api/register', None, 400, 0)
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
        
        duration = (time.time() - start) * 1000
        log_request('/api/register', user_id, 201, duration)
        
        logger.info(f"User registered: user_id={user_id}, username={username}")
        
        return jsonify(encrypt_response({'message': 'User registered', 'user_id': user_id})), 201
    except sqlite3.IntegrityError:
        conn.close()
        log_request('/api/register', None, 400, 0)
        return jsonify({'error': 'Username exists'}), 400

@app.route('/api/login', methods=['POST'])
@rate_limit_all(max_requests=10, window=60)
@validate_and_sanitize
def login():
    """User login with full security"""
    start = time.time()
    
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, password_hash, tier FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        log_request('/api/login', None, 401, 0)
        return jsonify({'error': 'Invalid credentials'}), 401
    
    if not bcrypt.checkpw(password.encode(), user[1].encode()):
        log_request('/api/login', None, 401, 0)
        return jsonify({'error': 'Invalid credentials'}), 401
    
    token = jwt.encode({
        'user_id': int(user[0]),
        'tier': user[2],
        'exp': datetime.now(timezone.utc) + timedelta(days=7)
    }, app.config['SECRET_KEY'], algorithm='HS256')
    
    duration = (time.time() - start) * 1000
    log_request('/api/login', user[0], 200, duration)
    
    logger.info(f"User logged in: user_id={user[0]}, username={username}, tier={user[2]}")
    
    response_data = {
        'token': token,
        'user_id': int(user[0]),
        'tier': user[2]
    }
    
    return jsonify(encrypt_response(response_data)), 200

if __name__ == '__main__':
    logger.info("Starting Blanket Security API with Full Security Stack (100% coverage)")
    app.run(host='0.0.0.0', port=5002, debug=True)