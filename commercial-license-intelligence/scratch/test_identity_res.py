import sys
sys.path.insert(0, ".")
from backend.inventory.detection.detection_normalizer import DetectionNormalizer
from backend.inventory.recognition.alias_system import ApplicationAliasSystem
from backend.inventory.recognition.microsoft_identity_resolver import MicrosoftProductIdentityResolver
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine

apps = [
    ("Power BI Desktop", "Microsoft", "2.157.1354.0"),
    ("SQL Server Management Studio", "Microsoft Corporation", "22.9.2"),
    ("Outlook for Windows", "Microsoft Corporation", "1.2026.902.100"),
    ("Microsoft OneDrive", "Microsoft Corporation", "26.158.0816.0003"),
    ("Microsoft Teams", "Microsoft Corporation", "26149.701.4759.8860"),
    ("Paint", "Microsoft Corporation", "11.2605.81.0"),
    ("Lenovo Vantage Service", "Lenovo Group Ltd.", "5.1.2608.14"),
    ("PHP", None, "8.2.33"),
]

for app, pub, ver in apps:
    norm_name = DetectionNormalizer.normalize_name(app)
    ms_res = MicrosoftProductIdentityResolver.resolve_identity(app, raw_publisher=pub, detected_version=ver)
    alias_res = ApplicationAliasSystem.resolve_application(app, raw_publisher=pub, raw_version=ver)
    hybrid_res = HybridLicenseEngine.resolve_hybrid_record(None, app, pub, ver)
    
    print(f"=== {app} ===")
    print(f"  norm_name: {norm_name}")
    print(f"  ms_res canonical: {ms_res.canonical_name if ms_res else None}")
    print(f"  alias_res canonical: {alias_res.canonical_product if alias_res else None}")
    print(f"  hybrid_res: app={hybrid_res.get('application')}, class={hybrid_res.get('classification')}, lic_req={hybrid_res.get('license_required')}, model={hybrid_res.get('license_model')}")
