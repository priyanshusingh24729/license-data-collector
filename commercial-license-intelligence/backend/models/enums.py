"""Enumerations for License Intelligence, Discovery, Collectors, Extraction, Validation, Consolidation, Catalog, Monitoring, Inventory, Entitlements & Audit."""

from enum import Enum


class SourceType(str, Enum):
    """Types of licensing sources."""
    OFFICIAL_WEB = "OFFICIAL_WEB"
    OFFICIAL_DOCUMENT = "OFFICIAL_DOCUMENT"
    OFFICIAL_PDF = "OFFICIAL_PDF"
    OFFICIAL_API = "OFFICIAL_API"
    OFFICIAL_TERMS = "OFFICIAL_TERMS"
    OFFICIAL_EULA = "OFFICIAL_EULA"
    OFFICIAL_LICENSING_GUIDE = "OFFICIAL_LICENSING_GUIDE"
    OFFICIAL_PRODUCT_DOCUMENTATION = "OFFICIAL_PRODUCT_DOCUMENTATION"
    SECONDARY_SOURCE = "SECONDARY_SOURCE"
    DOCUMENTATION = "DOCUMENTATION"
    TERMS = "TERMS"
    EULA = "EULA"
    API = "API"
    HTML_PAGE = "HTML_PAGE"
    UNKNOWN = "UNKNOWN"


class AuthorityLevel(str, Enum):
    """Authority hierarchy for licensing sources."""
    OFFICIAL_VENDOR = "OFFICIAL_VENDOR"                      # Priority rank 1 (Highest)
    OFFICIAL_VENDOR_DOCUMENT = "OFFICIAL_VENDOR_DOCUMENT"      # Rank 2
    OFFICIAL_VENDOR_TERMS = "OFFICIAL_VENDOR_TERMS"            # Rank 3
    OFFICIAL_VENDOR_EULA = "OFFICIAL_VENDOR_EULA"              # Rank 4
    OFFICIAL_VENDOR_DOCUMENTATION = "OFFICIAL_VENDOR_DOCUMENTATION" # Rank 5
    OFFICIAL_DISTRIBUTOR = "OFFICIAL_DISTRIBUTOR"              # Rank 6
    TRUSTED_SECONDARY = "TRUSTED_SECONDARY"                  # Rank 7
    UNKNOWN = "UNKNOWN"                                      # Rank 8


class ScopeType(str, Enum):
    """Scope of software applicability for a source or fact."""
    VENDOR = "VENDOR"
    PRODUCT = "PRODUCT"
    EDITION = "EDITION"
    VERSION = "VERSION"
    ALL_VERSIONS = "ALL_VERSIONS"
    VERSION_RANGE = "VERSION_RANGE"
    ALL_EDITIONS = "ALL_EDITIONS"
    UNKNOWN = "UNKNOWN"


class CollectionMethod(str, Enum):
    """Intended collection mechanism."""
    WEB = "WEB"
    PDF = "PDF"
    API = "API"
    DOCUMENT = "DOCUMENT"
    MANUAL = "MANUAL"


