import re

with open('backend/inventory/detection/detection_normalizer.py', 'r', encoding='utf-8') as f:
    orig = f.read()

# 1. Update imports
orig = orig.replace(
    "from typing import Optional, Tuple",
    "from typing import Optional, Tuple, NamedTuple, List, Dict"
)

# 2. Find PUBLISHER_CANONICAL_MAP definition and replace it with VendorRule & VENDOR_NORMALIZATION_RULES & PUBLISHER_CANONICAL_MAP
map_start = orig.find("PUBLISHER_CANONICAL_MAP = {")
map_end = orig.find("GUID_PUBLISHER_MAP = {")

# Extract exact rules from existing text
raw_map_text = orig[map_start:map_end]
exact_rules = []
for line in raw_map_text.split('\n'):
    line = line.strip()
    m = re.match(r'["\']([^"\']+)["\']\s*:\s*["\']([^"\']+)["\'],?', line)
    if m:
        exact_rules.append((m.group(1), m.group(2)))

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

rule_defs = []
rule_defs.append("class VendorRule(NamedTuple):")
rule_defs.append("    pattern: str")
rule_defs.append("    match_type: str  # 'exact', 'contains', 'regex'")
rule_defs.append("    canonical_vendor: str\n")

rule_defs.append("VENDOR_NORMALIZATION_RULES: List[VendorRule] = [")
rule_defs.append("    # Exact vendor normalization rules (Priority 1)")
for pat, vend in exact_rules:
    escaped_pat = pat.replace('\\', '\\\\').replace('"', '\\"')
    escaped_vend = vend.replace('\\', '\\\\').replace('"', '\\"')
    rule_defs.append(f'    VendorRule("{escaped_pat}", "exact", "{escaped_vend}"),')

rule_defs.append("\n    # Substring / pattern vendor normalization rules (Priority 2)")
for pat, vend in substring_rules:
    escaped_pat = pat.replace('\\', '\\\\').replace('"', '\\"')
    escaped_vend = vend.replace('\\', '\\\\').replace('"', '\\"')
    rule_defs.append(f'    VendorRule("{escaped_pat}", "contains", "{escaped_vend}"),')
rule_defs.append("]\n")

rule_defs.append("# Backward-compatible mapping view of exact rules")
rule_defs.append("PUBLISHER_CANONICAL_MAP: Dict[str, str] = {")
rule_defs.append('    r.pattern: r.canonical_vendor for r in VENDOR_NORMALIZATION_RULES if r.match_type == "exact"')
rule_defs.append("}\n")

new_rules_section = "\n".join(rule_defs) + "\n# Vendor GUID to Official Vendor Resolution Map (Step 2)\n"

orig = orig[:map_start] + new_rules_section + orig[map_end + len("GUID_PUBLISHER_MAP = {") - len("GUID_PUBLISHER_MAP = {"):]

# 3. Replace the substring matching chain in normalize_publisher
old_chain_start = orig.find("        # Check third-party publisher strings\n        if \"crowdstrike\" in lower_key:")
old_chain_end = orig.find("        # Check GUID mapping first\n        if lower_key in GUID_PUBLISHER_MAP:")

if old_chain_start == -1 or old_chain_end == -1:
    raise Exception(f"Could not find substring chain locations: {old_chain_start}, {old_chain_end}")

new_chain = """        # Check third-party publisher rules (substring / regex) in priority order
        for rule in VENDOR_NORMALIZATION_RULES:
            if rule.match_type == "exact":
                continue
            if rule.match_type == "contains":
                if rule.pattern in lower_key:
                    return rule.canonical_vendor
            elif rule.match_type == "regex":
                if re.search(rule.pattern, norm, re.IGNORECASE):
                    return rule.canonical_vendor\n\n"""

orig = orig[:old_chain_start] + new_chain + orig[old_chain_end:]

# 4. Remove the trailing dead code if lower_key in PUBLISHER_CANONICAL_MAP: return ...
dead_check = """        if lower_key in PUBLISHER_CANONICAL_MAP:
            return PUBLISHER_CANONICAL_MAP[lower_key]
        return norm"""
orig = orig.replace(dead_check, "        return norm")

with open('backend/inventory/detection/detection_normalizer.py', 'w', encoding='utf-8') as f:
    f.write(orig)

print("Successfully refactored detection_normalizer.py!")
