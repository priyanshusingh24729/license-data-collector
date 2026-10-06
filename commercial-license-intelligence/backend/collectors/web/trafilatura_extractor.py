"""
Trafilatura Content Extractor.
Extracts pristine, noise-free Markdown with table formatting intact,
stripping navigation bars, cookie consent banners, ads, and footers.
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TrafilaturaExtractionResult:
    """Container for clean content extracted by Trafilatura."""
    title: Optional[str]
    markdown_content: str
    clean_text: str
    tables_found: int = 0
    raw_tables_markdown: List[str] = field(default_factory=list)
    char_count: int = 0
    is_success: bool = False


class TrafilaturaExtractor:
    """
    Wrapper around Trafilatura for extracting structured, boilerplate-free Markdown.
    """

    @classmethod
    def extract(cls, html: str, base_url: Optional[str] = None) -> TrafilaturaExtractionResult:
        """
        Extracts clean Markdown and tables from raw or rendered HTML.
        """
        if not html or not html.strip():
            return TrafilaturaExtractionResult(
                title=None,
                markdown_content="",
                clean_text="",
                is_success=False
            )

        try:
            import trafilatura
        except ImportError:
            logger.warning("Trafilatura is not installed. Falling back to default parser.")
            return TrafilaturaExtractionResult(
                title=None,
                markdown_content="",
                clean_text="",
                is_success=False
            )

        try:
            # 1. Extract clean Markdown with tables, links, and formatting preserved
            extracted_md = trafilatura.extract(
                html,
                url=base_url,
                output_format="markdown",
                include_tables=True,
                include_links=True,
                include_formatting=True,
                include_comments=False,
                favor_recall=True,
                deduplicate=True,
            )

            # 2. Extract plain text as baseline
            clean_text = trafilatura.extract(
                html,
                url=base_url,
                output_format="txt",
                include_tables=True,
                include_comments=False,
            ) or ""

            # 3. Extract title/metadata if available
            metadata = trafilatura.extract_metadata(html, default_url=base_url)
            title = metadata.title if metadata and metadata.title else None

            if not extracted_md or len(extracted_md.strip()) < 30:
                return TrafilaturaExtractionResult(
                    title=title,
                    markdown_content=clean_text,
                    clean_text=clean_text,
                    char_count=len(clean_text),
                    is_success=bool(len(clean_text) >= 30),
                )

            # Detect markdown tables in output
            table_count = extracted_md.count("|---")
            tables_md: List[str] = []
            if table_count > 0:
                lines = extracted_md.split("\n")
                current_table: List[str] = []
                for line in lines:
                    if line.strip().startswith("|") and "|" in line.strip()[1:]:
                        current_table.append(line.strip())
                    else:
                        if current_table and any("|---" in l for l in current_table):
                            tables_md.append("\n".join(current_table))
                        current_table = []
                if current_table and any("|---" in l for l in current_table):
                    tables_md.append("\n".join(current_table))

            return TrafilaturaExtractionResult(
                title=title,
                markdown_content=extracted_md.strip(),
                clean_text=clean_text.strip() if clean_text else extracted_md.strip(),
                tables_found=len(tables_md),
                raw_tables_markdown=tables_md,
                char_count=len(extracted_md),
                is_success=True,
            )

        except Exception as exc:
            logger.warning(f"[TrafilaturaExtractor] Extraction failed: {exc}")
            return TrafilaturaExtractionResult(
                title=None,
                markdown_content="",
                clean_text="",
                is_success=False
            )
