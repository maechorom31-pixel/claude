"""자동 갱신 스크립트 — GitHub Actions 가 실행한다.

pdfs/ 폴더에 PDF를 올려 두기만 하면:

  1. data/archive.jsonl.gz 에서 지금까지의 색인을 복원하고
  2. pdfs/ 를 훑어 새 파일만 색인에 추가한 뒤        (이미 넣은 파일은 내용으로 건너뜀)
  3. data/archive.jsonl.gz 를 다시 쓴다               ← 이 파일이 진짜 데이터다
  4. data/REPORT.md 에 처리 결과를 적는다             ← 사람이 볼 것은 이것뿐
  5. site/ 에 과목별 검색 페이지를 만든다             (Pages 배포 / 실행 결과물로 내려받기)

사람 손이 필요한 경우는 REPORT.md 에 남는다. 과목을 못 읽은 시험지는
pdfs/ 안에서 파일명에 과목을 넣어 바꾸면 다음 실행에서 채워진다 —
이미 색인된 파일은 내용(sha1)으로 대조하므로 이름만 바꿔도 안전하다.

로컬에서도 그대로 쓸 수 있다:  python3 scripts/ci_update.py [pdfs] [data] [site]
"""

from __future__ import annotations

import html
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gichul import index as idx                    # noqa: E402
from gichul.archive import export_jsonl, import_jsonl   # noqa: E402
from gichul.meta import from_filename              # noqa: E402
from gichul.pipeline import ingest_paths           # noqa: E402
from gichul.standalone import build                # noqa: E402

KST = timezone(timedelta(hours=9))

# 과목 페이지 하나가 이보다 커지면 지면 이미지를 빼고 텍스트만 담는다.
# 한 과목 10년치(문항 200~400개)가 이미지 포함 15~25MB 정도다.
PAGE_BUDGET_MB = 30.0


def _pdfs(folder: str) -> list[str]:
    out = []
    for root, _dirs, files in os.walk(folder):
        out += [os.path.join(root, f) for f in sorted(files)
                if f.lower().endswith(".pdf")]
    return out


def repair_meta_from_filenames(conn, pdf_dir: str) -> list[tuple[str, dict]]:
    """과목·연도를 못 읽은 시험지를 파일명으로 바로잡는다.

    이미 색인된 파일은 내용(sha1)으로 건너뛰기 때문에 파일명을 고쳐도
    재색인되지 않는다. 그래서 sha1 로 대조해 빠진 칸만 채워 넣는다.
    """
    fixed = []
    for path in _pdfs(pdf_dir):
        row = idx.already_indexed(conn, idx.file_sha1(path))
        if row is None:
            continue

        # 파일이 개명·이동되었으면 경로부터 현재 위치로. 안 하면 그 시험지의
        # 지면 이미지를 오려낼 수 없다.
        abspath = os.path.abspath(path)
        if row["path"] != abspath:
            conn.execute("UPDATE exams SET path=?, filename=? WHERE id=?",
                         (abspath, os.path.basename(path), row["id"]))

        fm = from_filename(os.path.basename(path))
        updates = {}
        for field in ("year", "exam", "grade", "subject"):
            if row[field] is None and getattr(fm, field):
                updates[field] = getattr(fm, field)
        if updates:
            sets = ", ".join(f"{k}=?" for k in updates)
            conn.execute(f"UPDATE exams SET {sets} WHERE id=?",
                         [*updates.values(), row["id"]])
            fixed.append((os.path.basename(path), updates))
    conn.commit()
    return fixed


