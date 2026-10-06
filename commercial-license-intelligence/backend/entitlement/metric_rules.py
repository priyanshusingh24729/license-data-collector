"""
License Metric Compatibility & Reconciliation Rules.
Evaluates whether entitlement metrics and consumption metrics can be deterministically compared.
"""

from typing import Tuple, Optional


class MetricRules:
    """
    Evaluates metric compatibility and conversion rules between entitlement and consumption.
    """

    @classmethod
    def normalize_metric(cls, metric: Optional[str]) -> str:
        """Standardizes metric strings to uppercase canonical format."""
        if not metric:
            return "UNKNOWN"
        m = " ".join(metric.strip().split()).upper().replace("-", "_").replace(" ", "_")
        if m in ["PER_USER", "USER_BASED"]:
            return "USER"
        if m in ["PER_NAMED_USER", "NAMED_USERS"]:
            return "NAMED_USER"
        if m in ["PER_DEVICE", "DEVICE_BASED"]:
            return "DEVICE"
        if m in ["PER_CORE", "CORE_BASED"]:
            return "CORE"
        if m in ["PER_SEAT", "SEAT"]:
            return "INSTALLATION"
        return m

    @classmethod
    def are_metrics_compatible(
        cls,
        entitlement_metric: str,
        consumption_metric: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Determines whether entitlement metric and consumption metric are compatible for reconciliation.
        Returns: (is_compatible, failure_reason)
        """
        e_norm = cls.normalize_metric(entitlement_metric)
        c_norm = cls.normalize_metric(consumption_metric)

        if e_norm == "UNKNOWN" or c_norm == "UNKNOWN":
            return False, f"Cannot calculate position: metric '{entitlement_metric or consumption_metric}' is UNKNOWN."

        # Exact match
        if e_norm == c_norm:
            return True, None

        # Compatible device/installation family
        if e_norm in ["DEVICE", "INSTALLATION"] and c_norm in ["DEVICE", "INSTALLATION"]:
            return True, None

        # Compatible user family
        if e_norm in ["USER", "NAMED_USER"] and c_norm in ["USER", "NAMED_USER"]:
            return True, None

        # Incompatible metric combinations
        return False, (
            f"METRIC_MISMATCH: Entitlement metric '{e_norm}' cannot be directly reconciled "
            f"against consumption metric '{c_norm}' without explicit conversion rules."
        )

    @classmethod
    def can_derive_consumption_from_installations(
        cls,
        metric: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Checks if consumption can be automatically derived from active installation counts.
        """
        m_norm = cls.normalize_metric(metric)
        if m_norm in ["DEVICE", "INSTALLATION"]:
            return True, None
        elif m_norm in ["NAMED_USER", "USER"]:
            return False, "NAMED_USER licensing requires known assigned users; installation count cannot be directly assumed as consumption."
        elif m_norm in ["CONCURRENT_USER", "FLOATING"]:
            return False, "CONCURRENT_USER licensing requires peak concurrency telemetry; installation count cannot determine consumption."
        elif m_norm in ["CORE", "CPU", "SOCKET"]:
            return False, "CORE licensing requires hardware core telemetry; endpoint installation count is insufficient."
        else:
            return False, f"Licensing metric '{metric}' does not support automatic consumption derivation from installation count."
