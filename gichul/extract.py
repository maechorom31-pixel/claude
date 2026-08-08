"""PDF -> 읽기 순서대로 정렬된 텍스트 줄 (+ 원본 좌표).

시험지는 대부분 2단 편집이라 그냥 뽑으면 좌우 단이 뒤섞인다.
블록 좌표를 보고 '전체폭 블록(머리글·표제)'과 '좌/우 단'을 나눈 뒤
띠(band) 단위로 좌단 -> 우단 순서로 이어 붙인다.

각 줄에 원본 블록의 좌표를 달아 둔다. 나중에 "이 문항을 PDF에서 오려내
보여주기"를 하려면 좌표가 필요하기 때문이다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pymupdf

from .normalize import clean_text, count_unreadable

FULL_WIDTH_RATIO = 0.62   # 페이지 폭의 이 비율을 넘으면 단을 가로지르는 블록
MIN_TEXT_PER_PAGE = 40    # 이보다 글자가 적으면 스캔본(이미지 PDF)으로 의심

FULL = -1                 # 단을 가로지르는 블록의 열 번호


@dataclass
class Line:
    page: int                       # 1-based
    text: str
    col: int = FULL                 # 0=좌단, 1=우단, FULL=전체폭
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    colbox: tuple[float, float] = (0.0, 0.0)   # 이 줄이 속한 단의 좌우 끝


@dataclass
class Table:
    page: int
    bbox: tuple[float, float, float, float]
    rows: list[list[str]]


@dataclass
class Extraction:
    lines: list[Line]
    n_pages: int
    scanned_pages: list[int]        # 텍스트가 거의 없는 페이지 = OCR 필요
    columns_per_page: list[int]
    page_sizes: list[tuple[float, float]] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    n_chars: int = 0
    n_broken: int = 0               # 글꼴 매핑이 없어 못 읽은 문자 수

    @property
    def text(self) -> str:
        return "\n".join(ln.text for ln in self.lines)


def _find_tables(page: "pymupdf.Page", pno: int) -> list[Table]:
    """표를 찾되 오탐을 걸러낸다.

    find_tables() 는 페이지 테두리나 성명·수험번호 칸까지 표로 잡는다.
    윤문할 때 쓸 만한 자료표만 남기려면 크기·칸 수·채움 비율로 추려야 한다.
    """
    page_area = abs(page.rect.get_area()) or 1.0
    out: list[Table] = []
    try:
        found = page.find_tables()
    except Exception:                       # noqa: BLE001 - 표 검출 실패가 색인을 막지 않게
        return out

    for t in found.tables:
        x0, y0, x1, y1 = t.bbox
        if (x1 - x0) * (y1 - y0) > page_area * 0.5:      # 페이지 테두리
            continue
        try:
            rows = [[clean_text(c or "").replace("\n", " ").strip() for c in r]
                    for r in t.extract()]
        except Exception:                   # noqa: BLE001
            continue
        rows = [r for r in rows if any(c for c in r)]
        if len(rows) < 2 or max(len(r) for r in rows) < 2:
            continue
        cells = [c for r in rows for c in r]
        if sum(1 for c in cells if c) < len(cells) * 0.4:  # 거의 빈 격자
            continue
        out.append(Table(pno, (x0, y0, x1, y1), rows))
    return out


def _gutter(page: "pymupdf.Page", width: float) -> float:
    """두 단 사이 빈 띠의 한가운데. 본문 글줄 위치로 정한다."""
    mid = width / 2
    narrow = [b for b in page.get_text("blocks")
              if b[6] == 0 and b[4].strip() and (b[2] - b[0]) <= width * FULL_WIDTH_RATIO]
    left = [b[2] for b in narrow if (b[0] + b[2]) / 2 < mid]
    right = [b[0] for b in narrow if (b[0] + b[2]) / 2 >= mid]
    if not left or not right:
        return mid
    return (max(left) + min(right)) / 2


def _column_bounds(page: "pymupdf.Page", two_col: bool) -> dict[int, tuple[float, float]]:
    """단별 좌우 끝.

    그림·표 괘선까지 넣어야 문항을 오려낼 때 그래프가 잘리지 않는다. 다만
    단 경계를 넘기면 옆 단 문항이 딸려 들어오므로 gutter 에서 자른다.
    """
    width = page.rect.width
    gutter = _gutter(page, width) if two_col else width
    spans: dict[int, list[float]] = {}

    def note(col: int, x0: float, x1: float) -> None:
        if col == 0:
            x1 = min(x1, gutter)
        elif col == 1:
            x0 = max(x0, gutter)
        if x1 <= x0:
            return
        g = spans.get(col)
        if g is None:
            spans[col] = [x0, x1]
        else:
            g[0], g[1] = min(g[0], x0), max(g[1], x1)

    def assign(x0: float, x1: float) -> int:
        if not two_col or (x1 - x0) > width * FULL_WIDTH_RATIO:
            return FULL
        return 0 if (x0 + x1) / 2 < gutter else 1

    for b in page.get_text("blocks"):
        note(assign(b[0], b[2]), b[0], b[2])
    for d in page.get_drawings():          # 그래프 축·표 괘선
        r = d["rect"]
        if r.is_empty or r.width > width * 0.95:
            continue
        note(assign(r.x0, r.x1), r.x0, r.x1)

    return {k: (v[0], v[1]) for k, v in spans.items()}


def _ordered_blocks(page: "pymupdf.Page") -> tuple[list[tuple], int]:
    """(블록, 열번호) 를 읽기 순서대로. 블록은 PyMuPDF 의 blocks 튜플."""
    raw = [b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
    if not raw:
        return [], 0
    width = page.rect.width
    raw.sort(key=lambda b: (round(b[1], 1), b[0]))

    is_full = {id(b): (b[2] - b[0]) > width * FULL_WIDTH_RATIO for b in raw}
    mid = width / 2
    narrow = [b for b in raw if not is_full[id(b)]]
    n_left = sum(1 for b in narrow if (b[0] + b[2]) / 2 < mid)
    two_col = n_left >= 2 and (len(narrow) - n_left) >= 2

    if not two_col:
        return [(b, FULL) for b in raw], 1

    out: list[tuple] = []
    buf: list[tuple] = []

    def flush() -> None:
        if not buf:
            return
        left = sorted((b for b in buf if (b[0] + b[2]) / 2 < mid), key=lambda b: b[1])
        right = sorted((b for b in buf if (b[0] + b[2]) / 2 >= mid), key=lambda b: b[1])
        out.extend([(b, 0) for b in left] + [(b, 1) for b in right])
        buf.clear()

    for b in raw:
        if is_full[id(b)]:
            flush()
            out.append((b, FULL))
        else:
            buf.append(b)
    flush()
    return out, 2


def _strip_running_heads(pages: list[list[Line]]) -> list[list[Line]]:
    """모든 페이지에 반복되는 머리말/꼬리말(과목명, 쪽번호 등)을 제거."""
    if len(pages) < 3:
        return pages
    from collections import Counter

    counter: Counter[str] = Counter()
    for lines in pages:
        edge = lines[:2] + lines[-2:]
        counter.update({ln.text.strip() for ln in edge if 0 < len(ln.text.strip()) <= 24})
    threshold = max(2, int(len(pages) * 0.5))
    noise = {k for k, v in counter.items() if v >= threshold}
    if not noise:
        return pages
    return [[ln for ln in lines if ln.text.strip() not in noise] for lines in pages]


def extract(path: str) -> Extraction:
    doc = pymupdf.open(path)
    per_page: list[list[Line]] = []
    scanned: list[int] = []
    cols: list[int] = []
    sizes: list[tuple[float, float]] = []
    tables: list[Table] = []
    n_chars = n_broken = 0
    try:
        for pno in range(doc.page_count):
            page = doc.load_page(pno)
            sizes.append((page.rect.width, page.rect.height))
            blocks, ncol = _ordered_blocks(page)
            cols.append(ncol)
            tables += _find_tables(page, pno + 1)
            bounds = _column_bounds(page, ncol == 2)
            default_bound = (page.rect.x0, page.rect.x1)

            page_lines: list[Line] = []
            for block, col in blocks:
                body = block[4]
                n_chars += len(body)
                n_broken += count_unreadable(body)
                bbox = (block[0], block[1], block[2], block[3])
                colbox = bounds.get(col, default_bound)
                for txt in clean_text(body).split("\n"):
                    if txt.strip():
                        page_lines.append(Line(pno + 1, txt, col, bbox, colbox))

            if sum(len(ln.text) for ln in page_lines) < MIN_TEXT_PER_PAGE:
                scanned.append(pno + 1)
            per_page.append(page_lines)
    finally:
        doc.close()

    per_page = _strip_running_heads(per_page)
    return Extraction(lines=[ln for lines in per_page for ln in lines],
                      n_pages=len(per_page), scanned_pages=scanned,
                      columns_per_page=cols, page_sizes=sizes, tables=tables,
                      n_chars=n_chars, n_broken=n_broken)
