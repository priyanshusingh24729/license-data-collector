import csv, re
from collections import Counter

input_path = r'C:\Users\Priyanshu Singh\OneDrive - Silver Leaf Solutions Private Limited\Desktop\DB\srs apps.csv'

# Rule-based resolutions for 42 Custom compare values
custom_resolutions = {
    # CAL
    251466: "CAL",                             # IBM Domino Messaging 9.0 CAL
    
    # Users (Employee User, Named User, SaaS User, PeopleSoft / Oracle App User)
    70891: "Users",                            # Oracle Access Management Employee User
    13960: "Users",                            # Peoplesoft Enterprise Payroll
    403492: "Users",                           # PeopleSoft Enterprise Human Resources
    111391: "Users",                           # Oracle EBS (GRC) Advanced Controls
    500427: "Users",                           # Oracle EBS Purchasing - Option: Services Procurement
    301738: "Users",                           # PeopleSoft Enterprise Time and Labor 9
    349780: "Users",                           # PeopleSoft Enterprise eRecruit
    575883: "Users",                           # PeopleSoft Enterprise ePerformance 9
    600425: "Users",                           # PeopleSoft Enterprise Learning Management
    59822: "Users",                            # PeopleSoft Enterprise HCM Portal Pack
    361180: "Users",                           # IBM Connections Cloud S1
    623575: "Users",                           # Oracle Internet Developer Suite
    6366: "Users",                             # Oracle Hyperion Planning Plus
    832793: "Users",                           # Oracle EBS Incentive Compensation
    92753: "Users",                            # Oracle Inventory Management 12
    115997: "Users",                           # Oracle Financials 12
    361040: "Users",                           # Oracle Internet Expenses 12
    533161: "Users",                           # Oracle Procurement Contracts for Oracle Purchasing 12
    572926: "Users",                           # Oracle Purchasing 12
    853354: "Users",                           # Oracle iSupplier Portal for Oracle Purchasing 12
    860886: "Users",                           # Oracle iProcurement 12

    # Installations / Devices
    681724: "Installations",                   # Symantec NetBackup 7.6 NDMP Option Server
    732596: "Installations",                   # VERITAS NetBackup 8.0 NDMP Option Server
    95588: "Installations",                    # IBM Rational Functional Tester 9.1
    572559: "Installations",                   # IBM Rational Performance Tester 9.2
    836256: "Installations",                   # IBM Rational Application Developer 9.7
    349709: "Installations",                   # IBM Aspera High-Speed Transfer Endpoint 3.8
    293033: "Devices",                         # IBM Endpoint Manager 9.1 for Lifecycle Management

    # Unresolved -> blank
    54185: "",                                 # IBM Security Identity and Access Manager 3.1
    70947: "",                                 # IBM Security Identity Manager 7.0 Host Edition
    730401: "",                                # IBM Security Identity Manager 6.0 Host Edition
    113418: "",                                # IBM Security Access Manager Virtual Federation Edition
    227548: "",                                # IBM Security Access Manager 9.0 Virtual Edition
    526372: "",                                # IBM Security Access Manager for Web 7.0
    436818: "",                                # IBM Rational Performance Test Pack
    422456: "",                                # AppDynamics Pro Java
    544943: "",                                # Oracle Business Intelligence Publisher 12
    663692: "",                                # IBM Tivoli Application Dependency Discovery Manager 7.3
    689433: "",                                # Adobe Experience Manager 6.0
    759126: "",                                # Oracle Policy Modeling 10.4
    906799: ""                                 # Adobe Target Standard
}

def transform_metric(row):
    raw_metric = row.get('Metric', '')
    app_id = int(row.get('App_ID', 0)) if row.get('App_ID') else 0
    name = row.get('Name', '')
    nlr = str(row.get('NoLicenseRequired', '')).strip()

    # 1. Custom compare values handling
    if raw_metric == 'Custom compare values':
        return custom_resolutions.get(app_id, '')

    # 2. Corrupt / numeric metric (Cake 1 has 25 with NoLicenseRequired=1)
    if raw_metric == '25' or app_id == 708409:
        return 'No License Required'

    # 3. Direct dictionary normalization
    if raw_metric == 'Installations':
        return 'Installations'
    elif raw_metric == 'Devices':
        return 'Devices'
    elif raw_metric == 'Users':
        return 'Users'
    elif raw_metric == 'PVU':
        return 'PVU'
    elif raw_metric in ('CAL (Client Access License)', 'CAL'):
        return 'CAL'
    elif raw_metric == 'Number of processor cores':
        return 'Processor Cores'
    elif raw_metric == 'Number of processors':
        return 'Processors'
    elif raw_metric == 'Concurrent users':
        return 'Concurrent Users'
    elif raw_metric == 'Concurrent devices':
        return 'Concurrent Devices'
    elif raw_metric == 'No license required':
        return 'No License Required'

    # 4. Handle NULL, empty, missing
    if raw_metric in ('NULL', '', None) or str(raw_metric).strip().upper() in ('NULL', 'UNKNOWN', 'N/A', 'NONE', 'NOT AVAILABLE', 'NOT FOUND'):
        # Check if the product name provides definitive evidence
        if re.search(r'\b(?:User|Device|Messaging|Enterprise|Standard|Terminal Services|Exchange|SharePoint|Remote Desktop|SQL Server|Windows Server)\s+CAL\b', name, re.I) or name.endswith(' CAL'):
            return 'CAL'
        if re.search(r'\b(?:Per[\s-]User|Named[\s-]User)\b', name, re.I):
            return 'Users'
        if re.search(r'\b(?:Concurrent[\s-]User|Floating[\s-]User)\b', name, re.I):
            return 'Concurrent Users'
        if re.search(r'\b(?:Per[\s-]Core|Core[\s-]License)\b', name, re.I):
            return 'Processor Cores'
        
        # Unavailable / missing metric -> blank
        return ''

    # Fallback to blank if unrecognized
    return ''

# Run test pass
input_count = 0
changed_count = 0
blank_count = 0
improved_counts = Counter()
original_counts = Counter()
changes_by_type = Counter()

with open(input_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
    reader = csv.DictReader(f)
    for row in reader:
        input_count += 1
        orig = row['Metric']
        original_counts[orig] += 1
        
        improved = transform_metric(row)
        improved_counts[improved] += 1

        if orig != improved:
            changed_count += 1
            changes_by_type[(orig, improved)] += 1
            
        if improved == '':
            blank_count += 1

print("=== VALIDATION SUMMARY ===")
print(f"Input Row Count:  {input_count:,}")
print(f"Changed Rows:     {changed_count:,}")
print(f"Blank Metric:     {blank_count:,}")
print("\nUnique Improved Metric Values:")
for k, v in improved_counts.most_common():
    label = repr(k) if k != '' else "'' (Blank)"
    print(f"  {label:<25}: {v:>10,}")

print("\nBreakdown of Changes (Original -> Improved):")
for (orig, imp), cnt in changes_by_type.most_common():
    orig_label = repr(orig)
    imp_label = repr(imp) if imp != '' else "'' (Blank)"
    print(f"  {orig_label:<30} -> {imp_label:<25}: {cnt:>10,}")
