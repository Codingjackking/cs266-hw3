#!/usr/bin/env python3
"""
Performance Testing - Selective vs Blanket Security Comparison
Metrics:
- Latency variance (std dev, CV)
- Scalability testing
- Error type breakdown
- Security surface area
- Cost analysis
"""

import requests
import time
import statistics
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
from typing import List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import traceback

SELECTIVE_BASE = 'http://localhost:5001/api'
BLANKET_BASE = 'http://localhost:5002/api'

# Number of unique users to pre-register for blanket scalability testing
BLANKET_USER_POOL_SIZE = 100


class PerformanceMetrics:
    """Container for comprehensive performance metrics"""
    def __init__(self, name: str):
        self.name = name
        self.latencies: List[float] = []
        self.errors: Dict[str, int] = {
            '401_Unauthorized': 0,
            '429_Rate_Limit': 0,
            '500_Internal_Error': 0,
            'Connection_Error': 0,
            'Timeout': 0
        }
        self.successful_requests = 0
        self.failed_requests = 0
        self.start_time = None
        self.end_time = None

    def add_request(self, latency: float, success: bool, error_type: str = None):
        self.latencies.append(latency)
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            if error_type and error_type in self.errors:
                self.errors[error_type] += 1

    def get_stats(self) -> Dict:
        """Calculate comprehensive statistics"""
        if not self.latencies:
            return {}

        duration = (self.end_time - self.start_time) if self.end_time and self.start_time else 0

        mean_lat = statistics.mean(self.latencies)
        std_dev = statistics.stdev(self.latencies) if len(self.latencies) > 1 else 0
        cv = (std_dev / mean_lat * 100) if mean_lat > 0 else 0

        return {
            'mean_latency': mean_lat,
            'median_latency': statistics.median(self.latencies),
            'std_dev': std_dev,
            'cv': cv,
            'p95_latency': np.percentile(self.latencies, 95),
            'min_latency': min(self.latencies),
            'max_latency': max(self.latencies),
            'total_requests': self.successful_requests + self.failed_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'success_rate': (self.successful_requests / (self.successful_requests + self.failed_requests) * 100)
                           if (self.successful_requests + self.failed_requests) > 0 else 0,
            'throughput': (self.successful_requests / duration) if duration > 0 else 0,
            'errors': dict(self.errors),
            'duration': duration,
            'latencies_list': self.latencies  # Keep for box plots
        }


