"""
Windows Endpoint Application Discovery Collector Entrypoint.
Runs read-only software discovery from Windows Registry and modern packages, normalizes entries,
deduplicates installations, generates offline JSON reports, and optionally uploads to backend.
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, Optional

# Add parent directory to sys.path if executed directly as script
if __name__ == "__main__" or "collector" in __name__:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    grandparent_dir = os.path.dirname(parent_dir)
    for p in [grandparent_dir, parent_dir, current_dir]:
        if p not in sys.path:
            sys.path.insert(0, p)

try:
    from .config import AgentConfig, AGENT_VERSION
    from .logger import setup_logger
    from .registry_scanner import WindowsRegistryScanner
    from .package_scanner import WindowsPackageScanner
    from .winget_scanner import WindowsWingetScanner
    from .start_menu_scanner import WindowsStartMenuScanner
    from .inventory_builder import InventoryBuilder
    from .api_client import IngestionApiClient
except ImportError:
    try:
        from windows.config import AgentConfig, AGENT_VERSION
        from windows.logger import setup_logger
        from windows.registry_scanner import WindowsRegistryScanner
        from windows.package_scanner import WindowsPackageScanner
        from windows.winget_scanner import WindowsWingetScanner
        from windows.start_menu_scanner import WindowsStartMenuScanner
        from windows.inventory_builder import InventoryBuilder
        from windows.api_client import IngestionApiClient
    except ImportError:
        from config import AgentConfig, AGENT_VERSION
        from logger import setup_logger
        from registry_scanner import WindowsRegistryScanner
        from package_scanner import WindowsPackageScanner
        from winget_scanner import WindowsWingetScanner
        from start_menu_scanner import WindowsStartMenuScanner
        from inventory_builder import InventoryBuilder
        from api_client import IngestionApiClient


class WindowsEndpointCollector:
    """Orchestrates safe, read-only Windows application discovery across multiple sources."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.logger = setup_logger("windows-collector", quiet=config.quiet)
        self.registry_scanner = WindowsRegistryScanner()
        self.package_scanner = WindowsPackageScanner()
        self.winget_scanner = WindowsWingetScanner()
        self.start_menu_scanner = WindowsStartMenuScanner()
        self.inventory_builder = InventoryBuilder(config)
        self.api_client = IngestionApiClient(config)

    def run_discovery(self) -> Dict[str, Any]:
        """
        Executes full discovery pipeline across registry hives, AppX packages, Winget, and Start Menu.
        """
        start_time = datetime.now(timezone.utc)
        self.logger.info("Starting Windows Endpoint Application Discovery (read-only)...")

        # 1. Scan Registry Hives (64-bit, 32-bit, User)
        reg_entries, reg_counts = self.registry_scanner.scan_all_hives()
        self.logger.info(
            f"Registry Scan Completed: {len(reg_entries)} raw entries found "
            f"(64-bit: {reg_counts.get('registry_machine_64', 0)}, "
            f"32-bit: {reg_counts.get('registry_machine_32', 0)}, "
            f"User: {reg_counts.get('registry_user', 0)})"
        )

        # 2. Scan Modern Windows Packages (AppX / MSIX)
        pkg_entries = []
        if self.config.include_packages:
            pkg_entries = self.package_scanner.scan_packages()
            self.logger.info(f"Windows Package Scan Completed: {len(pkg_entries)} packages found.")

        # 3. Scan Winget Packages
        winget_entries = self.winget_scanner.scan_packages()
        self.logger.info(f"Winget Scan Completed: {len(winget_entries)} packages found.")

        # 4. Scan Start Menu Shortcuts
        start_menu_entries = self.start_menu_scanner.scan_shortcuts()
        self.logger.info(f"Start Menu Scan Completed: {len(start_menu_entries)} shortcuts found.")

        all_raw_entries = reg_entries + pkg_entries + winget_entries + start_menu_entries

        # 5. Build & Deduplicate Payload
        payload = self.inventory_builder.build_payload(all_raw_entries)
        deduped_apps = payload.get("applications", [])
        device_meta = payload.get("device", {})

        # Compute Statistics
        with_pub = sum(1 for a in deduped_apps if a.get("publisher"))
        without_pub = len(deduped_apps) - with_pub
        with_ver = sum(1 for a in deduped_apps if a.get("version"))
        without_ver = len(deduped_apps) - with_ver

        sources_summary = {
            "registry_machine_64": reg_counts.get("registry_machine_64", 0),
            "registry_machine_32": reg_counts.get("registry_machine_32", 0),
            "registry_user": reg_counts.get("registry_user", 0),
            "windows_packages": len(pkg_entries),
            "winget_packages": len(winget_entries),
            "start_menu_shortcuts": len(start_menu_entries),
            "total_raw_entries": len(all_raw_entries),
            "deduplicated_applications": len(deduped_apps),
        }

        # Attach telemetry and discovery summary directly to payload
        payload["discovery_summary"] = sources_summary
        payload["discovery_timestamp"] = datetime.now(timezone.utc).isoformat()
        if not deduped_apps:
            payload["scan_warning"] = "ZERO_APPLICATIONS_DETECTED. Verify administrator permissions or registry access."

        # 4. Save Local Reports (JSON, Standardized CSV & XLSX)
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = self.config.output_file or f"inventory_{now_str}.json"
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Local offline inventory saved to: {out_path}")
        except Exception as e:
            self.logger.warning(f"Could not save local JSON report: {e}")

        # Automatically generate standardized Application Inventory Excel and CSV
        try:
            from backend.inventory.export.standardized_inventory_exporter import StandardizedInventoryExporter
            base_prefix = out_path.rsplit(".", 1)[0] if "." in out_path else out_path
            csv_path = f"{base_prefix}.csv"
            xlsx_path = f"{base_prefix}.xlsx"

            df_std = StandardizedInventoryExporter.transform_inventory(
                records=deduped_apps,
                scan_timestamp=payload.get("discovery_timestamp"),
                device_context=device_meta,
            )
            with open(csv_path, "wb") as f_csv:
                f_csv.write(StandardizedInventoryExporter.to_csv_bytes(df_std))
            with open(xlsx_path, "wb") as f_xlsx:
                f_xlsx.write(StandardizedInventoryExporter.to_excel_bytes(df_std))
            self.logger.info(f"Standardized Application Inventory saved to:\n  CSV: {csv_path}\n  Excel: {xlsx_path}")
        except Exception as e:
            self.logger.warning(f"Could not generate standardized offline export: {e}")

        # 5. Submit to Backend API if not dry-run
        upload_status = "SKIPPED_DRY_RUN"
        upload_response = None
        if not self.config.dry_run:
            self.logger.info(f"Uploading inventory to backend: {self.config.backend_url}...")
            ok, status_code, resp_data = self.api_client.upload_inventory(payload)
            if ok:
                upload_status = "UPLOADED"
                upload_response = resp_data
                self.logger.info(f"Successfully ingested {len(deduped_apps)} applications into backend.")
            else:
                upload_status = "FAILED"
                upload_response = resp_data
                self.logger.warning(f"Backend upload failed (Status: {status_code}). Offline inventory preserved locally.")

        duration_sec = (datetime.now(timezone.utc) - start_time).total_seconds()

        return {
            "status": "SUCCESS",
            "agent_version": self.config.agent_version,
            "device": device_meta,
            "application_count": len(deduped_apps),
            "raw_entries_count": len(all_raw_entries),
            "statistics": {
                "with_publisher": with_pub,
                "without_publisher": without_pub,
                "with_version": with_ver,
                "without_version": without_ver,
            },
            "sources": sources_summary,
            "local_report_file": out_path,
            "upload_status": upload_status,
            "upload_response": upload_response,
            "duration_seconds": duration_sec,
            "payload": payload
        }


