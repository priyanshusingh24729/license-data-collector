import os, pandas as pd

search_dirs = [
    r'C:\Users\Priyanshu Singh\OneDrive - Silver Leaf Solutions Private Limited\Desktop',
    r'C:\Users\Priyanshu Singh\Downloads',
    r'c:\Users\Priyanshu Singh\OneDrive - Silver Leaf Solutions Private Limited\Desktop\license data collector'
]

found = []
for sd in search_dirs:
    for root, dirs, files in os.walk(sd):
        for f in files:
            if f.endswith(('.csv', '.xlsx')):
                p = os.path.join(root, f)
                try:
                    if f.endswith('.csv'):
                        df = pd.read_csv(p, nrows=2)
                    else:
                        df = pd.read_excel(p, nrows=2)
                    cols = [str(c).strip() for c in df.columns]
                    has_metric = any('metric' in c.lower() for c in cols)
                    has_class = any('class' in c.lower() for c in cols)
                    has_model = any('model' in c.lower() for c in cols)
                    if has_metric:
                        found.append({
                            'path': p,
                            'cols': cols,
                            'has_class': has_class,
                            'has_model': has_model,
                            'size': os.path.getsize(p)
                        })
                except Exception:
                    pass

for item in found:
    print(f"PATH: {item['path']} ({item['size']} bytes)")
    print(f"  Cols: {item['cols']}")
