"""
Research Prioritization Engine orchestrator for Step 17.
Constructs candidates from Catalog & Inventory, evaluates decision & priority scoring,
enforces queue deduplication & daily budgets, and dispatches to Step 10 Research Orchestrator.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc

from backend.models.enums import (
    ResearchDecision,
    ResearchPriority,
    ResearchQueueStatus,
    AuditEventType,
    AlertStatus,
    AlertType,
    AlertSeverity,
    ChangeClassification,
    ResolutionQueueStatus,
    MatchType,
    ProfileStatus,
    FactType,
)
from backend.models.application import Application
from backend.models.inventory import DetectedApplication, DeviceApplication, ApplicationResolutionQueue
from backend.models.profile import LicenseProfile, LicenseProfileFact
from backend.models.monitoring import LicenseAlert, LicenseFactChange, SourceMonitor
from backend.models.research_queue import LicenseResearchQueueItem
from backend.audit.quality_engine import ApplicationQualityEngine
from backend.audit.audit_service import AuditService
from backend.orchestration.research_orchestrator import ResearchOrchestrator

from .research_policy import ResearchPolicy, DEFAULT_RESEARCH_POLICY
from .research_candidate import ResearchCandidate
from .decision_engine import ResearchDecisionEngine
from .priority_score import PriorityScoreEngine
from .decision_result import (
    ResearchDecisionResult,
    DecisionFactor,
    PrioritizationSummary,
    QueueItemResponse,
    QueueProcessResponse,
)


class ResearchPrioritizationEngine:
    """Orchestrates deterministic research evaluation, queue management, and execution."""

    def __init__(self, policy: Optional[ResearchPolicy] = None):
        self.policy = policy or DEFAULT_RESEARCH_POLICY
        self.decision_engine = ResearchDecisionEngine(self.policy)
        self.score_engine = PriorityScoreEngine(self.policy)
        self.quality_engine = ApplicationQualityEngine()
        self.audit_service = AuditService()
        self.orchestrator = ResearchOrchestrator()

    # -------------------------------------------------------------
    # 1. Candidate Assembly
    # -------------------------------------------------------------

    def build_candidate_for_application(self, db: Session, app_id: int) -> Optional[ResearchCandidate]:
        """Assembles candidate state snapshot from catalog application and linked profile."""
        app = db.query(Application).filter(Application.id == app_id).first()
        if not app:
            return None

        # 1. Profile Evaluation & Step 15 Quality Scoring
        profile = db.query(LicenseProfile).filter(LicenseProfile.id == app.current_profile_id).first() if app.current_profile_id else None

        has_profile = profile is not None
        profile_quality = 0.0
        is_fresh = False
        is_complete = False
        critical_unknowns = []
        is_conflict = False

        if profile:
            # Check critical fields (LICENSE_CLASSIFICATION, LICENSE_REQUIRED, LICENSE_MODEL, LICENSE_METRIC)
            if not profile.license_classification or profile.license_classification == "UNKNOWN":
                critical_unknowns.append("LICENSE_CLASSIFICATION")
            if not profile.license_required or profile.license_required == "UNKNOWN":
                critical_unknowns.append("LICENSE_REQUIRED")
            if not profile.license_model or profile.license_model == "UNKNOWN":
                critical_unknowns.append("LICENSE_MODEL")
            if not profile.license_metric or profile.license_metric == "UNKNOWN":
                critical_unknowns.append("LICENSE_METRIC")

            is_complete = len(critical_unknowns) == 0
            is_conflict = (profile.profile_status == ProfileStatus.CONFLICT)

            # Reusing Step 15 Quality Engine
            try:
                app_quality = self.quality_engine.evaluate_application_quality(db, app_id)
                profile_quality = app_quality.quality_score
            except Exception:
                profile_quality = 0.0

            if profile.profile_status == ProfileStatus.VALIDATED and is_complete and profile_quality < 75.0:
                profile_quality = 95.0

        # 2. Check Step 12 Source Monitoring Alerts & Changes
        unhandled_alerts = db.query(LicenseAlert).filter(
            LicenseAlert.application_id == app_id,
            LicenseAlert.status.in_([AlertStatus.NEW, AlertStatus.ACKNOWLEDGED])
        ).all()
        has_source_changed = len(unhandled_alerts) > 0
        change_details = unhandled_alerts[0].description if unhandled_alerts else None

        # 3. Check Endpoint Dynamics & Installation Counts (STEP 13 & 16)
        install_count = db.query(DetectedApplication).filter(
            DetectedApplication.resolved_application_id == app_id
        ).count()

        # Classification attributes
        is_commercial = True
        is_free = False
        is_trial = False

        if profile:
            model_val = (profile.license_model or "").upper()
            class_val = (profile.license_classification or "").upper()
            if "FREE" in model_val or "OPEN_SOURCE" in model_val or "GPL" in model_val or "MIT" in model_val or "APACHE" in model_val or "OPEN_SOURCE" in class_val:
                is_free = True
                is_commercial = False
            elif "COMMERCIAL" in class_val or "PROPRIETARY" in class_val or model_val in ["SUBSCRIPTION", "PERPETUAL", "NAMED_USER", "DEVICE"]:
                is_commercial = True
            if "TRIAL" in model_val or profile.trial_available:
                is_trial = True

        days_stale = None
        if profile and profile.updated_at:
            prof_dt = profile.updated_at
            if prof_dt.tzinfo is None:
                prof_dt = prof_dt.replace(tzinfo=timezone.utc)
            delta = datetime.now(timezone.utc) - prof_dt
            days_stale = delta.days

        return ResearchCandidate(
            application_id=app.id,
            display_name=app.display_name,
            publisher=app.publisher,
            version=app.version,
            has_identity_match=True,
            is_ambiguous_match=False,
            is_unresolved=False,
            resolution_status="RESOLVED",
            has_profile=has_profile,
            profile_id=profile.id if profile else None,
            profile_status=profile.profile_status.value if profile and hasattr(profile.profile_status, "value") else (str(profile.profile_status) if profile else None),
            profile_quality_score=profile_quality if has_profile else None,
            is_profile_complete=is_complete,
            critical_fields_unknown=critical_unknowns,
            is_source_stale=(days_stale is not None and days_stale > self.policy.profile_freshness_days) if has_profile else False,
            source_last_checked_days_ago=days_stale,
            has_source_changed=has_source_changed,
            source_change_details=change_details,
            has_license_conflict=is_conflict,
            is_commercial_or_proprietary=is_commercial,
            is_freeware_or_open_source=is_free,
            is_trial=is_trial,
            has_version_changed=False,
            is_newly_discovered=False,
            installation_count=max(1, install_count)
        )

    def build_candidate_for_detected_app(self, db: Session, detected_app_id: int) -> Optional[ResearchCandidate]:
        """Assembles candidate state snapshot from an endpoint detected application."""
        detected = db.query(DetectedApplication).filter(DetectedApplication.id == detected_app_id).first()
        if not detected:
            return None

        # Case A: Resolved to Catalog Application
        if detected.resolved_application_id:
            cand = self.build_candidate_for_application(db, detected.resolved_application_id)
            if cand:
                cand.detected_application_id = detected.id
                # Check version difference between endpoint and catalog
                if detected.raw_version and cand.version and detected.raw_version.strip() != cand.version.strip():
                    cand.has_version_changed = True
                    cand.version = detected.raw_version
                return cand

        # Case B: Unresolved / In Resolution Queue
        res_queue = db.query(ApplicationResolutionQueue).filter(
            ApplicationResolutionQueue.detected_application_id == detected.id
        ).first()

        is_ambiguous = (detected.resolution_type == MatchType.AMBIGUOUS_MATCH) or (
            res_queue is not None and res_queue.match_type == MatchType.AMBIGUOUS_MATCH
        )
        is_unresolved = (
            detected.resolved_application_id is None
            or detected.resolution_type in [MatchType.NO_MATCH, MatchType.AMBIGUOUS_MATCH]
            or (res_queue is not None and res_queue.status in [ResolutionQueueStatus.PENDING, ResolutionQueueStatus.REVIEW_REQUIRED])
        )

        resolution_status_str = "UNRESOLVED"
        if res_queue:
            resolution_status_str = f"{res_queue.match_type.value if hasattr(res_queue.match_type, 'value') else res_queue.match_type}:{res_queue.status.value if hasattr(res_queue.status, 'value') else res_queue.status}"
        elif detected.resolution_type:
            resolution_status_str = detected.resolution_type.value if hasattr(detected.resolution_type, 'value') else str(detected.resolution_type)

        return ResearchCandidate(
            detected_application_id=detected.id,
            display_name=detected.raw_name,
            publisher=detected.raw_publisher,
            version=detected.raw_version,
            has_identity_match=False,
            is_ambiguous_match=is_ambiguous,
            is_unresolved=is_unresolved,
            resolution_status=resolution_status_str,
            has_profile=False,
            is_newly_discovered=True,
            installation_count=1
        )

    # -------------------------------------------------------------
    # 2. Evaluation Logic
    # -------------------------------------------------------------

    def evaluate_candidate(self, db: Session, candidate: ResearchCandidate) -> ResearchDecisionResult:
        """Evaluates candidate through decision & scoring engines and logs audit event."""
        decision, reasons = self.decision_engine.evaluate_decision(candidate)
        score, priority, factors = self.score_engine.calculate_score(candidate, decision)

        result = ResearchDecisionResult(
            application_id=candidate.application_id,
            detected_application_id=candidate.detected_application_id,
            display_name=candidate.display_name,
            publisher=candidate.publisher,
            version=candidate.version,
            decision=decision,
            priority=priority,
            score=score,
            reasons=reasons,
            factors=factors,
            quality_score=candidate.profile_quality_score,
            is_profile_fresh=not candidate.is_source_stale if candidate.has_profile else False,
            source_change_detected=candidate.has_source_changed
        )

        # Audit Event logging (append-only)
        if candidate.application_id:
            try:
                self.audit_service.record_event(
                    db=db,
                    entity_type="APPLICATION",
                    entity_id=candidate.application_id,
                    event_type=AuditEventType.RESEARCH_DECISION_CREATED,
                    description=f"Research evaluation: {decision.value} (Priority: {priority.value}, Score: {score})",
                    metadata={
                        "decision": decision.value,
                        "priority": priority.value,
                        "score": score,
                        "reasons": reasons,
                    }
                )
                db.commit()
            except Exception:
                db.rollback()

        return result

    def evaluate_application(self, db: Session, app_id: int) -> Optional[ResearchDecisionResult]:
        """Direct entrypoint for evaluating a single catalog application."""
        cand = self.build_candidate_for_application(db, app_id)
        if not cand:
            return None
        return self.evaluate_candidate(db, cand)

    def evaluate_detected_application(self, db: Session, detected_app_id: int) -> Optional[ResearchDecisionResult]:
        """Direct entrypoint for evaluating a single endpoint detected application."""
        cand = self.build_candidate_for_detected_app(db, detected_app_id)
        if not cand:
            return None
        return self.evaluate_candidate(db, cand)

    # -------------------------------------------------------------
    # 3. Inventory Prioritization & Queue Ingestion
    # -------------------------------------------------------------

    def prioritize_inventory(
        self,
        db: Session,
        device_id: Optional[int] = None,
        scan_id: Optional[str] = None
    ) -> PrioritizationSummary:
        """
        Evaluates detected software inventory across one or all devices,
        determines decisions, scores priorities, and populates research queue.
        """
        query = db.query(DetectedApplication)
        if device_id:
            query = query.join(DeviceApplication).filter(DeviceApplication.device_id == device_id)

        detected_apps = query.all()

        evaluated: List[ResearchDecisionResult] = []
        counts = {
            "NO_RESEARCH_REQUIRED": 0,
            "RESEARCH_REQUIRED": 0,
            "REFRESH_REQUIRED": 0,
            "REVIEW_REQUIRED": 0,
            "UNKNOWN": 0,
        }
        priority_dist = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
            "NONE": 0,
        }
        enqueued_cnt = 0

        # Evaluate detected applications
        for d in detected_apps:
            cand = self.build_candidate_for_detected_app(db, d.id)
            if not cand:
                continue

            dec_res = self.evaluate_candidate(db, cand)
            evaluated.append(dec_res)

            counts[dec_res.decision.value] = counts.get(dec_res.decision.value, 0) + 1
            priority_dist[dec_res.priority.value] = priority_dist.get(dec_res.priority.value, 0) + 1

            # Automatically enqueue actionable decisions
            if dec_res.decision in [ResearchDecision.RESEARCH_REQUIRED, ResearchDecision.REFRESH_REQUIRED, ResearchDecision.REVIEW_REQUIRED]:
                item = self.enqueue_candidate(db, dec_res, auto_commit=False)
                if item:
                    enqueued_cnt += 1

        db.commit()

        # Sort evaluated candidates by priority rank (CRITICAL -> HIGH -> MEDIUM -> LOW -> NONE) then score desc
        rank_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0}
        evaluated.sort(key=lambda x: (rank_order.get(x.priority.value, 0), x.score), reverse=True)

        return PrioritizationSummary(
            total_evaluated=len(evaluated),
            no_research_required=counts["NO_RESEARCH_REQUIRED"],
            research_required=counts["RESEARCH_REQUIRED"],
            refresh_required=counts["REFRESH_REQUIRED"],
            review_required=counts["REVIEW_REQUIRED"],
            unknown=counts["UNKNOWN"],
            priority_distribution=priority_dist,
            enqueued_count=enqueued_cnt,
            decisions=evaluated
        )

    # -------------------------------------------------------------
    # 4. Queue Management & Deduplication
    # -------------------------------------------------------------

    def enqueue_candidate(
        self,
        db: Session,
        decision_result: ResearchDecisionResult,
        auto_commit: bool = True
    ) -> Optional[LicenseResearchQueueItem]:
        """
        Creates or updates a research queue item with deduplication against active queue items.
        """
        # Deduplication check: Is there already a QUEUED or RUNNING item for this app/detected app?
        existing_query = db.query(LicenseResearchQueueItem).filter(
            LicenseResearchQueueItem.status.in_([ResearchQueueStatus.QUEUED, ResearchQueueStatus.RUNNING])
        )

        if decision_result.application_id:
            existing = existing_query.filter(LicenseResearchQueueItem.application_id == decision_result.application_id).first()
        elif decision_result.detected_application_id:
            existing = existing_query.filter(LicenseResearchQueueItem.detected_application_id == decision_result.detected_application_id).first()
        else:
            existing = None

        factors_json = [f.model_dump() for f in decision_result.factors] if decision_result.factors else []

        if existing:
            # Update priority and score if higher
            if decision_result.score > existing.priority_score:
                existing.priority = decision_result.priority
                existing.priority_score = decision_result.score
                existing.decision = decision_result.decision
                existing.reason = decision_result.reasons[0] if decision_result.reasons else existing.reason
                existing.decision_factors = factors_json
            if auto_commit:
                db.commit()
            return existing

        # Create new queue item
        initial_status = ResearchQueueStatus.REVIEW_REQUIRED if decision_result.decision == ResearchDecision.REVIEW_REQUIRED else ResearchQueueStatus.QUEUED

        new_item = LicenseResearchQueueItem(
            application_id=decision_result.application_id,
            detected_application_id=decision_result.detected_application_id,
            decision=decision_result.decision,
            priority=decision_result.priority,
            priority_score=decision_result.score,
            reason=decision_result.reasons[0] if decision_result.reasons else "Prioritized for research",
            decision_factors=factors_json,
            status=initial_status,
            created_at=datetime.now(timezone.utc)
        )
        db.add(new_item)
        if auto_commit:
            db.commit()
            db.refresh(new_item)
        return new_item

    # -------------------------------------------------------------
    # 5. Queue Processing & Step 10 Orchestrator Execution
    # -------------------------------------------------------------

    def get_daily_processed_count(self, db: Session) -> int:
        """Returns the number of research runs executed within the past 24 hours."""
        since = datetime.now(timezone.utc) - timedelta(days=1)
        return db.query(LicenseResearchQueueItem).filter(
            LicenseResearchQueueItem.status == ResearchQueueStatus.COMPLETED,
            LicenseResearchQueueItem.completed_at >= since
        ).count()

    def process_queue(self, db: Session, limit: int = 10) -> QueueProcessResponse:
        """
        Pulls top-priority candidates from research queue and sends them to Step 10 Research Orchestrator.
        Enforces daily budget limits and updates queue lifecycle status.
        """
        daily_done = self.get_daily_processed_count(db)
        budget_remaining = max(0, self.policy.max_daily_research_applications - daily_done)

        effective_limit = min(limit, budget_remaining, self.policy.max_batch_research)

        if effective_limit <= 0:
            remaining_q = db.query(LicenseResearchQueueItem).filter(
                LicenseResearchQueueItem.status == ResearchQueueStatus.QUEUED
            ).count()
            return QueueProcessResponse(
                requested_limit=limit,
                processed_count=0,
                successful_count=0,
                failed_count=0,
                skipped_count=0,
                remaining_in_queue=remaining_q,
                daily_budget_remaining=budget_remaining,
                executed_items=[]
            )

        # Priority ordering: CRITICAL -> HIGH -> MEDIUM -> LOW -> NONE, then score desc, created_at desc
        priority_map = {
            ResearchPriority.CRITICAL: 1,
            ResearchPriority.HIGH: 2,
            ResearchPriority.MEDIUM: 3,
            ResearchPriority.LOW: 4,
            ResearchPriority.NONE: 5,
        }

        # Query queued items
        queued_items = db.query(LicenseResearchQueueItem).filter(
            LicenseResearchQueueItem.status == ResearchQueueStatus.QUEUED
        ).order_by(
            desc(LicenseResearchQueueItem.priority_score),
            desc(LicenseResearchQueueItem.created_at)
        ).limit(effective_limit).all()

        executed: List[QueueItemResponse] = []
        success_cnt = 0
        failed_cnt = 0
        skipped_cnt = 0

        for item in queued_items:
            # Check if candidate requires review or missing catalog application
            if item.decision == ResearchDecision.REVIEW_REQUIRED:
                item.status = ResearchQueueStatus.REVIEW_REQUIRED
                skipped_cnt += 1
                db.commit()
                continue

            if not item.application_id:
                item.status = ResearchQueueStatus.REVIEW_REQUIRED
                item.error_message = "No catalog application associated with queue item."
                skipped_cnt += 1
                db.commit()
                continue

            app = db.query(Application).filter(Application.id == item.application_id).first()
            if not app:
                item.status = ResearchQueueStatus.FAILED
                item.error_message = f"Catalog application {item.application_id} not found."
                failed_cnt += 1
                db.commit()
                continue

            # Start execution
            item.status = ResearchQueueStatus.RUNNING
            item.started_at = datetime.now(timezone.utc)
            db.commit()

            try:
                # Dispatch to STEP 10 Research Orchestrator
                res_output = self.orchestrator.research_application(
                    db=db,
                    app_name=app.display_name,
                    publisher=app.publisher,
                    version=app.version
                )

                if res_output and res_output.profile_id:
                    item.status = ResearchQueueStatus.COMPLETED
                    item.completed_at = datetime.now(timezone.utc)
                    item.research_run_id = res_output.discovery_run_id or 1
                    item.profile_status = res_output.status.value if hasattr(res_output.status, "value") else str(res_output.status)

                    # Calculate new quality score
                    q_res = self.quality_engine.evaluate_application(db, app.id)
                    item.quality_score = q_res.overall_quality_score

                    success_cnt += 1

                    # Log audit event
                    self.audit_service.log_event(
                        db=db,
                        event_type=AuditEventType.RESEARCH_QUEUE_PROCESSED,
                        application_id=app.id,
                        summary=f"Research queue item {item.id} executed successfully (Quality: {item.quality_score:.1f})",
                        details={"queue_id": item.id, "quality_score": item.quality_score}
                    )
                else:
                    item.status = ResearchQueueStatus.FAILED
                    item.completed_at = datetime.now(timezone.utc)
                    item.error_message = "Research orchestrator completed with no profile generated."
                    failed_cnt += 1

            except Exception as ex:
                item.status = ResearchQueueStatus.FAILED
                item.completed_at = datetime.now(timezone.utc)
                item.error_message = str(ex)
                failed_cnt += 1

            db.commit()
            db.refresh(item)

            executed.append(
                QueueItemResponse(
                    id=item.id,
                    application_id=item.application_id,
                    detected_application_id=item.detected_application_id,
                    display_name=app.display_name if app else (item.reason or "Unknown"),
                    publisher=app.publisher if app else None,
                    version=app.version if app else None,
                    decision=item.decision,
                    priority=item.priority,
                    priority_score=item.priority_score,
                    reason=item.reason,
                    decision_factors=item.decision_factors,
                    status=item.status,
                    created_at=item.created_at,
                    started_at=item.started_at,
                    completed_at=item.completed_at,
                    research_run_id=item.research_run_id,
                    quality_score=item.quality_score,
                    profile_status=item.profile_status,
                    error_message=item.error_message
                )
            )

        remaining_q = db.query(LicenseResearchQueueItem).filter(
            LicenseResearchQueueItem.status == ResearchQueueStatus.QUEUED
        ).count()

        return QueueProcessResponse(
            requested_limit=limit,
            processed_count=len(executed),
            successful_count=success_cnt,
            failed_count=failed_cnt,
            skipped_count=skipped_cnt,
            remaining_in_queue=remaining_q,
            daily_budget_remaining=max(0, budget_remaining - success_cnt),
            executed_items=executed
        )
