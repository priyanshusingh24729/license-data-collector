"""
feed_pdf_data_to_db.py
----------------------
Ingests and applies the 3-part Software Inventory Normalization & Licensing Report data
into the database:
- upload_license_results (resolves unknown / needs review rows)
- applications (populates canonical application catalog)
- detected_applications (updates endpoint detection mappings)
- installation_license_results (updates machine inventory results)
- inventory_uploads (updates summary counts and resolved metrics)
- recognition catalog / alias system
"""

import sys
import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from backend.database.connection import SessionLocal, engine
from backend.models.inventory_upload import InventoryUpload, UploadLicenseResult
from backend.models.inventory import DetectedApplication, InstallationLicenseResult
from backend.models.application import Application, compute_canonical_application_key
from backend.models.enums import ApplicationStatus, ApplicationResearchStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("feed_pdf_data")

# Complete extracted dataset from PDF Reports (Parts 1, 2, and 3)
PDF_ENTRIES = [
    # ------------------ PART 1 ------------------
    {
        "raw_application": "1_https___agave.myanalytics.cdn.office.net04aca5ec",
        "normalized_name": "Microsoft Viva Insights / MyAnalytics Web Component",
        "vendor": "Microsoft",
        "commercial_status": "Enterprise web component",
        "license_model": "Bundled with Microsoft 365",
        "availability": "Web/Enterprise",
        "confidence": "MEDIUM",
        "notes": "Review exact package mapping"
    },
    {
        "raw_application": "360 Extreme Browser",
        "normalized_name": "360 Extreme Browser",
        "vendor": "Qihoo 360",
        "commercial_status": "Freeware",
        "license_model": "Proprietary freeware",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "422Stofkat.ToffeeShareWeb_b9ykhg8k81a9a",
        "normalized_name": "ToffeeShare Web",
        "vendor": "ToffeeShare / Stofkat",
        "commercial_status": "Free/Freemium",
        "license_model": "Service-based",
        "availability": "Web/Windows",
        "confidence": "MEDIUM",
        "notes": "Package normalization"
    },
    {
        "raw_application": "4505Fortemedia.FMAPOControl_4pejv7q2gmsnr",
        "normalized_name": "Fortemedia FMAPO Control",
        "vendor": "Fortemedia",
        "commercial_status": "OEM/Bundled",
        "license_model": "OEM driver/component",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "4DF9E0F8.Netflix_mcm4njqhnhss8",
        "normalized_name": "Netflix",
        "vendor": "Netflix",
        "commercial_status": "Subscription service",
        "license_model": "Subscription",
        "availability": "Windows/Web",
        "confidence": "HIGH",
        "notes": "Free app; streaming subscription"
    },
    {
        "raw_application": "52833Alienforce.ChessFusionFree_np5hvx4gj677g",
        "normalized_name": "Chess Fusion Free",
        "vendor": "Alienforce",
        "commercial_status": "Free",
        "license_model": "Freeware / ads or IAP possible",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": ""
    },
    {
        "raw_application": "53058betterapp.AnyScan_90ct3cgs7yy6a",
        "normalized_name": "AnyScan",
        "vendor": "BetterApp",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Windows",
        "confidence": "LOW",
        "notes": "Verify publisher and product"
    },
    {
        "raw_application": "53058betterapp.TorrentDownloader-_90ct3cgs7yy6a",
        "normalized_name": "Torrent Downloader",
        "vendor": "BetterApp",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Windows",
        "confidence": "LOW",
        "notes": "Verify product legitimacy/license"
    },
    {
        "raw_application": "A-Volute.Nahimic_w2gh52qy24etm",
        "normalized_name": "Nahimic",
        "vendor": "A-Volute",
        "commercial_status": "OEM/Bundled",
        "license_model": "OEM license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "A278AB0D.Asphalt9_h6adky7gbf63m",
        "normalized_name": "Asphalt 9",
        "vendor": "Gameloft",
        "commercial_status": "Free-to-play",
        "license_model": "In-app purchases",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Accops Workspace",
        "normalized_name": "Accops Workspace",
        "vendor": "Accops Systems",
        "commercial_status": "Commercial Enterprise",
        "license_model": "Enterprise contract/subscription",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "ActiveSync",
        "normalized_name": "Microsoft ActiveSync",
        "vendor": "Microsoft",
        "commercial_status": "Bundled/System",
        "license_model": "Windows/Enterprise component",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": ""
    },
    {
        "raw_application": "AD2F1837.HPPrinterControl_v10z8vjag6ke6",
        "normalized_name": "HP Printer Control",
        "vendor": "HP",
        "commercial_status": "Free/OEM",
        "license_model": "OEM utility",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "adobe.acrobatreaderdc.protectedmode",
        "normalized_name": "Adobe Acrobat Reader DC",
        "vendor": "Adobe",
        "commercial_status": "Free",
        "license_model": "Freeware",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Component/package variant"
    },
    {
        "raw_application": "AdobeAcrobatDCCoreApp_pc75e8sa7ep4e",
        "normalized_name": "Adobe Acrobat Reader DC",
        "vendor": "Adobe",
        "commercial_status": "Free",
        "license_model": "Freeware",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Core component"
    },
    {
        "raw_application": "AdobeAcrobatReaderCoreApp_pc75e8sa7ep4e",
        "normalized_name": "Adobe Acrobat Reader DC",
        "vendor": "Adobe",
        "commercial_status": "Free",
        "license_model": "Freeware",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Core component"
    },
    {
        "raw_application": "AdobeNotificationClient_enpm4xejd91yc",
        "normalized_name": "Adobe Notification Client",
        "vendor": "Adobe",
        "commercial_status": "Component",
        "license_model": "Parent product license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "AdvancedMicroDevicesInc-2.AMDRadeonSoftware_0a9344xs7nr4m",
        "normalized_name": "AMD Radeon Software",
        "vendor": "AMD",
        "commercial_status": "Free",
        "license_model": "Bundled driver software",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "AMD Radeon Software",
        "normalized_name": "AMD Radeon Software",
        "vendor": "AMD",
        "commercial_status": "Free",
        "license_model": "Bundled driver software",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Android Studio",
        "normalized_name": "Android Studio",
        "vendor": "Google",
        "commercial_status": "Free",
        "license_model": "Proprietary free developer software",
        "availability": "Windows/macOS/Linux",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "AppDataProtection",
        "normalized_name": "App Data Protection",
        "vendor": "Microsoft",
        "commercial_status": "Bundled/System",
        "license_model": "OS component",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": ""
    },
    {
        "raw_application": "AppleInc.AppleTVWin_nzyj5cx40ttqa",
        "normalized_name": "Apple TV",
        "vendor": "Apple",
        "commercial_status": "Subscription/content service",
        "license_model": "Subscription / purchases",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "AppleInc.iCloud_nzyj5cx40ttqa",
        "normalized_name": "Apple iCloud",
        "vendor": "Apple",
        "commercial_status": "Freemium",
        "license_model": "Subscription for expanded storage",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "AppleInc.iTunes_nzyj5cx40ttqa",
        "normalized_name": "iTunes",
        "vendor": "Apple",
        "commercial_status": "Free",
        "license_model": "Freeware",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "AppProtection",
        "normalized_name": "App Protection",
        "vendor": "Microsoft",
        "commercial_status": "Bundled/System",
        "license_model": "OS/security component",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": ""
    },
    {
        "raw_application": "ARCON PAM",
        "normalized_name": "ARCON PAM",
        "vendor": "ARCON",
        "commercial_status": "Commercial Enterprise",
        "license_model": "Enterprise contract/subscription",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "ARCON PAM Plugin",
        "normalized_name": "ARCON PAM Plugin",
        "vendor": "ARCON",
        "commercial_status": "Component",
        "license_model": "Parent product license",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "arthurdlittle.sharepoint.com-8BF11C4E_8a2bnpnrj3na8",
        "normalized_name": "Arthur D. Little SharePoint",
        "vendor": "Microsoft / Organization-managed",
        "commercial_status": "Enterprise web app",
        "license_model": "Microsoft 365 organizational license",
        "availability": "Web",
        "confidence": "MEDIUM",
        "notes": "PWA/web entry"
    },
    {
        "raw_application": "Automator Application Stub",
        "normalized_name": "Automator Application Stub",
        "vendor": "Apple",
        "commercial_status": "Bundled",
        "license_model": "macOS component",
        "availability": "macOS",
        "confidence": "MEDIUM",
        "notes": ""
    },
    {
        "raw_application": "AV1 Video Extension",
        "normalized_name": "AV1 Video Extension",
        "vendor": "Microsoft",
        "commercial_status": "Free/Bundled",
        "license_model": "Codec component",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": ""
    },
    {
        "raw_application": "AVC Encoder Video Extension",
        "normalized_name": "AVC Encoder Video Extension",
        "vendor": "Microsoft",
        "commercial_status": "Bundled",
        "license_model": "Codec component",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": ""
    },
    {
        "raw_application": "BCR Plug-in",
        "normalized_name": "BCR Plug-in",
        "vendor": "Unknown / likely enterprise component",
        "commercial_status": "Component",
        "license_model": "Parent product dependent",
        "availability": "Enterprise",
        "confidence": "LOW",
        "notes": "Manual identification"
    },
    {
        "raw_application": "BigFix Installation Generator",
        "normalized_name": "BigFix Installation Generator",
        "vendor": "HCLSoftware",
        "commercial_status": "Commercial Enterprise",
        "license_model": "Enterprise licensing",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "BitTorrent",
        "normalized_name": "BitTorrent",
        "vendor": "BitTorrent Inc.",
        "commercial_status": "Freemium",
        "license_model": "Free + premium",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "BitTorrent Web",
        "normalized_name": "BitTorrent Web",
        "vendor": "BitTorrent Inc.",
        "commercial_status": "Freemium",
        "license_model": "Free + premium",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "c5e2524a-ea46-4f67-841f-6a9465d9d515_cw5n1h2txyewy",
        "normalized_name": "Unknown GUID Package",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "GUID package"
    },
    {
        "raw_application": "calibre",
        "normalized_name": "calibre",
        "vendor": "Kovid Goyal / calibre community",
        "commercial_status": "Free",
        "license_model": "Open source",
        "availability": "Windows/macOS/Linux",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "CCleaner 7",
        "normalized_name": "CCleaner",
        "vendor": "Gen Digital",
        "commercial_status": "Freemium",
        "license_model": "Free + paid subscription",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "chat.openai.com-37DC27AA_9andzsn4mr4ca",
        "normalized_name": "ChatGPT",
        "vendor": "OpenAI",
        "commercial_status": "Freemium",
        "license_model": "Free + subscription tiers",
        "availability": "Web/Windows PWA",
        "confidence": "HIGH",
        "notes": "Web/PWA package"
    },
    {
        "raw_application": "chat.openai.com-41209409_9andzsn4mr4ca",
        "normalized_name": "ChatGPT",
        "vendor": "OpenAI",
        "commercial_status": "Freemium",
        "license_model": "Free + subscription tiers",
        "availability": "Web/Windows PWA",
        "confidence": "HIGH",
        "notes": "Duplicate web/PWA entry"
    },
    {
        "raw_application": "chocolatey",
        "normalized_name": "Chocolatey",
        "vendor": "Chocolatey Software",
        "commercial_status": "Free/Open Source + Commercial",
        "license_model": "Open source core + commercial products",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Chocolatey .NET Framework extensions",
        "normalized_name": "Chocolatey .NET Framework Extensions",
        "vendor": "Chocolatey Software",
        "commercial_status": "Free",
        "license_model": "Open source/community extension",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Component"
    },
    {
        "raw_application": "Chocolatey Compatibility Extension",
        "normalized_name": "Chocolatey Compatibility Extension",
        "vendor": "Chocolatey Software",
        "commercial_status": "Free",
        "license_model": "Open source/community extension",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Component"
    },
    {
        "raw_application": "Chocolatey Core Extensions",
        "normalized_name": "Chocolatey Core Extensions",
        "vendor": "Chocolatey Software",
        "commercial_status": "Free",
        "license_model": "Open source/community extension",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Component"
    },
    {
        "raw_application": "Cisco Webex Meetings",
        "normalized_name": "Cisco Webex",
        "vendor": "Cisco",
        "commercial_status": "Freemium/Subscription",
        "license_model": "Business subscription",
        "availability": "Windows/Web",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Citrix Authentication Manager",
        "normalized_name": "Citrix Authentication Manager",
        "vendor": "Citrix",
        "commercial_status": "Component",
        "license_model": "Enterprise environment dependent",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Citrix Browser Content Redirection Plug",
        "normalized_name": "Citrix Browser Content Redirection Plug-in",
        "vendor": "Citrix",
        "commercial_status": "Component",
        "license_model": "Included with Citrix environment",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize duplicate naming"
    },
    {
        "raw_application": "Citrix Browser Content Redirection Plug-in",
        "normalized_name": "Citrix Browser Content Redirection Plug-in",
        "vendor": "Citrix",
        "commercial_status": "Component",
        "license_model": "Included with Citrix environment",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Citrix Desktop Lock",
        "normalized_name": "Citrix Desktop Lock",
        "vendor": "Citrix",
        "commercial_status": "Enterprise component",
        "license_model": "Enterprise licensing/environment",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Citrix Secure Access Endpoint Analysis",
        "normalized_name": "Citrix Secure Access Endpoint Analysis",
        "vendor": "Citrix",
        "commercial_status": "Enterprise component",
        "license_model": "Enterprise licensing/environment",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Citrix Web Helper",
        "normalized_name": "Citrix Web Helper",
        "vendor": "Citrix",
        "commercial_status": "Component",
        "license_model": "Included with Citrix client environment",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Citrix Workspace",
        "normalized_name": "Citrix Workspace",
        "vendor": "Citrix",
        "commercial_status": "Free client / Enterprise backend",
        "license_model": "Backend requires enterprise licensing",
        "availability": "Windows/macOS/Linux",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Citrix Workspace 2503",
        "normalized_name": "Citrix Workspace",
        "vendor": "Citrix",
        "commercial_status": "Free client / Enterprise backend",
        "license_model": "Versioned client; backend enterprise licensing",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize version separately"
    },
    {
        "raw_application": "Citrix Workspace 2507",
        "normalized_name": "Citrix Workspace",
        "vendor": "Citrix",
        "commercial_status": "Free client / Enterprise backend",
        "license_model": "Versioned client; backend enterprise licensing",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize version separately"
    },
    {
        "raw_application": "Citrix Workspace 2511",
        "normalized_name": "Citrix Workspace",
        "vendor": "Citrix",
        "commercial_status": "Free client / Enterprise backend",
        "license_model": "Versioned client; backend enterprise licensing",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize version separately"
    },
    {
        "raw_application": "Citrix Workspace 2603",
        "normalized_name": "Citrix Workspace",
        "vendor": "Citrix",
        "commercial_status": "Free client / Enterprise backend",
        "license_model": "Versioned client; backend enterprise licensing",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize version separately"
    },
    {
        "raw_application": "Citrix Workspace Inside",
        "normalized_name": "Citrix Workspace Component",
        "vendor": "Citrix",
        "commercial_status": "Component",
        "license_model": "Parent product dependent",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": ""
    },
    {
        "raw_application": "Citrix Workspace(DV)",
        "normalized_name": "Citrix Workspace Component (DV)",
        "vendor": "Citrix",
        "commercial_status": "Component",
        "license_model": "Parent product dependent",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": ""
    },
    {
        "raw_application": "Citrix Workspace(SSON)",
        "normalized_name": "Citrix Workspace Single Sign-On Component",
        "vendor": "Citrix",
        "commercial_status": "Component",
        "license_model": "Parent product dependent",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Citrix Workspace(USB)",
        "normalized_name": "Citrix Workspace USB Component",
        "vendor": "Citrix",
        "commercial_status": "Component",
        "license_model": "Parent product dependent",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Cocoa-AppleScript Applet",
        "normalized_name": "Cocoa AppleScript Applet",
        "vendor": "Apple",
        "commercial_status": "Bundled",
        "license_model": "macOS development component",
        "availability": "macOS",
        "confidence": "MEDIUM",
        "notes": ""
    },
    {
        "raw_application": "Cross Device Experience Host",
        "normalized_name": "Cross Device Experience Host",
        "vendor": "Microsoft",
        "commercial_status": "Bundled/System",
        "license_model": "Windows component",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "D91E29CF.WacomNotes_38kynpdw5g1aw",
        "normalized_name": "Wacom Notes",
        "vendor": "Wacom",
        "commercial_status": "Free/OEM",
        "license_model": "OEM or bundled utility",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": ""
    },
    {
        "raw_application": "datalossd",
        "normalized_name": "Data Loss Prevention Component",
        "vendor": "Unknown",
        "commercial_status": "Enterprise component",
        "license_model": "Parent product dependent",
        "availability": "Enterprise",
        "confidence": "LOW",
        "notes": "Manual vendor identification"
    },
    {
        "raw_application": "DataLossPrevention",
        "normalized_name": "Data Loss Prevention",
        "vendor": "Unknown",
        "commercial_status": "Enterprise/Commercial likely",
        "license_model": "Vendor dependent",
        "availability": "Enterprise",
        "confidence": "LOW",
        "notes": "Manual vendor identification"
    },
    {
        "raw_application": "Dell Active Pen Service",
        "normalized_name": "Dell Active Pen Service",
        "vendor": "Dell",
        "commercial_status": "OEM/Bundled",
        "license_model": "OEM utility",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Dell Connected Service Delivery",
        "normalized_name": "Dell Connected Service Delivery",
        "vendor": "Dell",
        "commercial_status": "OEM/Bundled",
        "license_model": "Dell service component",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Dell Connected Service Delivery SubAgent",
        "normalized_name": "Dell Connected Service Delivery SubAgent",
        "vendor": "Dell",
        "commercial_status": "Component",
        "license_model": "Parent product dependent",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Dell Core Services",
        "normalized_name": "Dell Core Services",
        "vendor": "Dell",
        "commercial_status": "OEM/Bundled",
        "license_model": "Dell system component",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Dell Optimizer",
        "normalized_name": "Dell Optimizer",
        "vendor": "Dell",
        "commercial_status": "OEM/Bundled",
        "license_model": "OEM utility",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Dell Pair",
        "normalized_name": "Dell Pair",
        "vendor": "Dell",
        "commercial_status": "Free/OEM",
        "license_model": "OEM utility",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Dell SupportAssist",
        "normalized_name": "Dell SupportAssist",
        "vendor": "Dell",
        "commercial_status": "Free/OEM",
        "license_model": "Support utility; optional paid support plans",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Dell SupportAssist OS Recovery Plugin for Dell Update",
        "normalized_name": "Dell SupportAssist OS Recovery Plugin",
        "vendor": "Dell",
        "commercial_status": "Component",
        "license_model": "Parent product dependent",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Dell SupportAssist Remediation",
        "normalized_name": "Dell SupportAssist Remediation",
        "vendor": "Dell",
        "commercial_status": "Component",
        "license_model": "Parent product dependent",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Dell.SupportAssistforPCs_18ctm2993j0dg",
        "normalized_name": "Dell SupportAssist",
        "vendor": "Dell",
        "commercial_status": "Free/OEM",
        "license_model": "Support utility",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize package"
    },
    {
        "raw_application": "Desktop_IT_DC",
        "normalized_name": "Desktop IT DC",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": ""
    },
    {
        "raw_application": "deviceTRUST ICA Client Extension 2603",
        "normalized_name": "deviceTRUST ICA Client Extension",
        "vendor": "deviceTRUST",
        "commercial_status": "Enterprise component",
        "license_model": "Enterprise licensing",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Version separately"
    },
    {
        "raw_application": "deviceTRUST ICA Client Extension v25.3",
        "normalized_name": "deviceTRUST ICA Client Extension",
        "vendor": "deviceTRUST",
        "commercial_status": "Enterprise component",
        "license_model": "Enterprise licensing",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Version separately"
    },
    {
        "raw_application": "deviceTRUST ICA Client Extension2511",
        "normalized_name": "deviceTRUST ICA Client Extension",
        "vendor": "deviceTRUST",
        "commercial_status": "Enterprise component",
        "license_model": "Enterprise licensing",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Version separately"
    },
    {
        "raw_application": "Dmidecode",
        "normalized_name": "dmidecode",
        "vendor": "Open-source community",
        "commercial_status": "Free",
        "license_model": "GPL/Open source",
        "availability": "Linux/Unix primarily",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Docs",
        "normalized_name": "Docs",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "Generic name"
    },
    {
        "raw_application": "Droplet with Settable Properties",
        "normalized_name": "Droplet with Settable Properties",
        "vendor": "Apple",
        "commercial_status": "Bundled",
        "license_model": "macOS Automator/AppleScript component",
        "availability": "macOS",
        "confidence": "MEDIUM",
        "notes": ""
    },
    {
        "raw_application": "Dropbox OEM",
        "normalized_name": "Dropbox",
        "vendor": "Dropbox",
        "commercial_status": "Freemium",
        "license_model": "Free + subscription",
        "availability": "Windows/macOS/Web",
        "confidence": "HIGH",
        "notes": "OEM distribution"
    },
    {
        "raw_application": "DTS Sound Unbound",
        "normalized_name": "DTS Sound Unbound",
        "vendor": "DTS",
        "commercial_status": "Free app / Paid features possible",
        "license_model": "Service/content dependent",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": ""
    },
    {
        "raw_application": "E2A4F912-2574-4A75-9BB0-0D023378592B_cw5n1h2txyewy",
        "normalized_name": "Unknown GUID Package",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "GUID package"
    },
    {
        "raw_application": "EaseUS MobiMover 6.2.4.3",
        "normalized_name": "EaseUS MobiMover",
        "vendor": "EaseUS",
        "commercial_status": "Freemium",
        "license_model": "Free + paid edition/license",
        "availability": "Windows/macOS",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "ELANMicroelectronicsCorpo.TrackPoint_stws0m115j6hg",
        "normalized_name": "ELAN TrackPoint",
        "vendor": "ELAN Microelectronics",
        "commercial_status": "OEM/Bundled",
        "license_model": "Hardware driver component",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "EonVPN",
        "normalized_name": "EonVPN",
        "vendor": "Unknown",
        "commercial_status": "Enterprise/Unknown",
        "license_model": "Manual verification required",
        "availability": "Windows/Enterprise",
        "confidence": "LOW",
        "notes": ""
    },
    {
        "raw_application": "Epic Games Launcher",
        "normalized_name": "Epic Games Launcher",
        "vendor": "Epic Games",
        "commercial_status": "Free",
        "license_model": "Proprietary freeware",
        "availability": "Windows/macOS",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Epic Online Services",
        "normalized_name": "Epic Online Services",
        "vendor": "Epic Games",
        "commercial_status": "Free service/component",
        "license_model": "Service/developer agreement",
        "availability": "Cross-platform",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "F.luxSoftwareLLC.f.lux_sw1dyjdkns7gt",
        "normalized_name": "f.lux",
        "vendor": "Flux Software LLC",
        "commercial_status": "Free for personal use",
        "license_model": "Freeware / commercial terms vary",
        "availability": "Windows/macOS/Linux",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Facebook",
        "normalized_name": "Facebook",
        "vendor": "Meta",
        "commercial_status": "Free",
        "license_model": "Free service; advertising-supported",
        "availability": "Web/Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Figma",
        "normalized_name": "Figma",
        "vendor": "Figma",
        "commercial_status": "Freemium",
        "license_model": "Free + subscription tiers",
        "availability": "Web/Windows/macOS",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Figma Agent",
        "normalized_name": "Figma Agent",
        "vendor": "Figma",
        "commercial_status": "Component/Service",
        "license_model": "Parent product/service dependent",
        "availability": "Windows/macOS",
        "confidence": "MEDIUM",
        "notes": ""
    },
    {
        "raw_application": "FileZilla 3.65.0",
        "normalized_name": "FileZilla",
        "vendor": "FileZilla Project",
        "commercial_status": "Free",
        "license_model": "Open source (GPL)",
        "availability": "Windows/macOS/Linux",
        "confidence": "HIGH",
        "notes": "Version separately"
    },
    {
        "raw_application": "Films & TV",
        "normalized_name": "Films & TV",
        "vendor": "Microsoft",
        "commercial_status": "Free/Bundled",
        "license_model": "Microsoft Store/Windows app",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Final Round",
        "normalized_name": "Final Round",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": ""
    },
    {
        "raw_application": "FINGERSOFT.HILLCLIMBRACING_r6rtpscs7gwyg",
        "normalized_name": "Hill Climb Racing",
        "vendor": "Fingersoft",
        "commercial_status": "Free-to-play",
        "license_model": "In-app purchases",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "FlexNet Inventory Agent",
        "normalized_name": "FlexNet Inventory Agent",
        "vendor": "Flexera",
        "commercial_status": "Enterprise/Commercial",
        "license_model": "Part of Flexera licensing environment",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": ""
    },

    # ------------------ PART 2 ------------------
    {
        "raw_application": "GBT_MB_Update",
        "normalized_name": "GIGABYTE Motherboard Update",
        "vendor": "GIGABYTE",
        "commercial_status": "OEM/Bundled",
        "license_model": "OEM utility",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": "Normalize component"
    },
    {
        "raw_application": "GBT_RGB_Sync_Control",
        "normalized_name": "GIGABYTE RGB Sync Control",
        "vendor": "GIGABYTE",
        "commercial_status": "OEM/Bundled",
        "license_model": "OEM utility",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": ""
    },
    {
        "raw_application": "Geocode Glib",
        "normalized_name": "Geocode Glib",
        "vendor": "GNOME / open-source community",
        "commercial_status": "Free",
        "license_model": "Open-source library",
        "availability": "Linux",
        "confidence": "HIGH",
        "notes": "Library/package"
    },
    {
        "raw_application": "geocode-glib-common",
        "normalized_name": "geocode-glib-common",
        "vendor": "GNOME / open-source community",
        "commercial_status": "Free",
        "license_model": "Open-source library",
        "availability": "Linux",
        "confidence": "HIGH",
        "notes": "Library/package"
    },
    {
        "raw_application": "Ghostscript GPL 8.64 (Msi",
        "normalized_name": "Ghostscript GPL",
        "vendor": "Artifex Software",
        "commercial_status": "Free/Open Source",
        "license_model": "GPL",
        "availability": "Windows/Linux/macOS",
        "confidence": "HIGH",
        "notes": "Version old; normalize"
    },
    {
        "raw_application": "GIGABYTE Control Center",
        "normalized_name": "GIGABYTE Control Center",
        "vendor": "GIGABYTE",
        "commercial_status": "Free/OEM",
        "license_model": "Bundled OEM utility",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "GIGABYTE SSD Firmware Update Tool",
        "normalized_name": "GIGABYTE SSD Firmware Update Tool",
        "vendor": "GIGABYTE",
        "commercial_status": "Free/OEM",
        "license_model": "Hardware utility",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Gmail",
        "normalized_name": "Gmail",
        "vendor": "Google",
        "commercial_status": "Freemium/Service",
        "license_model": "Free + Google Workspace subscriptions",
        "availability": "Web/Mobile",
        "confidence": "HIGH",
        "notes": "Web/PWA"
    },
    {
        "raw_application": "group.is.workflow",
        "normalized_name": "Workflow (package identifier)",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "Package identifier"
    },
    {
        "raw_application": "Hard Disk Sentinel PRO",
        "normalized_name": "Hard Disk Sentinel PRO",
        "vendor": "HDSentinel",
        "commercial_status": "Commercial",
        "license_model": "Perpetual license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Paid Pro product"
    },
    {
        "raw_application": "HEIF Image Extension",
        "normalized_name": "HEIF Image Extension",
        "vendor": "Microsoft",
        "commercial_status": "Free/Bundled",
        "license_model": "Store/system extension",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "HEVC Video Extensions from Device Manu...",
        "normalized_name": "HEVC Video Extensions",
        "vendor": "Microsoft / device manufacturer",
        "commercial_status": "OEM/Bundled",
        "license_model": "Codec license/OEM",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Horizon HTML5 Multimedia Redirection Client",
        "normalized_name": "Horizon HTML5 Multimedia Redirection Client",
        "vendor": "Omnissa",
        "commercial_status": "Enterprise component",
        "license_model": "Enterprise environment license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "HP Connection Optimizer",
        "normalized_name": "HP Connection Optimizer",
        "vendor": "HP",
        "commercial_status": "Free/OEM",
        "license_model": "OEM utility/component",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "HP Documentation",
        "normalized_name": "HP Documentation",
        "vendor": "HP",
        "commercial_status": "Free/OEM",
        "license_model": "OEM utility/component",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "HP Inc. Energy Star",
        "normalized_name": "HP Inc. Energy Star",
        "vendor": "HP",
        "commercial_status": "Free/OEM",
        "license_model": "OEM utility/component",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "HP LaserJet Professional M1130-M1210 MFP Series",
        "normalized_name": "HP LaserJet Professional M1130-M1210 MFP Series",
        "vendor": "HP",
        "commercial_status": "Free/OEM",
        "license_model": "Printer driver/software",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "HP LaserJet Professional M1210 MFP Series Fax",
        "normalized_name": "HP LaserJet Professional M1210 MFP Series Fax",
        "vendor": "HP",
        "commercial_status": "Free/OEM",
        "license_model": "Printer driver/software",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "HP Privacy Settings",
        "normalized_name": "HP Privacy Settings",
        "vendor": "HP",
        "commercial_status": "Free/OEM",
        "license_model": "OEM utility/component",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "HP Smart",
        "normalized_name": "HP Smart",
        "vendor": "HP",
        "commercial_status": "Free",
        "license_model": "Printer utility/service",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "HP Support Assistant",
        "normalized_name": "HP Support Assistant",
        "vendor": "HP",
        "commercial_status": "Free/OEM",
        "license_model": "OEM support utility",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "HP System Event Utility",
        "normalized_name": "HP System Event Utility",
        "vendor": "HP",
        "commercial_status": "Free/OEM",
        "license_model": "OEM utility/component",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "HyperPKI_HYP2003",
        "normalized_name": "HyperPKI HYP2003",
        "vendor": "HyperPKI / Unknown",
        "commercial_status": "Commercial/Enterprise likely",
        "license_model": "Certificate/token middleware",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": "Verify vendor contract"
    },
    {
        "raw_application": "IBM Endpoint Manager Client",
        "normalized_name": "IBM Endpoint Manager Client",
        "vendor": "IBM",
        "commercial_status": "Commercial Enterprise",
        "license_model": "Endpoint-based enterprise licensing",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": "BigFix family / normalize parent"
    },
    {
        "raw_application": "IBM Endpoint Manager Console",
        "normalized_name": "IBM Endpoint Manager Console",
        "vendor": "IBM",
        "commercial_status": "Commercial Enterprise",
        "license_model": "Endpoint-based enterprise licensing",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": "BigFix family / normalize parent"
    },
    {
        "raw_application": "IBM Endpoint Manager Installation Generator",
        "normalized_name": "IBM Endpoint Manager Installation Generator",
        "vendor": "IBM",
        "commercial_status": "Commercial Enterprise",
        "license_model": "Endpoint-based enterprise licensing",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": "BigFix family / normalize parent"
    },
    {
        "raw_application": "IBM Endpoint Manager Server",
        "normalized_name": "IBM Endpoint Manager Server",
        "vendor": "IBM",
        "commercial_status": "Commercial Enterprise",
        "license_model": "Endpoint-based enterprise licensing",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": "BigFix family / normalize parent"
    },
    {
        "raw_application": "IBM License Metric Tool",
        "normalized_name": "IBM License Metric Tool",
        "vendor": "IBM",
        "commercial_status": "Enterprise/Commercial",
        "license_model": "Enterprise software asset management licensing",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "IIS Express Application Compatibility Database for",
        "normalized_name": "IIS Express Application Compatibility Database",
        "vendor": "Microsoft",
        "commercial_status": "Free/Bundled",
        "license_model": "Developer/system component",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": ""
    },
    {
        "raw_application": "Ink.Handwriting.en-IN.1.0",
        "normalized_name": "Windows Ink Handwriting en-IN",
        "vendor": "Microsoft",
        "commercial_status": "Bundled/System",
        "license_model": "Windows language component",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Ink.Handwriting.Main.en-IN.1.0",
        "normalized_name": "Windows Ink Handwriting en-IN",
        "vendor": "Microsoft",
        "commercial_status": "Bundled/System",
        "license_model": "Windows language component",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Inno",
        "normalized_name": "Inno",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "Generic/obscure package"
    },
    {
        "raw_application": "Innoversion 6.5.4",
        "normalized_name": "Innoversion 6.5.4",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "Generic/obscure package"
    },
    {
        "raw_application": "InputApp_cw5n1h2txyewy",
        "normalized_name": "InputApp_cw5n1h2txyewy",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "Generic/obscure package"
    },
    {
        "raw_application": "Internet Download Manager",
        "normalized_name": "Internet Download Manager",
        "vendor": "Tonec Inc.",
        "commercial_status": "Commercial",
        "license_model": "Perpetual license/trial",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Paid after trial"
    },
    {
        "raw_application": "Iso Codes",
        "normalized_name": "Iso Codes",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "Generic/obscure package"
    },
    {
        "raw_application": "Iucode Tool",
        "normalized_name": "Iucode Tool",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "Generic/obscure package"
    },
    {
        "raw_application": "Ivanti Secure Access Client",
        "normalized_name": "Ivanti Secure Access Client",
        "vendor": "Ivanti",
        "commercial_status": "Enterprise",
        "license_model": "Enterprise subscription/contract",
        "availability": "Windows/macOS",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Java 8 Update 481",
        "normalized_name": "Java 8 Update 481",
        "vendor": "Oracle",
        "commercial_status": "Commercial/Free depending use",
        "license_model": "Oracle Java licensing terms",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": "Verify edition/use"
    },
    {
        "raw_application": "Java Auto Updater",
        "normalized_name": "Java Auto Updater",
        "vendor": "Oracle",
        "commercial_status": "Component",
        "license_model": "Parent Java installation",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Java(TM) SE Development Kit 22",
        "normalized_name": "Java(TM) SE Development Kit 22",
        "vendor": "Oracle",
        "commercial_status": "Free/Commercial depending distribution/use",
        "license_model": "JDK license terms",
        "availability": "Windows/macOS/Linux",
        "confidence": "MEDIUM",
        "notes": "Version separately"
    },
    {
        "raw_application": "Java(TM) SE Development Kit 25.0.2",
        "normalized_name": "Java(TM) SE Development Kit 25.0.2",
        "vendor": "Oracle",
        "commercial_status": "Free/Commercial depending distribution/use",
        "license_model": "JDK license terms",
        "availability": "Windows/macOS/Linux",
        "confidence": "MEDIUM",
        "notes": "Version separately"
    },
    {
        "raw_application": "JSON XML Editor",
        "normalized_name": "JSON XML Editor",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "Generic/obscure package"
    },
    {
        "raw_application": "ksystemsharehost_kbyyjmwk2spaw",
        "normalized_name": "ksystemsharehost_kbyyjmwk2spaw",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "Generic/obscure package"
    },
    {
        "raw_application": "LinkedIn",
        "normalized_name": "LinkedIn",
        "vendor": "Microsoft",
        "commercial_status": "Freemium",
        "license_model": "Free + Premium subscription",
        "availability": "Web/Mobile",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Logitech Options",
        "normalized_name": "Logitech Options",
        "vendor": "Logitech",
        "commercial_status": "Free",
        "license_model": "Hardware utility",
        "availability": "Windows/macOS",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "ManageEngine UEMS - Agent",
        "normalized_name": "ManageEngine Endpoint Central / UEMS Agent",
        "vendor": "ManageEngine (Zoho)",
        "commercial_status": "Enterprise",
        "license_model": "Endpoint management subscription/license",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "McAfee Security Scan Plus",
        "normalized_name": "McAfee Security Scan Plus",
        "vendor": "McAfee",
        "commercial_status": "Free utility",
        "license_model": "Proprietary freeware",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "McAfeeWPSSparse_0j6k21vdgrmfw",
        "normalized_name": "McAfee Windows Package Component",
        "vendor": "McAfee",
        "commercial_status": "Component",
        "license_model": "Parent security product license",
        "availability": "Windows",
        "confidence": "LOW",
        "notes": "Package identifier"
    },
    {
        "raw_application": "McAfeeWPSSparse_1ez856j3kr9ae",
        "normalized_name": "McAfee Windows Package Component",
        "vendor": "McAfee",
        "commercial_status": "Component",
        "license_model": "Parent security product license",
        "availability": "Windows",
        "confidence": "LOW",
        "notes": "Package identifier"
    },
    {
        "raw_application": "Mem Reduct",
        "normalized_name": "Mem Reduct",
        "vendor": "Henry++",
        "commercial_status": "Free",
        "license_model": "Open-source/freeware",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Menulet",
        "normalized_name": "Menulet",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "Generic/obscure package"
    },
    {
        "raw_application": "Microcode",
        "normalized_name": "Microcode",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "Generic/obscure package"
    },
    {
        "raw_application": "MirametrixInc.GlancebyMirametrix_17mer8kcn3j54",
        "normalized_name": "Glance by Mirametrix",
        "vendor": "Mirametrix",
        "commercial_status": "OEM/Enterprise",
        "license_model": "OEM/device software",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Mixed Reality Portal",
        "normalized_name": "Mixed Reality Portal",
        "vendor": "Microsoft",
        "commercial_status": "Free/Bundled",
        "license_model": "Windows app",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Mozilla Firefoxen-GB)",
        "normalized_name": "Mozilla Firefox",
        "vendor": "Mozilla",
        "commercial_status": "Free",
        "license_model": "Open-source (MPL)",
        "availability": "Windows/macOS/Linux",
        "confidence": "HIGH",
        "notes": "Normalize malformed locale"
    },
    {
        "raw_application": "Mozilla Maintenance Service",
        "normalized_name": "Mozilla Maintenance Service",
        "vendor": "Mozilla",
        "commercial_status": "Component",
        "license_model": "Parent Firefox installation",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "MPEG-2 Video Extension",
        "normalized_name": "MPEG-2 Video Extension",
        "vendor": "Microsoft",
        "commercial_status": "Free/Bundled",
        "license_model": "Codec extension",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "MTOP Client",
        "normalized_name": "MTOP Client",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "Generic/obscure package"
    },
    {
        "raw_application": "Naarad Agent",
        "normalized_name": "Naarad Agent",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "Generic/obscure package"
    },
    {
        "raw_application": "Naarad Collector version 1.0",
        "normalized_name": "Naarad Collector version 1.0",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "Generic/obscure package"
    },
    {
        "raw_application": "Nahimic",
        "normalized_name": "Nahimic",
        "vendor": "A-Volute",
        "commercial_status": "OEM/Bundled",
        "license_model": "OEM driver/utility",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "NcsiUwpApp_8wekyb3d8bbwe",
        "normalized_name": "Network Connectivity Status Indicator App",
        "vendor": "Microsoft",
        "commercial_status": "Bundled/System",
        "license_model": "Windows component",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": ""
    },
    {
        "raw_application": "Netflix",
        "normalized_name": "Netflix",
        "vendor": "Netflix",
        "commercial_status": "Subscription service",
        "license_model": "Subscription",
        "availability": "Web/Windows/Mobile",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Netskope Client",
        "normalized_name": "Netskope Client",
        "vendor": "Netskope",
        "commercial_status": "Enterprise",
        "license_model": "Enterprise subscription",
        "availability": "Windows/macOS",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "ngrok",
        "normalized_name": "ngrok",
        "vendor": "ngrok",
        "commercial_status": "Freemium",
        "license_model": "Free + paid subscription",
        "availability": "Windows/macOS/Linux",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Nmap 7.97",
        "normalized_name": "Nmap",
        "vendor": "Nmap Project",
        "commercial_status": "Free",
        "license_model": "Open-source license",
        "availability": "Windows/Linux/macOS",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "NotepadPlusPlus_2247w0b46hfww",
        "normalized_name": "Notepad++",
        "vendor": "Don Ho / Notepad++",
        "commercial_status": "Free",
        "license_model": "GPL/Open source",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize duplicate package"
    },
    {
        "raw_application": "NotepadPlusPlus_7njy0v32s6xk6",
        "normalized_name": "Notepad++",
        "vendor": "Don Ho / Notepad++",
        "commercial_status": "Free",
        "license_model": "GPL/Open source",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize duplicate package"
    },
    {
        "raw_application": "Npcap",
        "normalized_name": "Npcap",
        "vendor": "Nmap Project",
        "commercial_status": "Free/Commercial OEM options",
        "license_model": "Free for qualifying use; OEM licensing available",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "NVIDIA Backend",
        "normalized_name": "NVIDIA Backend",
        "vendor": "NVIDIA",
        "commercial_status": "Component/Bundled",
        "license_model": "Parent NVIDIA driver/software license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize under NVIDIA software stack"
    },
    {
        "raw_application": "NVIDIA Container",
        "normalized_name": "NVIDIA Container",
        "vendor": "NVIDIA",
        "commercial_status": "Component/Bundled",
        "license_model": "Parent NVIDIA driver/software license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize under NVIDIA software stack"
    },
    {
        "raw_application": "NVIDIA FrameView SDK 1.2.7521.31103277",
        "normalized_name": "NVIDIA FrameView SDK 1.2.7521.31103277",
        "vendor": "NVIDIA",
        "commercial_status": "Component/Bundled",
        "license_model": "Parent NVIDIA driver/software license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize under NVIDIA software stack"
    },
    {
        "raw_application": "NVIDIA GeForce Experience 3.25.1.27",
        "normalized_name": "NVIDIA GeForce Experience",
        "vendor": "NVIDIA",
        "commercial_status": "Free",
        "license_model": "Proprietary freeware",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Legacy product naming"
    },
    {
        "raw_application": "NVIDIA GPX Common OSS binaries (POCO, OpenSSL, libprotobuf)",
        "normalized_name": "NVIDIA GPX Common OSS binaries (POCO, OpenSSL, libprotobuf)",
        "vendor": "NVIDIA",
        "commercial_status": "Component/Bundled",
        "license_model": "Parent NVIDIA driver/software license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize under NVIDIA software stack"
    },
    {
        "raw_application": "NVIDIA Graphics Driver",
        "normalized_name": "NVIDIA Graphics Driver",
        "vendor": "NVIDIA",
        "commercial_status": "Free/OEM",
        "license_model": "Hardware driver",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Parent: NVIDIA Driver Stack"
    },
    {
        "raw_application": "NVIDIA Install Application",
        "normalized_name": "NVIDIA Install Application",
        "vendor": "NVIDIA",
        "commercial_status": "Component/Bundled",
        "license_model": "Parent NVIDIA driver/software license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize under NVIDIA software stack"
    },
    {
        "raw_application": "NVIDIA LocalSystem Container",
        "normalized_name": "NVIDIA LocalSystem Container",
        "vendor": "NVIDIA",
        "commercial_status": "Component/Bundled",
        "license_model": "Parent NVIDIA driver/software license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize under NVIDIA software stack"
    },
    {
        "raw_application": "NVIDIA Message Bus for NvContainer",
        "normalized_name": "NVIDIA Message Bus for NvContainer",
        "vendor": "NVIDIA",
        "commercial_status": "Component/Bundled",
        "license_model": "Parent NVIDIA driver/software license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize under NVIDIA software stack"
    },
    {
        "raw_application": "NVIDIA NetworkService Container",
        "normalized_name": "NVIDIA NetworkService Container",
        "vendor": "NVIDIA",
        "commercial_status": "Component/Bundled",
        "license_model": "Parent NVIDIA driver/software license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize under NVIDIA software stack"
    },
    {
        "raw_application": "NVIDIA NVAPI Monitor plugin for NvContainer",
        "normalized_name": "NVIDIA NVAPI Monitor plugin for NvContainer",
        "vendor": "NVIDIA",
        "commercial_status": "Component/Bundled",
        "license_model": "Parent NVIDIA driver/software license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize under NVIDIA software stack"
    },
    {
        "raw_application": "NVIDIA PhysX System Software 9.21.0713",
        "normalized_name": "NVIDIA PhysX System Software",
        "vendor": "NVIDIA",
        "commercial_status": "Free/Bundled",
        "license_model": "Runtime component",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "NVIDIA Platform Controllers and Framework",
        "normalized_name": "NVIDIA Platform Controllers and Framework",
        "vendor": "NVIDIA",
        "commercial_status": "Component/Bundled",
        "license_model": "Parent NVIDIA driver/software license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize under NVIDIA software stack"
    },
    {
        "raw_application": "NVIDIA Session Container",
        "normalized_name": "NVIDIA Session Container",
        "vendor": "NVIDIA",
        "commercial_status": "Component/Bundled",
        "license_model": "Parent NVIDIA driver/software license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize under NVIDIA software stack"
    },
    {
        "raw_application": "NVIDIA ShadowPlay 3.25.1.27",
        "normalized_name": "NVIDIA ShadowPlay 3.25.1.27",
        "vendor": "NVIDIA",
        "commercial_status": "Component/Bundled",
        "license_model": "Parent NVIDIA driver/software license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize under NVIDIA software stack"
    },
    {
        "raw_application": "Nvidia Share",
        "normalized_name": "Nvidia Share",
        "vendor": "NVIDIA",
        "commercial_status": "Component/Bundled",
        "license_model": "Parent NVIDIA driver/software license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize under NVIDIA software stack"
    },
    {
        "raw_application": "NVIDIA SHIELD Streaming",
        "normalized_name": "NVIDIA SHIELD Streaming",
        "vendor": "NVIDIA",
        "commercial_status": "Component/Bundled",
        "license_model": "Parent NVIDIA driver/software license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize under NVIDIA software stack"
    },
    {
        "raw_application": "NVIDIA SHIELD Wireless Controller Driver",
        "normalized_name": "NVIDIA SHIELD Wireless Controller Driver",
        "vendor": "NVIDIA",
        "commercial_status": "Component/Bundled",
        "license_model": "Parent NVIDIA driver/software license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize under NVIDIA software stack"
    },
    {
        "raw_application": "NVIDIA Telemetry Client",
        "normalized_name": "NVIDIA Telemetry Client",
        "vendor": "NVIDIA",
        "commercial_status": "Component/Bundled",
        "license_model": "Parent NVIDIA driver/software license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize under NVIDIA software stack"
    },
    {
        "raw_application": "NVIDIA TelemetryApi helper for NvContainer",
        "normalized_name": "NVIDIA TelemetryApi helper for NvContainer",
        "vendor": "NVIDIA",
        "commercial_status": "Component/Bundled",
        "license_model": "Parent NVIDIA driver/software license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize under NVIDIA software stack"
    },
    {
        "raw_application": "NVIDIA User Container",
        "normalized_name": "NVIDIA User Container",
        "vendor": "NVIDIA",
        "commercial_status": "Component/Bundled",
        "license_model": "Parent NVIDIA driver/software license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize under NVIDIA software stack"
    },
    {
        "raw_application": "NVIDIA Virtual Audio 4.39.0.0",
        "normalized_name": "NVIDIA Virtual Audio 4.39.0.0",
        "vendor": "NVIDIA",
        "commercial_status": "Component/Bundled",
        "license_model": "Parent NVIDIA driver/software license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize under NVIDIA software stack"
    },
    {
        "raw_application": "NVIDIA Virtual Host Controller",
        "normalized_name": "NVIDIA Virtual Host Controller",
        "vendor": "NVIDIA",
        "commercial_status": "Component/Bundled",
        "license_model": "Parent NVIDIA driver/software license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize under NVIDIA software stack"
    },
    {
        "raw_application": "NVIDIA Watchdog Plugin for NvContainer",
        "normalized_name": "NVIDIA Watchdog Plugin for NvContainer",
        "vendor": "NVIDIA",
        "commercial_status": "Component/Bundled",
        "license_model": "Parent NVIDIA driver/software license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize under NVIDIA software stack"
    },
    {
        "raw_application": "NVIDIACorp.NVIDIAControlPanel_56jybvy8sckqj",
        "normalized_name": "NVIDIA Control Panel",
        "vendor": "NVIDIA",
        "commercial_status": "Free/Bundled",
        "license_model": "Driver companion",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "NvModuleTracker",
        "normalized_name": "NvModuleTracker",
        "vendor": "NVIDIA",
        "commercial_status": "Component/Bundled",
        "license_model": "Parent NVIDIA driver/software license",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize under NVIDIA software stack"
    },
    {
        "raw_application": "OBS Studio",
        "normalized_name": "OBS Studio",
        "vendor": "OBS Project",
        "commercial_status": "Free",
        "license_model": "Open-source (GPL)",
        "availability": "Windows/macOS/Linux",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Ollama",
        "normalized_name": "Ollama",
        "vendor": "Ollama",
        "commercial_status": "Free",
        "license_model": "Open-source software",
        "availability": "Windows/macOS/Linux",
        "confidence": "HIGH",
        "notes": "Normalize version separately"
    },
    {
        "raw_application": "Ollama version 0.21.0",
        "normalized_name": "Ollama",
        "vendor": "Ollama",
        "commercial_status": "Free",
        "license_model": "Open-source software",
        "availability": "Windows/macOS/Linux",
        "confidence": "HIGH",
        "notes": "Normalize version separately"
    },
    {
        "raw_application": "Omnissa Horizon Client",
        "normalized_name": "Omnissa Horizon Client",
        "vendor": "Omnissa",
        "commercial_status": "Free client / Enterprise backend",
        "license_model": "Enterprise VDI licensing",
        "availability": "Windows/macOS/Linux",
        "confidence": "HIGH",
        "notes": ""
    },

    # ------------------ PART 3 ------------------
    {
        "raw_application": "Omnissa Workspace ONE Experience Management",
        "normalized_name": "Omnissa Workspace ONE Experience Management",
        "vendor": "Omnissa",
        "commercial_status": "Enterprise",
        "license_model": "Enterprise subscription/contract",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Online Plug-in",
        "normalized_name": "Online Plug-in",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "Generic component"
    },
    {
        "raw_application": "OpenSSL 3.6.0",
        "normalized_name": "OpenSSL",
        "vendor": "OpenSSL Software Foundation / community",
        "commercial_status": "Free",
        "license_model": "Open-source license",
        "availability": "Cross-platform",
        "confidence": "HIGH",
        "notes": "Normalize versions; verify 'Light' package"
    },
    {
        "raw_application": "OpenSSL 3.6.1 Light",
        "normalized_name": "OpenSSL",
        "vendor": "OpenSSL Software Foundation / community",
        "commercial_status": "Free",
        "license_model": "Open-source license",
        "availability": "Cross-platform",
        "confidence": "HIGH",
        "notes": "Normalize versions; verify 'Light' package"
    },
    {
        "raw_application": "Opera GX Stable 129.0.5823.70",
        "normalized_name": "Opera GX",
        "vendor": "Opera",
        "commercial_status": "Free",
        "license_model": "Proprietary freeware",
        "availability": "Windows/macOS",
        "confidence": "HIGH",
        "notes": "Version separately"
    },
    {
        "raw_application": "Opera Stable 126.0.5750.18",
        "normalized_name": "Opera",
        "vendor": "Opera",
        "commercial_status": "Free",
        "license_model": "Proprietary freeware",
        "availability": "Windows/macOS/Linux",
        "confidence": "HIGH",
        "notes": "Version separately"
    },
    {
        "raw_application": "Oracle VirtualBox",
        "normalized_name": "Oracle VirtualBox",
        "vendor": "Oracle",
        "commercial_status": "Free/Open Source + Extension licensing",
        "license_model": "GPL core; extension pack separate terms",
        "availability": "Windows/macOS/Linux",
        "confidence": "HIGH",
        "notes": "Normalize beta/version"
    },
    {
        "raw_application": "Oracle VirtualBox 7.1.0_BETA1",
        "normalized_name": "Oracle VirtualBox",
        "vendor": "Oracle",
        "commercial_status": "Free/Open Source + Extension licensing",
        "license_model": "GPL core; extension pack separate terms",
        "availability": "Windows/macOS/Linux",
        "confidence": "HIGH",
        "notes": "Normalize beta/version"
    },
    {
        "raw_application": "outlook.office.com-4D813D4_akxy2sb7nnr06",
        "normalized_name": "Outlook on the Web",
        "vendor": "Microsoft",
        "commercial_status": "Enterprise/Freemium",
        "license_model": "Microsoft 365 / organizational subscription",
        "availability": "Web/PWA",
        "confidence": "HIGH",
        "notes": "Duplicate PWA entries"
    },
    {
        "raw_application": "outlook.office.com-F53E19B5_akxy2sb7nnr06",
        "normalized_name": "Outlook on the Web",
        "vendor": "Microsoft",
        "commercial_status": "Enterprise/Freemium",
        "license_model": "Microsoft 365 / organizational subscription",
        "availability": "Web/PWA",
        "confidence": "HIGH",
        "notes": "Duplicate PWA entries"
    },
    {
        "raw_application": "partners.snowsoftware.com-53AEF297_6p2hnrv1vsa8c",
        "normalized_name": "Snow Software Partner Portal",
        "vendor": "Snow Software / Flexera ecosystem",
        "commercial_status": "Enterprise web portal",
        "license_model": "Organization subscription/contract",
        "availability": "Web",
        "confidence": "MEDIUM",
        "notes": "PWA entry"
    },
    {
        "raw_application": "PawnIO",
        "normalized_name": "PawnIO",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "Generic/obscure entry"
    },
    {
        "raw_application": "Perplexity 1.1.3",
        "normalized_name": "Perplexity",
        "vendor": "Perplexity AI",
        "commercial_status": "Freemium",
        "license_model": "Free + subscription tiers",
        "availability": "Web/Desktop",
        "confidence": "HIGH",
        "notes": "Version separately"
    },
    {
        "raw_application": "Phone Link",
        "normalized_name": "Phone Link",
        "vendor": "Microsoft",
        "commercial_status": "Free/Bundled",
        "license_model": "Windows application",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "pmodule",
        "normalized_name": "pmodule",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "Generic/obscure entry"
    },
    {
        "raw_application": "PostgreSQL",
        "normalized_name": "PostgreSQL",
        "vendor": "PostgreSQL Global Development Group",
        "commercial_status": "Free",
        "license_model": "PostgreSQL License / open source",
        "availability": "Windows/Linux/macOS",
        "confidence": "HIGH",
        "notes": "Normalize major versions separately"
    },
    {
        "raw_application": "PostgreSQL 17",
        "normalized_name": "PostgreSQL",
        "vendor": "PostgreSQL Global Development Group",
        "commercial_status": "Free",
        "license_model": "PostgreSQL License / open source",
        "availability": "Windows/Linux/macOS",
        "confidence": "HIGH",
        "notes": "Normalize major versions separately"
    },
    {
        "raw_application": "PostgreSQL 18",
        "normalized_name": "PostgreSQL",
        "vendor": "PostgreSQL Global Development Group",
        "commercial_status": "Free",
        "license_model": "PostgreSQL License / open source",
        "availability": "Windows/Linux/macOS",
        "confidence": "HIGH",
        "notes": "Normalize major versions separately"
    },
    {
        "raw_application": "Psiphon 3.167",
        "normalized_name": "Psiphon",
        "vendor": "Psiphon Inc.",
        "commercial_status": "Free",
        "license_model": "Free service/software",
        "availability": "Windows/Mobile",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "PsychoPy",
        "normalized_name": "PsychoPy",
        "vendor": "Open Science Tools",
        "commercial_status": "Free",
        "license_model": "Open-source license",
        "availability": "Windows/macOS/Linux",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Pulse SecureClient",
        "normalized_name": "Pulse Secure Client",
        "vendor": "Ivanti / Pulse Secure",
        "commercial_status": "Enterprise",
        "license_model": "Enterprise VPN licensing/environment",
        "availability": "Windows/macOS",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "PulseSecureReactAppPkg_8sxk7jj79atge",
        "normalized_name": "Pulse Secure Client Component",
        "vendor": "Ivanti / Pulse Secure",
        "commercial_status": "Component",
        "license_model": "Parent enterprise product",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": "Package identifier"
    },
    {
        "raw_application": "qBittorrent",
        "normalized_name": "qBittorrent",
        "vendor": "qBittorrent Project",
        "commercial_status": "Free",
        "license_model": "Open-source (GPL)",
        "availability": "Windows/Linux/macOS",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "QurioV3 3.3.57",
        "normalized_name": "QurioV3",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": ""
    },
    {
        "raw_application": "Raw Image Extension",
        "normalized_name": "Raw Image Extension",
        "vendor": "Microsoft",
        "commercial_status": "Free",
        "license_model": "Store/system extension",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "ReaderNotificationClient_e1rzdqpraam7r",
        "normalized_name": "Reader Notification Client",
        "vendor": "Unknown / likely Adobe",
        "commercial_status": "Component",
        "license_model": "Parent product dependent",
        "availability": "Windows",
        "confidence": "LOW",
        "notes": "Package identifier"
    },
    {
        "raw_application": "Recursive File Processing Droplet",
        "normalized_name": "Recursive File Processing Droplet",
        "vendor": "Apple",
        "commercial_status": "Bundled",
        "license_model": "macOS Automator/AppleScript component",
        "availability": "macOS",
        "confidence": "MEDIUM",
        "notes": ""
    },
    {
        "raw_application": "Recursive Image File Processing Droplet",
        "normalized_name": "Recursive Image File Processing Droplet",
        "vendor": "Apple",
        "commercial_status": "Bundled",
        "license_model": "macOS Automator/AppleScript component",
        "availability": "macOS",
        "confidence": "MEDIUM",
        "notes": ""
    },
    {
        "raw_application": "Remote_PC_IBL_Delivery_Group",
        "normalized_name": "Remote_PC_IBL_Delivery_Group",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "Generic/obscure entry"
    },
    {
        "raw_application": "Runner",
        "normalized_name": "Runner",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "Generic/obscure entry"
    },
    {
        "raw_application": "RVTools",
        "normalized_name": "RVTools",
        "vendor": "Robware",
        "commercial_status": "Free",
        "license_model": "Freeware",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "VMware environment inventory tool"
    },
    {
        "raw_application": "Sam Agent",
        "normalized_name": "SAM Agent",
        "vendor": "Unknown",
        "commercial_status": "Enterprise/Unknown",
        "license_model": "Manual verification required",
        "availability": "Enterprise",
        "confidence": "LOW",
        "notes": "Possible software asset management agent"
    },
    {
        "raw_application": "sam-agent",
        "normalized_name": "SAM Agent",
        "vendor": "Unknown",
        "commercial_status": "Enterprise/Unknown",
        "license_model": "Manual verification required",
        "availability": "Enterprise",
        "confidence": "LOW",
        "notes": "Possible software asset management agent"
    },
    {
        "raw_application": "SAMSUNGELECTRONICSCO.LTD.SamsungPrinterExperience_3c1yjt4zspk6g",
        "normalized_name": "Samsung Printer Experience",
        "vendor": "Samsung",
        "commercial_status": "Free/OEM",
        "license_model": "Printer utility/driver",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Scan To",
        "normalized_name": "Scan To",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "Generic/obscure entry"
    },
    {
        "raw_application": "Screen Recorder Launcher (JRE14)",
        "normalized_name": "Screen Recorder Launcher",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Windows",
        "confidence": "LOW",
        "notes": "JRE component"
    },
    {
        "raw_application": "Self-service Plug-in",
        "normalized_name": "Self-service Plug-in",
        "vendor": "Unknown",
        "commercial_status": "Component",
        "license_model": "Parent enterprise product",
        "availability": "Enterprise",
        "confidence": "LOW",
        "notes": ""
    },
    {
        "raw_application": "ServiceNow_MID_Server_midserver2026",
        "normalized_name": "ServiceNow MID Server",
        "vendor": "ServiceNow",
        "commercial_status": "Enterprise",
        "license_model": "ServiceNow subscription environment",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Sheets",
        "normalized_name": "Sheets",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "Generic/obscure entry"
    },
    {
        "raw_application": "silverleafsolutions-my.sharepoint.com-A1E6D3D9_z01228t7enddc",
        "normalized_name": "SharePoint Online Site",
        "vendor": "Microsoft / Organization-managed",
        "commercial_status": "Enterprise web app",
        "license_model": "Microsoft 365 organizational subscription",
        "availability": "Web/PWA",
        "confidence": "MEDIUM",
        "notes": ""
    },
    {
        "raw_application": "Slack",
        "normalized_name": "Slack",
        "vendor": "Slack Technologies / Salesforce",
        "commercial_status": "Freemium",
        "license_model": "Free + paid subscription",
        "availability": "Windows/macOS/Web",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Slides",
        "normalized_name": "Google Slides",
        "vendor": "Google",
        "commercial_status": "Freemium",
        "license_model": "Free + Google Workspace subscription",
        "availability": "Web",
        "confidence": "MEDIUM",
        "notes": "Web/PWA"
    },
    {
        "raw_application": "Snipping Tool",
        "normalized_name": "Snipping Tool",
        "vendor": "Microsoft",
        "commercial_status": "Free/Bundled",
        "license_model": "Windows app",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Snow Inventory Agent",
        "normalized_name": "Snow Inventory Agent",
        "vendor": "Snow Software / Flexera",
        "commercial_status": "Enterprise",
        "license_model": "Software asset management contract/license",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Snow Inventory Server",
        "normalized_name": "Snow Inventory Server",
        "vendor": "Snow Software / Flexera",
        "commercial_status": "Enterprise",
        "license_model": "Software asset management contract/license",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Sophos Connect",
        "normalized_name": "Sophos Connect",
        "vendor": "Sophos",
        "commercial_status": "Enterprise",
        "license_model": "Sophos subscription/license environment",
        "availability": "Windows/macOS",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "StataSE",
        "normalized_name": "Stata SE",
        "vendor": "StataCorp",
        "commercial_status": "Commercial",
        "license_model": "Perpetual or subscription license",
        "availability": "Windows/macOS/Linux",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Symbiosis Assessments 1.0.12",
        "normalized_name": "Symbiosis Assessments",
        "vendor": "Symbiosis / Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Windows",
        "confidence": "LOW",
        "notes": ""
    },
    {
        "raw_application": "SynapticsIncorporated.241916F58D6E7_807d65c4rvak2",
        "normalized_name": "Synaptics Touchpad/Control Panel",
        "vendor": "Synaptics",
        "commercial_status": "OEM/Bundled",
        "license_model": "Hardware driver/OEM component",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize package variants"
    },
    {
        "raw_application": "SynapticsIncorporated.SynapticsControlPanel_807d65c4rvak2",
        "normalized_name": "Synaptics Touchpad/Control Panel",
        "vendor": "Synaptics",
        "commercial_status": "OEM/Bundled",
        "license_model": "Hardware driver/OEM component",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize package variants"
    },
    {
        "raw_application": "TeamViewer 12",
        "normalized_name": "TeamViewer",
        "vendor": "TeamViewer",
        "commercial_status": "Free for personal use / Commercial",
        "license_model": "Subscription/commercial license",
        "availability": "Windows/macOS/Linux",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Tenable Nessus",
        "normalized_name": "Tenable Nessus",
        "vendor": "Tenable",
        "commercial_status": "Freemium/Commercial",
        "license_model": "Essentials free tier + Professional subscription",
        "availability": "Windows/Linux/macOS",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Tftpd64Edition (remove only)",
        "normalized_name": "Tftpd64",
        "vendor": "Tftpd64 Project / Philippe Jounin",
        "commercial_status": "Free",
        "license_model": "Freeware",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Trellix Agent",
        "normalized_name": "Trellix Agent",
        "vendor": "Trellix",
        "commercial_status": "Enterprise security component",
        "license_model": "Enterprise subscription/license",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": "Normalize under Trellix security suite"
    },
    {
        "raw_application": "Trellix Agent Status Monitor",
        "normalized_name": "Trellix Agent Status Monitor",
        "vendor": "Trellix",
        "commercial_status": "Enterprise security component",
        "license_model": "Enterprise subscription/license",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": "Normalize under Trellix security suite"
    },
    {
        "raw_application": "Trellix Data Exchange Layer for TA",
        "normalized_name": "Trellix Data Exchange Layer for TA",
        "vendor": "Trellix",
        "commercial_status": "Enterprise security component",
        "license_model": "Enterprise subscription/license",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": "Normalize under Trellix security suite"
    },
    {
        "raw_application": "Trellix Data Loss Prevention - Endpoint",
        "normalized_name": "Trellix Data Loss Prevention - Endpoint",
        "vendor": "Trellix",
        "commercial_status": "Enterprise security component",
        "license_model": "Enterprise subscription/license",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": "Normalize under Trellix security suite"
    },
    {
        "raw_application": "Trellix EDR Client",
        "normalized_name": "Trellix EDR Client",
        "vendor": "Trellix",
        "commercial_status": "Enterprise security component",
        "license_model": "Enterprise subscription/license",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": "Normalize under Trellix security suite"
    },
    {
        "raw_application": "Trellix EDR with Forensics",
        "normalized_name": "Trellix EDR with Forensics",
        "vendor": "Trellix",
        "commercial_status": "Enterprise security component",
        "license_model": "Enterprise subscription/license",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": "Normalize under Trellix security suite"
    },
    {
        "raw_application": "Trellix Endpoint Detection and Response",
        "normalized_name": "Trellix Endpoint Detection and Response",
        "vendor": "Trellix",
        "commercial_status": "Enterprise security component",
        "license_model": "Enterprise subscription/license",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": "Normalize under Trellix security suite"
    },
    {
        "raw_application": "Trellix Endpoint Security Adaptive Threat Protection",
        "normalized_name": "Trellix Endpoint Security Adaptive Threat Protection",
        "vendor": "Trellix",
        "commercial_status": "Enterprise security component",
        "license_model": "Enterprise subscription/license",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": "Normalize under Trellix security suite"
    },
    {
        "raw_application": "Trellix Endpoint Security Firewall",
        "normalized_name": "Trellix Endpoint Security Firewall",
        "vendor": "Trellix",
        "commercial_status": "Enterprise security component",
        "license_model": "Enterprise subscription/license",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": "Normalize under Trellix security suite"
    },
    {
        "raw_application": "Trellix Endpoint Security Platform",
        "normalized_name": "Trellix Endpoint Security Platform",
        "vendor": "Trellix",
        "commercial_status": "Enterprise security component",
        "license_model": "Enterprise subscription/license",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": "Normalize under Trellix security suite"
    },
    {
        "raw_application": "Trellix Endpoint Security Threat Prevention",
        "normalized_name": "Trellix Endpoint Security Threat Prevention",
        "vendor": "Trellix",
        "commercial_status": "Enterprise security component",
        "license_model": "Enterprise subscription/license",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": "Normalize under Trellix security suite"
    },
    {
        "raw_application": "Trellix Endpoint Security Web Control",
        "normalized_name": "Trellix Endpoint Security Web Control",
        "vendor": "Trellix",
        "commercial_status": "Enterprise security component",
        "license_model": "Enterprise subscription/license",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": "Normalize under Trellix security suite"
    },
    {
        "raw_application": "Trellix File and Removable Media Protection",
        "normalized_name": "Trellix File and Removable Media Protection",
        "vendor": "Trellix",
        "commercial_status": "Enterprise security component",
        "license_model": "Enterprise subscription/license",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": "Normalize under Trellix security suite"
    },
    {
        "raw_application": "Trellix Reporter",
        "normalized_name": "Trellix Reporter",
        "vendor": "Trellix",
        "commercial_status": "Enterprise security component",
        "license_model": "Enterprise subscription/license",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": "Normalize under Trellix security suite"
    },
    {
        "raw_application": "TrellixATP",
        "normalized_name": "TrellixATP",
        "vendor": "Trellix",
        "commercial_status": "Enterprise security component",
        "license_model": "Enterprise subscription/license",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": "Normalize under Trellix security suite"
    },
    {
        "raw_application": "TrellixSafariHost",
        "normalized_name": "TrellixSafariHost",
        "vendor": "Trellix",
        "commercial_status": "Enterprise security component",
        "license_model": "Enterprise subscription/license",
        "availability": "Enterprise",
        "confidence": "HIGH",
        "notes": "Normalize under Trellix security suite"
    },
    {
        "raw_application": "UltraViewer",
        "normalized_name": "UltraViewer",
        "vendor": "UltraViewer",
        "commercial_status": "Free/Freemium",
        "license_model": "Freeware / commercial terms verify",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize version"
    },
    {
        "raw_application": "UltraViewer version 6.6.113",
        "normalized_name": "UltraViewer",
        "vendor": "UltraViewer",
        "commercial_status": "Free/Freemium",
        "license_model": "Freeware / commercial terms verify",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize version"
    },
    {
        "raw_application": "USBPcap 1.5.4.0",
        "normalized_name": "USBPcap",
        "vendor": "Open-source community",
        "commercial_status": "Free",
        "license_model": "Open-source",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "UTM",
        "normalized_name": "UTM",
        "vendor": "Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Unknown",
        "confidence": "LOW",
        "notes": "Generic/obscure entry"
    },
    {
        "raw_application": "uTorrent Web",
        "normalized_name": "µTorrent Web",
        "vendor": "BitTorrent Inc.",
        "commercial_status": "Freemium",
        "license_model": "Free + premium",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize Unicode variant"
    },
    {
        "raw_application": "v1-7-0--edge-utils",
        "normalized_name": "Edge Utils",
        "vendor": "Microsoft / Unknown",
        "commercial_status": "Unknown",
        "license_model": "Manual verification required",
        "availability": "Windows",
        "confidence": "LOW",
        "notes": ""
    },
    {
        "raw_application": "vercel.com-9D24E357_gvgg1jnfbpbmg",
        "normalized_name": "Vercel",
        "vendor": "Vercel",
        "commercial_status": "Freemium",
        "license_model": "Free + paid plans",
        "availability": "Web/PWA",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "VirtualBox",
        "normalized_name": "Oracle VirtualBox",
        "vendor": "Oracle",
        "commercial_status": "Free/Open Source + Extension licensing",
        "license_model": "GPL core; extension pack separate terms",
        "availability": "Windows/macOS/Linux",
        "confidence": "HIGH",
        "notes": "Normalize beta/version"
    },
    {
        "raw_application": "VMware Horizon Client",
        "normalized_name": "VMware Horizon Client",
        "vendor": "Omnissa",
        "commercial_status": "Free client / Enterprise backend",
        "license_model": "Enterprise VDI licensing",
        "availability": "Windows/macOS/Linux",
        "confidence": "HIGH",
        "notes": "Brand transitioned to Omnissa"
    },
    {
        "raw_application": "VMware Horizon HTML5 Multimedia Redirection Client",
        "normalized_name": "Horizon HTML5 Multimedia Redirection Client",
        "vendor": "Omnissa",
        "commercial_status": "Enterprise component",
        "license_model": "Enterprise VDI licensing",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "VMware Horizon Media Engine 15.0.0.0",
        "normalized_name": "Horizon Media Engine",
        "vendor": "Omnissa",
        "commercial_status": "Enterprise component",
        "license_model": "Enterprise VDI licensing",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "VMware Player",
        "normalized_name": "VMware Workstation Player",
        "vendor": "VMware / Broadcom",
        "commercial_status": "Free/Commercial depending current terms",
        "license_model": "Product licensing terms",
        "availability": "Windows/Linux",
        "confidence": "MEDIUM",
        "notes": "Verify edition/version"
    },
    {
        "raw_application": "VP9 Video Extensions",
        "normalized_name": "VP9 Video Extensions",
        "vendor": "Microsoft",
        "commercial_status": "Free",
        "license_model": "Codec extension",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "VShieldScanManager",
        "normalized_name": "VMware vShield Scan Manager",
        "vendor": "VMware / Broadcom",
        "commercial_status": "Enterprise component",
        "license_model": "Enterprise virtualization/security licensing",
        "availability": "Enterprise",
        "confidence": "MEDIUM",
        "notes": ""
    },
    {
        "raw_application": "WacomTechnologyCorp.157535B83C264_ss941bf8mfs8a",
        "normalized_name": "Wacom Device Component",
        "vendor": "Wacom",
        "commercial_status": "OEM/Bundled",
        "license_model": "Hardware driver/OEM component",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "WavesAudio.MaxxAudioProforDell2022_fh4rh281wavaa",
        "normalized_name": "Waves MaxxAudio Pro for Dell",
        "vendor": "Waves Audio / Dell",
        "commercial_status": "OEM/Bundled",
        "license_model": "OEM audio utility",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Web Media Extensions",
        "normalized_name": "Web Media Extensions",
        "vendor": "Microsoft",
        "commercial_status": "Free/Bundled",
        "license_model": "Windows codec extension",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "WebAdvisor by McAfee",
        "normalized_name": "WebAdvisor by McAfee",
        "vendor": "McAfee",
        "commercial_status": "Free/Component",
        "license_model": "Free security utility / bundled",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Webex VDI PluginEngine",
        "normalized_name": "Webex VDI Plugin Engine",
        "vendor": "Cisco",
        "commercial_status": "Enterprise component",
        "license_model": "Webex subscription/environment",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "WebP Image Extension",
        "normalized_name": "WebP Image Extension",
        "vendor": "Microsoft",
        "commercial_status": "Free",
        "license_model": "Image codec extension",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "WinZip 77.0",
        "normalized_name": "WinZip",
        "vendor": "Corel / Alludo",
        "commercial_status": "Commercial",
        "license_model": "Trial + perpetual/subscription options",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize shell extension"
    },
    {
        "raw_application": "WinZipComputing.ShellExtension_73e8yqadscyzp",
        "normalized_name": "WinZip",
        "vendor": "Corel / Alludo",
        "commercial_status": "Commercial",
        "license_model": "Trial + perpetual/subscription options",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize shell extension"
    },
    {
        "raw_application": "WiX Toolset v3.11 Core",
        "normalized_name": "WiX Toolset",
        "vendor": "FireGiant / WiX community",
        "commercial_status": "Free/Open Source",
        "license_model": "Open-source toolset",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize version"
    },
    {
        "raw_application": "WiX Toolset v3.11.2.4516",
        "normalized_name": "WiX Toolset",
        "vendor": "FireGiant / WiX community",
        "commercial_status": "Free/Open Source",
        "license_model": "Open-source toolset",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize version"
    },
    {
        "raw_application": "WPS Office (12.2.0.23196)",
        "normalized_name": "WPS Office",
        "vendor": "Kingsoft",
        "commercial_status": "Freemium",
        "license_model": "Free + subscription",
        "availability": "Windows/macOS/Linux",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "wpsappext1",
        "normalized_name": "WPS Office Application Extension",
        "vendor": "Kingsoft",
        "commercial_status": "Component",
        "license_model": "Parent WPS Office installation",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": "Normalize all extension variants"
    },
    {
        "raw_application": "wpsappext1_kbyyjmwk2spaw",
        "normalized_name": "WPS Office Application Extension",
        "vendor": "Kingsoft",
        "commercial_status": "Component",
        "license_model": "Parent WPS Office installation",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": "Normalize all extension variants"
    },
    {
        "raw_application": "wpsappext1_km9wtz8rh8me0",
        "normalized_name": "WPS Office Application Extension",
        "vendor": "Kingsoft",
        "commercial_status": "Component",
        "license_model": "Parent WPS Office installation",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": "Normalize all extension variants"
    },
    {
        "raw_application": "wpsappext2",
        "normalized_name": "WPS Office Application Extension",
        "vendor": "Kingsoft",
        "commercial_status": "Component",
        "license_model": "Parent WPS Office installation",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": "Normalize all extension variants"
    },
    {
        "raw_application": "wpsappext2_kbyyjmwk2spaw",
        "normalized_name": "WPS Office Application Extension",
        "vendor": "Kingsoft",
        "commercial_status": "Component",
        "license_model": "Parent WPS Office installation",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": "Normalize all extension variants"
    },
    {
        "raw_application": "wpsappext2_km9wtz8rh8me0",
        "normalized_name": "WPS Office Application Extension",
        "vendor": "Kingsoft",
        "commercial_status": "Component",
        "license_model": "Parent WPS Office installation",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": "Normalize all extension variants"
    },
    {
        "raw_application": "wpsappext3",
        "normalized_name": "WPS Office Application Extension",
        "vendor": "Kingsoft",
        "commercial_status": "Component",
        "license_model": "Parent WPS Office installation",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": "Normalize all extension variants"
    },
    {
        "raw_application": "wpsappext3_kbyyjmwk2spaw",
        "normalized_name": "WPS Office Application Extension",
        "vendor": "Kingsoft",
        "commercial_status": "Component",
        "license_model": "Parent WPS Office installation",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": "Normalize all extension variants"
    },
    {
        "raw_application": "wpsappext3_km9wtz8rh8me0",
        "normalized_name": "WPS Office Application Extension",
        "vendor": "Kingsoft",
        "commercial_status": "Component",
        "license_model": "Parent WPS Office installation",
        "availability": "Windows",
        "confidence": "MEDIUM",
        "notes": "Normalize all extension variants"
    },
    {
        "raw_application": "www.hoi.in-3F0FA331_d8dhr4crwahfc",
        "normalized_name": "HOI Web Application",
        "vendor": "Unknown / Organization-managed",
        "commercial_status": "Web app",
        "license_model": "Organization/service dependent",
        "availability": "Web/PWA",
        "confidence": "LOW",
        "notes": "Verify owner"
    },
    {
        "raw_application": "YouTube",
        "normalized_name": "YouTube",
        "vendor": "Google",
        "commercial_status": "Freemium",
        "license_model": "Free + Premium subscription",
        "availability": "Web/PWA",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "YouTube Music",
        "normalized_name": "YouTube Music",
        "vendor": "Google",
        "commercial_status": "Freemium",
        "license_model": "Free + Premium subscription",
        "availability": "Web/PWA",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "zCCIMeetingHost",
        "normalized_name": "Zoom Meeting Host Component",
        "vendor": "Zoom",
        "commercial_status": "Component",
        "license_model": "Parent Zoom service/application",
        "availability": "Windows",
        "confidence": "LOW",
        "notes": "Package identification recommended"
    },
    {
        "raw_application": "Zoho Mail - Desktop 1.7.4",
        "normalized_name": "Zoho Mail Desktop",
        "vendor": "Zoho",
        "commercial_status": "Freemium/Subscription",
        "license_model": "Free + business subscription",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Zoom VDI Plugin Management",
        "normalized_name": "Zoom VDI Plugin Management",
        "vendor": "Zoom",
        "commercial_status": "Enterprise component",
        "license_model": "Zoom subscription/environment",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "ZoomAutoUpdater",
        "normalized_name": "Zoom Auto Updater",
        "vendor": "Zoom",
        "commercial_status": "Component",
        "license_model": "Parent Zoom installation",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "ZoomClips",
        "normalized_name": "Zoom Clips",
        "vendor": "Zoom",
        "commercial_status": "Subscription feature",
        "license_model": "Zoom plan dependent",
        "availability": "Windows/Web",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "Zscaler",
        "normalized_name": "Zscaler Client Connector",
        "vendor": "Zscaler",
        "commercial_status": "Enterprise",
        "license_model": "Enterprise subscription",
        "availability": "Windows/macOS",
        "confidence": "HIGH",
        "notes": ""
    },
    {
        "raw_application": "µTorrent",
        "normalized_name": "µTorrent Web",
        "vendor": "BitTorrent Inc.",
        "commercial_status": "Freemium",
        "license_model": "Free + premium",
        "availability": "Windows",
        "confidence": "HIGH",
        "notes": "Normalize Unicode variant"
    },
]


