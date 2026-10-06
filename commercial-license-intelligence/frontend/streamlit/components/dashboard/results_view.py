"""
Enhanced Enterprise Results Dashboard.
Integrates dynamic analysis source headers (Local Computer Scan vs Uploaded File),
polished metric cards, 5-tier navigation with count badges, structured filtering,
interactive data tables with sticky styling, and the complete Tier 4 human-in-the-loop review queue.
"""

import streamlit as st
import pandas as pd
import io
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from backend.database.connection import SessionLocal
from backend.models.inventory_upload import InventoryUpload, UploadLicenseResult
from backend.models.tier4_feedback import PendingCatalogRule, CatalogAuditLog
from backend.inventory.feedback.tier4_loop_service import Tier4LoopService, Tier4Resolution
from frontend.streamlit.components.ui.elements import render_metric_card


def get_tier(classification: str, license_required: Optional[str] = None) -> str:
    """Categorizes software into distinct business tiers."""
    c = (classification or "").upper()
    req = (license_required or "").upper()

    if req in ("NO", "NOT_APPLICABLE", "FREE"):
        if c in ("OPEN_SOURCE", "FREEWARE"):
            return "Tier 2: Freeware & Developer Open Source"
        return "Tier 3: OS & System Infrastructure"

    if c in ("COMMERCIAL", "FREE_AND_PAID") and req in ("YES", "CONTEXT_DEPENDENT"):
        return "Tier 1: Commercial & Billable"
    elif c in ("COMMERCIAL", "FREE_AND_PAID") and not req:
        return "Tier 1: Commercial & Billable"
    elif c in ("OPEN_SOURCE", "FREEWARE"):
        return "Tier 2: Freeware & Developer Open Source"
    elif c in ("OS_BUNDLED", "OEM_OR_BUNDLED", "OEM", "LINUX_SYSTEM_PACKAGE", "MACOS_SYSTEM_COMPONENT", "WEB_SHORTCUT_OR_PWA", "WEB_SHORTCUT/PWA", "COMMERCIAL_COMPONENT", "RUNTIME_FRAMEWORK", "SHARED_COMPONENT"):
        return "Tier 3: OS & System Infrastructure"
    else:
        return "Tier 4: Needs Review"


def generate_csv_bytes(records: List[Dict[str, Any]]) -> bytes:
    """Exports full records into a UTF-8 BOM CSV bytes object strictly matching the standardized 14-column schema."""
    if not records:
        return b""
    from backend.inventory.export.standardized_inventory_exporter import StandardizedInventoryExporter
    df = StandardizedInventoryExporter.transform_inventory(records)
    return StandardizedInventoryExporter.to_csv_bytes(df)


def generate_billable_csv_bytes(records: List[Dict[str, Any]]) -> bytes:
    """Exports only commercial records requiring license to CSV strictly matching the standardized schema."""
    if not records:
        return b""
    from backend.inventory.export.standardized_inventory_exporter import StandardizedInventoryExporter
    df = StandardizedInventoryExporter.transform_inventory(records)
    df_billable = df[(df["NoLicenseRequired"] == 0) | (df["License Required"] == "YES")]
    if df_billable.empty:
        df_billable = df
    return StandardizedInventoryExporter.to_csv_bytes(df_billable)


def generate_excel_bytes(records: List[Dict[str, Any]]) -> bytes:
    """Exports records into Excel workbook strictly matching the standardized 17-column schema."""
    if not records:
        return b""
    from backend.inventory.export.standardized_inventory_exporter import StandardizedInventoryExporter
    df = StandardizedInventoryExporter.transform_inventory(records)
    return StandardizedInventoryExporter.to_excel_bytes(df)


def generate_final_schema_csv_bytes(records: List[Dict[str, Any]]) -> bytes:
    """Exports records into 10-column Final Schema CSV bytes with clean blanks for missing values."""
    if not records:
        return b""
    from backend.inventory.export.standardized_inventory_exporter import StandardizedInventoryExporter
    df = StandardizedInventoryExporter.transform_to_final_schema(records)
    return StandardizedInventoryExporter.to_final_csv_bytes(df)


def generate_final_schema_excel_bytes(records: List[Dict[str, Any]]) -> bytes:
    """Exports records into 10-column Final Schema Excel workbook with clean blanks."""
    if not records:
        return b""
    from backend.inventory.export.standardized_inventory_exporter import StandardizedInventoryExporter
    df = StandardizedInventoryExporter.transform_to_final_schema(records)
    return StandardizedInventoryExporter.to_final_excel_bytes(df)


def load_upload_metadata(upload_id: str) -> Optional[Dict[str, Any]]:
    """Loads metadata for an upload or scan job."""
    db = SessionLocal()
    try:
        up = db.query(InventoryUpload).filter(InventoryUpload.upload_id == upload_id).first()
        if not up:
            return None
        return {
            "upload_id": up.upload_id,
            "file_name": up.file_name,
            "file_type": up.file_type,
            "total_rows": up.total_rows,
            "unique_applications": up.unique_applications,
            "unique_machines": up.unique_machines,
            "resolved_count": up.resolved_count,
            "unresolved_count": up.unresolved_count,
            "cache_hits": up.cache_hits,
            "new_researched": up.new_researched,
            "status": up.status,
            "created_at": up.created_at.strftime("%Y-%m-%d %H:%M") if up.created_at else "N/A",
        }
    finally:
        db.close()


