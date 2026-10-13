# main.py
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv

# Load Environment before anything reads os.environ
load_dotenv()

# from InvestorDesk.config import ensure_indexes, get_collection_data, print_mongo_collections, setup_initial_schema

# Routers
from Anvi_Mailing.routes import router as mailing_router
from InvestorDesk.routes import router as investor_router
from Vanika_Mailing.routes import router as vanika_router, get_waitlist, ensure_waitlist_indexes, storage_unavailable_reason
from Vanika_Mailing.mailer import active_transport

_background_tasks = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # await ensure_indexes()
    # await setup_initial_schema()
    # await print_mongo_collections()
    # await get_collection_data("InvestorsProfiles")
    # await get_collection_data("InvestorsContent")

    print(f"[Vanika] Mail transport: {active_transport()}")
    waitlist = get_waitlist()
    if waitlist is None:
        print(f"[Vanika] [WARN] Waitlist storage disabled ({storage_unavailable_reason()}) — sign-ups will NOT be stored.")
    else:
        # Don't block startup on Atlas; keep a reference so the task isn't garbage-collected.
        # If it fails, the first sign-up retries it.
        task = asyncio.create_task(ensure_waitlist_indexes(waitlist))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    print("Backend started successfully.")
    print("/////////////////////////////////////////////////////////////")
    yield


# app = FastAPI(docs_url=None, redoc_url=None)
app = FastAPI(lifespan=lifespan)

# ---------------------------------------------------------
# Register routers
# ---------------------------------------------------------
app.include_router(mailing_router, prefix="/anvi")
app.include_router(investor_router, prefix="/investorDesk")
app.include_router(vanika_router, prefix="/vanika")

# ---------------------------------------------------------
# Static files & favicon
# ---------------------------------------------------------
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.ico")

# ---------------------------------------------------------
# CORS CONFIG
# ---------------------------------------------------------
CORS_ORIGINS = [o.strip().rstrip("/") for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
ALLOW_ANY_ORIGIN = "*" in CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Accept",
        "Authorization",
        "X-Admin-Key",
    ],
    expose_headers=["Content-Disposition"],
    max_age=600,
)

# ---------------------------------------------------------
# 🔒 ORIGIN FIREWALL (OPTIONS SAFE)
# ---------------------------------------------------------
@app.middleware("http")
async def origin_firewall(request: Request, call_next):

    # ✅ Allow preflight requests
    if request.method == "OPTIONS":
        return await call_next(request)

    origin = request.headers.get("origin")
    path = request.url.path

    if origin and not ALLOW_ANY_ORIGIN and origin.rstrip("/") not in CORS_ORIGINS:
        print(f"🚫 CORS BLOCKED | {origin} → {path}")
        # Return (not raise): exceptions raised in middleware become 500s
        return JSONResponse(status_code=403, content={"detail": "CORS_BLOCKED"})

    response = await call_next(request)
    # Transport security: browsers must only ever reach this API over HTTPS
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    return response

# ---------------------------------------------------------
# Health check
# ---------------------------------------------------------
@app.get("/")
def home():
    return {"msg": "Anvi FastAPI-Mail-Backend Running ✅"}
