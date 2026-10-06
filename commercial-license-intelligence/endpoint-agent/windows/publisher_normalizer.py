"""
Publisher string normalization utilities.
Provides preliminary corporate cleanup while preserving raw publisher records.
"""

import re
from typing import Optional

_CORP_SUFFIX_RE = re.compile(
    r",?\s*\b(Inc\.?|LLC|Corporation|Corp\.?|Ltd\.?|Limited|GmbH|Co\.?|KG|Pte\.?|S\.A\.?|N\.V\.?|Software|Systems|Technologies|International)\b\.?$",
    re.IGNORECASE
)


class PublisherNormalizer:
    """Cleans corporate naming noise from publisher strings."""

    @staticmethod
    def normalize(raw_publisher: Optional[str]) -> Optional[str]:
        if not raw_publisher:
            return None

        pub = raw_publisher.strip()
        # Iteratively strip chained corporate tokens (e.g. "Systems Inc." -> "Systems" -> "")
        for _ in range(3):
            prev = pub
            pub = _CORP_SUFFIX_RE.sub("", pub).strip()
            pub = pub.rstrip(",.- ")
            if pub == prev:
                break

        return pub if pub else raw_publisher.strip()