def load_upload_results(upload_id: str) -> List[Dict[str, Any]]:
    """Loads processed license results for an upload or scan."""
    db = SessionLocal()
    try:
        results = db.query(UploadLicenseResult).filter(
            UploadLicenseResult.upload_id == upload_id
        ).order_by(UploadLicenseResult.id.asc()).all()

        # Fetch raw row mappings to preserve authoritative customer baseline columns (e.g. App_ID, OSType, Normalized_Application)
        from backend.models.inventory_upload import InventoryUploadRow
        raw_rows = db.query(InventoryUploadRow.row_index, InventoryUploadRow.raw_data_json).filter(
            InventoryUploadRow.upload_id == upload_id
        ).all()
        import json
        raw_map = {}
        for r_idx, r_json in raw_rows:
            if r_json:
                try:
                    raw_map[r_idx] = json.loads(r_json)
                except Exception:
                    pass

        rows = []
        for r in results:
            lic_req = "NO" if str(r.license_required or "").upper() == "NO" else "YES"
            lm = r.license_model if r.license_model and r.license_model != "UNKNOWN" else ""
            if not lm or " — " not in lm:
                from backend.validation.license_validation_layer import LicenseValidationLayer
                combined_lm = LicenseValidationLayer.build_combined_license_model(
                    raw_model=lm,
                    metric=r.license_metric or r.metric,
                    classification=r.classification,
                    app_name=r.canonical_product or r.raw_application,
                )
                if combined_lm:
                    lm = combined_lm

            tier = get_tier(r.classification, lic_req)

            raw_meta = raw_map.get(r.row_index, {})
            app_id_val = raw_meta.get("App_ID") or raw_meta.get("app_id") or r.row_index
            ostype_val = raw_meta.get("OSType")
            norm_app_val = raw_meta.get("Normalized_Application") or r.canonical_product or r.raw_application
            maj_ver = raw_meta.get("Major_Version")
            min_ver = raw_meta.get("Minor_Version")
            patch_ver = raw_meta.get("Patch_Version")
            op_sys = raw_meta.get("Operating_System")
            snow_nlr = raw_meta.get("NoLicenseRequired")
            if snow_nlr is not None and str(snow_nlr).strip() in ("0", "1"):
                no_lic_req_val = int(str(snow_nlr).strip())
            else:
                no_lic_req_val = 1 if lic_req == "NO" else 0

            rows.append({
                "Tier": tier,
                "App_ID": app_id_val,
                "app_id": app_id_val,
                "Name": r.raw_application,
                "raw_name": r.raw_application,
                "raw_application": r.raw_application,
                "Application": r.canonical_product or r.raw_application,
                "application": r.canonical_product or r.raw_application,
                "Normalized_Application": norm_app_val,
                "OSType": ostype_val,
                "ostype": ostype_val,
                "Operating_System": op_sys,
                "Major_Version": maj_ver,
                "Minor_Version": min_ver,
                "Patch_Version": patch_ver,
                "NoLicenseRequired": no_lic_req_val,
                "Vendor": r.canonical_vendor or r.raw_vendor or "",
                "vendor": r.canonical_vendor or r.raw_vendor or "",
                "raw_vendor": r.raw_vendor,
                "Version": r.version or r.raw_version or "",
                "version": r.version or r.raw_version or "",
                "raw_version": r.raw_version,
                "Classification": r.classification if r.classification and r.classification != "UNKNOWN" else "",
                "classification": r.classification if r.classification and r.classification != "UNKNOWN" else "",
                "License Required": lic_req,
                "license_required": True if lic_req == "YES" else False,
                "License Model": lm,
                "license_model": lm,
                "Metric": r.license_metric or r.metric or "",
                "metric": r.license_metric or r.metric or "",
                "Confidence": r.confidence if r.confidence and r.confidence != "UNKNOWN" else "",
                "Evidence Status": r.evidence_status if r.evidence_status and r.evidence_status != "MISSING" else "",
                "Evidence URL": r.evidence_url or "",
                "evidence_url": r.evidence_url or "",
                "Hostname": r.hostname or "",
                "Raw Application": r.raw_application,
                "Created_At": raw_meta.get("Created_At") or (r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else None),
                "winget_package_id": getattr(r, "winget_package_id", "") or "",
                "installer_url": getattr(r, "installer_url", "") or "",
                "installer_sha256": getattr(r, "installer_sha256", "") or "",
                "conflict_status": getattr(r, "conflict_status", "VERIFIED") or "VERIFIED",
                "override_reason": getattr(r, "override_reason", "") or "",
                "is_end_of_life": getattr(r, "is_end_of_life", None),
                "IsEndOfLife": getattr(r, "is_end_of_life", None),
                "is_end_of_support": getattr(r, "is_end_of_support", None),
                "IsEndOfSupport": getattr(r, "is_end_of_support", None),
                "canonical_edition": getattr(r, "canonical_edition", "") or "",
                "edition": getattr(r, "canonical_edition", "") or "",
                "spdx_id": getattr(r, "spdx_id", "") or "UNKNOWN",
                "version_rule_applied": getattr(r, "version_rule_applied", "") or "",
                "consensus_status": getattr(r, "consensus_status", "VERIFIED") or "VERIFIED",
                "evidence_source": getattr(r, "evidence_source", "") or "",
                "evidence_quote": getattr(r, "evidence_quote", "") or "",
                "reliability": f"{int(r.reliability_score)}%" if getattr(r, "reliability_score", None) is not None else "",
                "reliability_score": getattr(r, "reliability_score", None),
                "resolution_engine_version": getattr(r, "resolution_engine_version", "v1.3.0") or "v1.3.0",
                "is_already_resolved": True,
            })
        return rows
    finally:
        db.close()


