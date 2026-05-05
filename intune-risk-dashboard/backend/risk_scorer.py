"""
risk_scorer.py — Device risk scoring engine.

Evaluates each device across multiple security dimensions and produces
a weighted 0–100 risk score with per-factor breakdowns.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import List, Optional

from backend.models import DeviceRiskProfile, ManagedDevice, RiskFactor

HIGH_THRESHOLD = int(os.getenv("RISK_HIGH_THRESHOLD", 70))
MEDIUM_THRESHOLD = int(os.getenv("RISK_MEDIUM_THRESHOLD", 40))

# Known EOL OS versions (simplified; extend as needed)
EOL_OS_VERSIONS = {
    "Windows": ["10.0.19041", "10.0.18363", "10.0.17763", "10.0.14393"],
    "iOS": ["14.", "13.", "12.", "11."],
    "Android": ["9.", "8.", "7."],
}


def _days_since(dt: Optional[datetime]) -> Optional[int]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).days


def _is_eol_os(os_name: str, os_version: str) -> bool:
    for eol in EOL_OS_VERSIONS.get(os_name, []):
        if os_version.startswith(eol):
            return True
    return False


def _risk_level(score: int) -> str:
    if score >= HIGH_THRESHOLD:
        return "CRITICAL" if score >= 85 else "HIGH"
    if score >= MEDIUM_THRESHOLD:
        return "MEDIUM"
    if score > 0:
        return "LOW"
    return "PASS"


def build_risk_profile(device: ManagedDevice) -> DeviceRiskProfile:
    """
    Score a device across security risk dimensions.
    Returns a DeviceRiskProfile with per-factor breakdown.
    """
    factors: List[RiskFactor] = []
    raw_score = 0.0

    # ------------------------------------------------------------------
    # 1. Compliance state                          (max 35 pts)
    # ------------------------------------------------------------------
    state_scores = {
        "noncompliant": 35.0,
        "unknown":      20.0,
        "notApplicable": 10.0,
        "compliant":     0.0,
    }
    state_contrib = state_scores.get(device.compliance_state, 20.0)
    if state_contrib > 0:
        factors.append(RiskFactor(
            name="Compliance State",
            score_contribution=state_contrib,
            description=f"Device compliance state is '{device.compliance_state}'.",
        ))
        raw_score += state_contrib

    # ------------------------------------------------------------------
    # 2. Encryption                                (max 20 pts)
    # ------------------------------------------------------------------
    if device.is_encrypted is False:
        factors.append(RiskFactor(
            name="Disk Not Encrypted",
            score_contribution=20.0,
            description="Device storage is not encrypted.",
        ))
        raw_score += 20.0

    # ------------------------------------------------------------------
    # 3. Jailbreak / Root detection                (max 25 pts)
    # ------------------------------------------------------------------
    if device.jail_broken and device.jail_broken.lower() not in ("unknown", "false", "no", ""):
        factors.append(RiskFactor(
            name="Jailbroken / Rooted",
            score_contribution=25.0,
            description=f"Device jailbreak status: '{device.jail_broken}'.",
        ))
        raw_score += 25.0

    # ------------------------------------------------------------------
    # 4. Stale sync (last sync > 7 days)           (max 15 pts)
    # ------------------------------------------------------------------
    days_since_sync = _days_since(device.last_sync_date_time)
    if days_since_sync is not None:
        if days_since_sync > 30:
            contrib = 15.0
            desc = f"Device has not synced in {days_since_sync} days (>30)."
        elif days_since_sync > 7:
            contrib = 8.0
            desc = f"Device has not synced in {days_since_sync} days (>7)."
        else:
            contrib = 0.0
            desc = ""

        if contrib > 0:
            factors.append(RiskFactor(
                name="Stale Sync",
                score_contribution=contrib,
                description=desc,
            ))
            raw_score += contrib

    # ------------------------------------------------------------------
    # 5. End-of-life OS version                    (max 15 pts)
    # ------------------------------------------------------------------
    if _is_eol_os(device.operating_system, device.os_version):
        factors.append(RiskFactor(
            name="EOL OS Version",
            score_contribution=15.0,
            description=(
                f"{device.operating_system} {device.os_version} is end-of-life "
                f"and no longer receives security patches."
            ),
        ))
        raw_score += 15.0

    # ------------------------------------------------------------------
    # 6. Personal (BYOD) device                    (max 5 pts)
    # ------------------------------------------------------------------
    if device.managed_device_owner_type == "personal":
        factors.append(RiskFactor(
            name="Personal (BYOD) Device",
            score_contribution=5.0,
            description="Device is personally owned (BYOD), posing a higher data exfiltration risk.",
        ))
        raw_score += 5.0

    # ------------------------------------------------------------------
    # Normalize to 0–100
    # ------------------------------------------------------------------
    normalized = min(int(raw_score), 100)

    return DeviceRiskProfile(
        device_id=device.id,
        device_name=device.device_name,
        user_principal_name=device.user_principal_name,
        operating_system=device.operating_system,
        os_version=device.os_version,
        compliance_state=device.compliance_state,
        risk_score=normalized,
        risk_level=_risk_level(normalized),
        risk_factors=factors,
        days_since_sync=days_since_sync,
        is_encrypted=device.is_encrypted,
        jail_broken=device.jail_broken,
        last_sync_date_time=device.last_sync_date_time,
    )
