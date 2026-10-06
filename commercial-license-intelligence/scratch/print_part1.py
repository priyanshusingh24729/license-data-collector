import json
with open("scratch/all_61_unknowns.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for i, x in enumerate(data[:43]):
    print(f"{i+1:02d}. ID={x['id']:03d} | raw='{x['raw_name']}' | pub='{x['raw_pub']}'")
    print(f"    loc='{x['install_loc']}'")
    print(f"    ms_canonical='{x['ms_canonical']}' | ms_type='{x['ms_type']}' | res_ev='{x['research_ev_status']}' | res_class='{x['research_class']}'")
    print(f"    quote='{x['research_quote']}'")
    print()
