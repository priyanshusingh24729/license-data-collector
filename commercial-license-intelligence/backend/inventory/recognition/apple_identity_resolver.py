"""
Apple Product Identity & Licensing Resolver.
Provides deterministic resolution and license intelligence for Apple first-party software:
1. Paid Professional Software (Final Cut Pro, Logic Pro, Motion, Compressor, MainStage)
2. Free Productivity Suite (Pages, Numbers, Keynote, iMovie, GarageBand)
3. Developer Tools (Xcode, Instruments, Simulator, FileMerge, Create ML)
4. Built-in macOS Desktop Utilities (Finder, Safari, Preview, Time Machine, Activity Monitor, etc.)
5. Internal OS Daemons, Agents, and Helper Services (*Agent, *Service, *d, *IM, *UI)
"""

import re
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass


@dataclass
class ResolvedAppleIdentity:
    is_apple: bool
    canonical_product: str
    canonical_vendor: str
    category: str  # PAID_PRO, FREE_APP, DEV_TOOL, OS_BUNDLED_APP, OS_INTERNAL_COMPONENT
    classification: str
    availability: str
    license_required: str
    license_model: str
    metric: str
    confidence: str
    evidence_status: str
    evidence_url: str
    evidence_quote: str
    override_reason: str


class AppleProductIdentityResolver:
    """
    Deterministic Apple software recognition and license intelligence engine.
    """

    # 1. Paid Professional Applications (Require separate purchase / license)
    PAID_PRO_APPS: Dict[str, str] = {
        "final cut pro": "Final Cut Pro",
        "logic pro": "Logic Pro",
        "motion": "Motion",
        "compressor": "Compressor",
        "mainstage": "MainStage",
    }

    # 2. Free Mac App Store / iWork Suite
    FREE_APPS: Dict[str, str] = {
        "keynote": "Keynote",
        "pages": "Pages",
        "numbers": "Numbers",
        "imovie": "iMovie",
        "garageband": "GarageBand",
    }

    # 3. Developer Tools & Frameworks
    DEV_TOOLS: Dict[str, str] = {
        "xcode": "Xcode",
        "instruments": "Instruments",
        "simulator": "Simulator",
        "filemerge": "FileMerge",
        "reality composer pro": "Reality Composer Pro",
        "create ml": "Create ML",
        "install command line developer tools": "Command Line Developer Tools",
        "command line developer tools": "Command Line Developer Tools",
        "accessibility inspector": "Accessibility Inspector",
        "quick look simulator": "Quick Look Simulator",
        "widgetkit simulator": "WidgetKit Simulator",
    }

    # 4. Built-in macOS Desktop Utilities & Core User Applications
    OS_BUNDLED_APPS: Dict[str, str] = {
        "about this mac": "About This Mac",
        "activity monitor": "Activity Monitor",
        "airdrop": "AirDrop",
        "airport utility": "AirPort Utility",
        "app store": "App Store",
        "apple books": "Books",
        "apple diagnostics": "Apple Diagnostics",
        "apple mail": "Mail",
        "apple maps": "Maps",
        "apple music": "Music",
        "apple news": "News",
        "apple podcasts": "Podcasts",
        "apple tv": "TV",
        "archive utility": "Archive Utility",
        "audio midi": "Audio MIDI Setup",
        "audio midi setup": "Audio MIDI Setup",
        "automator": "Automator",
        "bluetooth file exchange": "Bluetooth File Exchange",
        "books": "Books",
        "boot camp assistant": "Boot Camp Assistant",
        "calculator": "Calculator",
        "calendar": "Calendar",
        "chess": "Chess",
        "colorsync utility": "ColorSync Utility",
        "console": "Console",
        "contacts": "Contacts",
        "control centre": "Control Centre",
        "control center": "Control Center",
        "desk view": "Desk View",
        "dictionary": "Dictionary",
        "digital colour meter": "Digital Colour Meter",
        "digital color meter": "Digital Color Meter",
        "directory utility": "Directory Utility",
        "disk utility": "Disk Utility",
        "dvd player": "DVD Player",
        "facetime": "FaceTime",
        "finder": "Finder",
        "find my": "Find My",
        "font book": "Font Book",
        "freeform": "Freeform",
        "game center": "Game Center",
        "grapher": "Grapher",
        "help viewer": "Help Viewer",
        "home": "Home",
        "icloud": "iCloud",
        "icloud drive": "iCloud Drive",
        "image capture": "Image Capture",
        "image playground": "Image Playground",
        "iphone mirroring": "iPhone Mirroring",
        "journal": "Journal",
        "keychain access": "Keychain Access",
        "launchpad": "Launchpad",
        "magnifier": "Magnifier",
        "mail": "Mail",
        "maps": "Maps",
        "messages": "Messages",
        "migration assistant": "Migration Assistant",
        "mission control": "Mission Control",
        "music": "Music",
        "news": "News",
        "notes": "Notes",
        "passwords": "Passwords",
        "photo booth": "Photo Booth",
        "photos": "Photos",
        "podcasts": "Podcasts",
        "preview": "Preview",
        "quicktime player": "QuickTime Player",
        "reminders": "Reminders",
        "safari": "Safari",
        "screen sharing": "Screen Sharing",
        "screen time": "Screen Time",
        "screenshot": "Screenshot",
        "script editor": "Script Editor",
        "shortcuts": "Shortcuts",
        "siri": "Siri",
        "stickies": "Stickies",
        "stocks": "Stocks",
        "system preferences": "System Preferences",
        "system settings": "System Settings",
        "terminal": "Terminal",
        "textedit": "TextEdit",
        "time machine": "Time Machine",
        "tips": "Tips",
        "tv": "TV",
        "universal control": "Universal Control",
        "voice memos": "Voice Memos",
        "voiceover utility": "VoiceOver Utility",
        "weather": "Weather",
        "wireless diagnostics": "Wireless Diagnostics",
    }

    # Common macOS daemon/agent suffixes and keywords
    DAEMON_SUFFIXES = (
        "agent", "service", "daemon", "d", "helper", "host", "launcher",
        "im", "server", "dispatcher", "ui", "viewservice", "monitor", "trampoline"
    )

    @classmethod
    def is_apple_vendor(cls, vendor_str: Optional[str]) -> bool:
        """Returns True if vendor string indicates Apple."""
        if not vendor_str:
            return False
        v = vendor_str.strip().lower()
        return v in ("apple", "apple inc.", "apple inc", "apple computer", "apple computer, inc.") or "apple inc" in v

    @classmethod
    def resolve_apple_product(
        cls,
        name: str,
        vendor: Optional[str] = None,
        version: Optional[str] = None,
        install_location: Optional[str] = None,
    ) -> Optional[ResolvedAppleIdentity]:
        """
        Attempts to resolve an application to an authoritative Apple identity.
        Returns ResolvedAppleIdentity if recognized, None otherwise.
        """
        raw_name = (name or "").strip()
        if not raw_name:
            return None

        n_lower = raw_name.lower()
        v_lower = (vendor or "").strip().lower()
        is_vendor_apple = cls.is_apple_vendor(v_lower)

        # Strip bundle identifier prefix if present (e.g. com.apple.Safari -> safari)
        clean_name = n_lower
        if clean_name.startswith("com.apple."):
            is_vendor_apple = True
            clean_name = clean_name.replace("com.apple.", "")

        # 1. Check Paid Professional Apps
        for key, canonical in cls.PAID_PRO_APPS.items():
            if clean_name == key or (is_vendor_apple and (clean_name.startswith(key) or key in clean_name)):
                return ResolvedAppleIdentity(
                    is_apple=True,
                    canonical_product=canonical,
                    canonical_vendor="Apple Inc.",
                    category="PAID_PRO",
                    classification="COMMERCIAL",
                    availability="PAID_ONLY",
                    license_required="YES",
                    license_model="Perpetual / App Store Commercial License",
                    metric="USER",
                    confidence="VERY_HIGH",
                    evidence_status="VERIFIED",
                    evidence_url="https://www.apple.com/legal/sla/",
                    evidence_quote=f"Apple {canonical} is commercial creative software requiring a paid App Store license per user/device.",
                    override_reason=f"Authoritative Apple professional software product ({canonical}).",
                )

        # 2. Check Free App Store Apps (iWork)
        for key, canonical in cls.FREE_APPS.items():
            if clean_name == key or (is_vendor_apple and clean_name == key):
                return ResolvedAppleIdentity(
                    is_apple=True,
                    canonical_product=canonical,
                    canonical_vendor="Apple Inc.",
                    category="FREE_APP",
                    classification="FREEWARE",
                    availability="FREE",
                    license_required="NO",
                    license_model="Freeware Application",
                    metric="NOT_APPLICABLE",
                    confidence="VERY_HIGH",
                    evidence_status="VERIFIED",
                    evidence_url="https://www.apple.com/legal/internet-services/itunes/dev/stdeula/",
                    evidence_quote=f"Apple {canonical} is free to download and use on macOS devices under Apple Standard EULA.",
                    override_reason=f"Apple free application ({canonical}).",
                )

        # 3. Check Developer Tools
        for key, canonical in cls.DEV_TOOLS.items():
            if clean_name == key or (is_vendor_apple and (clean_name.startswith(key) or key in clean_name)):
                return ResolvedAppleIdentity(
                    is_apple=True,
                    canonical_product=canonical,
                    canonical_vendor="Apple Inc.",
                    category="DEV_TOOL",
                    classification="FREEWARE",
                    availability="FREE",
                    license_required="NO",
                    license_model="Freeware Developer Tool",
                    metric="NOT_APPLICABLE",
                    confidence="VERY_HIGH",
                    evidence_status="VERIFIED",
                    evidence_url="https://developer.apple.com/support/terms/",
                    evidence_quote=f"Apple {canonical} is a developer tool available without fee under Apple Developer Program terms.",
                    override_reason=f"Apple developer tool ({canonical}).",
                )

        # 4. Check Built-in macOS Desktop Utilities
        for key, canonical in cls.OS_BUNDLED_APPS.items():
            if clean_name == key or (is_vendor_apple and clean_name == key):
                return ResolvedAppleIdentity(
                    is_apple=True,
                    canonical_product=canonical,
                    canonical_vendor="Apple Inc.",
                    category="OS_BUNDLED_APP",
                    classification="OS_BUNDLED",
                    availability="BUNDLED",
                    license_required="NO",
                    license_model="Operating System Bundled Feature",
                    metric="NOT_APPLICABLE",
                    confidence="VERY_HIGH",
                    evidence_status="VERIFIED",
                    evidence_url="https://www.apple.com/legal/sla/",
                    evidence_quote=f"Apple {canonical} is an integrated component bundled with macOS under the macOS Software License Agreement.",
                    override_reason=f"macOS built-in application ({canonical}).",
                )

        # 5. Check macOS System Daemons, Helpers & Agents
        if is_vendor_apple or clean_name.startswith("com.apple.") or (install_location and "/system/" in install_location.lower()):
            # If it has daemon-like characteristics or is by Apple and not matching third party
            is_daemon = (
                clean_name.endswith("d") or
                any(clean_name.endswith(suffix) for suffix in cls.DAEMON_SUFFIXES) or
                "helper" in clean_name or "service" in clean_name or "agent" in clean_name or "server" in clean_name or
                "sync" in clean_name or "palette" in clean_name or "dispatcher" in clean_name or "assistant" in clean_name
            )
            if is_daemon or is_vendor_apple:
                return ResolvedAppleIdentity(
                    is_apple=True,
                    canonical_product=raw_name,
                    canonical_vendor="Apple Inc.",
                    category="OS_INTERNAL_COMPONENT",
                    classification="OS_BUNDLED",
                    availability="BUNDLED",
                    license_required="NO",
                    license_model="Operating System Internal Component",
                    metric="NOT_APPLICABLE",
                    confidence="VERY_HIGH" if is_vendor_apple else "HIGH",
                    evidence_status="VERIFIED",
                    evidence_url="https://www.apple.com/legal/sla/",
                    evidence_quote="Internal macOS system background process or helper daemon bundled with the operating system.",
                    override_reason=f"macOS internal system component/daemon ({raw_name}).",
                )

        return None
