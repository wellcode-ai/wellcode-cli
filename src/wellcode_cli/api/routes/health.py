"""Health check endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text

from ...db.engine import get_engine

router = APIRouter()


@router.get("/health")
def health_check():
    db_ok = False
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    return {
        "status": "healthy" if db_ok else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": "connected" if db_ok else "disconnected",
        "version": "0.2.0",
    }
