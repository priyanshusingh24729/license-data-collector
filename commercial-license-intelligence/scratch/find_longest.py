import json

p_full = r'C:\Users\priya\.gemini\antigravity-ide\brain\bdf05050-bcef-4048-919d-5021c17710c4\.system_generated\logs\transcript_full.jsonl'

best_text = ""
with open(p_full, 'r', encoding='utf-8') as f:
    for idx, line in enumerate(f):
        if '360 Extreme Browser' in line:
            print(f"Line {idx} has length {len(line)}")
            if len(line) > len(best_text):
                best_text = line

print(f"Best line length: {len(best_text)}")
d = json.loads(best_text)
def search_all_str(o):
    if isinstance(o, str) and '360 Extreme Browser' in o and 'Zscaler Client Connector' in o:
        return o
    if isinstance(o, dict):
        for v in o.values():
            r = search_all_str(v)
            if r: return r
    if isinstance(o, list):
        for item in o:
            r = search_all_str(item)
            if r: return r
    return None

csv_full = search_all_str(d)
if csv_full:
    idx = csv_full.find('Tier,Application,Vendor')
    clean_csv = csv_full[idx:]
    with open('raw_full_dataset.csv', 'w', encoding='utf-8') as out:
        out.write(clean_csv)
    print(f"SUCCESS! Wrote raw_full_dataset.csv with {len(clean_csv.splitlines())} lines.")
else:
    print("Could not find full csv string")
