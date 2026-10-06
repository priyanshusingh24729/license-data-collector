"""
Dedicated System Software Scan View.
Renders live animated progress bar, 9-stage pipeline checklist, real-time metrics, and handles auto-transition.
"""

import streamlit as st
import time
from typing import Dict, Any, Optional

from frontend.streamlit.services.scanner_service import ScannerService
from frontend.streamlit.components.ui.elements import render_metric_card, render_pipeline_step

PIPELINE_STEPS_DEF = [
    ("detect_os", "Detect Operating System"),
    ("scan_registry", "Scan Windows Registry"),
    ("detect_apps", "Detect Installed Applications"),
    ("extract_versions", "Extract Application Versions"),
    ("identify_publishers", "Identify Software Publishers"),
    ("normalize_names", "Normalize Application Names"),
    ("remove_duplicates", "Remove Duplicates"),
    ("run_license_intelligence", "Run License Intelligence"),
    ("generate_report", "Generate Final Report"),
]


def render_scanning_screen():
    """Renders the dedicated live scanning dashboard."""
    # -------------------------------------------------------------
    # 1. COMPACT ENTERPRISE HEADER
    # -------------------------------------------------------------
    st.markdown("""
        <div class="compact-header">
            <div class="compact-header-left">
                <div class="card-icon-wrap" style="width: 36px; height: 36px; font-size: 18px; margin-bottom: 0; color: #38bdf8;">⚖️</div>
                <div>
                    <div class="compact-header-title">Commercial License Intelligence</div>
                    <div style="font-size: 12px; color: #94a3b8; margin-top: 1px;">Enterprise Software Asset & License Compliance</div>
                </div>
            </div>
            <div class="compact-status-badge">
                <span class="status-dot-pulse"></span>
                <span>Current status: Scanning Software Inventory</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Initialize or fetch active scan_id
    active_scan_id = st.session_state.get("active_scan_id")
    if not active_scan_id:
        with st.spinner("Initializing endpoint scanner..."):
            start_resp = ScannerService.start_scan()
            active_scan_id = start_resp.get("scan_id")
            st.session_state["active_scan_id"] = active_scan_id
            st.session_state["scan_start_time"] = time.time()
            st.rerun()

    # Query latest scan status
    scan_status = ScannerService.get_scan_status(active_scan_id)
    if not scan_status:
        st.warning("Connecting to endpoint scanner...")
        time.sleep(0.5)
        st.rerun()
        return

    status = scan_status.get("status", "RUNNING")
    progress = scan_status.get("progress", 0)
    current_step = scan_status.get("current_step", "Scanning System")
    step_statuses = scan_status.get("step_statuses", {})
    stats = scan_status.get("statistics", {})
    upload_id = scan_status.get("upload_id")
    dev_info = scan_status.get("device_info", {})

    # -------------------------------------------------------------
    # 2. TOP SUMMARY SECTION: 4 Responsive Statistic Cards
    # -------------------------------------------------------------
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_metric_card(
            label="Applications Detected",
            value=f"{stats.get('applications_detected', 0):,}",
            icon="📦",
            color="#38bdf8",
            meta_text="Raw detections"
        )
    with c2:
        render_metric_card(
            label="Applications Processed",
            value=f"{stats.get('applications_processed', 0):,}",
            icon="⚙️",
            color="#f8fafc",
            meta_text="Through intelligence engine"
        )
    with c3:
        render_metric_card(
            label="Duplicates Removed",
            value=f"{stats.get('duplicates_removed', 0):,}",
            icon="🧹",
            color="#94a3b8",
            meta_text="Unique installations"
        )
    with c4:
        render_metric_card(
            label="License Review Required",
            value=f"{stats.get('license_review_required', 0):,}",
            icon="🔍",
            color="#f59e0b",
            meta_text="Tier 4 resolution queue"
        )

    # -------------------------------------------------------------
    # 3. DEDICATED SCAN PROGRESS SECTION
    # -------------------------------------------------------------
    dev_os = dev_info.get("operating_system", "Windows 11")
    dev_node = dev_info.get("device_name", "Local PC")

    st.markdown(f"""
        <div class="scan-progress-card">
            <div class="scan-progress-title-row">
                <div>
                    <div class="scan-progress-main-title">
                        <span>SCANNING SOFTWARE INVENTORY</span>
                    </div>
                    <div class="scan-progress-sub">
                        Detecting installed applications and analyzing licensing information.
                    </div>
                </div>
                <div class="scan-progress-pct-badge">{progress}% Complete</div>
            </div>
            <div class="scan-step-indicator">
                <span class="scan-step-name">Active Task: <span style="color: #38bdf8; font-weight: 600;">{current_step}</span></span>
            </div>
    """, unsafe_allow_html=True)

    st.progress(progress / 100.0)

    st.markdown(f"""
            <div class="scan-meta-pill-row">
                <span class="scan-meta-pill">💻 Target Host: <b>{dev_node}</b></span>
                <span class="scan-meta-pill">🪟 Operating System: <b>{dev_os}</b></span>
                <span class="scan-meta-pill">🔑 Scan ID: <code>{active_scan_id}</code></span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # -------------------------------------------------------------
    # 4. DISCOVERY & INTELLIGENCE PIPELINE (2-Column Desktop Grid)
    # -------------------------------------------------------------
    st.markdown("""
        <div style="display: flex; align-items: center; justify-content: space-between; margin: 18px 0 10px 0;">
            <div style="font-size: 13px; font-weight: 700; color: #94a3b8; letter-spacing: 0.8px; text-transform: uppercase;">
                Discovery & Intelligence Pipeline
            </div>
            <div style="font-size: 11.5px; color: #64748b;">
                9-Stage Automated Pipeline
            </div>
        </div>
    """, unsafe_allow_html=True)

    col_pipe_left, col_pipe_right = st.columns(2)
    halfway = 5

    with col_pipe_left:
        for idx, (step_id, step_name) in enumerate(PIPELINE_STEPS_DEF[:halfway], start=1):
            st_state = step_statuses.get(step_id, "pending")
            render_pipeline_step(idx, step_name, st_state)

    with col_pipe_right:
        for idx, (step_id, step_name) in enumerate(PIPELINE_STEPS_DEF[halfway:], start=halfway + 1):
            st_state = step_statuses.get(step_id, "pending")
            render_pipeline_step(idx, step_name, st_state)

    # -------------------------------------------------------------
    # 5. SECONDARY SCAN CONTROLS (Discreet / Non-Competing)
    # -------------------------------------------------------------
    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
    with st.expander("⚙ Scan Controls & Alternate Actions", expanded=False):
        c_sec1, c_sec2 = st.columns(2)
        with c_sec1:
            if st.button("Cancel Scan & Return Home", key="btn_cancel_scan_sec", use_container_width=True):
                st.session_state["flow_state"] = "SELECT_SOURCE"
                st.session_state["active_scan_id"] = None
                st.rerun()
        with c_sec2:
            if st.button("📁 Upload File Instead", key="btn_switch_to_upload_sec", use_container_width=True):
                st.session_state["flow_state"] = "SELECT_SOURCE"
                st.session_state["active_scan_id"] = None
                st.rerun()

    # -------------------------------------------------------------
    # 6. STATE TRANSITIONS
    # -------------------------------------------------------------
    if status == "COMPLETED" and upload_id:
        st.success("✓ Scan completed! Transitioning to License Intelligence Results...")
        st.session_state["active_upload_id"] = upload_id
        st.session_state["flow_state"] = "RESULTS"
        st.session_state["analysis_source_type"] = "LOCAL_SCAN"
        st.session_state["scan_statistics"] = stats
        st.session_state["device_meta"] = dev_info
        time.sleep(0.8)
        st.rerun()

    elif status == "FAILED":
        err = scan_status.get("error_message") or "An error occurred during local endpoint discovery."
        st.error(f"Scan failed: {err}")
        c_r1, c_r2 = st.columns(2)
        with c_r1:
            if st.button("🔄 Retry Scan", key="btn_retry_scan", use_container_width=True):
                st.session_state["active_scan_id"] = None
                st.rerun()
        with c_r2:
            if st.button("📁 Upload Inventory Instead", key="btn_err_fallback_upload", use_container_width=True):
                st.session_state["flow_state"] = "UPLOAD"
                st.rerun()

    else:
        # Polling sleep for smooth real-time update
        time.sleep(0.4)
        st.rerun()