def write_report(conn, path: str, results, fixed) -> None:
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    lines = ["# 기출 색인 처리 결과", "", f"갱신: {now} (한국 시간)", ""]

    added = [r for r in results if r.status in ("added", "replaced")]
    failed = [r for r in results if r.status == "failed"]
    skipped = sum(1 for r in results if r.status == "skipped")

    lines.append("## 이번 실행")
    lines.append("")
    if not results:
        lines.append("- pdfs/ 에 처리할 파일이 없습니다.")
    for r in added:
        src = r.meta.source_label("").rstrip(" ·") if r.meta else "출처미상"
        lines.append(f"- ✅ `{os.path.basename(r.path)}` → **{src}** · 문항 {r.n_questions}개")
        for w in r.warnings or []:
            lines.append(f"  - ⚠️ {w}")
    for r in failed:
        lines.append(f"- ❌ `{os.path.basename(r.path)}` — {r.error}")
    if skipped:
        lines.append(f"- ⏭️ 이미 색인된 파일 {skipped}개는 건너뜀")
    lines.append("")

    if fixed:
        lines.append("## 파일명으로 채워진 정보")
        lines.append("")
        for name, updates in fixed:
            desc = ", ".join(f"{k}={v}" for k, v in updates.items())
            lines.append(f"- `{name}` → {desc}")
        lines.append("")

    unknown = conn.execute(
        "SELECT filename FROM exams WHERE subject IS NULL ORDER BY filename").fetchall()
    if unknown:
        lines.append("## ⚠️ 과목을 읽지 못한 시험지")
        lines.append("")
        lines.append("pdfs/ 안에서 **파일명에 과목을 넣어 이름을 바꾸면** "
                     "(예: `2026_7월학평_물리학1.pdf`) 다음 실행에서 자동으로 채워집니다.")
        lines.append("")
        for row in unknown:
            lines.append(f"- `{row['filename']}`")
        lines.append("")

    lines.append("## 전체 현황")
    lines.append("")
    lines.append("| 과목 | 시험지 | 문항 |")
    lines.append("|---|---:|---:|")
    for s, n, q in idx.subjects(conn):
        lines.append(f"| {s} | {n} | {q} |")
    st = idx.stats(conn)
    lines.append("")
    lines.append(f"합계: 시험지 **{st['exams']}개** · 문항 **{st['questions']}개**")
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


_INDEX_CSS = """
:root{--paper:#F6F7F4;--ink:#1A1C18;--soft:#5B6058;--rule:#D5D9D0;--mark:#C8E24B}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
 --paper:#141713;--ink:#E9ECE4;--soft:#9AA396;--rule:#333A30;--mark:#AFC93A}}
:root[data-theme="dark"]{--paper:#141713;--ink:#E9ECE4;--soft:#9AA396;
 --rule:#333A30;--mark:#AFC93A}
body{margin:0;background:var(--paper);color:var(--ink);
 font:16px/1.65 "Apple SD Gothic Neo","Malgun Gothic",sans-serif}
.wrap{max-width:38rem;margin:0 auto;padding:3rem 1.25rem}
h1{font-size:1.4rem}h1 span{background:var(--mark);color:#1A1C18;padding:0 .15em}
p{color:var(--soft)}
ul{list-style:none;margin:1.5rem 0;padding:0;display:grid;gap:.5rem}
a{display:flex;justify-content:space-between;gap:1rem;color:inherit;
 text-decoration:none;border:1px solid var(--rule);border-radius:3px;
 padding:.7rem 1rem}
a:hover{border-color:var(--mark)}
a small{color:var(--soft);font-variant-numeric:tabular-nums}
footer{margin-top:2rem;font-size:.82rem;color:var(--soft)}
"""


