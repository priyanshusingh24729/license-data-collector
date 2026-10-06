"""
Application and Publisher Normalization Engine for Endpoint Detections.
Cleans raw OS/Registry installation strings into canonical representations without aggressive loss of product meaning.
"""

import re
import unicodedata
from typing import Optional, Tuple, NamedTuple, List, Dict

class VendorRule(NamedTuple):
    pattern: str
    match_type: str  # 'exact', 'contains', 'regex'
    canonical_vendor: str

VENDOR_NORMALIZATION_RULES: List[VendorRule] = [
    # Exact vendor normalization rules (Priority 1)
    VendorRule("adobe inc.", "exact", "Adobe"),
    VendorRule("adobe systems", "exact", "Adobe"),
    VendorRule("adobe systems inc.", "exact", "Adobe"),
    VendorRule("adobe systems incorporated", "exact", "Adobe"),
    VendorRule("adobe", "exact", "Adobe"),
    VendorRule("microsoft corporation", "exact", "Microsoft"),
    VendorRule("microsoft corp.", "exact", "Microsoft"),
    VendorRule("microsoft windows", "exact", "Microsoft Windows"),
    VendorRule("microsoft", "exact", "Microsoft"),
    VendorRule("oracle america, inc.", "exact", "Oracle"),
    VendorRule("oracle corporation", "exact", "Oracle Corporation"),
    VendorRule("oracle", "exact", "Oracle Corporation"),
    VendorRule("autodesk, inc.", "exact", "Autodesk"),
    VendorRule("autodesk inc.", "exact", "Autodesk"),
    VendorRule("autodesk", "exact", "Autodesk"),
    VendorRule("vmware, inc.", "exact", "VMware"),
    VendorRule("vmware inc.", "exact", "VMware"),
    VendorRule("vmware", "exact", "VMware"),
    VendorRule("google llc", "exact", "Google"),
    VendorRule("google inc.", "exact", "Google"),
    VendorRule("google", "exact", "Google"),
    VendorRule("jetbrains s.r.o.", "exact", "JetBrains"),
    VendorRule("jetbrains", "exact", "JetBrains"),
    VendorRule("atlassian pty ltd", "exact", "Atlassian"),
    VendorRule("atlassian", "exact", "Atlassian"),
    VendorRule("salesforce, inc.", "exact", "Salesforce"),
    VendorRule("salesforce.com", "exact", "Salesforce"),
    VendorRule("docker inc.", "exact", "Docker Inc."),
    VendorRule("docker", "exact", "Docker Inc."),
    VendorRule("brave software inc", "exact", "Brave Software Inc"),
    VendorRule("brave software", "exact", "Brave Software Inc"),
    VendorRule("brave", "exact", "Brave Software Inc"),
    VendorRule("the git development community", "exact", "The Git Development Community"),
    VendorRule("git", "exact", "The Git Development Community"),
    VendorRule("the linux foundation", "exact", "The Linux Foundation"),
    VendorRule("osquery", "exact", "The Linux Foundation"),
    VendorRule("python software foundation", "exact", "Python Software Foundation"),
    VendorRule("the go authors", "exact", "The Go Authors"),
    VendorRule("node.js foundation", "exact", "OpenJS Foundation"),
    VendorRule("openjs foundation", "exact", "OpenJS Foundation"),
    VendorRule("openjs", "exact", "OpenJS Foundation"),
    VendorRule("nodejs foundation", "exact", "OpenJS Foundation"),
    VendorRule("php group", "exact", "The PHP Group"),
    VendorRule("the php group", "exact", "The PHP Group"),
    VendorRule("openai", "exact", "OpenAI"),
    VendorRule("spotify ab", "exact", "Spotify"),
    VendorRule("pdf technologies", "exact", "PDF Technologies"),
    VendorRule("ng pdf lab", "exact", "PDF Technologies"),
    VendorRule("6760 ngpdflab", "exact", "PDF Technologies"),
    VendorRule("meta platforms, inc.", "exact", "Meta Platforms, Inc."),
    VendorRule("meta platforms inc.", "exact", "Meta Platforms, Inc."),
    VendorRule("meta platforms", "exact", "Meta Platforms, Inc."),
    VendorRule("meta", "exact", "Meta Platforms, Inc."),
    VendorRule("whatsapp inc.", "exact", "Meta Platforms, Inc."),
    VendorRule("lenovo group ltd.", "exact", "Lenovo"),
    VendorRule("lenovo inc.", "exact", "Lenovo"),
    VendorRule("lenovo inc", "exact", "Lenovo"),
    VendorRule("lenovo", "exact", "Lenovo"),
    VendorRule("intel(r) corporation", "exact", "Intel Corporation"),
    VendorRule("intel corporation", "exact", "Intel Corporation"),
    VendorRule("intel corp", "exact", "Intel Corporation"),
    VendorRule("intel", "exact", "Intel Corporation"),
    VendorRule("realtek semiconductor corp", "exact", "Realtek Semiconductor Corp"),
    VendorRule("realtek", "exact", "Realtek Semiconductor Corp"),
    VendorRule("dolby laboratories", "exact", "Dolby Laboratories"),
    VendorRule("dolby", "exact", "Dolby Laboratories"),
    VendorRule("elevoc technology co., ltd.", "exact", "Elevoc Technology Co., Ltd."),
    VendorRule("elevoc", "exact", "Elevoc Technology Co., Ltd."),
    VendorRule("amzn mobile llc.", "exact", "Amazon"),
    VendorRule("amzn mobile llc", "exact", "Amazon"),
    VendorRule("amazon", "exact", "Amazon"),
    VendorRule("silverleaf solutions", "exact", "SilverLeaf Solutions"),
    VendorRule("zoom communications, inc.", "exact", "Zoom Video Communications, Inc."),
    VendorRule("zoom video communications, inc.", "exact", "Zoom Video Communications, Inc."),
    VendorRule("zoom", "exact", "Zoom Video Communications, Inc."),
    VendorRule("apple inc.", "exact", "Apple Inc."),
    VendorRule("apple computer, inc.", "exact", "Apple Inc."),
    VendorRule("apple", "exact", "Apple Inc."),
    VendorRule("advanced micro devices, inc.", "exact", "Advanced Micro Devices, Inc."),
    VendorRule("advanced micro devices", "exact", "Advanced Micro Devices, Inc."),
    VendorRule("amd", "exact", "Advanced Micro Devices, Inc."),
    VendorRule("anysphere inc.", "exact", "Anysphere"),
    VendorRule("anysphere, inc.", "exact", "Anysphere"),
    VendorRule("anysphere", "exact", "Anysphere"),
    VendorRule("anthropic, pbc", "exact", "Anthropic"),
    VendorRule("anthropic pbc", "exact", "Anthropic"),
    VendorRule("anthropic", "exact", "Anthropic"),
    VendorRule("videolan team", "exact", "VideoLAN"),
    VendorRule("videolan organization", "exact", "VideoLAN"),
    VendorRule("videolan", "exact", "VideoLAN"),
    VendorRule("win.rar gmbh", "exact", "win.rar GmbH"),
    VendorRule("rarlab", "exact", "win.rar GmbH"),
    VendorRule("alexander roshal", "exact", "win.rar GmbH"),
    VendorRule("simon tatham", "exact", "Simon Tatham"),
    VendorRule("postman inc.", "exact", "Postman Inc."),
    VendorRule("postman, inc.", "exact", "Postman Inc."),
    VendorRule("postman", "exact", "Postman Inc."),
    VendorRule("notion labs, inc.", "exact", "Notion Labs, Inc."),
    VendorRule("notion labs", "exact", "Notion Labs, Inc."),
    VendorRule("notion", "exact", "Notion Labs, Inc."),
    VendorRule("discord inc.", "exact", "Discord Inc."),
    VendorRule("discord, inc.", "exact", "Discord Inc."),
    VendorRule("discord", "exact", "Discord Inc."),
    VendorRule("canva pty ltd", "exact", "Canva Pty Ltd"),
    VendorRule("canva", "exact", "Canva Pty Ltd"),
    VendorRule("mongodb, inc.", "exact", "MongoDB, Inc."),
    VendorRule("mongodb inc.", "exact", "MongoDB, Inc."),
    VendorRule("mongodb", "exact", "MongoDB, Inc."),
    VendorRule("crowdstrike, inc.", "exact", "CrowdStrike, Inc."),
    VendorRule("crowdstrike inc.", "exact", "CrowdStrike, Inc."),
    VendorRule("crowdstrike", "exact", "CrowdStrike, Inc."),
    VendorRule("logitech inc.", "exact", "Logitech"),
    VendorRule("logitech europe s.a.", "exact", "Logitech"),
    VendorRule("logitech", "exact", "Logitech"),
    VendorRule("riot games, inc.", "exact", "Riot Games, Inc."),
    VendorRule("riot games", "exact", "Riot Games, Inc."),
    VendorRule("kitware, inc.", "exact", "Kitware, Inc."),
    VendorRule("kitware", "exact", "Kitware, Inc."),
    VendorRule("amazon web services, inc.", "exact", "Amazon Web Services, Inc."),
    VendorRule("amazon web services", "exact", "Amazon Web Services, Inc."),
    VendorRule("aws", "exact", "Amazon Web Services, Inc."),
    VendorRule("nvidia corporation", "exact", "NVIDIA Corporation"),
    VendorRule("nvidia", "exact", "NVIDIA Corporation"),
    VendorRule("warp, inc.", "exact", "Warp, Inc."),
    VendorRule("warp", "exact", "Warp, Inc."),
    VendorRule("gen digital inc. / avast", "exact", "Gen Digital Inc. / Avast"),
    VendorRule("avast", "exact", "Gen Digital Inc. / Avast"),
    VendorRule("mcafee, llc", "exact", "McAfee, LLC"),
    VendorRule("mcafee", "exact", "McAfee, LLC"),
    VendorRule("tlauncher", "exact", "TLauncher"),
    VendorRule("wondershare technology co., ltd.", "exact", "Wondershare Technology Co., Ltd."),
    VendorRule("wondershare", "exact", "Wondershare Technology Co., Ltd."),
    VendorRule("telegram messenger llp", "exact", "Telegram Messenger LLP"),
    VendorRule("telegram", "exact", "Telegram Messenger LLP"),
    VendorRule("kankaria", "exact", "Kankaria"),
    VendorRule("57495kankaria", "exact", "Kankaria"),
    VendorRule("meta platforms, inc. / open source community", "exact", "Meta Platforms, Inc. / Open Source Community"),
    VendorRule("epic games, inc.", "exact", "Epic Games, Inc."),
    VendorRule("epic games", "exact", "Epic Games, Inc."),
    VendorRule("mozilla", "exact", "Mozilla"),
    VendorRule("mozilla corporation", "exact", "Mozilla"),
    VendorRule("mozilla foundation", "exact", "Mozilla"),
    VendorRule("opera software", "exact", "Opera Software"),
    VendorRule("opera software as", "exact", "Opera Software"),
    VendorRule("opera", "exact", "Opera Software"),
    VendorRule("vivaldi technologies", "exact", "Vivaldi Technologies"),
    VendorRule("vivaldi", "exact", "Vivaldi Technologies"),
    VendorRule("dropbox, inc.", "exact", "Dropbox"),
    VendorRule("dropbox inc.", "exact", "Dropbox"),
    VendorRule("dropbox", "exact", "Dropbox"),
    VendorRule("box, inc.", "exact", "Box"),
    VendorRule("box inc.", "exact", "Box"),
    VendorRule("box", "exact", "Box"),
    VendorRule("cisco systems, inc.", "exact", "Cisco Systems, Inc."),
    VendorRule("cisco systems", "exact", "Cisco Systems, Inc."),
    VendorRule("cisco", "exact", "Cisco Systems, Inc."),
    VendorRule("fortinet, inc.", "exact", "Fortinet, Inc."),
    VendorRule("fortinet", "exact", "Fortinet, Inc."),
    VendorRule("the document foundation", "exact", "The Document Foundation"),
    VendorRule("document foundation", "exact", "The Document Foundation"),
    VendorRule("libreoffice", "exact", "The Document Foundation"),
    VendorRule("filezilla project", "exact", "FileZilla Project"),
    VendorRule("tim kosse", "exact", "FileZilla Project"),
    VendorRule("eclipse foundation", "exact", "Eclipse Foundation"),
    VendorRule("eclipse", "exact", "Eclipse Foundation"),
    VendorRule("postgresql global development group", "exact", "PostgreSQL Global Development Group"),
    VendorRule("postgresql", "exact", "PostgreSQL Global Development Group"),
    VendorRule("red hat, inc.", "exact", "Red Hat, Inc."),
    VendorRule("red hat", "exact", "Red Hat, Inc."),
    VendorRule("splunk, inc.", "exact", "Splunk, Inc."),
    VendorRule("splunk", "exact", "Splunk, Inc."),
    VendorRule("the foundry visionmongers ltd", "exact", "The Foundry"),
    VendorRule("the foundry", "exact", "The Foundry"),
    VendorRule("foundry", "exact", "The Foundry"),
    VendorRule("descript, inc.", "exact", "Descript"),
    VendorRule("descript", "exact", "Descript"),
    VendorRule("moritz bunkus", "exact", "MKVToolNix"),
    VendorRule("mkvtoolnix", "exact", "MKVToolNix"),
    VendorRule("steelseries aps", "exact", "SteelSeries"),
    VendorRule("steelseries", "exact", "SteelSeries"),
    VendorRule("gams development corp.", "exact", "GAMS Development Corp."),
    VendorRule("gams", "exact", "GAMS Development Corp."),
    VendorRule("mendix technology bv", "exact", "Mendix"),
    VendorRule("mendix", "exact", "Mendix"),
    VendorRule("igor pavlov", "exact", "Igor Pavlov"),
    VendorRule("don ho", "exact", "Don Ho"),
    VendorRule("spotify", "exact", "Spotify"),
    VendorRule("netflix, inc.", "exact", "Netflix, Inc."),
    VendorRule("netflix inc.", "exact", "Netflix, Inc."),
    VendorRule("netflix", "exact", "Netflix, Inc."),
    VendorRule("strava, inc.", "exact", "Strava"),
    VendorRule("strava inc.", "exact", "Strava"),
    VendorRule("strava", "exact", "Strava"),
    VendorRule("figma, inc.", "exact", "Figma"),
    VendorRule("figma inc.", "exact", "Figma"),
    VendorRule("figma", "exact", "Figma"),
    VendorRule("omnissa, inc.", "exact", "Omnissa"),
    VendorRule("omnissa inc.", "exact", "Omnissa"),
    VendorRule("omnissa", "exact", "Omnissa"),
    VendorRule("citrix systems, inc.", "exact", "Citrix"),
    VendorRule("citrix systems", "exact", "Citrix"),
    VendorRule("citrix", "exact", "Citrix"),
    VendorRule("trellix", "exact", "Trellix"),
    VendorRule("flexera software llc", "exact", "Flexera"),
    VendorRule("flexera software", "exact", "Flexera"),
    VendorRule("flexera", "exact", "Flexera"),
    VendorRule("snow software ab", "exact", "Snow Software"),
    VendorRule("snow software", "exact", "Snow Software"),
    VendorRule("anydesk software gmbh", "exact", "AnyDesk Software GmbH"),
    VendorRule("anydesk", "exact", "AnyDesk Software GmbH"),
    VendorRule("zscaler, inc.", "exact", "Zscaler"),
    VendorRule("zscaler", "exact", "Zscaler"),
    VendorRule("netskope, inc.", "exact", "Netskope"),
    VendorRule("netskope", "exact", "Netskope"),
    VendorRule("ivanti, inc.", "exact", "Ivanti"),
    VendorRule("ivanti", "exact", "Ivanti"),
    VendorRule("pulse secure, llc", "exact", "Ivanti"),
    VendorRule("pulse secure", "exact", "Ivanti"),
    VendorRule("zoho corporation pvt. ltd.", "exact", "Zoho"),
    VendorRule("zoho corporation", "exact", "Zoho"),
    VendorRule("zoho", "exact", "Zoho"),
    VendorRule("manageengine", "exact", "Zoho"),
    VendorRule("frontmotion", "exact", "FrontMotion"),
    VendorRule("coc coc", "exact", "Coc Coc"),
    VendorRule("coccoc", "exact", "Coc Coc"),
    VendorRule("openssl project", "exact", "OpenSSL Project"),
    VendorRule("openssl", "exact", "OpenSSL Project"),
    VendorRule("apache software foundation", "exact", "Apache Software Foundation"),
    VendorRule("apache", "exact", "Apache Software Foundation"),
    VendorRule("insecure.com llc", "exact", "Insecure.Com LLC"),
    VendorRule("insecure.org", "exact", "Insecure.Com LLC"),
    VendorRule("insecure", "exact", "Insecure.Com LLC"),
    VendorRule("nmap project", "exact", "Insecure.Com LLC"),
    VendorRule("nmap", "exact", "Insecure.Com LLC"),
    VendorRule("ngrok inc.", "exact", "Ngrok"),
    VendorRule("ngrok", "exact", "Ngrok"),
    VendorRule("ollama", "exact", "Ollama"),
    VendorRule("cursor", "exact", "Anysphere"),
    VendorRule("perplexity ai, inc.", "exact", "Perplexity AI"),
    VendorRule("perplexity ai", "exact", "Perplexity AI"),
    VendorRule("perplexity", "exact", "Perplexity AI"),
    VendorRule("obs project", "exact", "OBS Project"),
    VendorRule("obsproject", "exact", "OBS Project"),
    VendorRule("krita foundation", "exact", "Krita Foundation"),
    VendorRule("stichting krita foundation", "exact", "Krita Foundation"),
    VendorRule("krita", "exact", "Krita Foundation"),
    VendorRule("broadcom inc.", "exact", "Broadcom"),
    VendorRule("broadcom", "exact", "Broadcom"),
    VendorRule("sophos ltd.", "exact", "Sophos"),
    VendorRule("sophos ltd", "exact", "Sophos"),
    VendorRule("sophos", "exact", "Sophos"),
    VendorRule("tenable, inc.", "exact", "Tenable"),
    VendorRule("tenable", "exact", "Tenable"),
    VendorRule("dell inc.", "exact", "Dell"),
    VendorRule("dell", "exact", "Dell"),
    VendorRule("hp inc.", "exact", "HP"),
    VendorRule("hp", "exact", "HP"),
    VendorRule("hewlett-packard", "exact", "HP"),
    VendorRule("hewlett packard", "exact", "HP"),
    VendorRule("giga-byte technology co., ltd.", "exact", "Gigabyte"),
    VendorRule("gigabyte technology", "exact", "Gigabyte"),
    VendorRule("gigabyte", "exact", "Gigabyte"),
    VendorRule("wacom co., ltd.", "exact", "Wacom"),
    VendorRule("wacom", "exact", "Wacom"),
    VendorRule("corel corporation", "exact", "Corel"),
    VendorRule("corel", "exact", "Corel"),
    VendorRule("alludo", "exact", "Corel"),
    VendorRule("bittorrent, inc.", "exact", "BitTorrent"),
    VendorRule("bittorrent", "exact", "BitTorrent"),
    VendorRule("rainberry, inc.", "exact", "BitTorrent"),
    VendorRule("rainberry", "exact", "BitTorrent"),
    VendorRule("teamviewer germany gmbh", "exact", "TeamViewer"),
    VendorRule("teamviewer", "exact", "TeamViewer"),
    VendorRule("piriform software ltd", "exact", "CCleaner"),
    VendorRule("piriform", "exact", "CCleaner"),
    VendorRule("ccleaner", "exact", "CCleaner"),
    VendorRule("the qbittorrent project", "exact", "qBittorrent"),
    VendorRule("qbittorrent", "exact", "qBittorrent"),
    VendorRule("servicenow, inc.", "exact", "ServiceNow"),
    VendorRule("servicenow", "exact", "ServiceNow"),
    VendorRule("winzip computing", "exact", "WinZip Computing"),
    VendorRule("winzip", "exact", "WinZip Computing"),

    # Substring / pattern vendor normalization rules (Priority 2)
    VendorRule("silicon laboratories", "contains", "Silicon Laboratories"),
    VendorRule("crowdstrike", "contains", "CrowdStrike, Inc."),
    VendorRule("corel", "contains", "Corel"),
    VendorRule("apple", "contains", "Apple Inc."),
    VendorRule("realtek", "contains", "Realtek Semiconductor Corp"),
    VendorRule("google", "contains", "Google"),
    VendorRule("anthropic", "contains", "Anthropic"),
    VendorRule("dell", "contains", "Dell"),
    VendorRule("lenovo", "contains", "Lenovo"),
    VendorRule("intel", "contains", "Intel Corporation"),
    VendorRule("advanced micro devices", "contains", "Advanced Micro Devices, Inc. (AMD)"),
    VendorRule("amd", "contains", "Advanced Micro Devices, Inc. (AMD)"),
    VendorRule("nvidia", "contains", "NVIDIA Corporation"),
    VendorRule("riot", "contains", "Riot Games, Inc."),
    VendorRule("kitware", "contains", "Kitware, Inc."),
    VendorRule("oracle", "contains", "Oracle Corporation"),
    VendorRule("warp", "contains", "Warp, Inc."),
    VendorRule("avast", "contains", "Gen Digital Inc. / Avast"),
    VendorRule("mcafee", "contains", "McAfee, LLC"),
    VendorRule("tlauncher", "contains", "TLauncher"),
    VendorRule("wondershare", "contains", "Wondershare Technology Co., Ltd."),
    VendorRule("telegram", "contains", "Telegram Messenger LLP"),
    VendorRule("kankaria", "contains", "Kankaria"),
    VendorRule("adobe", "contains", "Adobe Inc."),
    VendorRule("mozilla", "contains", "Mozilla"),
    VendorRule("opera", "contains", "Opera Software"),
    VendorRule("vivaldi", "contains", "Vivaldi Technologies"),
    VendorRule("cisco", "contains", "Cisco Systems, Inc."),
    VendorRule("fortinet", "contains", "Fortinet, Inc."),
    VendorRule("document foundation", "contains", "The Document Foundation"),
    VendorRule("libreoffice", "contains", "The Document Foundation"),
    VendorRule("filezilla", "contains", "FileZilla Project"),
    VendorRule("eclipse", "contains", "Eclipse Foundation"),
    VendorRule("postgresql", "contains", "PostgreSQL Global Development Group"),
    VendorRule("red hat", "contains", "Red Hat, Inc."),
    VendorRule("redhat", "contains", "Red Hat, Inc."),
    VendorRule("splunk", "contains", "Splunk, Inc."),
    VendorRule("foundry", "contains", "The Foundry"),
    VendorRule("steelseries", "contains", "SteelSeries"),
    VendorRule("lists.ubuntu.com", "contains", "Ubuntu Community"),
    VendorRule("ubuntu developers", "contains", "Ubuntu Community"),
    VendorRule("canonical.com", "contains", "Canonical"),
    VendorRule("canonical", "contains", "Canonical"),
    VendorRule("debian.org", "contains", "Debian Project"),
    VendorRule("debian qa", "contains", "Debian Project"),
    VendorRule("gnu.org", "contains", "Free Software Foundation"),
    VendorRule("free software foundation", "contains", "Free Software Foundation"),
]

