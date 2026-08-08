"""표기 정규화.

기출 검색의 핵심은 "띄어쓰기를 몰라서 찾는다"는 점이다.
`빛에너지`로 검색해도 `빛 에너지`가 걸려야 하고, 반대도 마찬가지여야 한다.
그래서 원문과 별개로 '공백을 모두 지운 형태'(nospace)를 함께 저장하고,
nospace 위치 -> 원문 위치 매핑을 들고 다닌다.
"""

from __future__ import annotations

import re
import unicodedata

# PDF 추출 과정에서 흔히 섞여 들어오는 비표준 공백/제어문자
_INVISIBLE = dict.fromkeys(
    map(ord, "­​‌‍﻿⁠\x00"), None
)
_SPACE_RE = re.compile(r"\s+")

# 폰트에 ToUnicode 매핑이 없으면 추출 결과에 이런 문자가 섞인다.
BROKEN_GLYPHS = "\x00�"

# 원문 표기 차이를 흡수할 문자 치환 (검색 키에만 적용)
_FOLD = {
    "‐": "-", "‑": "-", "‒": "-", "–": "-",
    "—": "-", "―": "-", "−": "-",
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "～": "~", "〜": "~",
}


# 읽지 못한 수식·기호가 있던 자리. 공백으로 바꾸면 원문에 없던 띄어쓰기가
# 생겨 용례 통계가 오염되므로, 공백과 구별되는 표시를 남긴다.
OBJ = "\ufffc"

# clean_text 를 거친 뒤 본문에 남는 '검색 키에서 지울 문자'.
# SQL 쪽 검색 키 생성식(index._key_expr)과 반드시 같은 집합이어야 한다.
STRIPPED_SPACES = (" ", "\n", OBJ)
FOLD_MAP = dict(_FOLD)


def is_pua(ch: str) -> bool:
    """사설 사용 영역(PUA) 문자인가.

    수식·첨자를 전용 글꼴로 찍은 시험지에서 흔하다. 유니코드 매핑이 없어
    글자를 복원할 수 없으므로 검색 대상에서 빼야 한다.
    """
    o = ord(ch)
    return 0xE000 <= o <= 0xF8FF or 0xF0000 <= o <= 0x10FFFD


def count_unreadable(s: str) -> int:
    return sum(1 for ch in s if ch in BROKEN_GLYPHS or is_pua(ch))


def clean_text(s: str) -> str:
    """원문 보존용 정리: 못 읽는 문자를 표시로 바꾸고 공백 폭 정규화.

    수식 글리프(PUA)는 OBJ 표시로 바꾼다. 지우면 앞뒤 글자가 붙어 없던 낱말이
    생기고, 공백으로 바꾸면 없던 띄어쓰기가 용례 통계에 섞인다.
    """
    s = unicodedata.normalize("NFC", s)
    s = "".join(OBJ if is_pua(ch) or ch in BROKEN_GLYPHS else ch for ch in s)
    s = re.sub(f"{OBJ}+", OBJ, s)
    s = s.translate(_INVISIBLE)
    s = s.replace(" ", " ")
    # 줄바꿈은 살리고, 줄 안쪽 연속 공백만 하나로
    lines = [_SPACE_RE.sub(" ", ln).strip() for ln in s.split("\n")]
    return "\n".join(lines)


def _fold_char(ch: str) -> str:
    return _FOLD.get(ch, ch)


def nospace_map(text: str) -> tuple[str, list[int]]:
    """(공백 제거·폴딩된 검색 키, 키의 각 문자가 원문 몇 번째 문자였는지) 반환."""
    buf: list[str] = []
    idx: list[int] = []
    for i, ch in enumerate(text):
        # 공백과 '읽지 못한 자리'는 검색 키에서 뺀다.
        # index._key_expr 의 SQL 식과 결과가 같아야 한다.
        if ch.isspace() or ch == OBJ:
            continue
        folded = _fold_char(unicodedata.normalize("NFC", ch))
        for c in folded:
            buf.append(c)
            idx.append(i)
    return "".join(buf), idx


def nospace(text: str) -> str:
    return nospace_map(text)[0]


def query_key(q: str) -> str:
    """검색어를 저장된 키와 같은 규칙으로 변환."""
    return nospace(unicodedata.normalize("NFC", q))


def find_spans(text: str, query: str) -> list[tuple[int, int]]:
    """띄어쓰기를 무시하고 원문에서 검색어가 나타난 구간(시작, 끝)을 모두 찾는다."""
    key = query_key(query)
    if not key:
        return []
    hay, idx = nospace_map(text)
    spans: list[tuple[int, int]] = []
    start = 0
    while True:
        pos = hay.find(key, start)
        if pos < 0:
            break
        spans.append((idx[pos], idx[pos + len(key) - 1] + 1))
        start = pos + 1
    return spans


def readable(text: str) -> str:
    """사람에게 보여줄 형태. 못 읽은 자리를 눈에 보이는 표시로.

    표시는 □ 를 쓴다. ▯ 같은 기호는 한글 글꼴에 없어 두부(tofu)로 깨진다.
    """
    return text.replace(OBJ, "□")


def surface_forms(text: str, query: str) -> list[str]:
    """검색어가 원문에서 '실제로 어떻게 적혀 있었는지' 표기형들을 뽑는다.

    `빛에너지`로 찾아도 원문이 `빛 에너지`면 그대로 돌려준다.
    띄어쓰기 판례를 세는 데 쓴다.
    """
    return [text[a:b] for a, b in find_spans(text, query)]
