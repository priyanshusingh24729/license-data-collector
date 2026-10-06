"""
Snow SRS Master Database Indexer.
Reads the 907,437-row Snow Software Recognition Service (SRS) dump ('srs apps M.csv')
and builds a high-performance, indexed SQLite database at 'data/snow_srs_master.db'.

Preserves authentic Snow fields:
- App_ID
- Name
- OSType
- VersionName
- Normalized_Application
- Operating_System
- Major_Version
- Minor_Version
- Patch_Version
- NoLicenseRequired
- IsEndOfLife
- IsEndOfSupport
- Metric
"""

import os
import sys
import time
import sqlite3
import re
import pandas as pd

CSV_PATH = r"C:\Users\Priyanshu Singh\OneDrive - Silver Leaf Solutions Private Limited\Desktop\DB matching\srs apps M.csv"
DB_DIR = os.path.abspath("data")
DB_PATH = os.path.join(DB_DIR, "snow_srs_master.db")


def clean_text_key(text: str) -> str:
    """Normalizes application name key for fast, reliable matching."""
    if not text or pd.isna(text):
        return ""
    s = str(text).strip()
    # Strip TS- prefix (Snow Terminal Server package prefix)
    if s.upper().startswith("TS-"):
        s = s[3:].strip()
    elif s.upper().startswith("TS "):
        s = s[3:].strip()
    # Strip (reg) suffix
    s = re.sub(r"\s*\(reg\)\s*$", "", s, flags=re.IGNORECASE)
    # Collapse multiple spaces
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def clean_os_key(os_name: str) -> str:
    """Normalizes operating system string to broad category (windows, mac, linux, ios, android)."""
    if not os_name or pd.isna(os_name):
        return ""
    s = str(os_name).strip().lower()
    if "win" in s:
        return "windows"
    if "mac" in s or "darwin" in s or "osx" in s:
        return "mac"
    if "linux" in s or "unix" in s or "rhel" in s or "ubuntu" in s or "debian" in s:
        return "linux"
    if "ios" in s or "iphone" in s or "ipad" in s:
        return "ios"
    if "android" in s:
        return "android"
    return s


