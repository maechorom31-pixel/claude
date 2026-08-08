"""명령줄 인터페이스.

  python -m gichul ingest ./pdfs
  python -m gichul search 빛에너지 --subject 생명과학1
  python -m gichul variants "빛에너지"
  python -m gichul subjects
  python -m gichul web
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import index as idx
from .meta import ExamMeta, canon_subject
from .normalize import readable
from .pipeline import ingest_paths


def _overrides(a: argparse.Namespace) -> ExamMeta:
    return ExamMeta(year=a.year, exam=a.exam, grade=a.grade,
                    subject=canon_subject(a.subject), subject_raw=a.subject)


def cmd_ingest(a: argparse.Namespace) -> int:
    conn = idx.connect(a.db)
    results = ingest_paths(conn, a.paths, overrides=_overrides(a), force=a.force)
    if not results:
        print("PDF를 찾지 못했습니다.")
        return 1
    ok = 0
    for r in results:
        name = r.path.rsplit("/", 1)[-1]
        if r.status == "failed":
            print(f"  ✗ {name}: {r.error}")
            continue
        if r.status == "skipped":
            print(f"  – {name}: 이미 색인됨 (--force 로 재색인)")
            continue
        ok += 1
        src = r.meta.source_label("").rstrip(" ·") if r.meta else "출처미상"
        print(f"  ✓ {name}: {src} / {r.n_pages}쪽 / 문항 {r.n_questions}개")
        for w in r.warnings or []:
            print(f"      ! {w}")
    s = idx.stats(conn)
    print(f"\n색인 상태: 시험지 {s['exams']}개 · {s['pages']}쪽 · 문항 {s['questions']}개")
    return 0 if ok or any(r.status == "skipped" for r in results) else 1


def cmd_search(a: argparse.Namespace) -> int:
    conn = idx.connect(a.db)
    hits = idx.search(conn, a.query, subject=a.subject, year=a.year,
                      exam=a.exam, limit=a.limit)
    if a.json:
        print(json.dumps([{
            "segment_id": h.segment_id,
            "source": h.source, "subject": h.subject, "year": h.year,
            "page": h.page, "file": h.filename,
            "matches": [h.text[x:y] for x, y in h.spans],
            "snippet": h.snippet(),
        } for h in hits], ensure_ascii=False, indent=2))
        return 0

    if not hits:
        print(f"'{a.query}' 검색 결과 없음.")
        return 1

    forms, ambiguous = idx.variants(hits)
    total = sum(c for _f, c, _w in forms)
    print(f"'{a.query}' — {len(hits)}개 문항 / {total}회 등장\n")
    if len(forms) > 1:
        print("표기 분포 (띄어쓰기·부호 차이):")
        for form, cnt, _w in forms:
            print(f"  {cnt:4d}회  {form!r}")
        if ambiguous:
            print(f"  {ambiguous:4d}회  (줄바꿈에 걸려 판정 불가)")
        print()
    for h in hits:
        print(f"■ {h.source}   [p.{h.page} · {h.filename}]")
        print(f"   {h.snippet(a.width)}\n")
    return 0


def cmd_variants(a: argparse.Namespace) -> int:
    conn = idx.connect(a.db)
    hits = idx.search(conn, a.query, subject=a.subject, year=a.year,
                      exam=a.exam, limit=10_000)
    forms, ambiguous = idx.variants(hits)
    if not forms:
        print(f"'{a.query}' 용례 없음."
              + (f" (줄바꿈에 걸린 {ambiguous}건은 판정 불가)" if ambiguous else ""))
        return 1
    total = sum(c for _f, c, _w in forms)
    print(f"'{a.query}' 표기 용례 — 총 {total}회\n")
    for form, cnt, where in forms:
        pct = cnt * 100 / total
        print(f"  {form!r}  —  {cnt}회 ({pct:.0f}%)")
        for w in where:
            print(f"        예) {w}")
    if ambiguous:
        print(f"\n  (줄바꿈에 걸려 띄어쓰기를 판정할 수 없는 {ambiguous}건은 제외)")
    if len(forms) > 1:
        print(f"\n→ 우세 표기: {forms[0][0]!r}")
    return 0


def cmd_compare(a: argparse.Namespace) -> int:
    conn = idx.connect(a.db)
    filters = {"subject": a.subject, "year": a.year, "exam": a.exam}
    rows = idx.compare(conn, a.queries, **filters)
    grand = sum(r[2] for r in rows)
    if not grand:
        print("모두 용례가 없습니다.")
        return 1

    print(f"표현 비교 — 총 {grand}회\n")
    width = max(len(q) for q in a.queries) + 2
    for q, n_hits, total, forms, ambiguous in rows:
        bar = "█" * round(total * 30 / grand) if grand else ""
        print(f"  {q:<{width}} {total:>5}회  {total*100/grand:>4.0f}%  {bar}")
        for form, cnt, _w in forms:
            if form.replace(" ", "") != q.replace(" ", "") or len(forms) > 1:
                print(f"      └ {form!r} {cnt}회")
        if ambiguous:
            print(f"      └ (줄바꿈 판정 불가 {ambiguous}건)")
    top = rows[0]
    print(f"\n→ 가장 많이 쓰인 쪽: {top[0]!r} ({top[2]}회, {top[1]}개 문항)")
    if top[3]:
        print(f"   실제 표기: {top[3][0][0]!r}")
        for w in top[3][0][2]:
            print(f"     예) {w}")
    return 0


def cmd_show(a: argparse.Namespace) -> int:
    """문항 하나를 그대로 보여준다 (텍스트 + 표, --png 로 이미지 저장)."""
    conn = idx.connect(a.db)
    row = idx.get_segment(conn, a.segment_id)
    if row is None:
        print(f"{a.segment_id} 번 문항이 없습니다.")
        return 1
    print(f"■ {idx.segment_source(row)}   [p.{row['page']} · {row['filename']}]\n")
    print(readable(row["text"]))
    tables = idx.tables_of(row)
    if tables:
        print()
        for tb in tables:
            tb = [[readable(c) for c in r] for r in tb]
            widths = [max(len(r[i]) if i < len(r) else 0 for r in tb)
                      for i in range(max(len(r) for r in tb))]
            for r in tb:
                cells = [(r[i] if i < len(r) else "").ljust(widths[i])
                         for i in range(len(widths))]
                print("  | " + " | ".join(cells) + " |")
            print()
    if a.png:
        from .render import render_segment, segment_parts
        n = segment_parts(row)
        for i in range(n):
            out = a.png if n == 1 else a.png.replace(".png", f"-{i + 1}.png")
            with open(out, "wb") as f:
                f.write(render_segment(row, i, zoom=a.zoom))
            print(f"이미지 저장: {out}")
    return 0


def cmd_subjects(a: argparse.Namespace) -> int:
    conn = idx.connect(a.db)
    rows = idx.subjects(conn)
    if not rows:
        print("색인된 시험지가 없습니다. `python -m gichul ingest <경로>` 부터 하세요.")
        return 1
    print(f"{'과목':<14}{'시험지':>6}{'문항':>8}")
    for s, n, q in rows:
        print(f"{s:<14}{n:>6}{q:>8}")
    return 0


def cmd_stats(a: argparse.Namespace) -> int:
    conn = idx.connect(a.db)
    s = idx.stats(conn)
    print(f"시험지 {s['exams']}개 · {s['pages']}쪽 · 문항 {s['questions']}개  (DB: {a.db})")
    for row in conn.execute(
            "SELECT year, exam, subject, filename, n_questions FROM exams "
            "ORDER BY year DESC, subject"):
        print(f"  {row['year'] or '????'} {row['exam'] or '?':<8} "
              f"{row['subject'] or '?':<12} 문항{row['n_questions']:>3}  {row['filename']}")
    return 0


def cmd_web(a: argparse.Namespace) -> int:
    from .web import serve
    serve(a.db, host=a.host, port=a.port)
    return 0


def cmd_watch(a: argparse.Namespace) -> int:
    from .watch import watch
    watch(a.folder, a.db, interval=a.interval, once=a.once)
    return 0


def cmd_export(a: argparse.Namespace) -> int:
    from .archive import export_jsonl
    conn = idx.connect(a.db)
    n = export_jsonl(conn, a.out)
    size = os.path.getsize(a.out)
    print(f"시험지 {n}개를 {a.out} 로 내보냈습니다 ({size/2**20:.1f} MiB).")
    if not a.out.endswith(".gz"):
        print("  파일명을 .jsonl.gz 로 주면 훨씬 작아집니다.")
    return 0


def cmd_import(a: argparse.Namespace) -> int:
    from .archive import import_jsonl
    conn = idx.connect(a.db)
    r = import_jsonl(conn, a.path, force=a.force)
    print(f"불러오기 완료: 추가 {r['added']}개 / 건너뜀 {r['skipped']}개")
    return 0


def cmd_compact(a: argparse.Namespace) -> int:
    conn = idx.connect(a.db)
    before = os.path.getsize(a.db)
    conn.execute("INSERT INTO seg_fts(seg_fts) VALUES('optimize')")
    conn.commit()
    conn.execute("VACUUM")
    conn.commit()
    after = os.path.getsize(a.db)
    print(f"{before/2**20:.1f} MiB → {after/2**20:.1f} MiB")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gichul", description="기출 시험지 PDF 문항 검색기")
    p.add_argument("--db", default=idx.DEFAULT_DB, help="색인 DB 경로")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_filters(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--subject", help="과목 (예: 생명과학1, 국어)")
        sp.add_argument("--year", type=int, help="학년도")
        sp.add_argument("--exam", help="시험 종류 (수능 / 6월 모평 / 3월 학평)")

    sp = sub.add_parser("ingest", help="PDF/폴더를 색인에 추가")
    sp.add_argument("paths", nargs="+")
    sp.add_argument("--force", action="store_true", help="이미 넣은 파일도 다시 색인")
    sp.add_argument("--grade", help="학년 (고1/고2/고3)")
    add_filters(sp)
    sp.set_defaults(func=cmd_ingest)

    sp = sub.add_parser("search", help="단어 검색 (띄어쓰기 무시)")
    sp.add_argument("query")
    sp.add_argument("--limit", type=int, default=50)
    sp.add_argument("--width", type=int, default=60, help="발췌 좌우 글자 수")
    sp.add_argument("--json", action="store_true")
    add_filters(sp)
    sp.set_defaults(func=cmd_search)

    sp = sub.add_parser("variants", help="표기·띄어쓰기 용례 통계")
    sp.add_argument("query")
    add_filters(sp)
    sp.set_defaults(func=cmd_variants)

    sp = sub.add_parser("compare", help="여러 표현의 사용 빈도 비교 (윤문용)")
    sp.add_argument("queries", nargs="+", help='예: "옳은 것만을" "옳은 것을"')
    add_filters(sp)
    sp.set_defaults(func=cmd_compare)

    sp = sub.add_parser("show", help="문항 하나를 텍스트·표·이미지로 보기")
    sp.add_argument("segment_id", type=int, help="search --json 의 segment_id")
    sp.add_argument("--png", help="문항 이미지를 이 경로에 저장")
    sp.add_argument("--zoom", type=float, default=2.0)
    sp.set_defaults(func=cmd_show)

    sp = sub.add_parser("subjects", help="과목 목록")
    sp.set_defaults(func=cmd_subjects)

    sp = sub.add_parser("stats", help="색인 현황")
    sp.set_defaults(func=cmd_stats)

    sp = sub.add_parser("web", help="브라우저 UI 실행")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=8765)
    sp.set_defaults(func=cmd_web)

    sp = sub.add_parser("watch", help="폴더를 감시하며 새 PDF를 자동 색인")
    sp.add_argument("folder")
    sp.add_argument("--interval", type=float, default=5.0, help="검사 주기(초)")
    sp.add_argument("--once", action="store_true", help="한 번만 훑고 종료")
    sp.set_defaults(func=cmd_watch)

    sp = sub.add_parser("export", help="추출 결과를 JSONL 데이터 파일로 내보내기")
    sp.add_argument("out", help="예: backup.jsonl.gz")
    sp.set_defaults(func=cmd_export)

    sp = sub.add_parser("import", help="JSONL 데이터 파일에서 색인 복원 (PDF 불필요)")
    sp.add_argument("path")
    sp.add_argument("--force", action="store_true", help="이미 있는 시험지도 덮어쓰기")
    sp.set_defaults(func=cmd_import)

    sp = sub.add_parser("compact", help="DB 조각 정리 및 압축")
    sp.set_defaults(func=cmd_compact)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for name in ("subject", "year", "exam", "grade"):
        if not hasattr(args, name):
            setattr(args, name, None)
    try:
        return args.func(args)
    except idx.SchemaMismatch as exc:
        print(f"오류: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
