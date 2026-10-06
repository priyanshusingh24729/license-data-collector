import sys
import os
sys.path.insert(0, os.path.abspath("."))

from backend.database.connection import SessionLocal
from backend.models.inventory import DetectedApplication
from backend.inventory.recognition.microsoft_identity_resolver import MicrosoftProductIdentityResolver
from backend.research.windows_product_adapter import WindowsProductResearchAdapter
from backend.validation.microsoft_evidence_validator import MicrosoftEvidenceValidator

missing_ids = [76, 78, 80, 85, 94, 96, 102, 111, 115, 117, 129, 130, 141, 143, 144, 153, 154, 159]

db = SessionLocal()
apps = db.query(DetectedApplication).filter(DetectedApplication.id.in_(missing_ids)).order_by(DetectedApplication.id).all()

for a in apps:
    ident = MicrosoftProductIdentityResolver.resolve_identity(
        raw_name=a.raw_name,
        raw_publisher=a.raw_publisher,
        raw_version=a.detected_version,
        install_location=a.install_location,
    )
    res = WindowsProductResearchAdapter.research_product(ident)
    print(f"ID {a.id:03d} | raw='{a.raw_name}' -> ident_canon='{ident.canonical_name}' (type={ident.product_type}) -> research_class='{res.classification}' | ev_status='{res.evidence_status}' | url='{res.source_url}'")

db.close()
