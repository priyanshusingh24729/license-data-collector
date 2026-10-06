"""
Relevant Content Detection Engine.
Identifies high-intent licensing paragraphs, sections, tables, and page snippets
using deterministic keyword matching and context window harvesting.
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

LICENSING_KEYWORDS = [
    r"\blicens(?:e|ing|ed|es)\b",
    r"\bsubscription\b",
    r"\bperpetual\b",
    r"\bnamed[\s\-]user\b",
    r"\bconcurrent\b",
    r"\bfloating\b",
    r"\bnode[\s\-]locked\b",
    r"\buser[\s\-]based\b",
    r"\bdevice[\s\-]based\b",
    r"\bcore[\s\-]based\b",
    r"\bper[\s\-]core\b",
    r"\bper[\s\-]user\b",
    r"\bper[\s\-]device\b",
    r"\bper[\s\-]seat\b",
    r"\btrial\b",
    r"\bevaluation\b",
    r"\bcommercial\b",
    r"\bnon[\s\-]commercial\b",
    r"\beducational\b",
    r"\bfreeware\b",
    r"\bfree\s+for\s+personal\b",
    r"\bproprietary\b",
    r"\beula\b",
    r"\bterms\s+of\s+(?:use|service|license)\b",
    r"\bentitlement\b",
    r"\bactivation\b",
    r"\bvirtualization\b",
    r"\bsecondary\s+device\b",
    r"\bmultiplexing\b",
    r"\bcal\b",
]

KEYWORD_PATTERN = re.compile("|".join(LICENSING_KEYWORDS), re.IGNORECASE)


@dataclass
class RelevantContextBlock:
    """Harvested context snippet with exact document anchors."""
    text: str
    matched_keywords: List[str]
    page_number: Optional[int] = None
    section_name: Optional[str] = None
    document_id: Optional[int] = None
    source_id: Optional[int] = None
    is_table: bool = False


class RelevantContentDetector:
    """
    Scans document representations and isolates paragraphs/sections with licensing relevance.
    """

    def __init__(self, keyword_pattern: Optional[re.Pattern] = None):
        self.pattern = keyword_pattern or KEYWORD_PATTERN

    def scan_text(
        self,
        full_text: str,
        document_id: Optional[int] = None,
        source_id: Optional[int] = None
    ) -> List[RelevantContextBlock]:
        """Scans consolidated text broken down by paragraphs."""
        if not full_text:
            return []

        blocks: List[RelevantContextBlock] = []
        paragraphs = full_text.split("\n\n")

        current_page = 1
        current_section = "General"

        for p in paragraphs:
            p_strip = p.strip()
            if not p_strip:
                continue

            # Detect page markers (e.g. --- PAGE 2 ---)
            page_match = re.match(r"^---\s*PAGE\s*(\d+)\s*---", p_strip, re.IGNORECASE)
            if page_match:
                current_page = int(page_match.group(1))
                continue

            # Detect section markers (e.g. SECTION [H2]: Licensing)
            sec_match = re.match(r"^SECTION\s*\[\w+\]:\s*(.+)$", p_strip, re.IGNORECASE)
            if sec_match:
                current_section = sec_match.group(1).strip()
                continue

            matches = self.pattern.findall(p_strip)
            if matches:
                blocks.append(RelevantContextBlock(
                    text=p_strip,
                    matched_keywords=list(set(matches)),
                    page_number=current_page,
                    section_name=current_section,
                    document_id=document_id,
                    source_id=source_id,
                    is_table="[TABLE]" in p_strip or "|" in p_strip
                ))

        return blocks

    def scan_pages(
        self,
        pages: List[Any],
        document_id: Optional[int] = None,
        source_id: Optional[int] = None
    ) -> List[RelevantContextBlock]:
        """Scans page objects with exact page boundaries."""
        blocks: List[RelevantContextBlock] = []

        for p in pages:
            page_num = getattr(p, "page_number", 1)
            page_text = getattr(p, "text", "")
            if not page_text:
                continue

            # Check individual paragraphs on page
            for para in page_text.split("\n\n"):
                para_strip = para.strip()
                if not para_strip:
                    continue
                matches = self.pattern.findall(para_strip)
                if matches:
                    blocks.append(RelevantContextBlock(
                        text=para_strip,
                        matched_keywords=list(set(matches)),
                        page_number=page_num,
                        section_name=f"Page {page_num}",
                        document_id=document_id,
                        source_id=source_id,
                        is_table="|" in para_strip
                    ))

        return blocks
