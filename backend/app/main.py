from contextlib import asynccontextmanager
from fastapi import FastAPI
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from . import config
from .api import router
from .engine_api import router as engine_router
from .reports_api import router as reports_router
from .db import Base, SessionLocal, engine
from .models import User


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if not db.scalar(select(User).limit(1)):
            from .seed import seed
            seed(db)
    yield


app = FastAPI(title="AICTE Samvad API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


@app.middleware("http")
async def security_headers(request, call_next):
    r = await call_next(request)
    r.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer"})
    if request.url.path.startswith("/api") and not request.url.path.startswith("/api/documents"):
        r.headers.update({"Cache-Control": "no-store", "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'"})
    elif not request.url.path.startswith("/api"):
        r.headers.update({"Cache-Control": "no-cache, must-revalidate"})
    return r


app.include_router(router)
app.include_router(engine_router)
app.include_router(reports_router)


_FE = Path(__file__).resolve().parents[2] / "frontend"
if _FE.exists():  # serve the web app from the same origin (no build step, no CORS)
    app.mount("/", StaticFiles(directory=_FE, html=True), name="frontend")
