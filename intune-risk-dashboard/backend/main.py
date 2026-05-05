"""
main.py — FastAPI backend for Intune Device Risk Intelligence Dashboard.

Endpoints:
  GET  /health                  → service health + last sync time
  POST /sync                    → trigger a delta sync manually
  GET  /devices                 → all devices (paginated)
  GET  /devices/{device_id}     → single device details + risk profile
  GET  /risk                    → all risk profiles, sorted by score desc
  GET  /risk/summary            → dashboard summary stats
  GET  /risk/high               → devices above risk threshold
  GET  /sync/status             → current sync state
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

import backend.device_service as svc
from backend.models import DashboardSummary, DeviceRiskProfile, ManagedDevice, SyncState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("api")

HIGH_THRESHOLD = int(os.getenv("RISK_HIGH_THRESHOLD", 70))


# ---------------------------------------------------------------------------
# Startup — run initial sync in background (or load demo data)
# ---------------------------------------------------------------------------
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

@asynccontextmanager
async def lifespan(app: FastAPI):
    if DEMO_MODE:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from demo_loader import load_demo_devices
        count = load_demo_devices()
        logger.info("[DEMO MODE] Loaded %d mock devices.", count)
    else:
        logger.info("Starting initial device sync …")
        asyncio.create_task(svc.initial_sync())
    yield


app = FastAPI(
    title="Intune Device Risk Intelligence API",
    description="Real-time endpoint risk scoring and compliance dashboard powered by Microsoft Graph",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
def _compute_summary() -> DashboardSummary:
    profiles = svc.get_all_risk_profiles()
    devices = svc.get_all_devices()

    if not profiles:
        return DashboardSummary(
            total_devices=0, compliant_count=0, noncompliant_count=0, unknown_count=0,
            compliance_rate_pct=0.0, risk_level_distribution={},
            avg_risk_score=0.0, top_risk_devices=[], os_breakdown={},
            stale_device_count=0, unencrypted_count=0,
        )

    compliant = sum(1 for p in profiles if p.compliance_state == "compliant")
    noncompliant = sum(1 for p in profiles if p.compliance_state == "noncompliant")
    unknown = sum(1 for p in profiles if p.compliance_state not in ("compliant", "noncompliant"))
    total = len(profiles)

    risk_dist: dict = {}
    for p in profiles:
        risk_dist[p.risk_level] = risk_dist.get(p.risk_level, 0) + 1

    os_dist: dict = {}
    for d in devices:
        os_key = d.operating_system or "Unknown"
        os_dist[os_key] = os_dist.get(os_key, 0) + 1

    top_at_risk = sorted(profiles, key=lambda p: p.risk_score, reverse=True)[:10]

    stale = sum(1 for p in profiles if p.days_since_sync is not None and p.days_since_sync > 7)
    unencrypted = sum(1 for p in profiles if p.is_encrypted is False)

    return DashboardSummary(
        total_devices=total,
        compliant_count=compliant,
        noncompliant_count=noncompliant,
        unknown_count=unknown,
        compliance_rate_pct=round((compliant / total) * 100, 1) if total else 0.0,
        risk_level_distribution=risk_dist,
        avg_risk_score=round(sum(p.risk_score for p in profiles) / total, 1),
        top_risk_devices=top_at_risk,
        os_breakdown=os_dist,
        stale_device_count=stale,
        unencrypted_count=unencrypted,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    state = svc.get_sync_state()
    return {
        "status": "ok",
        "devices_cached": state.total_devices_cached,
        "last_synced_at": state.last_synced_at,
    }


@app.post("/sync", summary="Trigger a delta sync")
async def trigger_sync():
    try:
        changed = await svc.delta_sync()
        state = svc.get_sync_state()
        return {"changed_devices": changed, "total_cached": state.total_devices_cached,
                "last_synced_at": state.last_synced_at}
    except Exception as exc:
        logger.error("Sync failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/sync/status", response_model=SyncState)
async def sync_status():
    return svc.get_sync_state()


@app.get("/devices", response_model=List[ManagedDevice])
async def list_devices(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    os_filter: Optional[str] = Query(None, description="Filter by operating system"),
    compliance: Optional[str] = Query(None, description="Filter by compliance state"),
):
    devices = svc.get_all_devices()
    if os_filter:
        devices = [d for d in devices if os_filter.lower() in d.operating_system.lower()]
    if compliance:
        devices = [d for d in devices if d.compliance_state == compliance]
    return devices[skip: skip + limit]


@app.get("/devices/{device_id}", response_model=ManagedDevice)
async def get_device(device_id: str):
    device = svc.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@app.get("/risk", response_model=List[DeviceRiskProfile])
async def list_risk_profiles(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    min_score: int = Query(0, ge=0, le=100),
    level: Optional[str] = Query(None, description="Filter by risk level"),
):
    profiles = svc.get_all_risk_profiles()
    if min_score:
        profiles = [p for p in profiles if p.risk_score >= min_score]
    if level:
        profiles = [p for p in profiles if p.risk_level == level.upper()]
    profiles = sorted(profiles, key=lambda p: p.risk_score, reverse=True)
    return profiles[skip: skip + limit]


# NOTE: specific sub-paths MUST come before /{device_id} to avoid being swallowed
@app.get("/risk/summary", response_model=DashboardSummary)
async def get_summary():
    return _compute_summary()


@app.get("/risk/high", response_model=List[DeviceRiskProfile])
async def get_high_risk(threshold: int = Query(HIGH_THRESHOLD, ge=0, le=100)):
    return svc.get_high_risk_devices(threshold=threshold)


@app.get("/risk/{device_id}", response_model=DeviceRiskProfile)
async def get_risk_profile(device_id: str):
    profile = svc.get_risk_profile(device_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Risk profile not found")
    return profile


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000)),
        reload=True,
    )
