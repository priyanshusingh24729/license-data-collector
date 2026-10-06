from backend.inventory.detection.detection_normalizer import PUBLISHER_CANONICAL_MAP
from scratch.check_conflicts import patterns

print(f"Total exact: {len(PUBLISHER_CANONICAL_MAP)}")
for k, v in PUBLISHER_CANONICAL_MAP.items():
    # check if any substring rule matches k
    for p, sub_vend in patterns:
        if p in k and v != sub_vend:
            # For example, does 'microsoft windows' contain 'microsoft' (which is in exact map)?
            pass

print("Done checking.")
