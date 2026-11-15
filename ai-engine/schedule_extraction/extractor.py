"""Door schedule table extraction.

CAD-exported PDFs often have schedule tables without ruled column lines,
so pdfplumber's table detection merges cells. Instead we locate the
schedule caption, cluster words into rows by y-position and into columns
by the header's x-positions, and emit structured rows where every value
retains a page bounding box for click-to-source review.
"""

from __future__ import annotations

import re
from pathlib import Path

import pymupdf

_SCHEDULE_CAPTION = re.compile(r"schedule\s*of\s*doors", re.I)
_DOOR_TYPE_RE = re.compile(r"^D\d*A?$|^SW$|^BFG$", re.I)
_NUM_RE = re.compile(r"^\d+$")

# Known schedule column headers in priority order.
_HEADER_MAP = {
    "slno": "serial", "sl.no": "serial", "sl": "serial",
    "type": "type", "mark": "type",
    "width": "width", "height": "height",
    "nos": "count", "nos.": "count", "no": "count", "qty": "count",
    "description": "description",
    "material": "material", "frame": "frame",
    "firerating": "fire_rating", "remarks": "remarks",
}


def _words(page: pymupdf.Page) -> list[tuple[float, float, float, float, str]]:
    return [(w[0], w[1], w[2], w[3], w[4]) for w in page.get_text("words")]


def _find_caption(words) -> tuple[float, float] | None:
    """Locate the SCHEDULE OF DOORS caption; returns (x0, bottom)."""
    # caption may be one merged token ("SCHEDULEOFDOORS&WINDOWS") or several words
    for x0, y0, x1, y1, t in words:
        if _SCHEDULE_CAPTION.search(t.replace(" ", "")):
            return x0, y1
    # multi-word caption: look for "SCHEDULE" then "DOORS" on same line
    for x0, y0, x1, y1, t in words:
        if "SCHEDULE" in t.upper():
            return x0, y1
    return None


def _cluster_rows(words, x_min: float, y_min: float, y_tol: float = 4.0):
    """Group words below y_min and right of x_min into rows by top coordinate."""
    ws = sorted(
        [w for w in words if w[0] >= x_min - 20 and w[1] >= y_min - 10],
        key=lambda w: (w[1], w[0]),
    )
    rows: list[list] = []
    for w in ws:
        if rows and abs(w[1] - rows[-1][0][1]) <= y_tol:
            rows[-1].append(w)
        else:
            rows.append([w])
    return rows


def _column_centers(header_row) -> list[tuple[str, float]]:
    centers = []
    for x0, _, x1, _, t in header_row:
        key = _HEADER_MAP.get(t.lower().replace(" ", "").rstrip("."))
        if key:
            centers.append((key, (x0 + x1) / 2))
    return centers


def extract_door_schedule(pdf_path: str | Path, page_index: int = 0) -> dict:
    """Extract the door/window schedule table from a page.

    Returns {"page": i, "rows": [{...}], "warnings": [...]}
    """
    doc = pymupdf.open(str(pdf_path))
    page = doc[page_index]
    words = _words(page)
    warnings: list[str] = []

    cap = _find_caption(words)
    if cap is None:
        return {"page": page_index, "rows": [], "warnings": ["no door schedule caption found"]}
    cap_x, cap_bottom = cap

    rows = _cluster_rows(words, x_min=cap_x - 60, y_min=cap_bottom)

    # find the header row (contains TYPE/WIDTH/HEIGHT-like tokens)
    header_idx = None
    centers: list[tuple[str, float]] = []
    for i, row in enumerate(rows[:5]):
        centers = _column_centers(row)
        if any(k == "type" for k, _ in centers) and len(centers) >= 3:
            header_idx = i
            break
    if header_idx is None:
        return {"page": page_index, "rows": [], "warnings": ["schedule header row not recognized"]}

    out_rows = []
    stop_tokens = {"BIHAR", "PROJECT", "NOTES", "DEPT", "ARCH"}
    for row in rows[header_idx + 1 :]:
        texts = [w[4] for w in row]
        joined = " ".join(texts).upper()
        if any(t in joined for t in stop_tokens):
            break
        # assign each word to nearest column center
        cells: dict[str, list[str]] = {k: [] for k, _ in centers}
        for x0, _, x1, _, t in row:
            key = min(centers, key=lambda c: abs(c[1] - (x0 + x1) / 2))[0]
            cells[key].append(t)
        rec = {k: " ".join(v).strip() for k, v in cells.items()}
        rtype = rec.get("type", "")
        if not rtype or not re.match(r"^[A-Z]\w*$", rtype):
            continue
        y0 = min(w[1] for w in row)
        y1 = max(w[3] for w in row)
        out_rows.append(
            {
                "serial": rec.get("serial"),
                "type": rtype,
                "width": rec.get("width"),
                "height": rec.get("height"),
                "count": rec.get("count"),
                "description": rec.get("description"),
                "is_door": bool(_DOOR_TYPE_RE.match(rtype)),
                "bbox": [min(w[0] for w in row), y0, max(w[2] for w in row), y1],
            }
        )
    if not out_rows:
        warnings.append("schedule caption found but no rows parsed")
    return {"page": page_index, "rows": out_rows, "warnings": warnings}
