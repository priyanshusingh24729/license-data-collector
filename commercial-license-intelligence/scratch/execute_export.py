import csv, os, sys, shutil
from collections import Counter

input_path = r'C:\Users\Priyanshu Singh\OneDrive - Silver Leaf Solutions Private Limited\Desktop\DB\srs apps.csv'
output_dir_db = r'C:\Users\Priyanshu Singh\OneDrive - Silver Leaf Solutions Private Limited\Desktop\DB'
output_improved_path = os.path.join(output_dir_db, 'srs_apps_improved_metric.csv')
output_exports_dir = r'c:\Users\Priyanshu Singh\OneDrive - Silver Leaf Solutions Private Limited\Desktop\license data collector\commercial-license-intelligence\exports'
output_exports_path = os.path.join(output_exports_dir, 'srs_apps_improved_metric.csv')

# Backup path
backup_path = os.path.join(output_dir_db, 'srs apps.csv.bak')

from test_transform import transform_metric

print(f"Reading from: {input_path}")
print(f"Writing to:   {output_improved_path}")

input_rows = 0
output_rows = 0
changed_rows = 0
blank_rows = 0
improved_counts = Counter()

# Use utf-8-sig to preserve BOM compatibility with Excel and SAM tools
with open(input_path, 'r', encoding='utf-8-sig', errors='ignore') as infile:
    reader = csv.DictReader(infile)
    fieldnames = reader.fieldnames
    
    with open(output_improved_path, 'w', encoding='utf-8-sig', newline='') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for row in reader:
            input_rows += 1
            orig_m = row['Metric']
            new_m = transform_metric(row)
            
            if orig_m != new_m:
                changed_rows += 1
            if new_m == '':
                blank_rows += 1
                
            improved_counts[new_m] += 1
            row['Metric'] = new_m
            writer.writerow(row)
            output_rows += 1

print(f"\nProcessing Complete!")
print(f"Input Rows:   {input_rows:,}")
print(f"Output Rows:  {output_rows:,}")
print(f"Changed Rows: {changed_rows:,}")
print(f"Blank Rows:   {blank_rows:,}")

# Also copy to exports directory
os.makedirs(output_exports_dir, exist_ok=True)
shutil.copy2(output_improved_path, output_exports_path)
print(f"Copied export to: {output_exports_path}")

# Create backup of original srs apps.csv if not exists
if not os.path.exists(backup_path):
    shutil.copy2(input_path, backup_path)
    print(f"Created backup at: {backup_path}")

# Overwrite original srs apps.csv with improved version
shutil.copy2(output_improved_path, input_path)
print(f"Successfully updated original file: {input_path}")
