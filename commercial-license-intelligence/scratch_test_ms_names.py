from backend.inventory.recognition.microsoft_identity_resolver import MicrosoftProductIdentityResolver
from backend.research.windows_product_adapter import WindowsProductResearchAdapter
from backend.validation.microsoft_evidence_validator import MicrosoftEvidenceValidator

test_apps = [
    ("Windows Calculator", "Microsoft Corporation", "11.2607.0.0"),
    ("Windows Notepad", "Microsoft Corporation", "11.2607.14.0"),
    ("Windows Camera", "Microsoft Corporation", "2026.2607.1.0"),
    ("Windows Maps", "Microsoft Corporation", "11.2506.3.0"),
    ("Windows Terminal", "Microsoft Corporation", "1.24.11911.0"),
    ("Photos", "Microsoft Corporation", "2026.11060.2004.0"),
    ("Paint", "Microsoft Corporation", "11.2605.81.0"),
    ("Microsoft Sticky Notes", "Microsoft Corporation", "6.1.4.0"),
    ("Bing Weather", "Microsoft Corporation", "4.54.63045.0"),
    ("XBOX", "Microsoft Corporation", "2608.1001.17.0"),
    ("Power Automate", "Microsoft Corporation", "11.2608.115.0"),
    ("Outlook for Windows", "Microsoft Corporation", "1.2026.818.100"),
    ("Microsoft Teams", "Microsoft", "26213.1006.5014.9784"),
    ("Microsoft 365 companion apps", "Microsoft Corporation", "2.2605.21000.0"),
]

for name, pub, ver in test_apps:
    ident = MicrosoftProductIdentityResolver.resolve_identity(raw_name=name, raw_publisher=pub, raw_version=ver)
    research = WindowsProductResearchAdapter.research_product(ident, "OPEN_SOURCE / FREEWARE", "NO")
    validated = MicrosoftEvidenceValidator.validate_and_score(None, ident, research, "OPEN_SOURCE / FREEWARE", "NO", "NOT_APPLICABLE", "HIGH")
    print(f"'{name}' -> Canonical: '{ident.canonical_name}' | Type: {ident.product_type.value} | Research Class: {research.classification} | Validated Class: {validated['classification']} | Ev: {validated['evidence_status']} | Rel: {validated['reliability_score']}%")
