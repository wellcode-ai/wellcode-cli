"""FastAPI application for the Wellcode web dashboard and API."""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ..db.engine import init_db
from .routes import dora, metrics, surveys, health, ai_metrics


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Wellcode API",
    description="Open-source developer productivity platform API",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["Health"])
app.include_router(metrics.router, prefix="/api/v1/metrics", tags=["Metrics"])
app.include_router(dora.router, prefix="/api/v1/dora", tags=["DORA"])
app.include_router(ai_metrics.router, prefix="/api/v1/ai", tags=["AI Metrics"])
app.include_router(surveys.router, prefix="/api/v1/surveys", tags=["Surveys"])

# Serve static web dashboard if available
WEB_DIR = Path(__file__).parent.parent / "web" / "static"
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="static")
