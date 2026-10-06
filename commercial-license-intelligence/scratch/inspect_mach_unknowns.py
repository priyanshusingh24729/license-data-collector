from backend.database.connection import SessionLocal
from backend.models.inventory import InstallationLicenseResult

db = SessionLocal()
mach_apps = db.query(InstallationLicenseResult).order_by(InstallationLicenseResult.id.asc()).all()

print(f"Total machine records: {len(mach_apps)}")
unknown_mach = []
for ma in mach_apps:
    if ma.classification == "UNKNOWN":
        unknown_mach.append(ma)

print(f"Total UNKNOWN machine records: {len(unknown_mach)}")
for m in unknown_mach:
    print(f"ID {m.id:03d} | raw='{m.raw_application_name}' | vendor='{m.raw_vendor}' | can_prod='{m.canonical_product}' | can_vend='{m.canonical_vendor}' | ev_status='{m.evidence_status}'")

db.close()
