import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from app.rag.ingestion.models import HtmlExtractSpec
from app.rag.pdf_processor import PDFProcessor


@dataclass(frozen=True)
class ParsedMarkdown:
    markdown: str
    base_metadata: dict[str, Any]


def parse_pdf_to_markdown(pdf_bytes: bytes, source_id: str) -> ParsedMarkdown:
    tmp_path = _write_temp_pdf(pdf_bytes)
    try:
        markdown, metadata = PDFProcessor().parse_to_markdown(tmp_path)
    finally:
        _cleanup_temp_file(tmp_path)
    metadata["content_type"] = "pdf"
    metadata["source_id"] = source_id
    return ParsedMarkdown(markdown=markdown, base_metadata=metadata)


def parse_html_to_markdown(html_text: str, extract_spec: HtmlExtractSpec, source_id: str) -> ParsedMarkdown:
    soup = BeautifulSoup(html_text, "html.parser")
    _remove_nodes(soup, extract_spec.remove_selectors)
    selected = _select_text(soup, extract_spec.selectors)
    if not selected.strip():
        raise ValueError("no content extracted from provided selectors")
    markdown = _normalize_text(selected)
    if not markdown:
        raise ValueError("empty markdown after html extraction")
    return ParsedMarkdown(
        markdown=markdown,
        base_metadata={"content_type": "html", "source_id": source_id},
    )


def _write_temp_pdf(pdf_bytes: bytes) -> Path:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_bytes)
        return Path(tmp.name)


def _cleanup_temp_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def _remove_nodes(soup: BeautifulSoup, selectors: list[str]) -> None:
    for selector in selectors:
        for node in soup.select(selector):
            node.decompose()


def _select_text(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        nodes = soup.select(selector)
        if not nodes:
            continue
        text = "\n\n".join(node.get_text(separator="\n", strip=True) for node in nodes).strip()
        if text:
            return text
    return ""


def _normalize_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    non_empty = [line for line in lines if line]
    return "\n".join(non_empty).strip()
