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
from gichul.meta import from_filename, subject_sort_key   # noqa: E402
from gichul.pipeline import PARSER_VERSION, _year_from_dirs   # noqa: E402
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
        if fm.year is None:
            fm.year = _year_from_dirs(path)
        updates = {}
        for field in ("year", "exam", "grade", "subject"):
            if row[field] is None and getattr(fm, field):
                updates[field] = getattr(fm, field)
        # `연도_시험_과목` 규칙으로 지정한 과목은 이미 들어간 값과 달라도
        # 바로잡는다. 표지를 잘못 읽었을 때의 수정 경로다.
        if fm.explicit and fm.subject and row["subject"] != fm.subject:
            updates["subject"] = fm.subject
        if updates:
            sets = ", ".join(f"{k}=?" for k in updates)
            conn.execute(f"UPDATE exams SET {sets} WHERE id=?",
                         [*updates.values(), row["id"]])
            fixed.append((os.path.basename(path), updates))
    conn.commit()
    return fixed


def sweep_repo_root(repo_dir: str, pdf_dir: str) -> list[tuple[str, str]]:
    """저장소 맨 위에 잘못 올라온 PDF를 pdfs/ 로 거둔다.

    업로드 화면을 저장소 첫 화면에서 열면 파일이 저장소 루트로 들어간다.
    색인은 pdfs/ 만 보므로 여기 놓인 파일은 영영 처리되지 않는다 — 옮긴
    뒤는 여느 업로드처럼 색인되고 연도 폴더로 정리된다.
    """
    moved = []
    for name in sorted(os.listdir(repo_dir)):
        src = os.path.join(repo_dir, name)
        if not (os.path.isfile(src) and name.lower().endswith(".pdf")):
            continue
        os.makedirs(pdf_dir, exist_ok=True)
        dst = os.path.join(pdf_dir, name)
        if os.path.exists(dst):
            if idx.file_sha1(dst) == idx.file_sha1(src):
                os.remove(src)
                moved.append((name, "`pdfs/` 에 이미 있음 · 중복 제거"))
            continue
        os.rename(src, dst)
        moved.append((name, "저장소 맨 위에 있어 `pdfs/` 로 이동"))
    return moved


def sort_into_year_folders(conn, pdf_dir: str) -> list[tuple[str, str]]:
    """pdfs/ 바로 아래 놓인 파일을 연도 폴더로 옮긴다.

    업로드 단추는 pdfs/ 루트를 열기 때문에 새 파일은 늘 루트로 들어온다.
    연도는 색인이 이미 알고 있으니(파일명·표지·폴더 순으로 판독) 사람이
    옮길 이유가 없다. 옮긴 뒤의 경로는 repair 가 sha1 로 대조해 맞춘다.
    """
    moved = []
    for name in sorted(os.listdir(pdf_dir)):
        src = os.path.join(pdf_dir, name)
        if not (os.path.isfile(src) and name.lower().endswith(".pdf")):
            continue
        sha1 = idx.file_sha1(src)
        row = idx.already_indexed(conn, sha1)
        year = row["year"] if row else from_filename(name).year
        if not year:
            continue                     # 연도를 모르면 그대로 둔다 — REPORT 에 미상으로 뜬다
        dst_dir = os.path.join(pdf_dir, str(year))
        dst = os.path.join(dst_dir, name)
        if os.path.exists(dst):
            # 이미 들어간 파일을 또 올린 경우: 내용까지 같으면 루트 쪽을
            # 지워서 중복이 쌓이지 않게 한다. 내용이 다르면 사람이 봐야
            # 하는 상황이므로 건드리지 않는다.
            if idx.file_sha1(dst) == sha1:
                os.remove(src)
                moved.append((name, f"`pdfs/{year}/` 에 이미 있음 · 중복 제거"))
            continue
        os.makedirs(dst_dir, exist_ok=True)
        os.rename(src, dst)
        moved.append((name, f"`pdfs/{year}/` 로 이동"))
    return moved


def target_files(pdf_dir: str, target: str) -> list[str]:
    """연도별 재파싱 대상: 폴더 이름이 target 이거나 파일명이 target 으로 시작."""
    out = []
    for path in _pdfs(pdf_dir):
        rel = os.path.relpath(path, pdf_dir)
        parts = rel.split(os.sep)
        if target in parts[:-1] or parts[-1].startswith(target):
            out.append(path)
    return out


