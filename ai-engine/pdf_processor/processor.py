"""PDF sheet ingestion and classification primitives.

Determines whether each page is vector-based (CAD export) or scanned,
extracts words/text with coordinates, and renders pages to images.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf


@dataclass
class SheetInfo:
    page_index: int
    width: float
    height: float
    is_vector: bool
    text_chars: int
    image_count: int
    sheet_number: str | None = None
    sheet_title: str | None = None
    words: list[dict] = field(default_factory=list)


# Common architectural sheet-number patterns: A-101, A2.01, S-501, M-601
_SHEET_NUMBER_RE = re.compile(
    r"\b([ASMEPGLIF]?\d?(?:-\d{3}|\.\d{2}|[A-Z]-\d{2,4}))\b"
)


def _classify_page(page: pymupdf.Page) -> bool:
    """True if the page is vector-based (extractable text/paths)."""
    text_len = len(page.get_text("text").strip())
    image_area = 0.0
    for img in page.get_images(full=True):
        try:
            bbox = page.get_image_bbox(img)
            image_area += bbox.width * bbox.height
        except ValueError:
            pass
    page_area = page.rect.width * page.rect.height or 1
    # Vector pages carry real text; scanned pages are dominated by one big image.
    return text_len > 20 and (image_area / page_area) < 0.6


def _guess_sheet_metadata(page: pymupdf.Page) -> tuple[str | None, str | None]:
    """Heuristic sheet number/title: look in the title block (bottom-right)."""
    w, h = page.rect.width, page.rect.height
    title_block = pymupdf.Rect(w * 0.6, h * 0.7, w, h)
    text = page.get_text("text", clip=title_block)
    number = None
    for m in _SHEET_NUMBER_RE.finditer(text):
        number = m.group(1)
    title = None
    lines = [l.strip() for l in page.get_text("text").splitlines() if l.strip()]
    for l in lines:
        if re.search(r"\b(FLOOR|PLAN|ELEVATION|SECTION|SCHEDULE|DETAIL)\b", l, re.I) and len(l) < 60:
            title = l
            break
    return number, title


def analyze_pdf(pdf_path: str | Path) -> list[SheetInfo]:
    doc = pymupdf.open(str(pdf_path))
    sheets = []
    for i, page in enumerate(doc):
        words = [
            {"text": t, "bbox": [x0, y0, x1, y1]}
            for x0, y0, x1, y1, t, *_ in page.get_text("words")
        ]
        number, title = _guess_sheet_metadata(page)
        sheets.append(
            SheetInfo(
                page_index=i,
                width=page.rect.width,
                height=page.rect.height,
                is_vector=_classify_page(page),
                text_chars=len(page.get_text("text")),
                image_count=len(page.get_images(full=True)),
                sheet_number=number,
                sheet_title=title,
                words=words,
            )
        )
    return sheets


def render_page(pdf_path: str | Path, page_index: int, out_path: str | Path, dpi: int = 150) -> Path:
    doc = pymupdf.open(str(pdf_path))
    pix = doc[page_index].get_pixmap(dpi=dpi)
    out = Path(out_path)
    pix.save(str(out))
    return out
