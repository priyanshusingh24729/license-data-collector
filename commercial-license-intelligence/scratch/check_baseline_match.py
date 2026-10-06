import sys
sys.path.insert(0, '.')
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine

HybridLicenseEngine._init_lookup()
for app in ['Power BI Desktop', 'SQL Server Management Studio']:
    app_low = app.lower()
    matched = False
    for k, b in HybridLicenseEngine._BASELINE_MAP.items():
        if len(k) >= 6 and (k in app_low or app_low in k):
            print(f"'{app}' matched baseline key: '{k}' -> Baseline {b.get('id')}: '{b.get('name')}'")
            matched = True
            break
    if not matched:
        print(f"'{app}' did not match any baseline")
