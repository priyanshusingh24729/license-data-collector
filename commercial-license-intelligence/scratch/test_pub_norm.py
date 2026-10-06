import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.inventory.detection.detection_normalizer import DetectionNormalizer, PUBLISHER_CANONICAL_MAP

# Sample publishers to test
test_pubs = [
    "Adobe Inc.", "adobe systems incorporated", "Microsoft Corporation", "Microsoft Windows",
    "Google LLC", "JetBrains s.r.o.", "Realtek Semiconductor Corp", "CrowdStrike", "Corel",
    "Apple", "Dell", "Intel", "AMD", "NVIDIA", "Oracle", "Warp", "Avast", "McAfee", "TLauncher",
    "Wondershare", "Telegram", "Kankaria", "Mozilla", "Opera", "Vivaldi", "Cisco", "Fortinet",
    "The Document Foundation", "LibreOffice", "FileZilla", "Eclipse", "PostgreSQL", "Red Hat",
    "RedHat", "Splunk", "The Foundry", "SteelSeries", "Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>",
    "Canonical Desktop Team <desktop@canonical.com>", "Debian Install System Team <debian-boot@lists.debian.org>",
    "GNU Project <maintainers@gnu.org>", "{33F0F141-36F3-4EC2-A77D-51B53D0BA0E4}"
]

for p in test_pubs:
    res = DetectionNormalizer.normalize_publisher(p)
    print(f"'{p}' -> '{res}'")
