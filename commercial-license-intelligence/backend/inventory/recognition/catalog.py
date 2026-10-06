"""
Canonical Application Recognition Catalog & Deterministic Rules Engine (Step 19 Hardening).
Provides authoritative catalog definitions, canonical normalization, deterministic open-source,
OS-bundled, commercial component, and commercial licensing rules with discrete metrics and decoupled classifications.
"""

import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

from backend.models.enums import (
    FinalLicenseStatus,
    ResolutionMethod,
    ReviewReason,
    ExtractionConfidence,
    LicenseClassificationValue,
    AvailabilityModel,
    LicenseRequirement,
    LicenseMetricValue,
    SourceAuthorityTier,
    EvidenceType,
)


@dataclass
class CatalogRecognitionEntry:
    canonical_name: str
    canonical_vendor: str
    classification: str
    license_required: FinalLicenseStatus
    licensing_model: str
    licensing_metric: str
    commercial_use_allowed: bool
    confidence: ExtractionConfidence
    method: ResolutionMethod
    terms_summary: str
    primary_url: str
    evidence_quote: str
    availability_model: str = "UNKNOWN"
    license_requirement: str = "UNKNOWN"
    parent_product: Optional[str] = None
    is_os_bundled: bool = False
    is_oem: bool = False
    is_open_source: bool = False
    is_commercial: bool = False
    is_component: bool = False
    source_type: str = "EULA"
    authority_tier: SourceAuthorityTier = SourceAuthorityTier.TIER_1
    evidence_type: EvidenceType = EvidenceType.DIRECT_STATEMENT
    aliases: List[str] = None


# Generic corporate noise suffixes to strip safely from publisher strings
CORP_SUFFIX_PATTERN = re.compile(
    r"\b(?:Corporation|Corp\.?|Incorporated|Inc\.?|Limited|Ltd\.?|LLC|GmbH|Pty\s+Ltd|S\.r\.l\.|S\.A\.|Systems|Technologies|Company|Co\.?)\b",
    re.IGNORECASE
)

# Known Vendor Canonical Normalizations
EXACT_VENDOR_CANONICAL_MAP: Dict[str, str] = {
    "microsoft": "Microsoft",
    "microsoft corporation": "Microsoft",
    "microsoft corp.": "Microsoft",
    "microsoft windows": "Microsoft Windows",
    "adobe": "Adobe",
    "adobe inc.": "Adobe",
    "adobe systems": "Adobe",
    "adobe systems incorporated": "Adobe",
    "google": "Google",
    "google llc": "Google",
    "google inc.": "Google",
    "docker": "Docker",
    "docker inc.": "Docker",
    "oracle": "Oracle",
    "oracle corporation": "Oracle",
    "autodesk": "Autodesk",
    "autodesk inc.": "Autodesk",
    "jetbrains": "JetBrains",
    "jetbrains s.r.o.": "JetBrains",
    "the git development community": "Git Community",
    "python software foundation": "Python Software Foundation",
    "node.js foundation": "OpenJS Foundation",
    "openjs foundation": "OpenJS Foundation",
    "php group": "PHP Group",
    "brave software inc": "Brave Software",
    "brave software": "Brave Software",
    "igor pavlov": "Igor Pavlov",
    "don ho": "Don Ho",
    "win.rar gmbh": "win.rar GmbH",
    "lenovo group ltd.": "Lenovo",
    "lenovo": "Lenovo",
    "intel(r) corporation": "Intel",
    "intel corporation": "Intel",
    "intel": "Intel",
    "realtek": "Realtek",
    "osquery": "osquery",
    "silverleaf solutions": "SilverLeaf Solutions",
    "riot games, inc.": "Riot Games, Inc.",
    "riot games": "Riot Games, Inc.",
    "kitware, inc.": "Kitware, Inc.",
    "kitware": "Kitware, Inc.",
    "amazon web services, inc.": "Amazon Web Services, Inc.",
    "amazon web services": "Amazon Web Services, Inc.",
    "aws": "Amazon Web Services, Inc.",
    "advanced micro devices, inc. (amd)": "Advanced Micro Devices, Inc. (AMD)",
    "advanced micro devices, inc.": "Advanced Micro Devices, Inc. (AMD)",
    "advanced micro devices": "Advanced Micro Devices, Inc. (AMD)",
    "amd": "Advanced Micro Devices, Inc. (AMD)",
    "nvidia corporation": "NVIDIA Corporation",
    "nvidia": "NVIDIA Corporation",
    "warp, inc.": "Warp, Inc.",
    "warp": "Warp, Inc.",
    "gen digital inc. / avast": "Gen Digital Inc. / Avast",
    "avast": "Gen Digital Inc. / Avast",
    "mcafee, llc": "McAfee, LLC",
    "mcafee": "McAfee, LLC",
    "tlauncher": "TLauncher",
    "wondershare technology co., ltd.": "Wondershare Technology Co., Ltd.",
    "wondershare": "Wondershare Technology Co., Ltd.",
    "telegram messenger llp": "Telegram Messenger LLP",
    "telegram": "Telegram Messenger LLP",
    "kankaria": "Kankaria",
    "57495kankaria": "Kankaria",
    "meta platforms, inc. / open source community": "Meta Platforms, Inc. / Open Source Community",
    "meta platforms, inc.": "Meta Platforms, Inc.",
    "meta platforms": "Meta Platforms, Inc.",
    "meta": "Meta Platforms, Inc.",
    "epic games, inc.": "Epic Games, Inc.",
    "epic games": "Epic Games, Inc.",
    "apple inc.": "Apple Inc.",
    "apple": "Apple Inc.",
}


def sanitize_vendor_name(raw_vendor: Optional[str]) -> Optional[str]:
    """
    Sanitizes vendor string cleanly.
    CRITICAL RULE: Never classify 'Random Corporation' as 'Microsoft'.
    """
    if not raw_vendor:
        return None
    
    cleaned = " ".join(raw_vendor.strip().split())
    lower = cleaned.lower()
    
    # Direct match in canonical map
    if lower in EXACT_VENDOR_CANONICAL_MAP:
        return EXACT_VENDOR_CANONICAL_MAP[lower]
    
    # If URL format (e.g. https://go.dev), normalize to clean domain/name
    if "go.dev" in lower or "golang.org" in lower:
        return "Google / Go Authors"
    
    # Strip trailing corporate noise for clean display while preserving distinctive vendor name
    stripped = CORP_SUFFIX_PATTERN.sub("", cleaned).strip(" ,.-")
    stripped = " ".join(stripped.split())
    
    return stripped if stripped else cleaned


# -------------------------------------------------------------------------------------------------
# RECOGNITION CATALOG RULES (Step 19 Decoupled Taxonomy & Granular Metrics)
# -------------------------------------------------------------------------------------------------

