"""
graph_client.py — Microsoft Graph API HTTP client with delta query support.

Delta queries allow incremental sync: the first call returns all devices
and a deltaLink. Subsequent calls to the deltaLink return only changed
devices since the last sync, drastically reducing API load.
"""

import logging
from typing import AsyncGenerator, Dict, List, Optional, Tuple

import httpx

from backend.auth import get_access_token

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

DEVICE_SELECT_FIELDS = ",".join([
    "id", "deviceName", "userPrincipalName", "operatingSystem", "osVersion",
    "complianceState", "lastSyncDateTime", "enrolledDateTime",
    "azureADRegistered", "managedDeviceOwnerType", "model", "manufacturer",
    "totalStorageSpaceInBytes", "freeStorageSpaceInBytes",
    "isEncrypted", "isSupervised", "jailBroken", "managementState",
])


async def _get_headers() -> Dict[str, str]:
    token = get_access_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "ConsistencyLevel": "eventual",
    }


async def _paginate(client: httpx.AsyncClient, url: str) -> AsyncGenerator[Dict, None]:
    """Follow @odata.nextLink pagination and yield each page's value list."""
    while url:
        headers = await _get_headers()
        response = await client.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        for item in data.get("value", []):
            yield item

        url = data.get("@odata.nextLink")
        # Preserve deltaLink for the final page
        if not url:
            return


async def fetch_all_devices() -> Tuple[List[Dict], Optional[str]]:
    """
    Full sync: fetch all managed devices from Intune via Graph API.

    Returns:
        (devices, delta_link) — list of raw device dicts and the delta link
        to use for the next incremental sync.
    """
    url = f"{GRAPH_BASE}/deviceManagement/managedDevices?$select={DEVICE_SELECT_FIELDS}&$top=100"
    devices: List[Dict] = []
    delta_link: Optional[str] = None

    async with httpx.AsyncClient() as client:
        while url:
            headers = await _get_headers()
            response = await client.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            devices.extend(data.get("value", []))
            url = data.get("@odata.nextLink")

            # The last page contains the deltaLink
            if not url:
                delta_link = data.get("@odata.deltaLink")

    logger.info("Full sync complete: %d devices fetched.", len(devices))
    return devices, delta_link


async def fetch_delta_devices(delta_link: str) -> Tuple[List[Dict], str]:
    """
    Delta sync: fetch only devices changed since the last delta_link.

    Returns:
        (changed_devices, new_delta_link)
    """
    devices: List[Dict] = []
    current_url: Optional[str] = delta_link
    new_delta_link = delta_link

    async with httpx.AsyncClient() as client:
        while current_url:
            headers = await _get_headers()
            response = await client.get(current_url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            devices.extend(data.get("value", []))
            current_url = data.get("@odata.nextLink")

            if not current_url:
                new_delta_link = data.get("@odata.deltaLink", delta_link)

    logger.info("Delta sync complete: %d device change(s).", len(devices))
    return devices, new_delta_link


async def fetch_device_compliance_policies(device_id: str) -> List[Dict]:
    """Fetch compliance policy states for a specific device."""
    url = (
        f"{GRAPH_BASE}/deviceManagement/managedDevices/{device_id}"
        f"/deviceCompliancePolicyStates"
    )
    policies: List[Dict] = []

    async with httpx.AsyncClient() as client:
        async for policy in _paginate(client, url):
            policies.append(policy)

    return policies
