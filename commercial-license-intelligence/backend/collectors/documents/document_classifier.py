"""
Document Nature & Classification Engine.
Determines document type (e.g. Product Terms, EULA, Licensing Guide)
based on title, metadata, URL cues, and structural text headers.
Answers: 'What kind of document is this?' (NOT 'What license does it have?').
"""

import re
from typing import Optional
from backend.models.enums import DocumentClassification, SourceType


class DocumentClassifier:
    """
    Classifies the document archetype using deterministic heuristics.
    """

    def classify(
        self,
        url: str,
        title: Optional[str] = None,
        source_type: Optional[SourceType] = None,
        sample_text: Optional[str] = None
    ) -> DocumentClassification:
        """
        Infers document classification from available metadata and content tokens.
        """
        combined = f"{url} {title or ''} {sample_text[:1000] if sample_text else ''}".lower()

        # 1. SourceType direct mapping if specified
        if source_type == SourceType.OFFICIAL_EULA or "eula" in combined:
            return DocumentClassification.EULA

        if "product terms" in combined or "product-terms" in combined or "licenses-terms" in combined:
            return DocumentClassification.PRODUCT_TERMS

        if "licensing brief" in combined or "licensing-brief" in combined:
            return DocumentClassification.LICENSING_BRIEF

        if "licensing guide" in combined or "licensing-guide" in combined or "licensing faq" in combined:
            return DocumentClassification.LICENSING_GUIDE

        if "subscription" in combined and "terms" in combined:
            return DocumentClassification.SUBSCRIPTION_TERMS

        if "deployment" in combined and ("guide" in combined or "licensing" in combined):
            return DocumentClassification.DEPLOYMENT_GUIDE

        if "general terms" in combined or "terms of use" in combined or "terms of service" in combined or "license terms" in combined:
            return DocumentClassification.LICENSE_TERMS

        if "system requirements" in combined or "technical documentation" in combined or "admin guide" in combined:
            return DocumentClassification.PRODUCT_DOCUMENTATION

        if source_type in [SourceType.OFFICIAL_PDF, SourceType.OFFICIAL_DOCUMENT, SourceType.OFFICIAL_WEB]:
            return DocumentClassification.OTHER_OFFICIAL_DOCUMENT

        return DocumentClassification.UNKNOWN
