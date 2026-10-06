"""Database initialization and schema migration utilities."""

import logging
from backend.database.connection import engine, Base
# Import all models to ensure metadata registration
import backend.models
from backend.models.source import LicenseSource
from backend.models.discovery import DiscoveryRun
from backend.models.collection import CollectedDocument, DocumentPage
from backend.models.api_document import ApiDocument
from backend.models.fact import LicenseFact, LicenseEvidence, ExtractionRun
from backend.models.validation import FactValidationRun
from backend.models.profile import LicenseProfile, LicenseProfileFact, ProfileVersion
from backend.models.application import Application, ResearchBatch, ResearchBatchItem
from backend.models.monitoring import SourceMonitor, MonitoringRun, LicenseFactChange, LicenseAlert
from backend.models.inventory import Device, DetectedApplication, DeviceApplication, ApplicationResolutionQueue
from backend.models.inventory_upload import InventoryUpload, InventoryUploadRow, UploadLicenseResult
from backend.models.entitlement import LicenseEntitlement, LicenseConsumption, LicensePosition, LicensePositionHistory
from backend.models.audit import AuditEvent, QualityIssue
from backend.models.research_queue import LicenseResearchQueueItem
from backend.models.tier4_feedback import PendingCatalogRule, CatalogAuditLog
from backend.models.resolved_product_cache import ResolvedProductCache

logger = logging.getLogger(__name__)


def init_database_tables():
    """Initializes tables and automatically migrates any missing columns."""
    if engine is not None:
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database schema initialized successfully.")

            # Sync columns for existing tables
            from sqlalchemy import inspect, text
            inspector = inspect(engine)
            existing_tables = inspector.get_table_names()

            with engine.connect() as conn:
                for table_name, table in Base.metadata.tables.items():
                    if table_name in existing_tables:
                        existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
                        for col in table.columns:
                            if col.name not in existing_cols:
                                col_type = col.type.compile(engine.dialect)
                                alter_stmt = f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type}"
                                try:
                                    conn.execute(text(alter_stmt))
                                    conn.commit()
                                    logger.info(f"Added missing column '{col.name}' to table '{table_name}'.")
                                except Exception as e:
                                    logger.warning(f"Could not add column '{col.name}' to '{table_name}': {e}")

            return True
        except Exception as exc:
            logger.warning(f"Could not automatically create database tables: {exc}")
            return False
    return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_database_tables()
