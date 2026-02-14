"""Legacy module: unused by the deterministic /ingest pipeline."""

import requests
from urllib.parse import urlparse

from .types import SourceType


def detect_source_type(url: str, timeout: float = 5.0) -> SourceType:
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
        content_type = resp.headers.get("Content-Type", "").lower()

        if "pdf" in content_type:
            return SourceType.PDF

        if "html" in content_type:
            return SourceType.HTML

    except Exception:
        pass

    path = urlparse(url).path.lower()

    if path.endswith(".pdf"):
        return SourceType.PDF

    if path.endswith(".html") or path.endswith(".htm"):
        return SourceType.HTML

    return SourceType.UNKNOWN
