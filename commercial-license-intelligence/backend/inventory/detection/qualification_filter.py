"""
Application Qualification Filter and Windows System Tool Filter.
Distinguishes genuine installed software products from:
- Windows system utilities & administrative tools
- Windows OS internal components, hosts, dialogs, broker plugins
- Technical runtime & framework dependencies
- Installer infrastructure & shared components
- Raw Start Menu shortcuts
"""

import re
import logging
from enum import Enum
from typing import Dict, Any, Tuple, Optional, Set

logger = logging.getLogger("qualification-filter")


class QualificationCategory(str, Enum):
    """Qualification categories for application inventory ingestion."""
    STANDALONE_APPLICATION = "STANDALONE_APPLICATION"
    OS_SYSTEM_COMPONENT = "OS_SYSTEM_COMPONENT"
    RUNTIME_FRAMEWORK = "RUNTIME_FRAMEWORK"
    SHARED_COMPONENT = "SHARED_COMPONENT"
    INSTALLER_INFRASTRUCTURE = "INSTALLER_INFRASTRUCTURE"
    UNKNOWN_APPLICATION = "UNKNOWN_APPLICATION"
    WEB_SHORTCUT_OR_PWA = "WEB_SHORTCUT/PWA"
    LINUX_SYSTEM_PACKAGE = "LINUX_SYSTEM_PACKAGE"
    MACOS_SYSTEM_COMPONENT = "MACOS_SYSTEM_COMPONENT"