class SourceStatus(str, Enum):
    """Operational status of a source."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    BLOCKED = "BLOCKED"
    MOVED = "MOVED"
    INACCESSIBLE = "INACCESSIBLE"
    UNKNOWN = "UNKNOWN"


class AccessType(str, Enum):
    """Access tier for a source. Public sources are primary; paid are strictly optional."""
    PUBLIC = "PUBLIC"
    AUTHENTICATED = "AUTHENTICATED"
    PAID = "PAID"
    UNKNOWN = "UNKNOWN"


class AuthenticationType(str, Enum):
    """Authentication mechanism required by an official API source."""
    NONE = "NONE"
    API_KEY = "API_KEY"
    BEARER_TOKEN = "BEARER_TOKEN"
    OAUTH2 = "OAUTH2"
    BASIC = "BASIC"
    UNKNOWN = "UNKNOWN"


class SourceOrigin(str, Enum):
    """Origin tracking: manual entries take precedence over automated discovery."""
    MANUAL = "MANUAL"
    AUTOMATIC = "AUTOMATIC"
    IMPORTED = "IMPORTED"


class DiscoveryStatus(str, Enum):
    """Validation lifecycle status for discovered sources."""
    DISCOVERED = "DISCOVERED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    STALE = "STALE"


class DiscoveryRunStatus(str, Enum):
    """Execution status of an automatic source discovery run."""
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    NO_SEARCH_PROVIDER = "NO_SEARCH_PROVIDER"
    NO_OFFICIAL_SOURCE_FOUND = "NO_OFFICIAL_SOURCE_FOUND"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class DomainValidationStatus(str, Enum):
    """Domain authority status evaluated by DomainValidator."""
    OFFICIAL = "OFFICIAL"
    RELATED_OFFICIAL = "RELATED_OFFICIAL"
    NOT_OFFICIAL = "NOT_OFFICIAL"
    UNKNOWN = "UNKNOWN"


class RelevanceTier(str, Enum):
    """Relevance tier classification for discovered sources."""
    VERY_HIGH = "VERY_HIGH"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    IRRELEVANT = "IRRELEVANT"


class CollectionStatus(str, Enum):
    """Execution status for web content collection operations."""
    COLLECTED = "COLLECTED"
    NOT_FOUND = "NOT_FOUND"
    FORBIDDEN = "FORBIDDEN"
    UNAUTHORIZED = "UNAUTHORIZED"
    TIMEOUT = "TIMEOUT"
    TOO_LARGE = "TOO_LARGE"
    INVALID_CONTENT = "INVALID_CONTENT"
    DOMAIN_REJECTED = "DOMAIN_REJECTED"
    NETWORK_ERROR = "NETWORK_ERROR"
    BLOCKED = "BLOCKED"
    DOCUMENT_REQUIRES_STEP_5 = "DOCUMENT_REQUIRES_STEP_5"
    SSRF_REJECTED = "SSRF_REJECTED"


class DocumentClassification(str, Enum):
    """Classification of document nature/type (What kind of document is this?)."""
    LICENSE_TERMS = "LICENSE_TERMS"
    EULA = "EULA"
    LICENSING_GUIDE = "LICENSING_GUIDE"
    PRODUCT_TERMS = "PRODUCT_TERMS"
    LICENSING_BRIEF = "LICENSING_BRIEF"
    PRODUCT_DOCUMENTATION = "PRODUCT_DOCUMENTATION"
    SUBSCRIPTION_TERMS = "SUBSCRIPTION_TERMS"
    DEPLOYMENT_GUIDE = "DEPLOYMENT_GUIDE"
    OTHER_OFFICIAL_DOCUMENT = "OTHER_OFFICIAL_DOCUMENT"
    UNKNOWN = "UNKNOWN"


class DocumentCollectionStatus(str, Enum):
    """Execution lifecycle status for PDF / Document collection."""
    DISCOVERED = "DISCOVERED"
    DOWNLOADING = "DOWNLOADING"
    COLLECTED = "COLLECTED"
    PARSED = "PARSED"
    OCR_REQUIRED = "OCR_REQUIRED"
    NOT_FOUND = "NOT_FOUND"
    FORBIDDEN = "FORBIDDEN"
    UNAUTHORIZED = "UNAUTHORIZED"
    TIMEOUT = "TIMEOUT"
    TOO_LARGE = "TOO_LARGE"
    INVALID_DOCUMENT = "INVALID_DOCUMENT"
    DOMAIN_REJECTED = "DOMAIN_REJECTED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class ApiCollectionStatus(str, Enum):
    """Execution status for optional vendor API collection."""
    COLLECTED = "COLLECTED"
    PAID_SOURCE_UNAVAILABLE = "PAID_SOURCE_UNAVAILABLE"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    ACCESS_DENIED = "ACCESS_DENIED"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    VENDOR_SERVER_ERROR = "VENDOR_SERVER_ERROR"
    TIMEOUT = "TIMEOUT"
    TOO_LARGE = "TOO_LARGE"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    DOMAIN_REJECTED = "DOMAIN_REJECTED"
    NETWORK_ERROR = "NETWORK_ERROR"
    FAILED = "FAILED"


# -------------------------------------------------------------
# STEP 7 & 8: License Fact Taxonomy & Validation Enums
# -------------------------------------------------------------

class FactType(str, Enum):
    """Taxonomy of discrete, verifiable licensing facts."""
    LICENSE_CLASSIFICATION = "LICENSE_CLASSIFICATION"
    LICENSE_TYPE = "LICENSE_TYPE"
    LICENSE_AVAILABILITY = "LICENSE_AVAILABILITY"
    LICENSE_REQUIRED = "LICENSE_REQUIRED"
    LICENSE_MODEL = "LICENSE_MODEL"
    LICENSE_METRIC = "LICENSE_METRIC"
    LICENSE_DURATION = "LICENSE_DURATION"
    FREE_TIER_AVAILABLE = "FREE_TIER_AVAILABLE"
    PAID_TIER_AVAILABLE = "PAID_TIER_AVAILABLE"
    PARENT_PRODUCT = "PARENT_PRODUCT"
    COMMERCIAL_USE = "COMMERCIAL_USE"
    COMMERCIAL_USE_ALLOWED = "COMMERCIAL_USE_ALLOWED"
    EDUCATIONAL_USE = "EDUCATIONAL_USE"
    TRIAL_AVAILABLE = "TRIAL_AVAILABLE"
    ENTITLEMENT_REQUIRED = "ENTITLEMENT_REQUIRED"
    SECONDARY_DEVICE_RIGHTS = "SECONDARY_DEVICE_RIGHTS"
    VIRTUALIZATION_RIGHTS = "VIRTUALIZATION_RIGHTS"


class FactStatus(str, Enum):
    """Validation lifecycle status for a licensing fact."""
    EXTRACTED = "EXTRACTED"
    VALIDATED = "VALIDATED"
    CONFLICT = "CONFLICT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class EvidenceType(str, Enum):
    """Degree of directness for supporting source evidence."""
    DIRECT_STATEMENT = "DIRECT_STATEMENT"
    STRUCTURED_FIELD = "STRUCTURED_FIELD"
    TABLE = "TABLE"
    METADATA = "METADATA"
    INFERRED = "INFERRED"


class ExtractionConfidence(str, Enum):
    """Discrete confidence tier for an extracted fact, consolidated profile or match candidate."""
    VERY_HIGH = "VERY_HIGH"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class ExtractionRunStatus(str, Enum):
    """Execution status of an extraction run."""
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    NO_EVIDENCE_AVAILABLE = "NO_EVIDENCE_AVAILABLE"


# -------------------------------------------------------------
# STEP 9: Profile Consolidation Enums
# -------------------------------------------------------------

class ProfileStatus(str, Enum):
    """Consolidated lifecycle status of an application-level license intelligence profile."""
    VALIDATED = "VALIDATED"
    PARTIALLY_VALIDATED = "PARTIALLY_VALIDATED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"


# -------------------------------------------------------------
# STEP 11: Application Catalog & Batch Research Enums
# -------------------------------------------------------------

class ApplicationStatus(str, Enum):
    """Lifecycle status for managed software applications in catalog."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"


