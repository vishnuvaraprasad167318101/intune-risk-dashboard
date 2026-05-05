# Intune Device Risk Intelligence Dashboard

A full-stack application that pulls device compliance and management data from Microsoft Intune via the Microsoft Graph API, scores each device's security risk using a weighted multi-factor engine, and visualizes results in a real-time Streamlit dashboard backed by a FastAPI REST API.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              Streamlit Dashboard (frontend/)         │
│  KPI cards • Risk charts • Drill-down per device    │
└──────────────────────┬──────────────────────────────┘
                       │ REST (HTTP)
┌──────────────────────▼──────────────────────────────┐
│               FastAPI Backend (backend/)             │
│  /risk/summary  /devices  /risk  /sync              │
└────────────┬──────────────────────┬─────────────────┘
             │ In-memory store       │ APScheduler
┌────────────▼──────┐    ┌──────────▼──────────────┐
│  device_service   │    │  scheduler/sync.py       │
│  risk_scorer      │    │  Delta sync every N hrs  │
└────────────┬──────┘    └─────────────────────────-┘
             │ MSAL + HTTPS
┌────────────▼──────────────────────────────────────┐
│         Microsoft Graph API                        │
│  /deviceManagement/managedDevices/$delta           │
└────────────────────────────────────────────────────┘
```

## Features

- **Microsoft Graph delta queries** — incremental sync (only changed devices per poll, not full dataset)
- **MSAL client credentials flow** — secure OAuth2 with in-memory token caching and auto-refresh
- **6-factor risk scoring engine**: compliance state, encryption, jailbreak, stale sync, EOL OS, BYOD
- **FastAPI REST backend** with pagination, filtering, and OpenAPI docs
- **Streamlit dashboard**: KPI cards, pie/bar charts, sortable device table, per-device factor drill-down
- **APScheduler** for automatic background sync (configurable interval)

## Prerequisites

1. Azure AD App Registration with these **Application permissions** (admin consent required):
   - `DeviceManagementManagedDevices.Read.All`
   - `DeviceManagementConfiguration.Read.All`

2. Note your `tenant_id`, `client_id`, and `client_secret`

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/intune-risk-dashboard
cd intune-risk-dashboard
pip install -r requirements.txt
cp .env.example .env    # fill in your Azure AD credentials
```

## Running

**Start the API backend:**
```bash
uvicorn backend.main:app --reload
# OpenAPI docs: http://localhost:8000/docs
```

**Start the Streamlit dashboard (separate terminal):**
```bash
streamlit run frontend/dashboard.py
# Opens at http://localhost:8501
```

**Start the background sync scheduler (optional — for long-running deployments):**
```bash
python -m scheduler.sync
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health + last sync time |
| POST | `/sync` | Trigger delta sync manually |
| GET | `/sync/status` | Sync state + device count |
| GET | `/devices` | All devices (paginated, filterable) |
| GET | `/devices/{id}` | Single device details |
| GET | `/risk` | All risk profiles (sorted by score) |
| GET | `/risk/summary` | Dashboard KPI summary |
| GET | `/risk/high` | Devices above risk threshold |
| GET | `/risk/{device_id}` | Risk profile for a device |

## Risk Scoring Factors

| Factor | Max Points | Notes |
|--------|-----------|-------|
| Compliance State | 35 | noncompliant=35, unknown=20 |
| Disk Not Encrypted | 20 | is_encrypted = false |
| Jailbroken / Rooted | 25 | Any non-false jailbreak status |
| Stale Sync | 15 | >30 days=15pts, >7 days=8pts |
| EOL OS Version | 15 | Matches known EOL version list |
| BYOD Device | 5 | managedDeviceOwnerType = personal |

Score 0–39: LOW  |  40–69: MEDIUM  |  70–84: HIGH  |  85+: CRITICAL

## Technologies

Python · FastAPI · Streamlit · MSAL · Microsoft Graph API · APScheduler · Plotly · Pandas · Pydantic
