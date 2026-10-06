"""
Inventory Source Selector (Start Screen).
Provides dual entry points: 'Upload Software Inventory' (CSV/XLSX) and 'Scan This Computer' (Local Endpoint Discovery).
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, List, Optional
import time

from frontend.streamlit.services.scanner_service import ScannerService
from backend.inventory.upload.upload_parser import UploadFileParser
from backend.inventory.upload.upload_job_manager import UploadJobManager


def format_file_size(size_in_bytes: int) -> str:
    """Formats file size into human readable string."""
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    elif size_in_bytes < 1024 * 1024:
        return f"{size_in_bytes / 1024:.1f} KB"
    else:
        return f"{size_in_bytes / (1024 * 1024):.1f} MB"


def render_source_selector(past_uploads: Optional[List[Dict[str, Any]]] = None):
    """Renders the improved enterprise start screen with balanced dual inventory input cards."""
    # Top branding header
    st.markdown("""
        <div class="brand-header">
            <div class="brand-pill">⚡ Software Asset & License Intelligence</div>
            <div class="brand-title">COMMERCIAL LICENSE INTELLIGENCE</div>
            <div class="brand-subtitle">
                Analyze software inventory, identify licensing requirements, and detect commercial applications.
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Gather local device metadata for Card 2
    device_info = ScannerService.get_device_info()
    os_display = device_info.get("operating_system", "Windows")
    node_display = device_info.get("device_name", "Local Machine")

    # Side-by-Side Cards with Subtle OR divider
    c_card1, c_div, c_card2 = st.columns([1.0, 0.08, 1.0], gap="medium")

    # -------------------------------------------------------------
    # CARD 1: Upload Software Inventory
    # -------------------------------------------------------------
    with c_card1:
        with st.container(border=True):
            st.markdown("""
                <div>
                    <div class="card-icon-wrap" style="color: #38bdf8;">📁</div>
                    <div class="card-title">Upload Software Inventory</div>
                    <div class="card-description">
                        Upload an existing software inventory file from your IT asset management tool or spreadsheet.
                    </div>
                    <div style="font-size: 11.5px; color: #64748b; margin-bottom: 14px; font-weight: 500;">
                        SUPPORTED FORMATS: <span style="color: #cbd5e1; font-weight: 600;">CSV, XLSX, XLS</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            uploaded_file = st.file_uploader(
                "Choose a software inventory file",
                type=["csv", "xlsx", "xls"],
                label_visibility="collapsed",
                key="start_screen_file_uploader"
            )

            if uploaded_file is not None:
                file_bytes = uploaded_file.getvalue()
                file_name = uploaded_file.name
                file_size_str = format_file_size(len(file_bytes))

                try:
                    preview_data = UploadFileParser.preview_upload(file_bytes, file_name)
                    df_parsed, ftype = UploadFileParser.parse_file_to_dataframe(file_bytes, file_name)
                    total_rows = preview_data["total_rows"]
                    auto_map = preview_data["column_mapping"]
                    confidence = preview_data["confidence"]

                    st.markdown(f"""
                        <div style="background: #111a2e; border: 1px solid #1e293b; border-radius: 8px; padding: 10px 14px; margin-top: 10px; margin-bottom: 12px; font-size: 12.5px;">
                            <div style="font-weight: 600; color: #e2e8f0;">✓ {file_name}</div>
                            <div style="color: #94a3b8; font-size: 11.5px; margin-top: 2px;">
                                {file_size_str} &nbsp;|&nbsp; {ftype} &nbsp;|&nbsp; <span style="color: #38bdf8; font-weight: 600;">{total_rows:,} rows</span>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

                    final_mapping = dict(auto_map)
                    if not auto_map.get("application") or confidence == "LOW":
                        cols = list(df_parsed.columns)
                        sel_app = st.selectbox("Confirm Application Column", options=cols, key="src_fallback_app_col")
                        final_mapping["application"] = sel_app

                    if st.button("Upload Inventory & Run Intelligence", type="primary", use_container_width=True, key="btn_run_uploaded"):
                        job_mgr = UploadJobManager.get_instance()
                        upload_id = job_mgr.create_and_submit_job(
                            file_name=file_name,
                            file_type=ftype,
                            df=df_parsed,
                            column_mapping=final_mapping,
                        )
                        st.session_state["active_upload_id"] = upload_id
                        st.session_state["analysis_source_type"] = "FILE_UPLOAD"
                        st.session_state["source_file_name"] = file_name
                        st.session_state["job_start_time"] = time.time()
                        st.session_state["flow_state"] = "PROCESSING"
                        st.rerun()

                except Exception as ex:
                    st.error(f"Could not parse file: {ex}")
            else:
                st.caption("Drag and drop your spreadsheet or click browse above.")

    # -------------------------------------------------------------
    # SUBTLE OR DIVIDER
    # -------------------------------------------------------------
    with c_div:
        st.markdown("""
            <div class="or-divider-wrap">
                <div class="or-divider-line"></div>
                <span class="or-badge">OR</span>
            </div>
        """, unsafe_allow_html=True)

    # -------------------------------------------------------------
    # CARD 2: Scan This Computer
    # -------------------------------------------------------------
    with c_card2:
        with st.container(border=True):
            st.markdown(f"""
                <div>
                    <div class="card-icon-wrap" style="color: #10b981;">🖥</div>
                    <div class="card-title">Scan This Computer</div>
                    <div class="card-description">
                        Automatically detect installed applications on this Windows computer via registry hives, AppX packages, and Winget.
                    </div>
                    <div class="device-info-box">
                        <div class="device-info-row">
                            <span class="device-info-label">Operating System</span>
                            <span class="device-info-val">{os_display}</span>
                        </div>
                        <div class="device-info-row">
                            <span class="device-info-label">Device Name</span>
                            <span class="device-info-val">{node_display}</span>
                        </div>
                        <div class="device-info-row">
                            <span class="device-info-label">Scan Source</span>
                            <span class="device-info-val">Local Machine</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            btn_start_scan = st.button("Start System Scan", type="primary", use_container_width=True, key="btn_start_system_scan")
            if btn_start_scan:
                st.session_state["flow_state"] = "SCANNING"
                st.session_state["active_scan_id"] = None
                st.session_state["scan_start_time"] = time.time()
                st.session_state["analysis_source_type"] = "LOCAL_SCAN"
                st.session_state["device_meta"] = device_info
                st.rerun()

    # Historical Uploads Drawer
    if past_uploads:
        st.markdown("<div style='margin-top: 1.25rem;'></div>", unsafe_allow_html=True)
        with st.expander("📂 Access Previous Software Inventory Analyses", expanded=False):
            job_opts = [
                f"{p.get('file_name', 'Scan')} ({p.get('total_rows', 0):,} rows — {p.get('created_at', 'N/A')}) [ID: {p.get('upload_id')}]"
                for p in past_uploads
            ]
            chosen_job_idx = st.selectbox(
                "Select Past Analysis",
                range(len(job_opts)),
                format_func=lambda x: job_opts[x],
                key="past_job_select_widget"
            )
            if st.button("Open Selected Analysis", key="btn_open_selected_past", use_container_width=True):
                chosen_id = past_uploads[chosen_job_idx]["upload_id"]
                st.session_state["active_upload_id"] = chosen_id
                st.session_state["analysis_source_type"] = "LOCAL_SCAN" if "Local_Scan" in past_uploads[chosen_job_idx].get("file_name", "") else "FILE_UPLOAD"
                st.session_state["flow_state"] = "RESULTS"
                st.rerun()
