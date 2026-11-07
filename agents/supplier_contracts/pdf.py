"""ReportLab authoring and pdfplumber/pypdfium2 extraction. No line truncation."""

from __future__ import annotations

import hashlib
import textwrap
from pathlib import Path

from pypdfium2 import PdfDocument
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

WRAP_WIDTH = 92


def _wrapped_lines(pages: list[list[str]]) -> list[list[str]]:
    wrapped: list[list[str]] = []
    for page in pages:
        lines: list[str] = []
        for raw in page:
            if not raw:
                lines.append("")
                continue
            lines.extend(textwrap.wrap(raw, width=WRAP_WIDTH) or [""])
        wrapped.append(lines)
    return wrapped


def write_pdf(path: Path, pages: list[list[str]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    wrapped = _wrapped_lines(pages)
    document = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    for page_lines in wrapped:
        y = height - 54
        document.setFont("Times-Roman", 11)
        for line in page_lines:
            if y < 54:
                document.showPage()
                document.setFont("Times-Roman", 11)
                y = height - 54
            document.drawString(54, y, line)
            y -= 14
        document.showPage()
    document.save()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_pages(path: Path) -> list[str]:
    import pdfplumber

    texts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            texts.append(page.extract_text() or "")
    return texts


def render_page_pngs(path: Path, destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    document = PdfDocument(str(path))
    written: list[Path] = []
    try:
        for index, page in enumerate(document, start=1):
            bitmap = page.render(scale=1.5)
            image = bitmap.to_pil()
            target = destination / f"page-{index}.png"
            image.save(target)
            written.append(target)
    finally:
        document.close()
    return written


def pdf_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
