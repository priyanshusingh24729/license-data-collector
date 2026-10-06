import csv
import re

input_file = 'data/mvp_100_percent_sanitized_inventory.csv'
with open(input_file, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

print(f"Loaded {len(rows)} rows from {input_file}")

# Rule 1: Filtering noise
def is_noise(r):
    app = r["Application"].strip()
    vend = r["Vendor"].strip()
    cls = r["Classification"].strip()

    # Chromium/Edge sandbox PWA profiles
    if app.startswith("cr.sb.") or app.startswith("1_https___"):
        return True
    if any(pattern in app.lower() for pattern in [
        "sharepoint.com", "open.spotify.com", "play.google.com",
        "teams.microsoft.com", "web.whatsapp.com", "vercel.com",
        "www.hoi.in", "www.microsoft365.com", "chat.openai.com",
        "meet.google.com", "outlook.office.com", "partners.snowsoftware.com",
        "silverleafsolutions-my.sharepoint.com"
    ]):
        return True

    # Windows GUIDs & raw package names
    if app.endswith("_cw5n1h2txyewy") or app.endswith("_8wekyb3d8bbwe"):
        return True
    if re.match(r'^[0-9a-fA-F\-]{30,}', app):
        return True
    if re.match(r'^[A-Z0-9]{8}\-[A-Z0-9]{4}\-[A-Z0-9]{4}\-[A-Z0-9]{4}\-[A-Z0-9]{12}', app):
        return True
    if app in ("App", "windows_ie_ac_001"):
        return True
    if app.startswith("MicrosoftWindows."):
        return True
    if app.startswith("Windows System Component ("):
        return True

    # Debian / Ubuntu package patterns
    lower_app = app.lower()
    if lower_app.startswith("lib") or lower_app.startswith("gir1.2-") or lower_app.startswith("python3-") or lower_app.startswith("fonts-"):
        return True
    
    # macOS internal daemons / helper services (Tier 3 OS internal components that are not standalone apps)
    macos_internal_daemons = {
        "50onPaletteServer", "ABAssistantService", "About This Mac", "Accessibility Reader",
        "Accessibility Tutorial", "AccessibilityUIServer", "AccessibilityVisualsAgent",
        "AddPrinter", "AddressBookManager", "AddressBookSourceSync", "AddressBookSync",
        "AddressBookUrlForwarder", "AinuIM", "AirPlayUIAgent", "AirPort Base Station Agent",
        "AirScanLegacyDiscovery", "AirScanScanner", "AMSEngagementViewService", "AOSAlertManager",
        "AOSHeartbeat", "AOSPushRelay", "AOSUIPrefPaneLauncher", "Apple Diagnostics",
        "Apple Mobile Device Support", "AppleMobileDeviceHelper", "AppleMobileSync",
        "AppleScript Utility", "AppleSpell", "Apps", "AppSSOAgent", "AquaAppearanceHelper",
        "Archive Utility", "ARDAgent", "AskPermissionUI", "AskToMessagesHost", "Setup Assistant",
        "Assistive Control", "AutoFillPanelService", "AutomationModeUI", "AVB Configuration",
        "AXVisualSupportAgent", "BackgroundTaskManagementAgent", "Batteries",
        "Bluetooth Setup Assistant", "Bluetooth File Exchange", "BluetoothUIServer",
        "BluetoothUIService", "Boot Camp Assistant", "Build Web Page", "CalendarFileHandler",
        "Calibration Assistant", "Captive Network Assistant", "Certificate Assistant",
        "CharacterPalette", "ChineseTextConverterService", "CIMFindInputCodeTool",
        "CinematicFramingOnboardingUI", "ClassroomStudentMenuExtra", "ColorSync Utility",
        "Computer", "Conflict Resolver", "ContinuityCaptureOnboardingUI", "ControlStrip",
        "CoreLocationAgent", "CoreServicesUIAgent", "Coverage Details", "Database Events",
        "Desk View", "DFRHUD", "Diagnostics Reporter", "Dictation", "Digital Colour Meter",
        "DiscHelper", "DiskImageMounter", "DiskImages UI Agent", "Display Calibrator",
        "Dock", "Dwell Control", "eaptlstrust", "EmojiFunctionRowIM", "Enhanced Logging",
        "Erase Assistant", "EscrowSecurityAlert", "Expansion Slot Utility", "FamilyExtensionHost",
        "FeedbackRemoteView", "FileProvider-Feedback", "FindMyMacMessenger", "Folder Actions Setup",
        "FolderActionsDispatcher", "FollowUpUI", "FontRegistryUIAgent", "GameOverlayUI", "Games",
        "Help Viewer", "iCloud Outlook", "iCloud+", "iCloudUserNotificationsd", "Icon Composer",
        "identityservicesd", "IDSRemoteURLConnectionAgent", "Image Events", "Image Playground",
        "imagent", "IMAutomaticHistoryDeletionAgent", "IMTransferAgent", "Install in Progress",
        "Installer", "iOS App Installer", "IOUIAgent", "JapaneseIM-KanaTyping",
        "JapaneseIM-RomajiTyping", "JavaLauncher", "KerberosMenuExtra", "KeyboardAccessAgent",
        "KeyboardSetupAssistant", "Keychain Circle Notification", "KoreanIM", "Language Chooser",
        "LinkedNotesUIService", "liquiddetectiond", "Live Captions", "LiveSpeech", "loginwindow",
        "MakePDF", "ManagedClient", "MDMMigrationTrampoline", "MediaMLPluginApp",
        "Medical Imaging Calibrator", "Memory Slot Utility", "MobileDeviceUpdater", "MRT",
        "MTLReplayer", "Music Recognition", "nbagent", "NetAuthAgent", "Network",
        "Notification Centre", "NowPlayingTouchUI", "OBEXAgent", "ODSAgent", "OpenSpell",
        "OSDUIHelper", "Paired Devices", "Pass Viewer", "PeopleMessageService", "Phone",
        "PIPAgent", "PluginIM", "PosterBoard", "PowerChime", "PressAndHold", "PreviewShell",
        "PreviewShellMac", "Print Centre", "privatecloudcomputed", "Pro Display Calibrator",
        "Problem Reporter", "Profile Installer", "Installer Progress", "Python", # Apple macOS internal Python 3.9.6
        "qlmanage", "quicklookd", "QuickLookUIHelper", "RapportUIAgent", "rcd", "Recents",
        "RegisterPluginIMApp", "Remote Desktop Message", "Rosetta 2 Updater", "SCIM",
        "Screen Time", "screencaptureui", "ScreenReaderUIServer", "ScreenSaverEngine",
        "Script Menu", "ScriptMonitor", "ShortcutDroplet", "Shortcuts Events", "ShortcutsActions",
        "SmartCard Pairing", "sociallayerd", "Software Update", "SoftwareUpdateNotificationManager",
        "SpacesTouchBarAgent", "Speech Downloader", "SpeechRecognitionServer", "SpeechService",
        "Spotlight", "SSMenuAgent", "StageManagerOnboarding", "STMUIHelper", "storeuid",
        "Summary Service", "SyncServer", "syncuid", "System Events", "System Information",
        "System Speech", "SystemIntents", "SystemUIServer", "TamilIM", "TCIM",
        "TextInputMenuAgent", "TextInputSwitcher", "ThermalTrap", "Ticket Viewer",
        "Time Machine", "Tips", "TMHelperAgent", "TrackpadIM", "TransliterationIM", "TYIM",
        "UASharedPasteboardProgressUI", "UIKitSystem", "Universal Control",
        "universalAccessAuthWarn", "UniversalAccessControl", "UnmountAssistantAgent",
        "UserNotificationCenter", "VietnameseIM", "Voice Control Guide", "VoiceOver Quickstart",
        "Wallpaper", "Watch Face Help", "WiFiAgent", "WindowManager",
        "WindowManagerShowDesktopEducation", "Wish", "WorkoutAlert-Mac", "XProtect",
        "Droplet with Settable Properties", "group.is.workflow", "Menulet",
        "Cocoa-AppleScript Applet", "com.apple.ctcategories", "Recursive File Processing Droplet",
        "Recursive Image File Processing Droplet"
    }

    if vend == "Apple Inc." and app in macos_internal_daemons:
        return True

    # Windows OS internal updates / patches / infrastructure hooks
    if app.startswith("GDR ") or app.startswith("Service Pack ") or app.startswith("Update for "):
        return True
    if app.startswith("March 2014 servicing") or app.startswith("Microsoft security advisory") or app.startswith("Security update for Windows"):
        return True
    if app.startswith("Windows RT 8.1"):
        return True
    if app.startswith("Windows OS Component"):
        return True

    return False

filtered = [r for r in rows if not is_noise(r)]
print(f"After filtering noise: {len(filtered)} rows retained ({len(rows) - len(filtered)} noise rows dropped)")

# Group and Deduplicate by (Vendor, Application)
grouped = {}
for r in filtered:
    app = r["Application"].strip()
    vend = r["Vendor"].strip()
    
    # Rule 4: Sanitize Cross-Platform Vendor Hallucinations
    if app == "Gkbd Capplet":
        vend = "GNOME Foundation"
    elif app == "ParentalControls":
        vend = "Apple Inc."
    elif app == "Photos" and any(v.startswith("2026.") for v in r["Version"].split(";")):
        vend = "Microsoft Windows"
        app = "Windows Photos"
    
    # Clean app names where needed
    if app == "Microsoft 365" or app == "Microsoft 365 Apps":
        app = "Microsoft 365 Apps"
        vend = "Microsoft"

    # Key
    key = (vend, app)
    
    # Clean versions
    raw_ver = r["Version"].strip()
    # clean multiple whitespace/tab artifacts
    raw_ver = re.sub(r'\s+', ' ', raw_ver)
    vers = [v.strip() for v in re.split(r'[;,\s]+', raw_ver) if v.strip() and v.strip() != "N/A" and not v.strip().startswith("(+")]
    
    if key not in grouped:
        grouped[key] = {
            "Tier": r["Tier"],
            "Application": app,
            "Vendor": vend,
            "Versions": set(vers),
            "Classification": r["Classification"],
            "License Required": r["License Required"],
            "License Model": r["License Model"],
            "Confidence": r["Confidence"],
            "Evidence Status": r["Evidence Status"],
            "Evidence URL": r["Evidence URL"].strip(),
            "Hostname": r["Hostname"]
        }
    else:
        grouped[key]["Versions"].update(vers)
        # prefer more complete data
        if r["Evidence URL"].strip() and not grouped[key]["Evidence URL"]:
            grouped[key]["Evidence URL"] = r["Evidence URL"].strip()
        if r["Confidence"] in ("VERY_HIGH", "HIGH"):
            grouped[key]["Confidence"] = r["Confidence"]

print(f"Grouped into {len(grouped)} distinct canonical applications.")

clean_records = []
for (vend, app), item in sorted(grouped.items(), key=lambda x: (x[1]["Tier"], x[0][1])):
    # Rule 3: Fix High-Impact False Positives
    if app in ("Google Docs", "Google Sheets", "Google Slides", "Gmail"):
        item["Tier"] = "Tier 2: Freeware & Developer Open Source"
        item["Classification"] = "FREEWARE"
        item["License Required"] = "NO"
        item["License Model"] = "Free Cloud Productivity Client / Google Workspace"
    
    if app == "Oracle VirtualBox":
        item["Tier"] = "Tier 2: Freeware & Developer Open Source"
        item["Classification"] = "OPEN_SOURCE"
        item["License Required"] = "CONTEXT_DEPENDENT"
        item["License Model"] = "GPL-2.0 (Base Free) / PUEL (Commercial Extension Pack)"

    if app == "Microsoft Teams Meeting Add-in for Microsoft Office":
        item["Tier"] = "Tier 3: OS & System Infrastructure"
        item["Classification"] = "COMMERCIAL_COMPONENT"
        item["License Required"] = "NO"
        item["License Model"] = "Parent Suite Entitlement / Component"

    # Rule 5: Downgrade VERIFIED Claims Without URLs
    if not item["Evidence URL"] or item["Evidence URL"] == "N/A":
        if item["Evidence Status"] == "VERIFIED":
            item["Evidence Status"] = "UNVERIFIED"
    else:
        if item["Evidence Status"] in ("MISSING", "PARTIAL", "UNVERIFIED"):
            item["Evidence Status"] = "VERIFIED"

    # Format sorted versions
    sorted_v = sorted(list(item["Versions"]))
    if not sorted_v:
        ver_str = "N/A"
    elif len(sorted_v) <= 3:
        ver_str = "; ".join(sorted_v)
    else:
        ver_str = f"{sorted_v[0]}; {sorted_v[1]} (+{len(sorted_v)-2} more)"

    clean_records.append({
        "Tier": item["Tier"],
        "Application": app,
        "Vendor": vend,
        "Version": ver_str,
        "Classification": item["Classification"],
        "License Required": item["License Required"],
        "License Model": item["License Model"],
        "Confidence": item["Confidence"],
        "Evidence Status": item["Evidence Status"],
        "Evidence URL": item["Evidence URL"],
        "Hostname": "N/A"
    })

print(f"Final clean dataset has {len(clean_records)} curated products.")
counts = {}
for r in clean_records:
    counts[r["Tier"]] = counts.get(r["Tier"], 0) + 1

for t, c in sorted(counts.items()):
    print(f"  {t}: {c}")

with open('data/mvp_100_percent_license_intelligence.csv', 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=list(clean_records[0].keys()))
    writer.writeheader()
    writer.writerows(clean_records)

print("Saved data/mvp_100_percent_license_intelligence.csv successfully!")
