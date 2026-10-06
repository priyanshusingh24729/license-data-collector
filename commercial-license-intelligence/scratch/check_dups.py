import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.inventory.detection.detection_normalizer import VENDOR_NORMALIZATION_RULES

seen = {}
dups = []
for r in VENDOR_NORMALIZATION_RULES:
    if r.match_type == "exact":
        if r.pattern in seen:
            dups.append((r.pattern, seen[r.pattern], r.canonical_vendor))
        seen[r.pattern] = r.canonical_vendor

print("Exact rule duplicates:")
for d in dups:
    print(d)