# Backward-compatible mapping view of exact rules
PUBLISHER_CANONICAL_MAP: Dict[str, str] = {
    r.pattern: r.canonical_vendor for r in VENDOR_NORMALIZATION_RULES if r.match_type == "exact"
}

# Vendor GUID to Official Vendor Resolution Map (Step 2)
GUID_PUBLISHER_MAP = {
    "205e97f5-c441-4371-8adb-027c40fbe50d": "Amazon",
    "eb51a5da-0e72-4863-82e4-ea21c1f8dfe3": "Intel Corporation",
    "33f0f141-36f3-4ec2-a77d-51b53d0ba0e4": "Microsoft Corporation",
    "58d26209-1d57-482c-b403-b655571b5c7b": "Dolby Laboratories",
    "8f32efb2-b494-4aec-a27c-4b0736252363": "Lenovo",
    "20e7e2c9-a2a9-4a02-bb29-6fcfb9e042bb": "Lenovo",
    "4b11a687-5ad1-49cf-9839-d2e8cfb49433": "Elevoc Technology Co., Ltd.",
    "f6fd12b7-9e18-42b8-ba81-aa4ed127c991": "Autodesk",
    "83564403-0b26-46b8-9d84-040f43691d31": "Realtek Semiconductor Corp",
}

# Raw Package Name to Canonical Product Map (Step 1 & Step 8)
PACKAGE_NAME_CANONICAL_MAP = {
    "89006a2e.autocad360": "AutoCAD - DWG Viewer and Editor",
    "microsoft.microsoftpowerbidesktop": "Power BI Desktop",
    "57540amznmobilellc.amazonalexa": "Amazon Alexa",
    "appup.intelgraphicsexperience": "Intel Graphics Experience",
    "clipchamp.clipchamp": "Clipchamp",
    "dolbylaboratories.dolbyaudio": "Dolby Audio",
    "e046963f.lenovocompanion": "Lenovo Vantage",
    "e046963f.lenovovoiceworldwide": "Lenovo Voice",
    "e0469640.lenovoutility": "Lenovo Hotkeys",
    "elevoctechnologyco.ltd.smartmicrophonesettings": "Smart Microphone Settings",
    "realteksemiconductorcorp.realtekaudiocontrol": "Realtek Audio Control",
    "pythonsoftwarefoundation.pythonmanager": "Python Install Manager",
    "spotifyab.spotifymusic": "Spotify",
    "6760ngpdflab.pdfx": "PDF-X (PDF Editor & Reader)",
    "5319275a.whatsappdesktop": "WhatsApp",
    "57495kankaria.luminous": "Luminous",
    "adobesystemsincorporated.adobecreativecloudexpress": "Adobe Creative Cloud Express",
    "telegrammessengerllp.telegramdesktop": "Telegram Desktop",
    "www.instagram.com-e4b7766f": "Instagram",
    "openai.codex": "ChatGPT",
    "microsoft.bingweather": "Microsoft Weather",
    "microsoft.gamingapp": "Xbox app for Windows",
    "microsoft.xboxgamingoverlay": "Xbox Game Bar",
    "microsoft.xboxgameoverlay": "Xbox Game Bar",
    "microsoft.gamingservices": "Xbox Gaming Services",
    "microsoft.xboxidentityprovider": "Xbox Identity Provider",
    "microsoft.microsoftstickynotes": "Microsoft Sticky Notes",
    "microsoft.people": "Microsoft People",
    "microsoftcorporationii.quickassist": "Quick Assist",
    "microsoft.desktopappinstaller": "App Installer (WinGet)",
    "microsoft.microsoftofficehub": "Microsoft 365 (Office Hub)",
    "microsoft.windows.photos": "Windows Photos",
    "microsoft.windowscalculator": "Windows Calculator",
    "microsoft.windowsnotepad": "Windows Notepad",
    "microsoft.windowscamera": "Windows Camera",
    "microsoft.windowsmaps": "Windows Maps",
    "microsoft.windowsterminal": "Windows Terminal",
    "microsoft.paint": "Windows Paint",
    "microsoft.screensketch": "Snipping Tool",
    "microsoft.windowsalarms": "Windows Clock & Alarms",
    "microsoft.windowssoundrecorder": "Windows Sound Recorder",
    "microsoft.zunemusic": "Windows Media Player",
    "microsoft.zunevideo": "Movies & TV",
    "microsoft.windowsfeedbackhub": "Windows Feedback Hub",
    "microsoft.sechealthui": "Windows Security",
    "microsoft.yourphone": "Phone Link",
    "microsoft.todos": "Microsoft To Do",
    "microsoft.whiteboard": "Microsoft Whiteboard",
    "microsoft.microsoftjournal": "Microsoft Journal",
    "microsoft.microsoftsolitairecollection": "Microsoft Solitaire Collection",
    "microsoftcorporationii.microsoftfamily": "Microsoft Family Safety",
    "microsoftcorporationii.windowssubsystemforlinux": "Windows Subsystem for Linux",
    "microsoft.windows.devhome": "Dev Home",
    "microsoft.visualstudiocode": "Visual Studio Code",
    "microsoft.outlookforwindows": "Outlook for Windows",
    "microsoft.powerautomatedesktop": "Power Automate for desktop",
    "msteams": "Microsoft Teams",
    "microsoft.m365companions": "Microsoft 365 Companion Apps",
    "microsoft.onedrivesync": "Microsoft OneDrive Sync Client",
    "microsoft.bingnews": "Microsoft News",
    "microsoft.bingsearch": "Microsoft Bing",
    "microsoft.edge.gameassist": "Microsoft Edge Game Assist",
    "microsoft edge for game bar": "Microsoft Edge Game Assist",
    "microsoft edge game assist": "Microsoft Edge Game Assist",
    "microsoft.xboxspeechtotextoverlay": "Game Speech Window (Xbox Speech-to-Text Overlay)",
    "microsoft.xbox.tcui": "Xbox Gaming Component (Xbox TCUI)",
    "xbox tcui": "Xbox Gaming Component (Xbox TCUI)",
    "microsoft.xboxgamecallableui": "Windows System Component (XboxGameCallableUI)",
    "xbox game bar plugin": "Xbox Game Bar",
    "xbox identity provider": "Xbox Identity Provider",
    "game speech window": "Game Speech Window (Xbox Speech-to-Text Overlay)",
    "xbox app": "Xbox app for Windows",
    "xbox app for windows": "Xbox app for Windows",
    "microsoft.startexperiencesapp": "Start Experiences App",
    "microsoft.widgetsplatformruntime": "Widgets Platform Runtime",
    "microsoftwindows.client.webexperience": "Windows Web Experience Pack",
    "microsoftwindows.crossdevice": "Windows Cross Device Experience",
    "microsoft.officepushnotificationutility": "OfficePushNotificationsUtility",
    "microsoft.office.actionsserver": "Microsoft.Office.ActionsServer",
    "microsoft.winget.source": "Windows Package Manager Source (winget) V2",
    "microsoft.applicationcompatibilityenhancements": "Windows Application Compatibility Enhancements",
    "aimgr": "Windows AI Manager",
    "f46d4000-fd22-4db4-ac8e-4e1ddde828fe": "Windows System Component (AddSuggestedFoldersToLibraryDialog)",
    "microsoftwindows.61869720.voiess": "Windows System Component (Voice Access)",
    "microsoftwindows.61869721.livtop": "Windows System Component (Live Captions)",
    "microsoftwindows.61869722.speion": "Windows System Component (Speech Experience)",
    "microsoftwindows.61869836.inpapp": "Windows System Component (Input App)",
    "microsoftwindows.client.cbs": "Windows System Component (Client.CBS)",
    "microsoftwindows.client.core": "Windows System Component (Client.Core)",
    "microsoftwindows.client.coreai": "Windows System Component (Client.CoreAI)",
    "microsoftwindows.client.fileexp": "Windows System Component (Client.FileExp)",
    "microsoftwindows.client.oobe": "Windows System Component (Client.OOBE)",
    "microsoftwindows.client.photon": "Windows System Component (Client.Photon)",
    "microsoftwindows.undockeddevkit": "Windows System Component (UndockedDevKit)",
    "windows.cbspreview": "Windows System Component (CBSPreview)",
    "windows.immersivecontrolpanel": "Windows System Component (immersivecontrolpanel)",
    "windows.printdialog": "Windows System Component (PrintDialog)",
    "microsoft.ecapp": "Windows System Component (ECApp)",
    "microsoft.lockapp": "Windows System Component (LockApp)",
    "advancedmicrodevicesinc-2.amdradeonsoftware": "AMD Radeon Software",
    "advancedmicrodevicesinc.amdradeonsoftware": "AMD Radeon Software",
    "a-volute.nahimic": "Nahimic",
    "adobeacrobatdccoreapp": "Adobe Acrobat DC",
    "adobeacrobatreadercoreapp": "Adobe Acrobat Reader DC",
    "adobenotificationclient": "Adobe Notification Client",
    "appup.intelarcsoftware": "Intel Arc Software",
    "appup.intelconnectivityperformancesuite": "Intel Connectivity Performance Suite",
    "appup.intelgraphicsexperience": "Intel Graphics Experience",
    "appup.inteloptanememoryandstoragemanagement": "Intel Optane Memory and Storage Management",
    "appup.thunderboltcontrolcenter": "Thunderbolt Control Center",
    "claude": "Claude",
    "dell.supportassistforpcs": "Dell SupportAssist",
    "dolbylaboratories.dolbyaccess": "Dolby Access",
    "dolbylaboratories.dolbyaccessoem": "Dolby Access OEM",
    "dolbylaboratories.dolbyatmosspeakersystem": "Dolby Atmos Speaker System",
    "dolbylaboratories.dolbyaudio": "Dolby Audio",
    "dolbylaboratories.dolbydigitalplusdecoderoem": "Dolby Digital Plus Decoder OEM",
    "dolbylaboratories.dolbyvisionhdr": "Dolby Vision HDR",
    "dropboxinc.dropbox": "Dropbox",
    "e046963f.lenovocompanion": "Lenovo Vantage",
    "e046963f.lenovosettingsforenterprise": "Lenovo Commercial Vantage",
    "e046963f.lenovovoiceworldwide": "Lenovo Voice",
    "e0469640.lenovoutility": "Lenovo Hotkeys",
    "elanmicroelectronicscorpo.trackpoint": "ELAN TrackPoint",
    "elevoctechnologyco.ltd.smartmicrophonesettings": "Smart Microphone Settings",
    "goodix.goodixfingerprintreaderprebootmanager": "Goodix Fingerprint Reader Preboot Manager",
    "mcafeewpssparsepackage": "McAfee WPS Sparse Package",
    "mirametrixinc.glancebymirametrix": "Glance by Mirametrix",
    "nvidiacorp.nvidiacontrolpanel": "NVIDIA Control Panel",
    "realteksemiconductorcorp.realtekaudiocontrol": "Realtek Audio Control",
    "synapticsincorporated.241916f58d6e7": "Synaptics Touchpad Driver",
    "synapticsincorporated.synapticscontrolpanel": "Synaptics Control Panel",
    "wacomtechnologycorp.157535b83c264": "Wacom Device Component",
    "wavesaudio.maxxaudioprofordell2022": "Waves MaxxAudio Pro for Dell",
    "4505fortemedia.fmapocontrol": "Fortemedia FMAPO Control",
    "microsoftteams": "Microsoft Teams",
    "microsoft.549981c3f5f10": "Cortana",
    "microsoft.6365217ce6eb4": "Microsoft 365 (Office Hub)",
    "7ee7776c.linkedinforwindows": "LinkedIn for Windows",
    "goodnoteslimited.goodnotesforwindows": "GoodNotes for Windows",
    "amazonvideo.primevideo": "Amazon Prime Video",
    "nearbysharelauncher": "Quick Share (Nearby Share)",
    "microsoft.worldnationalparks": "Windows Desktop Theme (World National Parks)",
    "microsoft.amazonrainforest": "Windows Desktop Theme (Amazon Rainforest)",
    "microsoft.mountaindwellings": "Windows Desktop Theme (Mountain Dwellings)",
    "microsoft.languageexperiencepack": "Windows Language Experience Pack",
    "microsoft.languageexperiencepacken-gb": "Windows Language Experience Pack (en-GB)",
    "microsoft.languageexperiencepackmr-in": "Windows Language Experience Pack (mr-IN)",
    "microsoft.ink.handwriting": "Windows Handwriting Component",
    "microsoft.ink.handwriting.en-in.1.0": "Windows Handwriting Component (en-IN)",
    "microsoft.ink.handwriting.en-us.1.0": "Windows Handwriting Component (en-US)",
    "microsoft.ink.handwriting.main.en-in.1.0.1": "Windows Handwriting Component (en-IN)",
    "microsoft.ink.handwriting.main.en-us.1.0.1": "Windows Handwriting Component (en-US)",
    "microsoft.wallet": "Windows Wallet",
    "microsoft.rawimageextension": "Raw Image Extension",
    "microsoft.windowsscan": "Windows Scan",
    "microsoft.windows.callingshellapp": "Windows System Component (CallingShellApp)",
    "microsoft.windows.augloop.cbs": "Windows System Component (AugLoop.CBS)",
    "microsoft.windows.search": "Windows System Component (Search)",
    "microsoft.windows.sechealthui": "Windows Security",
    "microsoft.teams.slimcorevdi": "Microsoft Teams VDI Component",
    "microsoft.teams.slimcorevdifwk": "Microsoft Teams VDI Component",
    "microsoft.teams.slimcorevdihost": "Microsoft Teams VDI Component",
    "microsoft.ppiprojection": "Windows System Component (PPIProjection)",
    "microsoft.advertising.xaml": "Windows System Component (Advertising.Xaml)",
    "microsoft.companyportal": "Microsoft Intune Company Portal",
    "microsoft.directxruntime": "DirectX Runtime",
    "microsoft.services.store.engagement": "Windows Store Engagement Framework",
    "microsoft.ui.xaml": "WinUI Xaml Runtime",
    "microsoft.vclibs": "Visual C++ UWP Runtime",
    "microsoft.winappruntime": "Windows App Runtime",
    "microsoftcorporationii.winappruntime": "Windows App Runtime",
    "windowsappruntime": "Windows App Runtime",
    "winappruntime": "Windows App Runtime",
    "microsoft.windowsappruntime": "Windows App Runtime",
    "microsoft.net.native.framework": ".NET Native Framework",
    "microsoft.net.native.runtime": ".NET Native Runtime",
    "windows_ie_ac_001": "Windows System Component (IE Access Control)",
    "com.microsoft.openxml": "Open XML SDK",
    "4df9e0f8.netflix": "Netflix",
    "ad2f1837.hpprintercontrol": "HP Smart",
    "d91e29cf.wacomnotes": "Wacom Notes",
    "pulsesecurereactapppkg": "Pulse Secure",
    "samsungelectronicsco.ltd.samsungprinterexperience": "Samsung Printer Experience",
    "f.luxsoftwarellc.f.lux": "f.lux",
    "microsoft.skypeapp": "Skype",
    "microsoft.xboxapp": "Xbox app for Windows",
    "microsoft.microsoft3dviewer": "3D Viewer",
    "microsoft.mspaint": "Windows Paint",
    "microsoft.getstarted": "Windows Get Started (Tips)",
    "microsoft.winget.platform.source": "Windows Package Manager Source (winget) V2",
    "microsoft.midi.gmdls": "Windows System Component (General MIDI Soundbank)",
    "microsoftwindows.speech": "Windows Speech Recognition Component",
    "microsoft.windows.cortana": "Cortana",
    "docs": "Google Docs",
    "sheets": "Google Sheets",
    "slides": "Google Slides",
    "gmail": "Gmail",
    "youtube": "YouTube",
    "youtube music": "YouTube Music",
    "facebook": "Facebook",
    "linkedin": "LinkedIn",
    "adobeacrobatreaderdc": "Adobe Acrobat Reader",
    "notepadplusplus": "Notepad++",
    "57495kankaria.luminous": "Luminous",
    "adobesystemsincorporated.adobecreativecloudexpress": "Adobe Creative Cloud Express",
    "telegrammessengerllp.telegramdesktop": "Telegram Desktop",
    "www.instagram.com-e4b7766f": "Instagram",
    "riot vanguard": "Riot Vanguard",
    "valorant": "VALORANT",
    "riot client": "Riot Client",
    "cmake": "CMake",
    "bonjour": "Bonjour",
    "aws command line interface v2": "AWS Command Line Interface v2",
    "warp": "Warp",
    "legion arena": "Legion Arena",
    "tlauncher": "TLauncher",
    "avast update helper": "Avast Update Helper",
    "webadvisor by mcafee": "WebAdvisor by McAfee",
    "wondershare helper compact 2.6.0": "Wondershare Helper Compact",
    "launcher prerequisites": "Epic Games Launcher Prerequisites",
    "create react app sample": "Create React App Sample",

    # --- Browsers ---
    "mozilla.firefox": "Mozilla Firefox",
    "mozilla.firefox.esr": "Mozilla Firefox ESR",
    "mozilla.thunderbird": "Mozilla Thunderbird",
    "google.chrome": "Google Chrome",
    "google.chrome.canary": "Google Chrome Canary",
    "google.chrome.dev": "Google Chrome Dev",
    "google.chrome.beta": "Google Chrome Beta",
    "opera.opera": "Opera",
    "opera.operagx": "Opera GX",
    "brave.brave": "Brave Browser",
    "bravesoftware.bravebrowser": "Brave Browser",
    "vivaldi.vivaldi": "Vivaldi",
    "coccoc.coccoc": "Coc Coc",
    "frontmotion.firefox": "FrontMotion Firefox Community Edition",

    # --- Cloud Storage & Collaboration ---
    "dropbox.dropbox": "Dropbox",
    "box.box": "Box",
    "box.boxdrive": "Box Drive",
    "box.boxsync": "Box Sync",
    "slacktechnologies.slack": "Slack",
    "discord.discord": "Discord",

    # --- Consumer & Social ---
    "spotify.spotify": "Spotify",
    "spotifyab.spotifymusic": "Spotify",
    "meta.whatsapp": "WhatsApp",
    "meta.messenger": "Messenger",
    "meta.instagram": "Instagram",
    "strava.strava": "Strava",
    "netflix.netflix": "Netflix",
    "linkedin.linkedin": "LinkedIn",

    # --- Office & Productivity ---
    "thedocumentfoundation.libreoffice": "LibreOffice",
    "libreoffice.libreoffice": "LibreOffice",
    "notion.notion": "Notion",
    "canva.canva": "Canva",
    "figma.figma": "Figma",

    # --- Developer & Data Tools ---
    "postman.postman": "Postman",
    "postgresql.postgresql": "PostgreSQL",
    "redhat.podman": "Podman",
    "redhat.podman-desktop": "Podman Desktop",
    "timkosse.filezilla.client": "FileZilla",
    "filezilla.filezilla": "FileZilla",
    "eclipse.eclipse": "Eclipse IDE",
    "eclipseadoptium.temurin.17.jdk": "Eclipse Temurin JDK 17",
    "eclipseadoptium.temurin.21.jdk": "Eclipse Temurin JDK 21",
    "git.git": "Git",
    "7zip.7zip": "7-Zip",
    "igorpavlov.7zip": "7-Zip",
    "rarlab.winrar": "WinRAR",
    "anysphere.cursor": "Cursor",
    "notepad++.notepad++": "Notepad++",
    "videolan.vlc": "VLC media player",
    "gams.gams": "GAMS",
    "mendix.modeler": "Mendix Studio Pro",
    "oracle.java": "Java Runtime Environment",
    "mongodb.compass": "MongoDB Compass",
    "openjs.nodejs": "Node.js",
    "openjs.nodejs.lts": "Node.js LTS",
    "microsoft.dotnet": ".NET SDK",
    "openssl.openssl": "OpenSSL",
    "apache.httpd": "Apache HTTP Server",
    "insecure.nmap": "Nmap",
    "nmap.nmap": "Nmap",
    "ngrok.ngrok": "Ngrok",
    "ollama.ollama": "Ollama",
    "perplexity.perplexity": "Perplexity",

    # --- Creative & Media ---
    "thefoundry.nuke": "The Foundry Nuke",
    "foundry.nuke": "The Foundry Nuke",
    "descript.descript": "Descript",
    "moritzbunkus.mkvtoolnix": "MKVToolNix",
    "steelseries.gg": "SteelSeries GG",
    "dolby.dolbyaccess": "Dolby Access",
    "obsproject.obsstudio": "OBS Studio",
    "krita.krita": "Krita",

    # --- Security & Endpoint ---
    "cisco.anyconnect": "Cisco AnyConnect Secure Mobility Client",
    "cisco.ciscoanyconnectsecuremobilityclient": "Cisco AnyConnect Secure Mobility Client",
    "cisco.webex": "Cisco Webex",
    "cisco.ciscowebexmeetings": "Cisco Webex Meetings",
    "broadcom.symantec": "Symantec Endpoint Protection",
    "fortinet.forticlient": "FortiClient",
    "fortinet.forticlientvpn": "FortiClient VPN",
    "mcafee.mcafee": "McAfee Total Protection",
    "sophos.endpoint": "Sophos Endpoint",
    "tenable.nessus": "Nessus Agent",
    "pulsesecure.pulsesecure": "Pulse Secure",
    "splunk.universalforwarder": "Splunk Universal Forwarder",

    # --- Hardware & OEM ---
    "nvidia.geforceexperience": "NVIDIA GeForce Experience",
    "lenovo.vantage": "Lenovo Vantage",
    "dell.commandupdate": "Dell Command Update",
    "hp.supportassistant": "HP Support Assistant",
    "intel.graphicscommandcenter": "Intel Graphics Command Center",
    "amd.radeonsoftware": "AMD Radeon Software",
    "realtek.audiocontrol": "Realtek Audio Control",
    "logitech.ghub": "Logitech G HUB",
    "logitech.logioptionsplus": "Logi Options+",
    "gigabyte.controlcenter": "Gigabyte Control Center",
    "wacom.wacomtablet": "Wacom Tablet Driver",

    # --- Misc Utilities ---
    "corel.coreldraw": "CorelDRAW",
    "corel.winzip": "WinZip",
    "winzip.winzip": "WinZip",
    "bittorrent.bittorrent": "BitTorrent",
    "zoho.manageengine": "ManageEngine Desktop Central",
    "epicgames.epicgameslauncher": "Epic Games Launcher",
    "teamviewer.teamviewer": "TeamViewer",
    "piriform.ccleaner": "CCleaner",
    "qbittorrent.qbittorrent": "qBittorrent",
    "servicenow.agent": "ServiceNow Agent",
}