class ApplicationResearchStatus(str, Enum):
    """Current research lifecycle state of a cataloged application."""
    NOT_RESEARCHED = "NOT_RESEARCHED"
    QUEUED = "QUEUED"
    RESEARCHING = "RESEARCHING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class BatchStatus(str, Enum):
    """Execution status for batch research jobs."""
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class BatchItemStatus(str, Enum):
    """Execution status for individual application research tasks within a batch."""
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


# -------------------------------------------------------------
# STEP 12: Source Monitoring & Change Detection Enums
# -------------------------------------------------------------

class MonitorFrequency(str, Enum):
    """Scheduled check frequency for monitored sources."""
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    CUSTOM = "CUSTOM"


class MonitorStatus(str, Enum):
    """Operational status of a source monitor."""
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ERROR = "ERROR"
    DISABLED = "DISABLED"


class MonitoringRunStatus(str, Enum):
    """Outcome status of a source check run."""
    RUNNING = "RUNNING"
    UNCHANGED = "UNCHANGED"
    CHANGED = "CHANGED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


class ChangeClassification(str, Enum):
    """Classification of content difference between document versions."""
    NO_CHANGE = "NO_CHANGE"
    CONTENT_CHANGE = "CONTENT_CHANGE"
    LICENSING_RELEVANT_CHANGE = "LICENSING_RELEVANT_CHANGE"
    DOCUMENT_METADATA_CHANGE = "DOCUMENT_METADATA_CHANGE"
    NON_LICENSING_CHANGE = "NON_LICENSING_CHANGE"
    UNKNOWN_CHANGE = "UNKNOWN_CHANGE"


class FactChangeType(str, Enum):
    """Type of fact change detected after validation."""
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    MODIFIED = "MODIFIED"
    UNCHANGED = "UNCHANGED"
    CONFLICT_CREATED = "CONFLICT_CREATED"
    CONFLICT_RESOLVED = "CONFLICT_RESOLVED"


