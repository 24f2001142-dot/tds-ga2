import os
import time
import uuid
from pathlib import Path
from collections import defaultdict

import jwt
import yaml
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from collections import deque
from prometheus_client import Counter, generate_latest

START_TIME = time.time()
http_requests_total = Counter("http_requests_total", "Total HTTP Requests")
logs_queue = deque(maxlen=100)
app = FastAPI()

EMAIL = "24f2001142@ds.study.iitm.ac.in"  # <-- put your actual IITM login email here

# ---------- Q1 config ----------
Q1_ALLOWED_ORIGIN = "https://dash-uzy9zp.example.com"

# ---------- Q2 config ----------
ISSUER = "https://idp.exam.local"
AUDIENCE = "tds-1prufq2u.apps.exam.local"
PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA2okOHspNjgA+2rTLbeuY
cxiP/hG8C6Sb9iwg3yiLAA4HCnpITcbWCSelbvbYGuc3EbNy4xFyf5Cbj5DHJMID
EkryOgyd2giIIIBOUBj8S63uGcnRpOBh9NFatfNwheKuzsPuVNldu6A9cNteNpXc
WyJjG2axVfmq7i6SuKr1JoWYG7xTTAvKPujSl4OtsQfO3h5NepzdfXpr28oNnzfW
ed+zclR6BcmNNo/WVfJ4xyCLSf0BCOgdTgW6PdaChd1l9VDetJZVEgC5tkyvXsfI
SI6iyrYbKR0NEBSqq4XkadEjsCs4F1RncsS4LlgniT7GlkL9Mce3b0wGLs9/7ZIX
dQIDAQAB
-----END PUBLIC KEY-----"""

# ---------- Q3 config ----------
APP_ENV = os.environ.get("APP_ENV", "development")

def load_defaults():
    return {
        "port": 8000,
        "workers": 1,
        "debug": False,
        "log_level": "info",
        "api_key": "default-secret-000",
    }

def load_yaml_config():
    path = Path(f"config.{APP_ENV}.yaml")
    if path.exists():
        return yaml.safe_load(path.read_text()) or {}
    return {}

def load_dotenv_config():
    path = Path(".env")
    result = {}
    mapping = {"NUM_WORKERS": "workers", "APP_PORT": "port",
               "APP_DEBUG": "debug", "APP_LOG_LEVEL": "log_level",
               "APP_API_KEY": "api_key"}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            result[mapping.get(k, k.lower())] = v.strip().strip('"').strip("'")
    return result

def load_os_env_config():
    mapping = {"APP_PORT": "port", "APP_WORKERS": "workers",
               "APP_DEBUG": "debug", "APP_LOG_LEVEL": "log_level",
               "APP_API_KEY": "api_key"}
    return {cfg_key: os.environ[env_key]
            for env_key, cfg_key in mapping.items() if env_key in os.environ}

def coerce(key, val):
    if key in ("port", "workers"):
        return int(val)
    if key == "debug":
        return val if isinstance(val, bool) else str(val).strip().lower() in ("true", "1", "yes", "on")
    return str(val)

# ---------- Q5 config ----------
Q5_API_KEY = "ak_ci8b7qisuhacpwro59ycmh08"


# ============ MIDDLEWARE (Q1: CORS + timing headers) ============
@app.middleware("http")
async def add_headers_and_cors(request: Request, call_next):
    start = time.time()
    req_id = str(uuid.uuid4())
    origin = request.headers.get("origin")
    path = request.url.path.rstrip("/")
    if path == "":
        path = "/"

    http_requests_total.inc()
    logs_queue.append({
        "level": "INFO",
        "ts": time.time(),
        "path": request.url.path,
        "request_id": req_id,
    })

    if request.method == "OPTIONS":
        response = Response(status_code=204)
    else:
        response = await call_next(request)

    if origin:
        if path == "/stats":
            if origin == Q1_ALLOWED_ORIGIN:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = "*"
        else:
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "*"

    response.headers["X-Request-ID"] = req_id
    response.headers["X-Process-Time"] = f"{time.time() - start:.6f}"
    return response


# ============ Q1: /stats ============
@app.get("/stats")
async def stats(values: str = ""):
    try:
        nums = [int(x.strip()) for x in values.split(",") if x.strip() != ""]
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "invalid values"})

    if not nums:
        return JSONResponse(status_code=400, content={"error": "no values provided"})

    return {
        "email": EMAIL,
        "count": len(nums),
        "sum": sum(nums),
        "min": min(nums),
        "max": max(nums),
        "mean": round(sum(nums) / len(nums), 6),
    }


# ============ Q2: /verify ============
@app.post("/verify")
async def verify_token(request: Request):
    try:
        body = await request.json()
        token = body.get("token")
        claims = jwt.decode(
            token,
            PUBLIC_KEY_PEM,
            algorithms=["RS256"],
            issuer=ISSUER,
            audience=AUDIENCE,
        )
        return {
            "valid": True,
            "email": claims.get("email", ""),
            "sub": claims.get("sub", ""),
            "aud": claims.get("aud", ""),
        }
    except Exception:
        return JSONResponse(status_code=401, content={"valid": False})


# ============ Q3: /effective-config ============
@app.get("/effective-config")
async def effective_config(request: Request):
    cfg = {}
    for loader in (load_defaults, load_yaml_config, load_dotenv_config, load_os_env_config):
        cfg.update(loader())

    for key, value in request.query_params.multi_items():
        if key == "set" and "=" in value:
            k, _, v = value.partition("=")
            cfg[k.strip()] = v.strip()

    result = {k: coerce(k, cfg.get(k)) for k in ("port", "workers", "debug", "log_level")}
    result["api_key"] = "****"

    response = JSONResponse(content=result)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


# ============ Q5: /analytics ============
@app.post("/analytics")
async def analytics(request: Request):
    if request.headers.get("X-API-Key") != Q5_API_KEY:
        response = JSONResponse(status_code=401, content={"error": "Unauthorized"})
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    try:
        body = await request.json()
        events = body.get("events", [])
    except Exception:
        response = JSONResponse(status_code=400, content={"error": "Invalid body"})
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    unique_users = set()
    revenue = 0.0
    user_totals = defaultdict(float)

    for e in events:
        user = e.get("user")
        amount = e.get("amount", 0)
        if user:
            unique_users.add(user)
        if amount > 0:
            revenue += amount
            if user:
                user_totals[user] += amount

    top_user = max(user_totals, key=user_totals.get) if user_totals else None

    result = {
        "email": EMAIL,
        "total_events": len(events),
        "unique_users": len(unique_users),
        "revenue": round(revenue, 2),
        "top_user": top_user,
    }
    response = JSONResponse(content=result)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response
@app.get("/work")
async def do_work(n: int = 1):
    return {"email": EMAIL, "done": n}

@app.get("/metrics")
async def get_metrics():
    return Response(generate_latest(), media_type="text/plain")

@app.get("/healthz")
async def healthz():
    uptime = time.time() - START_TIME
    return {"status": "ok", "uptime_s": uptime}

@app.get("/logs/tail")
async def logs_tail(limit: int = 10):
    return list(logs_queue)[-limit:]

import re
from pydantic import BaseModel

class InvoiceOut(BaseModel):
    vendor: str = ""
    amount: float = 0.0
    currency: str = ""
    date: str = ""

@app.post("/extract", response_model=InvoiceOut)
async def extract(request: Request):
    try:
        body = await request.json()
        text = body.get("text", "")
    except Exception:
        return InvoiceOut()

    if not text or not isinstance(text, str):
        return InvoiceOut()

    # --- Date: YYYY-MM-DD anywhere ---
    date_match = re.search(r'(20\d{2}-\d{2}-\d{2})', text)
    date = date_match.group(1) if date_match else ""

    # --- Currency: 3-letter code ---
    curr_match = re.search(r'\b(USD|EUR|GBP)\b', text, re.IGNORECASE)
    currency = curr_match.group(1).upper() if curr_match else ""

    # --- Amount: currency symbol/code followed by a number ---
    amount = 0.0
    amount_match = re.search(
        r'(?:USD|EUR|GBP|\$|€|£)\s*([\d,]+(?:\.\d{1,2})?)',
        text, re.IGNORECASE
    )
    if amount_match:
        amount = float(amount_match.group(1).replace(",", ""))
    else:
        fallback_match = re.search(
            r'(?:total|amount|due|balance|pay)\D{0,15}?([\d,]+(?:\.\d{1,2})?)',
            text, re.IGNORECASE
        )
        if fallback_match:
            amount = float(fallback_match.group(1).replace(",", ""))

    # --- Vendor: hyphenated-code style name (e.g. "Acme-xxxx Industries Ltd.") ---
    vendor = ""
    vendor_match = re.search(
        r'([A-Z][A-Za-z0-9]*-[A-Za-z0-9]{2,8}(?:\s+[A-Z][A-Za-z]+){0,4}\.?)',
        text
    )
    if vendor_match:
        vendor = vendor_match.group(1)
    else:
        # fallback: capitalized words ending in a common company suffix
        fallback_vendor = re.search(
            r'([A-Z][A-Za-z0-9&,\.\-\s]{2,50}?(?:Inc\.?|LLC|Ltd\.?|Corp\.?|Co\.|Industries))',
            text
        )
        if fallback_vendor:
            vendor = fallback_vendor.group(1).strip()

    return InvoiceOut(vendor=vendor, amount=amount, currency=currency, date=date)

import uuid as uuid_lib
from collections import deque

Q9_TOTAL_ORDERS = 43
Q9_RATE_LIMIT = 17

idempotency_store = {}
rate_limit_buckets = {}  # client_id -> deque of request timestamps

def check_rate_limit(client_id: str) -> bool:
    """Returns True if request should be allowed, False if rate-limited."""
    now = time.time()
    bucket = rate_limit_buckets.setdefault(client_id, deque())

    while bucket and bucket[0] <= now - 10:
        bucket.popleft()

    if len(bucket) >= Q9_RATE_LIMIT:
        return False

    bucket.append(now)
    return True


@app.post("/orders")
async def create_order(request: Request):
    client_id = request.headers.get("X-Client-Id", "default")
    if not check_rate_limit(client_id):
        return JSONResponse(
            status_code=429,
            content={"error": "rate limited"},
            headers={"Retry-After": "10"},
        )

    idem_key = request.headers.get("Idempotency-Key")
    if idem_key and idem_key in idempotency_store:
        return JSONResponse(
            status_code=201,
            content={"id": idempotency_store[idem_key]},
        )

    order_id = str(uuid_lib.uuid4())
    if idem_key:
        idempotency_store[idem_key] = order_id

    return JSONResponse(status_code=201, content={"id": order_id})


@app.get("/orders")
async def get_orders(request: Request, limit: int = 10, cursor: str = None):
    client_id = request.headers.get("X-Client-Id", "default")
    if not check_rate_limit(client_id):
        return JSONResponse(
            status_code=429,
            content={"error": "rate limited"},
            headers={"Retry-After": "10"},
        )

    all_items = [{"id": i} for i in range(1, Q9_TOTAL_ORDERS + 1)]
    start_idx = int(cursor) if cursor and cursor.isdigit() else 0
    end_idx = start_idx + limit
    page = all_items[start_idx:end_idx]
    next_cursor = str(end_idx) if end_idx < len(all_items) else None

    return {"items": page, "next_cursor": next_cursor}
