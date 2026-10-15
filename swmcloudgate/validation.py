"""Shared request validation helpers for the cloud gate."""

from __future__ import annotations

import re

JOB_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def assert_job_id(job_id: str | None) -> str:
    """Require a UUID-shaped job id (Sky Port / OpenAPI style)."""
    value = (job_id or "").strip()
    if not JOB_ID_RE.fullmatch(value):
        raise ValueError(f"job_id must be a UUID (got {job_id!r})")
    return value
