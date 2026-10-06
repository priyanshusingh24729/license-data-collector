"""
Automatic Official License Source Discovery Engine.
Orchestrates query generation, multi-query external search, domain validation,
signal ranking, deduplication, run tracking, and registry synchronization.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Set
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.source import LicenseSource
from backend.models.discovery import DiscoveryRun
from backend.models.enums import (
    SourceType,
    AuthorityLevel,
    ScopeType,
    CollectionMethod,
    SourceStatus,
    AccessType,
    SourceOrigin,
    DiscoveryStatus,
    DiscoveryRunStatus,
    DomainValidationStatus,
    RelevanceTier,
)
from backend.schemas.discovery import (
    DiscoveryTargetRequest,
    DiscoveredSourceCandidate,
    DiscoveryExecutionResponse,
)
from backend.sources.discovery.query_builder import QueryBuilder
from backend.sources.discovery.domain_validator import DomainValidator
from backend.sources.discovery.search_provider import SearchProvider, get_search_provider
from backend.sources.discovery.source_ranker import SourceRanker
from backend.services.source_registry_service import normalize_url, extract_base_domain

logger = logging.getLogger(__name__)


class SourceDiscoveryEngine:
    """
    Coordinates end-to-end official source discovery workflows.
    """

    def __init__(
        self,
        query_builder: Optional[QueryBuilder] = None,
        domain_validator: Optional[DomainValidator] = None,
        search_provider: Optional[SearchProvider] = None,
        source_ranker: Optional[SourceRanker] = None,
    ):
        self.query_builder = query_builder or QueryBuilder()
        self.domain_validator = domain_validator or DomainValidator()
        self.search_provider = search_provider or get_search_provider()
        self.source_ranker = source_ranker or SourceRanker()

    def run_discovery(
        self,
        db: Session,
        target: DiscoveryTargetRequest
    ) -> DiscoveryExecutionResponse:
        """
        Executes automated official source discovery for a software target.
        """
        vendor = target.vendor.strip()
        product = target.product.strip() if target.product else None
        edition = target.edition.strip() if target.edition else None
        version = target.version.strip() if target.version else None
        os_env = target.os.strip() if target.os else None

        # 1. Initialize and persist DiscoveryRun
        discovery_run = DiscoveryRun(
            vendor_name=vendor,
            product_name=product,
            edition=edition,
            version=version,
            os=os_env,
            status=DiscoveryRunStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        db.add(discovery_run)
        db.commit()
        db.refresh(discovery_run)

        # 2. Check Search Provider availability
        if not self.search_provider.is_available():
            logger.warning(f"No operational search provider available for discovery run {discovery_run.id}")
            discovery_run.status = DiscoveryRunStatus.NO_SEARCH_PROVIDER
            discovery_run.completed_at = datetime.now(timezone.utc)
            discovery_run.details = "No external search provider or developer mock fallback configured."
            db.commit()
            return DiscoveryExecutionResponse(
                run_id=discovery_run.id,
                status=DiscoveryRunStatus.NO_SEARCH_PROVIDER,
                vendor=vendor,
                product=product,
                edition=edition,
                version=version,
                os=os_env,
                queries_executed=0,
                sources_found=0,
                sources_accepted=0,
                sources_rejected=0,
                candidates=[],
                message="No search provider configured. Set SEARCH_PROVIDER or enable dev fallback in .env."
            )

        # 3. Resolve expected official domain
        known_domain = self.domain_validator.get_known_official_domain(vendor)

        # 4. Generate targeted discovery queries
        queries = self.query_builder.build_queries(
            vendor=vendor,
            product=product,
            edition=edition,
            version=version,
            os=os_env,
            official_domain=known_domain,
            max_queries=target.max_queries,
        )

        seen_normalized_urls: Set[str] = set()
        raw_candidates: List[Dict[str, Any]] = []
        queries_executed = 0

        # 4B. Free Direct Discovery: llms.txt and sitemap exploration
        if known_domain:
            from backend.config.settings import get_settings
            app_settings = get_settings()

            if getattr(app_settings, "ENABLE_LLMS_TXT_DISCOVERY", True):
                try:
                    from backend.collectors.web.llms_txt_collector import LlmsTxtCollector
                    llms_res = LlmsTxtCollector().discover(f"https://{known_domain}")
                    if llms_res and llms_res.is_available:
                        for l_url, l_title in llms_res.extracted_links:
                            norm_url = normalize_url(l_url)
                            if norm_url and norm_url not in seen_normalized_urls:
                                seen_normalized_urls.add(norm_url)
                                raw_candidates.append({
                                    "url": l_url,
                                    "normalized_url": norm_url,
                                    "title": l_title or f"{vendor} llms.txt",
                                    "snippet": f"Discovered from {known_domain}/llms.txt",
                                    "engine": "llms_txt",
                                })
                except Exception as e:
                    logger.debug(f"llms.txt discovery notice for {known_domain}: {e}")

            if getattr(app_settings, "ENABLE_SITEMAP_DISCOVERY", True):
                try:
                    from backend.collectors.web.sitemap_collector import SitemapCollector
                    sitemap_urls = SitemapCollector().discover_licensing_sitemap_urls(f"https://{known_domain}")
                    for s_url in sitemap_urls:
                        norm_url = normalize_url(s_url)
                        if norm_url and norm_url not in seen_normalized_urls:
                            seen_normalized_urls.add(norm_url)
                            raw_candidates.append({
                                "url": s_url,
                                "normalized_url": norm_url,
                                "title": f"{vendor} Licensing Page (Sitemap)",
                                "snippet": f"Discovered from sitemap at {known_domain}",
                                "engine": "sitemap",
                            })
                except Exception as e:
                    logger.debug(f"Sitemap discovery notice for {known_domain}: {e}")

        # 5. Execute search queries across provider
        for query in queries:
            try:
                results = self.search_provider.search(query, num_results=5)
                queries_executed += 1
                for r in results:
                    norm_url = normalize_url(r.url)
                    if not norm_url or norm_url in seen_normalized_urls:
                        continue
                    seen_normalized_urls.add(norm_url)
                    raw_candidates.append({
                        "url": r.url,
                        "normalized_url": norm_url,
                        "title": r.title,
                        "snippet": r.snippet,
                        "engine": r.engine,
                    })
            except Exception as search_err:
                logger.warning(f"Query execution failed for '{query}': {search_err}")

        # 6. Validate domains and rank candidate sources
        accepted_candidates: List[DiscoveredSourceCandidate] = []
        rejected_count = 0

        for item in raw_candidates:
            domain_status = self.domain_validator.validate_domain(
                url=item["normalized_url"],
                vendor=vendor,
                expected_official_domain=known_domain
            )

            # Extract base domain
            base_domain = extract_base_domain(item["normalized_url"])

            (
                score,
                tier,
                authority_level,
                source_type,
                reasons,
                matched_v,
                matched_p,
                matched_e,
                matched_ver
            ) = self.source_ranker.rank_candidate(
                url=item["normalized_url"],
                title=item["title"],
                snippet=item["snippet"],
                vendor=vendor,
                product=product,
                edition=edition,
                version=version,
                domain_status=domain_status
            )

            # Infer scope
            scope_type, scope_identifier = self.source_ranker.infer_scope(
                vendor=vendor,
                product=product,
                edition=edition,
                version=version,
                url=item["normalized_url"],
                title=item["title"]
            )

            # Classify collection method
            col_method = CollectionMethod.PDF if source_type == SourceType.OFFICIAL_PDF else CollectionMethod.WEB

            # Reject completely non-official or irrelevant links
            if domain_status == DomainValidationStatus.NOT_OFFICIAL and score < 40:
                rejected_count += 1
                continue

            # Check if source already exists in registry
            existing = db.query(LicenseSource).filter(
                func.lower(LicenseSource.vendor_name) == vendor.lower(),
                LicenseSource.normalized_url == item["normalized_url"],
            ).first()

            is_existing = existing is not None
            existing_id = existing.id if existing else None

            # Create Candidate Data Structure
            candidate = DiscoveredSourceCandidate(
                source_url=item["url"],
                normalized_url=item["normalized_url"],
                source_title=item["title"] or f"{vendor} Licensing Source",
                source_type=source_type,
                authority_level=authority_level,
                official_domain=known_domain or base_domain,
                base_domain=base_domain,
                domain_status=domain_status,
                relevance_score=score,
                relevance_tier=tier,
                ranking_reasons=reasons,
                discovery_method="SEARCH",
                matched_vendor=matched_v,
                matched_product=matched_p,
                matched_edition=matched_e,
                matched_version=matched_ver,
                scope_type=scope_type,
                scope_identifier=scope_identifier,
                collection_method=col_method,
                access_type=AccessType.PUBLIC,
                discovery_timestamp=datetime.now(timezone.utc),
                is_existing=is_existing,
                existing_source_id=existing_id
            )

            # 7. Persist to license_sources if requested
            if target.store_discovered:
                if is_existing:
                    # Update discovery metadata without overwriting manually verified source attributes
                    if existing.source_origin != SourceOrigin.MANUAL:
                        existing.relevance_score = score
                        existing.updated_at = datetime.now(timezone.utc)
                    existing.last_checked_at = datetime.now(timezone.utc)
                    existing.discovered_at = existing.discovered_at or datetime.now(timezone.utc)
                    db.commit()
                else:
                    # Insert newly discovered candidate
                    new_src = LicenseSource(
                        vendor_name=vendor,
                        product_name=product,
                        scope_type=scope_type,
                        scope_identifier=scope_identifier,
                        source_name=candidate.source_title,
                        source_type=source_type,
                        authority_level=authority_level,
                        official_domain=candidate.official_domain,
                        base_domain=base_domain,
                        source_url=candidate.source_url,
                        normalized_url=candidate.normalized_url,
                        description=f"Automatically discovered via query targeting {vendor} {product or ''}".strip(),
                        is_active=True,
                        is_public=True,
                        status=SourceStatus.ACTIVE,
                        access_type=AccessType.PUBLIC,
                        collection_method=col_method,
                        priority=1 if tier == RelevanceTier.VERY_HIGH else (2 if tier == RelevanceTier.HIGH else 3),
                        source_origin=SourceOrigin.AUTOMATIC,
                        discovery_status=DiscoveryStatus.DISCOVERED,
                        discovery_method="SEARCH",
                        relevance_score=score,
                        discovered_at=datetime.now(timezone.utc),
                    )
                    db.add(new_src)
                    db.commit()
                    db.refresh(new_src)
                    candidate.is_existing = True
                    candidate.existing_source_id = new_src.id

            accepted_candidates.append(candidate)

        # Sort candidates by relevance score descending
        accepted_candidates.sort(key=lambda c: c.relevance_score, reverse=True)

        # 8. Determine final run status
        if not raw_candidates:
            final_status = DiscoveryRunStatus.NO_OFFICIAL_SOURCE_FOUND
            msg = "No search candidates were returned by the search provider."
        elif not accepted_candidates:
            final_status = DiscoveryRunStatus.NO_OFFICIAL_SOURCE_FOUND
            msg = "Search candidates were found but none passed official domain validation."
        elif any(c.domain_status != DomainValidationStatus.OFFICIAL for c in accepted_candidates):
            final_status = DiscoveryRunStatus.REVIEW_REQUIRED
            msg = f"Discovered {len(accepted_candidates)} sources (some require review)."
        else:
            final_status = DiscoveryRunStatus.COMPLETED
            msg = f"Successfully discovered and registered {len(accepted_candidates)} authoritative sources."

        # 9. Update discovery run record
        discovery_run.status = final_status
        discovery_run.queries_executed = queries_executed
        discovery_run.sources_found = len(raw_candidates)
        discovery_run.sources_accepted = len(accepted_candidates)
        discovery_run.sources_rejected = rejected_count
        discovery_run.completed_at = datetime.now(timezone.utc)
        discovery_run.details = msg
        db.commit()

        return DiscoveryExecutionResponse(
            run_id=discovery_run.id,
            status=final_status,
            vendor=vendor,
            product=product,
            edition=edition,
            version=version,
            os=os_env,
            queries_executed=queries_executed,
            sources_found=len(raw_candidates),
            sources_accepted=len(accepted_candidates),
            sources_rejected=rejected_count,
            candidates=accepted_candidates,
            message=msg
        )
