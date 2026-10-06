# Windows Endpoint Collector (`endpoint-agent`)

A lightweight, safe, read-only Windows application discovery agent that extracts installed software metadata from the local operating system and feeds it into the **Commercial License Intelligence** ingestion & identity resolution engine.

---

## Architectural Principles

```
THIS WINDOWS LAPTOP
        ↓
Windows Endpoint Collector (Read-Only)
        ↓
┌────────────────────────────────────────────────────────┐
│ Discovery Sources                                      │
│                                                        │
│ • HKLM 64-bit Registry                                 │
│ • HKLM 32-bit Registry (WOW6432Node)                   │
│ • HKCU Current User Registry                           │
│ • Windows Modern Packages (AppX / MSIX)                │
└────────────────────────────────────────────────────────┘
        ↓
Raw Preserved Software Inventory
        ↓
Local Deduplication & Heuristic System Filter
        ↓
Ingestion API (`POST /api/inventory/ingest`)
        ↓
Backend Normalization & Identity Resolution (Step 13)
        ↓
Application Catalog (Step 11)
        ↓
License Profile Consolidation (Step 9)
        ↓
Streamlit Discovery & Audit Dashboard
```

---

## Critical Conceptual Invariants

```
INSTALLED ≠ LICENSED
DETECTED ≠ ENTITLED
LICENSE INTELLIGENCE ≠ ENTITLEMENT
```

1. **Installed Devices / Active Installations**: Indicates software installed on endpoint hardware.
2. **License Intelligence**: Identifies what official vendor terms stipulate (e.g. `NAMED_USER` vs `DEVICE`).
3. **Entitlement**: Represents what the organization has purchased/contracted.
4. **License Position**: The reconciled balance between Entitlements and Consumption.

---

## Safety & Security Guarantees

- **100% Read-Only**: The agent only reads registry keys and executes read-only package enumeration.
- **No Command Execution**: `UninstallString` and other registry command lines are captured strictly as text metadata and are **never executed**.
- **No System Modifications**: Does not modify Windows system files, services, firewall, registry, or installed applications.
- **No Sensitive Data**: Never accesses browser history, personal files, documents, or credentials.
- **Auditable & Offline Fallback**: Generates `inventory_<timestamp>.json` locally before transmitting to the backend.

---

## Usage

### 1. Dry Run (Local Scan Without Upload)
```bash
python collector.py --dry-run
```
Outputs local file: `inventory_YYYYMMDD_HHMMSS.json`.

### 2. Live Scan & Backend Ingestion
```bash
python collector.py --backend-url http://localhost:8000
```

### 3. Optional Flags
- `--dry-run`: Scans laptop and saves local JSON without network upload.
- `--output path/to/file.json`: Custom output filename.
- `--backend-url http://...`: Target backend service URL.
- `--api-key <secret>`: Optional agent authentication key.
- `--no-packages`: Skips AppX / MSIX package discovery.
- `--quiet`: Suppresses non-essential log messages.

---

## Known Limitations

- **Portable Applications**: Standalone single-binary `.exe` tools that do not create registry entries or install packages are not detected in registry scans.
- **Non-Elevated Package Scope**: Modern Windows Store packages are enumerated for the current user session when run without administrative privileges.