def prune_missing(conn, enabled: bool) -> list[str]:
    """원본 PDF가 더는 없는 시험지를 색인에서 뺀다.

    기본 동작은 '지워도 데이터는 남는다'(용량 정리용)이므로, 잘못 올린 파일을
    치우고 싶을 때만 수동 실행에서 켠다.
    """
    if not enabled:
        return []
    gone = [(r["id"], r["filename"]) for r in
            conn.execute("SELECT id, filename, path FROM exams")
            if not os.path.exists(r["path"])]
    for exam_id, _name in gone:
        idx.delete_exam(conn, exam_id)
    return [name for _id, name in gone]


def write_report(conn, path: str, results, fixed, pruned=(), moved=()) -> None:
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

    if moved:
        lines.append("## 연도 폴더로 정리")
        lines.append("")
        for name, what in moved:
            lines.append(f"- `{name}` → {what}")
        lines.append("")

    if pruned:
        lines.append("## 색인에서 뺀 시험지 (원본 PDF 삭제됨, prune 실행)")
        lines.append("")
        for name in pruned:
            lines.append(f"- `{name}`")
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
        lines.append("pdfs/ 안에서 파일명을 **`연도_시험_과목`** 꼴로 바꾸면 "
                     "(예: `2027_수능_생명과학1.pdf`, 약어 `생윤`·`물1`·`언매`도 됨) "
                     "다음 실행에서 자동으로 채워집니다. 과목이 **잘못** 잡혔을 때도 "
                     "같은 방법으로 바로잡힙니다.")
        lines.append("")
        for row in unknown:
            lines.append(f"- `{row['filename']}`")
        lines.append("")

    _exam_order = {"6월 모평": 0, "9월 모평": 1, "수능": 2}
    cov: dict[tuple, dict[str, int]] = {}
    subjects_seen: set[str] = set()
    for r in conn.execute("SELECT year, exam, subject, n_questions FROM exams "
                          "WHERE subject IS NOT NULL"):
        key = (r["year"] or 0, r["exam"] or "?")
        cov.setdefault(key, {})[r["subject"]] = \
            cov.get(key, {}).get(r["subject"], 0) + (r["n_questions"] or 0)
        subjects_seen.add(r["subject"])
    if cov:
        cols = sorted(subjects_seen, key=subject_sort_key)
        lines.append("## 보유 현황 — 어느 시험의 어떤 과목이 올라와 있나")
        lines.append("")
        lines.append("숫자는 문항 수, ─ 는 아직 안 올라온 과목. "
                     "0 은 올라왔지만 글자를 못 읽은 파일(스캔본)이다.")
        lines.append("")
        lines.append("| 시험 \\ 과목 | " + " | ".join(cols) + " |")
        lines.append("|---|" + "---:|" * len(cols))
        for (year, exam) in sorted(cov, key=lambda k: (-k[0], _exam_order.get(k[1], 9))):
            row = cov[(year, exam)]
            cells = [str(row[c]) if c in row else "─" for c in cols]
            lines.append(f"| {year}학년도 {exam} | " + " | ".join(cells) + " |")
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


_PDFJS_VERSION = "3.11.174"


def fetch_pdfjs(site_dir: str) -> bool:
    """pdf.js 를 사이트에 싣는다. 실패하면 False — 그땐 예전처럼 이미지를 굽는다."""
    import urllib.request
    vendor = os.path.join(site_dir, "vendor")
    os.makedirs(vendor, exist_ok=True)
    base = f"https://cdnjs.cloudflare.com/ajax/libs/pdf.js/{_PDFJS_VERSION}/"
    for fname in ("pdf.min.js", "pdf.worker.min.js"):
        dst = os.path.join(vendor, fname)
        if os.path.exists(dst) and os.path.getsize(dst) > 10_000:
            continue
        try:
            urllib.request.urlretrieve(base + fname, dst)
        except Exception:                          # noqa: BLE001
            return False
    return True