RECOGNITION_RULES: List[CatalogRecognitionEntry] = [
    # Added via Tier 4 Feedback Loop
    CatalogRecognitionEntry(
        canonical_name="Enterprise Internal Tool Suite",
        canonical_vendor="Acme Corporation",
        classification="FREEWARE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Freeware Application",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Human verified via Tier 4 feedback loop by auditor_jane.",
        primary_url="https://intranet.acme.corp/tools",
        evidence_quote="Internal utility approved for corporate workstation use.",
        is_open_source=False,
        source_type="AUDITOR_RESOLUTION",
        aliases=[
            "custominhousetool_406c43",
            "enterprise internal tool suite"
        ]
    ),
    # Added via Tier 4 Feedback Loop
    CatalogRecognitionEntry(
        canonical_name="Enterprise Internal Tool Suite",
        canonical_vendor="Acme Corporation",
        classification="FREEWARE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Freeware Application",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Human verified via Tier 4 feedback loop by auditor_jane.",
        primary_url="https://intranet.acme.corp/tools",
        evidence_quote="Internal utility approved for corporate workstation use.",
        is_open_source=False,
        source_type="AUDITOR_RESOLUTION",
        aliases=[
            "custominhousetool_270b9d",
            "enterprise internal tool suite"
        ]
    ),
    # Added via Tier 4 Feedback Loop
    CatalogRecognitionEntry(
        canonical_name="API Sample Tool",
        canonical_vendor="API Sample Vendor Inc.",
        classification="FREEWARE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Freeware Application",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Human verified via Tier 4 feedback loop by qa_auditor.",
        primary_url="https://example.com/tool-terms",
        evidence_quote="Freeware utility for enterprise endpoints.",
        is_open_source=False,
        source_type="AUDITOR_RESOLUTION",
        aliases=[
            "apisampleunresolvedtool",
            "api sample tool"
        ]
    ),
    # Added via Tier 4 Feedback Loop
    CatalogRecognitionEntry(
        canonical_name="TestDynamicProduct_19f4ea",
        canonical_vendor="Dynamic Vendor LLC",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Commercial Application",
        licensing_metric="USER",
        commercial_use_allowed=False,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Human verified via Tier 4 feedback loop by lead_auditor.",
        primary_url="https://vendor.com/pricing",
        evidence_quote="Standard commercial licensing applies.",
        is_open_source=False,
        source_type="AUDITOR_RESOLUTION",
        aliases=[
            "testdynamicproduct_19f4ea"
        ]
    ),
    CatalogRecognitionEntry(
        canonical_name="SQL Server Management Studio",
        canonical_vendor="Microsoft",
        classification="FREEWARE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Freeware Application",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="SQL Server Management Studio (SSMS) is a free integrated environment for managing SQL Server infrastructure.",
        primary_url="https://learn.microsoft.com/en-us/sql/ssms/download-sql-server-management-studio-ssms",
        evidence_quote="SQL Server Management Studio (SSMS) is a free, stand-alone utility to configure, monitor, and administer instances of SQL Server.",
        is_open_source=False,
        source_type="TERMS",
        aliases=[
            "sql server management studio",
            "ssms",
            "microsoft sql server management studio",
            "sql server management studio 21",
            "sql server management studio 22",
        ]
    ),
    CatalogRecognitionEntry(
        canonical_name="Power BI Desktop",
        canonical_vendor="Microsoft",
        classification="FREE_AND_PAID",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Subscription / Free Client",
        licensing_metric="USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Power BI Desktop is available free for personal report authoring; organizational sharing and cloud collaboration require a paid Power BI Pro or Microsoft 365 subscription.",
        primary_url="https://powerbi.microsoft.com/en-us/desktop/",
        evidence_quote="Power BI Desktop is a free authoring client for building reports. Sharing reports, collaboration in workspaces, and enterprise publishing requires an eligible Microsoft 365 or Power BI Pro user license.",
        is_open_source=False,
        source_type="TERMS",
        aliases=[
            "power bi desktop",
            "powerbi desktop",
            "microsoft power bi desktop",
        ]
    ),
    # 0. High-Priority Enterprise & Productivity Applications
    CatalogRecognitionEntry(
        canonical_name="Adobe Acrobat Reader",
        canonical_vendor="Adobe",
        classification="FREEWARE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Freeware PDF Reader",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Adobe Acrobat Reader is a free PDF viewer for desktop and mobile devices.",
        primary_url="https://www.adobe.com/acrobat/pdf-reader.html",
        evidence_quote="Adobe Acrobat Reader software is the free, trusted global standard for viewing, printing, signing, and annotating PDFs.",
        is_open_source=False,
        source_type="TERMS",
        aliases=[
            "adobe acrobat reader dc",
            "adobe acrobat reader",
            "acrobat reader dc",
            "acrobat reader",
            "adobe reader",
            "adobe acrobat reader dc (64-bit)",
            "adobeacrobatreadercoreapp",
        ]
    ),
    CatalogRecognitionEntry(
        canonical_name="Adobe Acrobat",
        canonical_vendor="Adobe",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Named User Subscription / Perpetual",
        licensing_metric="USER",
        commercial_use_allowed=False,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Adobe Acrobat Pro / Standard / DC is commercial PDF editing software licensed per named user subscription.",
        primary_url="https://www.adobe.com/products/acrobatpro/pricing.html",
        evidence_quote="Adobe Acrobat Pro subscription plans for individuals and teams. Paid commercial license required.",
        is_open_source=False,
        source_type="TERMS",
        aliases=[
            "adobe acrobat dc",
            "adobe acrobat pro",
            "adobe acrobat pro dc",
            "adobe acrobat standard",
            "adobe acrobat",
            "acrobat dc",
            "acrobat pro",
            "adobeacrobatdccoreapp",
        ]
    ),
    CatalogRecognitionEntry(
        canonical_name="Google Docs",
        canonical_vendor="Google",
        classification="FREE_AND_PAID",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Freemium Cloud Productivity Suite / Google Workspace Subscription",
        licensing_metric="USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Google Docs provides free personal word processing and is licensed under Google Workspace commercial subscriptions for enterprise business use.",
        primary_url="https://workspace.google.com/products/docs/",
        evidence_quote="Google Docs: Online Document Editor | Google Workspace. Create and collaborate on online documents in real-time and from any device.",
        is_open_source=False,
        source_type="TERMS",
        aliases=["google docs", "docs"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Google Sheets",
        canonical_vendor="Google",
        classification="FREE_AND_PAID",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Freemium Cloud Spreadsheet / Google Workspace Subscription",
        licensing_metric="USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Google Sheets provides free personal spreadsheets and is licensed under Google Workspace commercial subscriptions for business use.",
        primary_url="https://workspace.google.com/products/sheets/",
        evidence_quote="Google Sheets: Online Spreadsheet Editor | Google Workspace. Create and collaborate on online spreadsheets in real-time.",
        is_open_source=False,
        source_type="TERMS",
        aliases=["google sheets", "sheets"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Google Slides",
        canonical_vendor="Google",
        classification="FREE_AND_PAID",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Freemium Cloud Presentation / Google Workspace Subscription",
        licensing_metric="USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Google Slides provides free personal presentations and is licensed under Google Workspace commercial subscriptions for business use.",
        primary_url="https://workspace.google.com/products/slides/",
        evidence_quote="Google Slides: Online Presentation Maker | Google Workspace. Create and collaborate on online presentations.",
        is_open_source=False,
        source_type="TERMS",
        aliases=["google slides", "slides"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Gmail",
        canonical_vendor="Google",
        classification="FREE_AND_PAID",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Freemium Webmail / Google Workspace Subscription",
        licensing_metric="USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Gmail is a free webmail service for personal accounts, with commercial business licensing provided under Google Workspace.",
        primary_url="https://workspace.google.com/products/gmail/",
        evidence_quote="Secure, smart, and easy-to-use business email from Google Workspace.",
        is_open_source=False,
        source_type="TERMS",
        aliases=["gmail", "google mail"]
    ),
    CatalogRecognitionEntry(
        canonical_name="YouTube",
        canonical_vendor="Google",
        classification="FREEWARE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Ad-Supported Web Media Platform / Free Client",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="YouTube is an ad-supported video sharing and streaming service with optional consumer premium subscriptions.",
        primary_url="https://www.youtube.com/t/terms",
        evidence_quote="YouTube Terms of Service: By using the Service, you agree to these terms. Enjoy the videos and music you love.",
        is_open_source=False,
        source_type="TERMS",
        aliases=["youtube", "youtube web"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Facebook",
        canonical_vendor="Meta Platforms, Inc.",
        classification="FREEWARE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Ad-Supported Social Platform / Free Client",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Facebook is a free, advertising-supported social networking platform provided by Meta Platforms, Inc.",
        primary_url="https://www.facebook.com/terms.php",
        evidence_quote="Meta Terms of Service. We agree to provide you with the Facebook Products and services, which include all Facebook features, applications, and technologies.",
        is_open_source=False,
        source_type="TERMS",
        aliases=["facebook"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Oracle Java SE",
        canonical_vendor="Oracle",
        classification="COMMERCIAL",
        availability_model="COMMERCIAL",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Oracle Java SE Universal Subscription / OTN License",
        licensing_metric="EMPLOYEE",
        commercial_use_allowed=False,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Oracle Java SE requires a paid commercial subscription (Universal Subscription or legacy per-Named User / Processor) for commercial production use.",
        primary_url="https://www.oracle.com/java/technologies/java-se-subscription.html",
        evidence_quote="Oracle Java SE Universal Subscription is a simple, low-cost monthly subscription that includes Java SE licensing and support for use on Desktops, Servers or Cloud deployments.",
        is_open_source=False,
        source_type="TERMS",
        aliases=[
            "java 8 update",
            "java auto updater",
            "java(tm) se development kit",
            "oracle java",
            "java se development kit 22",
            "java se development kit 25",
        ]
    ),
    CatalogRecognitionEntry(
        canonical_name="Oracle VirtualBox",
        canonical_vendor="Oracle",
        classification="OPEN_SOURCE",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="GPL-2.0 (Base) / PUEL (Extension Pack Commercial License)",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="VirtualBox base software is open source under GNU GPL v2. The Oracle VM VirtualBox Extension Pack is licensed under the PUEL and requires commercial licensing for enterprise business use.",
        primary_url="https://www.virtualbox.org/wiki/Licensing_FAQ",
        evidence_quote="The VirtualBox base package is released under the GNU General Public License (GPL) version 2. The VirtualBox Extension Pack is available under the VirtualBox Personal Use and Evaluation License (PUEL).",
        is_open_source=True,
        source_type="TERMS",
        aliases=["oracle virtualbox", "virtualbox", "oracle vm virtualbox"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Android Studio",
        canonical_vendor="Google",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Apache License 2.0 / Free Developer Tool",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Android Studio is the official IDE for Android development, based on IntelliJ IDEA Community and distributed free of charge.",
        primary_url="https://developer.android.com/studio/terms",
        evidence_quote="Android Studio is available free of charge for commercial and personal app development under open source and developer terms.",
        is_open_source=True,
        source_type="TERMS",
        aliases=["android studio"]
    ),
    CatalogRecognitionEntry(
        canonical_name="OBS Studio",
        canonical_vendor="OBS Project",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="GNU General Public License v2.0 (GPL-2.0)",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="OBS Studio is free and open-source software for video recording and live streaming under the GPL-2.0 license.",
        primary_url="https://github.com/obsproject/obs-studio/blob/master/COPYING",
        evidence_quote="OBS Studio is licensed under the GNU General Public License v2.0. Free for commercial and non-commercial use.",
        is_open_source=True,
        source_type="TERMS",
        aliases=["obs studio"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Ollama",
        canonical_vendor="Ollama",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="MIT License",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Ollama is an open-source local LLM runner distributed under the permissive MIT License.",
        primary_url="https://github.com/ollama/ollama/blob/main/LICENSE",
        evidence_quote="Ollama is released under the MIT License, allowing commercial use, modification, and distribution without restriction.",
        is_open_source=True,
        source_type="TERMS",
        aliases=["ollama", "ollama version"]
    ),
    CatalogRecognitionEntry(
        canonical_name="FileZilla",
        canonical_vendor="Tim Kosse",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="GNU General Public License v2.0 (GPL-2.0)",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="FileZilla Client is free and open source cross-platform FTP, FTPS and SFTP client under GNU GPL.",
        primary_url="https://filezilla-project.org/license.php",
        evidence_quote="FileZilla is free open source software distributed under the terms of the GNU General Public License.",
        is_open_source=True,
        source_type="TERMS",
        aliases=["filezilla", "filezilla client", "timkosse.filezilla.client", "filezilla.filezilla"]
    ),
    CatalogRecognitionEntry(
        canonical_name="calibre",
        canonical_vendor="Kovid Goyal",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="GNU General Public License v3.0 (GPL-3.0)",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="calibre is a powerful and easy to use e-book manager licensed under the GNU General Public License v3.",
        primary_url="https://calibre-ebook.com/about#license",
        evidence_quote="calibre is open source software, licensed under the GNU General Public License v3.",
        is_open_source=True,
        source_type="TERMS",
        aliases=["calibre"]
    ),
    CatalogRecognitionEntry(
        canonical_name="OpenSSL",
        canonical_vendor="OpenSSL Software Foundation",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Apache License 2.0",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="OpenSSL is a robust, commercial-grade, full-featured Open Source Toolkit for TLS and SSL protocols.",
        primary_url="https://www.openssl.org/source/license.html",
        evidence_quote="OpenSSL 3.0 and newer versions are licensed under the Apache License 2.0.",
        is_open_source=True,
        source_type="TERMS",
        aliases=["openssl", "openssl light"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Opera Browser",
        canonical_vendor="Opera Software",
        classification="FREEWARE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Freeware Web Browser",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Opera and Opera GX are proprietary freeware web browsers distributed free of charge.",
        primary_url="https://www.opera.com/terms",
        evidence_quote="Opera web browsers are available free of charge for personal and commercial browsing.",
        is_open_source=False,
        source_type="TERMS",
        aliases=["opera", "opera gx", "opera stable", "opera gx stable", "opera.opera", "opera.operagx"]
    ),
    CatalogRecognitionEntry(
        canonical_name="ManageEngine Endpoint Central Agent",
        canonical_vendor="Zoho Corporation",
        classification="COMMERCIAL",
        availability_model="COMMERCIAL",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Commercial Endpoint Management Subscription",
        licensing_metric="DEVICE",
        commercial_use_allowed=False,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="ManageEngine Endpoint Central (formerly Desktop Central / UEMS) is an enterprise unified endpoint management solution licensed per managed device.",
        primary_url="https://www.manageengine.com/products/desktop-central/pricing.html",
        evidence_quote="ManageEngine Endpoint Central enterprise editions are licensed based on the number of managed computers and mobile devices.",
        is_open_source=False,
        source_type="TERMS",
        aliases=["manageengine uems", "manageengine uems - agent", "manageengine endpoint central"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Trellix Endpoint Security",
        canonical_vendor="Trellix",
        classification="COMMERCIAL",
        availability_model="COMMERCIAL",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Commercial Endpoint Security Subscription",
        licensing_metric="DEVICE",
        commercial_use_allowed=False,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Trellix Endpoint Security (formerly McAfee Enterprise) is a suite of endpoint protection, EDR, and DLP products licensed per protected node.",
        primary_url="https://www.trellix.com/en-us/about/legal.html",
        evidence_quote="Trellix enterprise software licenses and subscriptions are governed by the Trellix End User License Agreement and licensed per node/device.",
        is_open_source=False,
        source_type="TERMS",
        aliases=[
            "trellix data loss prevention",
            "trellix edr",
            "trellix endpoint security",
            "trellix file and removable media",
            "trellix reporter",
            "trellixatp",
        ]
    ),
    # 1. Open Source Development Tools & Runtimes (Metric: NOT_APPLICABLE, Classification: OPEN_SOURCE)
    CatalogRecognitionEntry(
        canonical_name=".NET SDK",
        canonical_vendor="Microsoft",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Open Source Permissive (MIT)",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary=".NET SDK and runtime are licensed under the open-source MIT license and free for commercial and non-commercial development.",
        primary_url="https://github.com/dotnet/core/blob/main/LICENSE.TXT",
        evidence_quote=".NET is open source under the MIT License. The MIT license allows reuse within proprietary software provided all copies of the licensed software include the license terms.",
        is_open_source=True,
        source_type="TERMS",
        aliases=[
            "microsoft .net sdk",
            ".net sdk 10",
            ".net sdk 9",
            ".net sdk 8",
            ".net sdk 7",
            ".net sdk 6",
            ".net sdk",
            "microsoft .net runtime",
            ".net runtime",
            "microsoft .net core",
        ]
    ),
    CatalogRecognitionEntry(
        canonical_name="Visual Studio Code",
        canonical_vendor="Microsoft",
        classification="FREEWARE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Freeware Developer Tool",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Visual Studio Code binaries are free for commercial development under Microsoft Software License Terms; the core repository is open source under the MIT License.",
        primary_url="https://code.visualstudio.com/License",
        evidence_quote="You may install and use any number of copies of the software to develop and test your applications, including commercial applications.",
        is_open_source=False,
        source_type="TERMS",
        aliases=[
            "microsoft visual studio code",
            "microsoft visual studio code (user)",
            "visual studio code",
            "vscode",
            "microsoft.visualstudiocode",
        ]
    ),
    CatalogRecognitionEntry(
        canonical_name="Python",
        canonical_vendor="Python Software Foundation",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Open Source Permissive (PSFL)",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Python is distributed under the PSF License, an OSI-approved open-source permissive license allowing unrestricted commercial use and distribution.",
        primary_url="https://docs.python.org/3/license.html",
        evidence_quote="PSF grants licensee a nonexclusive, royalty-free license to reproduce, prepare derivative works, distribute and perform commercially.",
        is_open_source=True,
        source_type="TERMS",
        aliases=[
            "python",
            "python 3",
            "python 3.14",
            "python 3.13",
            "python 3.12",
            "python 3.11",
            "python 3.10",
            "pythonsoftwarefoundation.pythonmanager",
        ]
    ),
    CatalogRecognitionEntry(
        canonical_name="Node.js",
        canonical_vendor="OpenJS Foundation",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Open Source Permissive (MIT)",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Node.js runtime is licensed under the MIT license, free for all personal and commercial production deployments.",
        primary_url="https://github.com/nodejs/node/blob/main/LICENSE",
        evidence_quote="Node.js is available under the MIT license. Node.js also includes external libraries with permissive licenses.",
        is_open_source=True,
        source_type="TERMS",
        aliases=["node.js", "nodejs", "node"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Git",
        canonical_vendor="Git Community",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Open Source Copyleft (GPL v2)",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Git version control system is distributed under GNU General Public License v2; unrestricted for internal corporate and commercial software development.",
        primary_url="https://git-scm.com/about/free-and-open-source",
        evidence_quote="Git is free software distributed under the terms of the GNU General Public License version 2.",
        is_open_source=True,
        source_type="TERMS",
        aliases=["git", "git for windows"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Go Programming Language",
        canonical_vendor="Google / Go Authors",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Open Source Permissive (BSD-3-Clause)",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Go compiler and tools are licensed under a 3-clause BSD license and free for commercial applications.",
        primary_url="https://golang.org/LICENSE",
        evidence_quote="Redistribution and use in source and binary forms, with or without modification, are permitted provided that the conditions are met.",
        is_open_source=True,
        source_type="TERMS",
        aliases=[
            "go programming language",
            "go programming language amd64",
            "golang",
            "go",
        ]
    ),
    CatalogRecognitionEntry(
        canonical_name="PHP",
        canonical_vendor="PHP Group",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Open Source Permissive (PHP 3.01)",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="PHP is distributed under the open-source PHP License v3.01, free for commercial server and command line deployment.",
        primary_url="https://www.php.net/license/3_01.txt",
        evidence_quote="Redistribution and use in source and binary forms, with or without modification, is permitted.",
        is_open_source=True,
        source_type="TERMS",
        aliases=["php", "php 8.2", "php 8.3", "php 8.1", "php 8.0"]
    ),
    CatalogRecognitionEntry(
        canonical_name="osquery",
        canonical_vendor="Linux Foundation / osquery",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Open Source Permissive (Apache 2.0 / GPL v2)",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="osquery endpoint instrumentation framework is open source under Apache 2.0 and GPL v2.",
        primary_url="https://github.com/osquery/osquery/blob/master/LICENSE",
        evidence_quote="osquery is an open source software project licensed under Apache 2.0.",
        is_open_source=True,
        source_type="TERMS",
        aliases=["osquery"]
    ),
    CatalogRecognitionEntry(
        canonical_name="7-Zip",
        canonical_vendor="Igor Pavlov",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Open Source LGPL",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="7-Zip is open-source compression software under GNU LGPL, explicitly free for commercial companies.",
        primary_url="https://www.7-zip.org/license.txt",
        evidence_quote="You can use 7-Zip on any computer, including a computer in a commercial organization. You don't need to register or pay for 7-Zip.",
        is_open_source=True,
        source_type="TERMS",
        aliases=["7-zip", "7-zip (64-bit)", "7zip"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Notepad++",
        canonical_vendor="Don Ho",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Open Source Copyleft (GPL v3)",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Notepad++ is free software under GNU GPL, unrestricted for internal enterprise and commercial use.",
        primary_url="https://notepad-plus-plus.org/repository/licence/",
        evidence_quote="Distributed under GNU General Public License. Free for commercial and non-commercial use.",
        is_open_source=True,
        source_type="TERMS",
        aliases=["notepad++", "notepad plus plus"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Google Chrome",
        canonical_vendor="Google",
        classification="FREEWARE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Freeware Proprietary",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Google Chrome is freeware permitted for enterprise fleet deployment without subscription fees.",
        primary_url="https://www.google.com/chrome/terms/",
        evidence_quote="Google grants you a personal, worldwide, royalty-free, non-assignable and non-exclusive license to use the software.",
        source_type="TERMS",
        aliases=["google chrome", "chrome", "google.chrome", "google.chrome.canary"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Brave Browser",
        canonical_vendor="Brave Software",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Open Source (MPL 2.0)",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Brave browser is open-source under Mozilla Public License 2.0 and free for commercial and private use.",
        primary_url="https://brave.com/terms-of-use/",
        evidence_quote="Brave Browser core is open source under MPL 2.0.",
        is_open_source=True,
        source_type="TERMS",
        aliases=["brave", "brave browser", "brave software", "brave.brave", "bravesoftware.bravebrowser"]
    ),

    # 2. Free + Paid Products (Part 2 & 20: Antigravity)
    CatalogRecognitionEntry(
        canonical_name="Antigravity",
        canonical_vendor="Google",
        classification="FREE_AND_PAID",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.RESEARCH_REQUIRED,
        licensing_model="Subscription / Tiered Quota",
        licensing_metric="USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.KNOWN_PROFILE,
        terms_summary="Antigravity provides a free tier with base capability quotas and paid enterprise/professional subscription tiers for advanced bandwidth.",
        primary_url="https://deepmind.google/technologies/antigravity/licensing-terms",
        evidence_quote="Google Antigravity is available via a free tier with base capability quotas and paid enterprise or professional subscription tiers.",
        is_commercial=True,
        source_type="OFFICIAL_TERMS",
        aliases=["antigravity", "antigravity 2.10.0", "antigravity ide", "antigravity ide (user)"]
    ),

    # 3. Commercial Standalone Software & Databases (Part 17: SQL Server, Docker, WinRAR, Acrobat)
    CatalogRecognitionEntry(
        canonical_name="Microsoft SQL Server",
        canonical_vendor="Microsoft",
        classification="COMMERCIAL",
        availability_model="FREE_AND_PAID",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Per Core / Server + CAL",
        licensing_metric="CORE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.KNOWN_PROFILE,
        terms_summary="Microsoft SQL Server Standard and Enterprise require paid core-based licenses (minimum 4 cores per processor) for commercial production.",
        primary_url="https://www.microsoft.com/licensing/terms/product/SQLServer/all",
        evidence_quote="Customer must license all physical or virtual cores on the operating system environment. Minimum 4 core licenses per processor.",
        is_commercial=True,
        source_type="OFFICIAL_LICENSING_GUIDE",
        aliases=[
            "microsoft sql server 2025",
            "microsoft sql server 2022",
            "microsoft sql server 2019",
            "microsoft sql server",
            "microsoft sql server 2025 setup",
            "sql server management studio",
            "sql server management studio 22",
        ]
    ),
    CatalogRecognitionEntry(
        canonical_name="Docker Desktop",
        canonical_vendor="Docker",
        classification="COMMERCIAL",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Named User Subscription",
        licensing_metric="USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.KNOWN_PROFILE,
        terms_summary="Docker Desktop requires a paid per-user subscription (Pro, Team, or Business) for commercial use in organizations with >250 employees or >$10M annual revenue.",
        primary_url="https://www.docker.com/legal/docker-software-end-user-license-agreement/",
        evidence_quote="Docker Desktop requires a paid subscription (Pro, Team, or Business) for commercial use in organizations with >250 employees or >$10M in annual revenue.",
        is_commercial=True,
        source_type="OFFICIAL_EULA",
        aliases=["docker desktop", "docker"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Adobe Acrobat Pro",
        canonical_vendor="Adobe",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Named User Subscription",
        licensing_metric="USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.KNOWN_PROFILE,
        terms_summary="Adobe Acrobat Pro is a commercial PDF editor requiring a paid per-user subscription.",
        primary_url="https://www.adobe.com/legal/licenses-terms.html",
        evidence_quote="Acrobat Pro requires a valid paid user subscription.",
        is_commercial=True,
        source_type="OFFICIAL_TERMS",
        aliases=[
            "adobe acrobat pro",
            "adobe acrobat pro dc",
            "adobe acrobat standard",
        ]
    ),
    CatalogRecognitionEntry(
        canonical_name="WinRAR",
        canonical_vendor="win.rar GmbH",
        classification="COMMERCIAL",
        availability_model="TRIAL",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Per User / Per PC License",
        licensing_metric="DEVICE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.KNOWN_PROFILE,
        terms_summary="WinRAR is shareware. After a 40-day evaluation trial, commercial usage requires purchasing a paid license.",
        primary_url="https://www.rarlab.com/license.htm",
        evidence_quote="WinRAR is not free. After a 40 days trial period a user must either buy a license or remove it from his computer.",
        is_commercial=True,
        source_type="OFFICIAL_EULA",
        aliases=["winrar"]
    ),

    # 4. Commercial Components (Part 21: OfficePushNotificationUtility, ActionsServer, M365Companions)
    CatalogRecognitionEntry(
        canonical_name="OfficePushNotificationUtility",
        canonical_vendor="Microsoft",
        classification="COMMERCIAL_COMPONENT",
        availability_model="BUNDLED",
        license_requirement="NOT_APPLICABLE",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Component Functionality",
        licensing_metric="NOT_APPLICABLE",
        parent_product="Microsoft 365 Apps",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="OfficePushNotificationUtility is a background notification component bundled with Microsoft 365 Apps. Licensed under parent Microsoft 365 entitlement.",
        primary_url="https://learn.microsoft.com/en-us/deployoffice/overview",
        evidence_quote="Background client component included with Microsoft 365 Apps. Covered under parent Microsoft 365 entitlement and not independently licensed.",
        is_component=True,
        source_type="OFFICIAL_DOCUMENT",
        aliases=[
            "officepushnotificationutility",
            "microsoft.officepushnotificationutility",
        ]
    ),
    CatalogRecognitionEntry(
        canonical_name="Office.ActionsServer",
        canonical_vendor="Microsoft",
        classification="COMMERCIAL_COMPONENT",
        availability_model="BUNDLED",
        license_requirement="NOT_APPLICABLE",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Component Functionality",
        licensing_metric="NOT_APPLICABLE",
        parent_product="Microsoft 365 Apps",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Office.ActionsServer is a background service component included with Microsoft 365 Apps and covered under parent suite entitlement.",
        primary_url="https://learn.microsoft.com/en-us/deployoffice/overview",
        evidence_quote="Internal background actions component for Microsoft 365 Apps.",
        is_component=True,
        source_type="OFFICIAL_DOCUMENT",
        aliases=[
            "office.actionsserver",
            "microsoft.office.actionsserver",
        ]
    ),
    CatalogRecognitionEntry(
        canonical_name="Microsoft 365 Companion Apps",
        canonical_vendor="Microsoft",
        classification="COMMERCIAL_COMPONENT",
        availability_model="BUNDLED",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Subscription / Service Entitlement",
        licensing_metric="USER",
        parent_product="Microsoft 365",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Microsoft 365 Companion Apps (People, Files, Calendar) are lightweight productivity apps bundled with Microsoft 365. Full functionality may require an eligible Microsoft 365 commercial license with the required Microsoft 365 services enabled.",
        primary_url="https://learn.microsoft.com/en-us/microsoft-365-apps/overview-companion-apps",
        evidence_quote="Users must be assigned a commercial license that includes both Exchange Online and SharePoint (OneDrive) Online services to access the companion apps.",
        is_component=True,
        source_type="OFFICIAL_DOCUMENT",
        aliases=[
            "m365companions",
            "microsoft.m365companions",
            "microsoft 365 companion apps",
            "people companion",
            "files companion",
            "calendar companion",
        ]
    ),

    # 5. Windows OS Bundled Applications (Part 19: Calculator, Photos, Paint, Notepad, Camera, etc.)
    CatalogRecognitionEntry(
        canonical_name="Windows Calculator",
        canonical_vendor="Microsoft Windows",
        classification="OS_BUNDLED",
        availability_model="BUNDLED",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Operating System Bundled Feature",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Windows Calculator is a built-in operating system applet included with the Windows OS license.",
        primary_url="https://www.microsoft.com/legal/terms-of-use",
        evidence_quote="Built-in Windows operating system applet included under Microsoft Windows OS EULA.",
        is_os_bundled=True,
        source_type="OFFICIAL_TERMS",
        aliases=[
            "calculator",
            "microsoft.windowscalculator",
            "windowscalculator",
        ]
    ),
    CatalogRecognitionEntry(
        canonical_name="Windows Photos",
        canonical_vendor="Microsoft Windows",
        classification="OS_BUNDLED",
        availability_model="BUNDLED",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Operating System Bundled Feature",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Windows Photos is a built-in media viewer included with the Windows OS license.",
        primary_url="https://www.microsoft.com/legal/terms-of-use",
        evidence_quote="Standard built-in Windows media application licensed under Windows OS EULA.",
        is_os_bundled=True,
        source_type="OFFICIAL_TERMS",
        aliases=[
            "photos",
            "microsoft.windowsphotos",
            "windowsphotos",
        ]
    ),
    CatalogRecognitionEntry(
        canonical_name="Windows Notepad",
        canonical_vendor="Microsoft Windows",
        classification="OS_BUNDLED",
        availability_model="BUNDLED",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Operating System Bundled Feature",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Windows Notepad is a built-in text editor applet included with the Windows OS license.",
        primary_url="https://www.microsoft.com/legal/terms-of-use",
        evidence_quote="Built-in Windows operating system utility included with Microsoft Windows OS.",
        is_os_bundled=True,
        source_type="OFFICIAL_TERMS",
        aliases=[
            "notepad",
            "microsoft.windowsnotepad",
            "windowsnotepad",
        ]
    ),
    CatalogRecognitionEntry(
        canonical_name="Windows Paint",
        canonical_vendor="Microsoft Windows",
        classification="OS_BUNDLED",
        availability_model="BUNDLED",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Operating System Bundled Feature",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Windows Paint is a built-in graphics applet included with the Windows OS license.",
        primary_url="https://www.microsoft.com/legal/terms-of-use",
        evidence_quote="Built-in Windows operating system applet included with Microsoft Windows OS.",
        is_os_bundled=True,
        source_type="OFFICIAL_TERMS",
        aliases=[
            "paint",
            "microsoft.paint",
        ]
    ),
    CatalogRecognitionEntry(
        canonical_name="Windows Camera",
        canonical_vendor="Microsoft Windows",
        classification="OS_BUNDLED",
        availability_model="BUNDLED",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Operating System Bundled Feature",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Windows Camera is a built-in capture utility included with the Windows OS license.",
        primary_url="https://www.microsoft.com/legal/terms-of-use",
        evidence_quote="Built-in Windows camera utility included under Microsoft Windows OS EULA.",
        is_os_bundled=True,
        source_type="OFFICIAL_TERMS",
        aliases=[
            "camera",
            "microsoft.windowscamera",
            "windowscamera",
        ]
    ),
    CatalogRecognitionEntry(
        canonical_name="Cursor",
        canonical_vendor="Anysphere",
        classification="FREE_AND_PAID",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Freemium / Named User Subscription",
        licensing_metric="USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Cursor AI code editor offers Free Hobby tier and Paid Pro/Business subscriptions.",
        primary_url="https://www.cursor.com/pricing",
        evidence_quote="Cursor AI editor provides free hobby tiers alongside commercial Pro and Business subscriptions.",
        source_type="OFFICIAL_PRICING",
        aliases=["cursor", "cursor editor", "cursor ai"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Claude",
        canonical_vendor="Anthropic",
        classification="FREE_AND_PAID",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Freemium / Named User Subscription",
        licensing_metric="USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Anthropic Claude offers Free tier and commercial Claude Pro/Team plans.",
        primary_url="https://www.anthropic.com/pricing",
        evidence_quote="Anthropic Claude desktop application and AI assistant plans.",
        source_type="OFFICIAL_PRICING",
        aliases=["claude", "claude desktop"]
    ),
    CatalogRecognitionEntry(
        canonical_name="VLC Media Player",
        canonical_vendor="VideoLAN",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="GNU General Public License (GPL)",
        licensing_metric="FREE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="VLC is a free and open-source cross-platform multimedia player under GNU GPL.",
        primary_url="https://www.videolan.org/legal.html",
        evidence_quote="VLC is a free and open-source cross-platform multimedia player distributed under GNU GPL.",
        is_open_source=True,
        source_type="EULA",
        aliases=["vlc", "vlc media player"]
    ),
    CatalogRecognitionEntry(
        canonical_name="WinRAR",
        canonical_vendor="win.rar GmbH",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Commercial Shareware (Trialware)",
        licensing_metric="DEVICE_OR_USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="WinRAR is a trialware utility requiring a paid license after evaluation.",
        primary_url="https://www.win-rar.com/terms.html",
        evidence_quote="WinRAR is a trialware software utility distributed by win.rar GmbH requiring license purchase after evaluation.",
        is_commercial=True,
        source_type="EULA",
        aliases=["winrar", "winrar archiver"]
    ),
    CatalogRecognitionEntry(
        canonical_name="PuTTY",
        canonical_vendor="Simon Tatham",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Open Source (MIT)",
        licensing_metric="FREE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="PuTTY is an open-source SSH client licensed under the MIT licence.",
        primary_url="https://www.chiark.greenend.org.uk/~sgtatham/putty/licence.html",
        evidence_quote="PuTTY is an open-source SSH and telnet client copyright Simon Tatham under the MIT licence.",
        is_open_source=True,
        source_type="EULA",
        aliases=["putty", "putty release"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Postman",
        canonical_vendor="Postman Inc.",
        classification="FREE_AND_PAID",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Freemium / Named User Subscription",
        licensing_metric="USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Postman API platform offers Free tier and paid Basic/Pro/Enterprise plans.",
        primary_url="https://www.postman.com/pricing/",
        evidence_quote="Postman API platform provides Free tier and paid Basic, Professional, and Enterprise subscriptions.",
        source_type="OFFICIAL_PRICING",
        aliases=["postman", "postman agent", "postman.postman"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Notion",
        canonical_vendor="Notion Labs, Inc.",
        classification="FREE_AND_PAID",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Freemium / Named User Subscription",
        licensing_metric="USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Notion workspace provides Free plan alongside Plus, Business, and Enterprise tiers.",
        primary_url="https://www.notion.so/pricing",
        evidence_quote="Notion workspace collaboration platform offers Free tier alongside Plus, Business, and Enterprise plans.",
        source_type="OFFICIAL_PRICING",
        aliases=["notion", "notion desktop", "notion.notion"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Discord",
        canonical_vendor="Discord Inc.",
        classification="FREEWARE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Freeware Application / Nitro Addon",
        licensing_metric="FREE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Discord voice and chat platform provides free core software with optional Nitro.",
        primary_url="https://discord.com/terms",
        evidence_quote="Discord voice and chat platform provides free core communication software with optional Nitro subscriptions.",
        source_type="OFFICIAL_TERMS",
        aliases=["discord"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Canva",
        canonical_vendor="Canva Pty Ltd",
        classification="FREE_AND_PAID",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Freemium / Named User Subscription",
        licensing_metric="USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Canva graphic design suite offers Free tier and Canva Pro/Teams subscriptions.",
        primary_url="https://www.canva.com/pricing/",
        evidence_quote="Canva graphic design suite offers Free tier and Canva Pro/Teams subscriptions.",
        source_type="OFFICIAL_PRICING",
        aliases=["canva"]
    ),
    CatalogRecognitionEntry(
        canonical_name="MongoDB",
        canonical_vendor="MongoDB, Inc.",
        classification="OPEN_SOURCE",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Server Side Public License (SSPL) / Enterprise",
        licensing_metric="SERVER_OR_CORE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="MongoDB Community is under SSPL; Commercial Enterprise licenses are available.",
        primary_url="https://www.mongodb.com/pricing",
        evidence_quote="MongoDB Community is available under Server Side Public License (SSPL) with Commercial Enterprise licenses available.",
        source_type="OFFICIAL_PRICING",
        aliases=["mongodb", "mongodb community server", "mongodb compass"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Google Chrome",
        canonical_vendor="Google",
        classification="FREEWARE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Freeware Application (Google Chrome Terms)",
        licensing_metric="FREE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Google Chrome is a proprietary web browser developed by Google, free to use.",
        primary_url="https://www.google.com/chrome/terms/",
        evidence_quote="Google Chrome is a proprietary web browser developed by Google, free to download and use.",
        source_type="OFFICIAL_TERMS",
        aliases=["google chrome", "chrome"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Brave Browser",
        canonical_vendor="Brave Software Inc",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Mozilla Public License 2.0 (MPL 2.0)",
        licensing_metric="FREE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Brave is a free, open-source web browser developed under Mozilla Public License 2.0.",
        primary_url="https://brave.com/terms-of-use/",
        evidence_quote="Brave is a free, open-source web browser developed by Brave Software under MPL 2.0.",
        is_open_source=True,
        source_type="EULA",
        aliases=["brave", "brave browser", "bravesoftware"]
    ),
    CatalogRecognitionEntry(
        canonical_name="AMD Radeon Software",
        canonical_vendor="Advanced Micro Devices, Inc.",
        classification="OEM_OR_BUNDLED",
        availability_model="BUNDLED",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Hardware Bundled Driver / Free Utility",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="AMD Software: Adrenalin Edition is bundled with AMD Radeon hardware graphics devices.",
        primary_url="https://www.amd.com/en/legal/terms.html",
        evidence_quote="AMD Software: Adrenalin Edition is bundled with AMD Radeon hardware graphics devices.",
        is_oem=True,
        source_type="OFFICIAL_TERMS",
        aliases=["amd radeon software", "amd radeon", "amd software", "radeon software"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Apple Time Machine",
        canonical_vendor="Apple Inc.",
        classification="OS_BUNDLED",
        availability_model="BUNDLED",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Operating System Bundled Feature",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Time Machine is a built-in backup utility component of the macOS operating system.",
        primary_url="https://www.apple.com/legal/sla/",
        evidence_quote="Time Machine is a built-in backup utility component of the macOS operating system.",
        is_os_bundled=True,
        source_type="OFFICIAL_TERMS",
        aliases=["time machine", "apple time machine"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Apple AirPort Utility",
        canonical_vendor="Apple Inc.",
        classification="OS_BUNDLED",
        availability_model="BUNDLED",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Operating System Bundled Feature",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="AirPort Utility is an Apple macOS system utility included with macOS.",
        primary_url="https://www.apple.com/legal/sla/",
        evidence_quote="AirPort Utility is an Apple macOS system utility for configuring AirPort base stations.",
        is_os_bundled=True,
        source_type="OFFICIAL_TERMS",
        aliases=["airport utility", "apple airport utility", "airport"]
    ),
    CatalogRecognitionEntry(
        canonical_name="CrowdStrike Falcon",
        canonical_vendor="CrowdStrike, Inc.",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Commercial Enterprise Subscription",
        licensing_metric="DEVICE_OR_USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="CrowdStrike Falcon endpoint protection and Device Control require enterprise commercial subscription.",
        primary_url="https://www.crowdstrike.com/terms-of-service/",
        evidence_quote="CrowdStrike Falcon endpoint protection and Device Control services require enterprise commercial subscription.",
        is_commercial=True,
        source_type="OFFICIAL_TERMS",
        aliases=["crowdstrike falcon", "crowdstrike device control", "crowdstrike sensor", "crowdstrike", "crowdstrike windows sensor"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Logitech Options",
        canonical_vendor="Logitech",
        classification="OEM_OR_BUNDLED",
        availability_model="BUNDLED",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Hardware Bundled Utility",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Logitech Options is a companion application bundled for Logitech hardware.",
        primary_url="https://www.logitech.com/en-us/legal/terms.html",
        evidence_quote="Logitech Options is a companion application for Logitech mice and keyboards.",
        is_oem=True,
        source_type="OFFICIAL_TERMS",
        aliases=["logitech options", "logi options+", "logitech g hub"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Linux Kernel Headers",
        canonical_vendor="The Linux Foundation",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="GNU General Public License v2 (GPL-2.0)",
        licensing_metric="FREE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Linux kernel headers are distributed under the GNU General Public License v2.",
        primary_url="https://www.kernel.org",
        evidence_quote="Linux kernel headers are distributed under the GNU General Public License v2 (GPL-2.0).",
        is_open_source=True,
        source_type="EULA",
        aliases=["linux-headers", "linux kernel headers", "kernel-headers"]
    ),
    CatalogRecognitionEntry(
        canonical_name="GCC",
        canonical_vendor="Free Software Foundation",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="GNU General Public License v3 (GPL-3.0)",
        licensing_metric="FREE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="GCC, the GNU Compiler Collection, is free software under GNU GPLv3.",
        primary_url="https://gcc.gnu.org",
        evidence_quote="GCC, the GNU Compiler Collection, is free software published under the GNU GPLv3.",
        is_open_source=True,
        source_type="EULA",
        aliases=["gcc", "gcc 11", "gcc-11", "gnu compiler collection", "g++"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Citrix Workspace",
        canonical_vendor="Citrix Systems, Inc.",
        classification="COMMERCIAL",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Client Access / Commercial VDI Infrastructure License",
        licensing_metric="CONCURRENT_OR_NAMED_USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Citrix Workspace app client connects to Citrix Virtual Apps and Desktops licensed per user or device.",
        primary_url="https://www.citrix.com/products/citrix-workspace/",
        evidence_quote="Citrix Workspace client application connects to licensed Citrix cloud and on-premises virtual desktop environments.",
        is_commercial=True,
        source_type="OFFICIAL_TERMS",
        aliases=["citrix workspace", "citrix workspace app", "citrix receiver"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Citrix Browser Content Redirection Plugin",
        canonical_vendor="Citrix Systems, Inc.",
        classification="COMMERCIAL_COMPONENT",
        availability_model="BUNDLED",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Bundled Component of Citrix Workspace",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Browser Content Redirection is a client companion plug-in for Citrix Workspace.",
        primary_url="https://docs.citrix.com/",
        evidence_quote="Citrix Browser Content Redirection is a client companion plugin covered under the parent Citrix Workspace deployment.",
        parent_product="Citrix Workspace",
        is_component=True,
        source_type="OFFICIAL_TERMS",
        aliases=["citrix browser content redirection", "citrix browser content redirection plug-in", "citrix browser content redirection plugin"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Citrix Authentication Manager",
        canonical_vendor="Citrix Systems, Inc.",
        classification="COMMERCIAL_COMPONENT",
        availability_model="BUNDLED",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Bundled Component of Citrix Workspace",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Authentication manager component included with Citrix Workspace.",
        primary_url="https://docs.citrix.com/",
        evidence_quote="Citrix Authentication Manager is an internal component included with Citrix Workspace.",
        parent_product="Citrix Workspace",
        is_component=True,
        source_type="OFFICIAL_TERMS",
        aliases=["citrix authentication manager"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Trellix Agent",
        canonical_vendor="Trellix",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Commercial Endpoint Subscription",
        licensing_metric="NODE_OR_DEVICE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Trellix Agent (formerly McAfee Agent) manages security client policies and requires enterprise subscription.",
        primary_url="https://www.trellix.com/en-us/about/legal.html",
        evidence_quote="Trellix endpoint management and security products require commercial enterprise licensing.",
        is_commercial=True,
        source_type="OFFICIAL_TERMS",
        aliases=["trellix agent", "mcafee agent"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Skyhigh Client Proxy",
        canonical_vendor="Skyhigh Security",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Commercial Enterprise Subscription",
        licensing_metric="USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Skyhigh Client Proxy directs web traffic to Skyhigh Security Cloud and requires commercial subscription.",
        primary_url="https://www.skyhighsecurity.com/en-us/about/legal.html",
        evidence_quote="Skyhigh Security products and client proxies are licensed under commercial subscription agreements.",
        is_commercial=True,
        source_type="OFFICIAL_TERMS",
        aliases=["skyhigh client proxy"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Netskope Client",
        canonical_vendor="Netskope",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Commercial Cloud Security Subscription",
        licensing_metric="USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Netskope Security Cloud client requires an active enterprise subscription.",
        primary_url="https://www.netskope.com/terms-of-service",
        evidence_quote="Netskope Cloud Security solutions are licensed on a per-user subscription basis.",
        is_commercial=True,
        source_type="OFFICIAL_TERMS",
        aliases=["netskope client", "netskope"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Tenable Nessus Agent",
        canonical_vendor="Tenable, Inc.",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Commercial Vulnerability Management Subscription",
        licensing_metric="ASSET_OR_NODE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Nessus Agent collects vulnerability scan telemetry for Tenable Vulnerability Management under paid subscription.",
        primary_url="https://www.tenable.com/legal/terms-of-service",
        evidence_quote="Tenable Nessus and Nessus Agents require commercial licensing per managed asset or node.",
        is_commercial=True,
        source_type="OFFICIAL_TERMS",
        aliases=["tenable nessus", "nessus agent", "tenable nessus agent"]
    ),
    CatalogRecognitionEntry(
        canonical_name="WinZip",
        canonical_vendor="Corel / Alludo",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Commercial Proprietary License",
        licensing_metric="DEVICE_OR_USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="WinZip is a commercial compression utility requiring a paid license after trial.",
        primary_url="https://www.winzip.com/en/company/legal/eula/",
        evidence_quote="WinZip is commercial software; business and corporate use requires a paid license.",
        is_commercial=True,
        source_type="EULA",
        aliases=["winzip", "winzip 24.0", "corel graphics - windows shell extension"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Npcap",
        canonical_vendor="Nmap Software LLC",
        classification="COMMERCIAL",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Dual License (Free for up to 5 systems / Commercial OEM)",
        licensing_metric="DEVICE_OR_INSTALLATION",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Npcap is free for personal use or up to 5 systems in an organization; larger corporate deployments require an Npcap Commercial Enterprise License.",
        primary_url="https://npcap.com/license/",
        evidence_quote="Npcap Free License allows usage on up to 5 systems; commercial license required for broader enterprise use.",
        is_commercial=True,
        source_type="OFFICIAL_PRICING",
        aliases=["npcap", "npcap oem"]
    ),
    CatalogRecognitionEntry(
        canonical_name="WiX Toolset",
        canonical_vendor="FireGiant",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Open Source (MS-RL / Apache 2.0)",
        licensing_metric="FREE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="WiX Toolset is an open-source Windows installer creation framework.",
        primary_url="https://wixtoolset.org/",
        evidence_quote="WiX Toolset is open source software available under open source licenses.",
        is_open_source=True,
        source_type="EULA",
        aliases=["wix toolset", "wix toolset v3", "wix toolset v4"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Robware RVTools",
        canonical_vendor="Robware",
        classification="FREEWARE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Freeware for VMware Environments",
        licensing_metric="FREE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="RVTools is a free Windows .NET application that displays VMware ESX/vCenter information.",
        primary_url="https://www.robware.net/rvtools/",
        evidence_quote="RVTools is a free Windows .NET utility to inventory VMware virtual environments.",
        is_commercial=False,
        source_type="OFFICIAL_TERMS",
        aliases=["rvtools", "robware rvtools"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Mem Reduct",
        canonical_vendor="Henry++",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Open Source (GPL v3)",
        licensing_metric="FREE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Mem Reduct is a lightweight open-source real-time memory management application under GPL v3.",
        primary_url="https://github.com/henrypp/memreduct",
        evidence_quote="Mem Reduct is an open-source memory management utility licensed under GNU GPL v3.",
        is_open_source=True,
        source_type="EULA",
        aliases=["mem reduct", "memreduct"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Perplexity",
        canonical_vendor="Perplexity AI",
        classification="FREE_AND_PAID",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Freemium / Named User Subscription",
        licensing_metric="USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Perplexity AI assistant offers Free tier and Pro/Enterprise subscriptions.",
        primary_url="https://www.perplexity.ai/pro",
        evidence_quote="Perplexity AI assistant offers Free access and commercial Pro subscriptions.",
        source_type="OFFICIAL_PRICING",
        aliases=["perplexity", "perplexity ai"]
    ),
    CatalogRecognitionEntry(
        canonical_name="AnyDesk",
        canonical_vendor="AnyDesk Software GmbH",
        classification="FREE_AND_PAID",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Freemium (Free for Personal Use / Commercial License Required for Business)",
        licensing_metric="NAMED_USER_OR_DEVICE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="AnyDesk is free for private use only; any commercial or business use requires a paid AnyDesk license.",
        primary_url="https://anydesk.com/en/order",
        evidence_quote="AnyDesk is free for personal use. Commercial use requires a paid license.",
        is_commercial=True,
        source_type="OFFICIAL_PRICING",
        aliases=["anydesk"]
    ),
    CatalogRecognitionEntry(
        canonical_name="UltraViewer",
        canonical_vendor="DucFabulous Co., Ltd.",
        classification="FREE_AND_PAID",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Freemium (Free with usage limits / Paid Commercial Pro)",
        licensing_metric="DEVICE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="UltraViewer offers a free tier with time limits and paid commercial licenses for business support.",
        primary_url="https://www.ultraviewer.net/en/order.html",
        evidence_quote="UltraViewer remote desktop provides free basic version and commercial paid licenses.",
        source_type="OFFICIAL_PRICING",
        aliases=["ultraviewer"]
    ),
    CatalogRecognitionEntry(
        canonical_name="CCleaner",
        canonical_vendor="Piriform Software",
        classification="FREE_AND_PAID",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Freemium (Free for Home Use / CCleaner Business Required for Corporate)",
        licensing_metric="DEVICE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="CCleaner Free is licensed for personal home use only; corporate environments require CCleaner Business Edition.",
        primary_url="https://www.ccleaner.com/business",
        evidence_quote="CCleaner Free is for home use only. Commercial environments require CCleaner Business or CCleaner Cloud.",
        is_commercial=True,
        source_type="OFFICIAL_PRICING",
        aliases=["ccleaner"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Zoom Workplace",
        canonical_vendor="Zoom Video Communications",
        classification="FREE_AND_PAID",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Freemium / Named User Subscription",
        licensing_metric="USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Zoom Workplace offers Basic Free tier and Pro/Business/Enterprise subscriptions.",
        primary_url="https://zoom.us/pricing",
        evidence_quote="Zoom Workplace platform provides Basic free tier and commercial Pro, Business, and Enterprise plans.",
        is_commercial=True,
        source_type="OFFICIAL_PRICING",
        aliases=["zoom workplace", "zoom", "zoom meetings"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Internet Download Manager",
        canonical_vendor="Tonec Inc.",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Commercial Shareware / Perpetual or 1-Year License",
        licensing_metric="DEVICE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Internet Download Manager (IDM) is shareware requiring purchase of a commercial license after 30-day trial.",
        primary_url="https://www.internetdownloadmanager.com/purchase.html",
        evidence_quote="Internet Download Manager is commercial software requiring license registration after evaluation.",
        is_commercial=True,
        source_type="OFFICIAL_PRICING",
        aliases=["internet download manager", "idm"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Qurio Assessment Platform",
        canonical_vendor="TeamLease EdTech",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Commercial Enterprise Proctored Assessment License",
        licensing_metric="TEST_OR_CANDIDATE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Qurio is an AI-powered proctoring and assessment platform for enterprise examination and hiring.",
        primary_url="https://teamleaseedtech.com/qurio/",
        evidence_quote="Qurio AI proctored assessment platform is commercially licensed for institutional and corporate testing.",
        is_commercial=True,
        source_type="OFFICIAL_TERMS",
        aliases=["qurio assessment platform", "qurio"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Naarad Collector Agent",
        canonical_vendor="Silver Leaf Solutions",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Commercial Enterprise Agent",
        licensing_metric="NODE_OR_DEVICE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Naarad is an enterprise data collection and software asset intelligence agent.",
        primary_url="https://silverleafsolutions.com",
        evidence_quote="Naarad collector agent is proprietary enterprise inventory software.",
        is_commercial=True,
        source_type="OFFICIAL_TERMS",
        aliases=["naarad collector agent", "naarad"]
    ),
    CatalogRecognitionEntry(
        canonical_name="PostgreSQL",
        canonical_vendor="PostgreSQL Global Development Group",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="PostgreSQL License (Permissive BSD-style)",
        licensing_metric="FREE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="PostgreSQL is an open-source object-relational database system under the liberal PostgreSQL licence.",
        primary_url="https://www.postgresql.org/about/licence/",
        evidence_quote="PostgreSQL is released under the PostgreSQL License, a liberal Open Source license, similar to BSD or MIT.",
        is_open_source=True,
        source_type="EULA",
        aliases=["postgresql", "postgresql 16", "postgresql 15", "postgresql 14", "postgres", "postgresql.postgresql"]
    ),
    CatalogRecognitionEntry(
        canonical_name="ARCON PAM",
        canonical_vendor="ARCON",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Enterprise Privileged Access Management License",
        licensing_metric="TARGET_OR_USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="ARCON Privileged Access Management is an enterprise security platform licensed commercially.",
        primary_url="https://arconnet.com/",
        evidence_quote="ARCON PAM is enterprise security software requiring commercial enterprise license agreement.",
        is_commercial=True,
        source_type="OFFICIAL_TERMS",
        aliases=["arcon pam", "arcon"]
    ),
    CatalogRecognitionEntry(
        canonical_name="ARCON PAM Plugin",
        canonical_vendor="ARCON",
        classification="COMMERCIAL_COMPONENT",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Parent Product Component",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="ARCON PAM Plugin is a client component covered by the parent enterprise ARCON PAM deployment.",
        primary_url="https://arconnet.com/",
        evidence_quote="Client plugin for enterprise ARCON Privileged Access Management installations.",
        parent_product="ARCON PAM",
        source_type="OFFICIAL_TERMS",
        aliases=["arcon pam plugin"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Zscaler Client Connector",
        canonical_vendor="Zscaler",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Enterprise SASE Named User Subscription",
        licensing_metric="USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Zscaler Client Connector connects endpoints to the Zscaler Zero Trust Exchange under commercial enterprise subscription.",
        primary_url="https://www.zscaler.com/pricing-and-plans",
        evidence_quote="Zscaler Client Connector is licensed as part of Zscaler Internet Access (ZIA) or Zscaler Private Access (ZPA) subscriptions.",
        is_commercial=True,
        source_type="OFFICIAL_TERMS",
        aliases=["zscaler client connector", "zscaler"]
    ),
    CatalogRecognitionEntry(
        canonical_name="ManageEngine Endpoint Central",
        canonical_vendor="ManageEngine (Zoho)",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Commercial Endpoint Subscription / Device License",
        licensing_metric="DEVICE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="ManageEngine Endpoint Central is commercial endpoint management software licensed per managed computer.",
        primary_url="https://www.manageengine.com/products/desktop-central/pricing.html",
        evidence_quote="Endpoint Central is licensed based on the number of computers and mobile devices managed.",
        is_commercial=True,
        source_type="OFFICIAL_PRICING",
        aliases=["manageengine endpoint central / uems agent", "manageengine endpoint central", "uems agent", "desktop central"]
    ),
    CatalogRecognitionEntry(
        canonical_name="ServiceNow MID Server",
        canonical_vendor="ServiceNow",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Enterprise ITOM / ServiceNow Subscription Entitlement",
        licensing_metric="SERVER_OR_INSTANCE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="ServiceNow Management, Instrumentation, and Discovery (MID) Server facilitates communication between a ServiceNow instance and external systems.",
        primary_url="https://www.servicenow.com/",
        evidence_quote="MID Server is an enterprise integration agent included with ServiceNow ITOM and platform subscriptions.",
        is_commercial=True,
        source_type="OFFICIAL_TERMS",
        aliases=["servicenow mid server", "mid server"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Snow Inventory Agent",
        canonical_vendor="Snow Software / Flexera",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Enterprise Software Asset Management Subscription",
        licensing_metric="DEVICE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Snow Inventory Agent collects hardware and software inventory under commercial enterprise license.",
        primary_url="https://www.snowsoftware.com/",
        evidence_quote="Snow Inventory is commercial SAM software licensed per inventory endpoint.",
        is_commercial=True,
        source_type="OFFICIAL_TERMS",
        aliases=["snow inventory agent", "snow inventory agent for windows", "snow software"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Snow Inventory Server",
        canonical_vendor="Snow Software / Flexera",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Enterprise Software Asset Management Server License",
        licensing_metric="SERVER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Snow Inventory Server aggregates endpoint discovery data for software asset management.",
        primary_url="https://www.snowsoftware.com/",
        evidence_quote="Snow Inventory Server is commercial enterprise management infrastructure.",
        is_commercial=True,
        source_type="OFFICIAL_TERMS",
        aliases=["snow inventory server"]
    ),
    CatalogRecognitionEntry(
        canonical_name="FlexNet Inventory Agent",
        canonical_vendor="Flexera",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Enterprise Software Asset Management License",
        licensing_metric="DEVICE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="FlexNet Inventory Agent is Flexera commercial endpoint software for SAM discovery.",
        primary_url="https://www.flexera.com/",
        evidence_quote="FlexNet Manager is commercial enterprise software asset management software.",
        is_commercial=True,
        source_type="OFFICIAL_TERMS",
        aliases=["flexnet inventory agent", "flexera"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Sophos Connect",
        canonical_vendor="Sophos",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Enterprise Firewall / VPN Subscription",
        licensing_metric="USER_OR_DEVICE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Sophos Connect is an enterprise IPSec and SSL VPN client for Sophos Firewall.",
        primary_url="https://www.sophos.com/",
        evidence_quote="Sophos Connect client enables remote workers to connect to enterprise networks protected by Sophos Firewall.",
        is_commercial=True,
        source_type="OFFICIAL_TERMS",
        aliases=["sophos connect", "sophos"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Ivanti Secure Access Client",
        canonical_vendor="Ivanti",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Enterprise Secure Access / VPN License",
        licensing_metric="CONCURRENT_OR_USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Ivanti Secure Access Client (formerly Pulse Secure) provides enterprise network access.",
        primary_url="https://www.ivanti.com/",
        evidence_quote="Ivanti Secure Access Client is enterprise software licensed as part of Ivanti Connect Secure.",
        is_commercial=True,
        source_type="OFFICIAL_TERMS",
        aliases=["ivanti secure access client", "pulse secure client", "pulse secure"]
    ),
    CatalogRecognitionEntry(
        canonical_name="VMware Horizon Client",
        canonical_vendor="Omnissa",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Enterprise VDI Named / Concurrent User License",
        licensing_metric="USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="VMware Horizon Client connects to enterprise virtual desktop infrastructure managed by Omnissa/VMware.",
        primary_url="https://www.omnissa.com/",
        evidence_quote="Horizon Client is the client endpoint for VMware Horizon enterprise VDI environments.",
        is_commercial=True,
        source_type="OFFICIAL_TERMS",
        aliases=["vmware horizon client", "omnissa horizon client", "horizon client"]
    ),
    CatalogRecognitionEntry(
        canonical_name="VMware Workstation Player",
        canonical_vendor="VMware / Broadcom",
        classification="FREE_AND_PAID",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Free for Personal Use / Commercial License Required for Business",
        licensing_metric="USER_OR_DEVICE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="VMware Workstation Player is free for personal non-commercial use, but requires a commercial license for business use.",
        primary_url="https://www.vmware.com/products/workstation-player.html",
        evidence_quote="VMware Workstation Player is free for personal, non-commercial use. Commercial use requires purchase of a commercial license.",
        is_commercial=True,
        source_type="OFFICIAL_TERMS",
        aliases=["vmware workstation player", "vmware workstation pro", "vmware workstation"]
    ),
    CatalogRecognitionEntry(
        canonical_name="IBM License Metric Tool",
        canonical_vendor="IBM",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Enterprise Software Asset Management Licensing (Sub-Capacity)",
        licensing_metric="SERVER_OR_CORE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="IBM License Metric Tool helps maintain an audit-ready inventory of IBM software assets under sub-capacity licensing.",
        primary_url="https://www.ibm.com/products/license-metric-tool",
        evidence_quote="ILMT is a mandatory tool for IBM Passport Advantage sub-capacity licensing compliance.",
        is_commercial=True,
        source_type="OFFICIAL_TERMS",
        aliases=["ibm license metric tool", "ilmt"]
    ),
    CatalogRecognitionEntry(
        canonical_name="BigFix",
        canonical_vendor="HCLSoftware",
        classification="COMMERCIAL",
        availability_model="PAID_ONLY",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Enterprise Endpoint Management Licensing",
        licensing_metric="NODE_OR_DEVICE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="BigFix is an enterprise endpoint management platform licensed commercially per managed endpoint.",
        primary_url="https://www.hcl-software.com/bigfix",
        evidence_quote="BigFix automates endpoint management and security compliance under enterprise licensing agreements.",
        is_commercial=True,
        source_type="OFFICIAL_TERMS",
        aliases=["bigfix", "ibm endpoint manager client", "ibm endpoint manager console", "ibm endpoint manager server", "ibm endpoint manager installation generator", "bigfix installation generator"]
    ),
    CatalogRecognitionEntry(
        canonical_name="TeamViewer",
        canonical_vendor="TeamViewer",
        classification="FREE_AND_PAID",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Free for Personal Use / Business Subscription Required",
        licensing_metric="USER_OR_DEVICE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="TeamViewer is free for private non-commercial use, but requires a commercial subscription for professional/business use.",
        primary_url="https://www.teamviewer.com/en/pricing/",
        evidence_quote="TeamViewer is free for personal use. For business use, a commercial license is required.",
        is_commercial=True,
        source_type="OFFICIAL_PRICING",
        aliases=["teamviewer"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Slack",
        canonical_vendor="Slack Technologies / Salesforce",
        classification="FREE_AND_PAID",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Freemium / Named User Subscription",
        licensing_metric="USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Slack provides a Free plan with limited message history and Pro, Business+, and Enterprise Grid paid subscriptions.",
        primary_url="https://slack.com/pricing",
        evidence_quote="Slack offers free and paid subscription plans on a per-active-user basis.",
        is_commercial=True,
        source_type="OFFICIAL_PRICING",
        aliases=["slack"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Figma",
        canonical_vendor="Figma",
        classification="FREE_AND_PAID",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Freemium / Named User Subscription",
        licensing_metric="USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Figma is a collaborative interface design tool offering a Free Starter plan and Professional/Organization subscriptions.",
        primary_url="https://www.figma.com/pricing/",
        evidence_quote="Figma provides free Starter plans and paid Professional and Organization subscriptions.",
        is_commercial=True,
        source_type="OFFICIAL_PRICING",
        aliases=["figma"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Figma Agent",
        canonical_vendor="Figma",
        classification="COMMERCIAL_COMPONENT",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Parent Product Font Helper Component",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Figma Agent is a free background helper allowing the Figma browser app to use local fonts.",
        primary_url="https://www.figma.com/",
        evidence_quote="Figma Agent is a helper component for local font access in Figma.",
        parent_product="Figma",
        source_type="OFFICIAL_TERMS",
        aliases=["figma agent"]
    ),
    CatalogRecognitionEntry(
        canonical_name="BitTorrent",
        canonical_vendor="BitTorrent Inc.",
        classification="FREE_AND_PAID",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Freemium / Ad-Supported with Pro Upgrade",
        licensing_metric="USER",
        commercial_use_allowed=False,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="BitTorrent client has an ad-supported free version and optional paid Pro subscriptions.",
        primary_url="https://www.bittorrent.com/",
        evidence_quote="BitTorrent software offers free basic downloading and optional paid Pro enhancements.",
        source_type="OFFICIAL_TERMS",
        aliases=["bittorrent", "bittorrent web", "utorrent", "utorrent web", "µtorrent", "µtorrent web"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Dropbox",
        canonical_vendor="Dropbox",
        classification="FREE_AND_PAID",
        availability_model="FREE_AND_PAID",
        license_requirement="CONTEXT_DEPENDENT",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Freemium / Named User Subscription",
        licensing_metric="USER",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Dropbox provides a Basic free tier with 2 GB storage and paid Plus, Essentials, and Business subscriptions.",
        primary_url="https://www.dropbox.com/plans",
        evidence_quote="Dropbox offers free storage accounts and commercial subscription plans for professionals and teams.",
        is_commercial=True,
        source_type="OFFICIAL_PRICING",
        aliases=["dropbox", "dropboxinc.dropbox", "dropbox.dropbox"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Core Temp",
        canonical_vendor="ALCPU",
        classification="FREEWARE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Freeware Hardware Monitoring Utility",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Core Temp is a compact, no fuss, small footprint, yet powerful program to monitor processor temperature.",
        primary_url="https://www.alcpu.com/CoreTemp/",
        evidence_quote="Core Temp is freeware for personal and commercial monitoring use.",
        source_type="OFFICIAL_TERMS",
        aliases=["core temp"]
    ),
    CatalogRecognitionEntry(
        canonical_name="360 Extreme Browser",
        canonical_vendor="Qihoo 360",
        classification="FREEWARE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Freeware Web Browser",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="360 Extreme Browser is a free Chromium-based web browser developed by Qihoo 360.",
        primary_url="https://browser.360.cn/",
        evidence_quote="360 Extreme Browser is free proprietary software for web browsing.",
        source_type="OFFICIAL_TERMS",
        aliases=["360 extreme browser", "360 safe center"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Amazon Send to Kindle",
        canonical_vendor="Amazon",
        classification="FREEWARE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Free Companion Application",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Send to Kindle is a free desktop companion for transferring documents to Kindle devices.",
        primary_url="https://www.amazon.com/sendtokindle",
        evidence_quote="Free desktop application provided by Amazon for Kindle document delivery.",
        source_type="OFFICIAL_TERMS",
        aliases=["amazon send to kindle", "send to kindle"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Discord",
        canonical_vendor="Discord Inc.",
        classification="FREEWARE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Freeware Communication Client / Nitro Add-on",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=False,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Discord is free proprietary VoIP and instant messaging software with optional Nitro consumer perks.",
        primary_url="https://discord.com/terms",
        evidence_quote="Discord service is free to use with optional consumer subscriptions (Nitro).",
        source_type="OFFICIAL_TERMS",
        aliases=["discord"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Dell SupportAssist",
        canonical_vendor="Dell",
        classification="OEM_OR_BUNDLED",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="OEM Hardware Support Utility",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Dell SupportAssist is pre-installed OEM support software for Dell PCs.",
        primary_url="https://www.dell.com/supportassist",
        evidence_quote="SupportAssist is automated technology from Dell that provides proactively monitored support.",
        is_oem=True,
        source_type="OEM_TERMS",
        aliases=["dell supportassist", "dell.supportassistforpcs", "dell supportassist os recovery plugin", "dell supportassist remediation"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Dell Optimizer",
        canonical_vendor="Dell",
        classification="OEM_OR_BUNDLED",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="OEM Hardware Optimization Utility",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Dell Optimizer is an AI-based software application that optimizes the performance of Dell systems.",
        primary_url="https://www.dell.com/",
        evidence_quote="Dell Optimizer is bundled free with compatible Dell commercial systems.",
        is_oem=True,
        source_type="OEM_TERMS",
        aliases=["dell optimizer", "dell core services", "dell pair", "dell connected service delivery", "dell connected service delivery subagent"]
    ),
    CatalogRecognitionEntry(
        canonical_name="HP Support Assistant",
        canonical_vendor="HP",
        classification="OEM_OR_BUNDLED",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="OEM Hardware Support Utility",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="HP Support Assistant provides automated support solutions and updates for HP PCs.",
        primary_url="https://www.hp.com/go/hpsupportassistant",
        evidence_quote="HP Support Assistant is included with new HP desktop and notebook PCs.",
        is_oem=True,
        source_type="OEM_TERMS",
        aliases=["hp support assistant", "hp connection optimizer", "hp documentation", "hp privacy settings", "hp system event utility", "omen gaming hub"]
    ),
    CatalogRecognitionEntry(
        canonical_name="Lenovo Vantage",
        canonical_vendor="Lenovo",
        classification="OEM_OR_BUNDLED",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="OEM Hardware Companion Application",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Lenovo Vantage is pre-installed OEM software for managing Lenovo system settings and hardware updates.",
        primary_url="https://www.lenovo.com/us/en/software/vantage/",
        evidence_quote="Lenovo Vantage is a customized application for Lenovo PCs to optimize hardware settings.",
        is_oem=True,
        source_type="OEM_TERMS",
    ),
    CatalogRecognitionEntry(
        canonical_name="MySQL Community Server",
        canonical_vendor="Oracle",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="GPL-2.0 — Free/Open Source",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="MySQL Community Server is the freely downloadable version of the world's most popular open source database, licensed under the GNU General Public License v2.",
        primary_url="https://www.mysql.com/about/legal/licensing/oem/",
        evidence_quote="MySQL Community Edition is available under the GPL-2.0 license free of charge.",
        is_open_source=True,
        source_type="TERMS",
        aliases=[
            "mysql server",
            "mysql server 8.0",
            "mysql server 8.4",
            "mysql server 5.7",
            "mysql community server",
            "mysql workbench",
            "mysql installer",
        ],
    ),
    CatalogRecognitionEntry(
        canonical_name="MongoDB Compass",
        canonical_vendor="MongoDB, Inc.",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="SSPL-1.0 — Free to Use",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="MongoDB Compass GUI is free to use for developing and querying MongoDB databases under the Server Side Public License (SSPL v1.0).",
        primary_url="https://www.mongodb.com/licensing/server-side-public-license",
        evidence_quote="MongoDB Compass is provided under the Server Side Public License (SSPL v1.0).",
        is_open_source=True,
        source_type="TERMS",
        aliases=[
            "mongodb compass",
            "mongodb compass community",
            "mongodb compass isolated",
            "mongodb compass readonly",
        ],
    ),
    CatalogRecognitionEntry(
        canonical_name="Steam",
        canonical_vendor="Valve Corporation",
        classification="FREEWARE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="Freeware",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Steam client software is free to download and install for accessing digital content governed by the consumer Steam Subscriber Agreement.",
        primary_url="https://store.steampowered.com/subscriber_agreement/",
        evidence_quote="The Steam client is distributed free of charge under the Steam Subscriber Agreement.",
        source_type="TERMS",
        aliases=[
            "steam",
            "steam client",
            "valve steam",
        ],
    ),
    CatalogRecognitionEntry(
        canonical_name="OpenJDK",
        canonical_vendor="OpenJDK Community",
        classification="OPEN_SOURCE",
        availability_model="FREE",
        license_requirement="NO",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_NO,
        licensing_model="GPL-2.0 with Classpath Exception — Free/Open Source",
        licensing_metric="NOT_APPLICABLE",
        commercial_use_allowed=True,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="OpenJDK is an open-source implementation of the Java SE Platform licensed under the GNU General Public License v2 with Classpath Exception.",
        primary_url="https://openjdk.org/legal/gplv2+ce.html",
        evidence_quote="Licensed under GNU General Public License v2 with Classpath Exception.",
        is_open_source=True,
        source_type="TERMS",
        aliases=[
            "openjdk",
            "eclipse temurin",
            "temurin",
            "amazon corretto",
            "corretto",
            "adoptium",
            "microsoft build of openjdk",
            "zulu openjdk",
            "bellsoft liberica openjdk",
        ],
    ),
    CatalogRecognitionEntry(
        canonical_name="Microsoft Office Home & Student 2021",
        canonical_vendor="Microsoft",
        classification="COMMERCIAL",
        availability_model="COMMERCIAL",
        license_requirement="YES",
        license_required=FinalLicenseStatus.LICENSE_REQUIRED_YES,
        licensing_model="Commercial — Perpetual",
        licensing_metric="DEVICE",
        commercial_use_allowed=False,
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Microsoft Office Home & Student 2021 is a one-time purchase, perpetual desktop license for 1 PC or Mac.",
        primary_url="https://www.microsoft.com/en-us/microsoft-365/p/office-home-student-2021/",
        evidence_quote="One-time purchase for 1 PC or Mac. Classic 2021 versions of Word, Excel, and PowerPoint.",
        is_commercial=True,
        source_type="TERMS",
        aliases=[
            "office home & student 2021",
            "office home and student 2021",
            "microsoft office home & student 2021",
            "microsoft office home and student 2021",
            "office home & student 2019",
            "office home and student 2019",
        ],
    ),
]

try:
    from backend.inventory.recognition.catalog_extensions import EXTENSION_RECOGNITION_RULES
    RECOGNITION_RULES.extend(EXTENSION_RECOGNITION_RULES)
except Exception as _e:
    pass



# -------------------------------------------------------------------------------------------------
# APPINVENTORY RECOGNITION PATTERNS FOR BUILT-IN WINDOWS COMPONENTS & OEM DRIVERS
# -------------------------------------------------------------------------------------------------

WINDOWS_OS_COMPONENTS_PREFIXES = [
    "microsoft.windows.",
    "microsoftwindows.",
    "microsoft.windows",
    "windows.",
    "microsoft.winappruntime",
    "microsoftcorporationii.winappruntime",
    "microsoft.aad.brokerplugin",
    "microsoft.accountscontrol",
    "microsoft.asynctextservice",
    "microsoft.bioenrollment",
    "microsoft.creddialoghost",
    "microsoft.win32webviewhost",
    "microsoft.gamingapp",
    "microsoft.gaming",
    "microsoft.heifimageextension",
    "microsoft.vclibs",
    "microsoft.xboxgamecallableui",
    "microsoft.xboxgamingoverlay",
    "microsoft.xboxgameoverlay",
    "microsoft.xboxidentityprovider",
    "microsoft.xboxspeechtotextoverlay",
    "microsoft.xbox.tcui",
    "microsoft.windowscalculator",
    "microsoft.windowscommunicationsapps",
    "microsoft.windowsmaps",
    "microsoft.windowsterminal",
    "microsoft.zunemusic",
    "microsoft.zunevideo",
    "microsoft.microsoftstickynotes",
    "microsoft.microsoftjournal",
    "microsoft.microsoftsolitairecollection",
    "microsoft.todos",
    "microsoft.windowssoundrecorder",
    "microsoft.windowsalarms",
    "microsoft.ecapp",
    "microsoft.lockapp",
    "microsoft.startexperiencesapp",
    "microsoft.widgetsplatformruntime",
    "microsoft.webpimageextension",
    "microsoft.av1videoextension",
    "microsoft.gethelp",
    "microsoft.powerautomatedesktop",
    "microsoft.screensketch",
    "microsoft.yourphone",
    "microsoft.desktopappinstaller",
    "microsoft.heifimageextension",
    "microsoft.paint",
    "microsoft.windowsfeedbackhub",
    "microsoft.storepurchaseapp",
    "microsoft.windowsstore",
    "microsoft.winget.source",
    "microsoft.windowsnotepad",
    "microsoft.windowscamera",
    "microsoft.windowsphotos",
    "microsoft.onedrivesync",
    "microsoft.onedrive",
    "microsoft.copilot",
    "copilot",
    "microsoft.microsoftedge",
    "microsoft.edge",
    "microsoft.bingsearch",
    "microsoft.bingweather",
    "microsoft.bingnews",
    "microsoft.people",
    "microsoft.sechealthui",
    "microsoft.mixedreality.portal",
    "microsoft.hevcvideoextension",
    "microsoft.avcencodervideoextension",
    "microsoft.mpeg2videoextension",
    "microsoft.webmediaextensions",
    "microsoft.whiteboard",
    "microsoftcorporationii.microsoftfamily",
    "microsoftcorporationii.quickassist",
    "microsoftcorporationii.windowssubsystemf",
    "microsoft.applicationcompatibilityenhanc",
    "f46d4000-fd22-4db4-ac8e-4e1ddde828fe",
]

OEM_HARDWARE_PREFIXES = [
    "intel(r) chipset",
    "intel chipset",
    "appup.intelgraphicsexperience",
    "realteksemiconductorcorp.realtekaudiocon",
    "realtek audio",
    "e046963f.lenovocompanion",
    "e046963f.lenovovoiceworldwide",
    "e0469640.lenovoutility",
    "lenovo vantage service",
    "lenovo voice service",
    "elevoctechnologyco.ltd.smartmicrophonese",
    "dolbylaboratories.dolbyaudio",
    "57540amznmobilellc.amazonalexa",
    "clipchamp.clipchamp",
]


class RecognitionCatalog:
    """
    Evaluates application names against the catalog and classification hierarchies.
    """

    @classmethod
    def derive_license_type(cls, rule: Optional[CatalogRecognitionEntry]) -> str:
        """Derives legal/license family from a catalog recognition entry."""
        if not rule:
            return "Unknown"

        corpus = f"{rule.licensing_model or ''} {rule.terms_summary or ''} {rule.evidence_quote or ''} {rule.canonical_name or ''}".lower()
        if re.search(r"\b(psf|python software foundation)\b", corpus):
            return "PSF License"
        if re.search(r"\b(sspl|server side public license)\b", corpus):
            return "SSPL-1.0"
        if re.search(r"\bclasspath exception\b", corpus):
            return "GPL-2.0 with Classpath Exception"
        if re.search(r"\bapache\b", corpus):
            return "Apache-2.0"
        if re.search(r"\b(gpl[- ]?v?3)\b", corpus):
            return "GPL-3.0"
        if re.search(r"\b(gpl[- ]?v?2)\b", corpus):
            return "GPL-2.0"
        if re.search(r"\blgpl\b", corpus):
            return "LGPL"
        if re.search(r"\bgpl\b", corpus):
            return "GPL-3.0"
        if re.search(r"\bmit\b", corpus):
            return "MIT"
        if re.search(r"\bbsd[- ]?3[- ]?clause\b", corpus):
            return "BSD-3-Clause"
        if re.search(r"\bbsd[- ]?2[- ]?clause\b", corpus):
            return "BSD-2-Clause"
        if re.search(r"\bbsd\b", corpus):
            return "BSD"
        if re.search(r"\b(mpl|mozilla public)\b", corpus):
            return "MPL"
        if re.search(r"\b(public domain|cc0)\b", corpus):
            return "Public Domain"
        if re.search(r"\bfreeware\b", corpus) or rule.classification in ("FREEWARE", "FREE"):
            return "Freeware"
        if re.search(r"\bproprietary\b", corpus):
            return "Proprietary"
        if rule.classification == "COMMERCIAL" or rule.is_commercial:
            return "Commercial"
        return "Unknown"

    @classmethod
    def derive_combined_license_model(cls, rule: Optional[CatalogRecognitionEntry]) -> str:
        """Derives improved combined LicenseModel (legal family + commercial model) from a catalog entry."""
        if not rule:
            return "No License Required"

        legal = cls.derive_license_type(rule)
        raw_m = str(rule.licensing_model or "").strip()

        # If already combined with ' — '
        if " — " in raw_m:
            return raw_m

        if legal in ("MIT", "Apache-2.0", "GPL-2.0", "GPL-3.0", "LGPL", "BSD", "BSD-3-Clause", "BSD-2-Clause", "MPL", "GPL-2.0 with Classpath Exception"):
            return f"{legal} — Free/Open Source"
        if legal == "PSF License":
            return "PSF License — Free/Open Source"
        if legal == "SSPL-1.0":
            return "SSPL-1.0 — Free to Use"
        if legal == "Public Domain":
            return "Public Domain — Free"
        if legal == "Freeware":
            return "Freeware"

        # Commercial or Proprietary
        m_lower = raw_m.lower()
        met_str = str(rule.licensing_metric or "").lower()
        name_lower = str(rule.canonical_name or "").lower()

        if any(term in name_lower or term in m_lower for term in ("home & student", "home and student", "ltsc", "2016", "2019", "2021", "2024", "perpetual", "one-time")):
            comm = "Perpetual"
        elif "per seat" in m_lower or (("subscription" in m_lower or "user" in m_lower) and "user" in met_str):
            comm = "Per Seat Subscription"
        elif "subscription" in m_lower:
            comm = "Subscription"
        elif "perpetual" in m_lower:
            comm = "Perpetual"
        elif "core" in m_lower or "core" in met_str:
            comm = "Per Core"
        elif "device" in m_lower or "device" in met_str:
            comm = "Per Device"
        elif "installation" in m_lower or "installation" in met_str:
            comm = "Per Installation"
        elif "user" in met_str:
            comm = "Per Seat Subscription" if legal == "Commercial" else "Subscription"
        elif "core" in met_str:
            comm = "Per Core"
        elif "device" in met_str:
            comm = "Per Device"
        elif "installation" in met_str:
            comm = "Per Installation"
        elif raw_m:
            comm = raw_m
        else:
            comm = "Perpetual" if any(term in name_lower for term in ("home", "student", "ltsc", "standard")) else ("Subscription" if legal == "Commercial" else "Perpetual")

        if legal != "Unknown":
            return f"{legal} — {comm}"
        return comm

    @classmethod
    def find_rule_by_name(cls, app_name: str, publisher: Optional[str] = None) -> Optional[CatalogRecognitionEntry]:
        """
        Attempts exact or canonical token matching against known catalog recognition rules.
        """
        if not app_name:
            return None
        
        name_lower = app_name.strip().lower()
        pub_lower = (publisher or "").strip().lower()
        
        # 1. Exact canonical alias check
        for rule in RECOGNITION_RULES:
            if name_lower == rule.canonical_name.lower():
                return rule
            if rule.aliases:
                for alias in rule.aliases:
                    a_low = alias.lower()
                    if a_low in ("calculator", "photos", "camera", "paint", "notepad"):
                        if not ("microsoft" in pub_lower or "windows" in pub_lower or "microsoft" in name_lower):
                            continue
                        if "gnome" in name_lower or "ubuntu" in pub_lower or "apple" in pub_lower or "debian" in pub_lower:
                            continue
                    if name_lower == a_low or name_lower.startswith(a_low + " ") or name_lower.endswith(" " + a_low):
                        if a_low in ("calculator", "photos", "camera", "paint", "notepad") and ("gnome" in name_lower or "ubuntu" in pub_lower or "apple" in pub_lower or "debian" in pub_lower):
                            continue
                        return rule
        
        # 2. Tokenized canonical checks with strict collision protection
        # Specifically: .NET SDK / .NET Runtime must NEVER match Visual Studio (Section 7)
        if ".net sdk" in name_lower or "dotnet sdk" in name_lower or ".net core sdk" in name_lower:
            for rule in RECOGNITION_RULES:
                if rule.canonical_name == ".NET SDK":
                    return rule
        
        if "visual studio code" in name_lower or "vscode" in name_lower:
            for rule in RECOGNITION_RULES:
                if rule.canonical_name == "Visual Studio Code":
                    return rule

        if "sql server management studio" in name_lower or "ssms" in name_lower:
            for rule in RECOGNITION_RULES:
                if rule.canonical_name == "SQL Server Management Studio":
                    return rule

        if "power bi desktop" in name_lower or "powerbi desktop" in name_lower:
            for rule in RECOGNITION_RULES:
                if rule.canonical_name == "Power BI Desktop":
                    return rule

        # 3. Known Open Source or Specific Tool checks
        if name_lower.startswith("python 3") or name_lower.startswith("python3") or name_lower == "python":
            for rule in RECOGNITION_RULES:
                if rule.canonical_name == "Python":
                    return rule
                    
        if name_lower.startswith("go programming language") or "golang" in name_lower:
            for rule in RECOGNITION_RULES:
                if rule.canonical_name == "Go":
                    return rule
                    
        if name_lower.startswith("php ") or name_lower == "php":
            for rule in RECOGNITION_RULES:
                if rule.canonical_name == "PHP":
                    return rule

        # 4. Check other exact rules
        for rule in RECOGNITION_RULES:
            if rule.aliases:
                for alias in rule.aliases:
                    a_low = alias.lower().strip()
                    if not a_low:
                        continue
                    # Match alias as full token or word boundary, not arbitrary substring inside another word
                    if not re.search(r'(?<![a-zA-Z0-9])' + re.escape(a_low) + r'(?![a-zA-Z0-9])', name_lower):
                        continue

                    # Avoid substring false positives
                    if a_low == "visual studio" and ("code" in name_lower or ".net" in name_lower):
                        continue
                    if a_low == "photos" and not ("photos" in name_lower and ("microsoft" in pub_lower or "windows" in pub_lower or "microsoft" in name_lower)):
                        continue
                    if a_low == "camera" and not ("camera" in name_lower and ("microsoft" in pub_lower or "windows" in pub_lower or "microsoft" in name_lower)):
                        continue
                    if a_low == "calculator" and not ("calculator" in name_lower and ("microsoft" in pub_lower or "windows" in pub_lower or "microsoft" in name_lower)):
                        continue
                    if a_low == "paint" and not ("paint" in name_lower and ("microsoft" in pub_lower or "windows" in pub_lower or "microsoft" in name_lower)):
                        continue
                    if a_low == "notepad" and not ("notepad" in name_lower and "notepad++" not in name_lower and ("microsoft" in pub_lower or "windows" in pub_lower or "microsoft" in name_lower)):
                        continue
                    return rule

        return None

    @classmethod
    def is_windows_os_component(cls, app_name: str, publisher: Optional[str] = None) -> bool:
        """
        Determines whether the application is an explicitly recognized Windows OS component or AppX package.
        """
        if not app_name:
            return False
        name_lower = app_name.strip().lower()
        name_dots = name_lower.replace(" ", ".").replace("-", ".").replace("_", ".")
        
        for prefix in WINDOWS_OS_COMPONENTS_PREFIXES:
            prefix_dots = prefix.replace(" ", ".").replace("-", ".").replace("_", ".")
            if (name_lower.startswith(prefix) or prefix in name_lower or
                name_dots.startswith(prefix_dots) or prefix_dots in name_dots):
                return True
        return False

    @classmethod
    def is_oem_hardware_component(cls, app_name: str, publisher: Optional[str] = None) -> bool:
        """
        Determines whether the application is an OEM hardware driver or bundled utility.
        """
        if not app_name:
            return False
        name_lower = app_name.strip().lower()
        name_dots = name_lower.replace(" ", ".").replace("-", ".").replace("_", ".")
        for prefix in OEM_HARDWARE_PREFIXES:
            prefix_dots = prefix.replace(" ", ".").replace("-", ".").replace("_", ".")
            if (name_lower.startswith(prefix) or prefix in name_lower or
                name_dots.startswith(prefix_dots) or prefix_dots in name_dots):
                return True
        return False
