"""시험지 표지/파일명에서 출처 메타데이터를 뽑는다.

목표 출력: "2014학년도 수능 · 생명과학I · 14번" 처럼 사람이 바로 알아보는 출처.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_ROMAN = {"Ⅰ": "I", "Ⅱ": "II", "Ⅲ": "III", "Ⅳ": "IV", "ⅰ": "I", "ⅱ": "II"}

# 과목명 어간: 뒤에 1/2/Ⅰ/Ⅱ가 붙는 것들
_NUMBERED_STEMS = ("물리학", "화학", "생명과학", "지구과학", "수학", "물리", "생물", "지구")

KNOWN_SUBJECTS = [
    # 국어
    "국어", "화법과작문", "언어와매체", "화법과언어", "독서와작문", "독서", "문학",
    # 수학 (가/나형·A/B형은 아래 _TYPE_SUFFIX 로 붙는다)
    "수학", "수학I", "수학II", "미적분", "확률과통계", "기하", "미적분II",
    # 영어·한국사
    "영어", "영어I", "영어II", "영어독해와작문", "한국사",
    # 사회탐구
    "생활과윤리", "윤리와사상", "한국지리", "세계지리", "동아시아사", "세계사",
    "경제", "정치와법", "법과정치", "사회문화", "사회·문화", "통합사회",
    # 과학탐구
    "물리학I", "물리학II", "화학I", "화학II",
    "생명과학I", "생명과학II", "지구과학I", "지구과학II",
    "물리I", "물리II", "생물I", "생물II", "지구과학", "통합과학",
]

# "수학 영역 (가형)", "수학 영역(A형)" 처럼 과목 뒤에 붙는 유형 표기.
# 2021학년도까지의 수학·영어에 쓰였고, 서로 다른 시험지이므로 과목을 갈라야 한다.
_TYPE_SUFFIX = re.compile(r"^([가나ABＡＢ])\s*형$")

# 개별 과목이 아니라 시험 묶음 이름. 이게 잡히면 실제 과목을 더 찾아야 한다.
UMBRELLA = {"과학탐구", "사회탐구", "직업탐구", "탐구", "제2외국어", "한문"}

# 파일명에서 자주 쓰는 과목 약어. 자리 규칙(`연도_시험_과목`)의 세 번째
# 칸에서만 풀어 쓴다 — 본문에서 풀면 오탐이 난다.
SUBJECT_ABBREV = {
    "화작": "화법과작문", "언매": "언어와매체",
    "확통": "확률과통계", "미적": "미적분",
    "생윤": "생활과윤리", "윤사": "윤리와사상", "사문": "사회문화",
    "정법": "정치와법", "동사": "동아시아사", "세사": "세계사",
    "한지": "한국지리", "세지": "세계지리",
    "물1": "물리학I", "물2": "물리학II", "화1": "화학I", "화2": "화학II",
    "생1": "생명과학I", "생2": "생명과학II", "지1": "지구과학I", "지2": "지구과학II",
    "통사": "통합사회", "통과": "통합과학",
}

# 과목 칸에 올 수 없는 토큰: 학년, 판형, 문서 종류 표기
_NOT_SUBJECT = re.compile(
    r"^(고[1-3]|[0-9]+|[AB]형?|홀수형?|짝수형?|최종본?|문제지?|문항|해설지?|"
    r"정답표?|답지|본문|배포용?)$")


def _positional_subject(parts: list[str]) -> tuple[str | None, bool]:
    """`연도_시험_과목` 규칙: 셋째 칸부터 과목을 찾는다.

    아는 과목명·약어가 있으면 그것을, 없으면 학년·판형 등을 뺀 첫 토큰을
    과목으로 믿는다. 어느 쪽이든 사용자가 자리로 지정한 것이므로 확정이다.
    반환: (과목, 자리 규칙으로 지정되었는가)
    """
    if len(parts) < 3:
        return None, False
    candidates = [t.strip() for t in parts[2:] if t.strip()]
    for tok in candidates:
        c = canon_subject(SUBJECT_ABBREV.get(tok, tok))
        if c and (c in KNOWN_SUBJECTS or c in _ORDER):
            return c, True
    for tok in candidates:
        if _NOT_SUBJECT.match(tok):
            continue
        if "수능" in tok or "모평" in tok or "학평" in tok or "모의" in tok:
            continue
        c = canon_subject(tok)
        if c in UMBRELLA:                  # `과학탐구` 는 묶음 이름이지 과목이 아니다
            continue
        if c and 2 <= len(c) <= 12:
            return c, True
    return None, False


# 수능 시간표 순서: 국어 → 수학 → 영어 → 한국사 → 사탐 → 과탐 → 그 밖.
# 과목 목록·칩을 이 순서로 늘어놓는다.
_ORDER_GROUPS = [
    ["국어", "화법과작문", "언어와매체", "화법과언어", "독서와작문", "독서", "문학"],
    ["수학", "수학I", "수학II", "미적분", "확률과통계", "기하",
     "수학가형", "수학나형", "수학A형", "수학B형", "미적분II"],
    ["영어", "영어I", "영어II", "영어독해와작문"],
    ["한국사"],
    ["통합사회", "생활과윤리", "윤리와사상", "한국지리", "세계지리",
     "동아시아사", "세계사", "경제", "정치와법", "법과정치", "사회문화"],
    ["통합과학", "물리학I", "물리학II", "화학I", "화학II",
     "생명과학I", "생명과학II", "지구과학I", "지구과학II",
     "물리I", "물리II", "생물I", "생물II", "지구과학"],
]
_ORDER = {name: (g, i) for g, group in enumerate(_ORDER_GROUPS)
          for i, name in enumerate(group)}


def subject_sort_key(subject: str | None) -> tuple:
    g, i = _ORDER.get(subject or "", (len(_ORDER_GROUPS), 0))
    return (g, i, subject or "")


@dataclass
class ExamMeta:
    year: int | None = None        # 학년도
    exam: str | None = None        # 수능 / 6월 모평 / 9월 모평 / 3월 학평 ...
    grade: str | None = None       # 고1 / 고2 / 고3
    subject: str | None = None
    subject_raw: str | None = None
    # 파일명이 `연도_시험_과목` 규칙을 따라 과목을 지정했는가.
    # 참이면 이 과목이 표지 판독보다 우선한다 — 표지를 잘못 읽었을 때
    # 사용자가 파일명으로 바로잡는 길이다.
    explicit: bool = False

    def source_label(self, question_label: str) -> str:
        head = []
        if self.year:
            head.append(f"{self.year}학년도")
        if self.grade and self.exam and "학평" in self.exam:
            head.append(f"{self.grade} {self.exam}")
        elif self.exam:
            head.append(self.exam)
        parts = [" ".join(head) or "출처미상"]
        if self.subject:
            parts.append(self.subject)
        parts.append(question_label)
        return " · ".join(p for p in parts if p)


def canon_subject(s: str | None) -> str | None:
    """`생명 과학Ⅰ`, `생명과학1`, `생명과학 I` -> `생명과학I`."""
    if not s:
        return None
    s = unicodedata.normalize("NFC", s)
    s = "".join(_ROMAN.get(ch, ch) for ch in s)
    s = re.sub(r"\s+", "", s).strip("()[]<>")
    # `사회·문화` 와 `사회문화` 는 같은 과목이다. 가운뎃점 표기를 없앤다.
    # 파일명에는 가운뎃점 대신 마침표를 쓰기도 한다 (`사회.문화`).
    s = re.sub(r"[·‧・･.．]", "", s)
    s = s.replace("영역", "").replace("과목", "")
    for stem in _NUMBERED_STEMS:
        m = re.fullmatch(rf"{stem}\s*([12])", s)
        if m:
            return stem + ("I" if m.group(1) == "1" else "II")
    return s or None


def subject_aliases(s: str) -> set[str]:
    """사용자가 어떻게 치든 같은 과목으로 보게 만드는 후보들."""
    c = canon_subject(s) or ""
    out = {c}
    out.add(c.replace("II", "2").replace("I", "1"))
    out.add(c.replace("II", "Ⅱ").replace("I", "Ⅰ"))
    return {x for x in out if x}


_YEAR = re.compile(r"(19|20)(\d{2})\s*학년도")
_YEAR_LOOSE = re.compile(r"(?<!\d)(19|20)(\d{2})(?!\d)")
_MONTH = re.compile(r"(\d{1,2})\s*월")
_GRADE = re.compile(r"고\s*([123])")


def _detect_exam(text: str) -> tuple[str | None, str | None]:
    if "전국연합학력평가" in text or "학력평가" in text:
        m = _MONTH.search(text)
        return (f"{int(m.group(1))}월 학평" if m else "학력평가"), None
    if "모의평가" in text:
        m = _MONTH.search(text)
        return (f"{int(m.group(1))}월 모평" if m else "모의평가"), None
    if "대학수학능력시험" in text or "수능" in text:
        return "수능", None
    return None, None


def from_text(front_text: str) -> ExamMeta:
    """표지(첫 문항 이전) 텍스트에서 메타데이터 추출."""
    t = unicodedata.normalize("NFC", front_text)
    meta = ExamMeta()

    m = _YEAR.search(t)
    if m:
        meta.year = int(m.group(0)[:4])

    meta.exam, _ = _detect_exam(t)

    g = _GRADE.search(t)
    if g:
        meta.grade = f"고{g.group(1)}"

    # "제4교시 과학탐구영역(물리학Ⅰ)" -> 괄호 안이 실제 선택과목
    m = re.search(r"([가-힣A-Za-zⅠ-Ⅻ]{2,10})\s*영역\s*[(（]([^)）]{1,20})[)）]", t)
    if m:
        area, inner = m.group(1).strip(), m.group(2).strip()
        suffix = _TYPE_SUFFIX.match(re.sub(r"\s+", "", inner))
        # "수학 영역 (가형)" 은 괄호 안이 과목이 아니라 시험지 유형이다.
        # 가형과 나형은 다른 시험지이므로 영역명에 붙여 과목을 가른다.
        meta.subject_raw = f"{area}{suffix.group(1)}형" if suffix else inner
    else:
        # "제1교시 국어 영역" -> 교시 표기를 걷어내고 '영역' 앞의 말만
        m = re.search(r"(?:제\s*\d+\s*교시)?\s*([가-힣A-Za-zⅠ-Ⅻ]{2,10})\s*영역", t)
        if m:
            meta.subject_raw = m.group(1).strip()

    # '과학탐구영역'처럼 묶음 이름만 잡혔으면 실제 과목명을 다시 찾는다
    if canon_subject(meta.subject_raw) in UMBRELLA:
        meta.subject_raw = None

    if not meta.subject_raw:
        flat = re.sub(r"\s+", "", t)
        flat = "".join(_ROMAN.get(ch, ch) for ch in flat)
        for cand in sorted(KNOWN_SUBJECTS, key=len, reverse=True):
            if cand in flat:
                meta.subject_raw = cand
                break

    meta.subject = canon_subject(meta.subject_raw)
    return meta


def from_filename(name: str) -> ExamMeta:
    raw = re.sub(r"\.pdf$", "", unicodedata.normalize("NFC", name), flags=re.I)
    parts = [p for p in re.split(r"[_\-]", raw)]
    t = raw.replace("_", " ").replace("-", " ")
    meta = ExamMeta()

    m = _YEAR.search(t) or _YEAR_LOOSE.search(t)
    if m:
        meta.year = int(m.group(0)[:4])

    meta.exam, _ = _detect_exam(t)
    if meta.exam is None:
        # `6모`, `9모평`, `3학평` 같은 축약도 파일명에서는 흔하다
        mm = re.search(r"(?<![0-9])(\d{1,2})\s*(?:월)?\s*(모평?|학평)(?![가-힣])", t)
        if mm:
            kind = "모평" if mm.group(2).startswith("모") else "학평"
            meta.exam = f"{int(mm.group(1))}월 {kind}"
        elif "모평" in t or "모의" in t:
            meta.exam = "모의평가"
        elif "학평" in t or "학력" in t:
            meta.exam = "학력평가"
        else:
            # `2025_9월_경제` 처럼 달만 적은 이름. 평가원 기출에서 6·9월은
            # 모평뿐이다. (3·7월 같은 학평 달은 넘겨짚지 않는다.)
            mb = re.search(r"(?<![0-9])([69])\s*월(?![가-힣0-9])", t)
            if mb:
                meta.exam = f"{mb.group(1)}월 모평"

    g = _GRADE.search(t)
    if g:
        meta.grade = f"고{g.group(1)}"

    # `연도_시험_과목` 자리 규칙이 먼저다. 사용자가 자리로 지정한 과목은
    # 표지를 잘못 읽었을 때 바로잡는 수단이므로 확정으로 본다.
    subject, explicit = _positional_subject(parts)
    if subject:
        meta.subject, meta.subject_raw, meta.explicit = subject, subject, explicit
        return meta

    flat = "".join(_ROMAN.get(ch, ch) for ch in re.sub(r"\s+", "", t))
    for cand in sorted(KNOWN_SUBJECTS, key=len, reverse=True):
        if cand in flat or cand.replace("II", "2").replace("I", "1") in flat:
            meta.subject_raw = cand
            break
    meta.subject = canon_subject(meta.subject_raw)
    return meta


def merge(*metas: ExamMeta) -> ExamMeta:
    """앞쪽 인자가 우선. (CLI 지정 > 표지 > 파일명)"""
    out = ExamMeta()
    for field_name in ("year", "exam", "grade", "subject", "subject_raw"):
        for m in metas:
            v = getattr(m, field_name)
            if v:
                setattr(out, field_name, v)
                break
    return out
