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
# `28. 2024 Green Future …` 처럼 문항 본문이 숫자(연도 등)로 시작하는 경우.
# 소수점(`1.5`)은 점 뒤에 공백이 없고, 날짜 조각(`3. 15.`)은 뒤따르는 수가
# 다시 `번호.` 꼴이라 걸러진다.
_Q_HEAD_NUM = re.compile(r"^(\d{1,2})\s*[.．]\s+(?=\d)(?!\d{1,2}\s*[.．])")
_PASSAGE_HEAD = re.compile(r"^\[\s*(\d{1,2})\s*[~～∼\-–]\s*(\d{1,2})\s*\]")
# 수학·국어의 선택과목 머리글. 이 뒤로는 문항 번호가 공통 마지막+1 로 되돌아가
# 같은 번호가 과목 수만큼 반복된다 (수학 23~30 세 벌, 국어 35~45 두 벌).
# 시험지에는 늘 괄호로 찍힌다 — 본문에 나오는 맨말 `기하` 와 헷갈리지 않게
# 괄호까지 요구한다.
_PART_HEAD = re.compile(
    r"^[\(（]\s*(확률과\s*통계|미적분|기하|화법과\s*작문|언어와\s*매체)\s*[\)）]$")
# 구획이 새 쪽에서 시작할 때 함께 찍히는 표지줄. 머리글 없이 번호가
# 되돌아가는 경우(국어 첫 단)를 구획 시작으로 인정하는 근거로 쓴다.
_BANNER = re.compile(r"문제지\s*$|^제\s*\d\s*교시")
_LOOKAHEAD = 3  # 번호를 한두 개 놓쳐도 따라잡을 수 있는 여유

Rect = tuple[int, float, float, float, float]   # page, x0, y0, x1, y1


@dataclass
class Segment:
    kind: str                 # "front" | "passage" | "question"
    number: int | None
    number_end: int | None
    page: int
    part: str | None = None   # 선택과목 구획 (예: "미적분", "언어와 매체")
    lines: list[str] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)
    _boxes: list[tuple[int, int, tuple[float, float, float, float],
                      tuple[float, float]]] = field(default_factory=list, repr=False)

    @property
    def text(self) -> str:
        return "\n".join(self.lines).strip()

    @property
    def label(self) -> str:
        head = f"{self.part} " if self.part else ""
        if self.kind == "question":
            return f"{head}{self.number}번"
        if self.kind == "passage":
            return f"{head}{self.number}~{self.number_end}번 지문"
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
    in_parts = False          # 선택과목 구획에 들어섰는가
    cur_part: str | None = None   # 지금 구획 이름 (아직 모르면 None)
    prev_part: str | None = None
    part_base = 0             # 구획이 시작되기 직전의 번호 (여기로 되돌아간다)
    pending = False           # 머리글로 구획이 바뀌어 번호 재시작 대기
    banner_ago = 999          # `…문제지`/`제N교시` 표지줄 뒤로 몇 줄 지났나

    def relabel(n: int, target: str | None) -> None:
        """머리글보다 먼저 잡혀 구획 표시가 빠진 문항·지문을 소급해 채운다."""
        for s in segments:
            if s.kind in ("question", "passage") and s.part is None \
                    and s.number is not None and s.number >= n:
                s.part = target

    def restart(n: int) -> bool:
        """구획 경계의 번호 재시작인가.

        수학은 구획 머리글이 문항보다 먼저 나와 pending 으로 잡히지만,
        국어는 구획 첫 단에 머리글이 없어(둘째 단부터 찍힘) 첫 문항이
        먼저 나온다. 그 경우 표지줄 직후의 번호 되돌아감을 구획 시작으로
        보고, 이름은 뒤따르는 머리글이 소급해서 붙인다.
        """
        nonlocal part_base, last_no, cur_part, pending
        window = part_base - _LOOKAHEAD <= n <= part_base + _LOOKAHEAD
        if pending and window:
            if n <= part_base:                # 경계가 알던 것보다 앞이었다
                relabel(n, prev_part)
                part_base = n - 1
            last_no, pending = n - 1, False
            return True
        if in_parts and cur_part is not None and window \
                and n <= last_no and banner_ago <= 8:
            if n <= part_base:
                relabel(n, cur_part)
                part_base = n - 1
            cur_part, last_no = None, n - 1   # 이름은 머리글이 오면 붙는다
            return True
        return False

    for ln in lines:
        text = ln.text
        banner_ago = 0 if _BANNER.search(text.strip()) else banner_ago + 1

        m_part = _PART_HEAD.match(text.strip())
        if m_part and last_no:
            name = re.sub(r"\s+", " ", m_part.group(1))
            if not in_parts:
                # 첫 구획. 머리글 줄은 앞 문항에 붙지 않게 자리를 갈라 둔다.
                in_parts, cur_part, part_base = True, name, last_no
                segments.append(Segment("front", None, None, ln.page))
            elif cur_part is None:
                # 이름 없이 열린 구획에 이름이 도착했다.
                cur_part = name
                relabel(part_base + 1, name)
            elif name != cur_part:
                # 정식 구획 전환 (머리글이 문항보다 먼저 나오는 지면).
                prev_part, cur_part = cur_part, name
                last_no, pending = part_base, True
                segments.append(Segment("front", None, None, ln.page))
            _add(segments[-1], ln)
            continue

        m_pass = _PASSAGE_HEAD.match(text)
        if m_pass:
            a, b = int(m_pass.group(1)), int(m_pass.group(2))
            if a <= b and (last_no < a <= last_no + _LOOKAHEAD + 1 or restart(a)):
                segments.append(Segment("passage", a, b, ln.page, part=cur_part))
                _add(segments[-1], ln)
                pending = False
                continue

        m_q = _Q_HEAD.match(text) or _Q_HEAD_NUM.match(text)
        if m_q:
            n = int(m_q.group(1))
            if last_no < n <= last_no + _LOOKAHEAD or restart(n):
                segments.append(Segment("question", n, n, ln.page, part=cur_part))
                _add(segments[-1], ln)
                last_no = n
                pending = False
                continue

        _add(segments[-1], ln)

    return [s for s in segments if s.text]