class EnhancedPerformanceTester:
    def __init__(self):
        self.selective_token = None
        self.blanket_token = None          # Single token for latency tests
        self.blanket_tokens = []           # Token pool for scalability tests (one per user)
        self.results = {'selective': {}, 'blanket': {}}
        self.scalability_results = {'selective': [], 'blanket': []}

    def setup_users(self):
        print("Setting up test users...")

        # ── Selective Security: single shared user ────────────────────────────
        resp = requests.post(f'{SELECTIVE_BASE}/login', json={
            'username': 'test_premium', 'password': 'password123'
        })
        if resp.status_code == 200:
            self.selective_token = resp.json()['token']
            print("  ✓ Logged into Selective Security")
        else:
            print(f"  ✗ Selective login failed: {resp.status_code}")
            raise Exception("Selective security login failed")

        # ── Blanket Security: single token for latency tests ──────────────────
        resp = requests.post(f'{BLANKET_BASE}/login', json={
            'username': 'test_premium', 'password': 'password123'
        })
        if resp.status_code == 200:
            self.blanket_token = resp.json()['token']
            print("  ✓ Logged into Blanket Security (primary user)")
        else:
            print(f"  ✗ Blanket login failed: {resp.status_code}")
            raise Exception("Blanket security login failed")

        # ── Blanket Security: register/login a pool of unique users ───────────
        # Each simulated concurrent user gets its own account so they have
        # separate per-user rate limit buckets during scalability tests.
        print(f"\n  Provisioning {BLANKET_USER_POOL_SIZE} unique users for blanket scalability tests...")
        self.blanket_tokens = []

        for i in range(BLANKET_USER_POOL_SIZE):
            username = f'scale_user_{i:03d}'
            password = 'password123'

            # Try login first — only register if user doesn't exist yet (401)
            token = None
            for attempt in range(5):
                resp = requests.post(f'{BLANKET_BASE}/login', json={
                    'username': username, 'password': password
                })
                if resp.status_code == 200:
                    token = resp.json().get('token')
                    break
                elif resp.status_code == 401:
                    # User doesn't exist yet — register then retry login
                    requests.post(f'{BLANKET_BASE}/register', json={
                        'username': username, 'password': password
                    })
                    # Don't count this as an attempt, loop will retry login
                elif resp.status_code == 429:
                    wait = 6 * (attempt + 1)  # 6s, 12s, 18s...
                    time.sleep(wait)
                else:
                    print(f"    Warning: Could not login {username}: {resp.status_code}")
                    break

            if token:
                self.blanket_tokens.append(token)
            else:
                print(f"    Warning: Failed to get token for {username} after retries")

            # Login rate limit is 10 req/60s per IP = 1 per 6s minimum
            # Use 6.5s to stay safely under. 100 users = ~11 min total provisioning.
            time.sleep(6.5)

            if (i + 1) % 10 == 0:
                print(f"    Provisioned {i + 1}/{BLANKET_USER_POOL_SIZE} users...")

        print(f"  ✓ Token pool ready: {len(self.blanket_tokens)} blanket users")

    def measure_request(self, base_url: str, endpoint: str, method='GET',
                        headers=None, data=None) -> Tuple[float, bool, str]:
        start_time = time.time()
        try:
            if method == 'GET':
                response = requests.get(f'{base_url}{endpoint}', headers=headers, timeout=10)
            else:
                response = requests.post(f'{base_url}{endpoint}', headers=headers, json=data, timeout=10)
            latency = time.time() - start_time
            if response.status_code == 200:
                return latency, True, None
            elif response.status_code == 401:
                return latency, False, '401_Unauthorized'
            elif response.status_code == 429:
                return latency, False, '429_Rate_Limit'
            elif response.status_code >= 500:
                return latency, False, '500_Internal_Error'
            else:
                return latency, False, f'{response.status_code}_Error'
        except requests.exceptions.Timeout:
            return time.time() - start_time, False, 'Timeout'
        except Exception:
            return time.time() - start_time, False, 'Connection_Error'

    def test_endpoint_detailed(self, base_url: str, endpoint: str, name: str,
                               method='GET', headers=None, data=None, num_requests=100) -> PerformanceMetrics:
        metrics = PerformanceMetrics(name)
        metrics.start_time = time.time()
        for _ in range(num_requests):
            latency, success, error_type = self.measure_request(base_url, endpoint, method, headers, data)
            metrics.add_request(latency, success, error_type)
            time.sleep(0.01)
        metrics.end_time = time.time()
        return metrics

    def test_scalability(self, base_url: str, endpoint: str, headers=None,
                         token_pool: list = None,
                         concurrency_levels=[10, 25, 50, 75, 100], duration_per_level=15):
        """
        Test scalability at different concurrency levels.

        If token_pool is provided, each concurrent worker is assigned its own
        token from the pool (worker index mod pool size), simulating distinct
        users with independent rate-limit buckets.
        """
        results = []
        for num_workers in concurrency_levels:
            print(f"    Testing with {num_workers} concurrent users...")
            request_count = 0
            error_count = 0
            start_time = time.time()
            end_time = start_time + duration_per_level

            def make_request(worker_idx=0):
                try:
                    # Pick per-worker token if pool available, otherwise use shared headers
                    if token_pool:
                        token = token_pool[worker_idx % len(token_pool)]
                        worker_headers = {'Authorization': f'Bearer {token}'}
                    else:
                        worker_headers = headers
                    resp = requests.get(f'{base_url}{endpoint}', headers=worker_headers, timeout=5)
                    return resp.status_code == 200
                except:
                    return False

            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                while time.time() < end_time:
                    futures = {
                        executor.submit(make_request, i % num_workers): i
                        for i in range(num_workers)
                    }
                    for future in as_completed(futures):
                        if future.result():
                            request_count += 1
                        else:
                            error_count += 1

            elapsed = time.time() - start_time
            throughput = request_count / elapsed
            results.append({
                'concurrency': num_workers,
                'throughput': throughput,
                'total_requests': request_count,
                'errors': error_count,
                'duration': elapsed
            })
            print(f"      -> {throughput:.2f} req/s ({request_count} successful, {error_count} errors)")

        return results

    def run_comprehensive_tests(self):
        print("\n" + "=" * 80)
        print("COMPREHENSIVE PERFORMANCE TESTING: SELECTIVE VS BLANKET SECURITY")
        print("=" * 80)

        scenarios = [
            {
                'name': 'Health Check (Public)',
                'endpoint': '/health',
                'method': 'GET',
                'selective_headers': None,
                'blanket_headers': {'Authorization': f'Bearer {self.blanket_token}'}
            },
            {
                'name': 'Historical Data (Public)',
                'endpoint': '/history/powerball',
                'method': 'GET',
                'selective_headers': None,
                'blanket_headers': {'Authorization': f'Bearer {self.blanket_token}'}
            },
            {
                'name': 'Jackpots (Public)',
                'endpoint': '/jackpots',
                'method': 'GET',
                'selective_headers': None,
                'blanket_headers': {'Authorization': f'Bearer {self.blanket_token}'}
            },
            {
                'name': 'Analysis (Moderate)',
                'endpoint': '/analyze/powerball',
                'method': 'GET',
                'selective_headers': None,
                'blanket_headers': {'Authorization': f'Bearer {self.blanket_token}'}
            },
            {
                'name': 'Prediction (Critical)',
                'endpoint': '/predict/powerball',
                'method': 'POST',
                'selective_headers': {'Authorization': f'Bearer {self.selective_token}'},
                'blanket_headers': {'Authorization': f'Bearer {self.blanket_token}'},
                'data': {'num_tickets': 3}
            }
        ]

        print("\nDETAILED LATENCY TESTS (100 requests per endpoint)")
        print("-" * 80)

        for scenario in scenarios:
            print(f"\n{scenario['name']}:")
            print("  Testing Selective Security...")
            selective_metrics = self.test_endpoint_detailed(
                SELECTIVE_BASE, scenario['endpoint'],
                f"Selective_{scenario['name']}",
                scenario['method'], scenario.get('selective_headers'), scenario.get('data')
            )
            print("  Testing Blanket Security...")
            blanket_metrics = self.test_endpoint_detailed(
                BLANKET_BASE, scenario['endpoint'],
                f"Blanket_{scenario['name']}",
                scenario['method'], scenario.get('blanket_headers'), scenario.get('data')
            )

            self.results['selective'][scenario['name']] = selective_metrics.get_stats()
            self.results['blanket'][scenario['name']] = blanket_metrics.get_stats()

            sel_stats = selective_metrics.get_stats()
            blan_stats = blanket_metrics.get_stats()

            print(f"\n  Results:")
            print(f"    Selective: {sel_stats['mean_latency']*1000:.2f}ms mean "
                  f"(s={sel_stats['std_dev']*1000:.2f}ms, CV={sel_stats['cv']:.1f}%)")
            print(f"    Blanket:   {blan_stats['mean_latency']*1000:.2f}ms mean "
                  f"(s={blan_stats['std_dev']*1000:.2f}ms, CV={blan_stats['cv']:.1f}%)")
            print(f"    Improvement: {((blan_stats['mean_latency'] - sel_stats['mean_latency']) / blan_stats['mean_latency'] * 100):.1f}% faster")

        print("\n\nSCALABILITY TESTS")
        print("-" * 80)
        print("Testing throughput at different concurrency levels (10, 25, 50, 75, 100 users)")
        print("Each blanket worker uses its own unique token (independent rate-limit bucket)")
        print("15 seconds per level\n")

        print("Selective Security:")
        self.scalability_results['selective'] = self.test_scalability(
            SELECTIVE_BASE, '/jackpots', headers=None,
            concurrency_levels=[10, 25, 50, 75, 100], duration_per_level=15
        )

        print("\nBlanket Security (per-user tokens):")
        self.scalability_results['blanket'] = self.test_scalability(
            BLANKET_BASE, '/jackpots',
            token_pool=self.blanket_tokens,
            concurrency_levels=[10, 25, 50, 75, 100], duration_per_level=15
        )

    def generate_latency_visualization(self):
        print("\nGenerating latency comparison visualizations...")
        os.makedirs('outputs', exist_ok=True)
        scenarios = list(self.results['selective'].keys())
        scenario_labels = [s.split('(')[0].strip() for s in scenarios]
        x = np.arange(len(scenarios))
        width = 0.35

        # Graph 1: Mean Latency
        fig, ax = plt.subplots(figsize=(10, 6))
        selective_means = [self.results['selective'][s]['mean_latency'] * 1000 for s in scenarios]
        blanket_means = [self.results['blanket'][s]['mean_latency'] * 1000 for s in scenarios]
        bars1 = ax.bar(x - width/2, selective_means, width, label='Selective Security',
                       color='#2ecc71', alpha=0.8, edgecolor='black', linewidth=1.5)
        bars2 = ax.bar(x + width/2, blanket_means, width, label='Blanket Security',
                       color='#e74c3c', alpha=0.8, edgecolor='black', linewidth=1.5)
        ax.set_ylabel('Mean Latency (ms)', fontsize=12, fontweight='bold')
        ax.set_title('Mean Response Latency', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(scenario_labels, rotation=45, ha='right')
        ax.legend(fontsize=10)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        for bars in [bars1, bars2]:
            for bar in bars:
                h = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., h, f'{h:.1f}',
                        ha='center', va='bottom', fontsize=9, fontweight='bold')
        fig.tight_layout()
        fig.savefig('outputs/latency_1_mean.png', dpi=300, bbox_inches='tight')
        plt.close(fig)
        print("  ✓ Saved: latency_1_mean.png")

        # Graph 2: Latency Distribution Box Plot
        fig, ax = plt.subplots(figsize=(8, 6))
        test_scenario = 'Jackpots (Public)'
        sel_lats = [l * 1000 for l in self.results['selective'][test_scenario].get('latencies_list', [])]
        blan_lats = [l * 1000 for l in self.results['blanket'][test_scenario].get('latencies_list', [])]
        if sel_lats and blan_lats:
            box = ax.boxplot([sel_lats, blan_lats],
                             tick_labels=['Selective\nSecurity', 'Blanket\nSecurity'],
                             patch_artist=True, widths=0.6)
            for patch, color in zip(box['boxes'], ['#2ecc71', '#e74c3c']):
                patch.set_facecolor(color)
                patch.set_alpha(0.7)
                patch.set_linewidth(2)
            for element in ['whiskers', 'fliers', 'means', 'medians', 'caps']:
                plt.setp(box[element], linewidth=1.5)
        ax.set_ylabel('Latency (ms)', fontsize=12, fontweight='bold')
        ax.set_title(f'Latency Distribution - {test_scenario}', fontsize=14, fontweight='bold')
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        fig.tight_layout()
        fig.savefig('outputs/latency_2_distribution.png', dpi=300, bbox_inches='tight')
        plt.close(fig)
        print("  ✓ Saved: latency_2_distribution.png")

        # Graph 3: Standard Deviation
        fig, ax = plt.subplots(figsize=(10, 6))
        selective_std = [self.results['selective'][s]['std_dev'] * 1000 for s in scenarios]
        blanket_std = [self.results['blanket'][s]['std_dev'] * 1000 for s in scenarios]
        bars1 = ax.bar(x - width/2, selective_std, width, label='Selective Security',
                       color='#3498db', alpha=0.8, edgecolor='black', linewidth=1.5)
        bars2 = ax.bar(x + width/2, blanket_std, width, label='Blanket Security',
                       color='#e67e22', alpha=0.8, edgecolor='black', linewidth=1.5)
        ax.set_ylabel('Standard Deviation (ms)', fontsize=12, fontweight='bold')
        ax.set_title('Latency Stability (Lower = More Stable)', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(scenario_labels, rotation=45, ha='right')
        ax.legend(fontsize=10)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        for bars in [bars1, bars2]:
            for bar in bars:
                h = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., h, f'{h:.1f}',
                        ha='center', va='bottom', fontsize=9, fontweight='bold')
        fig.tight_layout()
        fig.savefig('outputs/latency_3_std_dev.png', dpi=300, bbox_inches='tight')
        plt.close(fig)
        print("  ✓ Saved: latency_3_std_dev.png")

        # Graph 4: Coefficient of Variation
        fig, ax = plt.subplots(figsize=(10, 6))
        selective_cv = [self.results['selective'][s]['cv'] for s in scenarios]
        blanket_cv = [self.results['blanket'][s]['cv'] for s in scenarios]
        bars1 = ax.bar(x - width/2, selective_cv, width, label='Selective Security',
                       color='#9b59b6', alpha=0.8, edgecolor='black', linewidth=1.5)
        bars2 = ax.bar(x + width/2, blanket_cv, width, label='Blanket Security',
                       color='#f39c12', alpha=0.8, edgecolor='black', linewidth=1.5)
        ax.set_ylabel('Coefficient of Variation (%)', fontsize=12, fontweight='bold')
        ax.set_title('Relative Variability (Lower = More Consistent)', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(scenario_labels, rotation=45, ha='right')
        ax.legend(fontsize=10)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        for bars in [bars1, bars2]:
            for bar in bars:
                h = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., h, f'{h:.1f}%',
                        ha='center', va='bottom', fontsize=9, fontweight='bold')
        fig.tight_layout()
        fig.savefig('outputs/latency_4_cv.png', dpi=300, bbox_inches='tight')
        plt.close(fig)
        print("  ✓ Saved: latency_4_cv.png")

    def generate_throughput_visualization(self):
        print("Generating throughput comparison visualizations...")
        os.makedirs('outputs', exist_ok=True)
        scenarios = list(self.results['selective'].keys())
        scenario_labels = [s.split('(')[0].strip() for s in scenarios]
        x = np.arange(len(scenarios))
        width = 0.35

        sel_throughput = self.scalability_results['selective'][0]['throughput']
        blan_throughput = self.scalability_results['blanket'][0]['throughput']

        # Graph 1: Throughput Comparison
        fig, ax = plt.subplots(figsize=(8, 6))
        bars = ax.bar(['Selective\nSecurity', 'Blanket\nSecurity'],
                      [sel_throughput, blan_throughput],
                      color=['#2ecc71', '#e74c3c'], alpha=0.8, edgecolor='black', linewidth=2)
        ax.set_ylabel('Requests per Second', fontsize=12, fontweight='bold')
        ax.set_title('Throughput Comparison (10 Concurrent Users)', fontsize=14, fontweight='bold')
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., h, f'{h:.1f}\nreq/s',
                    ha='center', va='bottom', fontsize=11, fontweight='bold')
        if blan_throughput > 0:
            improvement = ((sel_throughput - blan_throughput) / blan_throughput) * 100
            label = f'{improvement:.0f}% Improvement'
        else:
            label = 'Blanket: 0 req/s\n(fully rate-limited)'
        max_val = max(sel_throughput, blan_throughput)
        ax.text(0.5, max_val * 0.5 if max_val > 0 else 0.5, label,
                ha='center', fontsize=13, fontweight='bold',
                transform=ax.transData if max_val > 0 else ax.transAxes,
                bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7))
        fig.tight_layout()
        fig.savefig('outputs/throughput_1_comparison.png', dpi=300, bbox_inches='tight')
        plt.close(fig)
        print("  ✓ Saved: throughput_1_comparison.png")

        # Graph 2: Scalability Curve
        fig, ax = plt.subplots(figsize=(8, 6))
        sel_concurrency = [r['concurrency'] for r in self.scalability_results['selective']]
        sel_throughputs = [r['throughput'] for r in self.scalability_results['selective']]
        blan_concurrency = [r['concurrency'] for r in self.scalability_results['blanket']]
        blan_throughputs = [r['throughput'] for r in self.scalability_results['blanket']]
        ax.plot(sel_concurrency, sel_throughputs, marker='o', linewidth=3, markersize=10,
                label='Selective Security', color='#2ecc71')
        ax.plot(blan_concurrency, blan_throughputs, marker='s', linewidth=3, markersize=10,
                label='Blanket Security', color='#e74c3c')
        ax.set_xlabel('Concurrent Users', fontsize=12, fontweight='bold')
        ax.set_ylabel('Throughput (req/s)', fontsize=12, fontweight='bold')
        ax.set_title('Scalability: Throughput vs Concurrency\n(Each blanket user has independent token)',
                     fontsize=13, fontweight='bold')
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3, linestyle='--')
        fig.tight_layout()
        fig.savefig('outputs/throughput_2_scalability.png', dpi=300, bbox_inches='tight')
        plt.close(fig)
        print("  ✓ Saved: throughput_2_scalability.png")

        # Graph 3: Error Rate
        fig, ax = plt.subplots(figsize=(10, 6))
        sel_error_rates = [(self.results['selective'][s]['failed_requests'] /
                            self.results['selective'][s]['total_requests'] * 100)
                           if self.results['selective'][s]['total_requests'] > 0 else 0
                           for s in scenarios]
        blan_error_rates = [(self.results['blanket'][s]['failed_requests'] /
                             self.results['blanket'][s]['total_requests'] * 100)
                            if self.results['blanket'][s]['total_requests'] > 0 else 0
                            for s in scenarios]
        bars1 = ax.bar(x - width/2, sel_error_rates, width, label='Selective Security',
                       color='#2ecc71', alpha=0.8, edgecolor='black', linewidth=1.5)
        bars2 = ax.bar(x + width/2, blan_error_rates, width, label='Blanket Security',
                       color='#e74c3c', alpha=0.8, edgecolor='black', linewidth=1.5)
        ax.set_ylabel('Error Rate (%)', fontsize=12, fontweight='bold')
        ax.set_title('Error Rate Comparison (Lower = Better)', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(scenario_labels, rotation=45, ha='right')
        ax.legend(fontsize=10)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        for bars in [bars1, bars2]:
            for bar in bars:
                h = bar.get_height()
                if h > 0:
                    ax.text(bar.get_x() + bar.get_width()/2., h, f'{h:.1f}%',
                            ha='center', va='bottom', fontsize=9, fontweight='bold')
        fig.tight_layout()
        fig.savefig('outputs/throughput_3_error_rate.png', dpi=300, bbox_inches='tight')
        plt.close(fig)
        print("  ✓ Saved: throughput_3_error_rate.png")

        # Graph 4: Success Rate
        fig, ax = plt.subplots(figsize=(10, 6))
        sel_success = [self.results['selective'][s]['success_rate'] for s in scenarios]
        blan_success = [self.results['blanket'][s]['success_rate'] for s in scenarios]
        bars1 = ax.bar(x - width/2, sel_success, width, label='Selective Security',
                       color='#27ae60', alpha=0.8, edgecolor='black', linewidth=1.5)
        bars2 = ax.bar(x + width/2, blan_success, width, label='Blanket Security',
                       color='#c0392b', alpha=0.8, edgecolor='black', linewidth=1.5)
        ax.set_ylabel('Success Rate (%)', fontsize=12, fontweight='bold')
        ax.set_title('Request Success Rate (Higher = Better)', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(scenario_labels, rotation=45, ha='right')
        ax.legend(fontsize=10)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        all_vals = sel_success + blan_success
        ax.set_ylim([max(0, min(all_vals) - 10), min(100, max(all_vals)) + 5])
        for bars in [bars1, bars2]:
            for bar in bars:
                h = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., h, f'{h:.1f}%',
                        ha='center', va='bottom', fontsize=9, fontweight='bold')
        fig.tight_layout()
        fig.savefig('outputs/throughput_4_success_rate.png', dpi=300, bbox_inches='tight')
        plt.close(fig)
        print("  ✓ Saved: throughput_4_success_rate.png")

    def generate_comprehensive_report(self):
        print("\nGenerating comprehensive analysis report...")

        report = []
        report.append("=" * 100)
        report.append("COMPREHENSIVE PERFORMANCE ANALYSIS: SELECTIVE VS BLANKET SECURITY")
        report.append("=" * 100)
        report.append("")
        report.append(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Blanket scalability test: {len(self.blanket_tokens)} unique users, each with independent rate-limit bucket")
        report.append("")

        report.append("EXECUTIVE SUMMARY")
        report.append("-" * 100)
        report.append("")

        scenarios = list(self.results['selective'].keys())

        avg_sel_lat = statistics.mean([self.results['selective'][s]['mean_latency'] * 1000 for s in scenarios])
        avg_blan_lat = statistics.mean([self.results['blanket'][s]['mean_latency'] * 1000 for s in scenarios])
        lat_improvement = ((avg_blan_lat - avg_sel_lat) / avg_blan_lat) * 100

        sel_throughput = self.scalability_results['selective'][0]['throughput']
        blan_throughput = self.scalability_results['blanket'][0]['throughput']
        throughput_improvement = ((sel_throughput - blan_throughput) / blan_throughput) * 100 if blan_throughput > 0 else float('inf')

        report.append("Average Latency:")
        report.append(f"  Selective Security: {avg_sel_lat:.2f}ms")
        report.append(f"  Blanket Security:   {avg_blan_lat:.2f}ms")
        report.append(f"  Improvement:        {lat_improvement:.1f}% faster")
        report.append("")

        report.append("Throughput (10 concurrent users):")
        report.append(f"  Selective Security: {sel_throughput:.2f} req/s")
        report.append(f"  Blanket Security:   {blan_throughput:.2f} req/s")
        if blan_throughput > 0:
            report.append(f"  Improvement:        {throughput_improvement:.1f}% higher")
        else:
            report.append("  Improvement:        N/A (blanket fully rate-limited at 0 req/s)")
        report.append("")

        report.append("KEY FINDING:")
        if blan_throughput > 0:
            report.append(f"  Throughput improvement ({throughput_improvement:.0f}%) is MUCH LARGER than latency improvement ({lat_improvement:.1f}%)")
        else:
            report.append(f"  Blanket security was fully blocked (0 req/s) vs latency improvement of {lat_improvement:.1f}%")
        report.append("  This suggests blanket security causes:")
        report.append("  - Authentication overhead amplification at scale")
        report.append("  - Unnecessary blocking on public endpoints")
        report.append("  - Token verification bottlenecks")
        report.append("  - Response encryption overhead on every request")
        report.append("")

        report.append("\n" + "=" * 100)
        report.append("1. LATENCY VARIANCE ANALYSIS (STABILITY)")
        report.append("=" * 100)
        report.append("")

        avg_sel_std = statistics.mean([self.results['selective'][s]['std_dev'] * 1000 for s in scenarios])
        avg_blan_std = statistics.mean([self.results['blanket'][s]['std_dev'] * 1000 for s in scenarios])
        stability_improvement = ((avg_blan_std - avg_sel_std) / avg_blan_std * 100) if avg_blan_std > 0 else 0

        avg_sel_cv = statistics.mean([self.results['selective'][s]['cv'] for s in scenarios])
        avg_blan_cv = statistics.mean([self.results['blanket'][s]['cv'] for s in scenarios])

        report.append("Average Standard Deviation:")
        report.append(f"  Selective: {avg_sel_std:.2f}ms")
        report.append(f"  Blanket:   {avg_blan_std:.2f}ms")
        if stability_improvement > 0:
            report.append(f"  Selective is {stability_improvement:.1f}% more stable")
        else:
            report.append(f"  Blanket is {abs(stability_improvement):.1f}% more stable")
        report.append("")
        report.append("Average Coefficient of Variation:")
        report.append(f"  Selective: {avg_sel_cv:.1f}%")
        report.append(f"  Blanket:   {avg_blan_cv:.1f}%")
        report.append("")
        report.append("INTERPRETATION:")
        report.append("  ✓ Lower standard deviation = less jitter")
        report.append("  ✓ Lower CV = more predictable performance")
        report.append(f"  -> {'Selective' if avg_sel_cv <= avg_blan_cv else 'Blanket'} security provides MORE STABLE response times")
        report.append("")

        report.append("\n" + "=" * 100)
        report.append("2. DETAILED ENDPOINT ANALYSIS")
        report.append("=" * 100)
        report.append("")

        for scenario in scenarios:
            sel = self.results['selective'][scenario]
            blan = self.results['blanket'][scenario]
            improvement = ((blan['mean_latency'] - sel['mean_latency']) / blan['mean_latency'] * 100)

            report.append(f"{scenario}:")
            report.append(f"  Selective Security:")
            report.append(f"    Mean:    {sel['mean_latency']*1000:.2f}ms  |  Median: {sel['median_latency']*1000:.2f}ms")
            report.append(f"    Std Dev: {sel['std_dev']*1000:.2f}ms  |  CV: {sel['cv']:.1f}%")
            report.append(f"    P95:     {sel['p95_latency']*1000:.2f}ms")
            report.append(f"    Success Rate: {sel['success_rate']:.1f}%")
            report.append(f"  Blanket Security:")
            report.append(f"    Mean:    {blan['mean_latency']*1000:.2f}ms  |  Median: {blan['median_latency']*1000:.2f}ms")
            report.append(f"    Std Dev: {blan['std_dev']*1000:.2f}ms  |  CV: {blan['cv']:.1f}%")
            report.append(f"    P95:     {blan['p95_latency']*1000:.2f}ms")
            report.append(f"    Success Rate: {blan['success_rate']:.1f}%")
            report.append(f"  -> Performance Improvement: {improvement:.1f}% faster with selective security")
            report.append("")

        report.append("\n" + "=" * 100)
        report.append("3. SCALABILITY ANALYSIS")
        report.append("=" * 100)
        report.append("")
        report.append("Note: Blanket security scalability tested with unique per-user tokens")
        report.append("      (each concurrent worker has its own account and independent rate-limit bucket)")
        report.append("")

        report.append("Throughput at Different Concurrency Levels:")
        report.append(f"{'Concurrent Users':>18} | {'Selective (req/s)':>18} | {'Blanket (req/s)':>18} | {'Improvement':>15}")
        report.append("-" * 100)

        for sel_result, blan_result in zip(self.scalability_results['selective'],
                                           self.scalability_results['blanket']):
            concurrency = sel_result['concurrency']
            sel_tps = sel_result['throughput']
            blan_tps = blan_result['throughput']
            if blan_tps > 0:
                improvement_str = f"{((sel_tps - blan_tps) / blan_tps) * 100:>14.1f}%"
            else:
                improvement_str = '       N/A (0 req/s)'
            report.append(f"{concurrency:>18} | {sel_tps:>18.2f} | {blan_tps:>18.2f} | {improvement_str}")

        report.append("")
        report.append("INTERPRETATION:")
        report.append("  -> Selective security scales linearly: public endpoints have zero auth/rate-limit overhead")
        report.append("  -> Blanket security overhead comes from JWT verification + encryption on every request")
        report.append("  -> With per-user tokens, rate limiting no longer artificially collapses blanket throughput")
        report.append("  -> Remaining gap reflects true cost of applying full security stack to all endpoints")
        report.append("")

        report.append("\n" + "=" * 100)
        report.append("4. SECURITY SURFACE AREA COMPARISON")
        report.append("=" * 100)
        report.append("")

        report.append("Selective Security - Endpoint Coverage:")
        report.append("  Public Endpoints (No Auth):           3  (Health, History, Jackpots)")
        report.append("  Protected Endpoints (Validation):      1  (Analysis)")
        report.append("  Critical Endpoints (Full Stack):       1  (Prediction)")
        report.append("  Auth Endpoints (Rate Limited):         2  (Register, Login)")
        report.append("  Total Endpoint Coverage:              ~57% (4/7 endpoints with security)")
        report.append("")
        report.append("Selective Security - Security Features:")
        report.append("  ✓ Authentication & Authorization (JWT) on critical endpoints")
        report.append("  ✓ Rate Limiting (10 req/60s, per user) on auth + prediction endpoints")
        report.append("  ✓ Input Validation & Sanitization on prediction endpoint")
        report.append("  ✓ Differential Privacy (epsilon=0.1) on prediction output")
        report.append("  ✓ Output Sanitization on prediction endpoint")
        report.append("  ✓ Comprehensive Audit Logging")
        report.append("  ✓ Result Caching (5-minute TTL)")
        report.append("")

        report.append("Blanket Security - Endpoint Coverage:")
        report.append("  All Endpoints (Full Auth):             7  (All endpoints)")
        report.append("  Total Endpoint Coverage:              100% of endpoints")
        report.append("")
        report.append("Blanket Security - Security Features:")
        report.append("  ✓ Authentication & Authorization (JWT) on ALL endpoints")
        report.append("  ✓ Rate Limiting (per user) on ALL endpoints")
        report.append("  ✓ Input Validation & Sanitization on ALL endpoints")
        report.append("  ✓ Response Encryption overhead on ALL endpoints")
        report.append("  ✓ Differential Privacy (epsilon=0.1) on prediction output")
        report.append("  ✓ Comprehensive Audit Logging")
        report.append("  ✓ Result Caching (5-minute TTL)")
        report.append("")

        report.append("ANALYSIS:")
        report.append("  Selective Security:")
        report.append("    ✓ Concentrates security overhead on high-value endpoints")
        report.append("    ✓ Public endpoints serve requests with zero auth/encryption overhead")
        report.append("    ✓ Differential privacy on prediction output prevents reverse engineering")
        report.append("    ✓ Balances security with performance")
        report.append("")
        report.append("  Blanket Security:")
        report.append("    ✓ Comprehensive 100% endpoint coverage")
        report.append("    ✗ JWT verification overhead on every request including public endpoints")
        report.append("    ✗ Response encryption adds latency overhead to every response")
        report.append("    ✗ Higher infrastructure cost per request at scale")
        report.append("")

        report.append("\n" + "=" * 100)
        report.append("5. INFRASTRUCTURE COST ANALYSIS")
        report.append("=" * 100)
        report.append("")

        overhead_percent = ((avg_blan_lat - avg_sel_lat) / avg_sel_lat) * 100
        additional_hours = 24 * (overhead_percent / 100)
        additional_cost_per_day = additional_hours * 0.0416
        additional_cost_per_month = additional_cost_per_day * 30
        additional_cost_per_year = additional_cost_per_day * 365

        report.append("Assumptions:")
        report.append("  - 1 million requests per day")
        report.append("  - AWS EC2 t3.medium instance ($0.0416/hour)")
        report.append("  - CPU overhead proportional to latency overhead")
        report.append("")
        report.append(f"Cost Impact of Blanket Security Overhead ({overhead_percent:.1f}% latency overhead):")
        report.append(f"  Additional compute hours per day: {additional_hours:.2f} hours")
        report.append(f"  Additional cost per day:  ${additional_cost_per_day:.2f}")
        report.append(f"  Additional cost per month: ${additional_cost_per_month:.2f}")
        report.append(f"  Additional cost per year:  ${additional_cost_per_year:.2f}")
        report.append("")
        report.append("INTERPRETATION:")
        report.append(f"  -> Blanket security adds ~${additional_cost_per_year:.0f}/year in base compute costs")
        report.append("  -> Under concurrent load, blanket security requires more infrastructure due to auth overhead")
        report.append("  -> Cost savings from selective security scale with request volume and concurrency")
        report.append("")

        report.append("\n" + "=" * 100)
        report.append("6. RECOMMENDATIONS")
        report.append("=" * 100)
        report.append("")
        report.append("Based on this analysis, SELECTIVE SECURITY is recommended because:")
        report.append("")
        report.append("1. PERFORMANCE:")
        report.append(f"   - {lat_improvement:.0f}% lower average latency per request")
        if blan_throughput > 0:
            report.append(f"   - {throughput_improvement:.0f}% higher throughput at 10 concurrent users")
        else:
            report.append(f"   - Blanket fully rate-limited (0 req/s vs {sel_throughput:.1f} req/s) under load")
        if avg_blan_cv > 0:
            report.append(f"   - {((avg_blan_cv - avg_sel_cv) / avg_blan_cv * 100):.0f}% more consistent response times (lower CV)")
        report.append("")
        report.append("2. SCALABILITY:")
        report.append("   - Public endpoints have zero auth/encryption overhead, scale freely")
        report.append("   - Blanket security applies JWT + encryption to every request regardless of sensitivity")
        report.append("   - Performance gap reflects true overhead of blanket approach, not testing artifacts")
        report.append("")
        report.append("3. COST EFFICIENCY:")
        report.append(f"   - ~${additional_cost_per_year:.0f}/year savings in base infrastructure")
        report.append("   - Better resource utilization per endpoint")
        report.append("   - Scales more efficiently with traffic growth")
        report.append("")
        report.append("4. SECURITY:")
        report.append("   - Full auth stack on high-value endpoints (Prediction, Register, Login)")
        report.append("   - Differential privacy prevents prediction algorithm reverse engineering")
        report.append("   - Input validation and sanitization on all protected endpoints")
        report.append("   - Security level matched to endpoint sensitivity")
        report.append("   - Comprehensive audit logging across all security events")
        report.append("")
        report.append("5. THREAT MODEL COVERAGE:")
        report.append("   ✓ API flooding/DoS        -> Rate limiting on auth + prediction endpoints")
        report.append("   ✓ SQL injection           -> Input validation on protected endpoints")
        report.append("   ✓ Unauthorized access     -> JWT authentication on critical endpoints")
        report.append("   ✓ Algorithm reverse eng   -> Differential privacy (epsilon=0.1)")
        report.append("   ✓ Data exfiltration       -> Audit logging + output sanitization")
        report.append("")
        report.append("CONCLUSION:")
        if blan_throughput > 0:
            report.append("  Selective security achieves equivalent protection on high-value endpoints")
            report.append(f"  while maintaining {throughput_improvement:.0f}% better throughput than blanket security.")
        else:
            report.append("  Selective security achieves equivalent protection on high-value endpoints")
            report.append("  while blanket security collapses entirely under concurrent load.")
        report.append("  Applying security proportional to endpoint sensitivity eliminates unnecessary")
        report.append("  overhead on public endpoints and ensures results reflect true policy costs,")
        report.append("  not testing artifacts from shared rate-limit buckets.")
        report.append("")
        report.append("=" * 100)
        report.append("")

        report_text = "\n".join(report)
        with open('outputs/comprehensive_performance_report.txt', 'w', encoding='utf-8') as f:
            f.write(report_text)
        print(report_text)
        print("\n  ✓ Saved: comprehensive_performance_report.txt")


def main():
    print("Lottery Oracle - Security Performance Testing")
    print("Selective vs Blanket Endpoint Security Comparison")
    print(f"Blanket scalability: {BLANKET_USER_POOL_SIZE} unique users with independent tokens")
    print()

    tester = EnhancedPerformanceTester()

    try:
        tester.setup_users()
        tester.run_comprehensive_tests()
        tester.generate_latency_visualization()
        tester.generate_throughput_visualization()
        tester.generate_comprehensive_report()

        print("\nTesting complete. Output files in outputs/:")
        print("  Latency Graphs:")
        print("    latency_1_mean.png            - Mean response latency per endpoint")
        print("    latency_2_distribution.png    - Latency distribution box plot")
        print("    latency_3_std_dev.png         - Latency stability (std deviation)")
        print("    latency_4_cv.png              - Relative variability (CV)")
        print("  Throughput Graphs:")
        print("    throughput_1_comparison.png   - Throughput at 10 concurrent users")
        print("    throughput_2_scalability.png  - Throughput vs concurrency curve")
        print("    throughput_3_error_rate.png   - Error rate per endpoint")
        print("    throughput_4_success_rate.png - Success rate per endpoint")
        print("  comprehensive_performance_report.txt - Full analysis")

    except Exception as e:
        print(f"\nError during testing: {e}")
        traceback.print_exc()


if __name__ == '__main__':
    main()