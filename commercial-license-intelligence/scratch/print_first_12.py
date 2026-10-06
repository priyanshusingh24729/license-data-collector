import json

with open("scratch/all_61_unknowns.json", "r", encoding="utf-8") as f:
    unknowns = json.load(f)

for idx, u in enumerate(unknowns[:12], 1):
    raw = u["raw_name"]
    pub = u["raw_pub"]
    loc = u["install_loc"] or "None"
    print(f"[{idx:02d}] ID {u['id']:03d} | raw='{raw}' | pub='{pub}' | loc='{loc}'")
