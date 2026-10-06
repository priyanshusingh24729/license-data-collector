"""
Test suite for Step 2: License Source Registry and Resolution Engine.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.database.connection import Base, get_db
from backend.main import app
from backend.models.enums import (
    SourceType,
    AuthorityLevel,
    ScopeType,
    CollectionMethod,
    SourceStatus,
    AccessType,
)
from backend.models.source import LicenseSource
from backend.schemas.source import LicenseSourceCreate, LicenseSourceUpdate
from backend.services.source_registry_service import (
    normalize_url,
    create_source,
    get_source_by_id,
    list_sources,
    update_source,
    deactivate_source,
    get_vendor_sources,
    get_product_sources,
    get_applicable_sources,
)
from backend.sources.registry import seed_initial_sources

# Test database setup (in-memory SQLite with StaticPool for thread-safe session sharing)
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def test_db():
    """Creates a fresh test database with schema initialized."""
    test_engine = create_engine(
        SQLALCHEMY_TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(test_db):
    """Provides a FastAPI test client using the shared test database session."""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# -------------------------------------------------------------
# 1. URL Normalization & Deduplication Tests
# -------------------------------------------------------------

def test_url_normalization():
    """Verify deterministic URL cleaning and stripping of tracking parameters."""
    raw_url = "HTTPS://WWW.Adobe.Com:443/legal/terms.html/?utm_source=google&b=2&utm_medium=cpc&a=1#section1"
    normalized = normalize_url(raw_url)
    assert normalized == "https://www.adobe.com/legal/terms.html?a=1&b=2"


def test_duplicate_prevention(test_db):
    """Test 8: Prevent duplicate active sources with the same vendor, normalized URL, and scope."""
    source_in = LicenseSourceCreate(
        vendor_name="Adobe",
        product_name="Acrobat",
        scope_type=ScopeType.PRODUCT,
        scope_identifier="Adobe Acrobat",
        source_name="Adobe Acrobat FAQ",
        source_type=SourceType.OFFICIAL_LICENSING_GUIDE,
        authority_level=AuthorityLevel.OFFICIAL_VENDOR,
        source_url="https://helpx.adobe.com/acrobat/kb/acrobat-licensing-faq.html",
        priority=1,
    )
    src1 = create_source(test_db, source_in)
    assert src1.id is not None

    # Attempt to insert identical source with trailing slash and uppercase characters
    duplicate_in = LicenseSourceCreate(
        vendor_name="adobe",
        product_name="Acrobat",
        scope_type=ScopeType.PRODUCT,
        scope_identifier="Adobe Acrobat",
        source_name="Duplicate Adobe FAQ",
        source_type=SourceType.OFFICIAL_LICENSING_GUIDE,
        authority_level=AuthorityLevel.OFFICIAL_VENDOR,
        source_url="https://helpx.adobe.com/acrobat/kb/acrobat-licensing-faq.html/",
        priority=1,
    )
    with pytest.raises(ValueError) as excinfo:
        create_source(test_db, duplicate_in)
    assert "Active source already exists" in str(excinfo.value)


# -------------------------------------------------------------
# 2. Source Creation, Retrieval, Filtering, Update & Deletion
# -------------------------------------------------------------

def test_source_creation_and_retrieval(test_db, client):
    """Test 1 & 2: Create a source via API and retrieve it."""
    payload = {
        "vendor_name": "Microsoft",
        "product_name": "SQL Server",
        "scope_type": "PRODUCT",
        "scope_identifier": "Microsoft SQL Server",
        "source_name": "SQL Server Licensing Guide",
        "source_type": "OFFICIAL_LICENSING_GUIDE",
        "authority_level": "OFFICIAL_VENDOR",
        "source_url": "https://www.microsoft.com/licensing/docs/view/SQL-Server",
        "priority": 1,
        "is_active": True,
        "is_public": True,
        "status": "ACTIVE",
        "access_type": "PUBLIC",
        "collection_method": "WEB"
    }

    response = client.post("/api/sources", json=payload)
    assert response.status_code == 201
    data = response.json()
    source_id = data["id"]
    assert data["vendor_name"] == "Microsoft"
    assert data["normalized_url"] == "https://www.microsoft.com/licensing/docs/view/SQL-Server"

    # Get single source
    get_res = client.get(f"/api/sources/{source_id}")
    assert get_res.status_code == 200
    assert get_res.json()["source_name"] == "SQL Server Licensing Guide"


def test_source_filtering(test_db):
    """Test 3: Filter sources by vendor, authority, source_type, and status."""
    seed_initial_sources(test_db)

    adobe_sources = list_sources(test_db, vendor="Adobe")
    assert len(adobe_sources) >= 4
    for s in adobe_sources:
        assert s.vendor_name.lower() == "adobe"

    terms_sources = list_sources(test_db, source_type=SourceType.OFFICIAL_TERMS)
    assert len(terms_sources) >= 3
    for s in terms_sources:
        assert s.source_type == SourceType.OFFICIAL_TERMS


def test_source_update(test_db, client):
    """Test 4: Update an existing source."""
    source_in = LicenseSourceCreate(
        vendor_name="Autodesk",
        product_name="AutoCAD",
        scope_type=ScopeType.PRODUCT,
        scope_identifier="Autodesk AutoCAD",
        source_name="AutoCAD Specs",
        source_type=SourceType.OFFICIAL_PRODUCT_DOCUMENTATION,
        authority_level=AuthorityLevel.OFFICIAL_VENDOR,
        source_url="https://www.autodesk.com/autocad-specs",
        priority=3,
    )
    src = create_source(test_db, source_in)

    # Patch source priority and description
    patch_res = client.patch(f"/api/sources/{src.id}", json={
        "priority": 1,
        "description": "Updated priority to tier 1"
    })
    assert patch_res.status_code == 200
    updated_data = patch_res.json()
    assert updated_data["priority"] == 1
    assert updated_data["description"] == "Updated priority to tier 1"


def test_inactive_source_not_returned_as_active(test_db, client):
    """Test 10: Inactive sources are excluded from active resolutions and queries."""
    source_in = LicenseSourceCreate(
        vendor_name="Adobe",
        product_name="Photoshop",
        scope_type=ScopeType.PRODUCT,
        scope_identifier="Adobe Photoshop",
        source_name="Old Photoshop Guide",
        source_type=SourceType.OFFICIAL_LICENSING_GUIDE,
        authority_level=AuthorityLevel.OFFICIAL_VENDOR,
        source_url="https://helpx.adobe.com/photoshop-old",
        priority=1,
        is_active=True,
        status=SourceStatus.ACTIVE,
    )
    src = create_source(test_db, source_in)

    # Soft delete
    del_res = client.delete(f"/api/sources/{src.id}")
    assert del_res.status_code == 200
    assert del_res.json()["is_active"] is False
    assert del_res.json()["status"] == "INACTIVE"

    # Verify not returned in active resolution
    resolved = get_applicable_sources(test_db, "Adobe", "Photoshop", active_only=True)
    assert not any(s.id == src.id for s in resolved)


# -------------------------------------------------------------
# 3. Source Resolution & Deterministic Hierarchy Tests
# -------------------------------------------------------------

def test_vendor_and_product_resolution(test_db):
    """Test 5 & 6: Vendor and product level source resolution."""
    seed_initial_sources(test_db)

    # Vendor level
    vendor_sources = get_vendor_sources(test_db, "Microsoft")
    assert len(vendor_sources) >= 2
    for s in vendor_sources:
        assert s.scope_type == ScopeType.VENDOR

    # Product level
    prod_sources = get_product_sources(test_db, "Microsoft", "SQL Server")
    assert len(prod_sources) >= 3
    # Check that SQL Server specific source is ranked above vendor general terms
    assert prod_sources[0].scope_type == ScopeType.PRODUCT
    assert prod_sources[0].product_name == "SQL Server"


def test_version_specific_source_priority_hierarchy(test_db, client):
    """
    Test 7: Full resolution hierarchy test.
    Adobe Acrobat Pro 2025 should resolve and prioritize:
    1. VERSION scope (Adobe Acrobat Pro 2025)
    2. EDITION scope (Acrobat Pro)
    3. PRODUCT scope (Adobe Acrobat)
    4. VENDOR scope (Adobe Master Terms)
    """
    # 1. Vendor scope
    create_source(test_db, LicenseSourceCreate(
        vendor_name="Adobe",
        scope_type=ScopeType.VENDOR,
        scope_identifier="Adobe",
        source_name="Adobe General Terms",
        source_type=SourceType.OFFICIAL_TERMS,
        authority_level=AuthorityLevel.OFFICIAL_VENDOR,
        source_url="https://www.adobe.com/terms",
        priority=1
    ))

    # 2. Product scope
    create_source(test_db, LicenseSourceCreate(
        vendor_name="Adobe",
        product_name="Acrobat",
        scope_type=ScopeType.PRODUCT,
        scope_identifier="Adobe Acrobat",
        source_name="Adobe Acrobat Product Terms",
        source_type=SourceType.OFFICIAL_TERMS,
        authority_level=AuthorityLevel.OFFICIAL_VENDOR,
        source_url="https://www.adobe.com/acrobat-terms",
        priority=1
    ))

    # 3. Edition scope
    create_source(test_db, LicenseSourceCreate(
        vendor_name="Adobe",
        product_name="Acrobat",
        scope_type=ScopeType.EDITION,
        scope_identifier="Acrobat Pro",
        source_name="Adobe Acrobat Pro Guide",
        source_type=SourceType.OFFICIAL_LICENSING_GUIDE,
        authority_level=AuthorityLevel.OFFICIAL_VENDOR,
        source_url="https://helpx.adobe.com/acrobat-pro-guide",
        priority=1
    ))

    # 4. Version scope
    create_source(test_db, LicenseSourceCreate(
        vendor_name="Adobe",
        product_name="Acrobat",
        scope_type=ScopeType.VERSION,
        scope_identifier="Acrobat Pro 2025",
        source_name="Adobe Acrobat Pro 2025 Release Licensing Notes",
        source_type=SourceType.OFFICIAL_LICENSING_GUIDE,
        authority_level=AuthorityLevel.OFFICIAL_VENDOR,
        source_url="https://helpx.adobe.com/acrobat-pro-2025-release",
        priority=1
    ))

    # Call resolution API
    res = client.get("/api/sources/resolve", params={
        "vendor": "Adobe",
        "product": "Acrobat",
        "edition": "Pro",
        "version": "2025"
    })
    assert res.status_code == 200
    payload = res.json()
    sources = payload["sources"]
    assert len(sources) == 4

    # Verify deterministic ordering: VERSION -> EDITION -> PRODUCT -> VENDOR
    assert sources[0]["scope_type"] == "VERSION"
    assert sources[0]["scope_identifier"] == "Acrobat Pro 2025"

    assert sources[1]["scope_type"] == "EDITION"
    assert sources[1]["scope_identifier"] == "Acrobat Pro"

    assert sources[2]["scope_type"] == "PRODUCT"
    assert sources[2]["scope_identifier"] == "Adobe Acrobat"

    assert sources[3]["scope_type"] == "VENDOR"
    assert sources[3]["scope_identifier"] == "Adobe"


def test_paid_source_optional_and_not_required(test_db):
    """
    Test 9: Paid sources can be registered as optional enrichment,
    but public sources are resolved without requiring paid ones.
    """
    # Create public source
    create_source(test_db, LicenseSourceCreate(
        vendor_name="Oracle",
        product_name="Database",
        scope_type=ScopeType.PRODUCT,
        scope_identifier="Oracle Database",
        source_name="Oracle Public Licensing Manual",
        source_type=SourceType.OFFICIAL_LICENSING_GUIDE,
        authority_level=AuthorityLevel.OFFICIAL_VENDOR,
        source_url="https://docs.oracle.com/database-licensing.htm",
        access_type=AccessType.PUBLIC,
        priority=1
    ))

    # Create paid enrichment source
    create_source(test_db, LicenseSourceCreate(
        vendor_name="Oracle",
        product_name="Database",
        scope_type=ScopeType.PRODUCT,
        scope_identifier="Oracle Database",
        source_name="Paid Vendor Licensing Advisory Portal",
        source_type=SourceType.SECONDARY_SOURCE,
        authority_level=AuthorityLevel.TRUSTED_SECONDARY,
        source_url="https://premium-licensing-advisors.example.com/oracle",
        access_type=AccessType.PAID,
        priority=10
    ))

    # Resolve
    resolved = get_applicable_sources(test_db, "Oracle", "Database")
    assert len(resolved) == 2
    # Public official vendor source must precede secondary paid source
    assert resolved[0].access_type == AccessType.PUBLIC
    assert resolved[0].authority_level == AuthorityLevel.OFFICIAL_VENDOR
    assert resolved[1].access_type == AccessType.PAID
