"""
Automatic Review Required Resolution Engine (Step 19 Hardening).
Resolves software inventory using Identity Resolution, Canonical Recognition Catalog,
Existing Knowledge reuse, Deterministic Rules, and Transparent 6-Part Reliability Scoring.
Strictly eliminates generic 'OPEN_SOURCE / FREEWARE' and 'Per User / Device' defaults.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session

from backend.models.enums import (
    FinalLicenseStatus,
    ResolutionMethod,
    ReviewReason,
    ExtractionConfidence,
    AuditEventType,
    MatchType,
    ProfileStatus,
    LicenseClassificationValue,
    AvailabilityModel,
    LicenseRequirement,
    LicenseMetricValue,
    SourceAuthorityTier,
    EvidenceType,
    DataQualityStatus,
)
from backend.models.inventory import DetectedApplication
from backend.models.application import Application
from backend.models.profile import LicenseProfile
from backend.models.audit import AuditEvent
from backend.models.resolution import ReviewResolutionRun
from backend.models.data_quality import DataQualityIssue
from backend.inventory.detection.detection_normalizer import DetectionNormalizer
from backend.inventory.recognition.catalog import (
    RecognitionCatalog,
    CatalogRecognitionEntry,
    sanitize_vendor_name,
)
from backend.validation.reliability_score import ReliabilityScoreEngine, ReliabilityBreakdown
from backend.validation.contradiction_detector import DataContradictionDetector

from backend.inventory.recognition.microsoft_identity_resolver import (
    MicrosoftProductIdentityResolver,
    WindowsProductCategory,
)
from backend.research.windows_product_adapter import (
    WindowsProductResearchAdapter,
)
from backend.validation.microsoft_evidence_validator import (
    MicrosoftEvidenceValidator,
)

logger = logging.getLogger(__name__)


class ResolutionResult:
    """Encapsulates the comprehensive, structured outcome of a review resolution attempt."""
    def __init__(
        self,
        detected_application_id: Optional[int],
        application_id: Optional[int],
        old_status: str,
        old_reason: Optional[ReviewReason],
        new_status: FinalLicenseStatus,
        review_reason: Optional[ReviewReason],
        method: ResolutionMethod,
        confidence: ExtractionConfidence,
        result_message: str,
        evidence: Optional[str] = None,
        terms_summary: Optional[str] = None,
        primary_url: Optional[str] = None,
        canonical_name: Optional[str] = None,
        canonical_vendor: Optional[str] = None,
        classification: str = "UNKNOWN",
        availability: str = "UNKNOWN",
        license_requirement: str = "UNKNOWN",
        license_model: str = "UNKNOWN",
        license_metric: str = "UNKNOWN",
        parent_product: Optional[str] = None,
        reliability_breakdown: Optional[ReliabilityBreakdown] = None,
        data_quality_status: DataQualityStatus = DataQualityStatus.UNKNOWN,
    ):
        self.detected_application_id = detected_application_id
        self.application_id = application_id
        self.old_status = old_status
        self.old_reason = old_reason
        self.new_status = new_status
        self.review_reason = review_reason
        self.method = method
        self.confidence = confidence
        self.result_message = result_message
        self.evidence = evidence
        self.terms_summary = terms_summary
        self.primary_url = primary_url
        self.canonical_name = canonical_name
        self.canonical_vendor = canonical_vendor

        # Step 19 Hardened Properties
        self.classification = classification
        self.availability = availability
        self.license_requirement = license_requirement
        self.license_model = license_model
        self.license_metric = license_metric
        self.parent_product = parent_product
        self.reliability_breakdown = reliability_breakdown
        self.data_quality_status = data_quality_status
        self.reliability_score = reliability_breakdown.overall if reliability_breakdown else 50.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detected_application_id": self.detected_application_id,
            "application_id": self.application_id,
            "old_status": self.old_status,
            "old_reason": self.old_reason.value if self.old_reason else None,
            "new_status": self.new_status.value,
            "review_reason": self.review_reason.value if self.review_reason else None,
            "method": self.method.value,
            "confidence": self.confidence.value,
            "result": self.result_message,
            "evidence": self.evidence,
            "terms_summary": self.terms_summary,
            "primary_url": self.primary_url,
            "canonical_name": self.canonical_name,
            "canonical_vendor": self.canonical_vendor,
            "classification": self.classification,
            "availability": self.availability,
            "license_requirement": self.license_requirement,
            "license_model": self.license_model,
            "license_metric": self.license_metric,
            "parent_product": self.parent_product,
            "reliability_score": self.reliability_score,
            "reliability_breakdown": self.reliability_breakdown.to_dict() if self.reliability_breakdown else None,
            "data_quality_status": self.data_quality_status.value if hasattr(self.data_quality_status, "value") else str(self.data_quality_status),
        }


class AutomaticReviewResolver:
    """
    Core engine that attempts automatic resolution for applications marked REVIEW_REQUIRED.
    """

    def __init__(self):
        self.catalog = RecognitionCatalog()

    def resolve_application(
        self,
        db: Session,
        detected_app: Optional[DetectedApplication] = None,
        raw_name: Optional[str] = None,
        raw_publisher: Optional[str] = None,
        version: Optional[str] = None,
        application_id: Optional[int] = None,
    ) -> ResolutionResult:
        """
        Executes multi-tiered automatic resolution for a single application with 6-part reliability scoring.
        """
        # 1. Resolve inputs
        det_id = detected_app.id if detected_app else None
        name = detected_app.raw_name if detected_app else (raw_name or "")
        publisher = detected_app.raw_publisher if detected_app else raw_publisher
        ver = detected_app.detected_version if detected_app else version
        
        normalized_name = DetectionNormalizer.normalize_name(name)
        sanitized_vendor = sanitize_vendor_name(publisher)

        old_status = "REVIEW_REQUIRED"
        old_reason = ReviewReason.UNKNOWN_IDENTITY

        # -------------------------------------------------------------
        # Tier 1: Identity & Ambiguity Check
        # -------------------------------------------------------------
        if not name or not name.strip():
            rel = ReliabilityScoreEngine.calculate_reliability(
                has_exact_identity=False,
                is_vendor_matched=False,
                identity_tier="UNKNOWN",
                source_type="NONE",
                has_evidence=False,
            )
            return self._record_and_return(
                db,
                det_id=det_id,
                app_id=application_id,
                old_status=old_status,
                old_reason=old_reason,
                new_status=FinalLicenseStatus.REVIEW_REQUIRED,
                review_reason=ReviewReason.UNKNOWN_IDENTITY,
                method=ResolutionMethod.DETERMINISTIC_RULE,
                confidence=ExtractionConfidence.UNKNOWN,
                result="Application name is empty or missing.",
                evidence="No application identification string provided in raw inventory.",
                classification=LicenseClassificationValue.UNKNOWN.value,
                availability=AvailabilityModel.UNKNOWN.value,
                license_requirement=LicenseRequirement.UNKNOWN.value,
                license_model="UNKNOWN",
                license_metric=LicenseMetricValue.UNKNOWN.value,
                reliability_breakdown=rel,
            )

        lower_name = name.strip().lower()
        if lower_name in ["acrobat", "adobe acrobat"]:
            rel = ReliabilityScoreEngine.calculate_reliability(
                has_exact_identity=False,
                is_vendor_matched=True,
                identity_tier="PARTIAL",
                source_type="DOCS",
                authority_tier=SourceAuthorityTier.TIER_2,
                evidence_type=EvidenceType.INFERRED,
                evidence_directness_tier="WEAK_INFERENCE",
                is_exact_edition=False,
                is_exact_version=False,
                scope_tier="UNKNOWN",
                validation_passed=False,
                validation_tier="CONFLICT",
                has_evidence=True,
            )
            return self._record_and_return(
                db,
                det_id=det_id,
                app_id=application_id,
                old_status=old_status,
                old_reason=old_reason,
                new_status=FinalLicenseStatus.REVIEW_REQUIRED,
                review_reason=ReviewReason.AMBIGUOUS_IDENTITY,
                method=ResolutionMethod.DETERMINISTIC_RULE,
                confidence=ExtractionConfidence.LOW,
                result="Ambiguous product identity: Multiple editions exist (Reader [Free] vs Standard/Pro [Paid]). Edition scope cannot be established.",
                evidence="Discovered raw name 'Acrobat' without edition discriminator.",
                canonical_name="Adobe Acrobat (Ambiguous Edition)",
                canonical_vendor="Adobe",
                classification=LicenseClassificationValue.COMMERCIAL.value,
                availability=AvailabilityModel.FREE_AND_PAID.value,
                license_requirement=LicenseRequirement.CONTEXT_DEPENDENT.value,
                license_model="Subscription / Perpetual",
                license_metric=LicenseMetricValue.USER.value,
                reliability_breakdown=rel,
            )

        # -------------------------------------------------------------
        # Tier 2: Canonical Recognition Catalog Rules (Deterministic)
        # -------------------------------------------------------------
        rule = self.catalog.find_rule_by_name(normalized_name, sanitized_vendor)
        if not rule and name != normalized_name:
            rule = self.catalog.find_rule_by_name(name, sanitized_vendor)

        if rule:
            res_method = rule.method
            rel = ReliabilityScoreEngine.calculate_reliability(
                has_exact_identity=True,
                is_vendor_matched=True,
                identity_tier="EXACT_VENDOR_CONFIRMED",
                source_type=rule.source_type,
                authority_tier=rule.authority_tier,
                evidence_type=rule.evidence_type,
                evidence_directness_tier="DIRECT_STATEMENT",
                is_exact_edition=True,
                is_exact_version=bool(ver),
                scope_tier="EXACT_ALL" if ver else "PRODUCT_EDITION",
                validation_passed=True,
                validation_tier="CLEAN",
                published_at=datetime.now(timezone.utc),
                has_evidence=True,
            )
            return self._record_and_return(
                db,
                det_id=det_id,
                app_id=application_id,
                old_status=old_status,
                old_reason=old_reason,
                new_status=rule.license_required,
                review_reason=None if rule.license_required != FinalLicenseStatus.REVIEW_REQUIRED else ReviewReason.OTHER,
                method=res_method,
                confidence=rule.confidence,
                result=f"Resolved via Canonical Recognition Catalog: {rule.canonical_name} ({rule.classification})",
                evidence=rule.evidence_quote,
                terms_summary=rule.terms_summary,
                primary_url=rule.primary_url,
                canonical_name=rule.canonical_name,
                canonical_vendor=rule.canonical_vendor,
                classification=rule.classification,
                availability=rule.availability_model,
                license_requirement=rule.license_requirement,
                license_model=rule.licensing_model,
                license_metric=rule.licensing_metric,
                parent_product=rule.parent_product,
                reliability_breakdown=rel,
            )

        # -------------------------------------------------------------
        # Tier 3: Dedicated Step 20 Microsoft & Windows Research Pipeline
        # -------------------------------------------------------------
        if MicrosoftProductIdentityResolver.is_microsoft_or_windows_related(name, sanitized_vendor, name):
            identity = MicrosoftProductIdentityResolver.resolve_identity(
                raw_name=name,
                raw_publisher=sanitized_vendor,
                raw_version=ver,
                install_source=detected_app.install_source if detected_app else None,
                architecture=detected_app.architecture if detected_app else None,
                raw_package_name=name,
            )
            research = WindowsProductResearchAdapter.research_product(
                identity=identity,
                prev_classification="OS_BUNDLED" if "windows" in name.lower() else "COMMERCIAL",
                prev_license_required="NO" if "windows" in name.lower() else "CONTEXT_DEPENDENT",
            )
            validated = MicrosoftEvidenceValidator.validate_and_score(
                app_id=det_id or application_id,
                identity=identity,
                research_result=research,
                prev_classification="OS_BUNDLED" if "windows" in name.lower() else "COMMERCIAL",
                prev_license_required="NO" if "windows" in name.lower() else "CONTEXT_DEPENDENT",
                prev_metric="NOT_APPLICABLE" if "windows" in name.lower() else "UNKNOWN",
            )

            req_status = FinalLicenseStatus.LICENSE_REQUIRED_NO if validated["license_required"] in ["NO", "NOT_APPLICABLE"] else (
                FinalLicenseStatus.LICENSE_REQUIRED_YES if validated["license_required"] == "YES" else FinalLicenseStatus.RESEARCH_REQUIRED
            )

            rel = ReliabilityScoreEngine.calculate_reliability(
                has_exact_identity=True,
                is_vendor_matched=True,
                identity_tier="EXACT_VENDOR_CONFIRMED",
                source_type="TERMS" if validated["classification"] in ["OS_BUNDLED", "COMMERCIAL", "COMMERCIAL_COMPONENT"] else "DOCS",
                evidence_directness_tier="DIRECT_STATEMENT" if validated["evidence_status"] == "VERIFIED" else "STRONG_AVAILABILITY",
                is_exact_edition=True,
                is_exact_version=bool(ver),
                scope_tier="EXACT_ALL" if ver else "PRODUCT_EDITION",
                validation_passed=True,
                validation_tier="CLEAN",
                has_evidence=validated["evidence_status"] == "VERIFIED",
            )

            return self._record_and_return(
                db,
                det_id=det_id,
                app_id=application_id,
                old_status=old_status,
                old_reason=old_reason,
                new_status=req_status,
                review_reason=None if req_status != FinalLicenseStatus.REVIEW_REQUIRED else ReviewReason.OTHER,
                method=ResolutionMethod.DETERMINISTIC_RULE,
                confidence=ExtractionConfidence.HIGH,
                result=f"Resolved via Microsoft Licensing & Windows Adapter: {validated['canonical_name']} ({validated['classification']})",
                evidence=validated["evidence_quote"],
                terms_summary=f"Model: {validated['license_model']}, Metric: {validated['metric']}",
                primary_url=validated.get("source_url", "https://www.microsoft.com"),
                canonical_name=validated["canonical_name"],
                canonical_vendor=validated["vendor"],
                classification=validated["classification"],
                availability=validated["availability"],
                license_requirement=validated["license_required"],
                license_model=validated["license_model"],
                license_metric=validated["metric"],
                parent_product=validated["parent_product"],
                reliability_breakdown=rel,
            )

        # -------------------------------------------------------------
        # Tier 4: Recognized OEM Hardware Drivers & Utilities
        # -------------------------------------------------------------
        if self.catalog.is_oem_hardware_component(name, sanitized_vendor) or self.catalog.is_oem_hardware_component(normalized_name, sanitized_vendor):
            rel = ReliabilityScoreEngine.calculate_reliability(
                has_exact_identity=True,
                is_vendor_matched=True,
                identity_tier="LIKELY",
                source_type="DOCS",
                authority_tier=SourceAuthorityTier.TIER_2,
                evidence_type=EvidenceType.STRUCTURED_FIELD,
                evidence_directness_tier="STRONG_AVAILABILITY",
                is_exact_edition=False,
                is_exact_version=bool(ver),
                scope_tier="PRODUCT_ONLY",
                validation_passed=True,
                validation_tier="CLEAN",
                has_evidence=True,
            )
            return self._record_and_return(
                db,
                det_id=det_id,
                app_id=application_id,
                old_status=old_status,
                old_reason=old_reason,
                new_status=FinalLicenseStatus.LICENSE_REQUIRED_NO,
                review_reason=None,
                method=ResolutionMethod.DETERMINISTIC_RULE,
                confidence=ExtractionConfidence.HIGH,
                result=f"Recognized OEM Hardware Utility / Driver: {normalized_name}",
                evidence="Device OEM firmware/driver utility bundled with hardware.",
                terms_summary="OEM hardware companion software provided free for use with corresponding device hardware.",
                primary_url="https://support.lenovo.com" if "lenovo" in (sanitized_vendor or "").lower() else "https://www.intel.com",
                canonical_name=normalized_name,
                canonical_vendor=sanitized_vendor or "OEM Hardware",
                classification=LicenseClassificationValue.OS_BUNDLED.value,
                availability=AvailabilityModel.BUNDLED.value,
                license_requirement=LicenseRequirement.NO.value,
                license_model="OEM Hardware Bundled Driver / Utility",
                license_metric=LicenseMetricValue.NOT_APPLICABLE.value,
                reliability_breakdown=rel,
            )

        # -------------------------------------------------------------
        # Tier 5: Existing Knowledge Base Check
        # -------------------------------------------------------------
        if sanitized_vendor and normalized_name:
            existing_prof = db.query(LicenseProfile).filter(
                LicenseProfile.vendor_name.ilike(sanitized_vendor),
                LicenseProfile.product_name.ilike(normalized_name)
            ).first()

            if existing_prof and existing_prof.profile_status in [ProfileStatus.VALIDATED, ProfileStatus.PARTIALLY_VALIDATED]:
                is_req = existing_prof.license_required in ["YES", "TRUE"] or "COMMERCIAL" in (existing_prof.license_classification or "").upper()
                status = FinalLicenseStatus.LICENSE_REQUIRED_YES if is_req else FinalLicenseStatus.LICENSE_REQUIRED_NO
                
                # Use stored subscores or calculate from profile
                rel = ReliabilityScoreEngine.calculate_reliability(
                    has_exact_identity=True,
                    is_vendor_matched=True,
                    identity_tier="EXACT_VENDOR_CONFIRMED",
                    source_type="TERMS",
                    authority_tier=SourceAuthorityTier.TIER_1,
                    evidence_type=EvidenceType.DIRECT_STATEMENT,
                    evidence_directness_tier="DIRECT_STATEMENT",
                    is_exact_edition=bool(existing_prof.edition),
                    is_exact_version=bool(existing_prof.version),
                    scope_tier="EXACT_ALL" if existing_prof.version else "PRODUCT_EDITION",
                    validation_passed=True,
                    validation_tier="CLEAN",
                    has_evidence=True,
                )
                return self._record_and_return(
                    db,
                    det_id=det_id,
                    app_id=application_id,
                    old_status=old_status,
                    old_reason=old_reason,
                    new_status=status,
                    review_reason=None,
                    method=ResolutionMethod.KNOWN_PROFILE,
                    confidence=existing_prof.overall_confidence or ExtractionConfidence.HIGH,
                    result=f"Reused validated knowledge profile ID #{existing_prof.id}",
                    evidence=f"Profile validated: classification={existing_prof.license_classification}.",
                    terms_summary=f"Model: {existing_prof.license_model}, Metric: {existing_prof.license_metric}",
                    primary_url="https://www.google.com",
                    canonical_name=existing_prof.product_name,
                    canonical_vendor=existing_prof.vendor_name,
                    classification=existing_prof.license_classification,
                    availability=existing_prof.availability_model,
                    license_requirement=existing_prof.license_required,
                    license_model=existing_prof.license_model,
                    license_metric=existing_prof.license_metric,
                    parent_product=existing_prof.parent_product,
                    reliability_breakdown=rel,
                )

        # -------------------------------------------------------------
        # Tier 6: Unresolved Commercial Software -> RESEARCH_REQUIRED
        # -------------------------------------------------------------
        if sanitized_vendor and len(sanitized_vendor) > 2 and not any(k in lower_name for k in ["unknown", "temp", "test"]):
            rel = ReliabilityScoreEngine.calculate_reliability(
                has_exact_identity=True,
                is_vendor_matched=bool(sanitized_vendor),
                identity_tier="LIKELY" if sanitized_vendor else "PARTIAL",
                source_type="NONE",
                has_evidence=False,
                authority_tier=None,
                evidence_type=None,
                evidence_directness_tier="NONE",
                is_exact_edition=False,
                is_exact_version=bool(ver),
                scope_tier="PRODUCT_ONLY",
                validation_passed=False,
                validation_tier="EXTRACTED_UNVALIDATED",
            )
            return self._record_and_return(
                db,
                det_id=det_id,
                app_id=application_id,
                old_status=old_status,
                old_reason=old_reason,
                new_status=FinalLicenseStatus.RESEARCH_REQUIRED,
                review_reason=None,
                method=ResolutionMethod.DETERMINISTIC_RULE,
                confidence=ExtractionConfidence.MEDIUM,
                result=f"Identified potential commercial software target '{normalized_name}'. Research required via official source discovery.",
                evidence=f"Publisher '{sanitized_vendor}' detected; licensing documentation discovery required.",
                canonical_name=normalized_name,
                canonical_vendor=sanitized_vendor,
                classification=LicenseClassificationValue.COMMERCIAL.value,
                availability=AvailabilityModel.UNKNOWN.value,
                license_requirement=LicenseRequirement.CONTEXT_DEPENDENT.value,
                license_model="Commercial (Research Needed)",
                license_metric=LicenseMetricValue.UNKNOWN.value,
                reliability_breakdown=rel,
            )

        # -------------------------------------------------------------
        # Tier 7: Final Fallback -> REVIEW_REQUIRED with Structured Reason
        # -------------------------------------------------------------
        fallback_reason = ReviewReason.UNKNOWN_IDENTITY
        if not sanitized_vendor:
            fallback_reason = ReviewReason.MISSING_VENDOR
        elif not ver:
            fallback_reason = ReviewReason.MISSING_VERSION

        rel = ReliabilityScoreEngine.calculate_reliability(
            has_exact_identity=False,
            is_vendor_matched=bool(sanitized_vendor),
            identity_tier="PARTIAL" if sanitized_vendor else "WEAK",
            source_type="NONE",
            has_evidence=False,
            authority_tier=None,
            evidence_type=None,
            evidence_directness_tier="NONE",
            is_exact_edition=False,
            is_exact_version=False,
            scope_tier="UNKNOWN",
            validation_passed=False,
            validation_tier="NONE",
        )
        return self._record_and_return(
            db,
            det_id=det_id,
            app_id=application_id,
            old_status=old_status,
            old_reason=old_reason,
            new_status=FinalLicenseStatus.REVIEW_REQUIRED,
            review_reason=fallback_reason,
            method=ResolutionMethod.DETERMINISTIC_RULE,
            confidence=ExtractionConfidence.UNKNOWN,
            result=f"Unresolved application: {fallback_reason.value}",
            evidence="No matching canonical recognition rule, OS component definition, or validated profile available.",
            canonical_name=normalized_name,
            canonical_vendor=sanitized_vendor,
            classification=LicenseClassificationValue.UNKNOWN.value,
            availability=AvailabilityModel.UNKNOWN.value,
            license_requirement=LicenseRequirement.UNKNOWN.value,
            license_model="UNKNOWN",
            license_metric=LicenseMetricValue.UNKNOWN.value,
            reliability_breakdown=rel,
        )

    def resolve_batch(
        self,
        db: Session,
        limit: int = 20,
        detected_app_ids: Optional[List[int]] = None
    ) -> List[ResolutionResult]:
        """
        Executes automatic review resolution for a batch of applications.
        """
        query = db.query(DetectedApplication)
        if detected_app_ids:
            query = query.filter(DetectedApplication.id.in_(detected_app_ids))
        
        apps = query.limit(limit).all()
        results: List[ResolutionResult] = []

        for app in apps:
            res = self.resolve_application(db, detected_app=app)
            results.append(res)

        return results

    def _record_and_return(
        self,
        db: Session,
        det_id: Optional[int],
        app_id: Optional[int],
        old_status: str,
        old_reason: Optional[ReviewReason],
        new_status: FinalLicenseStatus,
        review_reason: Optional[ReviewReason],
        method: ResolutionMethod,
        confidence: ExtractionConfidence,
        result: str,
        evidence: Optional[str] = None,
        terms_summary: Optional[str] = None,
        primary_url: Optional[str] = None,
        canonical_name: Optional[str] = None,
        canonical_vendor: Optional[str] = None,
        classification: str = "UNKNOWN",
        availability: str = "UNKNOWN",
        license_requirement: str = "UNKNOWN",
        license_model: str = "UNKNOWN",
        license_metric: str = "UNKNOWN",
        parent_product: Optional[str] = None,
        reliability_breakdown: Optional[ReliabilityBreakdown] = None,
    ) -> ResolutionResult:
        """
        Persists resolution run to review_resolution_runs, records audit event if auto-resolved,
        audits contradictions, updates DetectedApplication record, and returns the structured ResolutionResult.
        """
        # Audit contradictions & quality issues
        has_ev = bool(evidence and evidence.strip() and "No application identification" not in evidence and "No matching canonical" not in evidence)
        issues, quality_status = DataContradictionDetector.audit_and_persist_issues(
            db=db,
            application_id=det_id or app_id,
            app_name=canonical_name or "",
            vendor_name=canonical_vendor or "",
            classification=classification,
            availability=availability,
            requirement=license_requirement,
            metric=license_metric,
            evidence_text=evidence,
            has_evidence=has_ev,
            parent_product=parent_product,
        )

        run = ReviewResolutionRun(
            application_id=app_id,
            detected_application_id=det_id,
            old_status=old_status,
            old_reason=old_reason,
            resolution_attempt=1,
            resolution_method=method,
            result=result,
            new_status=new_status,
            confidence=confidence,
            evidence=evidence,
        )
        db.add(run)

        # Update DetectedApplication if available
        if det_id:
            det_app = db.query(DetectedApplication).filter(DetectedApplication.id == det_id).first()
            if det_app:
                if new_status in [FinalLicenseStatus.LICENSE_REQUIRED_NO, FinalLicenseStatus.LICENSE_REQUIRED_YES]:
                    det_app.resolution_type = MatchType.EXACT_MATCH if method == ResolutionMethod.DETERMINISTIC_RULE else MatchType.NORMALIZED_MATCH
                    det_app.resolution_confidence = confidence
                elif new_status == FinalLicenseStatus.RESEARCH_REQUIRED:
                    det_app.resolution_type = MatchType.FUZZY_MATCH
                    det_app.resolution_confidence = confidence

        # Audit Event if resolved automatically
        if new_status in [FinalLicenseStatus.LICENSE_REQUIRED_NO, FinalLicenseStatus.LICENSE_REQUIRED_YES, FinalLicenseStatus.RESEARCH_REQUIRED]:
            audit = AuditEvent(
                event_type=AuditEventType.REVIEW_AUTO_RESOLVED,
                entity_type="DetectedApplication" if det_id else "Application",
                entity_id=det_id or app_id or 0,
                actor_type="SYSTEM",
                actor_id="AutomaticReviewResolver_Step19",
                old_value=json.dumps({"status": old_status, "reason": old_reason.value if old_reason else None}),
                new_value=json.dumps({
                    "status": new_status.value,
                    "method": method.value,
                    "confidence": confidence.value,
                    "result": result,
                    "canonical_name": canonical_name,
                    "canonical_vendor": canonical_vendor,
                    "classification": classification,
                    "availability": availability,
                    "license_requirement": license_requirement,
                    "license_metric": license_metric,
                    "reliability_score": reliability_breakdown.overall if reliability_breakdown else 50.0,
                    "data_quality_status": quality_status.value,
                }),
                description=f"Auto-resolved to {new_status.value} (Classification: {classification}, Metric: {license_metric}, Reliability: {reliability_breakdown.overall if reliability_breakdown else 50.0}%)."
            )
            db.add(audit)

        db.commit()

        return ResolutionResult(
            detected_application_id=det_id,
            application_id=app_id,
            old_status=old_status,
            old_reason=old_reason,
            new_status=new_status,
            review_reason=review_reason,
            method=method,
            confidence=confidence,
            result_message=result,
            evidence=evidence,
            terms_summary=terms_summary,
            primary_url=primary_url,
            canonical_name=canonical_name,
            canonical_vendor=canonical_vendor,
            classification=classification,
            availability=availability,
            license_requirement=license_requirement,
            license_model=license_model,
            license_metric=license_metric,
            parent_product=parent_product,
            reliability_breakdown=reliability_breakdown,
            data_quality_status=quality_status,
        )
