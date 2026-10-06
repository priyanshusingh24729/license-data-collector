import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

with open('backend/inventory/detection/detection_normalizer.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Let's inspect the rules in VENDOR_NORMALIZATION_RULES
from backend.inventory.detection.detection_normalizer import VENDOR_NORMALIZATION_RULES, VendorRule

# Build deduplicated exact rules preserving the latest/canonical vendor mapping
exact_dict = {}
for r in VENDOR_NORMALIZATION_RULES:
    if r.match_type == "exact":
        exact_dict[r.pattern] = r.canonical_vendor

substring_rules = [r for r in VENDOR_NORMALIZATION_RULES if r.match_type == "contains"]

# Reconstruct VENDOR_NORMALIZATION_RULES text
rules_text = ["VENDOR_NORMALIZATION_RULES: List[VendorRule] = [", "    # Exact vendor normalization rules (Priority 1)"]
for pat, vend in exact_dict.items():
    escaped_pat = pat.replace('\\', '\\\\').replace('"', '\\"')
    escaped_vend = vend.replace('\\', '\\\\').replace('"', '\\"')
    rules_text.append(f'    VendorRule("{escaped_pat}", "exact", "{escaped_vend}"),')

rules_text.append("\n    # Substring / pattern vendor normalization rules (Priority 2)")
for r in substring_rules:
    escaped_pat = r.pattern.replace('\\', '\\\\').replace('"', '\\"')
    escaped_vend = r.canonical_vendor.replace('\\', '\\\\').replace('"', '\\"')
    rules_text.append(f'    VendorRule("{escaped_pat}", "{r.match_type}", "{escaped_vend}"),')
rules_text.append("]\n")

new_rules_block = "\n".join(rules_text)

start_mark = text.find("VENDOR_NORMALIZATION_RULES: List[VendorRule] = [")
end_mark = text.find("# Backward-compatible mapping view of exact rules")

text = text[:start_mark] + new_rules_block + "\n" + text[end_mark:]

with open('backend/inventory/detection/detection_normalizer.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated detection_normalizer.py with deduplicated, conflict-free rules!")