class AlertType(str, Enum):
    """Categories of licensing change alerts."""
    LICENSE_FACT_CHANGED = "LICENSE_FACT_CHANGED"
    LICENSE_MODEL_CHANGED = "LICENSE_MODEL_CHANGED"
    LICENSE_METRIC_CHANGED = "LICENSE_METRIC_CHANGED"
    LICENSE_REQUIREMENT_CHANGED = "LICENSE_REQUIREMENT_CHANGED"
    LICENSE_CLASSIFICATION_CHANGED = "LICENSE_CLASSIFICATION_CHANGED"
    TRIAL_CHANGED = "TRIAL_CHANGED"
    CONFLICT_CREATED = "CONFLICT_CREATED"
    CONFLICT_RESOLVED = "CONFLICT_RESOLVED"
    SOURCE_CHANGED = "SOURCE_CHANGED"


class AlertSeverity(str, Enum):
    """Severity tier for licensing change alerts."""
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    """Lifecycle status for a licensing alert."""
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    IGNORED = "IGNORED"


# -------------------------------------------------------------
# STEP 13: Endpoint Inventory & Identity Resolution Enums
# -------------------------------------------------------------

class DeviceStatus(str, Enum):
    """Lifecycle status of an endpoint device."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    RETIRED = "RETIRED"


class DetectedAppStatus(str, Enum):
    """Operational status of a detected software installation."""
    ACTIVE = "ACTIVE"
    REMOVED = "REMOVED"
    UNKNOWN = "UNKNOWN"


class DetectionMethod(str, Enum):
    """Mechanism used to discover application on endpoint."""
    WINDOWS_REGISTRY = "WINDOWS_REGISTRY"
    WINDOWS_REGISTRY_64 = "WINDOWS_REGISTRY_64"
    WINDOWS_REGISTRY_32 = "WINDOWS_REGISTRY_32"
    WINDOWS_USER_REGISTRY = "WINDOWS_USER_REGISTRY"
    WINDOWS_APPX = "WINDOWS_APPX"
    WINDOWS_UNINSTALL = "WINDOWS_UNINSTALL"
    MACOS_APPLICATIONS = "MACOS_APPLICATIONS"
    LINUX_PACKAGES = "LINUX_PACKAGES"
    PACKAGE_MANAGER = "PACKAGE_MANAGER"
    MANUAL_IMPORT = "MANUAL_IMPORT"
    API_IMPORT = "API_IMPORT"
    ENDPOINT_AGENT = "ENDPOINT_AGENT"
    FUTURE_AGENT = "FUTURE_AGENT"


class MatchType(str, Enum):
    """Resolution matching outcome against application catalog."""
    EXACT_MATCH = "EXACT_MATCH"
    NORMALIZED_MATCH = "NORMALIZED_MATCH"
    FUZZY_MATCH = "FUZZY_MATCH"
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"
    NO_MATCH = "NO_MATCH"
    MANUAL_MATCH = "MANUAL_MATCH"


class ResolutionQueueStatus(str, Enum):
    """Human review lifecycle state in the unresolved queue."""
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


# -------------------------------------------------------------
# STEP 14: Entitlement & License Position Enums
# -------------------------------------------------------------

class EntitlementType(str, Enum):
    """Category/model of acquired license entitlement."""
    PURCHASED = "PURCHASED"
    SUBSCRIBED = "SUBSCRIBED"
    GRANTED = "GRANTED"
    TRIAL = "TRIAL"
    EDUCATIONAL = "EDUCATIONAL"
    OEM = "OEM"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class EntitlementStatus(str, Enum):
    """Operational validity of an entitlement."""
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class EntitlementSourceType(str, Enum):
    """Origin of entitlement record."""
    MANUAL_ENTRY = "MANUAL_ENTRY"
    CSV_IMPORT = "CSV_IMPORT"
    VENDOR_EXPORT = "VENDOR_EXPORT"
    AUTHORIZED_API = "AUTHORIZED_API"
    CONTRACT = "CONTRACT"
    PURCHASE_RECORD = "PURCHASE_RECORD"


class LicensePositionStatus(str, Enum):
    """License position reconciliation state (distinct from legal compliance)."""
    COMPLIANT_POSITION = "COMPLIANT_POSITION"
    UNDER_LICENSED_POSITION = "UNDER_LICENSED_POSITION"
    OVER_LICENSED_POSITION = "OVER_LICENSED_POSITION"
    UNKNOWN_POSITION = "UNKNOWN_POSITION"
    NOT_CALCULABLE = "NOT_CALCULABLE"


# -------------------------------------------------------------
# STEP 15: Audit & Quality Enums
# -------------------------------------------------------------

class AuditEventType(str, Enum):
    """Immutable audit event categories."""
    APPLICATION_CREATED = "APPLICATION_CREATED"
    APPLICATION_UPDATED = "APPLICATION_UPDATED"
    SOURCE_DISCOVERED = "SOURCE_DISCOVERED"
    SOURCE_COLLECTED = "SOURCE_COLLECTED"
    SOURCE_CHANGED = "SOURCE_CHANGED"
    DOCUMENT_COLLECTED = "DOCUMENT_COLLECTED"
    DOCUMENT_CHANGED = "DOCUMENT_CHANGED"
    FACT_EXTRACTED = "FACT_EXTRACTED"
    FACT_VALIDATED = "FACT_VALIDATED"
    FACT_REJECTED = "FACT_REJECTED"
    FACT_REVIEW_REQUIRED = "FACT_REVIEW_REQUIRED"
    PROFILE_CREATED = "PROFILE_CREATED"
    PROFILE_UPDATED = "PROFILE_UPDATED"
    ENTITLEMENT_CREATED = "ENTITLEMENT_CREATED"
    ENTITLEMENT_UPDATED = "ENTITLEMENT_UPDATED"
    CONSUMPTION_CREATED = "CONSUMPTION_CREATED"
    POSITION_CALCULATED = "POSITION_CALCULATED"
    ALERT_CREATED = "ALERT_CREATED"
    ALERT_RESOLVED = "ALERT_RESOLVED"
    RESEARCH_DECISION_CREATED = "RESEARCH_DECISION_CREATED"
    RESEARCH_DECISION_UPDATED = "RESEARCH_DECISION_UPDATED"
    RESEARCH_QUEUE_PROCESSED = "RESEARCH_QUEUE_PROCESSED"
    REVIEW_AUTO_RESOLVED = "REVIEW_AUTO_RESOLVED"


# -------------------------------------------------------------
# STEP 17.7: Automatic Review Resolution Enums
# -------------------------------------------------------------

class ReviewReason(str, Enum):
    """Structured categorical reasons for an application remaining or being marked REVIEW_REQUIRED."""
    UNKNOWN_IDENTITY = "UNKNOWN_IDENTITY"
    AMBIGUOUS_IDENTITY = "AMBIGUOUS_IDENTITY"
    MISSING_VENDOR = "MISSING_VENDOR"
    MISSING_VERSION = "MISSING_VERSION"
    MISSING_LICENSE_EVIDENCE = "MISSING_LICENSE_EVIDENCE"
    CONFLICTING_LICENSE_EVIDENCE = "CONFLICTING_LICENSE_EVIDENCE"
    VERSION_SCOPE_UNKNOWN = "VERSION_SCOPE_UNKNOWN"
    EDITION_SCOPE_UNKNOWN = "EDITION_SCOPE_UNKNOWN"
    LICENSE_METRIC_UNKNOWN = "LICENSE_METRIC_UNKNOWN"
    RULE_CONFLICT = "RULE_CONFLICT"
    SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    OTHER = "OTHER"


class ResolutionMethod(str, Enum):
    """Method by which a review required record was evaluated or resolved."""
    DETERMINISTIC_RULE = "DETERMINISTIC_RULE"
    KNOWN_PROFILE = "KNOWN_PROFILE"
    SEARXNG_SEARCH = "SEARXNG_SEARCH"
    WEB_SEARCH = "WEB_SEARCH"
    OFFICIAL_DOCUMENT = "OFFICIAL_DOCUMENT"
    VALIDATION = "VALIDATION"


class FinalLicenseStatus(str, Enum):
    """Definitive final licensing states produced by the resolution engine."""
    LICENSE_REQUIRED_NO = "LICENSE_REQUIRED_NO"
    LICENSE_REQUIRED_YES = "LICENSE_REQUIRED_YES"
    LICENSE_REQUIRED_CONTEXT_DEPENDENT = "LICENSE_REQUIRED_CONTEXT_DEPENDENT"
    LICENSE_UNKNOWN = "LICENSE_UNKNOWN"
    RESEARCH_REQUIRED = "RESEARCH_REQUIRED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


# -------------------------------------------------------------
# STEP 17: Intelligent Research Prioritization Enums
# -------------------------------------------------------------

class ResearchDecision(str, Enum):
    """Categorical outcome of research decision engine."""
    RESEARCH_REQUIRED = "RESEARCH_REQUIRED"
    REFRESH_REQUIRED = "REFRESH_REQUIRED"
    NO_RESEARCH_REQUIRED = "NO_RESEARCH_REQUIRED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNKNOWN = "UNKNOWN"


class ResearchPriority(str, Enum):
    """Execution priority ranking for research candidates."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


