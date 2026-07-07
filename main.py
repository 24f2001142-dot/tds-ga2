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
