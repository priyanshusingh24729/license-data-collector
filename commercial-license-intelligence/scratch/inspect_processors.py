import pandas as pd

p = r'C:\Users\Priyanshu Singh\OneDrive - Silver Leaf Solutions Private Limited\Desktop\DB\srs apps.csv'
df = pd.read_csv(p, low_memory=False)

procs = df[df['Metric'] == 'Number of processors']
print(f"Total 'Number of processors': {len(procs)}")

# Check for keywords like core, sql server, windows server, oracle
cores_in_procs = procs[procs['Name'].str.contains(r'core|sql server|windows server|oracle database', case=False, na=False)]
print(f"Rows in 'Number of processors' mentioning core/sql server/windows server: {len(cores_in_procs)}")
for idx, r in cores_in_procs.head(20).iterrows():
    print(f"[{r['App_ID']}] {r['Name']} (Version: {r['VersionName']})")
