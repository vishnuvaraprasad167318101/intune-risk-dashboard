"""
models.py — Pydantic data models for device, compliance, and risk data.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Raw device data from Microsoft Graph / Intune
# ---------------------------------------------------------------------------

class DeviceCompliancePolicy(BaseModel):
    id: str
    display_name: str
    state: str                     # compliant | noncompliant | unknown | notApplicable
    setting_states: List[Dict] = Field(default_factory=list)


class ManagedDevice(BaseModel):
    id: str
    device_name: str
    user_principal_name: Optional[str] = None
    operating_system: str = ""
    os_version: str = ""
    compliance_state: str = ""     # compliant | noncompliant | unknown | notApplicable
    last_sync_date_time: Optional[datetime] = None
    enrolled_date_time: Optional[datetime] = None
    azure_ad_registered: bool = False
    managed_device_owner_type: str = ""  # company | personal
    model: str = ""
    manufacturer: str = ""
    total_storage_space_in_bytes: int = 0
    free_storage_space_in_bytes: int = 0
    is_encrypted: Optional[bool] = None
    is_supervised: Optional[bool] = None
    jail_broken: str = ""
    management_state: str = ""

    @classmethod
    def from_graph(cls, raw: Dict) -> "ManagedDevice":
        """Map raw Graph API response to ManagedDevice."""
        return cls(
            id=raw.get("id", ""),
            device_name=raw.get("deviceName", ""),
            user_principal_name=raw.get("userPrincipalName"),
            operating_system=raw.get("operatingSystem", ""),
            os_version=raw.get("osVersion", ""),
            compliance_state=raw.get("complianceState", "unknown"),
            last_sync_date_time=raw.get("lastSyncDateTime"),
            enrolled_date_time=raw.get("enrolledDateTime"),
            azure_ad_registered=raw.get("azureADRegistered", False),
            managed_device_owner_type=raw.get("managedDeviceOwnerType", ""),
            model=raw.get("model", ""),
            manufacturer=raw.get("manufacturer", ""),
            total_storage_space_in_bytes=raw.get("totalStorageSpaceInBytes", 0),
            free_storage_space_in_bytes=raw.get("freeStorageSpaceInBytes", 0),
            is_encrypted=raw.get("isEncrypted"),
            is_supervised=raw.get("isSupervised"),
            jail_broken=raw.get("jailBroken", "Unknown"),
            management_state=raw.get("managementState", ""),
        )


# ---------------------------------------------------------------------------
# Risk output models
# ---------------------------------------------------------------------------

class RiskFactor(BaseModel):
    name: str
    score_contribution: float
    description: str


class DeviceRiskProfile(BaseModel):
    device_id: str
    device_name: str
    user_principal_name: Optional[str]
    operating_system: str
    os_version: str
    compliance_state: str
    risk_score: int                # 0–100
    risk_level: str                # CRITICAL | HIGH | MEDIUM | LOW | PASS
    risk_factors: List[RiskFactor]
    days_since_sync: Optional[int]
    is_encrypted: Optional[bool]
    jail_broken: str
    last_sync_date_time: Optional[datetime]
    scanned_at: datetime = Field(default_factory=datetime.utcnow)


class DashboardSummary(BaseModel):
    total_devices: int
    compliant_count: int
    noncompliant_count: int
    unknown_count: int
    compliance_rate_pct: float
    risk_level_distribution: Dict[str, int]
    avg_risk_score: float
    top_risk_devices: List[DeviceRiskProfile]
    os_breakdown: Dict[str, int]
    stale_device_count: int        # not synced in > 7 days
    unencrypted_count: int


class SyncState(BaseModel):
    delta_link: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    total_devices_cached: int = 0
