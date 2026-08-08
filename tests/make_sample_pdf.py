"""검증용 모의 시험지 PDF 생성기.

실제 평가원 문제지처럼 '전체폭 표제 + 2단 본문' 구조로 만들어서
단 나누기·문항 분리·출처 추출이 제대로 되는지 확인하는 데 쓴다.
"""

from __future__ import annotations

import os

import pymupdf as fitz

# PyMuPDF 내장 CJK 폰트. ①②③, Ⅰ/Ⅱ, ㉠㉡ 까지 글리프가 있어 시험지 재현에 충분하다.
FONT = "korea"

W, H = 595, 842
MARGIN = 40
GUTTER = 18
COL_W = (W - 2 * MARGIN - GUTTER) / 2


def _write(page, rect, text, size=9.5):
    rc = page.insert_textbox(rect, text, fontname=FONT,
                             fontsize=size, align=0, lineheight=1.45)
    if rc < 0:
        raise RuntimeError(f"텍스트가 넘칩니다 ({rc}): {text[:30]!r}")


def build(path: str, header: list[str], questions: list[str],
          per_col: int = 4) -> None:
    doc = fitz.open()
    page = doc.new_page(width=W, height=H)
    top = MARGIN

    if header:
        head_rect = fitz.Rect(MARGIN, top, W - MARGIN, top + 26 * len(header) + 10)
        _write(page, head_rect, "\n".join(header), size=15)
        top = head_rect.y1 + 14

    col, y = 0, top
    for i, q in enumerate(questions):
        if i and i % per_col == 0:
            col += 1
            if col > 1:
                page = doc.new_page(width=W, height=H)
                col, y = 0, MARGIN
                _write(page, fitz.Rect(MARGIN, 12, W - MARGIN, 30),
                       "생명과학Ⅰ", size=9)
            else:
                y = top
        x0 = MARGIN + col * (COL_W + GUTTER)
        rect = fitz.Rect(x0, y, x0 + COL_W, y + 210)
        _write(page, rect, q)
        y = rect.y1 + 8
    doc.save(path)
    doc.close()


SCIENCE_2014 = [
    "1. 그림은 먹이의 종류나 서식지에 따른 새의 발 모양을 나타낸 것이다.\n"
    "이 자료에 나타난 생명 현상의 특성과 가장 관련이 깊은 것은?\n"
    "① 짚신벌레는 이분법으로 증식한다.\n"
    "② 미모사의 잎을 건드리면 잎이 접힌다.\n"
    "③ 효모는 포도당을 분해하여 에너지를 얻는다.\n"
    "④ 소나무는 빛에너지를 흡수하여 양분을 합성한다.\n"
    "⑤ 사막여우는 귀가 크고 몸집이 작으며, 북극여우는 귀가 작고 몸집이 크다.",

    "2. 다음은 어떤 자극에 대한 반응을 알아보기 위한 실험이다.\n"
    "실험 결과 자극의 세기가 커질수록 반응 시간이 짧아졌다.\n"
    "이에 대한 설명으로 옳은 것만을 고른 것은?",

    "3. 표는 세포 소기관 A~C의 특징을 나타낸 것이다. 미토콘드리아는 유기물을\n"
    "분해하여 생명 활동에 필요한 에너지를 얻는다.",

    "4. 그림 (가)와 (나)는 각각 동물 A(2n=6)와 B의 어떤 세포에 들어 있는 모든\n"
    "염색체를 모식적으로 나타낸 것이다. A와 B의 성염색체는 XY이다.\n"
    "ㄱ. ㉠은 성염색체이다.\n"
    "ㄴ. ㉡은 ㉢의 상동 염색체이다.",

    "5. 광합성 색소는 빛에너지를 흡수한다. 이에 대한 설명으로 옳은 것은?",

    "6. 다음은 사람의 유전 형질에 대한 자료이다. 돌연변이는 고려하지 않는다.",

    "7. 그림은 사람의 혈당량 조절 과정을 나타낸 것이다. 인슐린과 글루카곤의\n"
    "작용을 옳게 설명한 것은?",

    "8. 표는 생태계를 구성하는 요소 사이의 관계를 나타낸 것이다.",
]

SCIENCE_2026 = [
    "1. 다음은 광합성에 대한 설명이다. 엽록체는 빛 에너지를 화학 에너지로\n"
    "전환하여 양분을 합성한다.",

    "2. 그림은 사람의 신경계 구조를 나타낸 것이다. 이에 대한 설명으로 옳은\n"
    "것만을 <보기>에서 있는 대로 고른 것은?",

    "3. 다음은 세포 호흡에 대한 자료이다. 세포는 포도당을 분해하여 에너지를\n"
    "얻으며 이 과정에서 빛 에너지는 관여하지 않는다.",

    "4. 표는 어떤 집단의 대립유전자 빈도를 나타낸 것이다.",

    "5. 그림은 항원 항체 반응을 나타낸 것이다.",

    "6. 다음은 개체군의 생장 곡선에 대한 자료이다.",
]

KOREAN_2025 = [
    "[1~3] 다음 글을 읽고 물음에 답하시오.\n"
    "인간은 언어를 통해 세계를 인식한다. 언어가 사고를 규정한다는 견해와\n"
    "사고가 언어에 앞선다는 견해가 오랫동안 맞서 왔다.",

    "1. 윗글의 내용과 일치하지 않는 것은?",
    "2. 윗글을 바탕으로 <보기>를 이해한 내용으로 적절하지 않은 것은?",
    "3. ㉠에 대한 설명으로 가장 적절한 것은?",
    "4. 다음 중 띄어쓰기가 옳은 것은?",
    "5. <보기>의 밑줄 친 부분과 같은 의미로 쓰인 것은?",
]


def build_all(outdir: str) -> list[str]:
    os.makedirs(outdir, exist_ok=True)
    made = []

    p = os.path.join(outdir, "2014_수능_생명과학1.pdf")
    build(p, ["2014학년도 대학수학능력시험 문제지",
              "제4교시 과학탐구 영역 (생명 과학Ⅰ)"], SCIENCE_2014)
    made.append(p)

    p = os.path.join(outdir, "2026_6월모평_생명과학1.pdf")
    build(p, ["2026학년도 대학수학능력시험 6월 모의평가 문제지",
              "제4교시 과학탐구 영역 (생명과학Ⅰ)"], SCIENCE_2026)
    made.append(p)

    p = os.path.join(outdir, "2025_9월모평_국어.pdf")
    build(p, ["2025학년도 대학수학능력시험 9월 모의평가 문제지",
              "제1교시 국어 영역"], KOREAN_2025)
    made.append(p)

    return made


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "samples"
    for f in build_all(target):
        print("생성:", f)
