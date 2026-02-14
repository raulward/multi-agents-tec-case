from pathlib import Path
from typing import Any, Dict, List, Tuple

from pypdf import PdfReader


class PDFProcessor:
    """Parse PDF files into markdown and technical metadata only."""

    def parse_folder_to_markdown(self, folder: Path | str) -> List[dict[str, Any]]:
        parsed_docs: List[dict[str, Any]] = []
        for file in Path(folder).glob("*.pdf"):
            markdown, metadata = self.parse_to_markdown(file)
            parsed_docs.append({"filename": file.name, "markdown": markdown, "metadata": metadata})
        return parsed_docs

    def parse_to_markdown(self, file: Path | str) -> Tuple[str, Dict[str, Any]]:
        path = Path(file)

        reader = PdfReader(str(path))
        pages: List[str] = []
        for page in reader.pages:
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(text)

        md = "\n\n".join(pages).strip()
        meta: Dict[str, Any] = {"page_count": len(reader.pages)}
        meta.setdefault("source", str(path))
        meta.setdefault("filename", path.name)
        return md, meta
