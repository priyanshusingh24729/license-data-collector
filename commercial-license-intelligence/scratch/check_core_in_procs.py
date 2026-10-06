import pandas as pd
import re

p = r'C:\Users\Priyanshu Singh\OneDrive - Silver Leaf Solutions Private Limited\Desktop\DB\srs apps.csv'
df = pd.read_csv(p, low_memory=False)

procs = df[df['Metric'] == 'Number of processors']
core_named = procs[procs['Name'].str.contains(r'\bcore\b|\bcores\b', case=False, na=False)]
print(f"Number of processors with 'core' in Name: {len(core_named)}")
for idx, r in core_named.iterrows():
    print(f"[{r['App_ID']}] {r['Name']}")
