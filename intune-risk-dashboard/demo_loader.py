"""
demo_loader.py — Populate the device store with mock Intune devices for demo/offline mode.
"""

from datetime import datetime, timedelta, timezone
from backend.models import ManagedDevice
from backend.risk_scorer import build_risk_profile
import backend.device_service as svc


MOCK_DEVICES_RAW = [
    {
        "id": "dev-001", "deviceName": "LAPTOP-ALICE", "userPrincipalName": "alice@contoso.com",
        "operatingSystem": "Windows", "osVersion": "10.0.19041", "complianceState": "noncompliant",
        "lastSyncDateTime": (datetime.now(timezone.utc) - timedelta(days=35)).isoformat(),
        "enrolledDateTime": (datetime.now(timezone.utc) - timedelta(days=200)).isoformat(),
        "azureADRegistered": True, "managedDeviceOwnerType": "company",
        "model": "ThinkPad X1", "manufacturer": "Lenovo",
        "totalStorageSpaceInBytes": 500000000000, "freeStorageSpaceInBytes": 20000000000,
        "isEncrypted": False, "isSupervised": False, "jailBroken": "Unknown",
        "managementState": "managed",
    },
    {
        "id": "dev-002", "deviceName": "DESKTOP-BOB", "userPrincipalName": "bob@contoso.com",
        "operatingSystem": "Windows", "osVersion": "10.0.22621", "complianceState": "compliant",
        "lastSyncDateTime": datetime.now(timezone.utc).isoformat(),
        "enrolledDateTime": (datetime.now(timezone.utc) - timedelta(days=120)).isoformat(),
        "azureADRegistered": True, "managedDeviceOwnerType": "company",
        "model": "OptiPlex 7090", "manufacturer": "Dell",
        "totalStorageSpaceInBytes": 256000000000, "freeStorageSpaceInBytes": 100000000000,
        "isEncrypted": True, "isSupervised": True, "jailBroken": "False",
        "managementState": "managed",
    },
    {
        "id": "dev-003", "deviceName": "iPhone-CAROL", "userPrincipalName": "carol@contoso.com",
        "operatingSystem": "iOS", "osVersion": "13.5", "complianceState": "noncompliant",
        "lastSyncDateTime": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
        "enrolledDateTime": (datetime.now(timezone.utc) - timedelta(days=80)).isoformat(),
        "azureADRegistered": True, "managedDeviceOwnerType": "personal",
        "model": "iPhone 11", "manufacturer": "Apple",
        "totalStorageSpaceInBytes": 64000000000, "freeStorageSpaceInBytes": 5000000000,
        "isEncrypted": True, "isSupervised": False, "jailBroken": "True",
        "managementState": "managed",
    },
    {
        "id": "dev-004", "deviceName": "LAPTOP-DAVE", "userPrincipalName": "dave@contoso.com",
        "operatingSystem": "Windows", "osVersion": "10.0.22631", "complianceState": "compliant",
        "lastSyncDateTime": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
        "enrolledDateTime": (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
        "azureADRegistered": True, "managedDeviceOwnerType": "company",
        "model": "EliteBook 840", "manufacturer": "HP",
        "totalStorageSpaceInBytes": 512000000000, "freeStorageSpaceInBytes": 200000000000,
        "isEncrypted": True, "isSupervised": True, "jailBroken": "False",
        "managementState": "managed",
    },
    {
        "id": "dev-005", "deviceName": "Android-EVE", "userPrincipalName": "eve@contoso.com",
        "operatingSystem": "Android", "osVersion": "9.0", "complianceState": "noncompliant",
        "lastSyncDateTime": (datetime.now(timezone.utc) - timedelta(days=45)).isoformat(),
        "enrolledDateTime": (datetime.now(timezone.utc) - timedelta(days=300)).isoformat(),
        "azureADRegistered": False, "managedDeviceOwnerType": "personal",
        "model": "Galaxy S10", "manufacturer": "Samsung",
        "totalStorageSpaceInBytes": 128000000000, "freeStorageSpaceInBytes": 30000000000,
        "isEncrypted": False, "isSupervised": False, "jailBroken": "Unknown",
        "managementState": "managed",
    },
    {
        "id": "dev-006", "deviceName": "LAPTOP-FRANK", "userPrincipalName": "frank@contoso.com",
        "operatingSystem": "Windows", "osVersion": "10.0.22631", "complianceState": "compliant",
        "lastSyncDateTime": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "enrolledDateTime": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
        "azureADRegistered": True, "managedDeviceOwnerType": "company",
        "model": "MacBook Pro", "manufacturer": "Apple",
        "totalStorageSpaceInBytes": 512000000000, "freeStorageSpaceInBytes": 150000000000,
        "isEncrypted": True, "isSupervised": True, "jailBroken": "False",
        "managementState": "managed",
    },
    {
        "id": "dev-007", "deviceName": "TABLET-GRACE", "userPrincipalName": "grace@contoso.com",
        "operatingSystem": "iOS", "osVersion": "17.4", "complianceState": "unknown",
        "lastSyncDateTime": (datetime.now(timezone.utc) - timedelta(days=9)).isoformat(),
        "enrolledDateTime": (datetime.now(timezone.utc) - timedelta(days=15)).isoformat(),
        "azureADRegistered": True, "managedDeviceOwnerType": "company",
        "model": "iPad Pro", "manufacturer": "Apple",
        "totalStorageSpaceInBytes": 256000000000, "freeStorageSpaceInBytes": 80000000000,
        "isEncrypted": True, "isSupervised": True, "jailBroken": "False",
        "managementState": "managed",
    },
    {
        "id": "dev-008", "deviceName": "LAPTOP-HENRY", "userPrincipalName": "henry@contoso.com",
        "operatingSystem": "Windows", "osVersion": "10.0.17763", "complianceState": "noncompliant",
        "lastSyncDateTime": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
        "enrolledDateTime": (datetime.now(timezone.utc) - timedelta(days=500)).isoformat(),
        "azureADRegistered": True, "managedDeviceOwnerType": "company",
        "model": "Latitude 5510", "manufacturer": "Dell",
        "totalStorageSpaceInBytes": 256000000000, "freeStorageSpaceInBytes": 10000000000,
        "isEncrypted": False, "isSupervised": False, "jailBroken": "False",
        "managementState": "managed",
    },
]


def load_demo_devices():
    """Populate the in-memory device and risk stores with mock data."""
    svc._device_store.clear()
    svc._risk_store.clear()

    for raw in MOCK_DEVICES_RAW:
        device = ManagedDevice.from_graph(raw)
        svc._device_store[device.id] = device
        svc._risk_store[device.id] = build_risk_profile(device)

    from datetime import datetime, timezone
    svc._sync_state.last_synced_at = datetime.now(timezone.utc)
    svc._sync_state.total_devices_cached = len(svc._device_store)
    svc._sync_state.delta_link = "DEMO_MODE"

    return len(svc._device_store)
