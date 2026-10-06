"""
Structured Document Content Parser.
Extracts title, structured sections, paragraphs, lists, and HTML tables into a
coherent, readable document structure ready for license fact extraction.
"""

import re
import logging
from typing import List, Tuple, Optional, Dict, Any
from bs4 import BeautifulSoup, Tag

from backend.collectors.web.collection_result import DocumentSection, TableData

logger = logging.getLogger(__name__)


class ContentParser:
    """
    Parses cleaned HTML DOM into structured document hierarchy.
    """

    HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def extract_title(self, soup: BeautifulSoup) -> str:
        """Extracts page title from title tag or first h1."""
        if soup.title and soup.title.string:
            title_text = soup.title.string.strip()
            if title_text:
                return title_text

        h1 = soup.find("h1")
        if h1:
            h1_text = h1.get_text(strip=True)
            if h1_text:
                return h1_text

        return "Untitled Document"

    def parse_table(self, table_tag: Tag) -> TableData:
        """Converts an HTML table into structured TableData and Markdown string."""
        caption_el = table_tag.find("caption")
        caption = caption_el.get_text(strip=True) if caption_el else None

        headers: List[str] = []
        rows: List[List[str]] = []

        # Find headers (thead or first tr with th)
        thead = table_tag.find("thead")
        if thead:
            th_cells = thead.find_all(["th", "td"])
            headers = [c.get_text(separator=" ", strip=True) for c in th_cells if c.get_text(strip=True)]
        else:
            first_tr = table_tag.find("tr")
            if first_tr:
                th_cells = first_tr.find_all("th")
                if th_cells:
                    headers = [c.get_text(separator=" ", strip=True) for c in th_cells]

        # Extract data rows
        tbody = table_tag.find("tbody") or table_tag
        for tr in tbody.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            row_values = [c.get_text(separator=" ", strip=True) for c in cells]
            # Avoid duplicating header row if extracted from first tr
            if row_values and (not headers or row_values != headers):
                rows.append(row_values)

        # Build Markdown representation
        md_lines: List[str] = []
        if caption:
            md_lines.append(f"*{caption}*")

        if headers:
            md_lines.append("| " + " | ".join(headers) + " |")
            md_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        elif rows and rows[0]:
            # Synthesize generic headers if none exist
            synth_headers = [f"Col {i+1}" for i in range(len(rows[0]))]
            md_lines.append("| " + " | ".join(synth_headers) + " |")
            md_lines.append("| " + " | ".join(["---"] * len(synth_headers)) + " |")

        for r in rows:
            if headers and len(r) < len(headers):
                r = r + [""] * (len(headers) - len(r))
            md_lines.append("| " + " | ".join(r) + " |")

        md_repr = "\n".join(md_lines)
        return TableData(
            caption=caption,
            headers=headers,
            rows=rows,
            markdown_repr=md_repr
        )

    def parse_document(self, soup: BeautifulSoup) -> Tuple[str, List[DocumentSection], List[TableData], str]:
        """
        Extracts title, structured sections, tables, and formatted clean text.
        
        Returns:
        (title, structured_sections, tables, clean_text)
        """
        title = self.extract_title(soup)

        # Locate root content container (main, article, or body)
        content_root = soup.find("main") or soup.find("article") or soup.body or soup

        sections: List[DocumentSection] = []
        tables: List[TableData] = []

        current_heading_level = "H1"
        current_heading_text = "Introduction / Overview"
        current_paragraphs: List[str] = []
        current_lists: List[List[str]] = []
        current_raw_texts: List[str] = []

        def flush_current_section():
            nonlocal current_heading_level, current_heading_text, current_paragraphs, current_lists, current_raw_texts
            if current_paragraphs or current_lists or current_raw_texts:
                combined_text = "\n\n".join([p for p in current_paragraphs if p])
                sections.append(DocumentSection(
                    heading_level=current_heading_level,
                    heading_text=current_heading_text,
                    paragraphs=current_paragraphs,
                    lists=current_lists,
                    raw_text=combined_text
                ))
            current_paragraphs = []
            current_lists = []
            current_raw_texts = []

        # Walk through block elements in order
        for el in content_root.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "table", "blockquote"]):
            tag_name = el.name.lower()

            if tag_name in self.HEADING_TAGS:
                flush_current_section()
                current_heading_level = tag_name.upper()
                current_heading_text = el.get_text(strip=True) or "Section"
            elif tag_name == "p":
                p_text = el.get_text(separator=" ", strip=True)
                if p_text and len(p_text) > 3:
                    current_paragraphs.append(p_text)
                    current_raw_texts.append(p_text)
            elif tag_name in ["ul", "ol"]:
                items = [li.get_text(separator=" ", strip=True) for li in el.find_all("li", recursive=False) if li.get_text(strip=True)]
                if items:
                    current_lists.append(items)
                    list_text = "\n".join([f"- {it}" for it in items])
                    current_raw_texts.append(list_text)
            elif tag_name == "table":
                tbl = self.parse_table(el)
                if tbl.rows or tbl.headers:
                    tables.append(tbl)
                    if tbl.markdown_repr:
                        current_paragraphs.append(f"\n[TABLE]\n{tbl.markdown_repr}\n[/TABLE]\n")
            elif tag_name == "blockquote":
                b_text = el.get_text(separator=" ", strip=True)
                if b_text:
                    current_paragraphs.append(f"> {b_text}")
                    current_raw_texts.append(b_text)

        # Flush final section
        flush_current_section()

        # Fallback: if no sections extracted, grab plain text
        if not sections:
            plain_text = content_root.get_text(separator="\n", strip=True)
            if plain_text:
                sections.append(DocumentSection(
                    heading_level="H1",
                    heading_text="Document Content",
                    paragraphs=[plain_text],
                    raw_text=plain_text
                ))

        # Build clean structural text string
        clean_lines: List[str] = [f"TITLE: {title}", ""]
        for s in sections:
            clean_lines.append(f"SECTION [{s.heading_level}]: {s.heading_text}")
            for p in s.paragraphs:
                clean_lines.append(p)
            for lst in s.lists:
                for item in lst:
                    clean_lines.append(f"  • {item}")
            clean_lines.append("")

        clean_text = "\n".join(clean_lines).strip()

        return title, sections, tables, clean_text
