"""Legacy module: unused by the deterministic /ingest pipeline."""

from typing import Dict

from .types import SourceType, IngestorProtocol, IngestorOptions
from .detector import detect_source_type


class UnsupportedSourceError(Exception):
    pass


class IngestionDispatcher:
    def __init__(self) -> None:
        self._registry: Dict[SourceType, IngestorProtocol] = {}

    def register(self, source_type: SourceType, ingestor: IngestorProtocol) -> None:
        self._registry[source_type] = ingestor

    def ingest(self, url: str, options: IngestorOptions | None = None):
        source_type = detect_source_type(url)
        ingestor = self._registry.get(source_type)

        if not ingestor:
            raise UnsupportedSourceError(f"Unsupported source type: {source_type}")

        return ingestor.ingest(url, options or IngestorOptions())
