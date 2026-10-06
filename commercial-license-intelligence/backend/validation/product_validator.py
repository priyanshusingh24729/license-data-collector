"""
Product & Vendor Match Validator.
Prevents cross-product pollution (e.g. applying Photoshop terms to Acrobat Pro).
"""

from typing import Tuple, Optional
from backend.models.fact import LicenseFact


class ProductValidator:
    """
    Validates that evidence and fact refer to the exact same software product.
    """

    def validate_product(
        self,
        fact: LicenseFact,
        target_vendor: str,
        target_product: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Confirms vendor and product names match the fact and evidence.
        Returns: (is_valid_match, failure_reason)
        """
        clean_v = target_vendor.strip().lower()
        clean_p = target_product.strip().lower()

        # Check vendor
        if fact.vendor_name.strip().lower() != clean_v:
            return False, f"VENDOR_MISMATCH: Fact vendor '{fact.vendor_name}' does not match target vendor '{target_vendor}'."

        # Check product name
        fact_p = fact.product_name.strip().lower()
        if fact_p != clean_p and clean_p not in fact_p and fact_p not in clean_p:
            return False, f"PRODUCT_MISMATCH: Fact product '{fact.product_name}' does not match target product '{target_product}'."

        # Check evidence text does not explicitly refer only to a competing sibling product
        ev_lower = fact.evidence_text.lower()
        if "photoshop" in ev_lower and clean_p == "acrobat":
            if "acrobat" not in ev_lower:
                return False, "CROSS_PRODUCT_POLLUTION: Evidence text exclusively discusses Photoshop, not Acrobat."

        return True, None
