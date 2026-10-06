import csv
import os

for csv_path in ['data/PF490A36_LAPTOP-TTASCMUO_Installation.csv', 'data/PF490A36_LAPTOP-TTASCMUO_Installation(1).csv']:
    if not os.path.exists(csv_path):
        continue
    print(f"\n=== INSPECTING {csv_path} ===")
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    print(f"Total rows: {len(rows)}")
    
    # Check for name occurrences
    names = {}
    for r in rows:
        n = r.get('Application_Name', '').strip()
        names.setdefault(n, []).append(r)
    
    dups = {k: v for k, v in names.items() if len(v) > 1}
    print(f"Duplicate application names in CSV: {len(dups)}")
    for k, v in dups.items():
        print(f"  • '{k}' ({len(v)} occurrences):")
        for item in v:
            print(f"     - Ver: {item.get('Version')} | Vend: {item.get('Vendor')} | Source: {item.get('Install_Source')} | Loc: {item.get('Install_Location')}")

    # Check for similar names
    print("\nAll Applications in CSV:")
    for idx, r in enumerate(rows, 1):
        print(f"  {idx:02d}: Name='{r.get('Application_Name')}' | Vend='{r.get('Vendor')}' | Ver='{r.get('Version')}' | Source='{r.get('Install_Source')}'")