def build_site(conn, site_dir: str, pdf_dir: str) -> list[str]:
    """첫 화면 = 검색 페이지 하나.

    과목별 페이지를 따로 두지 않는다. 검색창의 과목 칩으로 이미 고를 수
    있는데 목차를 한 번 더 거치게 할 이유가 없다. 지면 이미지는 용량 예산
    안이면 넣고, 넘으면 빼되 문항마다 원본 PDF 해당 쪽 링크가 남는다.
    """
    os.makedirs(site_dir, exist_ok=True)
    notes = []
    if os.path.isdir(pdf_dir):
        n = _copy_pdfs_into_site(pdf_dir, site_dir)
        if n:
            notes.append(f"원본 PDF {n}개를 사이트에 실음")

    # 지면은 pdf.js 로 열 때 오려 그린다. 이미지를 미리 구우면 문항 수백 개에서
    # 페이지가 수십 MB가 되어 예산에 걸리고, 그때부터 지면이 사라져 보였다.
    use_pdfjs = fetch_pdfjs(site_dir)
    r = build(conn, os.path.join(site_dir, "index.html"),
              max_mb=PAGE_BUDGET_MB, pdf_base_url="pdfs", pdf_root=pdf_dir,
              upload_url=_upload_url(), repo_url=_repo_url(),
              pdfjs=use_pdfjs, images=False if use_pdfjs else None)
    mode = "지면은 열 때 PDF에서 그림" if use_pdfjs else (
        "이미지 내장" if r["images"] else "이미지 없음 · PDF 링크만")
    notes.append(f"index.html: 문항 {r['questions']} / {r['size']/2**20:.1f}MB ({mode})")
    return notes


def _repo_url() -> str | None:
    repo = os.environ.get("GITHUB_REPOSITORY")          # 예: 계정/저장소
    return f"https://github.com/{repo}" if repo else None


def _upload_url() -> str | None:
    """GitHub 웹의 '이 폴더에 파일 올리기' 화면으로 바로 가는 주소."""
    repo = _repo_url()
    if not repo:
        return None
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    return f"{repo}/upload/{branch}/pdfs"


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

        swept = sweep_repo_root(ROOT, pdf_dir)
        if swept:
            print(f"정리: 저장소 맨 위의 PDF {len(swept)}개를 pdfs/ 로 이동")

        results = []
        if os.path.isdir(pdf_dir):
            results = ingest_paths(conn, [pdf_dir], force=force)
            # 특정 연도(폴더)만 처음부터 다시 파싱 — 그 연도에서 이상을
            # 발견했을 때 전체를 건드리지 않고 고치는 관리 스위치다.
            target = os.environ.get("GICHUL_TARGET", "").strip()
            if target and not force:
                picked = target_files(pdf_dir, target)
                print(f"대상 재파싱: '{target}' → {len(picked)}개 파일")
                results += ingest_paths(conn, picked, force=True)
        moved = sort_into_year_folders(conn, pdf_dir) if os.path.isdir(pdf_dir) else []
        if moved:
            print(f"정리: {len(moved)}개 파일을 연도 폴더로 이동")
        moved = swept + moved
        fixed = repair_meta_from_filenames(conn, pdf_dir) if os.path.isdir(pdf_dir) else []

        # 파서가 좋아졌으면(PARSER_VERSION 인상) 옛 버전으로 파싱된 시험지를
        # 알아서 다시 파싱한다. force 를 손으로 켤 필요가 없다.
        if not force:
            stale = [row["path"] for row in conn.execute(
                "SELECT path FROM exams WHERE COALESCE(parser,0) < ?",
                (PARSER_VERSION,)) if os.path.isfile(row["path"])]
            if stale:
                print(f"파서 개선(v{PARSER_VERSION}): 시험지 {len(stale)}개를 다시 파싱")
                results += ingest_paths(conn, stale, force=True)

        pruned = prune_missing(conn, os.environ.get("GICHUL_PRUNE") == "1")
        if pruned:
            print(f"정리: 원본이 없는 시험지 {len(pruned)}개를 색인에서 뺌")

        n = export_jsonl(conn, archive)
        print(f"저장: 시험지 {n}개 → {archive} "
              f"({os.path.getsize(archive)/2**20:.2f}MB)")

        write_report(conn, os.path.join(data_dir, "REPORT.md"), results, fixed,
                     pruned, moved)
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
