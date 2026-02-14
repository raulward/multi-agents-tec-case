import json
import logging
from dataclasses import dataclass
from typing import Callable

import requests

from app.rag.ingestion.models import FetchOverrides


logger = logging.getLogger(__name__)


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; multi-agents-ingestion/1.0)",
    "Accept": "*/*",
}


@dataclass(frozen=True)
class FetchResult:
    url: str
    resolved_url: str
    status_code: int
    content_type: str
    content: bytes
    bytes_downloaded: int


class UrlFetcher:
    """Cliente HTTP do pipeline de ingestao com retry e limites de payload."""

    def __init__(
        self,
        headers: dict[str, str] | None = None,
        session_factory: Callable[[], requests.Session] = requests.Session,
    ) -> None:
        self._headers = headers or DEFAULT_HEADERS
        self._session_factory = session_factory

    def fetch(self, url: str, fetch_overrides: FetchOverrides) -> FetchResult:
        with self._session_factory() as session:
            session.headers.update(self._headers)
            response = self._request_with_retries(
                session=session,
                url=url,
                timeout_s=fetch_overrides.timeout_s,
                retries=fetch_overrides.retries,
            )
            self._validate_max_bytes(response.content, fetch_overrides.max_bytes)
            return FetchResult(
                url=url,
                resolved_url=response.url,
                status_code=response.status_code,
                content_type=response.headers.get("Content-Type", ""),
                content=response.content,
                bytes_downloaded=len(response.content),
            )

    def _request_with_retries(
        self,
        session: requests.Session,
        url: str,
        timeout_s: float,
        retries: int,
    ) -> requests.Response:
        last_error: Exception | None = None
        total_attempts = retries + 1
        for attempt in range(1, total_attempts + 1):
            try:
                response = self._request_once(session=session, url=url, timeout_s=timeout_s)
                self._log_fetch_event(
                    "fetch_attempt_succeeded",
                    url=url,
                    timeout_s=timeout_s,
                    attempt=attempt,
                    total_attempts=total_attempts,
                    status_code=response.status_code,
                )
                return response
            except Exception as exc:
                last_error = exc
                self._log_fetch_event(
                    "fetch_attempt_failed",
                    url=url,
                    timeout_s=timeout_s,
                    attempt=attempt,
                    total_attempts=total_attempts,
                    error=str(exc),
                )
        if last_error is None:
            raise RuntimeError("unexpected fetch failure")
        raise last_error

    def _request_once(self, session: requests.Session, url: str, timeout_s: float) -> requests.Response:
        response = session.get(url, timeout=timeout_s, allow_redirects=True)
        response.raise_for_status()
        return response

    def _validate_max_bytes(self, content: bytes, max_bytes: int) -> None:
        if len(content) > max_bytes:
            raise ValueError(f"response exceeds max_bytes={max_bytes}")

    def _log_fetch_event(self, step: str, **extra: object) -> None:
        event = {"step": step}
        event.update(extra)
        logger.info("ingestion_fetch=%s", json.dumps(event, ensure_ascii=False))


def fetch_url(url: str, fetch_overrides: FetchOverrides) -> FetchResult:
    """Wrapper de compatibilidade para chamadas legadas."""
    return UrlFetcher().fetch(url=url, fetch_overrides=fetch_overrides)
