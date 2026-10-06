"""
Enterprise UI Design System & Reusable Micro-Components.
Provides custom styling, badges, metric cards, progress indicators, empty states, and error handling.
"""

import streamlit as st
from typing import Optional, Callable, Any


def inject_enterprise_css():
    """Injects core enterprise dark theme design system CSS into the Streamlit app."""
    st.markdown("""
    <style>
        /* Google Fonts - Inter & JetBrains Mono */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            color: #e2e8f0;
        }

        /* Hide Streamlit default chrome */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .stDeployButton {display: none;}
        
        /* Container Spacing */
        .block-container {
            padding-top: 1.25rem !important;
            padding-bottom: 2.5rem !important;
            max-width: 1220px !important;
        }

        /* Flex stretch for Streamlit columns to equalize card heights */
        [data-testid="column"] {
            display: flex !important;
            flex-direction: column !important;
        }
        [data-testid="column"] > div {
            display: flex !important;
            flex-direction: column !important;
            flex: 1 1 auto !important;
            height: 100% !important;
        }

        /* Top Brand Header (Initial Screen) */
        .brand-header {
            text-align: center;
            margin-bottom: 1.6rem;
            padding: 0.5rem 0 0.25rem 0;
        }
        .brand-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(2, 132, 199, 0.12);
            border: 1px solid rgba(56, 189, 248, 0.3);
            border-radius: 9999px;
            padding: 4px 14px;
            font-size: 11px;
            font-weight: 700;
            color: #38bdf8;
            letter-spacing: 0.75px;
            text-transform: uppercase;
            margin-bottom: 10px;
        }
        .brand-title {
            font-size: 30px;
            font-weight: 800;
            color: #f8fafc;
            letter-spacing: -0.6px;
            margin-bottom: 6px;
            line-height: 1.2;
        }
        .brand-subtitle {
            font-size: 14px;
            color: #94a3b8;
            font-weight: 400;
            max-width: 640px;
            margin: 0 auto;
            line-height: 1.5;
        }

        /* Compact Header (Scanning & Secondary Screens) */
        .compact-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: linear-gradient(90deg, #0d1527 0%, #0b1120 100%);
            border: 1px solid #1e293b;
            border-radius: 12px;
            padding: 14px 20px;
            margin-bottom: 1.4rem;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
        }
        .compact-header-left {
            display: flex;
            align-items: center;
            gap: 14px;
        }
        .compact-header-title {
            font-size: 18px;
            font-weight: 800;
            color: #f8fafc;
            letter-spacing: -0.3px;
        }
        .compact-status-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(56, 189, 248, 0.12);
            border: 1px solid rgba(56, 189, 248, 0.35);
            border-radius: 9999px;
            padding: 3px 12px;
            font-size: 11.5px;
            font-weight: 700;
            color: #38bdf8;
            letter-spacing: 0.5px;
        }
        .status-dot-pulse {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background-color: #38bdf8;
            animation: pulse-ring 1.5s infinite;
        }

        /* Start Screen Selection Cards */
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.card-icon-wrap) {
            background: linear-gradient(180deg, #0d1527 0%, #080d1a 100%) !important;
            border: 1px solid #1e293b !important;
            border-radius: 14px !important;
            padding: 24px !important;
            height: 100% !important;
            min-height: 380px !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: space-between !important;
            transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
            position: relative !important;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35) !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.card-icon-wrap):hover {
            border-color: rgba(56, 189, 248, 0.45) !important;
            box-shadow: 0 10px 32px rgba(2, 132, 199, 0.18) !important;
            transform: translateY(-2px);
        }

        /* Completed Analysis Summary Section */
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.complete-summary-wrap) {
            background: linear-gradient(135deg, #0d1527 0%, #090e1a 100%) !important;
            border: 1px solid #1e293b !important;
            border-radius: 12px !important;
            padding: 14px 20px !important;
            height: auto !important;
            min-height: auto !important;
            margin-bottom: 1rem !important;
            box-shadow: 0 4px 18px rgba(0, 0, 0, 0.28) !important;
            position: relative !important;
            overflow: hidden !important;
            transition: border-color 0.2s ease !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.complete-summary-wrap):hover {
            border-color: #334155 !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.complete-summary-wrap)::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2.5px;
            background: linear-gradient(90deg, #10b981 0%, #38bdf8 100%);
        }

        /* Title and Status Badge */
        .complete-title-row {
            display: flex;
            align-items: center;
            gap: 9px;
            margin-bottom: 6px;
            flex-wrap: wrap;
        }
        .complete-status-badge {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.35);
            border-radius: 9999px;
            padding: 2.5px 9px;
            font-size: 11px;
            font-weight: 700;
            color: #10b981;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }
        .complete-status-dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background-color: #10b981;
            box-shadow: 0 0 6px rgba(16, 185, 129, 0.6);
        }
        .complete-main-title {
            font-size: 16.5px;
            font-weight: 800;
            color: #f8fafc;
            letter-spacing: -0.2px;
        }

        /* Compact Information Row */
        .complete-meta-row {
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 3px 5px;
            font-size: 12px;
            color: #94a3b8;
            line-height: 1.4;
        }
        .complete-meta-item {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            white-space: nowrap;
        }
        .complete-meta-label {
            color: #64748b;
            font-weight: 500;
            font-size: 11.5px;
        }
        .complete-meta-val {
            color: #cbd5e1;
            font-weight: 600;
            font-size: 12px;
        }
        .complete-meta-code {
            color: #38bdf8;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11.5px;
            font-weight: 600;
            background: rgba(56, 189, 248, 0.08);
            border: 1px solid rgba(56, 189, 248, 0.22);
            padding: 1px 6px;
            border-radius: 4px;
        }
        .complete-meta-highlight {
            color: #10b981;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
        }
        .complete-meta-sep {
            color: #334155;
            margin: 0 4px;
            font-weight: 300;
            font-size: 11px;
        }

        /* Equal-Sized Right-Aligned Action Buttons */
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.complete-summary-wrap) .stButton {
            margin-bottom: 0 !important;
            width: 100% !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.complete-summary-wrap) .stButton>button {
            height: 38px !important;
            min-height: 38px !important;
            max-height: 38px !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 6px !important;
            padding: 0 10px !important;
            white-space: nowrap !important;
            font-size: 12.5px !important;
            font-weight: 600 !important;
            letter-spacing: 0.1px !important;
            border-radius: 8px !important;
            background: #141d30 !important;
            border: 1px solid #293854 !important;
            color: #f1f5f9 !important;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2) !important;
            transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
            width: 100% !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.complete-summary-wrap) .stButton>button:hover {
            background: #1e2c47 !important;
            border-color: #38bdf8 !important;
            color: #38bdf8 !important;
            box-shadow: 0 4px 14px rgba(2, 132, 199, 0.25) !important;
            transform: translateY(-1px) !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.complete-summary-wrap) .stButton>button:active {
            transform: translateY(0) !important;
        }
        .selection-card-frame {
            background: linear-gradient(180deg, #0d1527 0%, #080d1a 100%);
            border: 1px solid #1e293b;
            border-radius: 14px;
            padding: 24px;
            height: 100%;
            min-height: 380px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
            position: relative;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
        }
        .selection-card-frame:hover {
            border-color: rgba(56, 189, 248, 0.45);
            box-shadow: 0 10px 32px rgba(2, 132, 199, 0.18);
            transform: translateY(-2px);
        }
        .selection-card-frame::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #0284c7, #38bdf8);
            opacity: 0;
            transition: opacity 0.25s ease;
        }
        .selection-card-frame:hover::before {
            opacity: 1;
        }
        .selection-card-frame.active-card {
            border-color: rgba(56, 189, 248, 0.4);
        }
        .card-icon-wrap {
            width: 44px;
            height: 44px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 22px;
            margin-bottom: 14px;
            background: rgba(30, 41, 59, 0.7);
            border: 1px solid #334155;
        }
        .card-title {
            font-size: 18px;
            font-weight: 700;
            color: #f1f5f9;
            margin-bottom: 6px;
        }
        .card-description {
            font-size: 13px;
            color: #94a3b8;
            line-height: 1.5;
            margin-bottom: 16px;
        }

        /* Device Meta Info Box in Card 2 */
        .device-info-box {
            background: rgba(11, 17, 32, 0.9);
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 12px 14px;
            margin-bottom: 16px;
            font-size: 12px;
            color: #cbd5e1;
        }
        .device-info-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 3.5px 0;
        }
        .device-info-label {
            color: #64748b;
            font-weight: 500;
            font-size: 11.5px;
        }
        .device-info-val {
            color: #38bdf8;
            font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
        }

        /* Subtle OR divider */
        .or-divider-wrap {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100%;
            min-height: 280px;
            position: relative;
        }
        .or-divider-line {
            position: absolute;
            top: 15%;
            bottom: 15%;
            width: 1px;
            background: #1e293b;
            z-index: 0;
        }
        .or-badge {
            position: relative;
            z-index: 1;
            background: #0d1527;
            border: 1px solid #334155;
            color: #64748b;
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 9999px;
            letter-spacing: 0.5px;
        }

        /* Seamless File Uploader Customization */
        [data-testid="stFileUploader"] {
            width: 100% !important;
            margin-top: auto !important;
        }
        [data-testid="stFileUploader"] section {
            background-color: rgba(11, 17, 32, 0.75) !important;
            border: 1px dashed #334155 !important;
            border-radius: 10px !important;
            padding: 12px 14px !important;
            transition: all 0.2s ease !important;
        }
        [data-testid="stFileUploader"] section:hover {
            border-color: #38bdf8 !important;
            background-color: rgba(14, 23, 42, 0.95) !important;
        }
        [data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"] {
            background: #1e293b !important;
            border: 1px solid #334155 !important;
            color: #f1f5f9 !important;
            font-weight: 600 !important;
            font-size: 13px !important;
            border-radius: 6px !important;
            padding: 6px 14px !important;
        }
        [data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"]:hover {
            background: #334155 !important;
            border-color: #38bdf8 !important;
        }

        /* Enterprise Metric Cards */
        .ent-metric-card {
            background: linear-gradient(180deg, #0d1527 0%, #080d1a 100%);
            border: 1px solid #1e293b;
            border-radius: 12px;
            padding: 16px 18px;
            position: relative;
            transition: all 0.2s ease;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
            height: 100%;
            min-height: 106px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .ent-metric-card:hover {
            border-color: rgba(56, 189, 248, 0.4);
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
        }
        .ent-metric-top {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 6px;
        }
        .ent-metric-label {
            font-size: 11px;
            font-weight: 700;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.6px;
        }
        .ent-metric-icon {
            font-size: 16px;
            opacity: 0.85;
        }
        .ent-metric-value {
            font-size: 26px;
            font-weight: 800;
            color: #f8fafc;
            line-height: 1.1;
            font-feature-settings: "tnum";
            font-variant-numeric: tabular-nums;
            font-family: 'JetBrains Mono', monospace;
        }
        .ent-metric-meta {
            font-size: 11.5px;
            color: #94a3b8;
            margin-top: 4px;
            display: flex;
            align-items: center;
            gap: 4px;
        }

        /* Dedicated Scan Progress Card (Page 2) */
        .scan-progress-card {
            background: linear-gradient(180deg, #0d1527 0%, #080d1a 100%);
            border: 1px solid #1e293b;
            border-radius: 14px;
            padding: 22px 24px;
            margin: 18px 0 22px 0;
            position: relative;
            overflow: hidden;
            box-shadow: 0 6px 24px rgba(0, 0, 0, 0.35);
        }
        .scan-progress-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #0284c7 0%, #38bdf8 50%, #10b981 100%);
        }
        .scan-progress-title-row {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 4px;
            flex-wrap: wrap;
            gap: 8px;
        }
        .scan-progress-main-title {
            font-size: 17px;
            font-weight: 800;
            color: #f8fafc;
            letter-spacing: -0.2px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .scan-progress-sub {
            font-size: 13px;
            color: #94a3b8;
            margin-bottom: 16px;
        }
        .scan-progress-pct-badge {
            font-size: 16px;
            font-weight: 800;
            color: #38bdf8;
            font-family: 'JetBrains Mono', monospace;
            background: rgba(56, 189, 248, 0.1);
            border: 1px solid rgba(56, 189, 248, 0.3);
            border-radius: 8px;
            padding: 4px 12px;
        }
        .scan-step-indicator {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            font-size: 13px;
        }
        .scan-step-name {
            font-weight: 600;
            color: #e2e8f0;
        }
        .scan-meta-pill-row {
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 14px;
            padding-top: 14px;
            border-top: 1px solid #1e293b;
        }
        .scan-meta-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #090e1a;
            border: 1px solid #1e293b;
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 11.5px;
            color: #94a3b8;
        }
        .scan-meta-pill b {
            color: #cbd5e1;
            font-weight: 600;
        }
        .scan-meta-pill code {
            color: #38bdf8;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
        }

        /* Streamlit Progress Bar Override */
        div[data-testid="stProgress"] > div {
            background-color: #1e293b !important;
            height: 10px !important;
            border-radius: 6px !important;
            overflow: hidden !important;
        }
        div[data-testid="stProgress"] > div > div {
            background: linear-gradient(90deg, #0284c7 0%, #38bdf8 100%) !important;
            box-shadow: 0 0 12px rgba(56, 189, 248, 0.4) !important;
            border-radius: 6px !important;
        }

        /* Pipeline Workflow Card */
        .pipeline-card {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            padding: 11px 16px;
            background: #0d1527;
            border: 1px solid #1e293b;
            border-radius: 10px;
            margin-bottom: 8px;
            transition: all 0.25s ease;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
        }
        .pipeline-card:hover {
            transform: translateX(2px);
        }
        .pipeline-card-active {
            border-color: #38bdf8;
            background: rgba(56, 189, 248, 0.06);
            box-shadow: 0 0 18px rgba(56, 189, 248, 0.15);
        }
        .pipeline-card-done {
            border-color: rgba(16, 185, 129, 0.35);
            background: rgba(16, 185, 129, 0.03);
        }
        .pipeline-card-left {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .step-icon-circle {
            width: 28px;
            height: 28px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 13px;
            font-weight: 700;
            flex-shrink: 0;
        }
        .step-icon-pending {
            background: #111a2e;
            color: #64748b;
            border: 1px solid #1e293b;
        }
        .step-icon-running {
            background: rgba(56, 189, 248, 0.18);
            color: #38bdf8;
            border: 1px solid #38bdf8;
            animation: pulse-ring 1.5s infinite;
        }
        .step-icon-completed {
            background: rgba(16, 185, 129, 0.18);
            color: #10b981;
            border: 1px solid #10b981;
        }
        .step-icon-failed {
            background: rgba(239, 68, 68, 0.18);
            color: #ef4444;
            border: 1px solid #ef4444;
        }
        .step-text {
            font-size: 13px;
            font-weight: 500;
            color: #cbd5e1;
        }
        .step-active-text {
            color: #38bdf8;
            font-weight: 600;
        }
        .step-state-tag {
            font-size: 10.5px;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            padding: 2px 8px;
            border-radius: 4px;
        }
        .tag-pending {
            color: #64748b;
            background: #111a2e;
            border: 1px solid #1e293b;
        }
        .tag-running {
            color: #38bdf8;
            background: rgba(56, 189, 248, 0.12);
            border: 1px solid rgba(56, 189, 248, 0.3);
        }
        .tag-done {
            color: #10b981;
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        /* Backwards compatible .pipeline-step class */
        .pipeline-step {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 10px 14px;
            background: #0d1527;
            border: 1px solid #1e293b;
            border-radius: 8px;
            margin-bottom: 8px;
            transition: all 0.2s ease;
        }
        .pipeline-step-active {
            border-color: #38bdf8;
            background: rgba(56, 189, 248, 0.05);
        }
        .pipeline-step-done {
            border-color: rgba(16, 185, 129, 0.35);
            background: rgba(16, 185, 129, 0.03);
        }

        @keyframes pulse-ring {
            0% { box-shadow: 0 0 0 0 rgba(56, 189, 248, 0.4); }
            70% { box-shadow: 0 0 0 6px rgba(56, 189, 248, 0); }
            100% { box-shadow: 0 0 0 0 rgba(56, 189, 248, 0); }
        }

        /* Buttons Styling */
        .stButton>button {
            border-radius: 8px !important;
            font-weight: 600 !important;
            font-size: 13.5px !important;
            padding: 8px 18px !important;
            transition: all 0.2s ease !important;
        }
        .stButton>button[kind="primary"] {
            background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%) !important;
            border: 1px solid #0284c7 !important;
            color: #ffffff !important;
            box-shadow: 0 2px 8px rgba(2, 132, 199, 0.25) !important;
        }
        .stButton>button[kind="primary"]:hover {
            background: linear-gradient(135deg, #0369a1 0%, #075985 100%) !important;
            border-color: #38bdf8 !important;
            box-shadow: 0 4px 16px rgba(2, 132, 199, 0.35) !important;
            transform: translateY(-1px) !important;
        }
        .stButton>button[kind="secondary"] {
            background: #1e293b !important;
            border: 1px solid #334155 !important;
            color: #e2e8f0 !important;
        }
        .stButton>button[kind="secondary"]:hover {
            background: #334155 !important;
            border-color: #64748b !important;
            color: #ffffff !important;
        }

        /* Streamlit Expander Styling */
        [data-testid="stExpander"] {
            background: #0d1527 !important;
            border: 1px solid #1e293b !important;
            border-radius: 10px !important;
            overflow: hidden !important;
            transition: border-color 0.2s ease !important;
            margin-top: 14px !important;
        }
        [data-testid="stExpander"]:hover {
            border-color: #334155 !important;
        }
        [data-testid="stExpander"] details summary {
            padding: 12px 16px !important;
            font-size: 13.5px !important;
            font-weight: 600 !important;
            color: #e2e8f0 !important;
        }

        /* Search input styling */
        .stTextInput>div>div>input {
            background: #0d1527 !important;
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
            color: #f8fafc !important;
            font-size: 13px !important;
        }
        .stTextInput>div>div>input:focus {
            border-color: #38bdf8 !important;
            box-shadow: 0 0 0 1px #38bdf8 !important;
        }

        /* Responsive Breakpoints */
        @media (max-width: 992px) {
            .block-container {
                padding-top: 1rem !important;
                padding-left: 1rem !important;
                padding-right: 1rem !important;
            }
            .brand-title {
                font-size: 24px !important;
            }
            .compact-header {
                flex-direction: column;
                align-items: flex-start;
                gap: 8px;
            }
            .or-divider-wrap {
                min-height: 40px !important;
                margin: 8px 0 !important;
            }
            .or-divider-line {
                display: none !important;
            }
            div[data-testid="stVerticalBlockBorderWrapper"]:has(.complete-summary-wrap) {
                padding: 14px 16px !important;
            }
            .complete-meta-row {
                gap: 5px 8px !important;
            }
        }
        @media (max-width: 768px) {
            div[data-testid="stVerticalBlockBorderWrapper"]:has(.complete-summary-wrap) {
                padding: 14px !important;
            }
            .complete-title-row {
                margin-bottom: 8px !important;
            }
            .complete-meta-sep {
                display: none !important;
            }
            .complete-meta-row {
                flex-direction: column !important;
                align-items: flex-start !important;
                gap: 5px !important;
                margin-bottom: 12px !important;
            }
        }
    </style>
    """, unsafe_allow_html=True)


