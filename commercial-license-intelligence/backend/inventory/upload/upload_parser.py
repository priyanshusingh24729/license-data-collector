"""
Upload File Parser & Intelligent Column Auto-Mapping Heuristics.
Supports CSV (with encoding detection) and Excel (.xlsx, .xls) files.
"""

import io
import re
import csv
import logging
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd

logger = logging.getLogger(__name__)

# Column Alias Mapping Patterns
APPLICATION_PATTERNS = [
    r"^application[\s_-]*name$",
    r"^software[\s_-]*name$",
    r"^display[\s_-]*name$",
    r"^product[\s_-]*name$",
    r"^app[\s_-]*name$",
    r"^application$",
    r"^software$",
    r"^package[\s_-]*name$",
    r"^product$",
    r"^app$",
    r"^name$",
    r"^title$",
]

VENDOR_PATTERNS = [
    r"^vendor[\s_-]*name$",
    r"^publisher[\s_-]*name$",
    r"^manufacturer[\s_-]*name$",
    r"^vendor$",
    r"^publisher$",
    r"^manufacturer$",
    r"^company$",
    r"^supplier$",
    r"^producer$",
    r"^author$",
    r"^developer$",
    r"^dev$",
]

VERSION_PATTERNS = [
    r"^product[\s_-]*version$",
    r"^display[\s_-]*version$",
    r"^app[\s_-]*version$",
    r"^software[\s_-]*version$",
    r"^version$",
    r"^ver$",
    r"^release$",
    r"^build$",
]

HOSTNAME_PATTERNS = [
    r"^computer[\s_-]*name$",
    r"^machine[\s_-]*name$",
    r"^device[\s_-]*name$",
    r"^host[\s_-]*name$",
    r"^endpoint[\s_-]*name$",
    r"^device[\s_-]*id$",
    r"^unique[\s_-]*id$",
    r"^hostname$",
    r"^computer$",
    r"^machine$",
    r"^device$",
    r"^host$",
    r"^endpoint$",
    r"^node$",
    r"^system$",
]

INSTALL_LOCATION_PATTERNS = [
    r"^install[\s_-]*location$",
    r"^installation[\s_-]*path$",
    r"^install[\s_-]*path$",
    r"^path$",
    r"^directory$",
    r"^location$",
]

INSTALL_SOURCE_PATTERNS = [
    r"^install[\s_-]*source$",
    r"^detection[\s_-]*method$",
    r"^source$",
    r"^method$",
]

NO_LICENSE_REQUIRED_PATTERNS = [
    r"^nolicenserequired$",
    r"^no[\s_-]*license[\s_-]*required$",
    r"^license[\s_-]*exempt$",
    r"^is[\s_-]*free$",
]

METRIC_PATTERNS = [
    r"^metric$",
    r"^license[\s_-]*metric$",
    r"^licensing[\s_-]*metric$",
    r"^pricing[\s_-]*metric$",
]

IS_END_OF_LIFE_PATTERNS = [
    r"^isendoflife$",
    r"^end[\s_-]*of[\s_-]*life$",
    r"^eol$",
    r"^is[\s_-]*eol$",
]

IS_END_OF_SUPPORT_PATTERNS = [
    r"^isendofsupport$",
    r"^end[\s_-]*of[\s_-]*support$",
    r"^eos$",
    r"^is[\s_-]*eos$",
]

APP_ID_PATTERNS = [
    r"^app[\s_-]*id$",
    r"^application[\s_-]*id$",
    r"^srs[\s_-]*id$",
    r"^id$",
]

NORMALIZED_APP_PATTERNS = [
    r"^normalized[\s_-]*application$",
    r"^normalized[\s_-]*name$",
    r"^canonical[\s_-]*name$",
]

OPERATING_SYSTEM_PATTERNS = [
    r"^operating[\s_-]*system$",
    r"^os$",
    r"^ostype$",
    r"^platform$",
]