class ResearchQueueStatus(str, Enum):
    """Lifecycle status of a research queue candidate."""
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    CANCELLED = "CANCELLED"


class QualityCategory(str, Enum):
    """Deterministic application quality tiers based on score (0-100)."""
    EXCELLENT = "EXCELLENT"  # 90-100
    GOOD = "GOOD"            # 75-89
    FAIR = "FAIR"            # 50-74
    POOR = "POOR"            # 25-49
    INSUFFICIENT = "INSUFFICIENT" # 0-24


class QualityIssueType(str, Enum):
    """Categories of data quality flags and gaps."""
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    MISSING_SOURCE = "MISSING_SOURCE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    CONFLICT = "CONFLICT"
    STALE_SOURCE = "STALE_SOURCE"
    UNKNOWN_LICENSE_MODEL = "UNKNOWN_LICENSE_MODEL"
    UNKNOWN_LICENSE_METRIC = "UNKNOWN_LICENSE_METRIC"
    METRIC_MISMATCH = "METRIC_MISMATCH"
    INVALID_SCOPE = "INVALID_SCOPE"


class IssueStatus(str, Enum):
    """Status of a quality issue."""
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"
    IGNORED = "IGNORED"


# Controlled Fact Values & Step 18 Taxonomy

class LicenseClassificationValue(str, Enum):
    """Values for LICENSE_CLASSIFICATION (Step 19 Decoupled Taxonomy)."""
    OPEN_SOURCE = "OPEN_SOURCE"
    FREEWARE = "FREEWARE"
    OS_BUNDLED = "OS_BUNDLED"
    COMMERCIAL = "COMMERCIAL"
    COMMERCIAL_COMPONENT = "COMMERCIAL_COMPONENT"
    TRIAL = "TRIAL"
    EDUCATIONAL = "EDUCATIONAL"
    FREE_AND_PAID = "FREE_AND_PAID"
    PROPRIETARY = "PROPRIETARY"
    NON_COMMERCIAL = "NON_COMMERCIAL"
    PUBLIC_DOMAIN = "PUBLIC_DOMAIN"
    UNKNOWN = "UNKNOWN"


