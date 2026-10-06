import pandas as pd

p_srs_apps = r'C:\Users\Priyanshu Singh\OneDrive - Silver Leaf Solutions Private Limited\Desktop\DB\srs apps.csv'
df_apps = pd.read_csv(p_srs_apps, low_memory=False)

keywords = [
    'Domino Messaging',
    'Experience Manager',
    'PeopleSoft',
    'NetBackup',
    'Rational Functional Tester',
    'Rational Performance Tester',
    'Security Access Manager',
    'Security Identity Manager',
    'Tivoli Application Dependency',
    'Oracle Financials',
    'Oracle Purchasing',
    'Oracle Inventory Management',
    'Target Standard',
    'AppDynamics Pro'
]

for kw in keywords:
    sub = df_apps[df_apps['Name'].str.contains(kw, case=False, na=False)]
    vc = sub['Metric'].value_counts(dropna=False).to_dict()
    print(f"Keyword: '{kw}' ({len(sub)} rows) -> Metric counts: {vc}")
