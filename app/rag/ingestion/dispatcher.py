from typing import Callable, Mapping, Any

from .types import SourceType, IngestorProtocol, IngestorOptions
from .detector import detect_source_type


class UnsupportedSourceError(Exception):
    pass


class IngestionDispatcher:
    """Roteador de ingestao por tipo de fonte, sem criar dependencias."""

    def __init__(
        self,
        ingestors: Mapping[str | SourceType, IngestorProtocol] | None = None,
        parsers: Mapping[str | SourceType, Any] | None = None,
        detector: Callable[[str], SourceType] = detect_source_type,
    ) -> None:
        self._registry: dict[SourceType, IngestorProtocol] = {}
        self._parsers: dict[SourceType, Any] = {}
        self._detector = detector

        for kind, ingestor in (ingestors or {}).items():
            self.register(kind, ingestor)

        for kind, parser in (parsers or {}).items():
            self.register_parser(kind, parser)

    def register(self, source_type: str | SourceType, ingestor: IngestorProtocol) -> None:
        self._registry[self._normalize_source_type(source_type)] = ingestor

    def register_parser(self, source_type: str | SourceType, parser: Any) -> None:
        self._parsers[self._normalize_source_type(source_type)] = parser

    def get_ingestor(self, source_type: str | SourceType) -> IngestorProtocol:
        normalized = self._normalize_source_type(source_type)
        ingestor = self._registry.get(normalized)
        if not ingestor:
            raise UnsupportedSourceError(f"Unsupported source type: {normalized}")
        return ingestor

    def get_parser(self, source_type: str | SourceType) -> Any:
        normalized = self._normalize_source_type(source_type)
        parser = self._parsers.get(normalized)
        if not parser:
            raise UnsupportedSourceError(f"No parser configured for source type: {normalized}")
        return parser

    def ingest(self, url: str, options: IngestorOptions | None = None):
        source_type = self._detector(url)
        ingestor = self.get_ingestor(source_type)
        return ingestor.ingest(url, options or IngestorOptions())

    @staticmethod
    def _normalize_source_type(source_type: str | SourceType) -> SourceType:
        if isinstance(source_type, SourceType):
            return source_type
        return SourceType(source_type)
