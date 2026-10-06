"""
Microsoft Product Identity Resolver (Step 20).
Resolves raw detected names, package identities, publishers, versions, installation sources,
and architectures into canonical Microsoft product identities, product families, product types,
and parent products.
"""

import re
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum


class WindowsProductCategory(str, Enum):
    """Product classification categories for Windows and Microsoft software."""
    WINDOWS_OS_COMPONENT = "WINDOWS_OS_COMPONENT"
    WINDOWS_INBOX_APP = "WINDOWS_INBOX_APP"
    OPTIONAL_WINDOWS_FEATURE = "OPTIONAL_WINDOWS_FEATURE"
    MICROSOFT_STORE_APP = "MICROSOFT_STORE_APP"
    FRAMEWORK_RUNTIME = "FRAMEWORK_RUNTIME"
    SYSTEM_DEPENDENCY = "SYSTEM_DEPENDENCY"
    COMMERCIAL_APPLICATION = "COMMERCIAL_APPLICATION"
    COMMERCIAL_COMPONENT = "COMMERCIAL_COMPONENT"
    OPEN_SOURCE_APPLICATION = "OPEN_SOURCE_APPLICATION"
    UNKNOWN = "UNKNOWN"


@dataclass
class ResolvedMicrosoftIdentity:
    """Canonical identity structure for Microsoft and Windows applications."""
    raw_name: str
    raw_package_name: Optional[str]
    raw_publisher: Optional[str]
    detected_version: Optional[str]
    canonical_name: str
    canonical_vendor: str
    product_family: str
    product_type: WindowsProductCategory
    parent_product: Optional[str]
    is_microsoft_related: bool
    identity_confidence: str  # "HIGH", "MEDIUM", "LOW"
    normalization_notes: str


