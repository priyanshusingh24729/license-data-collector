import csv
from collections import Counter

p = r'C:\Users\Priyanshu Singh\OneDrive - Silver Leaf Solutions Private Limited\Desktop\DB\srs apps.csv'
null_nlr_counts = Counter()
null_samples_nlr1 = []
null_samples_nlr0 = []

with open(p, 'r', encoding='utf-8-sig', errors='ignore') as f:
    reader = csv.DictReader(f)
    for r in reader:
        m = r['Metric']
        if m in ('NULL', '', None):
            nlr = r.get('NoLicenseRequired')
            null_nlr_counts[nlr] += 1
            if nlr == '1' and len(null_samples_nlr1) < 10:
                null_samples_nlr1.append(r)
            elif nlr == '0' and len(null_samples_nlr0) < 10:
                null_samples_nlr0.append(r)

print("NULL Metric breakdown by NoLicenseRequired:")
for k, v in null_nlr_counts.items():
    print(f"  NoLicenseRequired={k}: {v}")

print("\nSample NULL rows where NoLicenseRequired == '1':")
for r in null_samples_nlr1:
    print(f"  App_ID: {r['App_ID']} | Name: {r['Name']}")

print("\nSample NULL rows where NoLicenseRequired == '0':")
for r in null_samples_nlr0:
    print(f"  App_ID: {r['App_ID']} | Name: {r['Name']}")