class AvailabilityModel(str, Enum):
    """Step 18 & 19: Availability model describing licensing tiers."""
    FREE = "FREE"
    FREE_TIER = "FREE_TIER"
    PAID_ONLY = "PAID_ONLY"
    FREE_AND_PAID = "FREE_AND_PAID"
    TRIAL = "TRIAL"
    BUNDLED = "BUNDLED"
    UNKNOWN = "UNKNOWN"


class LicenseRequirement(str, Enum):
    """Step 18 & 19: Definitive license requirement indicating whether entitlement/payment is required."""
    YES = "YES"
    NO = "NO"
    CONTEXT_DEPENDENT = "CONTEXT_DEPENDENT"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class SourceAuthorityTier(str, Enum):
    """Step 18: Source authority tiers for evidence validation."""
    TIER_1 = "TIER_1"  # Official vendor licensing terms, EULA, product terms, licensing guide
    TIER_2 = "TIER_2"  # Official vendor documentation, product/pricing pages
    TIER_3 = "TIER_3"  # Authorized reseller/distributor
    TIER_4 = "TIER_4"  # Third-party technical/documentation source
    TIER_5 = "TIER_5"  # Blogs/forums/search-only evidence


class VersionScope(str, Enum):
    """Step 18: Version applicability scope for evidence and facts."""
    EXACT_VERSION = "EXACT_VERSION"
    VERSION_FAMILY = "VERSION_FAMILY"
    ALL_VERSIONS = "ALL_VERSIONS"
    UNKNOWN = "UNKNOWN"


