"""
Realistic sample log data and metrics for AIops demonstrations.

These simulate a typical production incident where an API gateway starts
experiencing errors due to an upstream database connection pool exhaustion.
"""

from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Generate timestamps relative to "now"
# ---------------------------------------------------------------------------
def _ts(minutes_ago: int) -> str:
    t = datetime.now() - timedelta(minutes=minutes_ago)
    return t.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# ---------------------------------------------------------------------------
# SAMPLE_LOGS - 20 realistic log lines showing a degradation incident
# ---------------------------------------------------------------------------
SAMPLE_LOGS = [
    f'{_ts(25)} INFO  api-gateway     [req-4821] GET /api/v2/users 200 OK (45ms)',
    f'{_ts(24)} INFO  auth-service    [auth-9912] Token validated for user_id=8821, scope=read',
    f'{_ts(23)} INFO  api-gateway     [req-4822] POST /api/v2/orders 201 Created (120ms)',
    f'{_ts(22)} INFO  db-pool         [pool-01] Connection pool: 8/50 active connections',
    f'{_ts(21)} INFO  cache-service   [cache-44] Cache HIT ratio: 94.2% (last 5 min)',
    f'{_ts(20)} WARN  db-pool         [pool-01] Connection pool: 38/50 active connections - approaching limit',
    f'{_ts(19)} WARN  api-gateway     [req-4901] GET /api/v2/products 200 OK (892ms) - slow response',
    f'{_ts(18)} WARN  auth-service    [auth-9988] High latency on token validation: 340ms (threshold: 200ms)',
    f'{_ts(17)} ERROR api-gateway     [req-4923] POST /api/v2/orders 500 Internal Server Error - upstream timeout',
    f'{_ts(17)} ERROR db-pool         [pool-01] Connection pool EXHAUSTED: 50/50 connections in use, 12 requests queued',
    f'{_ts(16)} ERROR api-gateway     [req-4924] GET /api/v2/users 503 Service Unavailable - db-pool unresponsive',
    f'{_ts(16)} ERROR api-gateway     [req-4925] GET /api/v2/products 503 Service Unavailable - db-pool unresponsive',
    f'{_ts(15)} ERROR db-pool         [pool-01] SQLException: Connection acquire timeout after 5000ms - com.zaxxer.hikari.pool.HikariPool',
    f'{_ts(15)} WARN  cache-service   [cache-44] Cache MISS spike detected: ratio dropped to 61.3% (last 1 min)',
    f'{_ts(14)} ERROR auth-service    [auth-0012] Database lookup failed: Unable to acquire connection from pool within 5s',
    f'{_ts(14)} ERROR api-gateway     [req-4980] POST /api/v2/auth/login 500 Internal Server Error - auth-service failure',
    f'{_ts(13)} WARN  db-pool         [pool-01] Long-running query detected: SELECT * FROM orders WHERE status=\'pending\' (>30s)',
    f'{_ts(12)} ERROR api-gateway     [req-5001] GET /api/v2/health 500 Internal Server Error - multiple upstream failures',
    f'{_ts(11)} WARN  cache-service   [cache-44] Memory usage at 87% - eviction rate increasing',
    f'{_ts(10)} ERROR db-pool         [pool-01] CRITICAL: 28 queries queued, p99 latency=12400ms, connection leak suspected in service: order-processor',
]

# ---------------------------------------------------------------------------
# SAMPLE_METRICS - 10 time-point snapshots showing degradation pattern
# Each list index = 1 time window (oldest → newest)
# ---------------------------------------------------------------------------
SAMPLE_METRICS = {
    "timestamps": [_ts(25 - i * 2) for i in range(10)],
    "cpu_usage": [42.1, 44.3, 46.8, 51.2, 58.9, 67.4, 79.1, 88.3, 92.7, 94.1],          # % - rising
    "memory_usage": [61.2, 62.0, 63.1, 65.4, 68.9, 72.3, 78.8, 83.2, 87.1, 89.4],       # % - rising
    "request_rate": [1240, 1265, 1288, 1301, 1289, 1102, 834, 612, 498, 445],             # req/min - dropping
    "error_rate": [0.12, 0.15, 0.18, 0.21, 2.40, 8.72, 21.34, 38.91, 52.10, 61.43],      # % - spiking
    "latency_p99": [120, 135, 148, 210, 892, 2341, 5892, 9210, 11430, 12400],             # ms - exploding
    "db_connections_active": [8, 12, 19, 28, 38, 50, 50, 50, 50, 50],                     # of 50 max
    "cache_hit_ratio": [94.2, 93.8, 93.1, 91.2, 88.4, 78.2, 65.3, 61.3, 58.9, 55.1],    # % - dropping
    "queue_depth": [0, 0, 0, 2, 5, 12, 18, 23, 26, 28],                                   # waiting requests
}

# ---------------------------------------------------------------------------
# SAMPLE_ALERT - a raw alert string for triage demos
# ---------------------------------------------------------------------------
SAMPLE_ALERT = """
ALERT: api-gateway error rate exceeded threshold
Time: {ts}
Service: api-gateway
Error rate: 61.4% (threshold: 5%)
Affected endpoints: /api/v2/users, /api/v2/orders, /api/v2/products
Error type: 503 Service Unavailable, 500 Internal Server Error
Duration: 15 minutes
Impact: ~800 requests/min affected (down from 1300 req/min baseline)
Region: us-east-1
Environment: production
""".format(ts=_ts(10))
