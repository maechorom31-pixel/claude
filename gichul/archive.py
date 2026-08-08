"""데이터 파일(JSONL) 내보내기·불러오기.

SQLite DB는 '검색용 산출물'이라 언제든 다시 만들 수 있어야 한다.
그래서 추출 결과 자체는 사람이 읽을 수 있는 JSONL 한 줄=한 시험지로 따로 보관한다.

  · PDF 원본이 없어도 이 파일만 있으면 색인을 통째로 복원할 수 있다.
  · gzip 으로 두면 원본 PDF의 1/100 수준이다.
  · 형식이 단순해서 나중에 다른 도구로 옮기기 쉽다.
"""

from __future__ import annotations

import gzip
import io
import json
import os
import sqlite3
from typing import Iterator

from . import index as idx
from .meta import ExamMeta

FORMAT = "gichul-jsonl/1"


def _open(path: str, mode: str):
    if path.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(path, mode.replace("t", "") + "b"),
                                encoding="utf-8")
    return open(path, mode, encoding="utf-8")


def export_jsonl(conn: sqlite3.Connection, path: str) -> int:
    """색인 전체를 JSONL 로 쓴다. 반환값은 시험지 수."""
    n = 0
    with _open(path, "wt") as f:
        f.write(json.dumps({"format": FORMAT}, ensure_ascii=False) + "\n")
        for e in conn.execute("SELECT * FROM exams ORDER BY id"):
            segs = []
            for s in conn.execute(
                    "SELECT kind, number, number_end, page, rects, tables, text "
                    "FROM segments WHERE exam_id=? ORDER BY id", (e["id"],)):
                d = {"kind": s["kind"], "number": s["number"],
                     "number_end": s["number_end"], "page": s["page"],
                     "text": s["text"]}
                # 좌표·표는 있을 때만 적는다. 이게 빠지면 복원 후
                # 지면 이미지를 오려낼 수 없다.
                rects = json.loads(s["rects"] or "[]")
                if rects:
                    d["rects"] = rects
                if s["tables"]:
                    d["tables"] = json.loads(s["tables"])
                segs.append(d)
            f.write(json.dumps({
                "sha1": e["sha1"], "filename": e["filename"], "path": e["path"],
                "year": e["year"], "exam": e["exam"], "grade": e["grade"],
                "subject": e["subject"], "n_pages": e["n_pages"],
                "scanned_pages": e["scanned_pages"],
                "segments": segs,
            }, ensure_ascii=False) + "\n")
            n += 1
    return n


def _records(path: str) -> Iterator[dict]:
    with _open(path, "rt") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if i == 0 and "format" in rec:
                if rec["format"] != FORMAT:
                    raise ValueError(f"모르는 형식입니다: {rec['format']}")
                continue
            yield rec


def import_jsonl(conn: sqlite3.Connection, path: str, *, force: bool = False) -> dict:
    """JSONL 을 색인에 넣는다. PDF 원본은 필요 없다."""
    added = skipped = 0
    for rec in _records(path):
        existing = idx.already_indexed(conn, rec["sha1"])
        if existing:
            if not force:
                skipped += 1
                continue
            idx.delete_exam(conn, existing["id"])
        # dict 그대로 넘긴다. Segment 로 다시 만들면 좌표·표가 사라진다.
        segs = rec["segments"]
        meta = ExamMeta(year=rec["year"], exam=rec["exam"], grade=rec["grade"],
                        subject=rec["subject"])
        scanned = [int(x) for x in (rec.get("scanned_pages") or "").split(",") if x]
        idx.add_exam(conn, sha1=rec["sha1"], path=rec.get("path") or rec["filename"],
                     meta=meta, segments=segs, n_pages=rec["n_pages"],
                     scanned_pages=scanned)
        added += 1
    return {"added": added, "skipped": skipped,
            "size": os.path.getsize(path) if os.path.exists(path) else 0}
