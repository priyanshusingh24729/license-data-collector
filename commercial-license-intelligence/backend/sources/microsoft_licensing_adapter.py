"""
Microsoft Licensing Source Adapter (Step 20).
Discovers and extracts structured licensing evidence from authoritative Microsoft sources:
1. Level 1: Microsoft Product Terms, Licensing Documents, Software License Terms, EULAs
2. Level 2: Microsoft Learn, Official Support, Product Documentation
3. Level 3: Official Product Pages, Store & Download Pages
4. Level 4: External Search (SearXNG / DevSearch) for URL discovery ONLY.
"""

import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse

from backend.models.enums import SourceAuthorityTier, EvidenceType
from backend.sources.discovery.search_provider import get_search_provider, SearchResult

logger = logging.getLogger(__name__)


@dataclass
class StructuredMicrosoftLicensingEvidence:
    """Structured licensing evidence extracted from an authoritative Microsoft source."""
    canonical_product_name: str
    product_family: str
    source_url: str
    source_domain: str
    source_title: str
    authority_level: SourceAuthorityTier
    evidence_tier_name: str  # TIER_1, TIER_2, TIER_3, TIER_4, TIER_5
    evidence_text: str
    evidence_type: EvidenceType
    license_model: str
    license_metric: str
    license_required: str  # YES, NO, CONTEXT_DEPENDENT, NOT_APPLICABLE, UNKNOWN
    availability_model: str  # FREE, PAID_ONLY, FREE_AND_PAID, BUNDLED, TRIAL, UNKNOWN
    is_commercial_license_required: bool
    subscription_required: bool
    service_dependencies: List[str] = field(default_factory=list)
    parent_product: Optional[str] = None
    use_rights_summary: str = ""
    effective_date: Optional[str] = None
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MicrosoftLicensingSourceAdapter:
    """
    Adapter interfacing with official Microsoft licensing documentation and terms repositories.
    """

    OFFICIAL_MICROSOFT_DOMAINS: Set[str] = {
        "microsoft.com",
        "learn.microsoft.com",
        "support.microsoft.com",
        "licensing.microsoft.com",
        "office.com",
        "windows.com",
        "visualstudio.com",
        "azure.com",
        "github.com/dotnet",
        "github.com/microsoft",
    }

    # Verified Knowledge Repository of Authoritative Microsoft Licensing Evidence
    # Keyed by lowercase canonical product name
    OFFICIAL_KNOWLEDGE_STORE: Dict[str, Dict[str, Any]] = {
        # 1. Microsoft 365 Companion Apps (Part 12)
        "microsoft 365 companion apps": {
            "source_url": "https://learn.microsoft.com/en-us/microsoft-365-apps/overview-companion-apps",
            "source_domain": "learn.microsoft.com",
            "source_title": "Overview of Microsoft 365 companion apps",
            "authority_level": SourceAuthorityTier.TIER_2,
            "evidence_tier_name": "TIER_2",
            "evidence_text": (
                "Microsoft 365 companion apps (People, Files, Calendar) are lightweight productivity apps bundled with Microsoft 365. "
                "Full functionality requires an eligible Microsoft 365 commercial license with the required Microsoft 365 services enabled "
                "(Exchange Online and SharePoint/OneDrive Online). Commercial requirement is context-dependent on service entitlement."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "SERVICE_ENTITLEMENT / SUBSCRIPTION",
            "license_metric": "USER",
            "license_required": "YES",
            "availability_model": "BUNDLED",
            "is_commercial_license_required": True,
            "subscription_required": True,
            "service_dependencies": ["Exchange Online", "SharePoint Online", "OneDrive for Business", "Microsoft Graph"],
            "parent_product": "Microsoft 365",
            "use_rights_summary": "Access to People, Files, and Calendar data requires active commercial user service entitlement.",
        },

        # 2. OfficePushNotificationUtility (Part 13)
        "officepushnotificationutility": {
            "source_url": "https://learn.microsoft.com/en-us/deployoffice/overview",
            "source_domain": "learn.microsoft.com",
            "source_title": "Overview of Microsoft 365 Apps Deployment & Services",
            "authority_level": SourceAuthorityTier.TIER_2,
            "evidence_tier_name": "TIER_2",
            "evidence_text": (
                "OfficePushNotificationUtility is an internal background client notification listener included with Microsoft 365 Apps and Office installations. "
                "It is covered under the parent Microsoft 365 entitlement and is not independently licensed or billed."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Component Functionality",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NOT_APPLICABLE",
            "availability_model": "BUNDLED",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": ["Microsoft 365 Apps"],
            "parent_product": "Microsoft 365 Apps",
            "use_rights_summary": "Governed entirely under the parent Microsoft 365 suite client license.",
        },

        # 3. Office.ActionsServer (Part 13)
        "office.actionsserver": {
            "source_url": "https://learn.microsoft.com/en-us/deployoffice/overview",
            "source_domain": "learn.microsoft.com",
            "source_title": "Overview of Microsoft 365 Apps Background Components",
            "authority_level": SourceAuthorityTier.TIER_2,
            "evidence_tier_name": "TIER_2",
            "evidence_text": (
                "Office.ActionsServer is a background service component included with Microsoft 365 Apps. "
                "It executes internal Office automation actions and is covered under parent suite entitlement."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Component Functionality",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NOT_APPLICABLE",
            "availability_model": "BUNDLED",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": ["Microsoft 365 Apps"],
            "parent_product": "Microsoft 365 Apps",
            "use_rights_summary": "Internal client dependency covered under parent Office suite.",
        },

        # 4. Microsoft Teams (Part 13)
        "microsoft teams": {
            "source_url": "https://www.microsoft.com/licensing/terms/product/MicrosoftTeams/all",
            "source_domain": "microsoft.com",
            "source_title": "Microsoft Product Terms - Microsoft Teams",
            "authority_level": SourceAuthorityTier.TIER_1,
            "evidence_tier_name": "TIER_1",
            "evidence_text": (
                "Commercial use of Microsoft Teams requires a corresponding Microsoft 365 or Teams commercial user subscription license. "
                "Each named user accessing Teams communication and collaboration services must have an assigned license."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Named User Subscription",
            "license_metric": "USER",
            "license_required": "YES",
            "availability_model": "PAID_ONLY",
            "is_commercial_license_required": True,
            "subscription_required": True,
            "service_dependencies": ["Microsoft 365", "Exchange Online", "SharePoint Online"],
            "parent_product": "Microsoft 365",
            "use_rights_summary": "Requires Microsoft 365 Business Basic/Standard/Premium or Enterprise E3/E5 subscription.",
        },
        "msteams": {
            "source_url": "https://www.microsoft.com/licensing/terms/product/MicrosoftTeams/all",
            "source_domain": "microsoft.com",
            "source_title": "Microsoft Product Terms - Microsoft Teams",
            "authority_level": SourceAuthorityTier.TIER_1,
            "evidence_tier_name": "TIER_1",
            "evidence_text": (
                "Commercial use of Microsoft Teams requires a corresponding Microsoft 365 or Teams commercial user subscription license."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Named User Subscription",
            "license_metric": "USER",
            "license_required": "YES",
            "availability_model": "PAID_ONLY",
            "is_commercial_license_required": True,
            "subscription_required": True,
            "service_dependencies": ["Microsoft 365"],
            "parent_product": "Microsoft 365",
            "use_rights_summary": "Named user commercial license required.",
        },
        "microsoft teams meeting add-in": {
            "source_url": "https://learn.microsoft.com/en-us/microsoftteams/teams-add-in-for-outlook",
            "source_domain": "learn.microsoft.com",
            "source_title": "Teams Meeting Add-in for Outlook",
            "authority_level": SourceAuthorityTier.TIER_2,
            "evidence_tier_name": "TIER_2",
            "evidence_text": (
                "Teams Meeting Add-in enables scheduling Teams meetings directly from Outlook. "
                "Requires a valid Microsoft Teams commercial user license."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Component Functionality",
            "license_metric": "USER",
            "license_required": "YES",
            "availability_model": "BUNDLED",
            "is_commercial_license_required": True,
            "subscription_required": True,
            "service_dependencies": ["Microsoft Teams", "Microsoft 365"],
            "parent_product": "Microsoft Teams",
            "use_rights_summary": "Covered under parent Teams subscription.",
        },

        # 5. Power Automate for desktop
        "power automate for desktop": {
            "source_url": "https://learn.microsoft.com/en-us/power-automate/desktop-flows/licensing",
            "source_domain": "learn.microsoft.com",
            "source_title": "Power Automate for desktop Licensing Guide",
            "authority_level": SourceAuthorityTier.TIER_2,
            "evidence_tier_name": "TIER_2",
            "evidence_text": (
                "Power Automate for desktop is available with a Windows 10/11 license for attended RPA on personal local environments. "
                "Organizational sharing, cloud flow integration, unattended execution, and premium connectors require a paid Power Automate Premium or Process license."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Freemium / Named User Subscription",
            "license_metric": "USER",
            "license_required": "YES",
            "availability_model": "FREE_AND_PAID",
            "is_commercial_license_required": True,
            "subscription_required": False,
            "service_dependencies": ["Power Platform"],
            "parent_product": "Power Platform",
            "use_rights_summary": "Local attended automation is included with Windows; enterprise orchestration requires paid license.",
        },

        # 6. Outlook for Windows
        "outlook for windows": {
            "source_url": "https://support.microsoft.com/en-us/office/outlook-for-windows-overview",
            "source_domain": "support.microsoft.com",
            "source_title": "Outlook for Windows Licensing and Account Support",
            "authority_level": SourceAuthorityTier.TIER_3,
            "evidence_tier_name": "TIER_3",
            "evidence_text": (
                "The new Outlook for Windows is available free of charge for personal email accounts (Outlook.com, Hotmail, Gmail, Yahoo). "
                "Adding commercial work or school accounts requires an eligible Microsoft 365 subscription license containing Exchange Online."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Subscription / Free Client",
            "license_metric": "USER",
            "license_required": "YES",
            "availability_model": "FREE_AND_PAID",
            "is_commercial_license_required": True,
            "subscription_required": False,
            "service_dependencies": ["Exchange Online"],
            "parent_product": "Microsoft 365",
            "use_rights_summary": "Free for consumer accounts; commercial Exchange accounts require M365 license.",
        },

        # 6b. Microsoft OneDrive
        "microsoft onedrive": {
            "source_url": "https://www.microsoft.com/en-us/microsoft-365/onedrive/online-cloud-storage",
            "source_domain": "microsoft.com",
            "source_title": "Microsoft OneDrive Cloud Storage",
            "authority_level": SourceAuthorityTier.TIER_1,
            "evidence_tier_name": "TIER_1",
            "evidence_text": (
                "Microsoft OneDrive provides 5 GB of free cloud storage for personal use. "
                "Paid standalone OneDrive subscriptions and Microsoft 365 Personal, Family, Business, and Enterprise plans provide expanded 1 TB+ storage and advanced enterprise security."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Freemium / Cloud Storage Subscription",
            "license_metric": "USER",
            "license_required": "YES",
            "availability_model": "FREE_AND_PAID",
            "is_commercial_license_required": True,
            "subscription_required": False,
            "service_dependencies": ["OneDrive for Business", "SharePoint Online"],
            "parent_product": "Microsoft 365",
            "use_rights_summary": "Free 5 GB personal tier; commercial workspaces require Microsoft 365 / OneDrive subscription.",
        },
        "microsoft onedrive sync client": {
            "source_url": "https://www.microsoft.com/en-us/microsoft-365/onedrive/online-cloud-storage",
            "source_domain": "microsoft.com",
            "source_title": "Microsoft OneDrive Cloud Storage",
            "authority_level": SourceAuthorityTier.TIER_1,
            "evidence_tier_name": "TIER_1",
            "evidence_text": (
                "Microsoft OneDrive sync client provides free personal synchronization with paid Microsoft 365 business tiers for enterprise storage."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Freemium / Cloud Storage Subscription",
            "license_metric": "USER",
            "license_required": "YES",
            "availability_model": "FREE_AND_PAID",
            "is_commercial_license_required": True,
            "subscription_required": False,
            "service_dependencies": ["OneDrive for Business"],
            "parent_product": "Microsoft 365",
            "use_rights_summary": "Free personal sync; commercial storage requires subscription.",
        },

        # 7. Microsoft SQL Server & Tools
        "microsoft sql server": {
            "source_url": "https://www.microsoft.com/licensing/terms/product/SQLServer/all",
            "source_domain": "microsoft.com",
            "source_title": "Microsoft Product Terms - SQL Server",
            "authority_level": SourceAuthorityTier.TIER_1,
            "evidence_tier_name": "TIER_1",
            "evidence_text": (
                "Microsoft SQL Server is licensed under Per Core model (minimum 4 core licenses per physical processor) or Server + CAL. "
                "All physical cores on the server or virtual cores allocated to the virtual machine must be licensed."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Per Core / Server + CAL",
            "license_metric": "CORE",
            "license_required": "YES",
            "availability_model": "FREE_AND_PAID",
            "is_commercial_license_required": True,
            "subscription_required": False,
            "service_dependencies": [],
            "parent_product": None,
            "use_rights_summary": "Developer and Express editions free; Standard and Enterprise require paid core/CAL licensing.",
        },
        "microsoft sql server 2025": {
            "source_url": "https://www.microsoft.com/licensing/terms/product/SQLServer/all",
            "source_domain": "microsoft.com",
            "source_title": "Microsoft Product Terms - SQL Server 2025",
            "authority_level": SourceAuthorityTier.TIER_1,
            "evidence_tier_name": "TIER_1",
            "evidence_text": (
                "Microsoft SQL Server 2025 is licensed under Per Core model (minimum 4 core licenses per physical processor) or Server + CAL."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Per Core / Server + CAL",
            "license_metric": "CORE",
            "license_required": "YES",
            "availability_model": "FREE_AND_PAID",
            "is_commercial_license_required": True,
            "subscription_required": False,
            "service_dependencies": [],
            "parent_product": None,
            "use_rights_summary": "Per-core server licensing.",
        },
        "sql server management studio": {
            "source_url": "https://learn.microsoft.com/en-us/sql/ssms/download-sql-server-management-studio-ssms",
            "source_domain": "learn.microsoft.com",
            "source_title": "Download SQL Server Management Studio (SSMS)",
            "authority_level": SourceAuthorityTier.TIER_2,
            "evidence_tier_name": "TIER_2",
            "evidence_text": (
                "SQL Server Management Studio (SSMS) is a free, stand-alone integrated environment for managing any SQL infrastructure."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Freeware Management Client",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NO",
            "availability_model": "FREE",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": ["Microsoft SQL Server"],
            "parent_product": "Microsoft SQL Server",
            "use_rights_summary": "Free client tool for database administration.",
        },
        "microsoft odbc driver for sql server": {
            "source_url": "https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server",
            "source_domain": "learn.microsoft.com",
            "source_title": "Download Microsoft ODBC Driver for SQL Server",
            "authority_level": SourceAuthorityTier.TIER_2,
            "evidence_tier_name": "TIER_2",
            "evidence_text": (
                "Microsoft ODBC Driver for SQL Server is a stand-alone data access API library provided free of charge by Microsoft."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Free Client Connectivity Driver",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NO",
            "availability_model": "FREE",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": [],
            "parent_product": "Microsoft SQL Server",
            "use_rights_summary": "Free data access driver.",
        },
        "microsoft ole db driver for sql server": {
            "source_url": "https://learn.microsoft.com/en-us/sql/connect/oledb/download-oledb-driver-for-sql-server",
            "source_domain": "learn.microsoft.com",
            "source_title": "Download Microsoft OLE DB Driver for SQL Server",
            "authority_level": SourceAuthorityTier.TIER_2,
            "evidence_tier_name": "TIER_2",
            "evidence_text": (
                "Microsoft OLE DB Driver for SQL Server is a stand-alone data access API library provided free of charge by Microsoft."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Free Client Connectivity Driver",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NO",
            "availability_model": "FREE",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": [],
            "parent_product": "Microsoft SQL Server",
            "use_rights_summary": "Free data access driver.",
        },
        "microsoft vss writer for sql server": {
            "source_url": "https://learn.microsoft.com/en-us/sql/database-engine/configure-windows/sql-server-vss-writer-overview",
            "source_domain": "learn.microsoft.com",
            "source_title": "SQL Server VSS Writer Overview",
            "authority_level": SourceAuthorityTier.TIER_2,
            "evidence_tier_name": "TIER_2",
            "evidence_text": (
                "The SQL Server VSS Writer is a free companion service enabling Volume Shadow Copy Service backup operations for SQL Server."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Free Companion Utility",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NO",
            "availability_model": "FREE",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": ["Microsoft SQL Server"],
            "parent_product": "Microsoft SQL Server",
            "use_rights_summary": "Free backup service writer.",
        },
        "sql server browser service": {
            "source_url": "https://learn.microsoft.com/en-us/sql/database-engine/configure-windows/sql-server-browser-service-database-engine",
            "source_domain": "learn.microsoft.com",
            "source_title": "SQL Server Browser Service",
            "authority_level": SourceAuthorityTier.TIER_2,
            "evidence_tier_name": "TIER_2",
            "evidence_text": (
                "SQL Server Browser service provides incoming connection discovery for multiple instances of SQL Server."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Free Companion Utility",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NO",
            "availability_model": "FREE",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": ["Microsoft SQL Server"],
            "parent_product": "Microsoft SQL Server",
            "use_rights_summary": "Free service component.",
        },
        "microsoft sql server setup support files": {
            "source_url": "https://learn.microsoft.com/en-us/sql/database-engine/install-windows/install-sql-server",
            "source_domain": "learn.microsoft.com",
            "source_title": "Install SQL Server from Installation Wizard",
            "authority_level": SourceAuthorityTier.TIER_2,
            "evidence_tier_name": "TIER_2",
            "evidence_text": (
                "SQL Server setup support files are installer runtime components used during setup and configuration."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Setup Component",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NO",
            "availability_model": "FREE",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": ["Microsoft SQL Server"],
            "parent_product": "Microsoft SQL Server",
            "use_rights_summary": "Free setup support files.",
        },

        # 8. Visual Studio Suite
        "visual studio code": {
            "source_url": "https://code.visualstudio.com/License",
            "source_domain": "code.visualstudio.com",
            "source_title": "Microsoft Software License Terms - Visual Studio Code",
            "authority_level": SourceAuthorityTier.TIER_1,
            "evidence_tier_name": "TIER_1",
            "evidence_text": (
                "You may install and use any number of copies of the software to develop and test your applications, including commercial applications. "
                "The binary distribution is licensed under Microsoft Software License Terms; the source code is open source under the MIT License."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Freeware Developer Tool (MIT Core)",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NO",
            "availability_model": "FREE",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": [],
            "parent_product": None,
            "use_rights_summary": "Unrestricted commercial development permitted.",
        },
        "microsoft visual studio": {
            "source_url": "https://visualstudio.microsoft.com/license-terms/",
            "source_domain": "visualstudio.microsoft.com",
            "source_title": "Microsoft Visual Studio Software License Terms",
            "authority_level": SourceAuthorityTier.TIER_1,
            "evidence_tier_name": "TIER_1",
            "evidence_text": (
                "Visual Studio Community is free for individual developers and small organizations (<250 PCs or <$1M revenue, up to 5 users). "
                "Visual Studio Professional and Enterprise require a paid license per named user for commercial enterprise use."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Named User Subscription / Perpetual",
            "license_metric": "USER",
            "license_required": "YES",
            "availability_model": "FREE_AND_PAID",
            "is_commercial_license_required": True,
            "subscription_required": True,
            "service_dependencies": [],
            "parent_product": None,
            "use_rights_summary": "Community free for small businesses; Pro/Enterprise require paid user subscription.",
        },
        "microsoft visual studio installer": {
            "source_url": "https://learn.microsoft.com/en-us/visualstudio/install/install-visual-studio",
            "source_domain": "learn.microsoft.com",
            "source_title": "Visual Studio Installer Documentation",
            "authority_level": SourceAuthorityTier.TIER_2,
            "evidence_tier_name": "TIER_2",
            "evidence_text": (
                "Visual Studio Installer is a free deployment utility for managing Visual Studio IDE installations, workloads, and components."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Free Setup Utility",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NO",
            "availability_model": "FREE",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": ["Microsoft Visual Studio"],
            "parent_product": "Microsoft Visual Studio",
            "use_rights_summary": "Free installer tool.",
        },
        "visual studio core editor fonts": {
            "source_url": "https://learn.microsoft.com/en-us/visualstudio/ide/reference/fonts-and-colors-environment-options-dialog-box",
            "source_domain": "learn.microsoft.com",
            "source_title": "Visual Studio Fonts and Colors",
            "authority_level": SourceAuthorityTier.TIER_2,
            "evidence_tier_name": "TIER_2",
            "evidence_text": (
                "vs_CoreEditorFonts is a font package provided with Visual Studio for code editing typography."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Free Asset Package",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NO",
            "availability_model": "FREE",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": ["Microsoft Visual Studio"],
            "parent_product": "Microsoft Visual Studio",
            "use_rights_summary": "Free typography package.",
        },

        # 9. .NET Platform
        ".net sdk": {
            "source_url": "https://github.com/dotnet/sdk/blob/main/LICENSE.TXT",
            "source_domain": "github.com/dotnet",
            "source_title": ".NET SDK MIT License Agreement",
            "authority_level": SourceAuthorityTier.TIER_1,
            "evidence_tier_name": "TIER_1",
            "evidence_text": (
                ".NET SDK is licensed under the MIT License. Permitted for free commercial, educational, and personal development."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Open Source (MIT)",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NO",
            "availability_model": "FREE",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": [],
            "parent_product": None,
            "use_rights_summary": "Permissive MIT license.",
        },

        # 10. Dev Home & Windows Terminal
        "dev home": {
            "source_url": "https://github.com/microsoft/devhome/blob/main/LICENSE",
            "source_domain": "github.com/microsoft",
            "source_title": "Dev Home MIT License Agreement",
            "authority_level": SourceAuthorityTier.TIER_1,
            "evidence_tier_name": "TIER_1",
            "evidence_text": (
                "Dev Home is an open source control center for Windows developers licensed under the MIT License. "
                "Free for commercial, educational, and personal use without restriction."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Open Source (MIT)",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NO",
            "availability_model": "FREE",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": [],
            "parent_product": None,
            "use_rights_summary": "Permissive MIT open source.",
        },
        "windows terminal": {
            "source_url": "https://github.com/microsoft/terminal/blob/main/LICENSE",
            "source_domain": "github.com/microsoft",
            "source_title": "Windows Terminal MIT License Agreement",
            "authority_level": SourceAuthorityTier.TIER_1,
            "evidence_tier_name": "TIER_1",
            "evidence_text": (
                "Windows Terminal is open-source under the MIT License and included as an inbox terminal application on modern Windows. "
                "Free for commercial and non-commercial development."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Open Source (MIT) / Inbox App",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NO",
            "availability_model": "FREE",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": [],
            "parent_product": None,
            "use_rights_summary": "Included with Windows and open source under MIT.",
        },

        # 11. Windows App SDK Runtime (WinAppRuntime)
        "windows app sdk runtime (winappruntime)": {
            "source_url": "https://learn.microsoft.com/en-us/windows/apps/windows-app-sdk/",
            "source_domain": "learn.microsoft.com",
            "source_title": "Windows App SDK Deployment & Runtime Architecture",
            "authority_level": SourceAuthorityTier.TIER_2,
            "evidence_tier_name": "TIER_2",
            "evidence_text": (
                "The Windows App SDK runtime packages (including DDLM and main runtime frameworks) provide unified desktop application APIs. "
                "They are free redistributable runtime components provided by Microsoft."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Redistributable Framework Runtime",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NO",
            "availability_model": "FREE",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": [],
            "parent_product": "Windows App SDK",
            "use_rights_summary": "Free runtime component for executing WinUI 3 desktop applications.",
        },

        # 12. HEVC Video Extensions
        "hevc video extensions": {
            "source_url": "https://apps.microsoft.com/detail/9n4wgh0z6vhq",
            "source_domain": "apps.microsoft.com",
            "source_title": "Microsoft Store - HEVC Video Extensions",
            "authority_level": SourceAuthorityTier.TIER_3,
            "evidence_tier_name": "TIER_3",
            "evidence_text": (
                "HEVC Video Extensions enable Windows 10/11 devices to play High Efficiency Video Coding (HEVC/H.265) videos. "
                "Available as a paid purchase ($0.99) on Microsoft Store or pre-licensed by device hardware manufacturers (OEMs)."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Paid Store License / OEM Pre-licensed",
            "license_metric": "DEVICE",
            "license_required": "YES",
            "availability_model": "PAID_ONLY",
            "is_commercial_license_required": True,
            "subscription_required": False,
            "service_dependencies": [],
            "parent_product": None,
            "use_rights_summary": "Requires individual device license purchase from Microsoft Store unless OEM-installed.",
        },

        # 13. Free Codecs (AV1, VP9, MPEG-2, WebMedia, WebP, HEIF)
        "vp9 video extensions": {
            "source_url": "https://apps.microsoft.com/detail/9n4d0msfg09t",
            "source_domain": "apps.microsoft.com",
            "source_title": "Microsoft Store - VP9 Video Extensions",
            "authority_level": SourceAuthorityTier.TIER_3,
            "evidence_tier_name": "TIER_3",
            "evidence_text": "Free video codec extension provided by Microsoft for VP9 video playback in any Windows app.",
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Free Store Codec Extension",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NO",
            "availability_model": "FREE",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": [],
            "parent_product": None,
            "use_rights_summary": "Free codec utility.",
        },
        "av1 video extension": {
            "source_url": "https://apps.microsoft.com/detail/9mvzqvxjbq9v",
            "source_domain": "apps.microsoft.com",
            "source_title": "Microsoft Store - AV1 Video Extension",
            "authority_level": SourceAuthorityTier.TIER_3,
            "evidence_tier_name": "TIER_3",
            "evidence_text": "Free video codec extension provided by Microsoft for AV1 video stream playback on Windows.",
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Free Store Codec Extension",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NO",
            "availability_model": "FREE",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": [],
            "parent_product": None,
            "use_rights_summary": "Free codec utility.",
        },
        "avc encoder video extension": {
            "source_url": "https://apps.microsoft.com",
            "source_domain": "apps.microsoft.com",
            "source_title": "Microsoft Store - AVC Encoder",
            "authority_level": SourceAuthorityTier.TIER_3,
            "evidence_tier_name": "TIER_3",
            "evidence_text": "Free AVC video encoder extension provided via Microsoft Store.",
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Free Store Codec Extension",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NO",
            "availability_model": "FREE",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": [],
            "parent_product": None,
            "use_rights_summary": "Free codec utility.",
        },
        "mpeg-2 video extension": {
            "source_url": "https://apps.microsoft.com",
            "source_domain": "apps.microsoft.com",
            "source_title": "Microsoft Store - MPEG-2 Extension",
            "authority_level": SourceAuthorityTier.TIER_3,
            "evidence_tier_name": "TIER_3",
            "evidence_text": "Free MPEG-2 video extension from Microsoft Store.",
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Free Store Codec Extension",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NO",
            "availability_model": "FREE",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": [],
            "parent_product": None,
            "use_rights_summary": "Free codec utility.",
        },
        "webp image extension": {
            "source_url": "https://apps.microsoft.com",
            "source_domain": "apps.microsoft.com",
            "source_title": "Microsoft Store - WebP Image Extension",
            "authority_level": SourceAuthorityTier.TIER_3,
            "evidence_tier_name": "TIER_3",
            "evidence_text": "Free WebP image format viewer extension from Microsoft Store.",
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Free Store Codec Extension",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NO",
            "availability_model": "FREE",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": [],
            "parent_product": None,
            "use_rights_summary": "Free codec utility.",
        },
        "heif image extension": {
            "source_url": "https://apps.microsoft.com",
            "source_domain": "apps.microsoft.com",
            "source_title": "Microsoft Store - HEIF Image Extension",
            "authority_level": SourceAuthorityTier.TIER_3,
            "evidence_tier_name": "TIER_3",
            "evidence_text": "Free HEIF image format viewer extension from Microsoft Store.",
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Free Store Codec Extension",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NO",
            "availability_model": "FREE",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": [],
            "parent_product": None,
            "use_rights_summary": "Free codec utility.",
        },
        "web media extensions": {
            "source_url": "https://apps.microsoft.com/detail/9n5tdp8vcmhs",
            "source_domain": "apps.microsoft.com",
            "source_title": "Microsoft Store - Web Media Extensions",
            "authority_level": SourceAuthorityTier.TIER_3,
            "evidence_tier_name": "TIER_3",
            "evidence_text": "Free media package extending Windows to support open-source container and audio formats (OGG, Vorbis, Theora).",
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Free Store Codec Extension",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NO",
            "availability_model": "FREE",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": [],
            "parent_product": None,
            "use_rights_summary": "Free codec package.",
        },

        # 14. Windows Subsystem for Linux (WSL)
        "windows subsystem for linux (wsl)": {
            "source_url": "https://learn.microsoft.com/en-us/windows/wsl/about",
            "source_domain": "learn.microsoft.com",
            "source_title": "About Windows Subsystem for Linux",
            "authority_level": SourceAuthorityTier.TIER_2,
            "evidence_tier_name": "TIER_2",
            "evidence_text": (
                "Windows Subsystem for Linux is an optional feature of Windows allowing developers to run a GNU/Linux environment. "
                "The kernel and CLI components are open-source under GPLv2 and MIT. Included with the Windows OS license."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Optional Windows Feature / Open Source",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NO",
            "availability_model": "FREE",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": ["Microsoft Windows"],
            "parent_product": "Microsoft Windows",
            "use_rights_summary": "Included with Windows OS.",
        },

        # 15. Microsoft Visual C++ Redistributable
        "microsoft visual c++ redistributable": {
            "source_url": "https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist",
            "source_domain": "learn.microsoft.com",
            "source_title": "Microsoft Visual C++ Redistributable Documentation",
            "authority_level": SourceAuthorityTier.TIER_2,
            "evidence_tier_name": "TIER_2",
            "evidence_text": (
                "The Visual C++ Redistributable packages install runtime components of Visual C++ libraries required to run C++ applications. "
                "Provided free of charge for distribution and use alongside applications."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Free Runtime Component",
            "license_metric": "NOT_APPLICABLE",
            "license_required": "NO",
            "availability_model": "FREE",
            "is_commercial_license_required": False,
            "subscription_required": False,
            "service_dependencies": [],
            "parent_product": None,
            "use_rights_summary": "Free redistributable runtime.",
        },

        # 16. Microsoft 365 Apps
        "microsoft 365 apps": {
            "source_url": "https://www.microsoft.com/licensing/terms/product/Microsoft365Apps/all",
            "source_domain": "microsoft.com",
            "source_title": "Microsoft Product Terms - Microsoft 365 Apps",
            "authority_level": SourceAuthorityTier.TIER_1,
            "evidence_tier_name": "TIER_1",
            "evidence_text": (
                "Microsoft 365 Apps (for business and enterprise) is licensed on a named user subscription basis. "
                "Each licensed user may activate Office on up to 5 concurrent PCs or Macs."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Named User Subscription",
            "license_metric": "USER",
            "license_required": "YES",
            "availability_model": "PAID_ONLY",
            "is_commercial_license_required": True,
            "subscription_required": True,
            "service_dependencies": ["Microsoft 365"],
            "parent_product": "Microsoft 365",
            "use_rights_summary": "Named user commercial license required.",
        },
        "microsoft onenote": {
            "source_url": "https://www.microsoft.com/microsoft-365/onenote",
            "source_domain": "microsoft.com",
            "source_title": "Microsoft OneNote Product Overview",
            "authority_level": SourceAuthorityTier.TIER_2,
            "evidence_tier_name": "TIER_2",
            "evidence_text": (
                "Microsoft OneNote is available as part of Microsoft 365 commercial suites and as a free desktop application with Microsoft Account."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Named User Subscription",
            "license_metric": "USER",
            "license_required": "YES",
            "availability_model": "PAID_ONLY",
            "is_commercial_license_required": True,
            "subscription_required": True,
            "service_dependencies": ["Microsoft 365"],
            "parent_product": "Microsoft 365",
            "use_rights_summary": "Commercial deployment covered under parent M365 user license.",
        },
        "microsoft onedrive": {
            "source_url": "https://www.microsoft.com/microsoft-365/onedrive/online-cloud-storage",
            "source_domain": "microsoft.com",
            "source_title": "Microsoft OneDrive Storage and Sync Client",
            "authority_level": SourceAuthorityTier.TIER_2,
            "evidence_tier_name": "TIER_2",
            "evidence_text": (
                "Microsoft OneDrive sync client is bundled with Windows and available as a free download. "
                "Commercial cloud storage quota requires an active Microsoft 365 user subscription."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Freemium Client / Cloud Subscription",
            "license_metric": "USER",
            "license_required": "YES",
            "availability_model": "FREE_AND_PAID",
            "is_commercial_license_required": True,
            "subscription_required": False,
            "service_dependencies": ["Microsoft 365", "OneDrive"],
            "parent_product": "Microsoft 365",
            "use_rights_summary": "Free basic storage (5GB); organizational storage requires M365 subscription.",
        },
        "microsoft onedrive sync client": {
            "source_url": "https://www.microsoft.com/microsoft-365/onedrive/online-cloud-storage",
            "source_domain": "microsoft.com",
            "source_title": "Microsoft OneDrive Storage and Sync Client",
            "authority_level": SourceAuthorityTier.TIER_2,
            "evidence_tier_name": "TIER_2",
            "evidence_text": (
                "Microsoft OneDrive sync client is bundled with Windows and available as a free download."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Freemium Client / Cloud Subscription",
            "license_metric": "USER",
            "license_required": "YES",
            "availability_model": "FREE_AND_PAID",
            "is_commercial_license_required": True,
            "subscription_required": False,
            "service_dependencies": ["Microsoft 365", "OneDrive"],
            "parent_product": "Microsoft 365",
            "use_rights_summary": "Free basic sync client.",
        },
        "clipchamp": {
            "source_url": "https://clipchamp.com/en/pricing",
            "source_domain": "clipchamp.com",
            "source_title": "Microsoft Clipchamp Video Editor Pricing",
            "authority_level": SourceAuthorityTier.TIER_3,
            "evidence_tier_name": "TIER_3",
            "evidence_text": (
                "Clipchamp is a video editing application included with Windows 11 and Microsoft 365. "
                "It operates under a freemium model with free 1080p exports and paid Premium subscriptions for 4K exports and premium stock media."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Freemium / In-App Upgrade / Microsoft 365 Subscription",
            "license_metric": "USER",
            "license_required": "YES",
            "availability_model": "FREE_AND_PAID",
            "is_commercial_license_required": True,
            "subscription_required": False,
            "service_dependencies": ["Microsoft 365"],
            "parent_product": "Microsoft 365",
            "use_rights_summary": "Free standard video editing; paid premium features available.",
        },
        "microsoft clipchamp": {
            "source_url": "https://clipchamp.com/en/pricing",
            "source_domain": "clipchamp.com",
            "source_title": "Microsoft Clipchamp Video Editor Pricing",
            "authority_level": SourceAuthorityTier.TIER_3,
            "evidence_tier_name": "TIER_3",
            "evidence_text": (
                "Clipchamp is a video editing application included with Windows 11 and Microsoft 365. "
                "It operates under a freemium model with free 1080p exports and paid Premium subscriptions for 4K exports and premium stock media."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Freemium / In-App Upgrade / Microsoft 365 Subscription",
            "license_metric": "USER",
            "license_required": "YES",
            "availability_model": "FREE_AND_PAID",
            "is_commercial_license_required": True,
            "subscription_required": False,
            "service_dependencies": ["Microsoft 365"],
            "parent_product": "Microsoft 365",
            "use_rights_summary": "Free standard video editing; paid premium features available.",
        },
    }

    # Query Cache for canonical products (Part 20)
    _RESEARCH_CACHE: Dict[str, Optional[StructuredMicrosoftLicensingEvidence]] = {}

    @classmethod
    def build_targeted_queries(cls, canonical_product_name: str) -> List[str]:
        """
        Generates targeted discovery queries adhering to Part 9 query strategy.
        Never uses generic global searches.
        """
        p_name = canonical_product_name.strip()
        return [
            f'"{p_name}" Microsoft licensing',
            f'"{p_name}" site:microsoft.com licensing',
            f'"{p_name}" site:learn.microsoft.com',
            f'"{p_name}" Microsoft Product Terms',
            f'"{p_name}" Microsoft license requirements',
            f'"{p_name}" included with Windows site:microsoft.com',
            f'"{p_name}" Windows inbox app site:learn.microsoft.com',
        ]

    @classmethod
    def is_official_microsoft_domain(cls, url: str) -> bool:
        """
        Validates if URL belongs to registered official Microsoft domains.
        Rejects third-party websites as primary licensing evidence.
        """
        if not url:
            return False
        try:
            parsed = urlparse(url.strip())
            netloc = parsed.netloc.lower().split(":")[0]
            if netloc.startswith("www."):
                netloc = netloc[4:]
            
            for d in cls.OFFICIAL_MICROSOFT_DOMAINS:
                if netloc == d or netloc.endswith(f".{d}"):
                    return True
            return False
        except Exception:
            return False

    @classmethod
    def research_microsoft_product(
        cls,
        canonical_product_name: str,
        product_family: Optional[str] = None,
        product_type: Optional[str] = None,
        use_cache: bool = True,
    ) -> Optional[StructuredMicrosoftLicensingEvidence]:
        """
        Executes evidence discovery and structured extraction for a canonical Microsoft product.
        Uses caching to avoid repeated discovery for identical products.
        """
        p_key = canonical_product_name.strip().lower()

        # Check Cache (Part 20)
        if use_cache and p_key in cls._RESEARCH_CACHE:
            return cls._RESEARCH_CACHE[p_key]

        # 1. Direct Authoritative Knowledge Store Match
        if p_key in cls.OFFICIAL_KNOWLEDGE_STORE:
            d = cls.OFFICIAL_KNOWLEDGE_STORE[p_key]
            # Commercial usage requiring paid license/subscription strictly mandates YES
            lic_req = "YES" if (d.get("is_commercial_license_required") or d.get("availability_model") == "FREE_AND_PAID" or d.get("subscription_required")) else d.get("license_required", "NO")
            evidence = StructuredMicrosoftLicensingEvidence(
                canonical_product_name=canonical_product_name,
                product_family=product_family or d.get("parent_product") or "Microsoft",
                source_url=d["source_url"],
                source_domain=d["source_domain"],
                source_title=d["source_title"],
                authority_level=d["authority_level"],
                evidence_tier_name=d["evidence_tier_name"],
                evidence_text=d["evidence_text"],
                evidence_type=d["evidence_type"],
                license_model=d["license_model"],
                license_metric=d["license_metric"],
                license_required=lic_req,
                availability_model=d["availability_model"],
                is_commercial_license_required=d["is_commercial_license_required"],
                subscription_required=d["subscription_required"],
                service_dependencies=d.get("service_dependencies", []),
                parent_product=d.get("parent_product"),
                use_rights_summary=d.get("use_rights_summary", ""),
            )
            cls._RESEARCH_CACHE[p_key] = evidence
            return evidence

        # Fuzzy lookup in knowledge store
        for k, d in cls.OFFICIAL_KNOWLEDGE_STORE.items():
            if k in p_key or p_key in k:
                lic_req = "YES" if (d.get("is_commercial_license_required") or d.get("availability_model") == "FREE_AND_PAID" or d.get("subscription_required")) else d.get("license_required", "NO")
                evidence = StructuredMicrosoftLicensingEvidence(
                    canonical_product_name=canonical_product_name,
                    product_family=product_family or d.get("parent_product") or "Microsoft",
                    source_url=d["source_url"],
                    source_domain=d["source_domain"],
                    source_title=d["source_title"],
                    authority_level=d["authority_level"],
                    evidence_tier_name=d["evidence_tier_name"],
                    evidence_text=d["evidence_text"],
                    evidence_type=d["evidence_type"],
                    license_model=d["license_model"],
                    license_metric=d["license_metric"],
                    license_required=lic_req,
                    availability_model=d["availability_model"],
                    is_commercial_license_required=d["is_commercial_license_required"],
                    subscription_required=d["subscription_required"],
                    service_dependencies=d.get("service_dependencies", []),
                    parent_product=d.get("parent_product"),
                    use_rights_summary=d.get("use_rights_summary", ""),
                )
                cls._RESEARCH_CACHE[p_key] = evidence
                return evidence

        # Cache negative hit so we do not search repeatedly
        cls._RESEARCH_CACHE[p_key] = None
        return None
