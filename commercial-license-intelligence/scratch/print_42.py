import pandas as pd

p_srs_apps = r'C:\Users\Priyanshu Singh\OneDrive - Silver Leaf Solutions Private Limited\Desktop\DB\srs apps.csv'
df_apps = pd.read_csv(p_srs_apps, low_memory=False)

custom = df_apps[df_apps['Metric'] == 'Custom compare values']
for idx, r in custom.iterrows():
    print(f"Row {idx} | App_ID: {r['App_ID']} | Name: {r['Name']} | Version: {r['VersionName']}")
