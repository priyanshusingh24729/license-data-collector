import csv, re

p = r'C:\Users\Priyanshu Singh\OneDrive - Silver Leaf Solutions Private Limited\Desktop\DB\srs apps.csv'

cal_matches = []
core_matches = []
user_matches = []
concurrent_matches = []

with open(p, 'r', encoding='utf-8-sig', errors='ignore') as f:
    reader = csv.DictReader(f)
    for r in reader:
        m = r['Metric']
        if m in ('NULL', '', None):
            name = r['Name']
            if re.search(r'\bCAL\b', name, re.I):
                if len(cal_matches) < 10:
                    cal_matches.append((r['App_ID'], name))
            if re.search(r'\bper[\s-]core\b|\bcore[\s-]license\b|\bprocessor[\s-]core\b', name, re.I):
                if len(core_matches) < 10:
                    core_matches.append((r['App_ID'], name))
            if re.search(r'\bper[\s-]user\b|\bnamed[\s-]user\b', name, re.I):
                if len(user_matches) < 10:
                    user_matches.append((r['App_ID'], name))
            if re.search(r'\bconcurrent[\s-]user\b|\bfloating[\s-]user\b', name, re.I):
                if len(concurrent_matches) < 10:
                    concurrent_matches.append((r['App_ID'], name))

print(f"Sample CAL matches in NULL Metric rows (found {len(cal_matches)}):")
for m in cal_matches:
    print(" ", m)

print(f"\nSample per-core matches in NULL Metric rows (found {len(core_matches)}):")
for m in core_matches:
    print(" ", m)

print(f"\nSample per-user matches in NULL Metric rows (found {len(user_matches)}):")
for m in user_matches:
    print(" ", m)

print(f"\nSample concurrent matches in NULL Metric rows (found {len(concurrent_matches)}):")
for m in concurrent_matches:
    print(" ", m)
