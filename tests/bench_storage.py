"""색인 용량·검색 속도 실측.

"모의고사가 쌓이면 용량이 걱정된다"에 숫자로 답하기 위한 스크립트.
PDF 원본을 빼고 '추출된 텍스트 + 검색 색인'만 쌓았을 때 얼마나 커지는지 잰다.
"""

from __future__ import annotations

import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gichul import index as idx           # noqa: E402
from gichul.meta import ExamMeta          # noqa: E402
from gichul.segment import Segment        # noqa: E402

SENTENCES = [
    "그림은 어떤 동물의 세포 분열 과정을 나타낸 것이다.",
    "이에 대한 설명으로 옳은 것만을 <보기>에서 있는 대로 고른 것은?",
    "표는 세 가지 물질의 특징을 비교하여 나타낸 것이다.",
    "소나무는 빛에너지를 흡수하여 양분을 합성한다.",
    "엽록체는 빛 에너지를 화학 에너지로 전환한다.",
    "다음은 유전 형질에 대한 자료이다. 돌연변이는 고려하지 않는다.",
    "학생 A의 실험 결과를 바탕으로 추론한 내용으로 가장 적절한 것은?",
    "윗글의 내용과 일치하지 않는 것은? 3점",
    "㉠에 대한 설명으로 가장 적절한 것을 고르시오.",
    "자극의 세기가 커질수록 반응의 크기는 어떻게 달라지는가?",
]
SUBJECTS = ["국어", "수학", "영어", "생명과학I", "지구과학I", "화학I",
            "물리학I", "사회문화", "생활과윤리", "한국사"]
EXAMS = ["수능", "6월 모평", "9월 모평", "3월 학평", "10월 학평"]


def synth_question(rng: random.Random, n: int, chars: int) -> Segment:
    body: list[str] = [f"{n}. "]
    size = 0
    while size < chars:
        s = rng.choice(SENTENCES)
        body.append(s)
        size += len(s)
    body += [f"{c} {rng.choice(SENTENCES)[:24]}" for c in "①②③④⑤"]
    return Segment("question", n, n, 1 + n // 4, ["\n".join(body)])


def run(n_exams: int, q_per_exam: int, chars_per_q: int, db_path: str) -> None:
    if os.path.exists(db_path):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(db_path + suffix)
            except FileNotFoundError:
                pass

    rng = random.Random(42)
    conn = idx.connect(db_path)
    t0 = time.time()
    total_chars = 0
    for i in range(n_exams):
        segs = [synth_question(rng, n, chars_per_q) for n in range(1, q_per_exam + 1)]
        total_chars += sum(len(s.text) for s in segs)
        meta = ExamMeta(year=2015 + i % 12, exam=EXAMS[i % len(EXAMS)],
                        subject=SUBJECTS[i % len(SUBJECTS)])
        idx.add_exam(conn, sha1=f"synthetic-{i:06d}", path=f"/x/{i}.pdf", meta=meta,
                     segments=segs, n_pages=max(1, q_per_exam // 4), scanned_pages=[])
    build_s = time.time() - t0

    conn.execute("VACUUM")
    conn.commit()
    size = os.path.getsize(db_path)

    print(f"시험지 {n_exams}개 × 문항 {q_per_exam}개 × 문항당 {chars_per_q}자")
    print(f"  원문 텍스트 총량   : {total_chars/1e6:.2f} M자 "
          f"(UTF-8 {total_chars*3/2**20:.1f} MiB)")
    print(f"  색인 DB 크기       : {size/2**20:.1f} MiB "
          f"(시험지 1개당 {size/n_exams/1024:.0f} KiB)")
    print(f"  색인 시간          : {build_s:.1f}s")

    for q, label in [("빛에너지", "띄어쓰기 무시 3글자"),
                     ("돌연변이는 고려하지 않는다", "긴 구절"),
                     ("㉠", "1글자(LIKE 우회)")]:
        t = time.time()
        hits = idx.search(conn, q, limit=50)
        print(f"  검색 '{q}' ({label}): {len(hits)}건 / {(time.time()-t)*1000:.0f} ms")
    conn.close()


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else "/tmp/gichul_bench.db"
    print("── 탐구 과목 규모 (문항 20개 / 문항당 300자)")
    run(500, 20, 300, db)
    print("\n── 국어·영어 포함 큰 시험지 (문항 45개 / 문항당 600자)")
    run(500, 45, 600, db)
