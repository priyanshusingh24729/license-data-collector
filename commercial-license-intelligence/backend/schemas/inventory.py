"""
Pydantic schemas for inventory ingestion and resolution.
Re-exports from backend.inventory.detection.detection_result for consistent schema module access.
"""

from backend.inventory.detection.detection_result import (
    DeviceIngestPayload,
    ApplicationIngestItem,
    InventoryIngestRequest,
    IngestedApplicationSummary,
    InventoryIngestResponse,
    ResolutionCandidateDetail,
    ResolutionQueueItemResponse,
    ManualResolveRequest,
    InventoryCatalogAppSummary,
    DeviceDetailResponse,
)

__all__ = [
    "DeviceIngestPayload",
    "ApplicationIngestItem",
    "InventoryIngestRequest",
    "IngestedApplicationSummary",
    "InventoryIngestResponse",
    "ResolutionCandidateDetail",
    "ResolutionQueueItemResponse",
    "ManualResolveRequest",
    "InventoryCatalogAppSummary",
    "DeviceDetailResponse",
]
