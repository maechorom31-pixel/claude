"""추출된 줄들을 문항 단위로 자른다.

`14.` 같은 줄머리 번호를 문항 시작으로 보되, 번호가 순서대로 늘어날 때만
인정한다. 그냥 정규식만 쓰면 본문 속 `1.` 이나 소수점 `1.5` 까지 문항으로
잡히기 때문이다.

국어/영어의 `[1~3] 다음 글을 읽고 물음에 답하시오.` 형태 지문은 별도
세그먼트로 보관하고 문항 범위를 붙여 둔다.

각 문항이 원본 PDF의 어느 자리인지도 함께 모은다. 한 문항이 좌단 아래에서
우단 위로 이어지면 사각형이 둘 생긴다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .extract import Line

_Q_HEAD = re.compile(r"^(\d{1,2})\s*[.．]\s*(?=[^\d\s]|\s*$)")
_PASSAGE_HEAD = re.compile(r"^\[\s*(\d{1,2})\s*[~～∼\-–]\s*(\d{1,2})\s*\]")
_LOOKAHEAD = 3  # 번호를 한두 개 놓쳐도 따라잡을 수 있는 여유

Rect = tuple[int, float, float, float, float]   # page, x0, y0, x1, y1


@dataclass
class Segment:
    kind: str                 # "front" | "passage" | "question"
    number: int | None
    number_end: int | None
    page: int
    lines: list[str] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)
    _boxes: list[tuple[int, int, tuple[float, float, float, float],
                      tuple[float, float]]] = field(default_factory=list, repr=False)

    @property
    def text(self) -> str:
        return "\n".join(self.lines).strip()

    @property
    def label(self) -> str:
        if self.kind == "question":
            return f"{self.number}번"
        if self.kind == "passage":
            return f"{self.number}~{self.number_end}번 지문"
        return "표지/안내"

    def rects(self, padx: float = 0.0, pady: float = 4.0) -> list[Rect]:
        """문항이 차지한 영역. (페이지, 단) 별로 하나씩."""
        groups: dict[tuple[int, int], list[float]] = {}
        for page, col, (x0, y0, x1, y1), (cx0, cx1) in self._boxes:
            # 가로는 단 전체로 넓힌다. 글 옆에 붙은 그림·표가 잘리지 않게.
            x0, x1 = min(x0, cx0), max(x1, cx1)
            g = groups.get((page, col))
            if g is None:
                groups[(page, col)] = [x0, y0, x1, y1]
            else:
                g[0], g[1] = min(g[0], x0), min(g[1], y0)
                g[2], g[3] = max(g[2], x1), max(g[3], y1)
        out = [(page, g[0] - padx, g[1] - pady, g[2] + padx, g[3] + pady)
               for (page, _col), g in groups.items()]
        return sorted(out, key=lambda r: (r[0], r[2]))


def _add(seg: Segment, ln: Line) -> None:
    seg.lines.append(ln.text)
    seg._boxes.append((ln.page, ln.col, ln.bbox, ln.colbox))


def segment(lines: list[Line]) -> list[Segment]:
    if not lines:
        return []
    segments: list[Segment] = [Segment("front", None, None, lines[0].page)]
    last_no = 0

    for ln in lines:
        text = ln.text
        m_pass = _PASSAGE_HEAD.match(text)
        if m_pass:
            a, b = int(m_pass.group(1)), int(m_pass.group(2))
            if a <= b and last_no < a <= last_no + _LOOKAHEAD + 1:
                segments.append(Segment("passage", a, b, ln.page))
                _add(segments[-1], ln)
                continue

        m_q = _Q_HEAD.match(text)
        if m_q:
            n = int(m_q.group(1))
            if last_no < n <= last_no + _LOOKAHEAD:
                segments.append(Segment("question", n, n, ln.page))
                _add(segments[-1], ln)
                last_no = n
                continue

        _add(segments[-1], ln)

    return [s for s in segments if s.text]