class EditionScope(str, Enum):
    """Step 18: Edition applicability scope for evidence and facts."""
    EXACT_EDITION = "EXACT_EDITION"
    PRODUCT_FAMILY = "PRODUCT_FAMILY"
    ALL_EDITIONS = "ALL_EDITIONS"
    UNKNOWN = "UNKNOWN"


class LicenseRequiredValue(str, Enum):
    """Values for LICENSE_REQUIRED fact property."""
    TRUE = "TRUE"
    FALSE = "FALSE"
    CONTEXT_DEPENDENT = "CONTEXT_DEPENDENT"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class LicenseModelValue(str, Enum):
    """Values for LICENSE_MODEL."""
    SUBSCRIPTION = "SUBSCRIPTION"
    PERPETUAL = "PERPETUAL"
    PERPETUAL_WITH_MAINTENANCE = "PERPETUAL_WITH_MAINTENANCE"
    TERM = "TERM"
    CONCURRENT = "CONCURRENT"
    NAMED_USER = "NAMED_USER"
    DEVICE = "DEVICE"
    NETWORK = "NETWORK"
    FLOATING = "FLOATING"
    TRIAL = "TRIAL"
    FREE = "FREE"
    OPEN_SOURCE = "OPEN_SOURCE"
    OEM = "OEM"
    UNKNOWN = "UNKNOWN"


class LicenseTypeValue(str, Enum):
    """Controlled legal and license family classifications."""
    MIT = "MIT"
    APACHE_2_0 = "Apache-2.0"
    GPL_2_0 = "GPL-2.0"
    GPL_3_0 = "GPL-3.0"
    LGPL = "LGPL"
    BSD = "BSD"
    MPL = "MPL"
    PROPRIETARY = "Proprietary"
    COMMERCIAL = "Commercial"
    FREEWARE = "Freeware"
    PUBLIC_DOMAIN = "Public Domain"
    UNKNOWN = "Unknown"


class LicenseMetricValue(str, Enum):
    """Values for LICENSE_METRIC (Step 19 Granular Metrics)."""
    USER = "USER"
    DEVICE = "DEVICE"
    CORE = "CORE"
    PROCESSOR = "PROCESSOR"
    INSTALLATION = "INSTALLATION"
    INSTANCE = "INSTANCE"
    CONCURRENT_USER = "CONCURRENT_USER"
    CONCURRENT_DEVICE = "CONCURRENT_DEVICE"
    SUBSCRIPTION = "SUBSCRIPTION"
    SITE = "SITE"
    ORGANIZATION = "ORGANIZATION"
    NAMED_USER = "NAMED_USER"
    CPU = "CPU"
    SOCKET = "SOCKET"
    SERVER = "SERVER"
    VM = "VM"
    NONE = "NONE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    CONTEXT_DEPENDENT = "CONTEXT_DEPENDENT"
    UNKNOWN = "UNKNOWN"


class ReliabilityBand(str, Enum):
    """Step 19: Discrete reliability tiers."""
    VERY_HIGH = "VERY_HIGH"  # 95–100
    HIGH = "HIGH"            # 80–94
    MEDIUM = "MEDIUM"        # 60–79
    LOW = "LOW"              # 40–59
    VERY_LOW = "VERY_LOW"    # 0–39


class DataQualityStatus(str, Enum):
    """Step 19: Application level data quality classification."""
    VALID = "VALID"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    EVIDENCE_MISSING = "EVIDENCE_MISSING"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"


class ContradictionSeverity(str, Enum):
    """Step 19: Severity ratings for data contradictions and quality issues."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class LicenseDurationValue(str, Enum):
    """Values for LICENSE_DURATION."""
    MONTHLY = "MONTHLY"
    ANNUAL = "ANNUAL"
    MULTI_YEAR = "MULTI_YEAR"
    PERPETUAL = "PERPETUAL"
    TRIAL_PERIOD = "TRIAL_PERIOD"
    UNKNOWN = "UNKNOWN"


class UsageRightValue(str, Enum):
    """Values for COMMERCIAL_USE, EDUCATIONAL_USE, SECONDARY_DEVICE_RIGHTS, VIRTUALIZATION_RIGHTS."""
    ALLOWED = "ALLOWED"
    RESTRICTED = "RESTRICTED"
    NOT_ALLOWED = "NOT_ALLOWED"
    UNKNOWN = "UNKNOWN"


class BooleanFactValue(str, Enum):
    """Values for TRIAL_AVAILABLE."""
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"

