# main.py
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
# from InvestorDesk.config import ensure_indexes, get_collection_data, print_mongo_collections, setup_initial_schema

# Routers
from Anvi_Mailing.routes import router as mailing_router
from InvestorDesk.routes import router as investor_router
from Vanika_Mailing.routes import router as vanika_router

# Load Environment
load_dotenv()

# app = FastAPI(docs_url=None, redoc_url=None)
app = FastAPI()

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
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Accept",
        "Authorization",
    ],
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

    allowed = CORS_ORIGINS

    if origin and origin not in allowed:
        print(f"🚫 CORS BLOCKED | {origin} → {path}")
        raise HTTPException(status_code=403, detail="CORS_BLOCKED")

    return await call_next(request)

# ---------------------------------------------------------
# Health check
# ---------------------------------------------------------
@app.get("/")
def home():
    return {"msg": "Anvi FastAPI-Mail-Backend Running ✅"}

# ---------------------------------------------------------
# Startup logs
# ---------------------------------------------------------
@app.on_event("startup")
async def on_startup():
    # await ensure_indexes()
    # await setup_initial_schema()
    # await print_mongo_collections()
    # await get_collection_data("InvestorsProfiles")
    # await get_collection_data("InvestorsContent")
    print("Database indexes ensured.")
    print("Backend started successfully.")
    print("/////////////////////////////////////////////////////////////")
