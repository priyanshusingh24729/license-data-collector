"""
backfill_linux_system_packages.py
---------------------------------
One-off backfill script to update historical Linux system package records in
data/license_intelligence.db from classification="OPEN_SOURCE" to
classification="LINUX_SYSTEM_PACKAGE".

Ensures frontend get_tier() routes these records to:
Tier 3: OS & System Infrastructure (instead of Tier 2).
"""

import os
import sqlite3
import sys
import time


def backfill_linux_system_packages(db_path: str = None) -> dict:
    if db_path is None:
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "license_intelligence.db")

    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}", file=sys.stderr)
        return {"success": False, "error": f"Database not found at {db_path}"}

    print(f"Starting Linux system package classification backfill on {db_path}...")
    start_time = time.time()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    condition = """
        classification = 'OPEN_SOURCE'
        AND (
            override_reason LIKE '%Linux operating system package%'
            OR override_reason LIKE '%Linux system package%'
            OR override_reason LIKE '%LINUX_SYSTEM_PACKAGE%'
            OR evidence_quote LIKE '%Linux system package%'
            OR license_model LIKE '%Linux System Package%'
        )
    """

    results = {}

    try:
        # 1. Backfill upload_license_results
        cursor.execute(f"SELECT COUNT(*) FROM upload_license_results WHERE {condition}")
        ulr_count = cursor.fetchone()[0]
        print(f"Found {ulr_count:,} matching rows in 'upload_license_results' to backfill.")

        if ulr_count > 0:
            cursor.execute(f"""
                UPDATE upload_license_results
                SET classification = 'LINUX_SYSTEM_PACKAGE'
                WHERE {condition}
            """)
            conn.commit()
            print(f"Successfully updated {ulr_count:,} rows in 'upload_license_results'.")
        results["upload_license_results_updated"] = ulr_count

        # 2. Backfill resolved_products_cache
        cursor.execute(f"SELECT COUNT(*) FROM resolved_products_cache WHERE {condition}")
        rpc_count = cursor.fetchone()[0]
        print(f"Found {rpc_count:,} matching rows in 'resolved_products_cache' to backfill.")

        if rpc_count > 0:
            cursor.execute(f"""
                UPDATE resolved_products_cache
                SET classification = 'LINUX_SYSTEM_PACKAGE'
                WHERE {condition}
            """)
            conn.commit()
            print(f"Successfully updated {rpc_count:,} rows in 'resolved_products_cache'.")
        results["resolved_products_cache_updated"] = rpc_count

        elapsed = time.time() - start_time
        print(f"Backfill complete in {elapsed:.2f}s. Total records updated: {ulr_count + rpc_count:,}")
        results["success"] = True
        results["total_updated"] = ulr_count + rpc_count
        return results

    except Exception as e:
        conn.rollback()
        print(f"Error during backfill: {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


if __name__ == "__main__":
    res = backfill_linux_system_packages()
    if not res.get("success"):
        sys.exit(1)
