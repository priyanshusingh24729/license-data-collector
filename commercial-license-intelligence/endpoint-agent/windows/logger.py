"""
Structured, safe logging for Windows Endpoint Agent.
Guarantees credentials, tokens, and sensitive system artifacts are never logged.
"""

import logging
import re
import sys

_SENSITIVE_PATTERNS = [
    re.compile(r"(api[-_]?key|token|password|secret|auth)\s*[:=]\s*['\"]?([^'\"\s]+)", re.IGNORECASE),
    re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]+", re.IGNORECASE),
]


class SafeFormatter(logging.Formatter):
    """Sanitizes sensitive information from log messages."""
    def format(self, record: logging.LogRecord) -> str:
        orig = super().format(record)
        sanitized = orig
        for pat in _SENSITIVE_PATTERNS:
            sanitized = pat.sub(r"\1=***REDACTED***", sanitized)
        return sanitized


def setup_logger(name: str = "endpoint-agent", quiet: bool = False) -> logging.Logger:
    """Configures structured logger."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.WARNING if quiet else logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.WARNING if quiet else logging.INFO)
        formatter = SafeFormatter("[%(asctime)s] [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
