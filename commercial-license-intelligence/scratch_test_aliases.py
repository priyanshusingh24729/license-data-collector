from backend.inventory.recognition.microsoft_identity_resolver import MicrosoftProductIdentityResolver, WindowsProductCategory
from backend.research.windows_product_adapter import WindowsProductResearchAdapter
from backend.validation.microsoft_evidence_validator import MicrosoftEvidenceValidator

# Add display name aliases to _EXACT_PACKAGE_MAP
DISPLAY_ALIASES = {
    "windows calculator": "microsoft.windowscalculator",
    "calculator": "microsoft.windowscalculator",
    "windows notepad": "microsoft.windowsnotepad",
    "notepad": "microsoft.windowsnotepad",
    "windows camera": "microsoft.windowscamera",
    "camera": "microsoft.windowscamera",
    "windows maps": "microsoft.windowsmaps",
    "maps": "microsoft.windowsmaps",
    "windows terminal": "microsoft.windowsterminal",
    "photos": "microsoft.windows.photos",
    "microsoft photos": "microsoft.windows.photos",
    "windows photos": "microsoft.windows.photos",
    "paint": "microsoft.paint",
    "windows paint": "microsoft.paint",
    "microsoft sticky notes": "microsoft.microsoftstickynotes",
    "sticky notes": "microsoft.microsoftstickynotes",
    "bing weather": "microsoft.bingweather",
    "msn weather": "microsoft.bingweather",
    "weather": "microsoft.bingweather",
    "xbox": "microsoft.gamingapp",
    "game bar": "microsoft.xboxgamingoverlay",
    "xbox game bar": "microsoft.xboxgamingoverlay",
    "power automate": "microsoft.powerautomatedesktop",
    "power automate for desktop": "microsoft.powerautomatedesktop",
    "outlook for windows": "microsoft.outlookforwindows",
    "microsoft teams": "msteams",
    "microsoft 365 companion apps": "microsoft.m365companions",
    "microsoft 365 copilot": "microsoft.microsoftofficehub",
    "microsoft store": "microsoft.windowsstore",
    "screen sketch": "microsoft.screensketch",
    "snipping tool": "microsoft.screensketch",
    "windows alarms": "microsoft.windowsalarms",
    "windows clock": "microsoft.windowsalarms",
    "windows sound recorder": "microsoft.windowssoundrecorder",
    "sound recorder": "microsoft.windowssoundrecorder",
    "zune music": "microsoft.zunemusic",
    "windows media player": "microsoft.zunemusic",
    "zune video": "microsoft.zunevideo",
    "movies & tv": "microsoft.zunevideo",
    "microsoft whiteboard": "microsoft.whiteboard",
    "whiteboard": "microsoft.whiteboard",
    "microsoft family": "microsoftcorporationii.microsoftfamily",
    "microsoft journal": "microsoft.microsoftjournal",
    "journal": "microsoft.microsoftjournal",
    "solitaire & casual games": "microsoft.microsoftsolitairecollection",
    "todos": "microsoft.todos",
    "microsoft to do": "microsoft.todos",
    "bing news": "microsoft.bingnews",
    "news": "microsoft.bingnews",
    "get help": "microsoft.gethelp",
    "your phone": "microsoft.yourphone",
    "phone link": "microsoft.yourphone",
    "windows feedback hub": "microsoft.windowsfeedbackhub",
    "feedback hub": "microsoft.windowsfeedbackhub",
    "portal": "microsoft.mixedreality.portal",
    "mixed reality portal": "microsoft.mixedreality.portal",
    "sec health ui": "microsoft.sechealthui",
    "windows security": "microsoft.sechealthui",
    "windows subsystem for linux": "microsoftcorporationii.windowssubsystemforlinux",
    "clipchamp": "clipchamp.clipchamp",
    "microsoft clipchamp": "clipchamp.clipchamp",
}

for alias, pkg in DISPLAY_ALIASES.items():
    if pkg in MicrosoftProductIdentityResolver._EXACT_PACKAGE_MAP:
        MicrosoftProductIdentityResolver._EXACT_PACKAGE_MAP[alias] = MicrosoftProductIdentityResolver._EXACT_PACKAGE_MAP[pkg]

test_apps = [
    ("Windows Calculator", "Microsoft Corporation", "11.2607.0.0"),
    ("Windows Notepad", "Microsoft Corporation", "11.2607.14.0"),
    ("Windows Camera", "Microsoft Corporation", "2026.2607.1.0"),
    ("Windows Maps", "Microsoft Corporation", "11.2506.3.0"),
    ("Windows Terminal", "Microsoft Corporation", "1.24.11911.0"),
    ("Photos", "Microsoft Corporation", "2026.11060.2004.0"),
    ("Paint", "Microsoft Corporation", "11.2605.81.0"),
    ("Microsoft Sticky Notes", "Microsoft Corporation", "6.1.4.0"),
    ("Bing Weather", "Microsoft Corporation", "4.54.63045.0"),
    ("XBOX", "Microsoft Corporation", "2608.1001.17.0"),
    ("Power Automate", "Microsoft Corporation", "11.2608.115.0"),
    ("Outlook for Windows", "Microsoft Corporation", "1.2026.818.100"),
    ("Microsoft Teams", "Microsoft", "26213.1006.5014.9784"),
    ("Microsoft 365 companion apps", "Microsoft Corporation", "2.2605.21000.0"),
]

for name, pub, ver in test_apps:
    ident = MicrosoftProductIdentityResolver.resolve_identity(raw_name=name, raw_publisher=pub, raw_version=ver)
    research = WindowsProductResearchAdapter.research_product(ident, "OPEN_SOURCE / FREEWARE", "NO")
    validated = MicrosoftEvidenceValidator.validate_and_score(None, ident, research, "OPEN_SOURCE / FREEWARE", "NO", "NOT_APPLICABLE", "HIGH")
    print(f"'{name}' -> Canonical: '{ident.canonical_name}' | Type: {ident.product_type.value} | Validated Class: {validated['classification']} | Ev: {validated['evidence_status']} | Rel: {validated['reliability_score']}%")