def build_snow_srs_master_index(csv_path: str = CSV_PATH, db_path: str = DB_PATH):
    if not os.path.exists(csv_path):
        print(f"ERROR: Snow CSV file not found at: {csv_path}")
        sys.exit(1)

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Remove existing db to ensure clean rebuild
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
            print(f"Removed existing database at {db_path}")
        except Exception as e:
            print(f"Warning removing old DB: {e}")

    print(f"Connecting to SQLite database at {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Enable SQLite high-speed bulk ingestion pragmas
    cursor.execute("PRAGMA journal_mode = OFF;")
    cursor.execute("PRAGMA synchronous = OFF;")
    cursor.execute("PRAGMA cache_size = -64000;")  # 64MB cache
    cursor.execute("PRAGMA temp_store = MEMORY;")

    print("Creating table 'snow_srs_master'...")
    cursor.execute("""
    CREATE TABLE snow_srs_master (
        app_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        clean_name TEXT NOT NULL,
        ostype INTEGER,
        version_name TEXT,
        normalized_application TEXT NOT NULL,
        clean_norm_app TEXT NOT NULL,
        operating_system TEXT,
        clean_os TEXT,
        major_version TEXT,
        minor_version TEXT,
        patch_version TEXT,
        no_license_required INTEGER NOT NULL,
        is_end_of_life INTEGER,
        is_end_of_support INTEGER,
        metric TEXT
    );
    """)

    print(f"Reading and indexing '{csv_path}' in chunks of 50,000...")
    chunk_size = 50000
    total_rows = 0
    start_time = time.perf_counter()

    insert_sql = """
    INSERT INTO snow_srs_master (
        app_id, name, clean_name, ostype, version_name,
        normalized_application, clean_norm_app, operating_system,
        clean_os, major_version, minor_version, patch_version,
        no_license_required, is_end_of_life, is_end_of_support, metric
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    for chunk_idx, chunk in enumerate(pd.read_csv(csv_path, chunksize=chunk_size, low_memory=False, encoding="utf-8-sig"), start=1):
        batch_records = []
        for _, row in chunk.iterrows():
            try:
                raw_app_id = row.get("App_ID")
                if pd.isna(raw_app_id):
                    continue
                app_id = int(raw_app_id)

                name = str(row.get("Name") or "").strip()
                clean_name = clean_text_key(name)

                raw_ostype = row.get("OSType")
                ostype = int(raw_ostype) if pd.notna(raw_ostype) and str(raw_ostype).strip().isdigit() else None

                ver_name = str(row.get("VersionName") or "").strip() if pd.notna(row.get("VersionName")) else None

                norm_app = str(row.get("Normalized_Application") or "").strip()
                clean_norm_app = clean_text_key(norm_app)

                op_sys = str(row.get("Operating_System") or "").strip() if pd.notna(row.get("Operating_System")) else None
                clean_os = clean_os_key(op_sys)

                # Versions as clean string numbers (e.g. "17", "2022")
                def parse_ver_str(val):
                    if pd.isna(val):
                        return None
                    s = str(val).strip()
                    if s.endswith(".0"):
                        s = s[:-2]
                    return s if s else None

                maj_ver = parse_ver_str(row.get("Major_Version"))
                min_ver = parse_ver_str(row.get("Minor_Version"))
                patch_ver = parse_ver_str(row.get("Patch_Version"))

                raw_nlr = row.get("NoLicenseRequired")
                nlr = int(str(raw_nlr).strip()) if pd.notna(raw_nlr) and str(raw_nlr).strip() in ("0", "1") else 0

                raw_eol = row.get("IsEndOfLife")
                eol = int(str(raw_eol).strip()) if pd.notna(raw_eol) and str(raw_eol).strip() in ("0", "1") else None

                raw_eos = row.get("IsEndOfSupport")
                eos = int(str(raw_eos).strip()) if pd.notna(raw_eos) and str(raw_eos).strip() in ("0", "1") else None

                metric_raw = row.get("Metric")
                metric = str(metric_raw).strip() if pd.notna(metric_raw) and str(metric_raw).strip() not in ("", "nan", "None", "NULL") else None

                batch_records.append((
                    app_id, name, clean_name, ostype, ver_name,
                    norm_app, clean_norm_app, op_sys, clean_os,
                    maj_ver, min_ver, patch_ver,
                    nlr, eol, eos, metric
                ))
            except Exception as row_err:
                continue

        cursor.executemany(insert_sql, batch_records)
        conn.commit()
        total_rows += len(batch_records)
        elapsed = time.perf_counter() - start_time
        print(f"  Chunk {chunk_idx}: Indexed {total_rows:,} rows ({total_rows/elapsed:.0f} rows/s)...")

    # Creating B-Tree indexes
    print("Building high-speed compound B-tree indices...")
    idx_start = time.perf_counter()
    cursor.execute("CREATE INDEX idx_snow_clean_name ON snow_srs_master (clean_name);")
    cursor.execute("CREATE INDEX idx_snow_clean_norm ON snow_srs_master (clean_norm_app);")
    cursor.execute("CREATE INDEX idx_snow_name_ver ON snow_srs_master (clean_name, major_version);")
    cursor.execute("CREATE INDEX idx_snow_norm_ver ON snow_srs_master (clean_norm_app, major_version);")
    cursor.execute("CREATE INDEX idx_snow_norm_os ON snow_srs_master (clean_norm_app, clean_os);")
    cursor.execute("CREATE INDEX idx_snow_nlr ON snow_srs_master (no_license_required);")
    conn.commit()
    idx_duration = time.perf_counter() - idx_start
    print(f"Indices built in {idx_duration:.2f}s.")

    # Re-enable standard SQLite journal mode
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA synchronous = NORMAL;")
    conn.commit()

    total_duration = time.perf_counter() - start_time
    file_size_mb = os.path.getsize(db_path) / (1024 * 1024)
    print("\n" + "=" * 75)
    print("SNOW SRS MASTER DATABASE INDEX COMPLETE")
    print("=" * 75)
    print(f"Total Rows Indexed:       {total_rows:,}")
    print(f"Total Database Size:      {file_size_mb:.2f} MB")
    print(f"Total Ingestion Time:     {total_duration:.2f}s ({total_rows/total_duration:.0f} rows/s)")

    # Audit Summary
    cursor.execute("SELECT COUNT(DISTINCT clean_norm_app) FROM snow_srs_master;")
    uniq_apps = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT clean_name) FROM snow_srs_master;")
    uniq_names = cursor.fetchone()[0]

    cursor.execute("SELECT metric, COUNT(*) FROM snow_srs_master GROUP BY metric ORDER BY COUNT(*) DESC;")
    metric_counts = cursor.fetchall()

    cursor.execute("SELECT no_license_required, COUNT(*) FROM snow_srs_master GROUP BY no_license_required;")
    nlr_counts = cursor.fetchall()

    print(f"Unique Normalized Apps:   {uniq_apps:,}")
    print(f"Unique Signature Names:   {uniq_names:,}")
    print("\nNoLicenseRequired Distribution:")
    for nlr_val, cnt in nlr_counts:
        label = "0 (License Required / YES)" if nlr_val == 0 else "1 (No License Required / NO)"
        print(f"  • {label}: {cnt:,} ({cnt/total_rows*100:.1f}%)")

    print("\nMetric Distribution:")
    for m_val, cnt in metric_counts:
        m_str = m_val if m_val else "NULL / Missing"
        print(f"  • {m_str}: {cnt:,} ({cnt/total_rows*100:.1f}%)")
    print("=" * 75)

    conn.close()


if __name__ == "__main__":
    build_snow_srs_master_index()
