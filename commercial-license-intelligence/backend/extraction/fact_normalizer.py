"""
Fact Normalization Engine.
Translates extracted strings and candidate values into the strict controlled taxonomy.
Guarantees that no unvalidated or arbitrary strings enter the knowledge database.
"""

import re
from typing import Optional
from backend.models.enums import (
    FactType,
    LicenseClassificationValue,
    LicenseRequiredValue,
    LicenseModelValue,
    LicenseMetricValue,
    LicenseDurationValue,
    UsageRightValue,
    BooleanFactValue,
    LicenseTypeValue,
)


class FactNormalizer:
    """
    Normalizes candidate fact strings to canonical enumeration values.
    """

    def normalize(self, fact_type: FactType, raw_value: str) -> str:
        """
        Maps a raw extracted value to the controlled taxonomy value for fact_type.
        """
        if not raw_value:
            return "UNKNOWN"

        clean = raw_value.strip().upper().replace("-", "_").replace(" ", "_")

        if fact_type == FactType.LICENSE_CLASSIFICATION:
            return self._normalize_classification(clean)
        elif fact_type == FactType.LICENSE_REQUIRED:
            return self._normalize_required(clean)
        elif fact_type == FactType.LICENSE_MODEL:
            return self._normalize_model(clean, raw_value=raw_value)
        elif fact_type == FactType.LICENSE_METRIC:
            return self._normalize_metric(clean)
        elif fact_type == FactType.LICENSE_DURATION:
            return self._normalize_duration(clean)
        elif fact_type in [
            FactType.COMMERCIAL_USE,
            FactType.EDUCATIONAL_USE,
            FactType.SECONDARY_DEVICE_RIGHTS,
            FactType.VIRTUALIZATION_RIGHTS,
        ]:
            return self._normalize_usage_rights(clean)
        elif fact_type == FactType.TRIAL_AVAILABLE:
            return self._normalize_boolean(clean)

        return "UNKNOWN"

    def _normalize_classification(self, val: str) -> str:
        if "FREE_AND_PAID" in val or "FREEMIUM" in val or "FREE_OR_PAID" in val:
            return LicenseClassificationValue.FREE_AND_PAID.value
        if "COMMERCIAL_COMPONENT" in val:
            return LicenseClassificationValue.COMMERCIAL_COMPONENT.value
        if "OS_BUNDLED" in val or "WINDOWS_INBOX" in val or "SYSTEM_COMPONENT" in val:
            return LicenseClassificationValue.OS_BUNDLED.value
        if "COMMERCIAL" in val and "NON" not in val:
            return LicenseClassificationValue.COMMERCIAL.value
        if "PROPRIETARY" in val:
            return LicenseClassificationValue.PROPRIETARY.value
        if "FREEWARE" in val or "FREE_FOR_PERSONAL" in val or "GRATIS" in val:
            return LicenseClassificationValue.FREEWARE.value
        if "TRIAL" in val or "EVALUATION" in val:
            return LicenseClassificationValue.TRIAL.value
        if "EDUCATIONAL" in val or "ACADEMIC" in val or "STUDENT" in val:
            return LicenseClassificationValue.EDUCATIONAL.value
        if "NON_COMMERCIAL" in val:
            return LicenseClassificationValue.NON_COMMERCIAL.value
        if "OPEN_SOURCE" in val or "FOSS" in val or "GPL" in val or "MIT" in val or "APACHE" in val:
            return LicenseClassificationValue.OPEN_SOURCE.value
        if "PUBLIC_DOMAIN" in val:
            return LicenseClassificationValue.PUBLIC_DOMAIN.value
        return LicenseClassificationValue.UNKNOWN.value

    def _normalize_required(self, val: str) -> str:
        if "CONTEXT_DEPENDENT" in val or "TIER_DEPENDENT" in val:
            return LicenseRequiredValue.CONTEXT_DEPENDENT.value
        if "NOT_APPLICABLE" in val or val in ["N/A", "NA"]:
            return LicenseRequiredValue.NOT_APPLICABLE.value
        if "NOT_REQUIRED" in val or "NO_LICENSE" in val or val in ["FALSE", "NO", "OPTIONAL", "0", "FREE"]:
            return LicenseRequiredValue.FALSE.value
        if "REQUIRED" in val or "MANDATORY" in val or val in ["TRUE", "YES", "1"]:
            return LicenseRequiredValue.TRUE.value
        return LicenseRequiredValue.UNKNOWN.value

    def _normalize_model(self, val: str, raw_value: Optional[str] = None) -> str:
        if raw_value and ("—" in raw_value or " - " in raw_value):
            return raw_value.strip().replace(" - ", " — ")
        if "FREEWARE" in val:
            return "Freeware"
        if "SUBSCRIPTION" in val or "SAAS" in val or "RECURRING" in val:
            return LicenseModelValue.SUBSCRIPTION.value
        if "PERPETUAL" in val and ("MAINTENANCE" in val or "ACTIVE" in val):
            return LicenseModelValue.PERPETUAL_WITH_MAINTENANCE.value
        if "PERPETUAL" in val or "ONE_TIME" in val:
            return LicenseModelValue.PERPETUAL.value
        if "TERM" in val:
            return LicenseModelValue.TERM.value
        if "NAMED_USER" in val or "NAMED" in val:
            return LicenseModelValue.NAMED_USER.value
        if "CONCURRENT" in val or "FLOATING" in val or "NETWORK" in val:
            return LicenseModelValue.CONCURRENT.value
        if "DEVICE" in val or "NODE_LOCKED" in val:
            return LicenseModelValue.DEVICE.value
        if "TRIAL" in val or "EVALUATION" in val:
            return LicenseModelValue.TRIAL.value
        if "FREE" in val:
            return LicenseModelValue.FREE.value
        if "OPEN_SOURCE" in val:
            return LicenseModelValue.OPEN_SOURCE.value
        if "OEM" in val:
            return LicenseModelValue.OEM.value
        return raw_value.strip() if raw_value else LicenseModelValue.UNKNOWN.value

    def _normalize_metric(self, val: str) -> str:
        if "NAMED_USER" in val:
            return LicenseMetricValue.NAMED_USER.value
        if "CONCURRENT_USER" in val:
            return LicenseMetricValue.CONCURRENT_USER.value
        if "CONCURRENT_DEVICE" in val:
            return LicenseMetricValue.CONCURRENT_DEVICE.value
        if "USER" in val or "SEAT" in val:
            return LicenseMetricValue.USER.value
        if "CORE" in val:
            return LicenseMetricValue.CORE.value
        if "CPU" in val or "PROCESSOR" in val:
            return LicenseMetricValue.CPU.value
        if "SOCKET" in val:
            return LicenseMetricValue.SOCKET.value
        if "SERVER" in val:
            return LicenseMetricValue.SERVER.value
        if "VM" in val or "VIRTUAL_MACHINE" in val:
            return LicenseMetricValue.VM.value
        if "INSTANCE" in val:
            return LicenseMetricValue.INSTANCE.value
        if "DEVICE" in val or "INSTALLATION" in val or "MACHINE" in val or "ENDPOINT" in val:
            return LicenseMetricValue.DEVICE.value
        if "ORGANIZATION" in val or "ENTERPRISE" in val or "SITE" in val:
            return LicenseMetricValue.ORGANIZATION.value
        return LicenseMetricValue.UNKNOWN.value

    def _normalize_duration(self, val: str) -> str:
        if "MONTH" in val:
            return LicenseDurationValue.MONTHLY.value
        if "YEAR" in val or "ANNUAL" in val:
            return LicenseDurationValue.ANNUAL.value
        if "MULTI_YEAR" in val:
            return LicenseDurationValue.MULTI_YEAR.value
        if "PERPETUAL" in val or "LIFETIME" in val:
            return LicenseDurationValue.PERPETUAL.value
        if "TRIAL" in val or "DAY" in val:
            return LicenseDurationValue.TRIAL_PERIOD.value
        return LicenseDurationValue.UNKNOWN.value

    def _normalize_usage_rights(self, val: str) -> str:
        if "ALLOWED" in val or "PERMITTED" in val or "YES" in val or "INCLUDED" in val:
            return UsageRightValue.ALLOWED.value
        if "RESTRICTED" in val or "CONDITIONAL" in val or "REQUIRES" in val:
            return UsageRightValue.RESTRICTED.value
        if "NOT_ALLOWED" in val or "PROHIBITED" in val or "NO" in val or "FORBIDDEN" in val:
            return UsageRightValue.NOT_ALLOWED.value
        return UsageRightValue.UNKNOWN.value

    def _normalize_boolean(self, val: str) -> str:
        if val in ["TRUE", "YES", "AVAILABLE", "1"]:
            return BooleanFactValue.TRUE.value
        if val in ["FALSE", "NO", "UNAVAILABLE", "0"]:
            return BooleanFactValue.FALSE.value
        return BooleanFactValue.UNKNOWN.value