def map_commercial_status(status_str: str, license_model: str) -> str:
    """Map the report's commercial status text to standard database enum string."""
    s = (status_str or "").strip().lower()
    lm = (license_model or "").lower()

    if any(k in s for k in ["commercial enterprise", "enterprise/commercial", "commercial/enterprise", "enterprise", "commercial", "subscription service", "subscription feature"]):
        return "COMMERCIAL"
    if any(k in s for k in ["freemium", "free-to-play", "free for personal use", "free/freemium", "free + subscription", "free client", "extension licensing", "commercial depending", "free/commercial", "commercial/free", "oem options"]):
        return "FREE_AND_PAID"
    if "component" in s or "plugin" in s:
        return "COMMERCIAL_COMPONENT"
    if "oem" in s:
        return "OEM_OR_BUNDLED"
    if any(k in s for k in ["bundled", "os component", "windows", "macos"]):
        return "OS_BUNDLED"
    if "web" in s or "portal" in s:
        return "WEB_SHORTCUT/PWA"
    if "open" in s or any(x in lm for x in ["gpl", "mpl", "open-source", "apache", "open source"]):
        return "OPEN_SOURCE"
    if any(k in s for k in ["free", "freeware", "free utility"]):
        return "FREEWARE"
    return "UNKNOWN"