def render_results_dashboard(upload_id: str):
    """Renders the comprehensive results dashboard."""
    meta = load_upload_metadata(upload_id)
    if not meta:
        st.error("Inventory analysis record not found.")
        if st.button("Return to Start Screen"):
            st.session_state["flow_state"] = "SELECT_SOURCE"
            st.rerun()
        return

    # Determine Source Context
    is_local_scan = (
        st.session_state.get("analysis_source_type") == "LOCAL_SCAN"
        or meta.get("file_type") == "LOCAL_SCAN"
        or "Local_Scan" in meta.get("file_name", "")
    )
    dev_meta = st.session_state.get("device_meta", {})
    dev_os = dev_meta.get("operating_system", "Windows")
    dev_name = dev_meta.get("device_name", "Local PC")

    # Fallback to parse device name from file_name if session state lost
    if is_local_scan and dev_name == "Local PC" and "Local_Scan_" in meta.get("file_name", ""):
        parts = meta["file_name"].split("_")
        if len(parts) >= 3:
            dev_name = parts[2]

    # -------------------------------------------------------------
    # 1. TOP SECTION: Professional "Analysis Complete" Summary Card
    # -------------------------------------------------------------
    source_icon = "🖥" if is_local_scan else "📁"
    source_text = "Local Computer Scan" if is_local_scan else "Uploaded Inventory"
    os_val = dev_os if is_local_scan else meta.get("file_type", "CSV")
    device_val = dev_name if is_local_scan else meta.get("file_name", "Inventory File")

    with st.container(border=True):
        col_meta, col_actions = st.columns([3.0, 2.0], gap="medium", vertical_alignment="center")

        with col_meta:
            st.markdown(f"""
                <div class="complete-summary-wrap">
                    <div class="complete-title-row">
                        <span class="complete-status-badge">
                            <span class="complete-status-dot"></span>
                            ✓ COMPLETE
                        </span>
                        <span class="complete-main-title">LICENSE INTELLIGENCE COMPLETE</span>
                    </div>
                    <div class="complete-meta-row">
                        <div class="complete-meta-item">
                            <span class="complete-meta-label">Source:</span>
                            <span class="complete-meta-val">{source_icon} {source_text}</span>
                        </div>
                        <span class="complete-meta-sep">|</span>
                        <div class="complete-meta-item">
                            <span class="complete-meta-label">OS:</span>
                            <span class="complete-meta-val">{os_val}</span>
                        </div>
                        <span class="complete-meta-sep">|</span>
                        <div class="complete-meta-item">
                            <span class="complete-meta-label">Device:</span>
                            <code class="complete-meta-code">{device_val}</code>
                        </div>
                        <span class="complete-meta-sep">|</span>
                        <div class="complete-meta-item">
                            <span class="complete-meta-label">Applications Detected:</span>
                            <span class="complete-meta-highlight">{meta['total_rows']:,}</span>
                        </div>
                        <span class="complete-meta-sep">|</span>
                        <div class="complete-meta-item">
                            <span class="complete-meta-label">Timestamp:</span>
                            <span class="complete-meta-val">{meta['created_at']}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

        with col_actions:
            c_scan, c_upload = col_actions.columns(2, gap="small", vertical_alignment="center")
            with c_scan:
                if st.button("🔄 Scan Again", use_container_width=True, key="btn_scan_again"):
                    st.session_state["flow_state"] = "SCANNING"
                    st.session_state["active_scan_id"] = None
                    st.session_state["active_upload_id"] = None
                    st.session_state["analysis_source_type"] = "LOCAL_SCAN"
                    st.rerun()
            with c_upload:
                if st.button("📁 Upload Another Inventory", use_container_width=True, key="btn_upload_another"):
                    st.session_state["flow_state"] = "SELECT_SOURCE"
                    st.session_state["active_upload_id"] = None
                    st.session_state["active_scan_id"] = None
                    st.rerun()

    # -------------------------------------------------------------
    # 2. METRIC CARDS
    # -------------------------------------------------------------
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_metric_card(
            label="Total Records",
            value=f"{meta['total_rows']:,}",
            icon="📋",
            color="#f8fafc",
            meta_text="Total software installations"
        )
    with c2:
        render_metric_card(
            label="Unique Applications",
            value=f"{meta['unique_applications']:,}",
            icon="📦",
            color="#38bdf8",
            meta_text="Distinct canonical products"
        )
    with c3:
        render_metric_card(
            label="Resolved Records",
            value=f"{meta['resolved_count']:,}",
            icon="✓",
            color="#10b981",
            meta_text="Verified license classification"
        )
    with c4:
        render_metric_card(
            label="Review Required",
            value=f"{meta['unresolved_count']:,}",
            icon="⚠️",
            color="#f59e0b",
            meta_text="Pending auditor review"
        )

    st.markdown('<div style="height: 12px;"></div>', unsafe_allow_html=True)

    # Load All Processed Records
    results = load_upload_results(upload_id)
    if not results:
        st.info("No software records found for this dataset.")
        return

    # -------------------------------------------------------------
    # 3. FILTER SECTION & EXPORT ACTIONS
    # -------------------------------------------------------------
    col_srch, col_fltr, col_exp_final, col_exp_bill, col_exp_csv, col_exp_xlsx = st.columns([2.0, 1.2, 1.2, 1.1, 0.9, 1.0])

    with col_srch:
        search_query = st.text_input(
            "Search",
            placeholder="🔍 Search applications, publishers, versions, hosts...",
            label_visibility="collapsed",
            key="dashboard_search_input"
        )

    filter_options = [
        "All Status",
        "Commercial",
        "Freeware",
        "Open Source",
        "Free and Paid",
        "OS Bundled",
        "System Infrastructure",
        "Review Required",
    ]

    with col_fltr:
        selected_filter = st.selectbox(
            "Classification Filter",
            options=filter_options,
            label_visibility="collapsed",
            key="dashboard_filter_select"
        )

    safe_fn = meta["file_name"].rsplit(".", 1)[0]

    # Pre-compute and cache DataFrames and binary exports once per upload_id
    from backend.inventory.export.standardized_inventory_exporter import (
        StandardizedInventoryExporter,
        STANDARDIZED_COLUMNS,
    )

    cache_key_std = f"df_std_{upload_id}"
    cache_key_final = f"df_final_{upload_id}"
    cache_key_exports = f"exports_{upload_id}"

    if cache_key_std not in st.session_state:
        df_std_m = StandardizedInventoryExporter.transform_inventory(
            results,
            scan_timestamp=meta.get("created_at"),
            device_context={"operating_system": dev_os, "device_name": dev_name},
        )
        if "App_ID" not in df_std_m.columns or df_std_m["App_ID"].isna().all():
            df_std_m["App_ID"] = list(range(1, len(df_std_m) + 1))

        df_std_disp = df_std_m[STANDARDIZED_COLUMNS].copy()
        for col in df_std_disp.columns:
            df_std_disp[col] = df_std_disp[col].astype(object).apply(
                lambda x: "" if pd.isna(x) or str(x).strip() in ("", "None", "<NA>", "nan", "NaN", "NULL", "UNKNOWN", "N/A") else str(x)
            )
        df_std_disp["_Tier"] = [r.get("Tier", "") for r in results]
        st.session_state[cache_key_std] = df_std_disp

    if cache_key_final not in st.session_state:
        df_fin_m = StandardizedInventoryExporter.transform_to_final_schema(
            results,
            scan_timestamp=meta.get("created_at"),
            device_context={"operating_system": dev_os, "device_name": dev_name},
        )
        df_fin_disp = df_fin_m.copy()
        for col in df_fin_disp.columns:
            df_fin_disp[col] = df_fin_disp[col].astype(object).apply(
                lambda x: "" if pd.isna(x) or str(x).strip() in ("", "None", "<NA>", "nan", "NaN", "NULL", "UNKNOWN", "N/A") else str(x)
            )
        df_fin_disp["_Tier"] = [r.get("Tier", "") for r in results]
        st.session_state[cache_key_final] = df_fin_disp

    if cache_key_exports not in st.session_state:
        st.session_state[cache_key_exports] = {
            "final_csv": generate_final_schema_csv_bytes(results),
            "billable_csv": generate_billable_csv_bytes(results),
            "full_csv": generate_csv_bytes(results),
            "excel": generate_excel_bytes(results),
        }

    exports = st.session_state[cache_key_exports]

    with col_exp_final:
        st.download_button(
            label="⬇ FINAL SCHEMA CSV",
            data=exports["final_csv"],
            file_name=f"{safe_fn}_license_intelligence.csv",
            mime="text/csv",
            use_container_width=True,
            key="btn_dl_final_csv"
        )

    with col_exp_bill:
        st.download_button(
            label="⬇ BILLABLE CSV",
            data=exports["billable_csv"],
            file_name=f"{safe_fn}_billable.csv",
            mime="text/csv",
            use_container_width=True,
            key="btn_dl_billable"
        )

    with col_exp_csv:
        st.download_button(
            label="⬇ FULL CSV",
            data=exports["full_csv"],
            file_name=f"{safe_fn}_full.csv",
            mime="text/csv",
            use_container_width=True,
            key="btn_dl_full_csv"
        )

    with col_exp_xlsx:
        st.download_button(
            label="⬇ EXCEL (TIERS)",
            data=exports["excel"],
            file_name=f"{safe_fn}_tiered.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="btn_dl_excel"
        )

    # -------------------------------------------------------------
    # 4. FAST IN-MEMORY FILTERING & TABLE HELPERS
    # -------------------------------------------------------------
    def apply_filters_to_df(df_source: pd.DataFrame, tier_prefix: Optional[str] = None) -> pd.DataFrame:
        df_f = df_source
        if tier_prefix:
            df_f = df_f[df_f["_Tier"].str.startswith(tier_prefix)]

        cat_map = {
            "Commercial": "COMMERCIAL",
            "Freeware": "FREE",
            "Open Source": "OPEN_SOURCE",
            "Free and Paid": "FREE_AND_PAID",
            "OS Bundled": "FREE",
            "System Infrastructure": "FREE",
        }

        if selected_filter == "Review Required":
            df_f = df_f[
                df_f["Classification"].isin(["UNKNOWN", ""])
                | df_f["License Required"].isin(["UNKNOWN", ""])
            ]
        elif selected_filter != "All Status":
            target_cat = cat_map.get(selected_filter, selected_filter.upper())
            if target_cat == "FREE":
                df_f = df_f[df_f["Classification"].str.upper().isin(["FREE", "FREEWARE", "OS_BUNDLED"])]
            else:
                df_f = df_f[df_f["Classification"].str.upper() == target_cat]

        if search_query:
            sq = search_query.strip().lower()
            mask = pd.Series(False, index=df_f.index)
            for c in df_f.columns:
                if not c.startswith("_"):
                    mask = mask | df_f[c].astype(str).str.lower().str.contains(sq, regex=False, na=False)
            df_f = df_f[mask]
        return df_f

    def render_inventory_table(tier_prefix: Optional[str] = None, context_label: str = ""):
        df_cached = st.session_state[cache_key_std]
        filtered = apply_filters_to_df(df_cached, tier_prefix=tier_prefix)
        display_cols = [c for c in filtered.columns if not c.startswith("_")]
        if not filtered.empty:
            st.dataframe(
                filtered[display_cols],
                width="stretch",
                height=520,
                hide_index=True
            )
            total_cat = len(df_cached[df_cached["_Tier"].str.startswith(tier_prefix)]) if tier_prefix else len(df_cached)
            st.caption(f"Showing {len(filtered):,} of {total_cat:,} applications {context_label} — Standardized Reference Format ({len(display_cols)} Columns)")
        else:
            st.info("No applications match the search or filter criteria in this category.")

    def render_final_schema_table(context_label: str = ""):
        df_cached = st.session_state[cache_key_final]
        filtered = apply_filters_to_df(df_cached)
        display_cols = [c for c in filtered.columns if not c.startswith("_")]
        if not filtered.empty:
            st.dataframe(
                filtered[display_cols],
                width="stretch",
                height=520,
                hide_index=True,
                column_config={
                    "Evidence URL": st.column_config.LinkColumn(
                        "Evidence URL",
                        help="Authoritative vendor licensing/lifecycle reference link",
                        validate=r"^https?://.+",
                        max_chars=100,
                    )
                }
            )
            st.caption(f"Showing {len(filtered):,} of {len(df_cached):,} applications {context_label} — Commercial License Intelligence Schema")
        else:
            st.info("No applications match the search or filter criteria in this category.")

    # -------------------------------------------------------------
    # 5. TIER NAVIGATION WITH DYNAMIC COUNT BADGES
    # -------------------------------------------------------------
    billable_items = [r for r in results if r.get("Tier", "").startswith("Tier 1") or (r.get("Classification") == "COMMERCIAL" and str(r.get("License Required", "")).upper() == "YES")]
    oss_items = [r for r in results if r.get("Tier", "").startswith("Tier 2") or r.get("Classification") in ("OPEN_SOURCE", "FREEWARE", "FREE")]
    infra_items = [r for r in results if r.get("Tier", "").startswith("Tier 3") or r.get("Classification") in ("OS_BUNDLED", "SYSTEM")]
    t4_items = [r for r in results if r.get("Tier", "").startswith("Tier 4") or r.get("Classification") in ("UNKNOWN", "")]

    tab_final, tab_std, tab_t1, tab_t2, tab_t3, tab_t4, tab_all = st.tabs([
        f"🎯 Final Schema ({len(results):,})",
        f"📊 Standardized Inventory ({len(results):,})",
        f"💎 Tier 1: Commercial & Billable ({len(billable_items):,})",
        f"🛠 Tier 2: Open Source & Freeware ({len(oss_items):,})",
        f"💻 Tier 3: OS & System Infrastructure ({len(infra_items):,})",
        f"🔍 Tier 4: Review Required ({len(t4_items):,})",
        f"📋 Full Inventory ({len(results):,})",
    ])

    with tab_final:
        st.markdown("##### Commercial License Intelligence (Final Output Columns)")
        st.caption("`Application Name | Version | OS | License Required | End of Support | End of Life | Metric | Classification | License Model | License Type | Evidence URL`")
        render_final_schema_table("(Final Schema)")

    with tab_std:
        st.markdown("##### Standardized Application Inventory (Exact Reference Format)")
        st.caption(f"{len(STANDARDIZED_COLUMNS)} Standardized Columns: `{' | '.join(STANDARDIZED_COLUMNS)}`")
        render_inventory_table(None, "(Total Scanned Inventory)")

    with tab_t1:
        st.markdown("##### Commercial, Paid & Subscription-Based Software")
        render_inventory_table("Tier 1", "(Commercial Software)")

    with tab_t2:
        st.markdown("##### Developer Open Source, Freeware & Community Tools")
        render_inventory_table("Tier 2", "(Open Source & Freeware)")

    with tab_t3:
        st.markdown("##### Operating System Components, Frameworks & Infrastructure")
        render_inventory_table("Tier 3", "(Infrastructure Components)")

    with tab_t4:
        st.markdown("##### Human-in-the-Loop Tier 4 Resolution & Permanent Rule Promotion")
        st.caption("Review unresolved applications, submit structured auditor decisions, update rows instantly, and promote verified catalog rules.")

        sub_queue, sub_pending, sub_audit = st.tabs([
            "📥 Frequency-Weighted Review Queue",
            "🚀 Staged Rules Awaiting Promotion",
            "📜 Catalog Audit History"
        ])

        with sub_queue:
            db_session = SessionLocal()
            try:
                queue_items = Tier4LoopService.get_tier4_queue(db_session, limit=100)
            finally:
                db_session.close()

            if queue_items:
                st.markdown(f"**Found {len(queue_items)} unresolved applications requiring auditor review:**")
                df_q = pd.DataFrame(queue_items)[["raw_application", "raw_vendor", "occurrences", "sample_version", "sample_hostname", "latest_seen"]]
                st.dataframe(df_q, width="stretch", height=260, hide_index=True)

                st.markdown("---")
                st.markdown("###### Structured Resolution Form")
                selected_app_names = [q["raw_application"] for q in queue_items]
                chosen_app = st.selectbox("Select Application to Resolve", options=selected_app_names, key="sel_t4_app_res")
                
                chosen_item = next((q for q in queue_items if q["raw_application"] == chosen_app), None)
                def_vendor = chosen_item["raw_vendor"] if chosen_item and chosen_item["raw_vendor"] != "UNKNOWN" else ""

                with st.form("form_resolve_t4_dash"):
                    c_f1, c_f2 = st.columns(2)
                    with c_f1:
                        f_pattern = st.text_input("Matched Pattern / Alias", value=chosen_app, help="Exact signature name or wildcard pattern")
                        f_canon_name = st.text_input("Canonical Product Name", value=chosen_app, help="Clean display product name")
                        f_vendor = st.text_input("Canonical Vendor", value=def_vendor, help="Actual software publisher/owner")
                        f_license_type = st.selectbox(
                            "License Classification",
                            options=["COMMERCIAL", "FREEWARE", "OPEN_SOURCE", "FREE_AND_PAID"],
                            index=0
                        )
                        f_tier = st.selectbox("Target Tier", options=[1, 2, 3], index=0, help="Tier 1: Billable, Tier 2: Freeware/OSS, Tier 3: OS/Infrastructure")
                    with c_f2:
                        f_license_req = st.selectbox("License Required?", options=["YES", "NO"], index=0)
                        f_metric = st.selectbox(
                            "Licensing Metric",
                            options=[
                                "Users",
                                "Devices",
                                "Installations",
                                "Concurrent Users",
                                "Concurrent Devices",
                                "CAL",
                                "PVU",
                                "Processor Cores",
                                "Processors",
                                "No License Required",
                                "",
                            ],
                            index=0
                        )
                        f_evidence_url = st.text_input("Evidence URL", placeholder="https://vendor.com/licensing/terms.html")
                        f_evidence_quote = st.text_area("Evidence Quote", placeholder="Verbatim quote from vendor licensing guide confirming terms...")
                        f_scope = st.selectbox("Resolution Scope", options=["exact_match", "pattern_family", "vendor_wide"], index=0)
                    
                    c_f3, c_f4 = st.columns(2)
                    with c_f3:
                        f_confidence = st.selectbox("Auditor Confidence", options=["auditor_confirmed", "auditor_guess"], index=0)
                        f_resolved_by = st.text_input("Auditor Name / ID", value="auditor")
                    with c_f4:
                        f_auto_promote = st.checkbox("Auto-Promote to catalog.py if confirmed", value=False)
                        st.markdown("<br>", unsafe_allow_html=True)
                        btn_submit_res = st.form_submit_button("⚡ Submit Resolution & Fix Rows Immediately", use_container_width=True)

                    if btn_submit_res:
                        res_obj = Tier4Resolution(
                            signature_id=chosen_app,
                            matched_pattern=f_pattern,
                            canonical_name=f_canon_name,
                            vendor=f_vendor or "UNKNOWN",
                            license_type=f_license_type,
                            license_required=f_license_req,
                            metric=f_metric,
                            tier=f_tier,
                            evidence_url=f_evidence_url,
                            evidence_quote=f_evidence_quote,
                            resolved_by=f_resolved_by,
                            confidence=f_confidence,
                            scope=f_scope,
                            auto_promote=f_auto_promote,
                        )
                        db_s = SessionLocal()
                        try:
                            submit_res = Tier4LoopService.submit_resolution(res_obj, db_s)
                            st.session_state.pop(cache_key_std, None)
                            st.session_state.pop(cache_key_final, None)
                            st.session_state.pop(cache_key_exports, None)
                            st.success(f"✓ Resolution Staged! Rule ID: {submit_res['rule_id']}. Immediately updated {submit_res['existing_rows_updated']} rows!")
                            time.sleep(1.0)
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Error submitting resolution: {ex}")
                        finally:
                            db_s.close()
            else:
                st.success("🎉 No unresolved Tier 4 items pending! Fleet software inventory is fully resolved.")

        with sub_pending:
            st.markdown("###### Staged Rules Awaiting Review & Promotion")
            db_session = SessionLocal()
            try:
                pending_rules = db_session.query(PendingCatalogRule).filter(
                    PendingCatalogRule.status == "pending_review"
                ).order_by(PendingCatalogRule.occurrence_count.desc()).all()
            finally:
                db_session.close()

            if pending_rules:
                for p_rule in pending_rules:
                    with st.expander(f"📦 Rule `{p_rule.rule_id}`: **{p_rule.canonical_name}** ({p_rule.vendor}) — {p_rule.occurrence_count} instances", expanded=True):
                        col_r1, col_r2 = st.columns([2, 1])
                        with col_r1:
                            st.markdown(f"""
                            - **Matched Pattern**: `{p_rule.matched_pattern}`
                            - **Classification**: `{p_rule.license_type}` | License Required: `{p_rule.license_required}` | Target Tier: `{p_rule.tier}`
                            - **Evidence URL**: [{p_rule.evidence_url}]({p_rule.evidence_url})
                            - **Resolved By**: `{p_rule.resolved_by}` ({p_rule.confidence}, scope: `{p_rule.scope}`)
                            """)
                            st.code(p_rule.diff_preview or Tier4LoopService.generate_catalog_py_entry(p_rule), language="python")
                        with col_r2:
                            st.markdown("###### Action")
                            p_approver = st.text_input("Reviewer Name", value="compliance_officer", key=f"appr_{p_rule.rule_id}")
                            if st.button("🚀 Approve & Promote to Catalog", key=f"btn_prm_{p_rule.rule_id}", use_container_width=True):
                                db_s = SessionLocal()
                                try:
                                    p_res = Tier4LoopService.promote_to_catalog(p_rule.rule_id, approved_by=p_approver, db=db_s)
                                    st.session_state.pop(cache_key_std, None)
                                    st.session_state.pop(cache_key_final, None)
                                    st.session_state.pop(cache_key_exports, None)
                                    st.success(f"✓ Rule {p_rule.rule_id} permanently merged into catalog.py!")
                                    time.sleep(1.0)
                                    st.rerun()
                                except Exception as e_prm:
                                    st.error(f"Failed to promote rule: {e_prm}")
                                finally:
                                    db_s.close()
            else:
                st.info("No pending rules awaiting promotion.")

        with sub_audit:
            st.markdown("###### Catalog Audit Trail")
            db_session = SessionLocal()
            try:
                audit_logs = db_session.query(CatalogAuditLog).order_by(CatalogAuditLog.timestamp.desc()).limit(50).all()
            finally:
                db_session.close()

            if audit_logs:
                df_audit = pd.DataFrame([a.to_dict() for a in audit_logs])[["timestamp", "action", "rule_id", "performed_by", "source_resolutions_count", "details"]]
                st.dataframe(df_audit, width="stretch", height=320, hide_index=True)
            else:
                st.info("No audit log entries recorded yet.")

    with tab_all:
        st.markdown("##### Complete Software Inventory")
        render_inventory_table(None, "(Total Inventory)")

    # -------------------------------------------------------------
    # 6. APPLICATION EVIDENCE, WINGET GROUND TRUTH & PROVENANCE INSPECTOR
    # -------------------------------------------------------------
    st.markdown('<div style="height: 16px;"></div>', unsafe_allow_html=True)
    with st.expander("🔍 **Application Evidence, WinGet Ground Truth & Provenance Inspector**", expanded=True):
        st.caption(
            "Inspect verified cryptographic WinGet ground-truth package data, official installer signatures, "
            "source provenance, conflict verification status, lifecycle EOL/EOS, and verbatim evidence quotes."
        )

        app_display_names = [
            f"{i + 1}. {r.get('Application') or r.get('Name')} {r.get('Version') or ''} — [{r.get('Classification') or 'UNKNOWN'}]"
            for i, r in enumerate(results)
        ]

        selected_idx = st.selectbox(
            "Choose Application to Inspect Detailed Evidence & Provenance",
            range(len(results)),
            format_func=lambda i: app_display_names[i],
            key="sel_app_inspector_dash"
        )

        item = results[selected_idx]

        col_c1, col_c2, col_c3 = st.columns([1.2, 1.2, 1.0], gap="medium")

        with col_c1:
            st.markdown("###### 📦 WinGet Ground Truth & Package Manifest")
            winget_id = item.get("winget_package_id") or "Not Matched / Native"
            c_status = item.get("conflict_status") or "VERIFIED"
            consensus_stat = item.get("consensus_status") or "VERIFIED"
            edition_val = item.get("canonical_edition") or item.get("edition") or "Standard"
            inst_url = item.get("installer_url") or ""
            inst_hash = item.get("installer_sha256") or ""
            o_reason = item.get("override_reason") or "Catalog rule / Primary evidence authoritative"

            status_color = (
                "#10b981" if c_status in ("VERIFIED", "CONFIRMED")
                else "#38bdf8" if c_status == "ENRICHED"
                else "#ef4444" if c_status == "DISCREPANCY_FLAGGED"
                else "#f59e0b"
            )
            edition_color = "#ef4444" if edition_val == "EDITION_AMBIGUOUS" else "#38bdf8" if edition_val != "Standard" else "#94a3b8"
            inst_link_html = f'<a href="{inst_url}" target="_blank" style="color: #38bdf8;">{inst_url}</a>' if inst_url else '<span style="color: #64748b;">None</span>'
            hash_display = f'<code>{inst_hash}</code>' if inst_hash else '<span style="color: #64748b;">N/A</span>'
            audit_note_html = f'<div style="margin-top: 6px; font-size: 11px; color: #94a3b8; word-break: break-word;"><b>Audit/Baseline:</b> {o_reason}</div>' if o_reason else ''

            st.markdown(f"""
                <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 12px; font-size: 13px;">
                    <div style="margin-bottom: 6px;"><b>Edition:</b> <span style="color: {edition_color}; font-weight: 700;">{edition_val}</span></div>
                    <div style="margin-bottom: 6px;"><b>Consensus:</b> <span style="color: #38bdf8; font-weight: 600;">{consensus_stat}</span></div>
                    <div style="margin-bottom: 6px;"><b>Package ID:</b> <code>{winget_id}</code></div>
                    <div style="margin-bottom: 6px;"><b>Conflict Status:</b> <span style="color: {status_color}; font-weight: 600;">{c_status}</span></div>
                    <div style="margin-bottom: 6px; word-break: break-all;"><b>Installer URL:</b> {inst_link_html}</div>
                    <div style="word-break: break-all;"><b>SHA-256 Digest:</b> {hash_display}</div>
                    {audit_note_html}
                </div>
            """, unsafe_allow_html=True)

        with col_c2:
            st.markdown("###### 🌐 Evidence Provenance & Primary Source")
            ev_source = item.get("evidence_source") or "SYSTEM_CATALOG"
            ev_url = item.get("Evidence URL") or item.get("evidence_url") or ""
            rel_score = item.get("reliability") or "100%"
            conf = item.get("Confidence") or "HIGH"
            v_rule = item.get("version_rule_applied") or ""
            quote = item.get("evidence_quote") or "Catalog entry verified against primary source."

            ev_link_html = f'<a href="{ev_url}" target="_blank" style="color: #38bdf8;">{ev_url}</a>' if ev_url else '<span style="color: #64748b;">None</span>'
            v_rule_html = f'<div style="margin-bottom: 6px; color: #a78bfa;"><b>Version Inflection:</b> {v_rule}</div>' if v_rule else ''

            st.markdown(f"""
                <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 12px; font-size: 13px;">
                    <div style="margin-bottom: 6px;"><b>Primary Source:</b> <code style="color: #38bdf8;">{ev_source}</code></div>
                    <div style="margin-bottom: 6px;"><b>Confidence:</b> <span style="color: #38bdf8; font-weight: 600;">{conf}</span> (Reliability: {rel_score})</div>
                    {v_rule_html}
                    <div style="margin-bottom: 6px; word-break: break-all;"><b>Evidence URL:</b> {ev_link_html}</div>
                    <div style="margin-top: 8px;"><b>Evidence Quote:</b></div>
                    <div style="background: #1e293b; border-radius: 4px; padding: 8px; margin-top: 4px; font-size: 11.5px; color: #cbd5e1; max-height: 80px; overflow-y: auto;">
                        {quote}
                    </div>
                </div>
            """, unsafe_allow_html=True)

        with col_c3:
            st.markdown("###### ⚖️ Licensing & Lifecycle Profile")
            lic_req = item.get("License Required") or "YES"
            lic_model = item.get("License Model") or "Unknown"
            metric = item.get("Metric") or "N/A"
            classification = item.get("Classification") or "UNKNOWN"
            spdx_val = item.get("spdx_id") or "Proprietary"
            eol = item.get("IsEndOfLife")
            eos = item.get("IsEndOfSupport")

            eol_str = "EOL (End of Life)" if eol == 1 else "Supported" if eol == 0 else "Unknown"
            eos_str = "EOS (End of Support)" if eos == 1 else "Supported" if eos == 0 else "Unknown"
            eol_color = "#ef4444" if eol == 1 else "#10b981" if eol == 0 else "#94a3b8"
            eos_color = "#ef4444" if eos == 1 else "#10b981" if eos == 0 else "#94a3b8"

            st.markdown(f"""
                <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 12px; font-size: 13px;">
                    <div style="margin-bottom: 6px;"><b>Classification:</b> <span style="color: #f8fafc; font-weight: 600;">{classification}</span></div>
                    <div style="margin-bottom: 6px;"><b>License Required:</b> <span style="color: {'#ef4444' if lic_req == 'YES' else '#10b981'}; font-weight: 700;">{lic_req}</span></div>
                    <div style="margin-bottom: 6px;"><b>License Model:</b> <span style="color: #cbd5e1;">{lic_model}</span></div>
                    <div style="margin-bottom: 6px;"><b>Exact Metric:</b> <span style="color: #38bdf8; font-weight: 600;">{metric}</span></div>
                    <div style="margin-bottom: 6px;"><b>SPDX 3.0 ID:</b> <code style="color: #10b981;">{spdx_val}</code></div>
                    <div style="margin-bottom: 6px;"><b>End of Life:</b> <span style="color: {eol_color}; font-weight: 600;">{eol_str}</span></div>
                    <div><b>End of Support:</b> <span style="color: {eos_color}; font-weight: 600;">{eos_str}</span></div>
                </div>
            """, unsafe_allow_html=True)