class MicrosoftProductIdentityResolver:
    """
    Normalizes raw application detection metadata into standardized canonical product entities.
    Prevents raw package names (e.g. 'Microsoft.M365Companions') from being used directly as classifications.
    """

    # Exact Canonical Package Name Mappings
    _EXACT_PACKAGE_MAP: Dict[str, Dict[str, Any]] = {
        # 1. Commercial Components & Suite Dependencies
        "microsoft.m365companions": {
            "canonical_name": "Microsoft 365 Companion Apps",
            "canonical_vendor": "Microsoft Corporation",
            "product_family": "Microsoft 365",
            "product_type": WindowsProductCategory.COMMERCIAL_COMPONENT,
            "parent_product": "Microsoft 365",
            "notes": "Bundled companion apps (People, Files, Calendar) for Microsoft 365 commercial suites.",
        },
        "microsoft.officepushnotificationutility": {
            "canonical_name": "OfficePushNotificationUtility",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft 365 Apps",
            "product_type": WindowsProductCategory.COMMERCIAL_COMPONENT,
            "parent_product": "Microsoft 365 Apps",
            "notes": "Background notification component bundled with Microsoft 365 Apps.",
        },
        "microsoft.office.actionsserver": {
            "canonical_name": "Office.ActionsServer",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft 365 Apps",
            "product_type": WindowsProductCategory.COMMERCIAL_COMPONENT,
            "parent_product": "Microsoft 365 Apps",
            "notes": "Internal background actions server for Microsoft 365 Apps.",
        },
        "microsoft.teamsmeetingaddin": {
            "canonical_name": "Microsoft Teams Meeting Add-in",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft Teams",
            "product_type": WindowsProductCategory.COMMERCIAL_COMPONENT,
            "parent_product": "Microsoft Teams",
            "notes": "Add-in for Microsoft Office desktop clients enabling Teams meeting creation.",
        },
        "microsoft.onedrivesync": {
            "canonical_name": "Microsoft OneDrive Sync Client",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft OneDrive",
            "product_type": WindowsProductCategory.COMMERCIAL_COMPONENT,
            "parent_product": "Microsoft 365",
            "notes": "Desktop synchronization engine for OneDrive and SharePoint Online.",
        },

        # 2. Commercial Standalone / Hybrid Applications
        "msteams": {
            "canonical_name": "Microsoft Teams",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft 365",
            "product_type": WindowsProductCategory.COMMERCIAL_APPLICATION,
            "parent_product": "Microsoft 365",
            "notes": "Enterprise collaboration client requiring Microsoft 365 commercial subscription.",
        },
        "microsoft.powerautomatedesktop": {
            "canonical_name": "Power Automate for desktop",
            "canonical_vendor": "Microsoft",
            "product_family": "Power Platform",
            "product_type": WindowsProductCategory.COMMERCIAL_APPLICATION,
            "parent_product": "Power Platform",
            "notes": "Desktop RPA tool. Free for basic Windows use, paid attended RPA subscription required for organization/cloud flows.",
        },
        "microsoft.outlookforwindows": {
            "canonical_name": "Outlook for Windows",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft 365",
            "product_type": WindowsProductCategory.COMMERCIAL_APPLICATION,
            "parent_product": "Microsoft 365",
            "notes": "Modern Outlook client. Free for personal accounts; requires paid commercial M365 license for business mailboxes.",
        },

        # 3. Developer Tools & Open Source Applications
        "microsoft.visualstudiocode": {
            "canonical_name": "Visual Studio Code",
            "canonical_vendor": "Microsoft",
            "product_family": "Visual Studio",
            "product_type": WindowsProductCategory.OPEN_SOURCE_APPLICATION,
            "parent_product": None,
            "notes": "Free code editor provided under Microsoft Software License Terms with open-source core.",
        },
        "microsoft.windows.devhome": {
            "canonical_name": "Dev Home",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Developer Platform",
            "product_type": WindowsProductCategory.OPEN_SOURCE_APPLICATION,
            "parent_product": None,
            "notes": "Open source developer control center licensed under the MIT License.",
        },
        "microsoft.windowsterminal": {
            "canonical_name": "Windows Terminal",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Developer Platform",
            "product_type": WindowsProductCategory.OPEN_SOURCE_APPLICATION,
            "parent_product": None,
            "notes": "Modern terminal emulator open source under MIT License.",
        },
        "microsoftcorporationii.windowssubsystemforlinux": {
            "canonical_name": "Windows Subsystem for Linux (WSL)",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Developer Platform",
            "product_type": WindowsProductCategory.OPTIONAL_WINDOWS_FEATURE,
            "parent_product": "Microsoft Windows",
            "notes": "Optional Windows platform feature allowing execution of Linux ELF binaries.",
        },

        # 4. Framework Runtimes & System Dependencies
        "microsoft.desktopappinstaller": {
            "canonical_name": "App Installer (WinGet)",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Package Manager",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Windows Package Manager installer client bundled with Windows.",
        },
        "microsoft.winget.source": {
            "canonical_name": "Windows Package Manager Source (winget) V2",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Package Manager",
            "product_type": WindowsProductCategory.SYSTEM_DEPENDENCY,
            "parent_product": "Windows Package Manager",
            "notes": "Default package source index metadata for WinGet client.",
        },
        "microsoft.widgetsplatformruntime": {
            "canonical_name": "Widgets Platform Runtime",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Shell",
            "product_type": WindowsProductCategory.FRAMEWORK_RUNTIME,
            "parent_product": "Microsoft Windows",
            "notes": "Runtime subsystem powering Windows desktop widgets.",
        },
        "microsoftwindows.client.webexperience": {
            "canonical_name": "Windows Web Experience Pack",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Shell",
            "product_type": WindowsProductCategory.FRAMEWORK_RUNTIME,
            "parent_product": "Microsoft Windows",
            "notes": "Windows Web Experience Pack runtime.",
        },
        "microsoft.xboxspeechtotextoverlay": {
            "canonical_name": "Game Speech Window",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Xbox Game Speech Window overlay.",
        },
        "microsoftwindows.61869720.voiess": {
            "canonical_name": "Windows System Component (Voice Access)",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows OS Core Components",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "Windows Voice Access subsystem component.",
        },
        "microsoftwindows.61869721.livtop": {
            "canonical_name": "Windows System Component (Live Captions)",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows OS Core Components",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "Windows Live Captions subsystem component.",
        },
        "microsoftwindows.61869722.speion": {
            "canonical_name": "Windows System Component (Speech Experience)",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows OS Core Components",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "Windows Speech Experience subsystem component.",
        },
        "microsoftwindows.61869836.inpapp": {
            "canonical_name": "Windows System Component (Input App)",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows OS Core Components",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "Windows Input App / Touch Keyboard component.",
        },
        "microsoftwindows.client.core": {
            "canonical_name": "Windows System Component (Client.Core)",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows OS Core Components",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "Windows Client.Core internal system component.",
        },
        "microsoftwindows.client.photon": {
            "canonical_name": "Windows System Component (Client.Photon)",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows OS Core Components",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "Windows Client.Photon internal system component.",
        },
        "microsoftwindows.undockeddevkit": {
            "canonical_name": "Windows System Component (UndockedDevKit)",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows OS Core Components",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "Windows UndockedDevKit internal system component.",
        },
        "f46d4000-fd22-4db4-ac8e-4e1ddde828fe": {
            "canonical_name": "Windows System Component (AddSuggestedFoldersToLibraryDialog)",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows OS Core Components",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "Windows AddSuggestedFoldersToLibraryDialog component.",
        },
        "aimgr": {
            "canonical_name": "Windows AI Manager",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows AI",
            "product_type": WindowsProductCategory.SYSTEM_DEPENDENCY,
            "parent_product": "Microsoft Windows",
            "notes": "System background agent for Windows machine learning acceleration.",
        },

        # 5. Media Codecs & Store Extensions
        "microsoft.hevcvideoextension": {
            "canonical_name": "HEVC Video Extensions",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Media Codecs",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Commercial codec extension available via Microsoft Store ($0.99) or OEM pre-installation.",
        },
        "microsoft.avcencodervideoextension": {
            "canonical_name": "AVC Encoder Video Extension",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Media Codecs",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Video encoder extension provided via Microsoft Store.",
        },
        "microsoft.mpeg2videoextension": {
            "canonical_name": "MPEG-2 Video Extension",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Media Codecs",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Free video codec extension from Microsoft Store.",
        },
        "microsoft.vp9videoextensions": {
            "canonical_name": "VP9 Video Extensions",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Media Codecs",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Free VP9 codec extension from Microsoft Store.",
        },
        "microsoft.av1videoextension": {
            "canonical_name": "AV1 Video Extension",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Media Codecs",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Free AV1 codec extension from Microsoft Store.",
        },
        "microsoft.webpimageextension": {
            "canonical_name": "WebP Image Extension",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Media Codecs",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Free WebP format extension from Microsoft Store.",
        },
        "microsoft.heifimageextension": {
            "canonical_name": "HEIF Image Extension",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Media Codecs",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Free HEIF image format viewer extension from Microsoft Store.",
        },
        "microsoft.webmediaextensions": {
            "canonical_name": "Web Media Extensions",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Media Codecs",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Free media container extensions (OGG, Vorbis, Theora) from Microsoft Store.",
        },

        # 6. Microsoft Store Apps & Productivity Tools
        "microsoft.microsoftofficehub": {
            "canonical_name": "Microsoft 365 (Office Hub)",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft 365",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": "Microsoft 365",
            "notes": "Free companion portal app providing quick access to web Office apps.",
        },
        "microsoft.microsoftstickynotes": {
            "canonical_name": "Microsoft Sticky Notes",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Standard Windows note-taking applet.",
        },
        "microsoft.microsoftjournal": {
            "canonical_name": "Microsoft Journal",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft Garage",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Free digital ink notebook app developed by Microsoft Garage.",
        },
        "microsoft.microsoftsolitairecollection": {
            "canonical_name": "Microsoft Solitaire Collection",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft Casual Games",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Free-to-play card game suite with optional ad-free premium tier.",
        },
        "microsoft.todos": {
            "canonical_name": "Microsoft To Do",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft 365",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": "Microsoft 365",
            "notes": "Free task management cloud client app.",
        },
        "microsoftcorporationii.microsoftfamily": {
            "canonical_name": "Microsoft Family Safety",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft Services",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Free companion client for Microsoft Family Safety service.",
        },
        "microsoftcorporationii.quickassist": {
            "canonical_name": "Quick Assist",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Utilities",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Remote assistance application included with Windows.",
        },
        "microsoft.whiteboard": {
            "canonical_name": "Microsoft Whiteboard",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft 365",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": "Microsoft 365",
            "notes": "Collaborative digital canvas; free with Microsoft Account, enterprise integration via M365.",
        },

        # 7. Windows Modern Inbox Apps
        "microsoft.windowscalculator": {
            "canonical_name": "Windows Calculator",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Built-in Windows calculator applet.",
        },
        "microsoft.windowsphotos": {
            "canonical_name": "Windows Photos",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Built-in Windows photo viewer and editor.",
        },
        "microsoft.windows.photos": {
            "canonical_name": "Windows Photos",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Built-in Windows photo viewer and editor.",
        },
        "microsoft.windowsnotepad": {
            "canonical_name": "Windows Notepad",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Built-in Windows text editor.",
        },
        "microsoft.paint": {
            "canonical_name": "Windows Paint",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Built-in Windows graphics editor.",
        },
        "microsoft.windowscamera": {
            "canonical_name": "Windows Camera",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Built-in Windows camera utility.",
        },
        "microsoft.windowsmaps": {
            "canonical_name": "Windows Maps",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Built-in Windows maps application.",
        },
        "microsoft.windowssoundrecorder": {
            "canonical_name": "Windows Sound Recorder",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Built-in audio recording applet.",
        },
        "microsoft.windowsalarms": {
            "canonical_name": "Windows Clock & Alarms",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Built-in clock, timer, and stopwatch utility.",
        },
        "microsoft.windowsfeedbackhub": {
            "canonical_name": "Windows Feedback Hub",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Windows user feedback and diagnostic reporting app.",
        },
        "microsoft.windowsstore": {
            "canonical_name": "Microsoft Store",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Windows app store catalog client.",
        },
        "microsoft.storepurchaseapp": {
            "canonical_name": "Microsoft Store Purchase Host",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Commerce",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "In-app purchase dialog host for Microsoft Store.",
        },
        "microsoft.screensketch": {
            "canonical_name": "Snipping Tool (Screen Sketch)",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Built-in screen capture and annotation tool.",
        },
        "microsoft.yourphone": {
            "canonical_name": "Phone Link (Windows)",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Built-in smartphone connection and sync app.",
        },
        "microsoft.gethelp": {
            "canonical_name": "Microsoft Get Help",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Built-in support troubleshooting assistant.",
        },
        "microsoft.copilot": {
            "canonical_name": "Microsoft Copilot (Windows App)",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft Copilot",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Windows integrated client wrapper for Copilot generative AI assistant.",
        },
        "microsoft.microsoftedge": {
            "canonical_name": "Microsoft Edge",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft Edge",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": "Microsoft",
            "notes": "Default web browser provided by Microsoft.",
        },
        "microsoft.microsoftedge.stable": {
            "canonical_name": "Microsoft Edge",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft Edge",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": "Microsoft",
            "notes": "Default web browser provided by Microsoft.",
        },
        "microsoft.microsoftedgedevtoolsclient": {
            "canonical_name": "Microsoft Edge DevTools Client",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft Edge",
            "product_type": WindowsProductCategory.COMMERCIAL_COMPONENT,
            "parent_product": "Microsoft Edge",
            "notes": "Developer tools preview and client component for Microsoft Edge.",
        },
        "microsoft.zunemusic": {
            "canonical_name": "Windows Media Player",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Modern audio and media player applet.",
        },
        "microsoft.zunevideo": {
            "canonical_name": "Movies & TV",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Modern video playback and store player.",
        },
        "microsoft.bingsearch": {
            "canonical_name": "Bing Search",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft Bing",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Bing search applet and web integration.",
        },
        "microsoft.bingweather": {
            "canonical_name": "Microsoft Weather",
            "canonical_vendor": "Microsoft",
            "product_family": "MSN Apps",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Weather forecast modern applet.",
        },
        "microsoft.bingnews": {
            "canonical_name": "Microsoft News",
            "canonical_vendor": "Microsoft",
            "product_family": "MSN Apps",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": "Microsoft Windows",
            "notes": "News briefing modern applet.",
        },
        "microsoft.people": {
            "canonical_name": "People",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Windows contacts and address book applet.",
        },
        "microsoft.windowscommunicationsapps": {
            "canonical_name": "Windows Mail and Calendar",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Legacy built-in Mail and Calendar suite.",
        },
        "microsoft.gamingapp": {
            "canonical_name": "Xbox app for Windows",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Xbox PC gaming hub client for Windows.",
        },
        "microsoft.xboxgamingoverlay": {
            "canonical_name": "Xbox Game Bar",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Xbox Game Bar built-in gaming overlay.",
        },
        "microsoft.xboxgameoverlay": {
            "canonical_name": "Xbox Game Bar",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Xbox Game Bar built-in gaming overlay.",
        },
        "microsoft.gamingservices": {
            "canonical_name": "Xbox Gaming Services",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.SYSTEM_DEPENDENCY,
            "parent_product": "Microsoft Windows",
            "notes": "Supporting background runtime service for Xbox PC games.",
        },
        "microsoft.xboxidentityprovider": {
            "canonical_name": "Xbox Identity Provider",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "Xbox Live authentication and identity module.",
        },
        "microsoft.xboxspeechtotextoverlay": {
            "canonical_name": "Game Speech Window (Xbox Speech-to-Text Overlay)",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "Xbox game speech transcription accessibility overlay.",
        },
        "microsoft.edge.gameassist": {
            "canonical_name": "Microsoft Edge Game Assist",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft Edge",
            "product_type": WindowsProductCategory.SYSTEM_DEPENDENCY,
            "parent_product": "Microsoft Edge",
            "notes": "Browser gaming overlay and companion widget.",
        },
        "microsoft.xbox.tcui": {
            "canonical_name": "Xbox Gaming Component (Xbox TCUI)",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.SYSTEM_DEPENDENCY,
            "parent_product": "Microsoft Windows",
            "notes": "Xbox Title Callable UI gaming component.",
        },
        "microsoft.xboxgamecallableui": {
            "canonical_name": "Windows System Component (XboxGameCallableUI)",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "Windows internal gaming system component.",
        },
        "microsoft.mixedreality.portal": {
            "canonical_name": "Mixed Reality Portal",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Mixed Reality",
            "product_type": WindowsProductCategory.OPTIONAL_WINDOWS_FEATURE,
            "parent_product": "Microsoft Windows",
            "notes": "Windows Mixed Reality headset setup and portal.",
        },
        "microsoft.sechealthui": {
            "canonical_name": "Windows Security (SecHealthUI)",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Security",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "Windows Defender Security Center interface.",
        },

        # Display Name Aliases & Direct Store Names
        "windows calculator": {
            "canonical_name": "Windows Calculator",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Standard Windows Calculator inbox utility.",
        },
        "windows notepad": {
            "canonical_name": "Windows Notepad",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Standard Windows Notepad text editor applet.",
        },
        "windows camera": {
            "canonical_name": "Windows Camera",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Standard Windows Camera capture utility.",
        },
        "windows maps": {
            "canonical_name": "Windows Maps",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Standard Windows Maps inbox utility.",
        },
        "windows terminal": {
            "canonical_name": "Windows Terminal",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Developer Platform",
            "product_type": WindowsProductCategory.OPEN_SOURCE_APPLICATION,
            "parent_product": None,
            "notes": "Modern terminal emulator open source under MIT License.",
        },
        "photos": {
            "canonical_name": "Windows Photos",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Built-in modern media viewer application.",
        },
        "paint": {
            "canonical_name": "Windows Paint",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Built-in graphics editor applet.",
        },
        "microsoft sticky notes": {
            "canonical_name": "Microsoft Sticky Notes",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Desktop sticky notes application included with Windows.",
        },
        "bing weather": {
            "canonical_name": "MSN Weather",
            "canonical_vendor": "Microsoft",
            "product_family": "MSN Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Weather forecast modern applet.",
        },
        "weather": {
            "canonical_name": "MSN Weather",
            "canonical_vendor": "Microsoft",
            "product_family": "MSN Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Weather forecast modern applet.",
        },
        "xbox": {
            "canonical_name": "Xbox App for Windows",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Xbox PC gaming hub client included with Windows.",
        },
        "power automate": {
            "canonical_name": "Power Automate for desktop",
            "canonical_vendor": "Microsoft",
            "product_family": "Power Platform",
            "product_type": WindowsProductCategory.COMMERCIAL_APPLICATION,
            "parent_product": "Power Platform",
            "notes": "Desktop RPA tool. Free personal attended RPA on Windows; paid subscription required for cloud/organization flows.",
        },
        "outlook for windows": {
            "canonical_name": "Outlook for Windows",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft 365",
            "product_type": WindowsProductCategory.COMMERCIAL_APPLICATION,
            "parent_product": "Microsoft 365",
            "notes": "Modern Outlook client. Free for personal accounts; commercial M365 license required for business mailboxes.",
        },
        "microsoft teams": {
            "canonical_name": "Microsoft Teams",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft 365",
            "product_type": WindowsProductCategory.COMMERCIAL_APPLICATION,
            "parent_product": "Microsoft 365",
            "notes": "Collaboration client. Free for personal use; commercial M365 subscription required for work/school accounts.",
        },
        "microsoft 365 companion apps": {
            "canonical_name": "Microsoft 365 Companion Apps",
            "canonical_vendor": "Microsoft Corporation",
            "product_family": "Microsoft 365",
            "product_type": WindowsProductCategory.COMMERCIAL_COMPONENT,
            "parent_product": "Microsoft 365",
            "notes": "Bundled companion apps for Microsoft 365 commercial suites.",
        },
        "microsoft 365 copilot": {
            "canonical_name": "Microsoft 365 (Office Hub)",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft 365",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": "Microsoft 365",
            "notes": "Office dashboard and web launcher hub application.",
        },
        "screen sketch": {
            "canonical_name": "Snipping Tool",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Screen capture and annotation tool (Snipping Tool).",
        },
        "snipping tool": {
            "canonical_name": "Snipping Tool",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Screen capture and annotation tool.",
        },
        "windows alarms": {
            "canonical_name": "Windows Clock & Alarms",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Clock, timer, and stopwatch inbox utility.",
        },
        "windows sound recorder": {
            "canonical_name": "Windows Sound Recorder",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Audio recording inbox utility.",
        },
        "zune music": {
            "canonical_name": "Windows Media Player",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Media",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Modern Windows Media Player applet.",
        },
        "zune video": {
            "canonical_name": "Movies & TV",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Media",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Movies & TV video player applet.",
        },
        "microsoft whiteboard": {
            "canonical_name": "Microsoft Whiteboard",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft 365",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": "Microsoft 365",
            "notes": "Free digital canvas application from Microsoft.",
        },
        "microsoft family": {
            "canonical_name": "Microsoft Family Safety",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft Services",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Free parental controls and safety dashboard app.",
        },
        "microsoft journal": {
            "canonical_name": "Microsoft Journal",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft Garage",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Free digital ink journaling application.",
        },
        "solitaire & casual games": {
            "canonical_name": "Microsoft Solitaire Collection",
            "canonical_vendor": "Microsoft",
            "product_family": "Casual Games",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Free card games collection with optional premium subscription.",
        },
        "todos": {
            "canonical_name": "Microsoft To Do",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft 365",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": "Microsoft 365",
            "notes": "Free task management and to-do list application.",
        },
        "bing news": {
            "canonical_name": "Microsoft News",
            "canonical_vendor": "Microsoft",
            "product_family": "MSN Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "News briefing modern applet.",
        },
        "get help": {
            "canonical_name": "Microsoft Get Help",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Built-in troubleshooting assistant included with Windows OS.",
        },
        "game bar": {
            "canonical_name": "Xbox Game Bar",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.SYSTEM_DEPENDENCY,
            "parent_product": "Microsoft Windows",
            "notes": "Customizable gaming overlay built into Windows 10 and 11.",
        },
        "your phone": {
            "canonical_name": "Phone Link",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Mobile device integration companion included with Windows.",
        },
        "windows feedback hub": {
            "canonical_name": "Windows Feedback Hub",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Pre-installed diagnostic reporting application included with Windows OS.",
        },
        "microsoft store": {
            "canonical_name": "Microsoft Store",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Store",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Built-in application marketplace client for Windows.",
        },
        "portal": {
            "canonical_name": "Mixed Reality Portal",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Mixed Reality",
            "product_type": WindowsProductCategory.OPTIONAL_WINDOWS_FEATURE,
            "parent_product": "Microsoft Windows",
            "notes": "Windows Mixed Reality headset setup and portal.",
        },
        "sec health ui": {
            "canonical_name": "Windows Security (SecHealthUI)",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Security",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "Windows Defender Security Center interface.",
        },
        "clipchamp": {
            "canonical_name": "Clipchamp",
            "canonical_vendor": "Microsoft Corporation",
            "product_family": "Microsoft 365 Video",
            "product_type": WindowsProductCategory.COMMERCIAL_APPLICATION,
            "parent_product": "Microsoft 365",
            "notes": "Video editor with free standard export and paid Clipchamp Premium / M365 subscription tiers.",
        },
        "microsoft clipchamp": {
            "canonical_name": "Clipchamp",
            "canonical_vendor": "Microsoft Corporation",
            "product_family": "Microsoft 365 Video",
            "product_type": WindowsProductCategory.COMMERCIAL_APPLICATION,
            "parent_product": "Microsoft 365",
            "notes": "Video editor with free standard export and paid Clipchamp Premium / M365 subscription tiers.",
        },
        "immersivecontrolpanel": {
            "canonical_name": "Windows System Component (immersivecontrolpanel)",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Settings",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "Modern Settings experience component for Windows OS.",
        },
        "windowscommunicationsapps": {
            "canonical_name": "Mail and Calendar",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Built-in Mail and Calendar suite included with Windows.",
        },
        "cbs": {
            "canonical_name": "Windows System Component (Client.CBS)",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Shell Experience",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "Component Based Servicing shell experience host.",
        },
        "core ai": {
            "canonical_name": "Windows System Component (Client.CoreAI)",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows AI Platform",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "Windows on-device AI system services component.",
        },
        "microsoft bing": {
            "canonical_name": "Microsoft Bing",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft Bing",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Microsoft Bing search client.",
        },
        "microsoft photos": {
            "canonical_name": "Windows Photos",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Built-in modern media viewer application.",
        },
        "windows advanced settings": {
            "canonical_name": "Dev Home",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Developer Platform",
            "product_type": WindowsProductCategory.OPEN_SOURCE_APPLICATION,
            "parent_product": None,
            "notes": "Open source developer control center licensed under MIT License.",
        },
        "dev home": {
            "canonical_name": "Dev Home",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Developer Platform",
            "product_type": WindowsProductCategory.OPEN_SOURCE_APPLICATION,
            "parent_product": None,
            "notes": "Open source developer control center licensed under MIT License.",
        },
        "news": {
            "canonical_name": "Microsoft News",
            "canonical_vendor": "Microsoft",
            "product_family": "MSN Apps",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": "Microsoft Windows",
            "notes": "News briefing modern applet.",
        },
        "windows clock": {
            "canonical_name": "Windows Clock & Alarms",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Built-in clock, timer, and stopwatch utility.",
        },
        "mobile devices": {
            "canonical_name": "Mobile devices",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows OS Core Components",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "Windows Cross Device Experience / Mobile devices.",
        },
        "officepushnotificationsutility": {
            "canonical_name": "OfficePushNotificationUtility",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft 365 Apps",
            "product_type": WindowsProductCategory.COMMERCIAL_COMPONENT,
            "parent_product": "Microsoft 365",
            "notes": "Background notification component bundled with Microsoft 365 Apps.",
        },
        "feedback hub": {
            "canonical_name": "Windows Feedback Hub",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Windows user feedback and diagnostic reporting app.",
        },
        "windows package manager source (winget) v2": {
            "canonical_name": "Windows Package Manager Source (winget) V2",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Package Manager",
            "product_type": WindowsProductCategory.SYSTEM_DEPENDENCY,
            "parent_product": "Windows Package Manager",
            "notes": "Default package source index metadata for WinGet client.",
        },
        "windowsmanager source (winget) v2": {
            "canonical_name": "Windows Package Manager Source (winget) V2",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Package Manager",
            "product_type": WindowsProductCategory.SYSTEM_DEPENDENCY,
            "parent_product": "Windows Package Manager",
            "notes": "Default package source index metadata for WinGet client.",
        },
        "windows application compatibility enhancements": {
            "canonical_name": "Windows Application Compatibility Enhancements",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows OS Core Components",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "Windows Application Compatibility Enhancements internal component.",
        },
        "microsoft edge for game bar": {
            "canonical_name": "Microsoft Edge for Game Bar",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft Edge",
            "product_type": WindowsProductCategory.SYSTEM_DEPENDENCY,
            "parent_product": "Microsoft Edge",
            "notes": "Browser gaming overlay and companion widget.",
        },
        "microsoft people": {
            "canonical_name": "Microsoft People",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Windows contacts and address book applet.",
        },
        "mail and calendar": {
            "canonical_name": "Mail and Calendar",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Built-in Mail and Calendar suite.",
        },
        "game speech window": {
            "canonical_name": "Game Speech Window",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Xbox Game Speech Window overlay.",
        },
        "start experiences app": {
            "canonical_name": "Start Experiences App",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows OS Core Components",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "Windows Start Experiences App.",
        },
        "widgets platform runtime": {
            "canonical_name": "Widgets Platform Runtime",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Shell",
            "product_type": WindowsProductCategory.FRAMEWORK_RUNTIME,
            "parent_product": "Microsoft Windows",
            "notes": "Runtime subsystem powering Windows desktop widgets.",
        },
        "windows web experience pack": {
            "canonical_name": "Windows Web Experience Pack",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Shell",
            "product_type": WindowsProductCategory.FRAMEWORK_RUNTIME,
            "parent_product": "Microsoft Windows",
            "notes": "Windows Web Experience Pack runtime.",
        },
        "store experience host": {
            "canonical_name": "Store Experience Host",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Commerce",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "In-app purchase dialog host for Microsoft Store.",
        },
        # Codecs & Extensions (Store & OEM)
        "avc encoder video extension": {
            "canonical_name": "AVC Encoder Video Extension",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Media Codecs",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Video encoder extension provided via Microsoft Store.",
        },
        "hevc video extensions from device manufacturer": {
            "canonical_name": "HEVC Video Extensions from Device Manufacturer",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Media Codecs",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "OEM hardware-accelerated HEVC video extension bundled with device.",
        },
        "mpeg-2 video extension": {
            "canonical_name": "MPEG-2 Video Extension",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Media Codecs",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Free video codec extension from Microsoft Store.",
        },
        "vp9 video extensions": {
            "canonical_name": "VP9 Video Extensions",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Media Codecs",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Free VP9 codec extension from Microsoft Store.",
        },
        "web media extensions": {
            "canonical_name": "Web Media Extensions",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Media Codecs",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Free media container extensions (OGG, Vorbis, Theora) from Microsoft Store.",
        },
        "webp image extension": {
            "canonical_name": "WebP Image Extension",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Media Codecs",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Free WebP format extension from Microsoft Store.",
        },
        "av1 video extension": {
            "canonical_name": "AV1 Video Extension",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Media Codecs",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Free AV1 codec extension from Microsoft Store.",
        },
        "heif image extension": {
            "canonical_name": "HEIF Image Extension",
            "canonical_vendor": "Microsoft",
            "product_family": "Windows Media Codecs",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Free HEIF image format viewer extension from Microsoft Store.",
        },
        "msn weather": {
            "canonical_name": "MSN Weather",
            "canonical_vendor": "Microsoft",
            "product_family": "MSN Apps",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Weather forecast modern applet from Microsoft.",
        },
        "xbox": {
            "canonical_name": "Xbox app for Windows",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Xbox PC gaming hub client for Windows.",
        },
        "xbox app": {
            "canonical_name": "Xbox app for Windows",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Xbox PC gaming hub client for Windows.",
        },
        "xbox app for windows": {
            "canonical_name": "Xbox app for Windows",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Xbox PC gaming hub client for Windows.",
        },
        "xbox app for pc": {
            "canonical_name": "Xbox app for Windows",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": None,
            "notes": "Xbox PC gaming hub client for Windows.",
        },
        "xbox game bar": {
            "canonical_name": "Xbox Game Bar",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Customizable gaming overlay built into Windows 10 and 11.",
        },
        "game bar": {
            "canonical_name": "Xbox Game Bar",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Customizable gaming overlay built into Windows 10 and 11.",
        },
        "xbox game pass": {
            "canonical_name": "Xbox Game Pass",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.COMMERCIAL_APPLICATION,
            "parent_product": None,
            "notes": "Paid commercial gaming subscription service.",
        },
        "pc game pass": {
            "canonical_name": "Xbox Game Pass",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.COMMERCIAL_APPLICATION,
            "parent_product": None,
            "notes": "Paid commercial gaming subscription service.",
        },
        "xbox gaming services": {
            "canonical_name": "Xbox Gaming Services",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.SYSTEM_DEPENDENCY,
            "parent_product": "Microsoft Windows",
            "notes": "Supporting background runtime service for Xbox PC games.",
        },
        "gaming services": {
            "canonical_name": "Xbox Gaming Services",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.SYSTEM_DEPENDENCY,
            "parent_product": "Microsoft Windows",
            "notes": "Supporting background runtime service for Xbox PC games.",
        },
        "xbox identity provider": {
            "canonical_name": "Xbox Identity Provider",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "Xbox Live authentication and identity module.",
        },
        "xbox tcui": {
            "canonical_name": "Xbox Gaming Component (Xbox TCUI)",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.SYSTEM_DEPENDENCY,
            "parent_product": "Microsoft Windows",
            "notes": "Xbox Title Callable UI gaming component.",
        },
        "xbox game bar plugin": {
            "canonical_name": "Xbox Game Bar",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Xbox Game Bar built-in gaming overlay.",
        },
        "xbox game overlay": {
            "canonical_name": "Xbox Game Bar",
            "canonical_vendor": "Microsoft",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Xbox Game Bar built-in gaming overlay.",
        },
        "game speech window": {
            "canonical_name": "Game Speech Window (Xbox Speech-to-Text Overlay)",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "Xbox game speech transcription accessibility overlay.",
        },
        "xbox speech to text overlay": {
            "canonical_name": "Game Speech Window (Xbox Speech-to-Text Overlay)",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Xbox Gaming",
            "product_type": WindowsProductCategory.WINDOWS_OS_COMPONENT,
            "parent_product": "Microsoft Windows",
            "notes": "Xbox game speech transcription accessibility overlay.",
        },
        "mixed reality portal": {
            "canonical_name": "Mixed Reality Portal",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Mixed Reality",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Windows Mixed Reality headset setup and portal.",
        },
        "windows security": {
            "canonical_name": "Windows Security",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Security",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Windows Defender Security Center interface.",
        },
        "windows media player": {
            "canonical_name": "Windows Media Player",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Media",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Built-in media player applet included with Windows OS.",
        },
        "movies & tv": {
            "canonical_name": "Movies & TV",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Media",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Built-in video player applet included with Windows OS.",
        },
        "quick assist": {
            "canonical_name": "Quick Assist",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Utilities",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Remote assistance application included with Windows OS.",
        },
        "microsoft to do": {
            "canonical_name": "Microsoft To Do",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft 365",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": "Microsoft 365",
            "notes": "Free task management and to-do list application.",
        },
        "phone link": {
            "canonical_name": "Phone Link",
            "canonical_vendor": "Microsoft Windows",
            "product_family": "Windows Inbox Apps",
            "product_type": WindowsProductCategory.WINDOWS_INBOX_APP,
            "parent_product": "Microsoft Windows",
            "notes": "Mobile device integration companion included with Windows OS.",
        },
        "microsoft 365 copilot": {
            "canonical_name": "Microsoft 365 (Office Hub)",
            "canonical_vendor": "Microsoft",
            "product_family": "Microsoft 365",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": "Microsoft 365",
            "notes": "Free companion portal app providing quick access to web Office apps and commercial M365 subscriptions.",
        },
        "vs_coreeditorfonts": {
            "canonical_name": "vs_CoreEditorFonts",
            "canonical_vendor": "Microsoft",
            "product_family": "Visual Studio",
            "product_type": WindowsProductCategory.COMMERCIAL_COMPONENT,
            "parent_product": "Microsoft Visual Studio",
            "notes": "Visual Studio core editor fonts component.",
        },
        "power bi desktop": {
            "canonical_name": "Power BI Desktop",
            "canonical_vendor": "Microsoft",
            "product_family": "Power BI",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": "Microsoft Power BI",
            "notes": "Free Power BI Desktop report authoring application.",
        },
        "microsoft.microsoftpowerbidesktop": {
            "canonical_name": "Power BI Desktop",
            "canonical_vendor": "Microsoft",
            "product_family": "Power BI",
            "product_type": WindowsProductCategory.MICROSOFT_STORE_APP,
            "parent_product": "Microsoft Power BI",
            "notes": "Free Power BI Desktop report authoring application.",
        },
    }

    NON_MICROSOFT_VENDORS = {
        "crowdstrike", "apple", "corel", "silicon laboratories", "realtek", "google",
        "goodnotes", "dell", "lenovo", "hp", "hewlett packard", "nvidia", "intel",
        "amd", "advanced micro devices", "dolby", "broadcom", "vmware", "cisco", "citrix",
        "trellix", "ivanti", "zoho", "manageengine", "anthropic", "openai", "meta",
        "zoom", "slack", "salesforce", "atlassian", "jetbrains", "adobe", "docker",
        "postman", "canva", "figma", "notion", "amazon", "artifex", "robware",
        "kingsoft", "kovid goyal", "teamlease", "tenable", "tonec", "musarubra", "silverleaf",
        "fortemedia", "elan", "elevoc", "goodix", "wacom", "synaptics", "mirametrix",
        "snow software", "flexera", "waves audio", "oracle", "mysql", "postgresql", "sqlite"
    }

    @classmethod
    def is_microsoft_or_windows_related(
        cls,
        name: str,
        publisher: Optional[str] = None,
        package_name: Optional[str] = None
    ) -> bool:
        """
        Determines if the detected software belongs to Microsoft or Windows ecosystem.
        Prevents non-Microsoft vendor products with 'Windows' in title from being hijacked.
        """
        n_low = (name or "").strip().lower()
        p_low = (publisher or "").strip().lower()
        pkg_low = (package_name or "").strip().lower()

        # Hard guard: non-Microsoft vendor explicitly provided in publisher
        if p_low and any(v in p_low for v in cls.NON_MICROSOFT_VENDORS):
            return False

        # Hard guard: non-Microsoft vendor or driver cues in name or package identifier
        non_ms_name_cues = (
            "usbaapl", "apple", "silabenm", "silicon laboratories", "realtek",
            "crowdstrike", "corel", "snow inventory", "google workspace",
            "fortemedia", "elanmicro", "elevoc", "goodix", "wacom", "synaptics",
            "mirametrix", "dolbylaboratories", "appup.", "advancedmicrodevices",
            "wavesaudio", "e046963", "e046964", "hp pc hardware diagnostics",
            "pointing device driver", "controller all-in-one windows driver",
            "windows driver package", "driver package", "mysql", "postgresql", "sqlite"
        )
        if any(cue in n_low or cue in pkg_low for cue in non_ms_name_cues):
            return False

        if "windows sensor" in n_low or "windows shell extension" in n_low or "diagnostics windows" in n_low:
            return False

        # Check vendor
        if "microsoft" in p_low:
            return True
        
        # Check prefixes
        prefixes = [
            "microsoft.", "microsoftwindows.", "windows.", "microsoftcorporation",
            "m365", "office.", "winappruntime"
        ]
        for pref in prefixes:
            if n_low.startswith(pref) or pkg_low.startswith(pref):
                return True

        # Check Microsoft product keywords (specific to Microsoft offerings)
        keywords = [
            "microsoft", "sql server", "onedrive", "visual studio",
            ".net sdk", ".net runtime", ".net framework", "m365", "msteams",
            "copilot", "xbox", "power automate", "windows terminal",
            "windows powershell", "windows subsystem for linux",
            "windows sdk", "windows security", "windows media player",
            "windows notepad", "windows calculator", "windows camera",
            "windows maps", "windows feedback hub", "windows sound recorder",
            "windows clock", "windows paint", "windows web experience pack"
        ]
        for kw in keywords:
            if kw in n_low:
                return True

        return False

    @classmethod
    def resolve_identity(
        cls,
        raw_name: str,
        raw_publisher: Optional[str] = None,
        raw_version: Optional[str] = None,
        install_source: Optional[str] = None,
        architecture: Optional[str] = None,
        raw_package_name: Optional[str] = None,
        install_location: Optional[str] = None,
        **kwargs,
    ) -> ResolvedMicrosoftIdentity:
        """
        Main entry point for Microsoft identity resolution.
        Maps raw detected strings to clean canonical names, vendor, family, and category.
        """
        from backend.inventory.detection.detection_normalizer import DetectionNormalizer
        n_clean = (raw_name or "").strip()
        n_low = n_clean.lower()
        p_clean = (raw_publisher or "").strip()

        # Check if genuinely Microsoft or Windows related
        if not cls.is_microsoft_or_windows_related(raw_name, raw_publisher, raw_package_name):
            norm_vendor = DetectionNormalizer.normalize_publisher(raw_publisher, raw_name=raw_name)
            return ResolvedMicrosoftIdentity(
                raw_name=raw_name,
                raw_package_name=raw_package_name,
                raw_publisher=raw_publisher,
                detected_version=raw_version,
                canonical_name=raw_name,
                canonical_vendor=norm_vendor or "UNKNOWN",
                product_family="Non-Microsoft Software",
                product_type=WindowsProductCategory.UNKNOWN,
                parent_product=None,
                is_microsoft_related=False,
                identity_confidence="MEDIUM",
                normalization_notes="Not classified as a proprietary Microsoft or Windows platform product.",
            )

        # Handle Sub-MSI fragmentation (vs_*, sptools_*, icecap_*) -> Roll into parent suite as non-billable component
        if n_low.startswith("vs_") or n_low.startswith("sptools_") or n_low.startswith("icecap_"):
            return ResolvedMicrosoftIdentity(
                raw_name=raw_name,
                raw_package_name=raw_package_name,
                raw_publisher=raw_publisher,
                detected_version=raw_version,
                canonical_name=n_clean,
                canonical_vendor="Microsoft",
                product_family="Visual Studio",
                product_type=WindowsProductCategory.COMMERCIAL_COMPONENT,
                parent_product="Microsoft Visual Studio",
                is_microsoft_related=True,
                identity_confidence="HIGH",
                normalization_notes="Visual Studio workload sub-MSI installer component.",
            )

        # Handle Windows desktop themes, language packs, handwriting, scan, wallet, raw image, inbox apps
        if any(w in n_low for w in (
            "worldnationalparks", "amazonrainforest", "mountaindwellings", "languageexperiencepack",
            "ink.handwriting", "windowsscan", "wallet", "rawimageextension", "sechealthui",
            "549981c3f5f10", "cortana", "getstarted", "winget.platform.source", "xboxapp",
            "microsoft3dviewer", "mspaint", "skypeapp", "midi.gmdls", "speech.en-"
        )):
            norm_name = DetectionNormalizer.normalize_name(raw_name)
            pt = WindowsProductCategory.WINDOWS_INBOX_APP
            if "xbox" in n_low or "skype" in n_low or "3dviewer" in n_low:
                pt = WindowsProductCategory.MICROSOFT_STORE_APP
            return ResolvedMicrosoftIdentity(
                raw_name=raw_name,
                raw_package_name=raw_package_name,
                raw_publisher=raw_publisher,
                detected_version=raw_version,
                canonical_name=norm_name or n_clean,
                canonical_vendor="Microsoft Windows" if pt == WindowsProductCategory.WINDOWS_INBOX_APP else "Microsoft",
                product_family="Windows Inbox Apps & Components",
                product_type=pt,
                parent_product="Microsoft Windows",
                is_microsoft_related=True,
                identity_confidence="HIGH",
                normalization_notes="Windows built-in personalization, accessory, store app, or inbox utility.",
            )

        # Handle Teams VDI components
        if "slimcorevdi" in n_low:
            return ResolvedMicrosoftIdentity(
                raw_name=raw_name,
                raw_package_name=raw_package_name,
                raw_publisher=raw_publisher,
                detected_version=raw_version,
                canonical_name="Microsoft Teams VDI SlimCore",
                canonical_vendor="Microsoft",
                product_family="Microsoft Teams",
                product_type=WindowsProductCategory.COMMERCIAL_COMPONENT,
                parent_product="Microsoft Teams",
                is_microsoft_related=True,
                identity_confidence="HIGH",
                normalization_notes="Microsoft Teams media optimization component for virtual desktops.",
            )

        # Handle free runtimes, SDKs, developer toolkits (.net runtime, asp.net core, windows desktop runtime, windows sdk, etc.)
        if any(rt in n_low for rt in (
            "windows desktop runtime", "asp.net core runtime", ".net runtime", ".net host",
            ".net apphost", ".net fx resolver", "universal crt", "targeting pack",
            "windows sdk", "windows software development kit", "sdk arm",
            "iis express", "url rewrite module", "assessment and planning toolkit",
            "azure authoring tools", "azure compute emulator", "azure libraries for .net",
            "azure powershell", "microsoft netstandard sdk", "testplatform sdk",
            "update health tools", "web deploy", "windows 11 installation assistant",
            "pc health check", "teams machine-wide installer", "clickonce bootstrapper",
            "open xml sdk", "powershell 7", "application verifier", "vcpp_crt.redist",
            "visual c++ uwp runtime", "winui xaml runtime", "windows app runtime",
            "ssms post install tasks", "msi development tools", "kits configuration",
            "intellitraceprofilerproxy", "diagnosticshub_collectionservice",
            ".net 10.0 templates", ".net toolset 10"
        )):
            norm_name = DetectionNormalizer.normalize_name(raw_name)
            return ResolvedMicrosoftIdentity(
                raw_name=raw_name,
                raw_package_name=raw_package_name,
                raw_publisher=raw_publisher,
                detected_version=raw_version,
                canonical_name=norm_name or n_clean,
                canonical_vendor="Microsoft",
                product_family="Developer Tools & System Runtimes",
                product_type=WindowsProductCategory.FRAMEWORK_RUNTIME,
                parent_product="Microsoft Windows / Developer Platform",
                is_microsoft_related=True,
                identity_confidence="HIGH",
                normalization_notes="Free developer toolkit, utility, or redistributable runtime framework.",
            )

        # 0. Check install location for SystemApps, WindowsApps, and SxS paths first
        if install_location:
            loc_low = install_location.lower().replace("\\", "/")
            if "systemapps" in loc_low or "windowsapps" in loc_low:
                folder = loc_low.split("systemapps/")[-1] if "systemapps" in loc_low else loc_low.split("windowsapps/")[-1]
                folder = folder.split("/")[0]
                clean_folder = re.sub(r"_[a-z0-9]+$", "", folder, flags=re.IGNORECASE)
                clean_pkg = re.sub(r"_\d+[\.\d]*_.*$", "", clean_folder, flags=re.IGNORECASE)
                if clean_pkg.startswith("sxs/"):
                    clean_pkg = clean_pkg[4:]
                clean_pkg_low = clean_pkg.lower()
                if clean_pkg_low in cls._EXACT_PACKAGE_MAP:
                    m = cls._EXACT_PACKAGE_MAP[clean_pkg_low]
                    return ResolvedMicrosoftIdentity(
                        raw_name=raw_name,
                        raw_package_name=raw_package_name,
                        raw_publisher=raw_publisher,
                        detected_version=raw_version,
                        canonical_name=m["canonical_name"],
                        canonical_vendor=m["canonical_vendor"],
                        product_family=m["product_family"],
                        product_type=m["product_type"],
                        parent_product=m.get("parent_product"),
                        is_microsoft_related=True,
                        identity_confidence="HIGH",
                        normalization_notes=m["notes"],
                    )
                if "systemapps" in loc_low:
                    clean_title = clean_pkg.replace("microsoftwindows.", "").replace("microsoft.", "").replace("windows.", "")
                    return ResolvedMicrosoftIdentity(
                        raw_name=raw_name,
                        raw_package_name=raw_package_name,
                        raw_publisher=raw_publisher,
                        detected_version=raw_version,
                        canonical_name=f"Windows System Component ({clean_title})",
                        canonical_vendor="Microsoft Windows",
                        product_family="Windows OS Core Components",
                        product_type=WindowsProductCategory.WINDOWS_OS_COMPONENT,
                        parent_product="Microsoft Windows",
                        is_microsoft_related=True,
                        identity_confidence="HIGH",
                        normalization_notes=f"Resolved via install location ({clean_folder}).",
                    )

        # 1. Check Exact Package Map
        pkg_clean = (raw_package_name or n_clean).strip()
        pkg_low = pkg_clean.lower()

        if pkg_low in cls._EXACT_PACKAGE_MAP:
            m = cls._EXACT_PACKAGE_MAP[pkg_low]
            return ResolvedMicrosoftIdentity(
                raw_name=raw_name,
                raw_package_name=raw_package_name,
                raw_publisher=raw_publisher,
                detected_version=raw_version,
                canonical_name=m["canonical_name"],
                canonical_vendor=m["canonical_vendor"],
                product_family=m["product_family"],
                product_type=m["product_type"],
                parent_product=m.get("parent_product"),
                is_microsoft_related=True,
                identity_confidence="HIGH",
                normalization_notes=m["notes"],
            )

        if n_low in cls._EXACT_PACKAGE_MAP:
            m = cls._EXACT_PACKAGE_MAP[n_low]
            return ResolvedMicrosoftIdentity(
                raw_name=raw_name,
                raw_package_name=raw_package_name,
                raw_publisher=raw_publisher,
                detected_version=raw_version,
                canonical_name=m["canonical_name"],
                canonical_vendor=m["canonical_vendor"],
                product_family=m["product_family"],
                product_type=m["product_type"],
                parent_product=m.get("parent_product"),
                is_microsoft_related=True,
                identity_confidence="HIGH",
                normalization_notes=m["notes"],
            )

        # Check prefix matching for truncated names
        for k, m in cls._EXACT_PACKAGE_MAP.items():
            if (len(pkg_low) >= 10 and (pkg_low.startswith(k) or k.startswith(pkg_low))) or \
               (len(n_low) >= 10 and (n_low.startswith(k) or k.startswith(n_low))):
                return ResolvedMicrosoftIdentity(
                    raw_name=raw_name,
                    raw_package_name=raw_package_name,
                    raw_publisher=raw_publisher,
                    detected_version=raw_version,
                    canonical_name=m["canonical_name"],
                    canonical_vendor=m["canonical_vendor"],
                    product_family=m["product_family"],
                    product_type=m["product_type"],
                    parent_product=m.get("parent_product"),
                    is_microsoft_related=True,
                    identity_confidence="HIGH",
                    normalization_notes=m["notes"],
                )

        # 2. Check for Unresolved GUIDs (only when unmapped and no install location exists)
        is_unresolved_stub = (
            bool(re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", n_clean))
        )
        if is_unresolved_stub:
            return ResolvedMicrosoftIdentity(
                raw_name=raw_name,
                raw_package_name=raw_package_name,
                raw_publisher=raw_publisher,
                detected_version=raw_version,
                canonical_name="UNRESOLVED",
                canonical_vendor="UNKNOWN",
                product_family="Unknown",
                product_type=WindowsProductCategory.UNKNOWN,
                parent_product=None,
                is_microsoft_related=False,
                identity_confidence="LOW",
                normalization_notes="Unresolved GUID without confirmed product metadata or install location.",
            )

        # 3. Pattern: WinAppRuntime / Windows App SDK (Runtimes)
        if "winappruntime" in n_low or "winappruntime" in pkg_low:
            return ResolvedMicrosoftIdentity(
                raw_name=raw_name,
                raw_package_name=raw_package_name,
                raw_publisher=raw_publisher,
                detected_version=raw_version,
                canonical_name="Windows App SDK Runtime (WinAppRuntime)",
                canonical_vendor="Microsoft",
                product_family="Windows App SDK",
                product_type=WindowsProductCategory.FRAMEWORK_RUNTIME,
                parent_product="Windows App SDK",
                is_microsoft_related=True,
                identity_confidence="HIGH",
                normalization_notes="Windows App SDK redistributable framework runtime required for modern WinUI 3 desktop apps.",
            )

        # 4. Pattern: Windows Internal Core / Shell / OOBE System Apps (Confirmed SystemApps)
        is_system_app = any(sys_kw in n_low for sys_kw in [
            "microsoft.aad.", "microsoft.accountscontrol", "microsoft.asynctextservice",
            "microsoft.bioenrollment", "microsoft.creddialoghost", "microsoft.win32webviewhost",
            "microsoft.windows.apprep", "microsoft.windows.assignedaccess", "microsoft.windows.capturepicker",
            "microsoft.windows.cloudexperiencehost", "microsoft.windows.contentdeliverymanager",
            "microsoft.windows.narrator", "microsoft.windows.oobe", "microsoft.windows.parentalcontrols",
            "microsoft.windows.peopleexperiencehost", "microsoft.windows.pinningconfirmation",
            "microsoft.windows.printqueue", "microsoft.windows.secureassessment", "microsoft.windows.shellexperiencehost",
            "microsoft.windows.startmenuexperiencehost", "microsoft.windows.xgpuejectdialog",
            "microsoft.xboxgamecallableui", "microsoftwindows.client.cbs", "microsoftwindows.client.coreai",
            "microsoftwindows.client.fileexp", "microsoftwindows.client.oobe",
            "windows.cbspreview", "windows.immersivecontrolpanel", "windows.printdialog",
            "microsoft.ecapp", "microsoft.lockapp",
            "microsoft.startexperiencesapp", "microsoftwindows.crossdevice",
            "microsoft.applicationcompatibilityenhanc"
        ])

        if is_system_app:
            clean_sys_title = n_clean.replace("Microsoft.", "").replace("MicrosoftWindows.", "").replace("Windows.", "")
            return ResolvedMicrosoftIdentity(
                raw_name=raw_name,
                raw_package_name=raw_package_name,
                raw_publisher=raw_publisher,
                detected_version=raw_version,
                canonical_name=f"Windows System Component ({clean_sys_title})",
                canonical_vendor="Microsoft Windows",
                product_family="Windows OS Core Components",
                product_type=WindowsProductCategory.WINDOWS_OS_COMPONENT,
                parent_product="Microsoft Windows",
                is_microsoft_related=True,
                identity_confidence="HIGH",
                normalization_notes="Internal Windows operating system client component built into Windows OS images.",
            )

        # 4. Pattern: Xbox Overlays & Identity
        if "xbox" in n_low and any(sub in n_low for sub in ["overlay", "identity", "tcui", "speechtotext"]):
            clean_xb_title = n_clean.replace("Microsoft.", "").replace("Xbox.", "Xbox ")
            return ResolvedMicrosoftIdentity(
                raw_name=raw_name,
                raw_package_name=raw_package_name,
                raw_publisher=raw_publisher,
                detected_version=raw_version,
                canonical_name=f"Xbox Gaming Component ({clean_xb_title})",
                canonical_vendor="Microsoft",
                product_family="Xbox Gaming Services",
                product_type=WindowsProductCategory.SYSTEM_DEPENDENCY,
                parent_product="Microsoft Windows",
                is_microsoft_related=True,
                identity_confidence="HIGH",
                normalization_notes="Xbox gaming subsystem overlay and identity provider bundled with Windows.",
            )

        # 5. Pattern: Microsoft SQL Server, Tools & Drivers
        if "sql server" in n_low and not any(db in n_low for db in ("mysql", "postgresql", "pgsql", "sqlite")) and not any(db in (raw_publisher or "").lower() for db in ("oracle", "mysql", "postgresql")):
            if "management studio" in n_low:
                return ResolvedMicrosoftIdentity(
                    raw_name=raw_name,
                    raw_package_name=raw_package_name,
                    raw_publisher=raw_publisher,
                    detected_version=raw_version,
                    canonical_name="SQL Server Management Studio",
                    canonical_vendor="Microsoft",
                    product_family="Microsoft SQL Server",
                    product_type=WindowsProductCategory.COMMERCIAL_APPLICATION,
                    parent_product="Microsoft SQL Server",
                    is_microsoft_related=True,
                    identity_confidence="HIGH",
                    normalization_notes="Free standalone database administration tool provided by Microsoft.",
                )
            if "odbc driver" in n_low:
                return ResolvedMicrosoftIdentity(
                    raw_name=raw_name,
                    raw_package_name=raw_package_name,
                    raw_publisher=raw_publisher,
                    detected_version=raw_version,
                    canonical_name="Microsoft ODBC Driver for SQL Server",
                    canonical_vendor="Microsoft",
                    product_family="Microsoft Data Access",
                    product_type=WindowsProductCategory.SYSTEM_DEPENDENCY,
                    parent_product="Microsoft SQL Server",
                    is_microsoft_related=True,
                    identity_confidence="HIGH",
                    normalization_notes="Stand-alone client driver provided free by Microsoft.",
                )
            if "ole db driver" in n_low:
                return ResolvedMicrosoftIdentity(
                    raw_name=raw_name,
                    raw_package_name=raw_package_name,
                    raw_publisher=raw_publisher,
                    detected_version=raw_version,
                    canonical_name="Microsoft OLE DB Driver for SQL Server",
                    canonical_vendor="Microsoft",
                    product_family="Microsoft Data Access",
                    product_type=WindowsProductCategory.SYSTEM_DEPENDENCY,
                    parent_product="Microsoft SQL Server",
                    is_microsoft_related=True,
                    identity_confidence="HIGH",
                    normalization_notes="Stand-alone OLE DB client driver library.",
                )
            if "vss writer" in n_low:
                return ResolvedMicrosoftIdentity(
                    raw_name=raw_name,
                    raw_package_name=raw_package_name,
                    raw_publisher=raw_publisher,
                    detected_version=raw_version,
                    canonical_name="Microsoft VSS Writer for SQL Server",
                    canonical_vendor="Microsoft",
                    product_family="Microsoft SQL Server",
                    product_type=WindowsProductCategory.COMMERCIAL_COMPONENT,
                    parent_product="Microsoft SQL Server",
                    is_microsoft_related=True,
                    identity_confidence="HIGH",
                    normalization_notes="SQL Server Volume Shadow Copy Service backup writer component.",
                )
            if "browser" in n_low:
                return ResolvedMicrosoftIdentity(
                    raw_name=raw_name,
                    raw_package_name=raw_package_name,
                    raw_publisher=raw_publisher,
                    detected_version=raw_version,
                    canonical_name="SQL Server Browser Service",
                    canonical_vendor="Microsoft",
                    product_family="Microsoft SQL Server",
                    product_type=WindowsProductCategory.SYSTEM_DEPENDENCY,
                    parent_product="Microsoft SQL Server",
                    is_microsoft_related=True,
                    identity_confidence="HIGH",
                    normalization_notes="SQL Server port resolution service listener.",
                )
            if "setup" in n_low:
                return ResolvedMicrosoftIdentity(
                    raw_name=raw_name,
                    raw_package_name=raw_package_name,
                    raw_publisher=raw_publisher,
                    detected_version=raw_version,
                    canonical_name="Microsoft SQL Server Setup Support Files",
                    canonical_vendor="Microsoft",
                    product_family="Microsoft SQL Server",
                    product_type=WindowsProductCategory.COMMERCIAL_COMPONENT,
                    parent_product="Microsoft SQL Server",
                    is_microsoft_related=True,
                    identity_confidence="HIGH",
                    normalization_notes="Installer and setup files for Microsoft SQL Server.",
                )
            # Default SQL Server Database Engine
            return ResolvedMicrosoftIdentity(
                raw_name=raw_name,
                raw_package_name=raw_package_name,
                raw_publisher=raw_publisher,
                detected_version=raw_version,
                canonical_name="Microsoft SQL Server",
                canonical_vendor="Microsoft",
                product_family="Microsoft SQL Server",
                product_type=WindowsProductCategory.COMMERCIAL_APPLICATION,
                parent_product=None,
                is_microsoft_related=True,
                identity_confidence="HIGH",
                normalization_notes="Commercial relational database engine.",
            )

        # 6. Pattern: Visual Studio & .NET
        if ".net sdk" in n_low or "dotnet" in n_low:
            return ResolvedMicrosoftIdentity(
                raw_name=raw_name,
                raw_package_name=raw_package_name,
                raw_publisher=raw_publisher,
                detected_version=raw_version,
                canonical_name=".NET SDK",
                canonical_vendor="Microsoft",
                product_family=".NET Platform",
                product_type=WindowsProductCategory.OPEN_SOURCE_APPLICATION,
                parent_product=None,
                is_microsoft_related=True,
                identity_confidence="HIGH",
                normalization_notes="Open-source software development kit under MIT License.",
            )
        if "visual studio" in n_low:
            if "installer" in n_low:
                return ResolvedMicrosoftIdentity(
                    raw_name=raw_name,
                    raw_package_name=raw_package_name,
                    raw_publisher=raw_publisher,
                    detected_version=raw_version,
                    canonical_name="Microsoft Visual Studio Installer",
                    canonical_vendor="Microsoft",
                    product_family="Visual Studio",
                    product_type=WindowsProductCategory.COMMERCIAL_COMPONENT,
                    parent_product="Microsoft Visual Studio",
                    is_microsoft_related=True,
                    identity_confidence="HIGH",
                    normalization_notes="Setup bootstrapper and workload installer for Visual Studio.",
                )
            if "code" in n_low:
                return ResolvedMicrosoftIdentity(
                    raw_name=raw_name,
                    raw_package_name=raw_package_name,
                    raw_publisher=raw_publisher,
                    detected_version=raw_version,
                    canonical_name="Visual Studio Code",
                    canonical_vendor="Microsoft",
                    product_family="Visual Studio",
                    product_type=WindowsProductCategory.OPEN_SOURCE_APPLICATION,
                    parent_product=None,
                    is_microsoft_related=True,
                    identity_confidence="HIGH",
                    normalization_notes="Free developer code editor binary.",
                )
            return ResolvedMicrosoftIdentity(
                raw_name=raw_name,
                raw_package_name=raw_package_name,
                raw_publisher=raw_publisher,
                detected_version=raw_version,
                canonical_name="Microsoft Visual Studio",
                canonical_vendor="Microsoft",
                product_family="Visual Studio",
                product_type=WindowsProductCategory.COMMERCIAL_APPLICATION,
                parent_product=None,
                is_microsoft_related=True,
                identity_confidence="HIGH",
                normalization_notes="Commercial IDE for software developers.",
            )

        # 7. Pattern: Microsoft 365 / Office Apps
        if "microsoft 365 apps" in n_low or "office 365" in n_low or ("onenote" in n_low and "microsoft" in p_clean.lower()):
            clean_app_name = "Microsoft 365 Apps" if "365" in n_low else "Microsoft OneNote"
            return ResolvedMicrosoftIdentity(
                raw_name=raw_name,
                raw_package_name=raw_package_name,
                raw_publisher=raw_publisher,
                detected_version=raw_version,
                canonical_name=clean_app_name,
                canonical_vendor="Microsoft",
                product_family="Microsoft 365",
                product_type=WindowsProductCategory.COMMERCIAL_APPLICATION,
                parent_product="Microsoft 365",
                is_microsoft_related=True,
                identity_confidence="HIGH",
                normalization_notes="Commercial productivity suite client.",
            )

        # 7.1 Pattern: Xbox Ecosystem & Components
        if "gamingservices" in n_low or "gamingservices" in pkg_low or n_low == "gaming services" or n_low == "xbox gaming services":
            return ResolvedMicrosoftIdentity(
                raw_name=raw_name,
                raw_package_name=raw_package_name,
                raw_publisher=raw_publisher,
                detected_version=raw_version,
                canonical_name="Xbox Gaming Services",
                canonical_vendor="Microsoft",
                product_family="Xbox Gaming",
                product_type=WindowsProductCategory.SYSTEM_DEPENDENCY,
                parent_product="Microsoft Windows",
                is_microsoft_related=True,
                identity_confidence="HIGH",
                normalization_notes="Supporting background service for Xbox PC games and Microsoft Store installations.",
            )

        if "xboxidentityprovider" in n_low or "xboxidentityprovider" in pkg_low or n_low == "xbox identity provider":
            return ResolvedMicrosoftIdentity(
                raw_name=raw_name,
                raw_package_name=raw_package_name,
                raw_publisher=raw_publisher,
                detected_version=raw_version,
                canonical_name="Xbox Identity Provider",
                canonical_vendor="Microsoft",
                product_family="Xbox Gaming",
                product_type=WindowsProductCategory.WINDOWS_OS_COMPONENT,
                parent_product="Microsoft Windows",
                is_microsoft_related=True,
                identity_confidence="HIGH",
                normalization_notes="Operating system identity module for Xbox Live connectivity.",
            )

        if "xboxspeechtotextoverlay" in n_low or "xboxspeechtotextoverlay" in pkg_low or "game speech window" in n_low:
            return ResolvedMicrosoftIdentity(
                raw_name=raw_name,
                raw_package_name=raw_package_name,
                raw_publisher=raw_publisher,
                detected_version=raw_version,
                canonical_name="Game Speech Window (Xbox Speech-to-Text Overlay)",
                canonical_vendor="Microsoft Windows",
                product_family="Xbox Gaming",
                product_type=WindowsProductCategory.WINDOWS_OS_COMPONENT,
                parent_product="Microsoft Windows",
                is_microsoft_related=True,
                identity_confidence="HIGH",
                normalization_notes="Windows gaming accessibility overlay component.",
            )

        if "gamebar" in n_low or "gamebar" in pkg_low or "xboxgamingoverlay" in n_low or "xboxgamingoverlay" in pkg_low or "xboxgameoverlay" in n_low or n_low in ("game bar", "xbox game bar"):
            return ResolvedMicrosoftIdentity(
                raw_name=raw_name,
                raw_package_name=raw_package_name,
                raw_publisher=raw_publisher,
                detected_version=raw_version,
                canonical_name="Xbox Game Bar",
                canonical_vendor="Microsoft",
                product_family="Xbox Gaming",
                product_type=WindowsProductCategory.WINDOWS_INBOX_APP,
                parent_product="Microsoft Windows",
                is_microsoft_related=True,
                identity_confidence="HIGH",
                normalization_notes="Customizable gaming overlay built into Windows 10 and 11.",
            )

        if "game pass" in n_low or "gamepass" in n_low:
            return ResolvedMicrosoftIdentity(
                raw_name=raw_name,
                raw_package_name=raw_package_name,
                raw_publisher=raw_publisher,
                detected_version=raw_version,
                canonical_name="Xbox Game Pass",
                canonical_vendor="Microsoft",
                product_family="Xbox Gaming",
                product_type=WindowsProductCategory.COMMERCIAL_APPLICATION,
                parent_product=None,
                is_microsoft_related=True,
                identity_confidence="HIGH",
                normalization_notes="Paid commercial gaming subscription service.",
            )

        if "gamingapp" in n_low or "gamingapp" in pkg_low or n_low in ("xbox", "xbox app", "xbox app for windows", "xbox app for pc"):
            return ResolvedMicrosoftIdentity(
                raw_name=raw_name,
                raw_package_name=raw_package_name,
                raw_publisher=raw_publisher,
                detected_version=raw_version,
                canonical_name="Xbox app for Windows",
                canonical_vendor="Microsoft",
                product_family="Xbox Gaming",
                product_type=WindowsProductCategory.MICROSOFT_STORE_APP,
                parent_product=None,
                is_microsoft_related=True,
                identity_confidence="HIGH",
                normalization_notes="Xbox PC gaming hub client for Windows.",
            )

        # 8. Pattern: Visual C++ Redistributable
        if "visual c++" in n_low or "vcredist" in n_low:
            return ResolvedMicrosoftIdentity(
                raw_name=raw_name,
                raw_package_name=raw_package_name,
                raw_publisher=raw_publisher,
                detected_version=raw_version,
                canonical_name="Microsoft Visual C++ Redistributable",
                canonical_vendor="Microsoft",
                product_family="Visual C++",
                product_type=WindowsProductCategory.FRAMEWORK_RUNTIME,
                parent_product=None,
                is_microsoft_related=True,
                identity_confidence="HIGH",
                normalization_notes="Free runtime component libraries for C++ applications.",
            )

        # 9. Pattern: Fonts & Assets
        if "fonts" in n_low or "coreeditorfonts" in n_low:
            return ResolvedMicrosoftIdentity(
                raw_name=raw_name,
                raw_package_name=raw_package_name,
                raw_publisher=raw_publisher,
                detected_version=raw_version,
                canonical_name="Visual Studio Core Editor Fonts",
                canonical_vendor="Microsoft",
                product_family="Visual Studio",
                product_type=WindowsProductCategory.SYSTEM_DEPENDENCY,
                parent_product="Microsoft Visual Studio",
                is_microsoft_related=True,
                identity_confidence="HIGH",
                normalization_notes="Font asset package for code editor.",
            )

        # Fallback for other Microsoft items
        is_ms = cls.is_microsoft_or_windows_related(raw_name, raw_publisher, raw_package_name)
        return ResolvedMicrosoftIdentity(
            raw_name=raw_name,
            raw_package_name=raw_package_name,
            raw_publisher=raw_publisher,
            detected_version=raw_version,
            canonical_name=n_clean,
            canonical_vendor="Microsoft" if is_ms else (raw_publisher or "Unknown"),
            product_family="Microsoft Windows" if is_ms else "Unknown",
            product_type=WindowsProductCategory.UNKNOWN,
            parent_product=None,
            is_microsoft_related=is_ms,
            identity_confidence="MEDIUM" if is_ms else "LOW",
            normalization_notes="Uncategorized application identity.",
        )