class UploadFileParser:
    """
    Parses uploaded CSV and Excel files and detects column mappings automatically.
    """

    @classmethod
    def match_column(cls, col_name: str, patterns: List[str]) -> bool:
        """Checks if a column header matches any regex pattern."""
        c = col_name.strip().lower()
        for p in patterns:
            if re.match(p, c, re.IGNORECASE):
                return True
        return False

    @classmethod
    def auto_detect_columns(cls, columns: List[str]) -> Dict[str, Optional[str]]:
        """
        Auto-maps inventory file column names to standard keys:
        - application
        - vendor
        - version
        - hostname
        - install_location
        - install_source
        - no_license_required (Snow SRS)
        - metric (Snow SRS)
        - is_end_of_life (Snow SRS)
        - is_end_of_support (Snow SRS)
        - app_id (Snow SRS)
        - normalized_application (Snow SRS)
        - operating_system (Snow SRS)
        """
        mapping: Dict[str, Optional[str]] = {
            "application": None,
            "vendor": None,
            "version": None,
            "hostname": None,
            "install_location": None,
            "install_source": None,
            "no_license_required": None,
            "metric": None,
            "is_end_of_life": None,
            "is_end_of_support": None,
            "app_id": None,
            "normalized_application": None,
            "operating_system": None,
        }

        unassigned = list(columns)

        # 1. Match Application
        for col in unassigned:
            if cls.match_column(col, APPLICATION_PATTERNS):
                mapping["application"] = col
                unassigned.remove(col)
                break

        # 2. Match Vendor
        for col in unassigned:
            if cls.match_column(col, VENDOR_PATTERNS):
                mapping["vendor"] = col
                unassigned.remove(col)
                break

        # 3. Match Version
        for col in unassigned:
            if cls.match_column(col, VERSION_PATTERNS):
                mapping["version"] = col
                unassigned.remove(col)
                break

        # 4. Match Hostname
        for col in unassigned:
            if cls.match_column(col, HOSTNAME_PATTERNS):
                mapping["hostname"] = col
                unassigned.remove(col)
                break

        # 5. Match Install Location
        for col in unassigned:
            if cls.match_column(col, INSTALL_LOCATION_PATTERNS):
                mapping["install_location"] = col
                unassigned.remove(col)
                break

        # 6. Match Install Source
        for col in unassigned:
            if cls.match_column(col, INSTALL_SOURCE_PATTERNS):
                mapping["install_source"] = col
                unassigned.remove(col)
                break

        # 7. Match Snow Baseline Columns
        for col in unassigned:
            if cls.match_column(col, NO_LICENSE_REQUIRED_PATTERNS):
                mapping["no_license_required"] = col
                unassigned.remove(col)
                break

        for col in unassigned:
            if cls.match_column(col, METRIC_PATTERNS):
                mapping["metric"] = col
                unassigned.remove(col)
                break

        for col in unassigned:
            if cls.match_column(col, IS_END_OF_LIFE_PATTERNS):
                mapping["is_end_of_life"] = col
                unassigned.remove(col)
                break

        for col in unassigned:
            if cls.match_column(col, IS_END_OF_SUPPORT_PATTERNS):
                mapping["is_end_of_support"] = col
                unassigned.remove(col)
                break

        for col in unassigned:
            if cls.match_column(col, APP_ID_PATTERNS):
                mapping["app_id"] = col
                unassigned.remove(col)
                break

        for col in unassigned:
            if cls.match_column(col, NORMALIZED_APP_PATTERNS):
                mapping["normalized_application"] = col
                unassigned.remove(col)
                break

        for col in unassigned:
            if cls.match_column(col, OPERATING_SYSTEM_PATTERNS):
                mapping["operating_system"] = col
                unassigned.remove(col)
                break

        # Fallback if application still not detected: pick first column that looks like text
        if not mapping["application"] and columns:
            mapping["application"] = columns[0]

        return mapping

    @classmethod
    def parse_file_to_dataframe(cls, file_content: bytes, file_name: str) -> Tuple[pd.DataFrame, str]:
        """
        Parses CSV or Excel bytes into a pandas DataFrame.
        Returns: (dataframe, file_type)
        """
        fn_low = file_name.lower()
        if fn_low.endswith(".csv"):
            file_type = "CSV"
            # Try multiple encodings
            encodings = ["utf-8-sig", "utf-8", "latin1", "cp1252", "iso-8859-1"]
            df = None
            for enc in encodings:
                try:
                    df = pd.read_csv(io.BytesIO(file_content), encoding=enc, dtype=str)
                    break
                except Exception:
                    continue
            if df is None:
                raise ValueError(f"Could not parse CSV file '{file_name}' with supported encodings.")
            return df, file_type

        elif fn_low.endswith(".xlsx") or fn_low.endswith(".xls"):
            file_type = "XLSX" if fn_low.endswith(".xlsx") else "XLS"
            try:
                df = pd.read_excel(io.BytesIO(file_content), dtype=str)
                return df, file_type
            except Exception as e:
                raise ValueError(f"Could not parse Excel file '{file_name}': {e}")

        else:
            raise ValueError(f"Unsupported file format '{file_name}'. Please upload a CSV or Excel (.xlsx / .xls) file.")

    @classmethod
    def preview_upload(cls, file_content: bytes, file_name: str) -> Dict[str, Any]:
        """
        Generates upload validation metadata, detected columns, and 10-row preview.
        """
        df, file_type = cls.parse_file_to_dataframe(file_content, file_name)
        # Clean column names (strip whitespace)
        df.columns = [str(c).strip() for c in df.columns]
        
        # Replace NaN with empty string
        df = df.fillna("")
        
        columns = list(df.columns)
        mapping = cls.auto_detect_columns(columns)
        total_rows = len(df)
        
        # Convert first 10 rows to list of dicts
        preview_slice = df.head(10).to_dict(orient="records")

        # Confidence calculation
        confidence = "HIGH" if mapping.get("application") and (mapping.get("vendor") or mapping.get("version")) else "MEDIUM"
        if not mapping.get("application"):
            confidence = "LOW"

        return {
            "file_name": file_name,
            "file_type": file_type,
            "total_rows": total_rows,
            "columns": columns,
            "column_mapping": mapping,
            "confidence": confidence,
            "preview_rows": preview_slice,
        }
