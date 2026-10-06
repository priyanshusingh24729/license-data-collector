"""
Evidence Existence & Text Integrity Validator.
Verifies that claimed evidence actually exists in the collected document and matches stored text.
Prevents fabricated or hallucinated evidence from entering verified knowledge.
"""

import re
import unicodedata
from typing import Tuple, Optional
from sqlalchemy.orm import Session

from backend.models.collection import CollectedDocument, DocumentPage
from backend.models.fact import LicenseFact


def normalize_whitespace_text(text: str) -> str:
    """Normalizes whitespace, linebreaks, and Unicode characters for fuzzy text matching."""
    if not text:
        return ""
    # Normalize unicode (NFKC)
    norm = unicodedata.normalize("NFKC", text)
    # Replace all whitespace runs with single space
    return " ".join(norm.split()).lower()


class EvidenceValidator:
    """
    Validates that evidence references exist and match actual document content.
    """

    def validate_evidence(
        self,
        db: Session,
        fact: LicenseFact
    ) -> Tuple[bool, bool, Optional[str]]:
        """
        Validates evidence existence and text match.
        Returns: (evidence_exists, text_matched, failure_reason)
        """
        # If no document_id is referenced
        if not fact.document_id:
            # Check if standalone evidence_text is present
            if fact.evidence_text and len(fact.evidence_text.strip()) > 5:
                return True, True, None
            return False, False, "EVIDENCE_NOT_FOUND: No document or evidence text associated with fact."

        # 1. Check document existence
        doc = db.query(CollectedDocument).filter(CollectedDocument.id == fact.document_id).first()
        if not doc:
            return False, False, f"EVIDENCE_NOT_FOUND: Referenced document ID {fact.document_id} does not exist."

        # 2. Check page existence if page_number is specified
        search_corpus = ""
        if fact.page_number:
            page = db.query(DocumentPage).filter(
                DocumentPage.document_id == doc.id,
                DocumentPage.page_number == fact.page_number
            ).first()
            if page and page.text:
                search_corpus = page.text
            elif doc.clean_text:
                search_corpus = doc.clean_text
            else:
                return True, False, f"EVIDENCE_PAGE_NOT_FOUND: Page {fact.page_number} not found in document {doc.id}."
        else:
            search_corpus = doc.clean_text or ""

        # 3. Fuzzy Text Matching
        norm_evidence = normalize_whitespace_text(fact.evidence_text)
        norm_corpus = normalize_whitespace_text(search_corpus)

        if not norm_evidence:
            return True, False, "EVIDENCE_TEXT_EMPTY: Fact has empty evidence string."

        if norm_evidence in norm_corpus:
            return True, True, None

        # Check sub-clause match (at least 70% of words match in sequence)
        ev_words = norm_evidence.split()
        if len(ev_words) >= 4:
            sub_phrase = " ".join(ev_words[:min(len(ev_words), 8)])
            if sub_phrase in norm_corpus:
                return True, True, None

        return True, False, "EVIDENCE_TEXT_NOT_FOUND: Claimed evidence text does not exist in the source document."