# Regex to safely remove architecture and installer noise
ARCH_SUFFIX_PATTERN = re.compile(
    r"\s*[\(\[]?\s*(?:64[\-\s]*bit|32[\-\s]*bit|x64|x86|amd64|arm64|ia32)\s*[\)\]]?",
    re.IGNORECASE
)
INSTALLER_SUFFIX_PATTERN = re.compile(
    r"\s*[\(\[]?\s*(?:installer|setup|package|standalone)\s*[\)\]]?",
    re.IGNORECASE
)
LANG_SUFFIX_PATTERN = re.compile(
    r"\s*[\(\[]?\s*(?:en[\-\s]*us|multilingual|all\s+languages)\s*[\)\]]?",
    re.IGNORECASE
)
GUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE
)


class DetectionNormalizer:
    """
    Normalizes raw detected application identity properties.
    """

    @classmethod
    def normalize_publisher(cls, raw_publisher: Optional[str], raw_name: Optional[str] = None) -> Optional[str]:
        """
        Maps publisher name variations and GUIDs to canonical vendor representation.
        Enforces Step 2: Vendor GUIDs resolved or marked UNKNOWN.
        """
        # First priority: If raw_name clearly indicates a third-party OEM hardware driver or store vendor,
        # never let a generic store/host publisher like 'Microsoft' or 'Microsoft Corporation' hijack it!
        if raw_name:
            low_name = raw_name.lower().strip()
            if "apple" in low_name or "usbaapl" in low_name or "bonjour" in low_name:
                return "Apple Inc."
            elif "silicon laboratories" in low_name or "silabenm" in low_name:
                return "Silicon Laboratories"
            elif "realtek" in low_name:
                return "Realtek Semiconductor Corp"
            elif "crowdstrike" in low_name:
                return "CrowdStrike, Inc."
            elif "corel" in low_name:
                return "Corel"
            elif "snow inventory" in low_name:
                return "Snow Software / Flexera"
            elif "google workspace" in low_name or "nearbyshare" in low_name:
                return "Google"
            elif "hp pc hardware diagnostics" in low_name or low_name.startswith("hp ") or "laserjet" in low_name or "omen gaming" in low_name:
                return "HP"
            elif low_name.startswith("advancedmicrodevices") or "amdradeon" in low_name or "amd radeon" in low_name or "ryzenmaster" in low_name or "amd psp" in low_name or "amd_chipset" in low_name or "amd chipset" in low_name or "amd sbxxx" in low_name or "amd i2c" in low_name or "amd gpio2" in low_name or "amd dvr64" in low_name or "amd wvr64" in low_name or "amd user experience" in low_name or "amd settings" in low_name or "amd ryzen" in low_name:
                return "Advanced Micro Devices, Inc. (AMD)"
            elif low_name.startswith("appup.") or "intelarc" in low_name or "intelconnectivity" in low_name or "inteloptane" in low_name or "thunderboltcontrol" in low_name or "intel graphics" in low_name or "intel(r) processor graphics" in low_name:
                return "Intel Corporation"
            elif low_name.startswith("dolbylaboratories") or "dolby" in low_name:
                return "Dolby Laboratories"
            elif low_name.startswith("e046963") or low_name.startswith("e046964") or "lenovo" in low_name or "legion arena" in low_name:
                return "Lenovo"
            elif low_name.startswith("elanmicro") or "trackpoint" in low_name:
                return "ELAN Microelectronics"
            elif low_name.startswith("elevoc") or "smartmicrophonesettings" in low_name:
                return "Elevoc Technology Co., Ltd."
            elif low_name.startswith("goodix") or "goodixfingerprint" in low_name:
                return "Goodix"
            elif low_name.startswith("goodnotes"):
                return "GoodNotes Limited"
            elif low_name.startswith("4505fortemedia") or "fortemedia" in low_name or "fmapocontrol" in low_name:
                return "Fortemedia"
            elif low_name.startswith("mirametrix") or "glancebymirametrix" in low_name:
                return "Mirametrix"
            elif low_name.startswith("nvidiacorp") or "nvidiacontrolpanel" in low_name or "nvidia" in low_name or "nvapp" in low_name or "nvcontainer" in low_name or "nvdlisr" in low_name or "shadowplay" in low_name or "frameview" in low_name:
                return "NVIDIA Corporation"
            elif low_name.startswith("synaptics") or "synapticscontrolpanel" in low_name:
                return "Synaptics"
            elif low_name.startswith("wacom") or "wacomtechnologycorp" in low_name:
                return "Wacom"
            elif low_name.startswith("wavesaudio") or "maxxaudiopro" in low_name:
                return "Waves Audio / Dell"
            elif low_name.startswith("mcafeewps") or "mcafee" in low_name or "webadvisor" in low_name:
                return "McAfee, LLC"
            elif low_name.startswith("claude"):
                return "Anthropic"
            elif low_name.startswith("dropbox"):
                return "Dropbox"
            elif low_name.startswith("dell.supportassist"):
                return "Dell"
            elif low_name.startswith("adobeacrobat") or low_name.startswith("adobenotification") or "adobecreativecloudexpress" in low_name or low_name.startswith("adobesystems"):
                return "Adobe Inc."
            elif low_name.startswith("a-volute") or "nahimic" in low_name:
                return "A-Volute"
            elif "amazon rainforest" in low_name or "amazonrainforest" in low_name:
                return "Microsoft Windows"
            elif "aws command line" in low_name or "aws cli" in low_name:
                return "Amazon Web Services, Inc."
            elif "riot games" in low_name or "riot client" in low_name or "riot vanguard" in low_name or "valorant" in low_name:
                return "Riot Games, Inc."
            elif "cmake" in low_name:
                return "Kitware, Inc."
            elif "mysql" in low_name:
                return "Oracle Corporation"
            elif "tlauncher" in low_name:
                return "TLauncher"
            elif "avast" in low_name:
                return "Gen Digital Inc. / Avast"
            elif "wondershare" in low_name:
                return "Wondershare Technology Co., Ltd."
            elif "create react app" in low_name:
                return "Meta Platforms, Inc. / Open Source Community"
            elif low_name == "warp" or low_name.startswith("warp ") or "warp terminal" in low_name:
                return "Warp, Inc."
            elif "57495kankaria" in low_name or "kankaria" in low_name:
                return "Kankaria"
            elif "telegram" in low_name:
                return "Telegram Messenger LLP"
            elif "instagram" in low_name:
                return "Meta Platforms, Inc."
            elif "launcher prerequisites" in low_name:
                return "Epic Games, Inc."
            elif low_name in ("docs", "sheets", "slides", "gmail", "youtube", "youtube music") or "google docs" in low_name or "google sheets" in low_name or "google slides" in low_name:
                return "Google"
            elif low_name == "facebook" or low_name.startswith("facebook"):
                return "Meta Platforms, Inc."
            elif low_name.startswith("4df9e0f8.netflix") or "netflix" in low_name:
                return "Netflix, Inc."
            elif low_name.startswith("ad2f1837.hp") or "hpprintercontrol" in low_name:
                return "HP"
            elif low_name.startswith("d91e29cf.wacom") or "wacomnotes" in low_name:
                return "Wacom"
            elif low_name.startswith("samsungelectronics") or "samsungprinter" in low_name:
                return "Samsung Electronics"
            elif "pulsesecurereact" in low_name:
                return "Ivanti"
            elif "f.lux" in low_name:
                return "f.lux"

        if not raw_publisher or raw_publisher.strip().lower() in ("unknown", "none", ""):
            if raw_name:
                # Priority 0: Auto-infer publisher from Winget Publisher.Product format
                # e.g., 'Mozilla.Firefox', 'Logitech.GHub', 'FrontMotion.Firefox', 'qBittorrent.qBittorrent'
                if "." in raw_name and not any(raw_name.lower().endswith(ext) for ext in [".exe", ".msi", ".dll", ".com", ".org", ".net", ".io", ".app", ".bat", ".cmd"]):
                    dot_parts = raw_name.split(".")
                    if len(dot_parts) >= 2:
                        pub_cand = dot_parts[0].strip()
                        norm_cand = cls.normalize_publisher(pub_cand)
                        if norm_cand and norm_cand != "UNKNOWN":
                            return norm_cand

                low_name = raw_name.lower().strip()
                if "amazon rainforest" in low_name or "amazonrainforest" in low_name:
                    return "Microsoft Windows"
                elif "aws command line" in low_name or "aws cli" in low_name:
                    return "Amazon Web Services, Inc."
                elif low_name.startswith("57540amzn") or "amazon" in low_name:
                    return "Amazon"
                elif low_name.startswith("clipchamp."):
                    return "Microsoft Corporation"
                elif low_name.startswith("pythonsoftware") or "python" in low_name:
                    return "Python Software Foundation"
                elif "riot games" in low_name or "riot client" in low_name or "riot vanguard" in low_name or "valorant" in low_name:
                    return "Riot Games, Inc."
                elif "cmake" in low_name:
                    return "Kitware, Inc."
                elif "bonjour" in low_name or "apple" in low_name or "usbaapl" in low_name:
                    return "Apple Inc."
                elif "mysql" in low_name:
                    return "Oracle Corporation"
                elif "nvidia" in low_name or "nvapp" in low_name or "nvcontainer" in low_name or "nvdlisr" in low_name or "shadowplay" in low_name or "frameview" in low_name:
                    return "NVIDIA Corporation"
                elif "amd" in low_name or "ryzen" in low_name:
                    return "Advanced Micro Devices, Inc. (AMD)"
                elif "legion arena" in low_name:
                    return "Lenovo"
                elif "tlauncher" in low_name:
                    return "TLauncher"
                elif "avast" in low_name:
                    return "Gen Digital Inc. / Avast"
                elif "webadvisor" in low_name or "mcafee" in low_name:
                    return "McAfee, LLC"
                elif "wondershare" in low_name:
                    return "Wondershare Technology Co., Ltd."
                elif "create react app" in low_name:
                    return "Meta Platforms, Inc. / Open Source Community"
                elif low_name == "warp" or low_name.startswith("warp ") or "warp terminal" in low_name:
                    return "Warp, Inc."
                elif "57495kankaria" in low_name or "kankaria" in low_name:
                    return "Kankaria"
                elif "adobecreativecloudexpress" in low_name or "adobesystems" in low_name:
                    return "Adobe Inc."
                elif "instagram" in low_name:
                    return "Meta Platforms, Inc."
                elif "telegram" in low_name:
                    return "Telegram Messenger LLP"
                elif "launcher prerequisites" in low_name:
                    return "Epic Games, Inc."
                elif low_name.startswith("microsoft.") or low_name.startswith("microsoftwindows.") or low_name.startswith("microsoftcorporation") or low_name.startswith("windows."):
                    return "Microsoft Windows" if "system component" in low_name or "windows." in low_name else "Microsoft"

                # Browsers & Internet Tools
                elif "frontmotion" in low_name:
                    return "FrontMotion"
                elif "firefox" in low_name or "mozilla" in low_name or "thunderbird" in low_name:
                    return "Mozilla"
                elif "opera" in low_name:
                    return "Opera Software"
                elif "brave" in low_name:
                    return "Brave Software Inc"
                elif "vivaldi" in low_name:
                    return "Vivaldi Technologies"
                elif "chrome" in low_name or "google" in low_name or "chromium" in low_name:
                    return "Google"
                elif "coccoc" in low_name:
                    return "Coc Coc"

                # Cloud & Collaboration
                elif "dropbox" in low_name:
                    return "Dropbox"
                elif "box" in low_name and ("sync" in low_name or "drive" in low_name or low_name == "box"):
                    return "Box"
                elif "slack" in low_name:
                    return "Slack"
                elif "discord" in low_name:
                    return "Discord Inc."
                elif "notion" in low_name:
                    return "Notion Labs, Inc."

                # Security & Enterprise
                elif "cisco" in low_name or "webex" in low_name or "anyconnect" in low_name:
                    return "Cisco Systems, Inc."
                elif "fortinet" in low_name or "forticlient" in low_name:
                    return "Fortinet, Inc."
                elif "splunk" in low_name:
                    return "Splunk, Inc."
                elif "broadcom" in low_name or "symantec" in low_name:
                    return "Broadcom"

                # Productivity & Office
                elif "libreoffice" in low_name or "documentfoundation" in low_name:
                    return "The Document Foundation"

                # Developer Tools & Databases
                elif "postman" in low_name:
                    return "Postman Inc."
                elif "postgresql" in low_name or "postgres" in low_name or "pgadmin" in low_name:
                    return "PostgreSQL Global Development Group"
                elif "filezilla" in low_name or "timkosse" in low_name:
                    return "FileZilla Project"
                elif "eclipse" in low_name:
                    return "Eclipse Foundation"
                elif "redhat" in low_name or "podman" in low_name:
                    return "Red Hat, Inc."
                elif re.search(r'\bgit\b', low_name):
                    return "The Git Development Community"
                elif "7-zip" in low_name or "7zip" in low_name or "igorpavlov" in low_name:
                    return "Igor Pavlov"
                elif "winrar" in low_name or "rarlab" in low_name:
                    return "win.rar GmbH"
                elif "notepad++" in low_name or "notepadplusplus" in low_name:
                    return "Don Ho"
                elif "vlc" in low_name or "videolan" in low_name:
                    return "VideoLAN"
                elif "gams" in low_name:
                    return "GAMS Development Corp."
                elif "mendix" in low_name:
                    return "Mendix"
                elif "thefoundry" in low_name or "foundry" in low_name or "nuke" in low_name:
                    return "The Foundry"
                elif "descript" in low_name:
                    return "Descript"
                elif "mkvtoolnix" in low_name or "bunkus" in low_name:
                    return "MKVToolNix"
                elif "steelseries" in low_name:
                    return "SteelSeries"
                elif "spotify" in low_name:
                    return "Spotify"
                elif "netflix" in low_name:
                    return "Netflix, Inc."
                elif "strava" in low_name:
                    return "Strava"
                elif "figma" in low_name:
                    return "Figma"
                elif "canva" in low_name:
                    return "Canva Pty Ltd"
                elif "omnissa" in low_name:
                    return "Omnissa"
                elif "citrix" in low_name:
                    return "Citrix"
                elif "trellix" in low_name:
                    return "Trellix"
                elif "flexera" in low_name:
                    return "Flexera"
                elif "snow software" in low_name:
                    return "Snow Software"
                elif "anydesk" in low_name:
                    return "AnyDesk Software GmbH"
                elif "zscaler" in low_name:
                    return "Zscaler"
                elif "netskope" in low_name:
                    return "Netskope"
                elif "ivanti" in low_name or "pulsesecure" in low_name:
                    return "Ivanti"
                elif "zoho" in low_name or "manageengine" in low_name:
                    return "Zoho"
                elif "frontmotion" in low_name:
                    return "FrontMotion"
                elif "openssl" in low_name:
                    return "OpenSSL Project"
                elif "apache" in low_name:
                    return "Apache Software Foundation"
                elif "nmap" in low_name or "insecure" in low_name:
                    return "Insecure.Com LLC"
                elif "ngrok" in low_name:
                    return "Ngrok"
                elif "ollama" in low_name:
                    return "Ollama"
                elif "cursor" in low_name or "anysphere" in low_name:
                    return "Anysphere"
                elif "perplexity" in low_name:
                    return "Perplexity AI"
                elif "obsproject" in low_name or "obs studio" in low_name:
                    return "OBS Project"
                elif "krita" in low_name:
                    return "Krita Foundation"
                elif "sophos" in low_name:
                    return "Sophos"
                elif "tenable" in low_name or "nessus" in low_name:
                    return "Tenable"
                elif "dell" in low_name:
                    return "Dell"
                elif "hp" in low_name and ("smart" in low_name or "printer" in low_name or "support" in low_name):
                    return "HP"
                elif "gigabyte" in low_name:
                    return "Gigabyte"
                elif "wacom" in low_name:
                    return "Wacom"
                elif "corel" in low_name:
                    return "Corel"
                elif "winzip" in low_name:
                    return "WinZip Computing"
                elif "qbittorrent" in low_name:
                    return "qBittorrent"
                elif "bittorrent" in low_name:
                    return "BitTorrent"
                elif "teamviewer" in low_name:
                    return "TeamViewer"
                elif "ccleaner" in low_name or "piriform" in low_name:
                    return "CCleaner"
                elif "servicenow" in low_name:
                    return "ServiceNow"
            return "UNKNOWN"

        norm = " ".join(raw_publisher.strip().split())
        lower_key = norm.lower()

        # Check exact canonical map first
        if lower_key in PUBLISHER_CANONICAL_MAP:
            return PUBLISHER_CANONICAL_MAP[lower_key]

        # Check alphanumeric-stripped key (resolves PascalCase/joined publisher keys like TheDocumentFoundation, MoritzBunkus)
        clean_key = re.sub(r'[^a-z0-9]', '', lower_key)
        if clean_key:
            for cand_k, cand_val in PUBLISHER_CANONICAL_MAP.items():
                if re.sub(r'[^a-z0-9]', '', cand_k) == clean_key:
                    return cand_val

        # Check third-party publisher rules (substring / regex) in priority order
        for rule in VENDOR_NORMALIZATION_RULES:
            if rule.match_type == "exact":
                continue
            if rule.match_type == "contains":
                if rule.pattern in lower_key:
                    return rule.canonical_vendor
            elif rule.match_type == "regex":
                if re.search(rule.pattern, norm, re.IGNORECASE):
                    return rule.canonical_vendor

        # Check GUID mapping first
        if lower_key in GUID_PUBLISHER_MAP:
            return GUID_PUBLISHER_MAP[lower_key]

        # If it matches raw GUID pattern and is not in mapping -> UNKNOWN
        if GUID_PATTERN.match(norm):
            return "UNKNOWN"

        # Check Debian / Ubuntu package maintainer formats (e.g. email lists)
        if "lists.ubuntu.com" in lower_key or "ubuntu developers" in lower_key:
            return "Ubuntu Community"
        if "canonical" in lower_key or "canonical.com" in lower_key:
            return "Canonical"
        if "debian.org" in lower_key or "debian qa" in lower_key:
            return "Debian Project"
        if "gnu.org" in lower_key or "free software foundation" in lower_key:
            return "Free Software Foundation"

        return norm

    @classmethod
    def normalize_name(cls, raw_name: str, install_location: Optional[str] = None) -> str:
        """
        Normalizes application name by resolving raw package names and removing architecture, language, and installer suffixes.
        Example: '57540AMZNMobileLLC.AmazonAlexa' -> 'Amazon Alexa'
        Example: 'Adobe Acrobat Pro (64-bit)' -> 'Adobe Acrobat Pro'
        """
        if not raw_name:
            return ""

        # Check install location first for WindowsApps and SystemApps packages
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
                if clean_pkg_low in PACKAGE_NAME_CANONICAL_MAP:
                    return PACKAGE_NAME_CANONICAL_MAP[clean_pkg_low]
                if "systemapps" in loc_low:
                    clean_title = clean_pkg.replace("microsoftwindows.", "").replace("microsoft.", "").replace("windows.", "")
                    return f"Windows System Component ({clean_title})"

        # Strip registry delimiter prefix noise (e.g., "itooTechnologies| Microsoft Teams" -> "Microsoft Teams")
        clean_raw = raw_name
        if "|" in clean_raw:
            clean_raw = clean_raw.split("|")[-1].strip()

        # Fix known mojibake occurrences
        clean_raw = clean_raw.replace("Â®", "®").replace("â„¢", "™").replace("Â©", "©")

        # Normalize unicode NFKC
        s = unicodedata.normalize("NFKC", clean_raw).strip()

        # Handle full AppX package string stripping (e.g. Vendor.Package_1.0.0.0_x64__hash or Name_hash)
        pkg_base = re.sub(r"_\d+[\.\d]*_(?:x64|x86|arm64|neutral|arm)_[~_]*[a-z0-9]+$", "", s, flags=re.IGNORECASE).strip()
        pkg_base = re.sub(r"_[a-z0-9]{13,14}$", "", pkg_base, flags=re.IGNORECASE).strip()
        pkg_base_low = pkg_base.lower()

        if pkg_base_low in PACKAGE_NAME_CANONICAL_MAP:
            return PACKAGE_NAME_CANONICAL_MAP[pkg_base_low]

        for k, v in PACKAGE_NAME_CANONICAL_MAP.items():
            if pkg_base_low == k or pkg_base_low.startswith(f"{k}_") or pkg_base_low.startswith(f"{k}."):
                return v

        lower_key = s.lower()

        # Dedicated product normalizations for common ambiguous names
        if "acrobat" in lower_key and "reader" in lower_key:
            return "Adobe Acrobat Reader"
        if lower_key in ("docs", "google docs"):
            return "Google Docs"
        if lower_key in ("sheets", "google sheets"):
            return "Google Sheets"
        if lower_key in ("slides", "google slides"):
            return "Google Slides"
        if lower_key == "gmail":
            return "Gmail"
        if lower_key in ("youtube", "youtube web"):
            return "YouTube"
        if lower_key == "facebook":
            return "Facebook"

        # Check raw package name map
        if lower_key in PACKAGE_NAME_CANONICAL_MAP:
            return PACKAGE_NAME_CANONICAL_MAP[lower_key]

        # Check prefix/package-family in package name map
        for k, v in PACKAGE_NAME_CANONICAL_MAP.items():
            if lower_key.startswith(k) or (len(lower_key) > 8 and k.startswith(lower_key)):
                return v

        # Strip architecture suffixes
        s = ARCH_SUFFIX_PATTERN.sub("", s)
        # Strip installer noise
        s = INSTALLER_SUFFIX_PATTERN.sub("", s)
        # Strip language markers
        s = LANG_SUFFIX_PATTERN.sub("", s)

        # Clean multiple spaces and trim
        s = " ".join(s.split()).strip()

        # Check Winget / AppX Publisher.Product pattern (e.g. "Mozilla.Firefox" -> "Mozilla Firefox")
        if "." in s and not any(s.lower().endswith(ext) for ext in [".exe", ".msi", ".dll", ".com", ".org", ".net", ".io", ".app", ".bat", ".cmd", ".json", ".zip", ".tar", ".gz"]):
            dot_parts = [p.strip() for p in s.split(".") if p.strip()]
            if len(dot_parts) >= 2 and all(re.match(r"^[A-Za-z0-9_-]+$", p) for p in dot_parts):
                vendor_part, product_parts = dot_parts[0], dot_parts[1:]
                prod_name = " ".join(product_parts)
                if vendor_part.lower() == prod_name.lower():
                    s = vendor_part
                elif vendor_part.lower() in prod_name.lower():
                    s = prod_name
                else:
                    s = f"{vendor_part} {prod_name}"

        return s

    @classmethod
    def normalize_version(cls, raw_version: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        Normalizes version string and extracts major, minor, patch segments.
        Strips bitness suffixes (e.g. -64, -32, -x64, -x86) and cleans prefix noise.
        Returns: (normalized_version, major_version, minor_version, patch_version)
        """
        if not raw_version or not str(raw_version).strip() or str(raw_version).strip().lower() in ("n/a", "unknown", "none", ""):
            return None, None, None, None

        v_clean = str(raw_version).strip().lower()
        # Remove 'v' or 'ver' prefix
        v_clean = re.sub(r"^(?:v|ver|version)[\.\s]*", "", v_clean)
        # Replace each placeholder 'x' with '0'
        v_clean = re.sub(r"x", "0", v_clean)

        # Strip architecture and bitness suffixes (e.g. "-64", "-32", "-x64", "-x86", "_64")
        v_clean = re.sub(r"[\s\-_]+(?:64[\-\s]*bit|32[\-\s]*bit|x64|x86|amd64|arm64|ia32|64|32)$", "", v_clean, flags=re.IGNORECASE)

        # Match semantic components (digits separated by dots or dashes)
        parts = re.findall(r"\d+", v_clean)
        if parts:
            major = parts[0] if len(parts) > 0 else None
            minor = parts[1] if len(parts) > 1 else None
            patch = parts[2] if len(parts) > 2 else None
            normalized = ".".join(parts[:4])
            return normalized, major, minor, patch

        return str(raw_version).strip(), None, None, None

    @classmethod
    def versions_are_equivalent(cls, v1: Optional[str], v2: Optional[str]) -> bool:
        """
        Determines whether two version representations refer to the same version.
        Handles formatting differences such as '1.134.0' vs '1.0.134.0', '1.0' vs '1.0.0.0',
        bitness variations ('3.14-64' vs '3.14'), and Windows AppX four-part packaging formats.
        """
        if not v1 and not v2:
            return True
        if not v1 or not v2:
            return False

        norm1, _, _, _ = cls.normalize_version(v1)
        norm2, _, _, _ = cls.normalize_version(v2)

        if norm1 and norm2 and norm1 == norm2:
            return True

        s1 = str(v1).strip().lower()
        s2 = str(v2).strip().lower()
        if s1 == s2:
            return True

        # Extract numeric components after normalization
        p1 = [int(x) for x in re.findall(r"\d+", norm1 or s1)]
        p2 = [int(x) for x in re.findall(r"\d+", norm2 or s2)]

        if not p1 or not p2:
            return False

        if p1 == p2:
            return True

        # Handle 4-part packaging where a 0 was inserted (e.g. 1.0.134.0 vs 1.134.0)
        # VS Code: 1.134.0 (major=1, minor=134, patch=0) vs 1.0.134.0 (major=1, build=0, minor=134, patch=0)
        # Check non-zero components equality
        non_zero_1 = [x for x in p1 if x != 0]
        non_zero_2 = [x for x in p2 if x != 0]
        if non_zero_1 and non_zero_1 == non_zero_2:
            return True

        # Check OneDrive style concat: e.g. [26, 150, 804, 11] vs [26150, 804, 11, 0]
        if len(p1) >= 2 and p1[0] * 1000 + p1[1] == (p2[0] if p2 else -1):
            if p1[2:] == [x for x in p2[1:] if x != 0][:len(p1[2:])]:
                return True
        if len(p2) >= 2 and p2[0] * 1000 + p2[1] == (p1[0] if p1 else -1):
            if p2[2:] == [x for x in p1[1:] if x != 0][:len(p2[2:])]:
                return True

        # Check prefix equality with trailing zeros (1.0 vs 1.0.0.0)
        p1_padded = list(p1)
        p2_padded = list(p2)
        while len(p1_padded) < 4:
            p1_padded.append(0)
        while len(p2_padded) < 4:
            p2_padded.append(0)

        return p1_padded == p2_padded