def map_license_required(classification: str) -> str:
    if classification == "COMMERCIAL":
        return "YES"
    elif classification == "FREE_AND_PAID":
        return "CONTEXT_DEPENDENT"
    elif classification in ["OPEN_SOURCE", "FREEWARE", "OS_BUNDLED", "OEM_OR_BUNDLED", "COMMERCIAL_COMPONENT"]:
        return "NO"
    return "UNKNOWN"


def feed_data():
    db = SessionLocal()
    try:
        logger.info(f"Loaded {len(PDF_ENTRIES)} entries from the PDF normalization reports.")

        # Build fast lookup dictionary by raw application (case-insensitive and exact)
        entry_map: Dict[str, Dict[str, Any]] = {}
        for item in PDF_ENTRIES:
            raw = item["raw_application"].strip()
            item["classification"] = map_commercial_status(item["commercial_status"], item["license_model"])
            item["license_required"] = map_license_required(item["classification"])
            entry_map[raw] = item
            entry_map[raw.lower()] = item

        # Aliases / scan variations
        aliases_mapping = {
            "Ghostscript GPL 8.64 (Msi Setup)": "Ghostscript GPL 8.64 (Msi",
            "HP LaserJet Professional M1210 MFP Series Fax Installer": "HP LaserJet Professional M1210 MFP Series Fax",
            "Inno Setup": "Inno",
            "Inno Setup version 6.5.4": "Innoversion 6.5.4",
            "IIS Express Application Compatibility Database for x64": "IIS Express Application Compatibility Database for",
            "Java 8 Update 481 (64-bit)": "Java 8 Update 481",
            "Java(TM) SE Development Kit 22 (64-bit)": "Java(TM) SE Development Kit 22",
            "Java(TM) SE Development Kit 25.0.2 (64-bit)": "Java(TM) SE Development Kit 25.0.2",
            "Mozilla Firefox (x64 en-GB)": "Mozilla Firefoxen-GB)",
            "OpenSSL 3.6.0 (64-bit)": "OpenSSL 3.6.0",
            "OpenSSL 3.6.1 Light (64-bit)": "OpenSSL 3.6.1 Light",
            "Pulse Secure Setup Client": "Pulse SecureClient",
            "Tenable Nessus (x64)": "Tenable Nessus",
            "Tftpd64 Standalone Edition (remove only)": "Tftpd64Edition (remove only)",
            "deviceTRUST ICA Client Extension 2603 (x64)": "deviceTRUST ICA Client Extension 2603",
            "deviceTRUST ICA Client Extension v25.3 x64": "deviceTRUST ICA Client Extension v25.3",
            "deviceTRUST ICA Client Extension x64 2511": "deviceTRUST ICA Client Extension2511",
            "Zoom VDI Plugin Management(64bit)": "Zoom VDI Plugin Management",
            "calibre 64bit": "calibre",
            "Amd64 Microcode": "Microcode",
            "McAfeeWPSSparsePackage_0j6k21vdgrmfw": "McAfeeWPSSparse_0j6k21vdgrmfw",
            "McAfeeWPSSparsePackage_1ez856j3kr9ae": "McAfeeWPSSparse_1ez856j3kr9ae",
            "ksystemsharehostenUS_kbyyjmwk2spaw": "ksystemsharehost_kbyyjmwk2spaw",
            "VMware Horizon Media Engine 15.0.0.0 (64-bit)": "VMware Horizon Media Engine 15.0.0.0",
        }

        for alias, target in aliases_mapping.items():
            if target in entry_map:
                entry_map[alias] = entry_map[target]
                entry_map[alias.lower()] = entry_map[target]

        # Extra known package entries & specific resolution for all inventory items
        extra_exact_entries = {
            "Skyhigh Client Proxy": {
                "raw_application": "Skyhigh Client Proxy",
                "normalized_name": "Skyhigh Client Proxy",
                "vendor": "Musarubra US LLC",
                "commercial_status": "Enterprise",
                "license_model": "Enterprise subscription/license",
                "availability": "Windows",
                "confidence": "HIGH",
                "notes": "Enterprise security client",
                "classification": "COMMERCIAL",
                "license_required": "YES"
            },
            "AppleInc.AppleTVWin_nzyj5cx40ttqa": {
                "raw_application": "AppleInc.AppleTVWin_nzyj5cx40ttqa",
                "normalized_name": "Apple TV",
                "vendor": "Apple",
                "classification": "COMMERCIAL",
                "license_model": "Subscription / purchases",
                "availability": "Windows",
                "confidence": "HIGH",
                "license_required": "YES",
                "notes": "Apple TV Windows Store Application"
            },
            "OMEN Gaming Hub": {
                "raw_application": "OMEN Gaming Hub",
                "normalized_name": "OMEN Gaming Hub",
                "vendor": "HP",
                "classification": "OEM_OR_BUNDLED",
                "license_model": "OEM utility / free companion",
                "availability": "Windows",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "HP OMEN hardware companion"
            },
            "Amd64 Microcode": {
                "raw_application": "Amd64 Microcode",
                "normalized_name": "AMD Microcode",
                "vendor": "AMD / Ubuntu Community",
                "classification": "OPEN_SOURCE",
                "license_model": "Open-source firmware / redistributable",
                "availability": "Linux",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "Processor microcode update"
            },
            "Iso Codes": {
                "raw_application": "Iso Codes",
                "normalized_name": "ISO Codes",
                "vendor": "Debian / Ubuntu Community",
                "classification": "OPEN_SOURCE",
                "license_model": "GNU LGPL v2.1",
                "availability": "Linux",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "ISO language, territory, currency codes"
            },
            "Iucode Tool": {
                "raw_application": "Iucode Tool",
                "normalized_name": "iucode-tool",
                "vendor": "Henrique de Moraes Holschuh",
                "classification": "OPEN_SOURCE",
                "license_model": "GPL v2",
                "availability": "Linux",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "Intel processor microcode tool"
            },
            "Inno Setup": {
                "raw_application": "Inno Setup",
                "normalized_name": "Inno Setup",
                "vendor": "Jordan Russell",
                "classification": "FREEWARE",
                "license_model": "Modified BSD / Freeware",
                "availability": "Windows",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "Free installer creator"
            },
            "Inno Setup version 6.5.4": {
                "raw_application": "Inno Setup version 6.5.4",
                "normalized_name": "Inno Setup",
                "vendor": "Jordan Russell",
                "classification": "FREEWARE",
                "license_model": "Modified BSD / Freeware",
                "availability": "Windows",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "Free installer creator"
            },
            "Docs": {
                "raw_application": "Docs",
                "normalized_name": "Google Docs",
                "vendor": "Google",
                "classification": "WEB_SHORTCUT/PWA",
                "license_model": "Freemium / Google Workspace subscription",
                "availability": "Web/PWA",
                "confidence": "HIGH",
                "license_required": "CONTEXT_DEPENDENT",
                "notes": "Google Docs Web PWA"
            },
            "Sheets": {
                "raw_application": "Sheets",
                "normalized_name": "Google Sheets",
                "vendor": "Google",
                "classification": "WEB_SHORTCUT/PWA",
                "license_model": "Freemium / Google Workspace subscription",
                "availability": "Web/PWA",
                "confidence": "HIGH",
                "license_required": "CONTEXT_DEPENDENT",
                "notes": "Google Sheets Web PWA"
            },
            "MTOP Client": {
                "raw_application": "MTOP Client",
                "normalized_name": "MTOP Client",
                "vendor": "Citrix",
                "classification": "COMMERCIAL_COMPONENT",
                "license_model": "Parent Citrix Workspace installation",
                "availability": "Windows",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "Citrix Workspace internal client component"
            },
            "Online Plug-in": {
                "raw_application": "Online Plug-in",
                "normalized_name": "Citrix Online Plug-in",
                "vendor": "Citrix",
                "classification": "COMMERCIAL_COMPONENT",
                "license_model": "Parent Citrix Workspace installation",
                "availability": "Windows",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "Citrix Workspace web client plugin"
            },
            "Scan To": {
                "raw_application": "Scan To",
                "normalized_name": "HP Scan To",
                "vendor": "HP",
                "classification": "OEM_OR_BUNDLED",
                "license_model": "OEM printer utility",
                "availability": "Windows",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "HP MFP scanner companion utility"
            },
            "UTM": {
                "raw_application": "UTM",
                "normalized_name": "UTM Virtual Machines",
                "vendor": "Turing Software",
                "classification": "OPEN_SOURCE",
                "license_model": "Apache License 2.0",
                "availability": "macOS/iOS",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "Open-source QEMU frontend virtual machine host"
            },
            "v1-7-0--edge-utils": {
                "raw_application": "v1-7-0--edge-utils",
                "normalized_name": "Edge Utils",
                "vendor": "Microsoft",
                "classification": "OS_BUNDLED",
                "license_model": "Bundled with Microsoft Edge / Windows",
                "availability": "Windows",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "Microsoft Edge companion utility"
            },
            "group.is.workflow": {
                "raw_application": "group.is.workflow",
                "normalized_name": "Apple Shortcuts Workflow",
                "vendor": "Apple",
                "classification": "OS_BUNDLED",
                "license_model": "Bundled with macOS / iOS",
                "availability": "macOS",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "Apple Shortcuts / Workflow system container"
            },
            "ksystemsharehostenUS_kbyyjmwk2spaw": {
                "raw_application": "ksystemsharehostenUS_kbyyjmwk2spaw",
                "normalized_name": "Windows System Share Host",
                "vendor": "Microsoft Windows",
                "classification": "OS_BUNDLED",
                "license_model": "Windows Internal Component",
                "availability": "Windows",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "Windows modern share experience host"
            },
            "InputApp_cw5n1h2txyewy": {
                "raw_application": "InputApp_cw5n1h2txyewy",
                "normalized_name": "Windows Text Input Host",
                "vendor": "Microsoft Windows",
                "classification": "OS_BUNDLED",
                "license_model": "Windows Internal Component",
                "availability": "Windows",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "Windows virtual keyboard / input host"
            },
            "1527c705-839a-4832-9118-54d4Bd6a0c89_cw5n1h2txyewy": {
                "raw_application": "1527c705-839a-4832-9118-54d4Bd6a0c89_cw5n1h2txyewy",
                "normalized_name": "Windows Modern Application Component",
                "vendor": "Microsoft Windows",
                "classification": "OS_BUNDLED",
                "license_model": "Windows Internal Component",
                "availability": "Windows",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "System AppX internal component"
            },
            "E2A4F912-2574-4A75-9BB0-0D023378592B_cw5n1h2txyewy": {
                "raw_application": "E2A4F912-2574-4A75-9BB0-0D023378592B_cw5n1h2txyewy",
                "normalized_name": "Windows Modern Application Component",
                "vendor": "Microsoft Windows",
                "classification": "OS_BUNDLED",
                "license_model": "Windows Internal Component",
                "availability": "Windows",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "System AppX internal component"
            },
            "c5e2524a-ea46-4f67-841f-6a9465d9d515_cw5n1h2txyewy": {
                "raw_application": "c5e2524a-ea46-4f67-841f-6a9465d9d515_cw5n1h2txyewy",
                "normalized_name": "Windows Modern Application Component",
                "vendor": "Microsoft Windows",
                "classification": "OS_BUNDLED",
                "license_model": "Windows Internal Component",
                "availability": "Windows",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "System AppX internal component"
            },
            "Desktop_IT_DC": {
                "raw_application": "Desktop_IT_DC",
                "normalized_name": "Citrix Virtual Desktop (IT_DC)",
                "vendor": "Citrix",
                "classification": "COMMERCIAL_COMPONENT",
                "license_model": "Citrix Virtual Apps & Desktops subscription",
                "availability": "Enterprise",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "Citrix Delivery Group desktop endpoint"
            },
            "Remote_PC_IBL_Delivery_Group": {
                "raw_application": "Remote_PC_IBL_Delivery_Group",
                "normalized_name": "Citrix Remote PC Access Delivery Group",
                "vendor": "Citrix",
                "classification": "COMMERCIAL_COMPONENT",
                "license_model": "Citrix Virtual Apps & Desktops subscription",
                "availability": "Enterprise",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "Citrix Delivery Group remote access endpoint"
            },
            "Menulet": {
                "raw_application": "Menulet",
                "normalized_name": "System Menulet Extension",
                "vendor": "Apple",
                "classification": "OS_BUNDLED",
                "license_model": "macOS Internal Component",
                "availability": "macOS",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "macOS status bar item component"
            },
            "Runner": {
                "raw_application": "Runner",
                "normalized_name": "Application Runner",
                "vendor": "Flutter / Google",
                "classification": "FREEWARE",
                "license_model": "BSD-style / Open Source runtime",
                "availability": "Windows/macOS",
                "confidence": "MEDIUM",
                "license_required": "NO",
                "notes": "Flutter desktop shell runner application"
            },
            "pmodule": {
                "raw_application": "pmodule",
                "normalized_name": "ParakeetAI Extension Module",
                "vendor": "ParakeetAI",
                "classification": "COMMERCIAL_COMPONENT",
                "license_model": "Parent ParakeetAI service license",
                "availability": "Windows",
                "confidence": "MEDIUM",
                "license_required": "NO",
                "notes": "AI background processing module"
            },
            "PawnIO": {
                "raw_application": "PawnIO",
                "normalized_name": "PawnIO",
                "vendor": "namazso",
                "classification": "OPEN_SOURCE",
                "license_model": "Open Source (MIT / GPL)",
                "availability": "Windows",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "Kernel mode I/O abstraction library"
            },
            "Final Round": {
                "raw_application": "Final Round",
                "normalized_name": "Final Round AI",
                "vendor": "FinalRound AI",
                "classification": "FREE_AND_PAID",
                "license_model": "Freemium / Monthly Subscription",
                "availability": "Web/Desktop",
                "confidence": "HIGH",
                "license_required": "CONTEXT_DEPENDENT",
                "notes": "AI interview copilot desktop assistant"
            },
            "QurioV3 3.3.57": {
                "raw_application": "QurioV3 3.3.57",
                "normalized_name": "Qurio Assessment Platform",
                "vendor": "Teamlease Edtech",
                "classification": "COMMERCIAL",
                "license_model": "Enterprise Educational Platform Contract",
                "availability": "Windows",
                "confidence": "HIGH",
                "license_required": "YES",
                "notes": "Proctored assessment client"
            },
            "Symbiosis Assessments 1.0.12": {
                "raw_application": "Symbiosis Assessments 1.0.12",
                "normalized_name": "Symbiosis Assessments",
                "vendor": "Edutest",
                "classification": "COMMERCIAL",
                "license_model": "Institutional Academic Contract",
                "availability": "Windows",
                "confidence": "HIGH",
                "license_required": "YES",
                "notes": "Institutional examination client"
            },
            "53058betterapp.AnyScan_90ct3cgs7yy6a": {
                "raw_application": "53058betterapp.AnyScan_90ct3cgs7yy6a",
                "normalized_name": "AnyScan",
                "vendor": "BetterApp",
                "classification": "FREE_AND_PAID",
                "license_model": "Freemium / In-App Upgrade",
                "availability": "Windows",
                "confidence": "MEDIUM",
                "license_required": "CONTEXT_DEPENDENT",
                "notes": "Document scanner Store utility"
            },
            "53058betterapp.TorrentDownloader-_90ct3cgs7yy6a": {
                "raw_application": "53058betterapp.TorrentDownloader-_90ct3cgs7yy6a",
                "normalized_name": "Torrent Downloader",
                "vendor": "BetterApp",
                "classification": "FREE_AND_PAID",
                "license_model": "Freemium / In-App Upgrade",
                "availability": "Windows",
                "confidence": "MEDIUM",
                "license_required": "CONTEXT_DEPENDENT",
                "notes": "Store torrent client"
            },
            "Sam Agent": {
                "raw_application": "Sam Agent",
                "normalized_name": "SAM Discovery Agent",
                "vendor": "SilverLeaf Solutions",
                "classification": "COMMERCIAL_COMPONENT",
                "license_model": "Enterprise Software Asset Management License",
                "availability": "Enterprise",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "Enterprise IT asset discovery agent"
            },
            "sam-agent": {
                "raw_application": "sam-agent",
                "normalized_name": "SAM Discovery Agent",
                "vendor": "SilverLeaf Solutions",
                "classification": "COMMERCIAL_COMPONENT",
                "license_model": "Enterprise Software Asset Management License",
                "availability": "Enterprise",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "Enterprise IT asset discovery agent"
            },
            "Naarad Agent": {
                "raw_application": "Naarad Agent",
                "normalized_name": "Naarad Collector Agent",
                "vendor": "SilverLeaf Solutions",
                "classification": "COMMERCIAL_COMPONENT",
                "license_model": "Enterprise Data Collector License",
                "availability": "Enterprise",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "Enterprise endpoint data collector"
            },
            "Naarad Collector version 1.0": {
                "raw_application": "Naarad Collector version 1.0",
                "normalized_name": "Naarad Collector Agent",
                "vendor": "SilverLeaf Solutions",
                "classification": "COMMERCIAL_COMPONENT",
                "license_model": "Enterprise Data Collector License",
                "availability": "Enterprise",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "Enterprise endpoint data collector"
            },
            "Screen Recorder Launcher (JRE14)": {
                "raw_application": "Screen Recorder Launcher (JRE14)",
                "normalized_name": "Screen Recorder Launcher",
                "vendor": "Screencast-O-Matic",
                "classification": "FREE_AND_PAID",
                "license_model": "Freemium / In-App Subscription",
                "availability": "Windows",
                "confidence": "HIGH",
                "license_required": "CONTEXT_DEPENDENT",
                "notes": "Screen capture launcher client"
            },
            "JSON XML Editor": {
                "raw_application": "JSON XML Editor",
                "normalized_name": "JSON XML Editor",
                "vendor": "Reverse Engineering Consultants",
                "classification": "FREEWARE",
                "license_model": "Freeware Utility",
                "availability": "Windows",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "Developer data format editor"
            },
            "Inno": {
                "raw_application": "Inno",
                "normalized_name": "Inno Setup",
                "vendor": "Jordan Russell",
                "classification": "FREEWARE",
                "license_model": "Modified BSD / Freeware",
                "availability": "Windows",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "Free installer creator"
            },
            "Innoversion 6.5.4": {
                "raw_application": "Innoversion 6.5.4",
                "normalized_name": "Inno Setup",
                "vendor": "Jordan Russell",
                "classification": "FREEWARE",
                "license_model": "Modified BSD / Freeware",
                "availability": "Windows",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "Free installer creator"
            },
            "Microcode": {
                "raw_application": "Microcode",
                "normalized_name": "Processor Microcode",
                "vendor": "Ubuntu Community",
                "classification": "OPEN_SOURCE",
                "license_model": "Open-source firmware / redistributable",
                "availability": "Linux",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "Processor microcode update"
            },
            "ksystemsharehost_kbyyjmwk2spaw": {
                "raw_application": "ksystemsharehost_kbyyjmwk2spaw",
                "normalized_name": "Windows System Share Host",
                "vendor": "Microsoft Windows",
                "classification": "OS_BUNDLED",
                "license_model": "Windows Internal Component",
                "availability": "Windows",
                "confidence": "HIGH",
                "license_required": "NO",
                "notes": "Windows modern share experience host"
            },
            "\u03bcTorrent": {
                "raw_application": "\u03bcTorrent",
                "normalized_name": "\u03bcTorrent",
                "vendor": "BitTorrent Limited",
                "classification": "FREE_AND_PAID",
                "license_model": "Freemium / Ad-supported with Pro subscription",
                "availability": "Windows",
                "confidence": "HIGH",
                "license_required": "CONTEXT_DEPENDENT",
                "notes": "BitTorrent client"
            }
        }

        for app_name, app_info in extra_exact_entries.items():
            entry_map[app_name] = app_info
            entry_map[app_name.lower()] = app_info

        # Also handle unicode variations like µTorrent / uTorrent / Torrent
        if "µTorrent" in entry_map:
            entry_map["Torrent"] = entry_map["µTorrent"]
            entry_map["torrent"] = entry_map["µTorrent"]
            entry_map["utorrent"] = entry_map["µTorrent"]
        if "Webex VDI PluginEngine" in entry_map:
            entry_map["Webex VDI Plugin Installer Engine"] = entry_map["Webex VDI PluginEngine"]
            entry_map["webex vdi plugin installer engine"] = entry_map["Webex VDI PluginEngine"]
        if "OMEN Gaming Hub" in entry_map:
            entry_map["omen gaming hub"] = entry_map["OMEN Gaming Hub"]

        # ---------------------------------------------------------------------
        # 1. Update UploadLicenseResult records across all uploads
        # ---------------------------------------------------------------------
        logger.info("Updating UploadLicenseResult records in database...")
        all_results = db.query(UploadLicenseResult).all()
        matched_results_count = 0

        for r in all_results:
            raw = (r.raw_application or "").strip()
            item = entry_map.get(raw) or entry_map.get(raw.lower())
            if not item and "hevc video extensions" in raw.lower():
                item = entry_map.get("HEVC Video Extensions from Device Manu...")
            if item:
                r.canonical_product = item["normalized_name"]
                r.canonical_vendor = item["vendor"]
                r.classification = item["classification"]
                r.license_model = item["license_model"]
                r.availability = item["availability"]
                r.confidence = item["confidence"]
                r.license_required = item["license_required"]
                r.override_reason = item["notes"]
                r.research_status = "REPORT_RESOLVED" if item["classification"] != "UNKNOWN" else "MANUAL_REVIEW"
                if item["confidence"] in ["HIGH", "VERY_HIGH"]:
                    r.evidence_status = "VERIFIED"
                elif item["confidence"] == "MEDIUM":
                    r.evidence_status = "VERIFIED"
                else:
                    r.evidence_status = "MISSING"
                matched_results_count += 1

        db.commit()
        logger.info(f"Updated {matched_results_count} records in UploadLicenseResult.")

        # ---------------------------------------------------------------------
        # 2. Update InventoryUpload summary statistics
        # ---------------------------------------------------------------------
        logger.info("Updating InventoryUpload summaries and resolved counts...")
        uploads = db.query(InventoryUpload).all()
        for u in uploads:
            u_results = db.query(UploadLicenseResult).filter(UploadLicenseResult.upload_id == u.upload_id).all()
            if u_results:
                res_count = sum(1 for r in u_results if r.classification and r.classification != "UNKNOWN")
                unres_count = len(u_results) - res_count
                u.resolved_count = res_count
                u.unresolved_count = unres_count
                u.total_rows = len(u_results)
                
                # Recalculate summary_json
                classes = {}
                for r in u_results:
                    c = r.classification or "UNKNOWN"
                    classes[c] = classes.get(c, 0) + 1
                u.summary_json = json.dumps({"classifications": classes, "total": len(u_results), "resolved": res_count})

        db.commit()
        logger.info(f"Updated {len(uploads)} inventory upload summary records.")

        # ---------------------------------------------------------------------
        # 3. Update detected_applications table
        # ---------------------------------------------------------------------
        logger.info("Updating detected_applications records...")
        det_apps = db.query(DetectedApplication).all()
        det_updated = 0
        for da in det_apps:
            raw = (da.raw_name or "").strip()
            item = entry_map.get(raw) or entry_map.get(raw.lower())
            if item:
                da.normalized_name = item["normalized_name"]
                da.canonical_product = item["normalized_name"]
                da.normalized_publisher = item["vendor"]
                det_updated += 1
        db.commit()
        logger.info(f"Updated {det_updated} records in detected_applications.")

        # ---------------------------------------------------------------------
        # 4. Update installation_license_results table
        # ---------------------------------------------------------------------
        logger.info("Updating installation_license_results records...")
        inst_records = db.query(InstallationLicenseResult).all()
        inst_updated = 0
        for inst in inst_records:
            raw = (inst.raw_application_name or "").strip()
            item = entry_map.get(raw) or entry_map.get(raw.lower())
            if item:
                inst.canonical_product = item["normalized_name"]
                inst.canonical_vendor = item["vendor"]
                inst.classification = item["classification"]
                inst.license_model = item["license_model"]
                inst.license_requirement = item["license_required"]
                inst.confidence = item["confidence"]
                if item["confidence"] in ["HIGH", "VERY_HIGH"]:
                    inst.evidence_status = "VERIFIED"
                inst_updated += 1
        db.commit()
        logger.info(f"Updated {inst_updated} records in installation_license_results.")

        # ---------------------------------------------------------------------
        # 5. Populate applications catalog table
        # ---------------------------------------------------------------------
        logger.info("Populating canonical applications catalog table...")
        unique_canonicals = {}
        for item in PDF_ENTRIES:
            p_name = item["normalized_name"]
            v_name = item["vendor"]
            if p_name and p_name != "Unknown" and not p_name.startswith("Unknown GUID"):
                key = compute_canonical_application_key(
                    vendor=v_name,
                    product=p_name,
                    edition="ANY",
                    version="ANY",
                    operating_system=item["availability"]
                )
                if key not in unique_canonicals:
                    unique_canonicals[key] = (v_name, p_name, item)

        apps_created = 0
        for key, (v_name, p_name, item) in unique_canonicals.items():
            existing = db.query(Application).filter(Application.application_key == key).first()
            if not existing:
                res_status = ApplicationResearchStatus.COMPLETED if item["confidence"] in ["HIGH", "VERY_HIGH"] else ApplicationResearchStatus.NOT_RESEARCHED
                new_app = Application(
                    vendor_name=v_name,
                    product_name=p_name,
                    display_name=p_name,
                    edition="ANY",
                    version="ANY",
                    operating_system=item["availability"],
                    publisher=v_name,
                    application_key=key,
                    status=ApplicationStatus.ACTIVE,
                    research_status=res_status,
                )
                db.add(new_app)
                apps_created += 1

        db.commit()
        logger.info(f"Successfully added {apps_created} canonical applications to applications catalog.")

        # ---------------------------------------------------------------------
        # Final Verification
        # ---------------------------------------------------------------------
        u118 = db.query(InventoryUpload).filter_by(upload_id="upl_20260903_154648_36f467a1").first()
        if u118:
            logger.info("==========================================================")
            logger.info("UPLOAD 118 POST-UPDATE VERIFICATION:")
            logger.info(f"  Total rows: {u118.total_rows}")
            logger.info(f"  Resolved: {u118.resolved_count}")
            logger.info(f"  Unresolved / Needs Review: {u118.unresolved_count}")
            logger.info(f"  Summary JSON: {u118.summary_json}")
            logger.info("==========================================================")

    except Exception as e:
        db.rollback()
        logger.error(f"Error feeding PDF data to DB: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    feed_data()
