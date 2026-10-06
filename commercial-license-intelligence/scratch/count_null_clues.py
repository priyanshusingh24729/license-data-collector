import csv, re

p = r'C:\Users\Priyanshu Singh\OneDrive - Silver Leaf Solutions Private Limited\Desktop\DB\srs apps.csv'

cal_count = 0
user_count = 0
concurrent_count = 0
core_count = 0

with open(p, 'r', encoding='utf-8-sig', errors='ignore') as f:
    reader = csv.DictReader(f)
    for r in reader:
        m = r['Metric']
        if m in ('NULL', '', None):
            name = r['Name']
            # High confidence patterns
            if re.search(r'\b(?:User|Device|Messaging|Enterprise|Standard|Terminal Services|Exchange|SharePoint|Remote Desktop|SQL Server|Windows Server)\s+CAL\b', name, re.I) or name.endswith(' CAL'):
                cal_count += 1
            elif re.search(r'\b(?:Per[\s-]User|Named[\s-]User)\b', name, re.I):
                user_count += 1
            elif re.search(r'\b(?:Concurrent[\s-]User|Floating[\s-]User)\b', name, re.I):
                concurrent_count += 1
            elif re.search(r'\b(?:Per[\s-]Core|Core[\s-]License)\b', name, re.I):
                core_count += 1

print(f"High-confidence Name matches in NULL rows:")
print(f"  CAL: {cal_count}")
print(f"  Users: {user_count}")
print(f"  Concurrent Users: {concurrent_count}")
print(f"  Processor Cores: {core_count}")