def _copy_pdfs_into_site(pdf_dir: str, site_dir: str) -> int:
    """PDF 원본을 사이트에 같이 싣는다.

    Pages 는 PDF를 브라우저 뷰어로 바로 열어 주므로, 검색 결과에서
    `pdfs/….pdf#page=3` 링크가 원문의 해당 쪽을 그대로 펼친다.
    (GitHub 저장소 파일 보기(blob)는 쪽 이동이 안 된다.)
    """
    import shutil
    n = 0
    for src in _pdfs(pdf_dir):
        rel = os.path.relpath(src, pdf_dir)
        dst = os.path.join(site_dir, "pdfs", rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        n += 1
    return n


def build_site(conn, site_dir: str, pdf_dir: str) -> list[str]:
    os.makedirs(site_dir, exist_ok=True)
    notes = []
    if os.path.isdir(pdf_dir):
        n = _copy_pdfs_into_site(pdf_dir, site_dir)
        if n:
            notes.append(f"원본 PDF {n}개를 사이트에 실음")
    entries = []

    for subject, n_exams, n_q in idx.subjects(conn):
        if subject == "(미상)":
            continue
        fname = f"{subject}.html"
        # 링크는 사이트에 복사된 사본(site/pdfs/…)을 가리킨다. 검색 페이지가
        # site/ 바로 아래 있으므로 "pdfs/파일명#page=N" 상대 경로면 된다.
        r = build(conn, os.path.join(site_dir, fname), subject=subject,
                  max_mb=PAGE_BUDGET_MB, pdf_base_url="pdfs", pdf_root=pdf_dir)
        tag = "" if r["images"] else " · 텍스트만"
        entries.append((fname, subject, f"시험지 {n_exams} · 문항 {n_q}{tag}"))
        notes.append(f"{fname}: 문항 {r['questions']} / {r['size']/2**20:.1f}MB"
                     + ("" if r["images"] else " (이미지 제외)"))

    r = build(conn, os.path.join(site_dir, "전체-텍스트.html"), images=False,
              pdf_base_url="pdfs", pdf_root=pdf_dir)
    entries.append(("전체-텍스트.html", "전체 과목 통합",
                    f"문항 {r['questions']} · 텍스트만"))

    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    items = "".join(
        f'<li><a href="{html.escape(f)}"><span>{html.escape(t)}</span>'
        f"<small>{html.escape(d)}</small></a></li>"
        for f, t, d in entries)
    with open(os.path.join(site_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(
            '<!doctype html><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>기출 용례 검색</title><style>{_INDEX_CSS}</style>"
            '<div class="wrap"><h1><span>기출 용례 검색</span></h1>'
            f"<ul>{items}</ul>"
            + _footer(now))
    return notes


def _footer(now: str) -> str:
    url = _upload_url()
    add = (f' · <a style="border:none;display:inline;padding:0;color:inherit;'
           f'text-decoration:underline" href="{html.escape(url)}">PDF 추가하기</a>'
           if url else "")
    return (f"<footer>갱신 {now}{add} — 올리면 1~2분 뒤 자동 반영</footer></div>")


def _upload_url() -> str | None:
    """GitHub 웹의 '이 폴더에 파일 올리기' 화면으로 바로 가는 주소."""
    repo = os.environ.get("GITHUB_REPOSITORY")          # 예: 계정/저장소
    if not repo:
        return None
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    return f"https://github.com/{repo}/upload/{branch}/pdfs"


def write_empty_site(site_dir: str) -> None:
    """아직 아무것도 색인되지 않았을 때의 첫 화면.

    처음 마주치는 화면이 이것이므로, 다음에 할 일(업로드)로 바로
    이어지게 만든다.
    """
    os.makedirs(site_dir, exist_ok=True)
    url = _upload_url()
    button = (f'<p><a class="go" href="{html.escape(url)}">pdfs 폴더에 PDF 올리기 →</a></p>'
              if url else
              "<p>저장소의 <b>pdfs</b> 폴더 → <b>Add file → Upload files</b> 로 올리세요.</p>")
    with open(os.path.join(site_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(
            '<!doctype html><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>기출 용례 검색</title><style>{_INDEX_CSS}"
            "a.go{display:inline-flex;background:var(--mark);color:#1A1C18;"
            "border:none;font-weight:600}</style>"
            '<div class="wrap"><h1><span>기출 용례 검색</span></h1>'
            "<p>아직 올라온 시험지가 없습니다. PDF를 올리면 1~2분 뒤 이 자리에 "
            "과목별 검색 페이지가 생깁니다.</p>"
            f"{button}"
            "<footer>올린 뒤에는 이 페이지를 새로고침하세요. 처리 결과는 저장소의 "
            "data/REPORT.md 에 적힙니다.</footer></div>")


def main() -> int:
    pdf_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "pdfs")
    data_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "data")
    site_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.join(ROOT, "site")
    force = os.environ.get("GICHUL_FORCE") == "1"

    os.makedirs(data_dir, exist_ok=True)
    archive = os.path.join(data_dir, "archive.jsonl.gz")

    # 색인 DB는 매번 JSONL 에서 다시 만든다. 커밋할 것은 JSONL 뿐이다.
    with tempfile.TemporaryDirectory() as tmp:
        conn = idx.connect(os.path.join(tmp, "index.db"))

        if os.path.exists(archive):
            r = import_jsonl(conn, archive)
            print(f"복원: 시험지 {r['added']}개 (data/archive.jsonl.gz)")

        results = []
        if os.path.isdir(pdf_dir):
            results = ingest_paths(conn, [pdf_dir], force=force)
        fixed = repair_meta_from_filenames(conn, pdf_dir) if os.path.isdir(pdf_dir) else []

        n = export_jsonl(conn, archive)
        print(f"저장: 시험지 {n}개 → {archive} "
              f"({os.path.getsize(archive)/2**20:.2f}MB)")

        write_report(conn, os.path.join(data_dir, "REPORT.md"), results, fixed)
        print(f"보고서: {os.path.join(data_dir, 'REPORT.md')}")

        if idx.stats(conn)["exams"]:
            for note in build_site(conn, site_dir, pdf_dir):
                print(f"페이지: {note}")
        else:
            write_empty_site(site_dir)

        failed = [r for r in results if r.status == "failed"]
        for r in failed:
            print(f"실패: {r.path}: {r.error}", file=sys.stderr)
        conn.close()
    return 0        # 일부 파일이 실패해도 나머지 결과는 배포한다


if __name__ == "__main__":
    sys.exit(main())
