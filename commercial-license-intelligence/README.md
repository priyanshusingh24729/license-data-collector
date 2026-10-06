# Commercial License Intelligence

An automated software intelligence platform designed to discover, collect, extract, validate, structure, continuously monitor, audit, and reconcile commercial software licensing intelligence from public vendor documentation, pricing guides, product sheets, terms of service, optional vendor APIs, and real Windows endpoint software discovery without reliance on paid vendor APIs.

---

## Problem Statement

Enterprise software licensing models (per-core, per-seat, tiered consumption, virtualization rules, multi-cloud restrictions) are notoriously complex, constantly evolving, and scattered across disparate vendor documentation portals, PDFs, and guides. Organizations lack a reliable, deterministic intelligence pipeline that links licensing facts directly to primary source evidence with confidence scoring, automated change tracking, endpoint inventory resolution, explicit entitlement position reconciliation, end-to-end audit explainability, and real local endpoint software discovery.

This platform bridges that gap by establishing a verifiable multi-modal pipeline:
```
THIS WINDOWS LAPTOP (Step 16)
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
Raw Preserved Software Inventory & Local Deduplication
        ↓
Ingestion API (`POST /api/inventory/ingest`)
        ↓
Normalization & Identity Resolution (Step 13)
        ↓
Application Catalog (Step 11)
        ↓
Batch Research Engine (Controlled Concurrency: 3 Workers)
        ↓
Research Orchestrator (Steps 3–9)
        ↓
┌────────────────────────────────────────────────────────┐
│ Discovery & Multi-Modal Collection Layer               │
│                                                        │
│ • Official Source Discovery (Step 3)                   │
│ • Official Web Collector (HTML Parsing & Tables)       │
│ • Official PDF Collector (PyMuPDF Page Boundaries)     │
│ • Optional Vendor API Collector (REST/JSON Enrichment) │
└────────────────────────────────────────────────────────┘
        ↓
License Fact Extraction (Step 7)
        ↓
Evidence Validation & Quality Engine (Step 8)
        ↓
License Knowledge Profile Consolidation (Step 9)
        ↓
Source Monitoring & Change Detection (Step 12)
        ↓
License Entitlement + Position Engine (Step 14)
        ↓
License Intelligence Audit + Quality Dashboard (Step 15)
        ↓
Interactive Streamlit Quality Scores, Evidence Lineage, Timelines & Local Discovery
```

---

## Step 16: Real Windows Endpoint Application Discovery

The **Windows Endpoint Collector** (`endpoint-agent/`) performs safe, read-only discovery of software installed on physical Windows machines:
1. **64-bit Registry**: `HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall` (KEY_WOW64_64KEY).
2. **32-bit Registry**: `HKLM\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall` (KEY_WOW64_32KEY).
3. **Current User Registry**: `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall`.
4. **Modern Windows Packages**: AppX / MSIX package enumeration via read-only PowerShell commands.

### Safety & Security Guarantees
- **100% Read-Only**: The agent only reads registry keys and packages.
- **No Command Execution**: `UninstallString` and other registry command lines are captured strictly as text metadata and are **never executed**.
- **No System Modifications**: Does not modify Windows system files, services, firewall, registry, or installed applications.
- **No Sensitive Data**: Never accesses browser history, personal files, documents, or credentials.
- **Auditable & Offline Fallback**: Generates `inventory_<timestamp>.json` locally before transmitting to the backend.

---

## 16-Step Architecture Roadmap

| Step | Milestone | Status |
| :--- | :--- | :--- |
| **STEP 1** | **Project Initialization & Architecture** | **Completed** |
| **STEP 2** | **License Source Registry** | **Completed** |
| **STEP 3** | **Automatic Official Source Discovery** | **Completed** |
| **STEP 4** | **Official Web Content Collector** | **Completed** |
| **STEP 5** | **Official PDF / Document Collector** | **Completed** |
| **STEP 6** | **Optional Vendor API Collector** | **Completed** |
| **STEP 7** | **License Fact Extraction Engine** | **Completed** |
| **STEP 8** | **Evidence Validation + Quality Engine** | **Completed** |
| **STEP 9** | **License Knowledge Consolidation Engine** | **Completed** |
| **STEP 10** | **Automatic Research Orchestrator** | **Completed** |
| **STEP 11** | **Application Intelligence Catalog + Batch Engine** | **Completed** |
| **STEP 12** | **Automated Source Monitoring + Change Detection** | **Completed** |
| **STEP 13** | **Application Detection + Identity Resolution** | **Completed** |
| **STEP 14** | **License Entitlement + License Position Engine** | **Completed** |
| **STEP 15** | **License Intelligence Audit + Quality Dashboard** | **Completed** |
| **STEP 16** | **Real Windows Endpoint Application Discovery** | **Completed** |
| **STEP 17** | **Intelligent License Research Prioritization Engine** | **Completed** |

---

## Getting Started & Verification

### 1. Run Complete Test Suite (133 passing tests)
```bash
cd commercial-license-intelligence
pytest
```

### 2. Run Local Windows Endpoint Discovery (Dry-Run)
```bash
python collector.py --dry-run
```

### 3. Evaluate Inventory & Prioritize Research Queue
```bash
# Evaluate applications and populate deterministic research queue
curl -X POST http://127.0.0.1:8000/api/research/prioritize/inventory
```

### 4. Start Backend Server
```bash
python run_backend.py
```
Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 5. Start Streamlit Verification Console
```bash
streamlit run frontend/streamlit/app.py --server.port 8501
```
Interactive Console: [http://127.0.0.1:8501](http://127.0.0.1:8501)
