"""문항을 원본 PDF에서 오려 이미지로 만든다.

텍스트만 보면 그림·표·수식이 빠져서 윤문 판단이 안 된다.
검색 결과를 눌렀을 때 실제 지면을 그대로 보여주기 위한 모듈.
"""

from __future__ import annotations

import json
import sqlite3

import pymupdf

MAX_ZOOM = 4.0


def rects_of(row: sqlite3.Row) -> list[tuple[int, float, float, float, float]]:
    try:
        return [tuple(r) for r in json.loads(row["rects"] or "[]")]
    except (json.JSONDecodeError, TypeError):
        return []


def render_clip(pdf_path: str, page_no: int, clip: tuple[float, float, float, float],
                zoom: float = 2.0) -> bytes:
    """PDF 한 페이지의 지정 영역을 PNG 로."""
    doc = pymupdf.open(pdf_path)
    try:
        page = doc.load_page(page_no - 1)
        rect = pymupdf.Rect(*clip) & page.rect
        if rect.is_empty:
            rect = page.rect
        pix = page.get_pixmap(matrix=pymupdf.Matrix(min(zoom, MAX_ZOOM), min(zoom, MAX_ZOOM)),
                              clip=rect)
        return pix.tobytes("png")
    finally:
        doc.close()


def render_page(pdf_path: str, page_no: int, zoom: float = 1.6) -> bytes:
    doc = pymupdf.open(pdf_path)
    try:
        page = doc.load_page(page_no - 1)
        z = min(zoom, MAX_ZOOM)
        return page.get_pixmap(matrix=pymupdf.Matrix(z, z)).tobytes("png")
    finally:
        doc.close()


def render_segment(row: sqlite3.Row, part: int = 0, zoom: float = 2.0) -> bytes:
    """검색 결과 행 하나를 이미지로. part 는 (페이지·단)별 조각 번호."""
    rs = rects_of(row)
    if not rs:
        return render_page(row["path"], row["page"], zoom=1.6)
    page, x0, y0, x1, y1 = rs[max(0, min(part, len(rs) - 1))]
    return render_clip(row["path"], int(page), (x0, y0, x1, y1), zoom=zoom)


def segment_parts(row: sqlite3.Row) -> int:
    return max(1, len(rects_of(row)))
