from app.rag.pdf_processor import PDFProcessor

from app.core.config import settings
from app.schemas.schemas import IngestResponse


class IngestionService:

    def __init__(self, deps, rag):
        self.processor = PDFProcessor(chunk_size=1200, chunk_overlap=200)
        self.docs = self.processor.parse_folder(settings.DATA_DIR)
        self._deps = deps

    def ingest(self) -> IngestResponse:
        total_chunks = 0
        for doc in self.docs:
            self._deps.rag.upsert(doc.chunks)
            total_chunks += len(doc.chunks)
            # TODO -> Implementar o logger em uma classe
            # logger.info("Ingested %s → %d chunks", doc.metadata.get("filename"), len(doc.chunks))

        return IngestResponse(
            documents_processed=len(self.docs),
            total_chunks=total_chunks,
        )