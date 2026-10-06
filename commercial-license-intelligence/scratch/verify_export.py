import csv, os
from collections import Counter

file_path = r'C:\Users\Priyanshu Singh\OneDrive - Silver Leaf Solutions Private Limited\Desktop\DB\srs apps.csv'
file_improved = r'C:\Users\Priyanshu Singh\OneDrive - Silver Leaf Solutions Private Limited\Desktop\DB\srs_apps_improved_metric.csv'

metric_counts = Counter()
total_rows = 0

with open(file_improved, 'r', encoding='utf-8-sig', errors='ignore') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    print("Fieldnames:", fieldnames)
    for r in reader:
        total_rows += 1
        metric_counts[r['Metric']] += 1

print(f"\nVerification on {file_improved}:")
print(f"Total rows: {total_rows:,}")
print("Metric values breakdown:")
for k, v in metric_counts.most_common():
    lbl = repr(k) if k != '' else "'' (Blank)"
    print(f"  {lbl:<25}: {v:>10,}")
