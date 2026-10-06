import json

with open("scratch/all_61_unknowns.json", "r", encoding="utf-8") as f:
    unknowns = json.load(f)

print(f"Loaded {len(unknowns)} UNKNOWN records.\n")

for u in unknowns:
    raw = u["raw_name"]
    pub = u["raw_pub"]
    loc = u["install_loc"] or ""
    print(f"ID {u['id']:03d} | raw: '{raw}' | pub: '{pub}' | loc: '{loc}'")
