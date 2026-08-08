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
    s = re.sub(r"[·‧・･]", "", s)
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
    t = unicodedata.normalize("NFC", name)
    t = re.sub(r"\.pdf$", "", t, flags=re.I)
    t = t.replace("_", " ").replace("-", " ")
    meta = ExamMeta()

    m = _YEAR.search(t) or _YEAR_LOOSE.search(t)
    if m:
        meta.year = int(m.group(0)[:4])

    meta.exam, _ = _detect_exam(t)
    if meta.exam is None:
        if "모평" in t:
            mm = _MONTH.search(t)
            meta.exam = f"{int(mm.group(1))}월 모평" if mm else "모의평가"
        elif "학평" in t:
            mm = _MONTH.search(t)
            meta.exam = f"{int(mm.group(1))}월 학평" if mm else "학력평가"

    g = _GRADE.search(t)
    if g:
        meta.grade = f"고{g.group(1)}"

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