def render_metric_card(
    label: str,
    value: Any,
    icon: str = "📊",
    color: str = "#f8fafc",
    meta_text: Optional[str] = None
):
    """Renders a polished enterprise metric card with icon and optional sub-text."""
    meta_html = f'<div class="ent-metric-meta">{meta_text}</div>' if meta_text else ""
    st.markdown(f"""
        <div class="ent-metric-card">
            <div class="ent-metric-top">
                <span class="ent-metric-label">{label}</span>
                <span class="ent-metric-icon">{icon}</span>
            </div>
            <div class="ent-metric-value" style="color: {color};">{value}</div>
            {meta_html}
        </div>
    """, unsafe_allow_html=True)


def render_pipeline_step(step_number: int, name: str, state: str = "pending"):
    """
    Renders an enterprise pipeline workflow step card.
    state: pending | running | completed | failed
    """
    config_map = {
        "pending": ("○", "step-icon-pending", "", "PENDING", "tag-pending"),
        "running": ("◌", "step-icon-running", "pipeline-card-active", "IN PROGRESS", "tag-running"),
        "completed": ("✓", "step-icon-completed", "pipeline-card-done", "COMPLETED", "tag-done"),
        "failed": ("⚠", "step-icon-failed", "", "FAILED", "tag-pending"),
    }
    symbol, circle_cls, card_cls, tag_text, tag_cls = config_map.get(
        state, ("○", "step-icon-pending", "", "PENDING", "tag-pending")
    )
    active_cls = "step-active-text" if state == "running" else ""

    st.markdown(f"""
        <div class="pipeline-card {card_cls}">
            <div class="pipeline-card-left">
                <div class="step-icon-circle {circle_cls}">{symbol}</div>
                <div class="step-text {active_cls}">{step_number}. {name}</div>
            </div>
            <div class="step-state-tag {tag_cls}">{tag_text}</div>
        </div>
    """, unsafe_allow_html=True)
