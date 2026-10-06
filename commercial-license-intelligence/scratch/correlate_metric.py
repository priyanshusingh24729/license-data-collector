import pandas as pd

p_srs_apps = r'C:\Users\Priyanshu Singh\OneDrive - Silver Leaf Solutions Private Limited\Desktop\DB\srs apps.csv'
p_srs = r'C:\Users\Priyanshu Singh\OneDrive - Silver Leaf Solutions Private Limited\Desktop\DB\SRS.csv'

# Read first 100k of both to correlate PreferredMetric integer with Metric string
df_apps = pd.read_csv(p_srs_apps, nrows=100000, low_memory=False)
df_srs = pd.read_csv(p_srs, nrows=100000, low_memory=False)

merged = pd.merge(df_apps[['Name', 'Metric']], df_srs[['Name', 'PreferredMetric']], on='Name').dropna()
ct = pd.crosstab(merged['PreferredMetric'], merged['Metric'])
print(ct.to_string())
