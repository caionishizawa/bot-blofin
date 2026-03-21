"""
Dashboard Web — FastAPI backend for NPK Sinais trading dashboard.

Run with:
    cd src && uvicorn web.app:app --host 0.0.0.0 --port 8000
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Add src/ to path so we can import modules/utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import yaml
from dotenv import load_dotenv

load_dotenv()

from modules.performance import PerformanceDB
from modules.share_pnl import create_share_card
from web.auth import authenticate, verify_token

logger = logging.getLogger(__name__)

app = FastAPI(title="NPK Sinais — Dashboard", docs_url=None, redoc_url=None)

# ─── Template setup ───────────────────────────────────────────────────
_templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))

# ─── DB singleton ─────────────────────────────────────────────────────
_db: Optional[PerformanceDB] = None


def _load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}


async def get_db() -> PerformanceDB:
    global _db
    if _db is None:
        config = _load_config()
        db_path = config.get("db_path", "data/trades.db")
        # Resolve relative to src/
        if not os.path.isabs(db_path):
            db_path = str(Path(__file__).parent.parent / db_path)
        _db = PerformanceDB(db_path)
        await _db.initialize()
    return _db


@app.on_event("startup")
async def startup():
    await get_db()
    logger.info("Dashboard started")


@app.on_event("shutdown")
async def shutdown():
    global _db
    if _db:
        await _db.close()


# ─── Auth helpers ─────────────────────────────────────────────────────

def _get_token_from_request(request: Request) -> Optional[str]:
    """Extract Bearer token from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def require_auth(request: Request) -> str:
    """Dependency: validates JWT and returns username."""
    token = _get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token ausente")
    username = verify_token(token)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado")
    return username


# ─── Pages ────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


# ─── Auth API ─────────────────────────────────────────────────────────

@app.post("/api/auth/login")
async def login(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON inválido")

    username = body.get("username", "").strip()
    password = body.get("password", "").strip()

    if not username or not password:
        raise HTTPException(status_code=400, detail="Usuário e senha obrigatórios")

    token = authenticate(username, password)
    if not token:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    return {"token": token, "username": username}


# ─── Data API ─────────────────────────────────────────────────────────

@app.get("/api/stats")
async def get_stats(
    days: int = 30,
    db: PerformanceDB = Depends(get_db),
    user: str = Depends(require_auth),
):
    stats = await db.get_stats(days=days)
    return stats


@app.get("/api/trades")
async def get_trades(
    limit: int = 100,
    db: PerformanceDB = Depends(get_db),
    user: str = Depends(require_auth),
):
    trades = await db.get_all_trades(limit=limit)
    # Parse reasons from JSON string
    for t in trades:
        import json
        if isinstance(t.get("reasons"), str):
            try:
                t["reasons"] = json.loads(t["reasons"])
            except Exception:
                t["reasons"] = []
    return trades


@app.get("/api/equity")
async def get_equity(
    limit: int = 200,
    db: PerformanceDB = Depends(get_db),
    user: str = Depends(require_auth),
):
    trades = await db.get_equity_curve(limit=limit)
    # Build cumulative PNL series
    cumulative = 0.0
    result = []
    for t in trades:
        cumulative += t.get("pnl_pct", 0)
        result.append({
            "date": t.get("closed_at", "")[:10],
            "pnl": round(t.get("pnl_pct", 0), 2),
            "cumulative": round(cumulative, 2),
            "pair": t.get("pair", ""),
            "direction": t.get("direction", ""),
            "status": t.get("status", ""),
        })
    return result


@app.get("/api/daily")
async def get_daily(
    days: int = 30,
    db: PerformanceDB = Depends(get_db),
    user: str = Depends(require_auth),
):
    daily = await db.get_daily_stats(days=days)
    return daily


@app.get("/api/today")
async def get_today(
    db: PerformanceDB = Depends(get_db),
    user: str = Depends(require_auth),
):
    count = await db.get_trades_today()
    return {"trades_today": count}


@app.get("/api/sharepnl")
async def get_share_pnl_image(
    days: int = 30,
    db: PerformanceDB = Depends(get_db),
    user: str = Depends(require_auth),
):
    """Generate and return a shareable PNL card as PNG."""
    from fastapi.responses import StreamingResponse
    config = _load_config()
    watermark = config.get("chart", {}).get("watermark", "NPK Sinais")
    stats = await db.get_stats(days=days)
    recent = await db.get_recent_trades(limit=20)
    buf = create_share_card(stats, recent, watermark=watermark)
    return StreamingResponse(buf, media_type="image/png")
