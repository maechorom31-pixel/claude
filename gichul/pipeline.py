"""PDF 한 개를 색인에 넣기까지의 전 과정."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass

from . import index as idx
from .extract import extract
from .meta import ExamMeta, from_filename, from_text, merge
from .segment import Segment, segment


@dataclass
class IngestResult:
    path: str
    status: str                  # "added" | "skipped" | "replaced" | "failed"
    exam_id: int | None = None
    meta: ExamMeta | None = None
    n_questions: int = 0
    n_pages: int = 0
    scanned_pages: list[int] | None = None
    warnings: list[str] | None = None
    error: str | None = None


def _meta_text(segments: list[Segment], full_text: str) -> str:
    """메타데이터를 찾을 텍스트.

    표지가 앞에 있는 시험지도 있고, 학력평가처럼 '2026학년도 7월 고3 전국연합
    학력평가 문제지' 머리글이 중간 페이지에 붙는 시험지도 있다. 그래서 앞부분만
    보지 않고 문서 전체를 대상으로 하되, 표지가 있으면 그쪽을 먼저 본다.
    """
    front = next((s.text for s in segments if s.kind == "front"), "")
    return front[:1500] + "\n" + full_text


def _attach_tables(segments: list[Segment], tables) -> None:
    """표를 그 표가 놓인 문항에 붙인다. 표 한가운데가 어느 문항 영역에 있는지로 판단."""
    boxes = [(s, s.rects()) for s in segments]
    for t in tables:
        cx = (t.bbox[0] + t.bbox[2]) / 2
        cy = (t.bbox[1] + t.bbox[3]) / 2
        for seg, rects in boxes:
            if any(page == t.page and x0 <= cx <= x1 and y0 <= cy <= y1
                   for page, x0, y0, x1, y1 in rects):
                seg.tables.append(t.rows)
                break


def _check(segments: list[Segment], scanned: list[int], n_pages: int,
           n_chars: int = 0, n_broken: int = 0) -> list[str]:
    warn: list[str] = []
    if n_chars and n_broken / n_chars > 0.02:
        warn.append(f"글꼴 매핑이 없어 읽지 못한 문자가 {n_broken}자 "
                    f"({n_broken * 100 / n_chars:.1f}%) 있습니다.")
    numbers = [s.number for s in segments if s.kind == "question"]
    if not numbers:
        warn.append("문항 번호를 하나도 찾지 못했습니다. 스캔본이거나 편집 형식이 다를 수 있습니다.")
    else:
        missing = sorted(set(range(1, max(numbers) + 1)) - set(numbers))
        if missing:
            warn.append(f"번호가 빠졌습니다: {', '.join(map(str, missing[:15]))}"
                        + (" …" if len(missing) > 15 else ""))
    if scanned:
        warn.append(f"텍스트가 거의 없는 페이지: {scanned} (스캔본이면 OCR 필요)")
    if n_pages and len(numbers) / n_pages < 1.5 and numbers:
        warn.append("페이지당 문항 수가 비정상적으로 적습니다. 단 나누기 결과를 확인하세요.")
    return warn


def ingest_file(conn: sqlite3.Connection, path: str, *,
                overrides: ExamMeta | None = None, force: bool = False) -> IngestResult:
    if not os.path.isfile(path):
        return IngestResult(path, "failed", error="파일이 없습니다")

    try:
        sha1 = idx.file_sha1(path)
        existing = idx.already_indexed(conn, sha1)
        if existing and not force:
            return IngestResult(path, "skipped", exam_id=existing["id"],
                                meta=ExamMeta(existing["year"], existing["exam"],
                                              existing["grade"], existing["subject"]))
        ex = extract(path)
        segs = segment(ex.lines)
        _attach_tables(segs, ex.tables)
        meta = merge(overrides or ExamMeta(),
                     from_text(_meta_text(segs, ex.text)),
                     from_filename(os.path.basename(path)))

        if existing:
            idx.delete_exam(conn, existing["id"])
        exam_id = idx.add_exam(conn, sha1=sha1, path=path, meta=meta, segments=segs,
                               n_pages=ex.n_pages, scanned_pages=ex.scanned_pages)
        return IngestResult(
            path, "replaced" if existing else "added", exam_id=exam_id, meta=meta,
            n_questions=sum(1 for s in segs if s.kind == "question"),
            n_pages=ex.n_pages, scanned_pages=ex.scanned_pages,
            warnings=_check(segs, ex.scanned_pages, ex.n_pages, ex.n_chars, ex.n_broken),
        )
    except Exception as exc:                     # noqa: BLE001 - 한 파일 실패가 전체를 막지 않게
        return IngestResult(path, "failed", error=f"{type(exc).__name__}: {exc}")


def ingest_paths(conn: sqlite3.Connection, paths: list[str], *,
                 overrides: ExamMeta | None = None,
                 force: bool = False) -> list[IngestResult]:
    targets: list[str] = []
    for p in paths:
        if os.path.isdir(p):
            for root, _dirs, files in os.walk(p):
                targets += [os.path.join(root, f) for f in sorted(files)
                            if f.lower().endswith(".pdf")]
        else:
            targets.append(p)
    return [ingest_file(conn, t, overrides=overrides, force=force) for t in targets]
