import re

with open('backend/inventory/detection/detection_normalizer.py', 'r', encoding='utf-8') as f:
    orig = f.read()

# Extract PUBLISHER_CANONICAL_MAP content
map_match = re.search(r'PUBLISHER_CANONICAL_MAP = \{([^}]+)\}', orig)
if not map_match:
    raise Exception("Could not find PUBLISHER_CANONICAL_MAP")

raw_map_content = map_match.group(1)

# Parse exact rules
exact_rules = []
for line in raw_map_content.strip().split('\n'):
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    m = re.match(r'["\']([^"\']+)["\']\s*:\s*["\']([^"\']+)["\'],?', line)
    if m:
        exact_rules.append((m.group(1), m.group(2)))

print(f"Extracted {len(exact_rules)} exact rules.")

substring_rules = [
    ("silicon laboratories", "Silicon Laboratories"),
    ("crowdstrike", "CrowdStrike, Inc."),
    ("corel", "Corel"),
    ("apple", "Apple Inc."),
    ("realtek", "Realtek Semiconductor Corp"),
    ("google", "Google"),
    ("anthropic", "Anthropic"),
    ("dell", "Dell"),
    ("lenovo", "Lenovo"),
    ("intel", "Intel Corporation"),
    ("advanced micro devices", "Advanced Micro Devices, Inc. (AMD)"),
    ("amd", "Advanced Micro Devices, Inc. (AMD)"),
    ("nvidia", "NVIDIA Corporation"),
    ("riot", "Riot Games, Inc."),
    ("kitware", "Kitware, Inc."),
    ("oracle", "Oracle Corporation"),
    ("warp", "Warp, Inc."),
    ("avast", "Gen Digital Inc. / Avast"),
    ("mcafee", "McAfee, LLC"),
    ("tlauncher", "TLauncher"),
    ("wondershare", "Wondershare Technology Co., Ltd."),
    ("telegram", "Telegram Messenger LLP"),
    ("kankaria", "Kankaria"),
    ("adobe", "Adobe Inc."),
    ("mozilla", "Mozilla"),
    ("opera", "Opera Software"),
    ("vivaldi", "Vivaldi Technologies"),
    ("cisco", "Cisco Systems, Inc."),
    ("fortinet", "Fortinet, Inc."),
    ("document foundation", "The Document Foundation"),
    ("libreoffice", "The Document Foundation"),
    ("filezilla", "FileZilla Project"),
    ("eclipse", "Eclipse Foundation"),
    ("postgresql", "PostgreSQL Global Development Group"),
    ("red hat", "Red Hat, Inc."),
    ("redhat", "Red Hat, Inc."),
    ("splunk", "Splunk, Inc."),
    ("foundry", "The Foundry"),
    ("steelseries", "SteelSeries"),
    ("lists.ubuntu.com", "Ubuntu Community"),
    ("ubuntu developers", "Ubuntu Community"),
    ("canonical.com", "Canonical"),
    ("canonical", "Canonical"),
    ("debian.org", "Debian Project"),
    ("debian qa", "Debian Project"),
    ("gnu.org", "Free Software Foundation"),
    ("free software foundation", "Free Software Foundation"),
]

print(f"Extracted {len(substring_rules)} substring rules.")
