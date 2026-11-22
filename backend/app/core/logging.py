"""Logging with redaction filter that prevents leaking patient content or secrets."""
from __future__ import annotations

import logging
import re

# Redaction patterns for API tokens, secret keys, and credentials
_REDACT_PATTERNS = [
    re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{6,}", re.IGNORECASE),
    re.compile(r"(api[_-]?key[\"'\s:=]+)[A-Za-z0-9_\-\.]{6,}", re.IGNORECASE),
    re.compile(r"(sk-[A-Za-z0-9]{8,})", re.IGNORECASE),
]


class RedactionFilter(logging.Filter):
    """Filter that strips out sensitive keys and credentials before logging."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            msg = record.msg
            for p in _REDACT_PATTERNS:
                msg = p.sub(r"\1[REDACTED]", msg)
            record.msg = msg
        if record.args:
            redacted_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    for p in _REDACT_PATTERNS:
                        arg = p.sub(r"\1[REDACTED]", arg)
                    redacted_args.append(arg)
                else:
                    redacted_args.append(arg)
            record.args = tuple(redacted_args)
        return True


_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
_handler.addFilter(RedactionFilter())

# Configure root logger with handler
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
if not root_logger.handlers:
    root_logger.addHandler(_handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"kotha.{name}")