def main():
    """Command-line interface entrypoint."""
    parser = argparse.ArgumentParser(
        description=f"Commercial License Intelligence — Windows Endpoint Collector v{AGENT_VERSION}"
    )
    parser.add_argument("--dry-run", action="store_true", help="Scan laptop and save local JSON without uploading to backend")
    parser.add_argument("--output", "-o", type=str, default=None, help="Custom path for generated JSON inventory file")
    parser.add_argument("--backend-url", "-u", type=str, default=None, help="Backend API base URL (default: http://localhost:8000)")
    parser.add_argument("--api-key", "-k", type=str, default=None, help="Optional agent authentication API key")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress verbose logging output")
    parser.add_argument("--no-packages", action="store_true", help="Skip modern Windows AppX/MSIX package scan")

    args = parser.parse_args()

    config = AgentConfig(
        backend_url=args.backend_url or os.getenv("BACKEND_URL", "http://localhost:8000"),
        api_key=args.api_key or os.getenv("AGENT_API_KEY", None),
        dry_run=args.dry_run,
        output_file=args.output,
        quiet=args.quiet,
        include_packages=not args.no_packages
    )

    collector = WindowsEndpointCollector(config)
    result = collector.run_discovery()

    # Print summary to console
    print("\n" + "=" * 60)
    print(f" WINDOWS ENDPOINT INVENTORY DISCOVERY SUMMARY")
    print("=" * 60)
    dev = result["device"]
    print(f" Device Key        : {dev.get('device_key')}")
    print(f" Hostname          : {dev.get('hostname')}")
    print(f" OS & Architecture : {dev.get('operating_system')} {dev.get('os_version')} ({dev.get('architecture')})")
    print(f" Agent Version     : {result.get('agent_version')}")
    print("-" * 60)
    print(f" Total Apps Found  : {result['application_count']} (Deduplicated from {result['raw_entries_count']} raw records)")
    print(f" Sources Breakdown :")
    for s_name, s_cnt in result["sources"].items():
        print(f"   • {s_name:<20}: {s_cnt}")
    stats = result["statistics"]
    print(f" Metadata Quality  :")
    print(f"   • With Publisher  : {stats['with_publisher']} | Without: {stats['without_publisher']}")
    print(f"   • With Version    : {stats['with_version']} | Without: {stats['without_version']}")
    print("-" * 60)
    print(f" Local Output File : {result['local_report_file']}")
    print(f" Backend Upload    : {result['upload_status']}")
    print(f" Duration          : {result['duration_seconds']:.2f}s")
    print("=" * 60 + "\n")

    if result["application_count"] == 0:
        print("!" * 60)
        print(" [WARNING] ZERO APPLICATIONS DETECTED!")
        print(" Possible causes:")
        print("   1. Missing registry read permissions (Run PowerShell / CMD as Administrator)")
        print("   2. PowerShell execution policy restricted AppX / Package discovery")
        print("   3. Registry paths HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall were unreadable")
        print("!" * 60 + "\n")


if __name__ == "__main__":
    main()
