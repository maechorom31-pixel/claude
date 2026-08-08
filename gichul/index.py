"""SQLite 저장소 + 검색.

FTS5 의 trigram 토크나이저를 쓴다. 한국어는 공백 단위로 잘라 봐야 조사 때문에
잘 안 맞는데, trigram 은 부분 문자열 검색이라 `빛에너지`, `에너지를` 같은 것이
전부 걸린다. 3글자 미만 검색어는 trigram 색인이 못 쓰므로 LIKE 로 떨어진다.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from .meta import ExamMeta, canon_subject, subject_aliases
from .normalize import OBJ, FOLD_MAP, STRIPPED_SPACES, find_spans, query_key, readable

DEFAULT_DB = os.environ.get("GICHUL_DB", os.path.expanduser("~/.gichul/index.db"))
SCHEMA_VERSION = 2


def _sql_str(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def _key_expr(col: str = "text") -> str:
    """검색 키를 만드는 SQL 식.

    normalize.nospace() 와 같은 결과를 내야 한다. 파이썬 쪽 표를 그대로 읽어
    식을 만들기 때문에 한쪽만 바뀌어 어긋날 일이 없다.
    """
    expr = col
    for src, dst in FOLD_MAP.items():
        expr = f"replace({expr},{_sql_str(src)},{_sql_str(dst)})"
    for ch in STRIPPED_SPACES:
        expr = f"replace({expr},{_sql_str(ch)},'')"
    return expr


# key 는 저장하지 않는 가상 생성 열이다. 본문과 거의 같은 크기라 그대로 쌓으면
# DB가 두 배가 된다. 대신 조회할 때마다 replace() 로 즉석 계산한다.
_SCHEMA = f"""
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS exams(
  id INTEGER PRIMARY KEY,
  sha1 TEXT UNIQUE NOT NULL,
  path TEXT NOT NULL,
  filename TEXT NOT NULL,
  year INTEGER, exam TEXT, grade TEXT, subject TEXT,
  n_pages INTEGER, n_questions INTEGER,
  scanned_pages TEXT,
  ingested_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS segments(
  id INTEGER PRIMARY KEY,
  exam_id INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  number INTEGER, number_end INTEGER, page INTEGER,
  part TEXT,                        -- 선택과목 구획 (미적분, 언어와 매체 …)
  rects TEXT,                       -- 원본 PDF 좌표 [[page,x0,y0,x1,y1], ...]
  tables TEXT,                      -- 문항에 딸린 표 [[[셀,...],...], ...]
  text TEXT NOT NULL,
  key  TEXT GENERATED ALWAYS AS ({_key_expr()}) VIRTUAL
);
CREATE INDEX IF NOT EXISTS idx_seg_exam ON segments(exam_id);
CREATE VIRTUAL TABLE IF NOT EXISTS seg_fts
  USING fts5(key, content='segments', content_rowid='id', tokenize='trigram');
CREATE TRIGGER IF NOT EXISTS seg_ai AFTER INSERT ON segments BEGIN
  INSERT INTO seg_fts(rowid, key) VALUES (new.id, new.key);
END;
CREATE TRIGGER IF NOT EXISTS seg_ad AFTER DELETE ON segments BEGIN
  INSERT INTO seg_fts(seg_fts, rowid, key) VALUES ('delete', old.id, old.key);
END;
"""


@dataclass
class Hit:
    exam_id: int
    segment_id: int
    source: str          # "2014학년도 수능 · 생명과학I · 1번"
    subject: str | None
    year: int | None
    exam: str | None
    page: int
    text: str
    spans: list[tuple[int, int]]
    filename: str
    has_image: bool = False       # 원본 PDF가 남아 있어 잘라 보여줄 수 있는가

    def snippet(self, width: int = 60, mark: tuple[str, str] = ("《", "》")) -> str:
        if not self.spans:
            return readable(self.text[: width * 2]).replace("\n", " ")
        a, b = self.spans[0]
        lo, hi = max(0, a - width), min(len(self.text), b + width)
        head = "…" if lo > 0 else ""
        tail = "…" if hi < len(self.text) else ""
        body = (self.text[lo:a] + mark[0] + self.text[a:b] + mark[1] + self.text[b:hi])
        return readable(head + body + tail).replace("\n", " ")


class SchemaMismatch(RuntimeError):
    pass


def connect(db_path: str = DEFAULT_DB) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(db_path)) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")

    exists = conn.execute(
        "SELECT 1 FROM sqlite_schema WHERE type='table' AND name='segments'").fetchone()
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if exists and version != SCHEMA_VERSION:
        raise SchemaMismatch(
            f"색인 DB 형식이 다릅니다 (v{version} → v{SCHEMA_VERSION}). "
            f"'{db_path}' 를 지우고 다시 색인하세요.")

    conn.executescript(_SCHEMA)
    conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
    return conn


def file_sha1(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def already_indexed(conn: sqlite3.Connection, sha1: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM exams WHERE sha1=?", (sha1,)).fetchone()


def delete_exam(conn: sqlite3.Connection, exam_id: int) -> None:
    conn.execute("DELETE FROM segments WHERE exam_id=?", (exam_id,))
    conn.execute("DELETE FROM exams WHERE id=?", (exam_id,))
    conn.commit()


def add_exam(conn: sqlite3.Connection, *, sha1: str, path: str, meta: ExamMeta,
             segments, n_pages: int, scanned_pages: list[int]) -> int:
    n_q = sum(1 for s in segments if _seg_kind(s) == "question")
    cur = conn.execute(
        """INSERT INTO exams(sha1, path, filename, year, exam, grade, subject,
                             n_pages, n_questions, scanned_pages, ingested_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (sha1, os.path.abspath(path), os.path.basename(path), meta.year, meta.exam,
         meta.grade, meta.subject, n_pages, n_q,
         ",".join(map(str, scanned_pages)), datetime.now(timezone.utc).isoformat(timespec="seconds")),
    )
    exam_id = int(cur.lastrowid)
    conn.executemany(
        """INSERT INTO segments(exam_id, kind, number, number_end, page,
                               part, rects, tables, text)
           VALUES(?,?,?,?,?,?,?,?,?)""",
        [(exam_id, *_seg_row(s)) for s in segments],
    )
    conn.commit()
    return exam_id


def _seg_kind(s) -> str:
    return s["kind"] if isinstance(s, dict) else s.kind


def _seg_row(s) -> tuple:
    """세그먼트 한 줄. 새로 파싱한 Segment 객체와 JSONL 에서 복원한 dict 를
    모두 받는다 — 복원본은 좌표·표를 이미 계산된 값 그대로 보존해야 한다."""
    if isinstance(s, dict):
        return (s["kind"], s.get("number"), s.get("number_end"), s.get("page"),
                s.get("part"),
                json.dumps(s.get("rects") or []),
                json.dumps(s["tables"], ensure_ascii=False) if s.get("tables") else None,
                s["text"])
    return (s.kind, s.number, s.number_end, s.page, s.part,
            json.dumps([list(r) for r in s.rects()]),
            json.dumps(s.tables, ensure_ascii=False) if s.tables else None,
            s.text)


def _row_meta(row: sqlite3.Row) -> ExamMeta:
    return ExamMeta(year=row["year"], exam=row["exam"], grade=row["grade"],
                    subject=row["subject"])


def _label(row: sqlite3.Row) -> str:
    head = f"{row['part']} " if row["part"] else ""
    if row["kind"] == "question":
        return f"{head}{row['number']}번"
    if row["kind"] == "passage":
        return f"{head}{row['number']}~{row['number_end']}번 지문"
    return "표지/안내"


def _fts_phrase(key: str) -> str:
    return '"' + key.replace('"', '""') + '"'


def _like_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _prefilter(key: str) -> tuple[str, str]:
    """짧은 검색어용 초벌 거르기 (열 이름, LIKE 패턴).

    `key` 가 공백 제거본 안에 있으면 원문에도 같은 순서로 글자들이 나타난다.
    그래서 `text LIKE '%ㄱ%ㄴ%'` 은 정답을 절대 놓치지 않는 상위집합이다.
    단, 부호 폴딩 대상 글자는 원문과 글자가 달라질 수 있으니 제외한다.
    """
    folded = set(FOLD_MAP) | set(FOLD_MAP.values())
    safe = [c for c in key if c not in folded]
    if safe:
        return "text", "%" + "%".join(_like_escape(c) for c in safe) + "%"
    return "key", f"%{_like_escape(key)}%"


def search(conn: sqlite3.Connection, query: str, *, subject: str | None = None,
           year: int | None = None, exam: str | None = None,
           kinds: tuple[str, ...] = ("question", "passage"),
           limit: int = 50) -> list[Hit]:
    key = query_key(query)
    if not key:
        return []

    where = ["s.kind IN (%s)" % ",".join("?" * len(kinds))]
    params: list = list(kinds)

    if subject:
        aliases = subject_aliases(subject)
        where.append("e.subject IN (%s)" % ",".join("?" * len(aliases)))
        params += sorted(aliases)
    if year:
        where.append("e.year = ?")
        params.append(year)
    if exam:
        where.append("e.exam LIKE ?")
        params.append(f"%{exam}%")

    if len(key) >= 3:
        sql = ("SELECT s.*, e.* , s.id AS sid, e.id AS eid FROM seg_fts f "
               "JOIN segments s ON s.id=f.rowid JOIN exams e ON e.id=s.exam_id "
               "WHERE seg_fts MATCH ? AND " + " AND ".join(where))
        args = [_fts_phrase(key)] + params
    else:
        # trigram 색인은 3글자 이상만 쓸 수 있다. 짧은 검색어는 스캔인데,
        # 생성 열(key)을 매 행마다 계산하면 느리므로 원문에 대해 값싼
        # 초벌 거르기(%ㄱ%ㄴ%)만 걸고 정확한 판정은 파이썬에 맡긴다.
        col, needle = _prefilter(key)
        sql = (f"SELECT s.*, e.*, s.id AS sid, e.id AS eid FROM segments s "
               f"JOIN exams e ON e.id=s.exam_id WHERE s.{col} LIKE ? ESCAPE '\\' AND "
               + " AND ".join(where))
        args = [needle] + params

    sql += " ORDER BY e.year DESC, e.subject, s.number LIMIT ?"
    args.append(limit)

    hits: list[Hit] = []
    for row in conn.execute(sql, args):
        spans = find_spans(row["text"], query)
        if not spans:          # trigram 은 근사 매칭이라 오탐이 나올 수 있다
            continue
        hits.append(Hit(
            exam_id=row["eid"], segment_id=row["sid"],
            source=_row_meta(row).source_label(_label(row)),
            subject=row["subject"], year=row["year"], exam=row["exam"],
            page=row["page"], text=row["text"], spans=spans,
            filename=row["filename"],
            has_image=bool(row["rects"]) and os.path.exists(row["path"]),
        ))
    return hits


def variants(hits: list[Hit]) -> tuple[list[tuple[str, int, list[str]]], int]:
    """검색어가 실제로 어떻게 표기되어 있었는지 집계.

    반환: ([(표기형, 등장 횟수, 예시 출처 최대 3개)], 판정 불가 건수)

    줄바꿈이나 못 읽은 수식을 사이에 둔 경우는 뺀다. 한국어 조판은 낱말 가운데서도
    줄을 바꾸므로 `옳은 것만\\n을` 이 붙여 쓴 건지 띄어 쓴 건지 PDF만 봐서는 알 수
    없고, 수식이 있던 자리도 마찬가지다. 이걸 세면 없는 띄어쓰기 사례가 생긴다.
    """
    from collections import defaultdict
    counts: dict[str, int] = defaultdict(int)
    where: dict[str, list[str]] = defaultdict(list)
    ambiguous = 0
    for h in hits:
        for a, b in h.spans:
            raw = h.text[a:b]
            if "\n" in raw or OBJ in raw:
                ambiguous += 1
                continue
            form = re.sub(r"[ \t]+", " ", raw)
            counts[form] += 1
            if h.source not in where[form] and len(where[form]) < 3:
                where[form].append(h.source)
    forms = sorted(((f, c, where[f]) for f, c in counts.items()),
                   key=lambda t: (-t[1], t[0]))
    return forms, ambiguous


def get_segment(conn: sqlite3.Connection, segment_id: int) -> sqlite3.Row | None:
    """문항 하나를 원본 PDF 경로·좌표와 함께 가져온다."""
    return conn.execute(
        """SELECT s.*, e.path, e.filename, e.year, e.exam, e.grade, e.subject
           FROM segments s JOIN exams e ON e.id = s.exam_id WHERE s.id = ?""",
        (segment_id,)).fetchone()


def segment_source(row: sqlite3.Row) -> str:
    return _row_meta(row).source_label(_label(row))


def compare(conn: sqlite3.Connection, queries: list[str], **filters
            ) -> list[tuple[str, int, int, list[tuple[str, int, list[str]]], int]]:
    """여러 표현을 나란히 세어 본다. 윤문할 때 '어느 쪽이 관례인가'를 보려는 것.

    반환: [(검색어, 문항 수, 등장 횟수, 표기 분포, 판정 불가 수)]
    """
    out = []
    for q in queries:
        hits = search(conn, q, limit=10_000, **filters)
        forms, ambiguous = variants(hits)
        out.append((q, len(hits), sum(c for _f, c, _w in forms), forms, ambiguous))
    return sorted(out, key=lambda t: -t[2])


def tables_of(row: sqlite3.Row) -> list[list[list[str]]]:
    try:
        return json.loads(row["tables"] or "[]")
    except (json.JSONDecodeError, TypeError):
        return []


def subjects(conn: sqlite3.Connection) -> list[tuple[str, int, int]]:
    rows = conn.execute(
        """SELECT COALESCE(subject,'(미상)') AS s, COUNT(*) n, SUM(n_questions) q
           FROM exams GROUP BY s ORDER BY n DESC"""
    ).fetchall()
    return [(r["s"], r["n"], r["q"] or 0) for r in rows]


def stats(conn: sqlite3.Connection) -> dict:
    e = conn.execute("SELECT COUNT(*) c, COALESCE(SUM(n_pages),0) p FROM exams").fetchone()
    s = conn.execute("SELECT COUNT(*) c FROM segments WHERE kind='question'").fetchone()
    return {"exams": e["c"], "pages": e["p"], "questions": s["c"]}


def canon(subject: str | None) -> str | None:
    return canon_subject(subject)
