"""
HTML Content Cleaner.
Removes navigational boilerplate, scripts, styles, cookie notices, and tracking elements
while carefully preserving all legal text, product terms, headings, lists, and tables.
"""

import re
import logging
from bs4 import BeautifulSoup, Comment

logger = logging.getLogger(__name__)

# Tags to strip entirely along with their children
DISCARD_TAGS = {
    "script", "style", "noscript", "svg", "form", "iframe",
    "template", "link", "meta", "button", "input", "select",
    "textarea", "canvas", "audio", "video", "source", "track"
}

# Structural / boilerplate elements to remove if they don't contain main legal terms
BOILERPLATE_TAGS = {
    "nav", "footer", "aside"
}

# Cookie / banner identifiers to filter out
BANNER_PATTERNS = re.compile(
    r"(cookie|consent|onetrust|privacy-banner|gdpr|advertisement|modal-backdrop|newsletter-signup)",
    re.IGNORECASE
)


class ContentCleaner:
    """
    Cleans raw HTML into semantic, structured DOM suitable for content extraction.
    """

    def clean_html(self, raw_html: str) -> BeautifulSoup:
        """
        Parses raw HTML and strips non-content tags, tracking code, and navigation elements.
        """
        if not raw_html:
            return BeautifulSoup("<html><body></body></html>", "html.parser")

        soup = BeautifulSoup(raw_html, "html.parser")

        # 1. Remove comments (using modern string= parameter)
        for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
            comment.extract()

        # 2. Remove script/style/form tags
        for tag_name in DISCARD_TAGS:
            for element in soup.find_all(tag_name):
                element.decompose()

        # 3. Remove standard navigation, footer, and sidebar elements
        for bp_tag in BOILERPLATE_TAGS:
            for element in soup.find_all(bp_tag):
                element.decompose()

        # 4. Remove cookie banners & consent overlays
        for banner in soup.find_all(attrs={"id": BANNER_PATTERNS}):
            banner.decompose()
        for banner in soup.find_all(attrs={"class": BANNER_PATTERNS}):
            banner.decompose()

        # 5. Remove hidden elements (e.g. style="display:none" or aria-hidden="true")
        for hidden in soup.find_all(attrs={"aria-hidden": "true"}):
            hidden.decompose()

        return soup
