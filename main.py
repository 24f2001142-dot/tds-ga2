import time
import uuid
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

app = FastAPI()

EMAIL = "24f2001142@ds.study.iitm.ac.in"  
ALLOWED_ORIGIN = "https://dash-uzy9zp.example.com"

@app.middleware("http")
async def add_headers_and_cors(request: Request, call_next):
    start = time.time()
    req_id = str(uuid.uuid4())
    origin = request.headers.get("origin")

    # Handle preflight ourselves so we control exactly who gets ACAO
    if request.method == "OPTIONS":
        response = Response(status_code=204)
    else:
        response = await call_next(request)

    if origin == ALLOWED_ORIGIN:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"

    response.headers["X-Request-ID"] = req_id
    response.headers["X-Process-Time"] = f"{time.time() - start:.6f}"
    return response

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

import jwt
from fastapi import Request

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
