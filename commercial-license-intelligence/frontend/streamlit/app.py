"""
Commercial License Intelligence - Enterprise Application.
Workflow:
  Start Screen: [ 📁 Upload Software Inventory ] OR [ 🖥 Scan This Computer ]
        ↓                                                    ↓
  File Parser / Preview                                Live 9-Stage System Scan
        ↓                                                    ↓
  Raw Ingest                                           Local Normalization
        └────────────────────────┬───────────────────────────┘
                                 ↓
                    License Intelligence Pipeline
                                 ↓
                    Unified Results Dashboard
                    (Metrics, 5 Tiers, Review Queue, Exports)
"""

import sys
import os
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

import streamlit as st
import pandas as pd

# Add repo root to python path
repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from backend.database.connection import SessionLocal
from backend.models.inventory_upload import InventoryUpload
from backend.inventory.upload.upload_job_manager import UploadJobManager

from frontend.streamlit.components.ui.elements import inject_enterprise_css
from frontend.streamlit.components.inventory.source_selector import render_source_selector
from frontend.streamlit.components.scanner.scan_view import render_scanning_screen
from frontend.streamlit.components.dashboard.results_view import render_results_dashboard

# =========================================================================
# PAGE CONFIGURATION & ENTERPRISE DARK STYLING
# =========================================================================
st.set_page_config(
    page_title="Commercial License Intelligence",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_enterprise_css()

# =========================================================================
# STATE INITIALIZATION
# =========================================================================
if "flow_state" not in st.session_state:
    st.session_state["flow_state"] = "SELECT_SOURCE"  # "SELECT_SOURCE", "SCANNING", "PROCESSING", "RESULTS"

if "active_upload_id" not in st.session_state:
    st.session_state["active_upload_id"] = None

if "active_scan_id" not in st.session_state:
    st.session_state["active_scan_id"] = None

if "analysis_source_type" not in st.session_state:
    st.session_state["analysis_source_type"] = "FILE_UPLOAD"  # "FILE_UPLOAD" or "LOCAL_SCAN"

if "job_start_time" not in st.session_state:
    st.session_state["job_start_time"] = None


# =========================================================================
# DATABASE HELPERS
# =========================================================================
def list_all_uploads() -> List[Dict[str, Any]]:
    """Lists completed historical uploads and local scans."""
    db = SessionLocal()
    try:
        records = db.query(InventoryUpload).order_by(InventoryUpload.created_at.desc()).limit(20).all()
        return [
            {
                "upload_id": r.upload_id,
                "file_name": r.file_name,
                "total_rows": r.total_rows,
                "status": r.status,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "N/A",
            }
            for r in records
        ]
    finally:
        db.close()


# =========================================================================
# PROCESSING SCREEN FOR FILE UPLOADS
# =========================================================================
def render_processing_screen():
    """Renders real-time processing status for bulk file uploads."""
    upload_id = st.session_state.get("active_upload_id")
    if not upload_id:
        st.session_state["flow_state"] = "SELECT_SOURCE"
        st.rerun()

    st.markdown("""
        <div class="brand-header">
            <div class="brand-pill">⚙ Processing Inventory</div>
            <div class="brand-title">LICENSE INTELLIGENCE ENGINE RUNNING</div>
            <div class="brand-subtitle">Analyzing software inventory against commercial licensing catalog and primary sources...</div>
        </div>
    """, unsafe_allow_html=True)

    job_mgr = UploadJobManager.get_instance()
    job_status = job_mgr.get_job_status(upload_id) or {}

    status = job_status.get("status", "PROCESSING")
    total_rows = job_status.get("total_rows", 0)
    processed_rows = job_status.get("processed_rows", 0)
    progress_pct = job_status.get("progress_percent", 0)

    start_t = st.session_state.get("job_start_time", time.time())
    elapsed_secs = int(time.time() - start_t)
    mins = elapsed_secs // 60
    secs = elapsed_secs % 60
    elapsed_str = f"{mins:02d}:{secs:02d}"

    st.progress(progress_pct / 100.0)

    col_info_1, col_info_2 = st.columns([2, 1])
    with col_info_1:
        if processed_rows > 0 and total_rows > 0:
            st.write(f"**Processing applications:** {processed_rows:,} / {total_rows:,} completed ({progress_pct}%)")
        else:
            st.write("**Processing applications...** Initializing intelligence engine")
    with col_info_2:
        st.write(f"**Elapsed Time:** `{elapsed_str}`")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### Processing Stages")

    # Dynamic stages checklist
    st.markdown('<div class="pipeline-step pipeline-step-done"><div class="step-icon-circle step-icon-completed">✓</div><div class="step-text">1. File uploaded and validated</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="pipeline-step pipeline-step-done"><div class="step-icon-circle step-icon-completed">✓</div><div class="step-text">2. Inventory parsed into data records</div></div>', unsafe_allow_html=True)

    if progress_pct >= 10:
        st.markdown('<div class="pipeline-step pipeline-step-done"><div class="step-icon-circle step-icon-completed">✓</div><div class="step-text">3. Applications normalized & deduplicated</div></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="pipeline-step pipeline-step-active"><div class="step-icon-circle step-icon-running">◌</div><div class="step-text step-active-text">3. Applications normalizing...</div></div>', unsafe_allow_html=True)

    if progress_pct >= 50:
        st.markdown('<div class="pipeline-step pipeline-step-done"><div class="step-icon-circle step-icon-completed">✓</div><div class="step-text">4. Matched canonical application intelligence</div></div>', unsafe_allow_html=True)
    elif progress_pct >= 10:
        st.markdown('<div class="pipeline-step pipeline-step-active"><div class="step-icon-circle step-icon-running">◌</div><div class="step-text step-active-text">4. Matching application intelligence...</div></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="pipeline-step"><div class="step-icon-circle step-icon-pending">○</div><div class="step-text">4. Match application intelligence</div></div>', unsafe_allow_html=True)

    if progress_pct >= 90:
        st.markdown('<div class="pipeline-step pipeline-step-done"><div class="step-icon-circle step-icon-completed">✓</div><div class="step-text">5. Licensing terms & obligations resolved</div></div>', unsafe_allow_html=True)
    elif progress_pct >= 50:
        st.markdown('<div class="pipeline-step pipeline-step-active"><div class="step-icon-circle step-icon-running">◌</div><div class="step-text step-active-text">5. Resolving licensing terms...</div></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="pipeline-step"><div class="step-icon-circle step-icon-pending">○</div><div class="step-text">5. Resolve licensing terms</div></div>', unsafe_allow_html=True)

    if status == "COMPLETED":
        st.markdown('<div class="pipeline-step pipeline-step-done"><div class="step-icon-circle step-icon-completed">✓</div><div class="step-text">6. Results generated</div></div>', unsafe_allow_html=True)
        time.sleep(0.5)
        st.session_state["flow_state"] = "RESULTS"
        st.rerun()
    elif status == "FAILED":
        err_msg = job_status.get("error_message") or "An unexpected error occurred during processing."
        st.error(f"Processing failed: {err_msg}")
        if st.button("Return to Start Screen", key="btn_err_return"):
            st.session_state["flow_state"] = "SELECT_SOURCE"
            st.rerun()
    else:
        time.sleep(0.6)
        st.rerun()


# =========================================================================
# MAIN ORCHESTRATOR
# =========================================================================
def main():
    state = st.session_state.get("flow_state", "SELECT_SOURCE")

    if state == "SELECT_SOURCE" or state == "UPLOAD":
        past_jobs = list_all_uploads()
        render_source_selector(past_uploads=past_jobs)

    elif state == "SCANNING":
        render_scanning_screen()

    elif state == "PROCESSING":
        render_processing_screen()

    elif state == "RESULTS":
        upload_id = st.session_state.get("active_upload_id")
        if not upload_id:
            st.session_state["flow_state"] = "SELECT_SOURCE"
            st.rerun()
        render_results_dashboard(upload_id)

    else:
        st.session_state["flow_state"] = "SELECT_SOURCE"
        st.rerun()


if __name__ == "__main__":
    main()