class WindowsSystemToolFilter:
    """
    Dedicated filter to identify and reject Windows system utilities,
    administrative consoles, MMC snap-ins, and diagnostic tools from entering
    the commercial application inventory.
    """

    # Exact names (case-insensitive) of built-in Windows system tools & consoles
    SYSTEM_TOOL_NAMES: Set[str] = {
        "registry editor",
        "task manager",
        "event viewer",
        "computer management",
        "component services",
        "services",
        "task scheduler",
        "system configuration",
        "system information",
        "resource monitor",
        "disk cleanup",
        "character map",
        "performance monitor",
        "steps recorder",
        "dfrgui",
        "hyper-v manager",
        "iscsi initiator",
        "memory diagnostics tool",
        "odbc data sources",
        "odbc data sources (32-bit)",
        "odbc data sources (64-bit)",
        "print management",
        "recoverydrive",
        "recovery drive",
        "remote desktop connection",
        "command prompt",
        "windows powershell",
        "windows powershell (x86)",
        "windows powershell ise",
        "windows powershell ise (x86)",
        "livecaptions",
        "magnify",
        "narrator",
        "on-screen keyboard",
        "voiceaccess",
        "voice access",
        "control panel",
        "administrative tools",
        "windows tools",
        "security and maintenance",
        "defragment and optimize drives",
        "windows memory diagnostic",
        "run",
        "file explorer",
        "snipping tool (legacy)",
        "wsl",
        "wsl settings",
        "quick assist (legacy)",
    }

    # Regex patterns for MMC snap-ins and internal system utilities
    SYSTEM_TOOL_PATTERNS = [
        re.compile(r"\b(mmc|msc|snap-in|control panel|administrative tool)\b", re.IGNORECASE),
        re.compile(r"^(windows (powershell|memory diagnostic|tools|system|accessories|administrative))", re.IGNORECASE),
        re.compile(r"^(odbc data sources|iscsi initiator|recovery drive|disk cleanup|performance monitor)", re.IGNORECASE),
        re.compile(r"^(system configuration|system information|resource monitor|component services|computer management)", re.IGNORECASE),
        re.compile(r"^(event viewer|task scheduler|registry editor|steps recorder|character map)", re.IGNORECASE),
    ]

    # Executable filenames that represent built-in OS tools
    SYSTEM_TOOL_EXECUTABLES: Set[str] = {
        "regedit.exe", "taskmgr.exe", "eventvwr.exe", "compmgmt.msc", "comexp.msc",
        "services.msc", "taskschd.msc", "msconfig.exe", "msinfo32.exe", "resmon.exe",
        "cleanmgr.exe", "charmap.exe", "perfmon.exe", "psr.exe", "dfrgui.exe",
        "virtmgmt.msc", "iscsicpl.exe", "MdSched.exe", "odbcad32.exe", "printmanagement.msc",
        "RecoveryDrive.exe", "mstsc.exe", "cmd.exe", "powershell.exe", "powershell_ise.exe",
        "LiveCaptions.exe", "magnify.exe", "narrator.exe", "osk.exe", "voiceaccess.exe",
        "control.exe", "explorer.exe"
    }

    @classmethod
    def is_system_tool(cls, name: str, exe_path: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Determines whether an item is a built-in Windows system utility or administrative console.
        Returns: (is_system_tool, rejection_reason)
        """
        if not name:
            return True, "EMPTY_NAME"

        n_clean = name.strip().lower()

        # 1. Exact name match
        if n_clean in cls.SYSTEM_TOOL_NAMES:
            return True, f"BUILTIN_WINDOWS_SYSTEM_TOOL ({name})"

        # 2. Regex pattern match
        for pat in cls.SYSTEM_TOOL_PATTERNS:
            if pat.search(n_clean):
                return True, f"WINDOWS_SYSTEM_TOOL_PATTERN ({pat.pattern})"

        # 3. Executable binary match
        if exe_path:
            exe_base = exe_path.strip().split("\\")[-1].lower()
            if exe_base in cls.SYSTEM_TOOL_EXECUTABLES:
                return True, f"WINDOWS_SYSTEM_TOOL_BINARY ({exe_base})"

        return False, None


class WindowsSystemComponentFilter:
    """
    Dedicated filter to identify and exclude Windows internal operating-system components,
    hosts, dialogs, broker plugins, experience hosts, and system infrastructure packages
    from entering the commercial application inventory.
    """

    # Exact package names / canonical names / identifiers of Windows internal system components
    EXACT_SYSTEM_COMPONENT_NAMES: Set[str] = {
        "aad.brokerplugin",
        "microsoft.aad.brokerplugin",
        "accountscontrol",
        "microsoft.accountscontrol",
        "asynctextservice",
        "microsoft.asynctextservice",
        "bioenrollment",
        "microsoft.bioenrollment",
        "creddialoghost",
        "microsoft.creddialoghost",
        "win32webviewhost",
        "microsoft.win32webviewhost",
        "apprep.chxapp",
        "microsoft.windows.apprep.chxapp",
        "assignedaccesslockapp",
        "microsoft.windows.assignedaccesslockapp",
        "capturepicker",
        "microsoft.windows.capturepicker",
        "cloudexperiencehost",
        "microsoft.windows.cloudexperiencehost",
        "contentdeliverymanager",
        "microsoft.windows.contentdeliverymanager",
        "narratorquickstart",
        "microsoft.windows.narratorquickstart",
        "oobenetworkcaptiveportal",
        "microsoft.windows.oobenetworkcaptiveportal",
        "oobenetworkconnectionflow",
        "microsoft.windows.oobenetworkconnectionflow",
        "parentalcontrols",
        "microsoft.windows.parentalcontrols",
        "peopleexperiencehost",
        "microsoft.windows.peopleexperiencehost",
        "pinningconfirmationdialog",
        "microsoft.windows.pinningconfirmationdialog",
        "printqueueactioncenter",
        "microsoft.windows.printqueueactioncenter",
        "secureassessmentbrowser",
        "microsoft.windows.secureassessmentbrowser",
        "shellexperiencehost",
        "microsoft.windows.shellexperiencehost",
        "startmenuexperiencehost",
        "microsoft.windows.startmenuexperiencehost",
        "xgpuejectdialog",
        "microsoft.windows.xgpuejectdialog",
        "client.core",
        "microsoftwindows.client.core",
        "client.photon",
        "microsoftwindows.client.photon",
        "undockeddevkit",
        "microsoftwindows.undockeddevkit",
        "cbspreview",
        "windows.cbspreview",
        "printdialog",
        "windows.printdialog",
        "ecapp",
        "microsoft.ecapp",
        "lockapp",
        "microsoft.lockapp",
        "microsoftwindows.61869720.voiess",
        "microsoftwindows.61869721.livtop",
        "microsoftwindows.61869722.speion",
        "microsoftwindows.61869836.inpapp",
        "microsoftwindows.client.cbs",
        "microsoftwindows.client.coreai",
        "microsoftwindows.client.fileexp",
        "microsoftwindows.client.oobe",
        "aimgr",
        "windows ai manager",
        "store experience host",
        "start experiences app",
        "windows web experience pack",
        "f46d4000-fd22-4db4-ac8e-4e1ddde828fe",
        "addsuggestedfolderstolibrarydialog",
        "microsoft.edgedevtoolsclient",
        "microsoft edge devtools client",
        "microsoft windows application compatibility fix database",
        "immersivecontrolpanel",
        "windows.immersivecontrolpanel",
        "cbs",
        "core ai",
        "sec health ui",
        "microsoft.sechealthui",
    }

    # Regex patterns identifying internal OS components, experience hosts, dialog hosts, broker plugins
    SYSTEM_COMPONENT_PATTERNS = [
        re.compile(r"^windows system component", re.IGNORECASE),
        re.compile(r"\b(brokerplugin|experiencehost|dialoghost|capturepicker|pinningconfirmation|lockapp|ecapp)\b", re.IGNORECASE),
        re.compile(r"^microsoftwindows\.client\.", re.IGNORECASE),
        re.compile(r"^microsoftwindows\.\d+\.", re.IGNORECASE),
        re.compile(r"^windows\.(cbspreview|printdialog|immersivecontrolpanel)", re.IGNORECASE),
        re.compile(r"^microsoft\.(ecapp|lockapp|creddialoghost|win32webviewhost|accountscontrol|bioenrollment|asynctextservice|aad\.brokerplugin)", re.IGNORECASE),
        re.compile(r"^microsoft\.windows\.(apprep|assignedaccess|capturepicker|cloudexperience|contentdelivery|narratorquick|oobenetwork|parental|peopleexperience|pinning|printqueue|secureassessment|shellexperience|startmenu|xgpu)", re.IGNORECASE),
        re.compile(r"\b(inputapp|ksystemsharehost|ncsiuwpapp|readernotificationclient|crossdevice|activesync|ink\.handwriting)\b", re.IGNORECASE),
        re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_cw5n1h2txyewy$", re.IGNORECASE),
        re.compile(r"^f46d4000-fd22-4db4-ac8e-4e1ddde828fe", re.IGNORECASE),
    ]

    # Windows internal installation paths
    SYSTEM_INSTALL_PATHS = [
        re.compile(r"c:\\windows\\systemapps\\", re.IGNORECASE),
        re.compile(r"c:\\windows\\immersivecontrolpanel", re.IGNORECASE),
        re.compile(r"c:\\windows\\system32\\", re.IGNORECASE),
        re.compile(r"c:\\windows\\syswow64\\", re.IGNORECASE),
        re.compile(r"c:\\windows\\winsxs\\", re.IGNORECASE),
    ]

    @classmethod
    def is_system_component(
        cls,
        name: str,
        install_location: Optional[str] = None,
        package_name: Optional[str] = None,
        package_family: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Determines whether a candidate is a Windows OS system/internal component.
        Returns: (is_system_component, rejection_reason)
        """
        if not name:
            return False, None

        n_clean = name.strip().lower()
        pkg_clean = (package_name or "").strip().lower()
        fam_clean = (package_family or "").strip().lower()

        # 1. Exact name/ID match
        if n_clean in cls.EXACT_SYSTEM_COMPONENT_NAMES:
            return True, f"EXACT_WINDOWS_SYSTEM_COMPONENT ({name})"
        if pkg_clean in cls.EXACT_SYSTEM_COMPONENT_NAMES:
            return True, f"EXACT_WINDOWS_SYSTEM_COMPONENT_PKG ({package_name})"
        if fam_clean in cls.EXACT_SYSTEM_COMPONENT_NAMES:
            return True, f"EXACT_WINDOWS_SYSTEM_COMPONENT_FAM ({package_family})"

        # 2. System Component string prefix
        if n_clean.startswith("windows system component"):
            return True, f"WINDOWS_SYSTEM_COMPONENT_PREFIX ({name})"

        # 3. Pattern match on name or package
        for pat in cls.SYSTEM_COMPONENT_PATTERNS:
            if pat.search(n_clean):
                return True, f"WINDOWS_SYSTEM_COMPONENT_PATTERN ({pat.pattern})"
            if pkg_clean and pat.search(pkg_clean):
                return True, f"WINDOWS_SYSTEM_COMPONENT_PKG_PATTERN ({pat.pattern})"
            if fam_clean and pat.search(fam_clean):
                return True, f"WINDOWS_SYSTEM_COMPONENT_FAM_PATTERN ({pat.pattern})"

        # 4. System path check (e.g. C:\Windows\SystemApps)
        if install_location:
            loc_clean = install_location.strip().lower()
            for p_pat in cls.SYSTEM_INSTALL_PATHS:
                if p_pat.search(loc_clean):
                    # Check if it's an inbox app that lives in SystemApps but is standalone (rare, usually inbox apps are in WindowsApps)
                    return True, f"WINDOWS_SYSTEM_INSTALL_PATH ({install_location})"

        return False, None


class WindowsRuntimeFrameworkFilter:
    """
    Dedicated filter to identify and exclude technical runtime, framework, SDK,
    and shared dependency packages from the main application inventory.
    """

    # Regex patterns for runtime/framework dependency packages and developer targeting packs
    RUNTIME_PATTERNS = [
        re.compile(r"(winappruntime|windowsappruntime)", re.IGNORECASE),
        re.compile(r"(\.|\b)ui\.xaml(\.|\b)", re.IGNORECASE),
        re.compile(r"(\.|\b)ddlm(\.|\b)", re.IGNORECASE),
        re.compile(r"\.?net\s*native\s*(framework|runtime)", re.IGNORECASE),
        re.compile(r"(\.|\b)vclibs(\.|\b)", re.IGNORECASE),
        re.compile(r"visual\s*c\+\+.*uwp\s*(desktop\s*)?runtime", re.IGNORECASE),
        re.compile(r"engagement\s*framework", re.IGNORECASE),
        re.compile(r"services\.store\.engagement", re.IGNORECASE),
        re.compile(r"directx\s*(end-user\s*)?runtimes?", re.IGNORECASE),
        re.compile(r"widgets\s*platform\s*runtime", re.IGNORECASE),
        re.compile(r"(\.net\s*(?:apphost|targeting|framework.*targeting|framework.*multi-targeting)\s*pack)", re.IGNORECASE),
        re.compile(r"(microsoft\.net\.(?:sdk|workload)\..*manifest)", re.IGNORECASE),
        re.compile(r"(universal\s*crt\s*(?:extension|headers|redistributable|tools))", re.IGNORECASE),
        re.compile(r"(universal\s*general\s*midi\s*dls\s*extension)", re.IGNORECASE),
        re.compile(r"(winrt\s*intellisense)", re.IGNORECASE),
        re.compile(r"(windows\s*(?:desktop|iot|mobile|team)\s*extension\s*sdk)", re.IGNORECASE),
        re.compile(r"(windows\s*app\s*certification\s*kit)", re.IGNORECASE),
        re.compile(r"(application\s*verifier\s*x64\s*external\s*package)", re.IGNORECASE),
        re.compile(r"(kits\s*configuration\s*installer)", re.IGNORECASE),
        re.compile(r"(msi\s*development\s*tools)", re.IGNORECASE),
        re.compile(r"(icecap_collection|diagnosticshub_collectionservice|intellitraceprofilerproxy)", re.IGNORECASE),
        re.compile(r"^(vs_|sptools_)", re.IGNORECASE),
        re.compile(r"wix\s*toolset.*(?:native|managed)\s*sdk", re.IGNORECASE),
        re.compile(r"^vcpp_crt\.redist", re.IGNORECASE),
    ]

    # Exact names (case-insensitive) of known runtime packages
    EXACT_RUNTIME_NAMES: Set[str] = {
        "microsoft visual c++ 2015 uwp desktop runtime package",
        "microsoft visual c++ 2015 uwp runtime package",
        "microsoft .net native framework package 2.2",
        "microsoft .net native runtime package 2.2",
        "microsoft engagement framework",
        "widgets platform runtime",
        "winappdeploy",
    }

    @classmethod
    def is_runtime_or_framework(cls, name: str, pkg_name: Optional[str] = None, pkg_fam: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Determines whether a candidate represents a technical runtime or framework dependency.
        Returns: (is_runtime, rejection_reason)
        """
        if not name:
            return False, None

        n_clean = name.strip().lower()
        if n_clean in cls.EXACT_RUNTIME_NAMES:
            return True, f"EXACT_RUNTIME_NAME ({name})"

        for pat in cls.RUNTIME_PATTERNS:
            if pat.search(n_clean):
                return True, f"RUNTIME_FRAMEWORK_PATTERN ({pat.pattern})"
            if pkg_name and pat.search(str(pkg_name)):
                return True, f"RUNTIME_FRAMEWORK_PKG ({pkg_name})"
            if pkg_fam and pat.search(str(pkg_fam)):
                return True, f"RUNTIME_FRAMEWORK_PKG_FAMILY ({pkg_fam})"

        return False, None


class WindowsOSUpdateFilter:
    """Filter to identify Windows OS patches, updates, servicing stacks, and KBs."""

    KB_PATTERNS = [
        re.compile(r"(?:^|\b)(?:update for|security update for|hotfix for|servicing stack update)\b", re.IGNORECASE),
        re.compile(r"\(kb\d{6,}\)", re.IGNORECASE),
        re.compile(r"\bkb\d{6,}\b", re.IGNORECASE),
        re.compile(r"^windows\s*(?:rt\s*)?[\d\.]+\s*(?:and\s*windows\s*server\s*[\d\s]+)?\s*update\s*:", re.IGNORECASE),
        re.compile(r"^update for universal c runtime in windows", re.IGNORECASE),
        re.compile(r"microsoft security advisory:.*(?:availability of sha-2|update)", re.IGNORECASE),
    ]

    @classmethod
    def is_os_update_or_patch(cls, name: str) -> Tuple[bool, Optional[str]]:
        if not name:
            return False, None
        n_clean = name.strip().lower()
        for pat in cls.KB_PATTERNS:
            if pat.search(n_clean):
                return True, f"WINDOWS_OS_UPDATE_PATCH ({name})"
        return False, None


class WindowsDriverFilter:
    """Filter to identify Windows hardware device drivers and OEM peripheral software."""

    DRIVER_PATTERNS = [
        re.compile(r"^windows driver package\b", re.IGNORECASE),
        re.compile(r"\bdriver package\b", re.IGNORECASE),
        re.compile(r".*\b(usb|ethernet|audio|sound|card reader|touchpad|fingerprint|chipset|camera|bluetooth|display|graphics|wireless|wlan|lan)\s+(?:controller\s+)?(?:all-in-one\s+)?(?:windows\s+)?driver\b", re.IGNORECASE),
        re.compile(r".*\b(pointing device driver|touchpad driver|audio driver|controller driver)\b", re.IGNORECASE),
        re.compile(r".*\b(usbaapl|usbaapl64|silabenm|fmapocontrol|nahimic|realtekaudiocontrol|synapticscontrolpanel)\b", re.IGNORECASE),
        re.compile(r".*\b(amdradeonsoftware|intelarcsoftware|intelconnectivityperformancesuite|inteloptanememoryandstoragemanagement|thunderboltcontrolcenter)\b", re.IGNORECASE),
        re.compile(r".*\b(dolbyaccess|dolbyaudio|dolbyatmos|dolbydigitalplus|dolbyvision)\b", re.IGNORECASE),
        re.compile(r".*\b(smartmicrophonesettings|goodixfingerprint|wacomdevice|wavesaudio|maxxaudio|supportassist)\b", re.IGNORECASE),
        re.compile(r".*\b(lenovocompanion|lenovosettings|lenovovoiceworldwide|lenovoutility|trackpoint)\b", re.IGNORECASE),
        re.compile(r".*\b(hp pc hardware diagnostics|diagnostics windows|intel graphics command center|intel\(r\) processor graphics|intel\(r\) graphics driver)\b", re.IGNORECASE),
        re.compile(r".*\b(corel graphics - windows shell extension)\b", re.IGNORECASE),
        re.compile(r".*\b(nvcontainer|nvapp|nvdlisr|shadowplay|frameviewsdk|frameview)\b", re.IGNORECASE),
        re.compile(r"^nvidia\s+(?:graphics\s+driver|hd\s+audio\s+driver|usbc\s+driver|virtual\s+audio|physx|frameview|container|telemetry|shadowplay|backend|app\s+driver|app)\b", re.IGNORECASE),
        re.compile(r".*\b(amd[_\s]chipset|amd\s+psp|amd\s+ryzen\s+balanced|amd\s+sbxxx|amd\s+i2c|amd\s+gpio2|amd\s+dvr64|amd\s+wvr64|amd\s+user\s+experience|ryzenmastersdk|amd\s+settings)\b", re.IGNORECASE),
    ]

    @classmethod
    def is_hardware_driver(cls, name: str, vendor: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        if not name:
            return False, None
        n_clean = name.strip().lower()
        for pat in cls.DRIVER_PATTERNS:
            if pat.search(n_clean):
                return True, f"HARDWARE_DRIVER_PACKAGE ({name})"
        return False, None


class LinuxSystemPackageFilter:
    """Filter to identify Linux system libraries, kernel packages, and core components."""

    CORE_OS_COMPONENTS: Set[str] = {
        "systemd", "bash", "coreutils", "util-linux", "initramfs-tools", "udev",
        "dpkg", "apt", "tar", "sed", "grep", "findutils", "procps", "net-tools",
        "iproute2", "kmod", "e2fsprogs", "login", "passwd", "systemd-sysv",
        "accountsservice", "acl", "acpid", "adduser", "adwaita-icon-theme",
        "alsa", "alsa-utils", "anacron", "apparmor", "apport", "baobab", "bind9",
        "binutils", "bubblewrap", "bzip2", "ca-certificates", "colord", "cron",
        "cups", "cups-browsed", "cups-filters", "dash", "dbus", "dconf", "diffutils",
        "dnsmasq-base", "dosfstools", "e2fsprogs", "evince", "file", "fontconfig",
        "fuse3", "gawk", "gdb", "gedit", "ghostscript", "gjs", "glib-networking",
        "gdm3", "gnome-shell", "gnome-terminal", "gnome-control-center", "gnome-session",
        "gnupg", "gpg", "gvfs", "gzip", "hostname", "htop", "ibus", "init", "iptables",
        "iputils-ping", "kbd", "less", "locales", "logrotate", "lsb-release", "lsof",
        "man-db", "mawk", "mutter", "nano", "nautilus", "ncurses-base", "ncurses-bin",
        "netbase", "netplan.io", "network-manager", "nftables", "openssh-client",
        "openssl", "openvpn", "parted", "patch", "pciutils", "perl", "perl-base",
        "pipewire", "plymouth", "polkitd", "rsyslog", "rsync", "samba", "sane-utils",
        "snapd", "sssd", "strace", "sudo", "tcpdump", "telnet", "time", "trace-cmd",
        "tracker", "tzdata", "ubuntu-desktop", "ubuntu-minimal", "ubuntu-standard",
        "ubuntu-drivers-common", "ubuntu-advantage-tools", "ubuntu-pro-client",
        "udisks2", "unattended-upgrades", "unzip", "update-manager", "upower",
        "usbutils", "vim", "vim-tiny", "wget", "which", "wireplumber", "wpasupplicant",
        "x11-common", "xauth", "xdg-utils", "xorg", "xserver-xorg", "xterm", "xz-utils",
        "zenity", "zip", "zlib1g"
    }

    UBUNTU_MAINTAINER_KEYWORDS = (
        "ubuntu developers", "ubuntu core developers", "ubuntu desktop team",
        "ubuntu kernel team", "canonical kernel team", "canonical (snap)",
        "ubuntu mozilla team", "ubuntu artwork team", "ubuntu bluetooth team",
        "ubuntu x-swat", "ubuntu motu developers", "ubuntu documentation team",
        "@ubuntu.com", "@canonical.com", "@debian.org", "canonical", "ubuntu community", "debian"
    )

    @classmethod
    def is_linux_system_package(
        cls,
        name: str,
        pkg_name: Optional[str] = None,
        vendor: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        target = (pkg_name or name or "").strip().lower()
        v_clean = (vendor or "").strip().lower()

        if not target and not v_clean:
            return False, None, None

        # Check if package publisher/vendor is official Ubuntu/Debian maintainer
        is_maintainer = any(kw in v_clean for kw in cls.UBUNTU_MAINTAINER_KEYWORDS) or "ubuntu" in v_clean or "canonical" in v_clean or "debian" in v_clean

        # Normalize target for hyphens and spaces
        target_norm = target.replace(" ", "-")

        if target in cls.CORE_OS_COMPONENTS or target_norm in cls.CORE_OS_COMPONENTS:
            return True, f"LINUX_CORE_OS_COMPONENT ({target})", QualificationCategory.OS_SYSTEM_COMPONENT.value

        if target.startswith("lib") and len(target) > 3:
            return True, f"LINUX_SHARED_LIBRARY ({target})", QualificationCategory.LINUX_SYSTEM_PACKAGE.value
        if target.startswith("gir1.2-") or target.startswith("gir1.2 "):
            return True, f"LINUX_GIR_PACKAGE ({target})", QualificationCategory.LINUX_SYSTEM_PACKAGE.value
        if target.startswith("fonts-") or target.startswith("fontconfig"):
            return True, f"LINUX_FONT_PACKAGE ({target})", QualificationCategory.LINUX_SYSTEM_PACKAGE.value
        if target.startswith("xfonts-"):
            return True, f"LINUX_FONT_PACKAGE ({target})", QualificationCategory.LINUX_SYSTEM_PACKAGE.value
        if target.startswith("printer-driver-"):
            return True, f"LINUX_PRINTER_DRIVER ({target})", QualificationCategory.LINUX_SYSTEM_PACKAGE.value
        if target.startswith("language-pack-") or target.startswith("language pack"):
            return True, f"LINUX_LANGUAGE_PACK ({target})", QualificationCategory.LINUX_SYSTEM_PACKAGE.value
        if target.startswith("linux-headers-") or target.startswith("linux-modules-") or target.startswith("linux-image-") or target.startswith("linux-tools-") or target.startswith("linux-hwe-"):
            return True, f"LINUX_KERNEL_PACKAGE ({target})", QualificationCategory.LINUX_SYSTEM_PACKAGE.value
        if target.startswith("linux image") or target.startswith("linux headers") or target.startswith("linux modules") or target.startswith("linux tools") or target.startswith("linux hwe"):
            return True, f"LINUX_KERNEL_PACKAGE ({target})", QualificationCategory.LINUX_SYSTEM_PACKAGE.value
        if re.match(r'^(cpp-\d+|gcc-\d+-base|g\+\+-\d+|cpp \d+|gcc \d+|g\+\+ \d+)', target):
            return True, f"LINUX_COMPILER_BASE ({target})", QualificationCategory.LINUX_SYSTEM_PACKAGE.value
        if target.startswith("gnome-") or target.startswith("gnome ") or target.startswith("yaru-theme-") or target.startswith("gsettings-"):
            return True, f"LINUX_DESKTOP_PACKAGE ({target})", QualificationCategory.LINUX_SYSTEM_PACKAGE.value

        # If from Ubuntu maintainer and not a third-party commercial app
        if is_maintainer:
            known_third_party = {"google-chrome", "chrome", "brave", "docker", "slack", "code", "vscode", "zoom", "spotify"}
            target_tokens = set(re.split(r"[-_.\s]+", target))
            if not any(tp in target_tokens or target == tp for tp in known_third_party):
                return True, f"UBUNTU_OFFICIAL_REPO_PACKAGE ({target})", QualificationCategory.LINUX_SYSTEM_PACKAGE.value

        return False, None, None


class MacOSSystemComponentFilter:
    """Filter to identify macOS system daemons, agents, and bundled services."""

    MACOS_DAEMONS_AND_AGENTS: Set[str] = {
        "launchd", "abassistantservice", "airplayuiagent", "identityservicesd", "imagent",
        "universalaccessd", "controlcenter", "controlcentre", "spotlight", "dock", "finder",
        "systemuiserver", "loginwindow", "sharingd", "biometrickitd", "powerd",
        "distnoted", "cfprefsd", "rapportd", "cloudd", "secd", "trustd", "rcd", "xprotect",
        "50onpaletteserver", "accessibilityuiserver", "accessibilityvisualsagent",
        "airscanlegacydiscovery", "airscanscanner", "amsengagementviewservice",
        "aosalertmanager", "aosheartbeat", "aospushrelay", "applemobiledevicehelper",
        "applemobilesync", "applescript utility", "applespell", "appssoagent",
        "aquaappearancehelper", "ardagent", "askpermissionui", "asktomessageshost",
        "autofillpanelservice", "automationmodeui", "axvisualsupportagent",
        "backgroundtaskmanagementagent", "bluetoothassistant", "bluetoothuiservice",
        "calendarfilehandler", "captivenetworkassistant", "chinesetextconverterservice",
        "cimfindinputcodetool", "cinematicframingonboardingui", "classroomstudentmenuextra",
        "conflictresolver", "continuitycaptureonboardingui", "controlstrip", "corelocationagent",
        "coreservicesuiagent", "coveragedetails", "databaseevents", "dfrhud", "diagnosticsreporter",
        "dischelper", "diskimagemounter", "diskimages ui agent", "dwellcontrol", "eaptlstrust",
        "emojifunctionrowim", "enhancedlogging", "eraseassistant", "escrowsecurityalert",
        "expansionslotutility", "familyextensionhost", "feedbackremoteview",
        "fileprovider-feedback", "findmymacmessenger", "folderactionsdispatcher", "followupui",
        "fontregistryuiagent", "gameoverlayui", "iconcomposer", "idsremoteurlconnectionagent",
        "imageevents", "imautomatichistorydeletionagent", "imtransferagent", "iouiagent",
        "japaneseim-kanatyping", "japaneseim-romajityping", "javalauncher", "kerberosmenuextra",
        "keyboardaccessagent", "keyboardassistant", "keychaincirclenotification", "koreanim",
        "linkednotesuiservice", "liquiddetectiond", "livespeech", "makepdf", "managedclient",
        "mdmmigrationtrampoline", "mediamlpluginapp", "medicalimagingcalibrator",
        "memoryslotutility", "mobiledeviceupdater", "mrt", "mtlreplayer", "musicrecognition",
        "nbagent", "netauthagent", "nowplayingtouchui", "obexagent", "odsagent", "openspell",
        "osduihelper", "paireddevices", "passviewer", "pipagent", "pluginim", "posterboard",
        "powerchime", "pressandhold", "previewshell", "previewshellmac", "printcentre",
        "privatecloudcomputed", "prodisplaycalibrator", "problemreporter", "qlmanage",
        "quicklookuihelper", "rapportuiagent", "registerpluginimapp", "remotedesktopmessage",
        "rosetta 2 updater", "scim", "screencaptureui", "screenreaderuiserver", "screensaverengine",
        "scriptmenu", "scriptmonitor", "shortcutdroplet", "shortcutsevents", "shortcutsactions",
        "smartcardpairing", "sociallayerd", "softwareupdate", "softwareupdatenotificationmanager",
        "spacestouchbaragent", "speechdownloader", "speechrecognitionserver", "speechservice",
        "ssmenuagent", "stagemanageronboarding", "stmuihelper", "storeuid", "summaryservice",
        "syncserver", "syncuid", "systemevents", "systemintents", "tamilim", "tcim",
        "textinputmenuagent", "textinputswitcher", "thermaltrap", "ticketviewer",
        "tmhelperagent", "trackpadim", "transliterationim", "tyim", "uasharedpasteboardprogressui",
        "uikitsystem", "universalaccessauthwarn", "universalaccesscontrol", "unmountassistantagent",
        "usernotificationcenter", "vietnameseim", "voicecontrolofflineguide", "voiceoverquickstart",
        "watchfacehelp", "wifiagent", "windowmanager", "windowmanagershowdeskt образова education",
        "windowmanagershowdesktopeducation", "workoutalert-mac"
    }

    @classmethod
    def is_macos_system_component(
        cls,
        name: str,
        install_loc: Optional[str] = None,
        vendor: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        n_clean = (name or "").strip().lower()
        v_clean = (vendor or "").strip().lower()
        loc_clean = (install_loc or "").strip().lower()
        base_name = n_clean.split(".")[-1]
        is_apple_vendor = v_clean in ("apple", "apple inc.", "apple inc", "apple computer") or "apple inc" in v_clean

        if (
            n_clean.startswith("com.apple.")
            or n_clean in cls.MACOS_DAEMONS_AND_AGENTS
            or base_name in cls.MACOS_DAEMONS_AND_AGENTS
            or n_clean.replace(" ", "") in cls.MACOS_DAEMONS_AND_AGENTS
            or "droplet" in n_clean
            or "automator application stub" in n_clean
            or "menulet" in n_clean
            or "group.is.workflow" in n_clean
        ):
            return True, f"MACOS_SYSTEM_DAEMON_OR_AGENT ({name})"

        if is_apple_vendor:
            # Check daemon / helper suffixes
            daemon_suffixes = ("agent", "service", "daemon", "d", "helper", "host", "launcher", "im", "server", "dispatcher", "ui")
            if any(n_clean.endswith(s) for s in daemon_suffixes) or n_clean.endswith("d"):
                return True, f"APPLE_SYSTEM_AGENT_OR_DAEMON ({name})"

        if loc_clean:
            if loc_clean.startswith("/system/library/") or loc_clean.startswith("/usr/libexec/"):
                return True, f"MACOS_SYSTEM_PATH ({install_loc})"
            if loc_clean.startswith("/system/applications/") and n_clean in ("utilities", "system preferences", "system settings"):
                return True, f"MACOS_SYSTEM_BUNDLE ({name})"

        return False, None


class BrowserArtifactAndPWAFilter:
    """Filter to identify Chrome sandbox artifacts, browser shortcuts, and PWAs."""

    PWA_DESKTOP_REGEX = re.compile(
        r'^([a-z0-9-]+\.)+(com|org|net|io|app|ai|gov|edu)-[a-zA-Z0-9_\-]+\.desktop$',
        re.IGNORECASE
    )

    @classmethod
    def is_browser_artifact_or_pwa(cls, name: str, shortcut_or_loc: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
        n_clean = (name or "").strip().lower()
        loc_clean = (shortcut_or_loc or "").strip().lower()

        # Chrome Sandbox artifact
        if n_clean.startswith("cr.sb.") or "cr.sb." in n_clean:
            return True, "CHROME_SANDBOX_ARTIFACT", QualificationCategory.WEB_SHORTCUT_OR_PWA.value

        # Browser Generated Web App / URL shortcut
        if (
            re.search(r"[a-z0-9\.\-]+\.(?:com|net|org|in|io|app|ai|co)-[a-z0-9_~]+", n_clean)
            or re.search(r"^(?:www\.|[a-z0-9\-]+\.)+[a-z0-9\-]+\.(?:com|net|org|in|io|app|ai|co)[-_]", n_clean)
            or n_clean.startswith("1_https___")
            or n_clean.startswith("1_http___")
            or "web application" in n_clean
        ):
            return True, f"WEB_SHORTCUT_PWA ({name})", QualificationCategory.WEB_SHORTCUT_OR_PWA.value

        # PWA / Web Shortcut .desktop files
        if n_clean.endswith(".desktop") or loc_clean.endswith(".desktop") or ".desktop" in n_clean or ".desktop" in loc_clean:
            filename = n_clean if n_clean.endswith(".desktop") else loc_clean.split("/")[-1]
            if cls.PWA_DESKTOP_REGEX.match(filename) or any(d in filename for d in ["meet.google.com", "sharepoint.com", "chatgpt.com", "teams.microsoft.com"]):
                return True, f"WEB_SHORTCUT_PWA ({filename})", QualificationCategory.WEB_SHORTCUT_OR_PWA.value

        return False, None, None


class ApplicationQualificationFilter:
    """
    Evaluates candidate applications and assigns them to one of 9 categories:
    1. STANDALONE_APPLICATION
    2. OS_SYSTEM_COMPONENT
    3. RUNTIME_FRAMEWORK
    4. SHARED_COMPONENT
    5. INSTALLER_INFRASTRUCTURE
    6. UNKNOWN_APPLICATION
    7. WEB_SHORTCUT/PWA
    8. LINUX_SYSTEM_PACKAGE
    9. MACOS_SYSTEM_COMPONENT

    Only STANDALONE_APPLICATION enters the main commercial application inventory.
    """

    # Installer infrastructure / utility fonts / package manager components
    INSTALLER_INFRA_NAMES: Set[str] = {
        "vs_coreeditorfonts",
        "windows package manager source (winget)",
        "windows package manager source (winget) v2",
        "app installer",
        "app installer (winget)",
        "microsoft.desktopappinstaller",
    }

    # Shared components (database drivers, redistributables)
    SHARED_COMPONENT_NAMES: Set[str] = {
        "microsoft visual studio installer",
        "microsoft sql server 2025 setup (english)",
        "microsoft sql server 2025 setup",
        "microsoft sql server setup support files",
        "microsoft vss writer for sql server 2025",
        "microsoft vss writer for sql server",
        "browser for sql server 2025",
        "sql server browser",
        "microsoft odbc driver 17 for sql server",
        "microsoft odbc driver 18 for sql server",
        "microsoft odbc driver for sql server",
        "microsoft ole db driver for sql server",
        "microsoft ole db driver 19 for sql server",
        "microsoft visual c++ redistributable",
        "microsoft visual c++ 2015-2022 redistributable (x64)",
        "microsoft visual c++ 2015-2022 redistributable (x86)",
    }

    @classmethod
    def qualify_candidate(cls, candidate: Dict[str, Any]) -> Tuple[bool, str, str]:
        """
        Evaluates a candidate application record.
        Returns: (is_qualified: bool, reason: str, category: str)
        """
        raw_name = (candidate.get("raw_name") or candidate.get("name") or candidate.get("raw_application_name") or "").strip()
        if not raw_name:
            return False, "EMPTY_APPLICATION_NAME", QualificationCategory.UNKNOWN_APPLICATION.value

        n_clean = raw_name.lower()
        raw_vend = candidate.get("raw_publisher") or candidate.get("publisher") or candidate.get("raw_vendor") or candidate.get("vendor") or ""
        install_loc = candidate.get("raw_install_location") or candidate.get("install_location") or candidate.get("shortcut_path")
        pkg_name = candidate.get("raw_package_name") or candidate.get("package_identifier")
        pkg_fam = candidate.get("package_family_name")
        det_method = candidate.get("detection_method") or candidate.get("install_source") or ""

        # 1. Rule: Start Menu shortcuts MUST NOT directly create new application records
        if det_method == "WINDOWS_START_MENU":
            return False, "START_MENU_SHORTCUT_NOT_PRIMARY_SOURCE", QualificationCategory.UNKNOWN_APPLICATION.value

        # 2. Rule: Browser Artifact & PWA Filter (cr.sb.*, meet.google.com-*.desktop)
        is_pwa, pwa_reason, pwa_cat = BrowserArtifactAndPWAFilter.is_browser_artifact_or_pwa(raw_name, install_loc)
        if is_pwa:
            return False, pwa_reason or "WEB_SHORTCUT_OR_PWA", pwa_cat or QualificationCategory.WEB_SHORTCUT_OR_PWA.value

        # 3. Rule: Linux System Package & Library Filter (lib*, gir*, linux-headers*, coreutils, etc.)
        is_lnx, lnx_reason, lnx_cat = LinuxSystemPackageFilter.is_linux_system_package(raw_name, pkg_name, raw_vend)
        if is_lnx:
            return False, lnx_reason or "LINUX_SYSTEM_PACKAGE", lnx_cat or QualificationCategory.LINUX_SYSTEM_PACKAGE.value

        # 4. Rule: macOS System Daemon & Component Filter (ABAssistantService, /System/Library/, etc.)
        is_mac, mac_reason = MacOSSystemComponentFilter.is_macos_system_component(raw_name, install_loc, raw_vend)
        if is_mac:
            return False, mac_reason or "MACOS_SYSTEM_COMPONENT", QualificationCategory.MACOS_SYSTEM_COMPONENT.value

        # 5. Rule: Windows System Tool Filter (MMC, taskmgr, control panel, etc.)
        is_sys_tool, sys_tool_reason = WindowsSystemToolFilter.is_system_tool(raw_name, install_loc)
        if is_sys_tool:
            return False, sys_tool_reason or "SYSTEM_TOOL", QualificationCategory.OS_SYSTEM_COMPONENT.value

        # 6. Rule: Windows OS System / Internal Component Filter (hosts, broker plugins, dialogs, experience hosts)
        is_sys_comp, sys_comp_reason = WindowsSystemComponentFilter.is_system_component(
            name=raw_name,
            install_location=install_loc,
            package_name=pkg_name,
            package_family=pkg_fam,
        )
        if is_sys_comp:
            return False, sys_comp_reason or "OS_SYSTEM_COMPONENT", QualificationCategory.OS_SYSTEM_COMPONENT.value

        # 7. Rule: Windows Runtime & Framework Dependency Filter
        is_rt, rt_reason = WindowsRuntimeFrameworkFilter.is_runtime_or_framework(raw_name, pkg_name, pkg_fam)
        if is_rt:
            return False, rt_reason or "RUNTIME_OR_FRAMEWORK_DEPENDENCY", QualificationCategory.RUNTIME_FRAMEWORK.value

        # 7.1 Rule: Windows OS Updates, Security Patches, and KBs
        is_update, update_reason = WindowsOSUpdateFilter.is_os_update_or_patch(raw_name)
        if is_update:
            return False, update_reason or "WINDOWS_OS_UPDATE_PATCH", QualificationCategory.OS_SYSTEM_COMPONENT.value

        # 7.2 Rule: Windows Hardware Device Drivers & Peripheral Packages
        is_driver, driver_reason = WindowsDriverFilter.is_hardware_driver(raw_name, raw_vend)
        if is_driver:
            return False, driver_reason or "HARDWARE_DRIVER_PACKAGE", QualificationCategory.OS_SYSTEM_COMPONENT.value

        # 8. Rule: Installer Infrastructure
        if n_clean in cls.INSTALLER_INFRA_NAMES or (pkg_name and str(pkg_name).lower() in cls.INSTALLER_INFRA_NAMES):
            return False, f"INSTALLER_INFRASTRUCTURE ({raw_name})", QualificationCategory.INSTALLER_INFRASTRUCTURE.value

        # 9. Check Primary Detection Signals
        is_reg = "REGISTRY" in det_method or "UNINSTALL" in det_method or "HKLM" in det_method or "HKU" in det_method
        is_appx = "APPX" in det_method or "PACKAGE" in det_method or "STORE" in det_method.upper() or bool(candidate.get("package_family_name")) or "windowsapps" in str(install_loc).lower()
        is_winget = "WINGET" in det_method or det_method == "PACKAGE_MANAGER"

        # Discard Windows Update KB packages & system patches
        if (raw_name.startswith("KB") and raw_name[2:8].isdigit()) or "KB" in raw_name:
            is_up, r_up = WindowsOSUpdateFilter.is_os_update_or_patch(raw_name)
            if is_up:
                return False, r_up, QualificationCategory.OS_SYSTEM_COMPONENT.value

        # Check Shared Component list (e.g. drivers/redistributables/setup bootstrappers in installation inventories)
        INSTALLER_SETUP_KEYWORDS = (
            " setup", " installer", " bootstrapper", " setup support files",
            " vss writer", " browser for sql server", " native client",
            " odbc driver", " ole db driver"
        )
        is_generic_setup_component = any(n_clean.endswith(kw) or f"{kw} " in n_clean for kw in INSTALLER_SETUP_KEYWORDS)
        inst_src_clean = str(candidate.get("install_source") or "").lower()
        is_setup_dir = any(token in inst_src_clean for token in ("\\setup\\", "/setup/", "\\packages\\", "/packages/", "\\package cache\\", "/package cache/"))
        is_protected_standalone = any(p in n_clean for p in ("visual studio code", "git", "python", "node.js", "docker", "brave", "chrome", "firefox", "zoom", "chatgpt"))

        if (n_clean in cls.SHARED_COMPONENT_NAMES or is_generic_setup_component or is_setup_dir) and not is_protected_standalone:
            return True, f"QUALIFIED_SHARED_COMPONENT ({raw_name})", QualificationCategory.SHARED_COMPONENT.value

        # Valid Registry signal: Must have non-trivial metadata
        if is_reg:
            has_ver = bool(candidate.get("raw_version") or candidate.get("version"))
            has_pub = bool(candidate.get("raw_publisher") or candidate.get("publisher") or candidate.get("raw_vendor"))
            has_loc = bool(install_loc)
            has_uninst = bool(candidate.get("raw_uninstall_string"))
            has_reg_key = bool(candidate.get("registry_key"))

            if has_uninst or has_ver or has_pub or has_loc or has_reg_key:
                return True, "QUALIFIED_REGISTRY_APPLICATION", QualificationCategory.STANDALONE_APPLICATION.value

        # Valid AppX/MSIX Store packaged app
        if is_appx:
            return True, "QUALIFIED_APPX_PACKAGE", QualificationCategory.STANDALONE_APPLICATION.value

        # Valid Winget package
        if is_winget:
            winget_id = candidate.get("package_identifier") or ""
            if winget_id.startswith("ARP\\Machine\\X86\\{") and not candidate.get("raw_version"):
                return False, "WINGET_UNRESOLVED_INTERNAL_ARP", QualificationCategory.UNKNOWN_APPLICATION.value
            return True, "QUALIFIED_WINGET_PACKAGE", QualificationCategory.STANDALONE_APPLICATION.value

        # Default fallback if valid version and publisher exist
        if candidate.get("raw_version") and (candidate.get("raw_publisher") or candidate.get("raw_vendor")):
            return True, "QUALIFIED_METADATA_MATCH", QualificationCategory.STANDALONE_APPLICATION.value

        return False, "INSUFFICIENT_QUALIFYING_EVIDENCE", QualificationCategory.UNKNOWN_APPLICATION.value
