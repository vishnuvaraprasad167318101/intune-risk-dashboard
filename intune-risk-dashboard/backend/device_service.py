"""
device_service.py — In-memory device store with delta sync management.

Acts as the data layer between Graph API calls and the API/dashboard.
Devices are stored in a dict keyed by device ID and updated incrementally.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from backend.graph_client import fetch_all_devices, fetch_delta_devices
from backend.models import ManagedDevice, SyncState
from backend.risk_scorer import build_risk_profile, DeviceRiskProfile

logger = logging.getLogger(__name__)

# In-memory stores
_device_store: Dict[str, ManagedDevice] = {}
_risk_store: Dict[str, DeviceRiskProfile] = {}
_sync_state = SyncState()
_sync_lock = asyncio.Lock()


async def initial_sync() -> int:
    """Run a full device sync, populating the in-memory store. Returns device count."""
    async with _sync_lock:
        raw_devices, delta_link = await fetch_all_devices()

        _device_store.clear()
        for raw in raw_devices:
            device = ManagedDevice.from_graph(raw)
            _device_store[device.id] = device

        # Score all devices
        _risk_store.clear()
        for device in _device_store.values():
            _risk_store[device.id] = build_risk_profile(device)

        _sync_state.delta_link = delta_link
        _sync_state.last_synced_at = datetime.now(timezone.utc)
        _sync_state.total_devices_cached = len(_device_store)

        logger.info("Initial sync complete: %d devices loaded.", len(_device_store))
        return len(_device_store)


async def delta_sync() -> int:
    """
    Incremental sync using stored delta link.
    Falls back to full sync if no delta link is available.
    Returns the number of devices updated/added.
    """
    async with _sync_lock:
        if not _sync_state.delta_link:
            logger.info("No delta link — running initial sync.")
            return await initial_sync()

        changed, new_delta_link = await fetch_delta_devices(_sync_state.delta_link)

        for raw in changed:
            # Graph delta uses @removed to signal deletions
            if raw.get("@removed"):
                device_id = raw.get("id", "")
                _device_store.pop(device_id, None)
                _risk_store.pop(device_id, None)
                continue

            device = ManagedDevice.from_graph(raw)
            _device_store[device.id] = device
            _risk_store[device.id] = build_risk_profile(device)

        _sync_state.delta_link = new_delta_link
        _sync_state.last_synced_at = datetime.now(timezone.utc)
        _sync_state.total_devices_cached = len(_device_store)

        logger.info("Delta sync complete: %d device(s) updated.", len(changed))
        return len(changed)


# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------

def get_all_devices() -> List[ManagedDevice]:
    return list(_device_store.values())


def get_all_risk_profiles() -> List[DeviceRiskProfile]:
    return list(_risk_store.values())


def get_device(device_id: str) -> Optional[ManagedDevice]:
    return _device_store.get(device_id)


def get_risk_profile(device_id: str) -> Optional[DeviceRiskProfile]:
    return _risk_store.get(device_id)


def get_sync_state() -> SyncState:
    return _sync_state


def get_noncompliant_devices() -> List[DeviceRiskProfile]:
    return [p for p in _risk_store.values() if p.compliance_state == "noncompliant"]


def get_high_risk_devices(threshold: int = 70) -> List[DeviceRiskProfile]:
    return sorted(
        [p for p in _risk_store.values() if p.risk_score >= threshold],
        key=lambda p: p.risk_score,
        reverse=True,
    )
