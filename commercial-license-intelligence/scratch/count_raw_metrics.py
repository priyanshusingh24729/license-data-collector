import csv
from collections import Counter

p = r'C:\Users\Priyanshu Singh\OneDrive - Silver Leaf Solutions Private Limited\Desktop\DB\srs apps.csv'
counts = Counter()
total_rows = 0

with open(p, 'r', encoding='utf-8-sig', errors='ignore') as f:
    reader = csv.DictReader(f)
    for r in reader:
        total_rows += 1
        m = r['Metric']
        counts[m] += 1

print(f"Total Rows: {total_rows}")
print("Metric raw counts:")
for k, v in counts.most_common():
    print(f"  {repr(k)}: {v}")
