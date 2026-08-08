"""전 과정 테스트. pytest 없이도 돌아간다.

  python3 tests/test_pipeline.py
  pytest tests/test_pipeline.py
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gichul import index as idx                              # noqa: E402
from gichul.archive import export_jsonl, import_jsonl        # noqa: E402
from gichul.extract import extract                           # noqa: E402
from gichul.meta import canon_subject, from_filename, from_text, subject_aliases  # noqa: E402
from gichul.normalize import clean_text, find_spans, is_pua, surface_forms  # noqa: E402
from gichul.pipeline import ingest_paths                     # noqa: E402
from gichul.segment import segment                           # noqa: E402

from make_sample_pdf import build_all                        # noqa: E402


# ---------------------------------------------------------------- 표기 정규화

def test_spacing_insensitive_search():
    assert surface_forms("소나무는 빛에너지를 흡수", "빛에너지") == ["빛에너지"]
    assert surface_forms("엽록체는 빛 에너지를 흡수", "빛에너지") == ["빛 에너지"]
    assert surface_forms("빛에너지 그리고 빛 에너지", "빛 에너지") == \
        ["빛에너지", "빛 에너지"]
    assert find_spans("상호 작용은 상리 공생", "상리공생") == [(7, 12)]


def test_spans_point_at_original_text():
    text = "소나무는 빛 에너지를 흡수한다"
    (a, b), = find_spans(text, "빛에너지")
    assert text[a:b] == "빛 에너지"


def test_pua_becomes_space_not_join():
    glyph = "\ue035"                  # 수식용 사설 영역 문자
    assert is_pua(glyph) and not is_pua("가")
    # 그냥 지우면 '질량결손'이라는 없던 낱말이 생긴다. 공백이 되어야 한다.
    cleaned = clean_text(f"질량{glyph}결손")
    assert cleaned == "질량\ufffc결손"            # 공백이 아니라 별도 표시
    # 검색은 여전히 걸리지만, 표기형에 '읽지 못한 자리'가 남아 통계에서 걸러진다
    assert surface_forms(cleaned, "질량결손") == ["질량\ufffc결손"]


def test_sql_and_python_keys_agree():
    """SQL 생성 열과 파이썬 정규화가 어긋나면 검색이 조용히 누락된다."""
    import sqlite3
    from gichul.index import _key_expr
    from gichul.normalize import nospace

    conn = sqlite3.connect(":memory:")
    for raw in ["질량\ue035결손", "빛 에너지", "옳은 것만\n을", "가~나 (다)",
                "‘인용’ –줄표", "A\u00a0B"]:
        text = clean_text(raw)
        sql = conn.execute("SELECT " + _key_expr("?"), (text,)).fetchone()[0]
        assert sql == nospace(text), (raw, sql, nospace(text))


def test_no_match_for_empty_or_missing():
    assert find_spans("아무 글", "") == []
    assert find_spans("아무 글", "없는말") == []


# ---------------------------------------------------------------- 메타데이터

def test_canon_subject():
    for raw in ("생명 과학Ⅰ", "생명과학1", "생명과학 I", "생명과학Ⅰ"):
        assert canon_subject(raw) == "생명과학I", raw
    assert canon_subject("물리학Ⅱ") == "물리학II"
    assert "생명과학1" in subject_aliases("생명과학Ⅰ")


def test_meta_from_suneung_cover():
    m = from_text("2014학년도 대학수학능력시험 문제지\n제4교시 과학탐구 영역 (생명 과학Ⅰ)")
    assert (m.year, m.exam, m.subject) == (2014, "수능", "생명과학I")


def test_meta_from_hakpyeong_header():
    """학력평가는 표지가 아니라 중간 페이지 머리글에 정보가 있다."""
    m = from_text("① ㄱ ② ㄴ\n2026학년도 7월 고3 전국연합학력평가 문제지\n"
                  "제4 교시\n과학탐구영역(물리학Ⅰ)")
    assert (m.year, m.exam, m.grade, m.subject) == (2026, "7월 학평", "고3", "물리학I")


def test_math_type_becomes_part_of_subject():
    """`수학 영역 (가형)` 은 괄호 안이 과목이 아니라 시험지 유형이다.

    가형과 나형은 문항이 다르므로 한 과목으로 묶으면 용례가 섞인다.
    """
    for text, want in [
        ("2017학년도 대학수학능력시험\n제2교시 수학 영역 (가형)", "수학가형"),
        ("2014학년도 대학수학능력시험\n제2교시 수학 영역 (A형)", "수학A형"),
    ]:
        assert from_text(text).subject == want, text


def test_subjects_across_all_areas():
    """국어·영어·사탐·과탐·고1 과목까지 표지에서 갈려야 한다."""
    cases = [
        ("2022학년도 수능\n제1교시 국어 영역 (언어와 매체)", "언어와매체"),
        ("2026학년도 6월 모의평가\n제3교시 영어 영역", "영어"),
        ("2025학년도 수능\n제4교시 사회탐구 영역 (생활과 윤리)", "생활과윤리"),
        ("2020학년도 수능\n제4교시 사회탐구 영역 (사회·문화)", "사회문화"),
        ("2026학년도 3월 고1 전국연합학력평가\n제4교시 통합사회 영역", "통합사회"),
    ]
    for text, want in cases:
        assert from_text(text).subject == want, text
    # 가운뎃점 표기는 같은 과목으로 묶여야 한다
    assert canon_subject("사회·문화") == canon_subject("사회문화")


def test_meta_umbrella_not_used_as_subject():
    m = from_text("제4 교시 과학탐구영역")
    assert m.subject != "과학탐구"


def test_meta_from_filename():
    m = from_filename("2026_6월모평_생명과학1.pdf")
    assert (m.year, m.exam, m.subject) == (2026, "6월 모평", "생명과학I")


# ---------------------------------------------------------------- 추출·분할

def _sample_dir(tmp: str) -> list[str]:
    return build_all(os.path.join(tmp, "samples"))


def test_two_column_reading_order(tmp_path_str=None):
    with tempfile.TemporaryDirectory() as tmp:
        science = _sample_dir(tmp)[0]
        ex = extract(science)
        segs = segment(ex.lines)
        numbers = [s.number for s in segs if s.kind == "question"]
        assert numbers == list(range(1, 9)), numbers
        # 1번 문항이 통째로 붙어 있어야 한다 (좌우 단이 섞이면 깨진다).
        # 줄바꿈이 낱말 가운데를 지나므로 띄어쓰기 무시 검색으로 확인한다.
        first = next(s for s in segs if s.number == 1)
        assert find_spans(first.text, "새의발모양") and "북극여우" in first.text


def test_passage_segment_detected():
    with tempfile.TemporaryDirectory() as tmp:
        korean = _sample_dir(tmp)[2]
        segs = segment(extract(korean).lines)
        passage = [s for s in segs if s.kind == "passage"]
        assert len(passage) == 1
        assert passage[0].number == 1 and passage[0].number_end == 3
        assert passage[0].label == "1~3번 지문"


def test_question_rects_cover_page_area():
    with tempfile.TemporaryDirectory() as tmp:
        segs = segment(extract(_sample_dir(tmp)[0]).lines)
        q1 = next(s for s in segs if s.number == 1)
        rects = q1.rects()
        assert rects and all(x1 > x0 and y1 > y0 for _p, x0, y0, x1, y1 in rects)


# ---------------------------------------------------------------- 색인·검색

def _indexed(tmp: str):
    conn = idx.connect(os.path.join(tmp, "t.db"))
    ingest_paths(conn, [os.path.join(tmp, "samples")])
    return conn


def test_search_reports_source_and_spacing_variants():
    with tempfile.TemporaryDirectory() as tmp:
        _sample_dir(tmp)
        conn = _indexed(tmp)
        hits = idx.search(conn, "빛에너지")
        sources = {h.source for h in hits}
        assert "2014학년도 수능 · 생명과학I · 1번" in sources
        assert "2026학년도 6월 모평 · 생명과학I · 1번" in sources

        forms, _amb = idx.variants(hits)
        assert dict((f, c) for f, c, _w in forms) == {"빛에너지": 2, "빛 에너지": 2}


def test_subject_filter_accepts_aliases():
    with tempfile.TemporaryDirectory() as tmp:
        _sample_dir(tmp)
        conn = _indexed(tmp)
        for alias in ("생명과학I", "생명과학1", "생명과학Ⅰ"):
            assert idx.search(conn, "에너지", subject=alias), alias
        assert not idx.search(conn, "빛에너지", subject="국어")


def test_short_query_falls_back_to_scan():
    with tempfile.TemporaryDirectory() as tmp:
        _sample_dir(tmp)
        conn = _indexed(tmp)
        assert idx.search(conn, "언어")          # 2글자 = trigram 색인 못 씀


def test_linebreak_occurrences_excluded_from_variants():
    with tempfile.TemporaryDirectory() as tmp:
        _sample_dir(tmp)
        conn = _indexed(tmp)
        conn.execute("INSERT INTO segments(exam_id, kind, number, number_end, page, text)"
                     " SELECT id, 'question', 99, 99, 1, '옳은 것만\n을 고른' FROM exams LIMIT 1")
        conn.commit()
        hits = idx.search(conn, "옳은것만을")
        forms, ambiguous = idx.variants(hits)
        assert ambiguous >= 1
        assert not any("것만 을" in f for f, _c, _w in forms)


def test_compare_ranks_by_frequency():
    with tempfile.TemporaryDirectory() as tmp:
        _sample_dir(tmp)
        conn = _indexed(tmp)
        rows = idx.compare(conn, ["빛에너지", "없는표현입니다"])
        assert rows[0][0] == "빛에너지" and rows[0][2] == 4
        assert rows[-1][2] == 0


def test_reingest_is_idempotent():
    with tempfile.TemporaryDirectory() as tmp:
        _sample_dir(tmp)
        conn = _indexed(tmp)
        before = idx.stats(conn)
        ingest_paths(conn, [os.path.join(tmp, "samples")])
        assert idx.stats(conn) == before


# ---------------------------------------------------------------- 데이터 파일

def test_jsonl_round_trip_without_pdfs():
    with tempfile.TemporaryDirectory() as tmp:
        _sample_dir(tmp)
        conn = _indexed(tmp)
        out = os.path.join(tmp, "backup.jsonl.gz")
        assert export_jsonl(conn, out) == 3

        conn2 = idx.connect(os.path.join(tmp, "restored.db"))
        assert import_jsonl(conn2, out)["added"] == 3
        assert idx.stats(conn2) == idx.stats(conn)
        assert idx.search(conn2, "빛에너지")


# ---------------------------------------------------------------- 자립형 HTML

def test_standalone_html_embeds_and_filters():
    from gichul.standalone import build
    with tempfile.TemporaryDirectory() as tmp:
        _sample_dir(tmp)
        conn = _indexed(tmp)

        out = os.path.join(tmp, "all.html")
        r = build(conn, out)
        assert r["questions"] == 19 and r["images"]
        page = open(out, encoding="utf-8").read()
        assert "data:image/jpeg;base64," in page
        assert "빛에너지" in page and "window.GICHUL=" in page

        # 과목 필터
        r = build(conn, os.path.join(tmp, "ko.html"), subject="국어")
        assert r["questions"] == 5 and r["papers"] == 1

        # 문항이 많아지면 이미지를 빼고 텍스트만 담는다
        r = build(conn, os.path.join(tmp, "slim.html"), max_mb=0.0001)
        assert r["questions"] == 19 and not r["images"] and r["image_bytes"] == 0
        assert "data:image/jpeg" not in open(
            os.path.join(tmp, "slim.html"), encoding="utf-8").read()


# ---------------------------------------------------------------- 이미지

def test_render_segment_returns_png():
    from gichul.render import render_segment, segment_parts
    with tempfile.TemporaryDirectory() as tmp:
        _sample_dir(tmp)
        conn = _indexed(tmp)
        hit = idx.search(conn, "빛에너지")[0]
        row = idx.get_segment(conn, hit.segment_id)
        assert segment_parts(row) >= 1
        png = render_segment(row, 0)
        assert png[:8] == b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------- 폴더 감시

def test_watch_once_indexes_new_files():
    from gichul.watch import watch
    with tempfile.TemporaryDirectory() as tmp:
        _sample_dir(tmp)
        db = os.path.join(tmp, "w.db")
        watch(os.path.join(tmp, "samples"), db, once=True)
        conn = idx.connect(db)
        assert idx.stats(conn)["exams"] == 3


def main() -> int:
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ok   {name}")
        except Exception as exc:                    # noqa: BLE001
            failed += 1
            print(f"  FAIL {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} 통과")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
