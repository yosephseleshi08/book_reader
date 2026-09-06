"""
Format-specific text extraction. Each parser returns a list of
(chapter_title, chapter_text) tuples so the ingestion task can build
Chapter + Chunk rows without caring about the source format.
"""
from io import BytesIO

from pypdf import PdfReader
from ebooklib import epub
import ebooklib
from bs4 import BeautifulSoup
import docx


def parse_pdf(file_obj) -> list[tuple[str, str]]:
    reader = PdfReader(file_obj)
    full_text = []
    for page in reader.pages:
        text = page.extract_text() or ""
        full_text.append(text)
    # PDFs rarely expose clean chapter boundaries — treat as one chapter here;
    # a heuristic chapter-title detector (e.g. matching "Chapter N" headings)
    # can be layered on top later without changing the chunking pipeline.
    return [("Full text", "\n\n".join(full_text))]


def parse_epub(file_obj) -> list[tuple[str, str]]:
    book = epub.read_epub(file_obj)
    chapters = []
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), "lxml")
            title_tag = soup.find(["h1", "h2", "title"])
            title = title_tag.get_text(strip=True) if title_tag else ""
            text = soup.get_text(separator="\n", strip=True)
            if text:
                chapters.append((title, text))
    return chapters or [("Full text", "")]


def parse_docx(file_obj) -> list[tuple[str, str]]:
    document = docx.Document(file_obj)
    chapters = []
    current_title = "Introduction"
    current_paragraphs = []

    def flush():
        if current_paragraphs:
            chapters.append((current_title, "\n".join(current_paragraphs)))

    for para in document.paragraphs:
        style_name = (para.style.name or "").lower()
        if style_name.startswith("heading") and para.text.strip():
            flush()
            current_title = para.text.strip()
            current_paragraphs = []
        elif para.text.strip():
            current_paragraphs.append(para.text)
    flush()
    return chapters or [("Full text", "")]


def parse_txt(file_obj) -> list[tuple[str, str]]:
    raw = file_obj.read()
    text = raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else raw
    return [("Full text", text)]


PARSERS = {
    "pdf": parse_pdf,
    "epub": parse_epub,
    "docx": parse_docx,
    "txt": parse_txt,
}


def parse_book(file_format: str, file_obj) -> list[tuple[str, str]]:
    parser = PARSERS.get(file_format)
    if not parser:
        raise ValueError(f"Unsupported format: {file_format}")
    if not isinstance(file_obj, BytesIO):
        file_obj.seek(0)
    return parser(file_obj)
