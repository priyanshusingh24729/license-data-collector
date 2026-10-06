import pandas as pd

p_srs_apps = r'C:\Users\Priyanshu Singh\OneDrive - Silver Leaf Solutions Private Limited\Desktop\DB\srs apps.csv'
p_srs = r'C:\Users\Priyanshu Singh\OneDrive - Silver Leaf Solutions Private Limited\Desktop\DB\SRS.csv'

df_apps = pd.read_csv(p_srs_apps, low_memory=False)
custom_apps = df_apps[df_apps['Metric'] == 'Custom compare values']
custom_names = set(custom_apps['Name'])

results = {}
for chunk in pd.read_csv(p_srs, chunksize=100000, low_memory=False):
    m = chunk[chunk['Name'].isin(custom_names)]
    if not m.empty:
        for _, row in m.iterrows():
            results[row['Name']] = {
                'Manufacturer': row['ManufacturerName'],
                'PreferredMetric': row['PreferredMetric'],
                'LicensingForm': row['LicensingForm'],
                'ApplicationType': row['ApplicationType'],
                'NoLicenseRequired': row['NoLicenseRequired']
            }

for name in sorted(custom_names):
    info = results.get(name, 'NOT FOUND IN SRS.csv')
    print(f"{name} => {info}")
