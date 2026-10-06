"""
Script to verify PostgreSQL/Supabase database connectivity, create/verify all tables for Steps 1-17,
and report schema table counts.
"""

import sys
import os

root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from backend.database.connection import engine, Base, check_db_connection, SessionLocal
import backend.models  # Registers all models with Base.metadata

def main():
    print("--- 1. Testing Database Connectivity ---")
    status = check_db_connection()
    print(f"Status: {status}")

    if not status.get("connected"):
        print(f"ERROR: Database is not connected: {status.get('message')}")
        sys.exit(1)

    print("\n--- 2. Creating/Verifying All Tables (Steps 1 to 17) ---")
    Base.metadata.create_all(bind=engine)
    print("Base.metadata.create_all executed successfully.")

    print("\n--- 3. Verifying All Required Tables ---")
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Total Tables Discovered: {len(tables)}")
    for t in sorted(tables):
        print(f"  - {t}")

    required_tables = [
        "applications",
        "research_batches",
        "research_batch_items",
        "license_sources",
        "collected_documents",
        "document_pages",
        "api_documents",
        "license_facts",
        "license_evidence",
        "fact_validation_runs",
        "license_profiles",
        "license_profile_facts",
        "profile_versions",
        "discovery_runs",
        "extraction_runs",
        "source_monitors",
        "monitoring_runs",
        "license_fact_changes",
        "license_alerts",
        "devices",
        "detected_applications",
        "device_applications",
        "application_resolution_queue",
        "license_entitlements",
        "license_consumption",
        "license_positions",
        "license_position_history",
        "audit_events",
        "quality_issues",
        "license_research_queue",
    ]

    missing = [t for t in required_tables if t not in tables]
    if missing:
        print(f"\nERROR: Missing tables: {missing}")
        sys.exit(1)
    else:
        print("\nSUCCESS: All 29 required tables for Steps 1 through 17 are present and verified in PostgreSQL/Supabase!")

if __name__ == "__main__":
    main()
