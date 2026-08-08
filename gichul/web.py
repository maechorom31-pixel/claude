"""표준 라이브러리만 쓰는 최소 웹 UI.

  python -m gichul web  ->  http://127.0.0.1:8765
  · 과목 선택 -> 단어 검색 -> 출처와 함께 결과
  · 결과를 누르면 원본 PDF에서 그 문항만 오려 보여준다 (그림·표 포함)
  · PDF 업로드하면 바로 색인에 쌓임
"""

from __future__ import annotations

import html
import os
import re
import shutil
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

from . import index as idx
from .normalize import readable
from .pipeline import ingest_file

LIBRARY = os.environ.get("GICHUL_LIBRARY", os.path.expanduser("~/.gichul/library"))

_CSS = """
:root{color-scheme:light dark}
body{max-width:62rem;margin:2rem auto;padding:0 1rem;
 font:15px/1.65 -apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif}
h1{font-size:1.3rem;margin-bottom:.2rem}
h1 a{color:inherit;text-decoration:none}
.sub{opacity:.6;font-size:.85rem;margin-bottom:1.5rem}
form.search{display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:1rem}
input[type=text]{flex:1;min-width:16rem;padding:.55rem .7rem;font-size:1rem}
select,button{padding:.55rem .7rem;font-size:1rem}
a.card{display:block;color:inherit;text-decoration:none;
 border:1px solid rgba(128,128,128,.35);border-radius:8px;
 padding:.7rem .9rem;margin:.6rem 0}
a.card:hover{border-color:#4a90d9;background:rgba(74,144,217,.07)}
.src{font-weight:600}
.meta{opacity:.55;font-size:.8rem;margin-left:.4rem}
.snip{margin-top:.35rem}
mark{background:#ffe066;color:#000;padding:0 .1em;border-radius:2px}
table{border-collapse:collapse;margin:.5rem 0 1.5rem;font-size:.9rem}
td,th{border:1px solid rgba(128,128,128,.35);padding:.3rem .6rem;text-align:left}
.upload{margin-top:2.5rem;padding-top:1rem;border-top:1px solid rgba(128,128,128,.3)}
.flash{background:rgba(120,200,120,.15);border-radius:6px;padding:.6rem .9rem}
img.clip{max-width:100%;border:1px solid rgba(128,128,128,.35);border-radius:6px;
 background:#fff;margin:.4rem 0}
pre.text{white-space:pre-wrap;background:rgba(128,128,128,.09);
 border-radius:6px;padding:.8rem;font:13px/1.6 ui-monospace,monospace}
.warn{font-size:.85rem;opacity:.7}
"""


def _shell(title: str, body: str) -> bytes:
    return (f'<!doctype html><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{html.escape(title)}</title><style>{_CSS}</style>"
            f'<h1><a href="/">기출 문항 검색</a></h1>{body}').encode("utf-8")


def _highlight(text: str, spans: list[tuple[int, int]], width: int = 90) -> str:
    text = readable(text)
    if not spans:
        return html.escape(text[:200].replace("\n", " "))
    a, b = spans[0]
    lo, hi = max(0, a - width), min(len(text), b + width)
    out = (("…" if lo else "") + html.escape(text[lo:a]) + "<mark>"
           + html.escape(text[a:b]) + "</mark>" + html.escape(text[b:hi])
           + ("…" if hi < len(text) else ""))
    return out.replace("\n", " ")


def _table_html(rows: list[list[str]]) -> str:
    ncol = max(len(r) for r in rows)
    out = ["<table>"]
    for i, r in enumerate(rows):
        tag = "th" if i == 0 else "td"
        cells = "".join(f"<{tag}>{html.escape(readable(r[j] if j < len(r) else ''))}</{tag}>"
                        for j in range(ncol))
        out.append(f"<tr>{cells}</tr>")
    out.append("</table>")
    return "".join(out)


def _search_page(conn, q: str, subject: str, flash: str = "") -> bytes:
    s = idx.stats(conn)
    options = "".join(
        f'<option value="{html.escape(name)}"'
        f'{" selected" if name == subject else ""}>{html.escape(name)} ({n})</option>'
        for name, n, _qn in idx.subjects(conn) if name != "(미상)")

    parts = [
        f'<div class="sub">시험지 {s["exams"]}개 · 문항 {s["questions"]}개 · '
        f'띄어쓰기를 무시하고 찾습니다 (<code>빛에너지</code> = <code>빛 에너지</code>)</div>',
        '<form class="search" method="get" action="/">'
        f'<select name="subject"><option value="">전체 과목</option>{options}</select>'
        f'<input type="text" name="q" value="{html.escape(q)}" '
        'placeholder="찾을 단어·표현" autofocus>'
        '<button type="submit">검색</button></form>',
    ]
    if flash:
        parts.append(f'<div class="flash">{flash}</div>')

    if q:
        hits = idx.search(conn, q, subject=subject or None, limit=200)
        if not hits:
            parts.append(f"<p>‘{html.escape(q)}’ 결과 없음.</p>")
        else:
            forms, ambiguous = idx.variants(hits)
            total = sum(c for _f, c, _w in forms)
            parts.append(f"<p><b>{len(hits)}</b>개 문항 · <b>{total}</b>회 등장</p>")
            if len(forms) > 1 or ambiguous:
                rows = "".join(
                    f"<tr><td><code>{html.escape(f)}</code></td><td>{c}회</td>"
                    f"<td>{c * 100 // max(1, total)}%</td></tr>" for f, c, _w in forms)
                if ambiguous:
                    rows += ("<tr><td colspan=3><small>줄바꿈에 걸려 판정 불가 "
                             f"{ambiguous}건 제외</small></td></tr>")
                parts.append("<table><tr><th>실제 표기</th><th>횟수</th><th>비중</th>"
                             f"</tr>{rows}</table>")
            back = f"?q={quote(q)}&subject={quote(subject)}"
            for h in hits:
                eye = " 🔍" if h.has_image else ""
                parts.append(
                    f'<a class="card" href="/q?id={h.segment_id}&back={quote(back)}">'
                    f'<span class="src">{html.escape(h.source)}{eye}</span>'
                    f'<span class="meta">p.{h.page} · {html.escape(h.filename)}</span>'
                    f'<div class="snip">{_highlight(h.text, h.spans)}</div></a>')

    parts.append(
        '<div class="upload"><h2 style="font-size:1rem">모의고사 추가</h2>'
        '<form method="post" action="/upload" enctype="multipart/form-data">'
        '<input type="file" name="pdf" accept="application/pdf" multiple required>'
        '<button type="submit">업로드 &amp; 색인</button></form>'
        '<div class="sub" style="margin-top:.5rem">파일명에 '
        '<code>2026_6월모평_생명과학1.pdf</code> 처럼 적어 두면 출처를 더 정확히 잡습니다.'
        "</div></div>")
    return _shell("기출 문항 검색", "".join(parts))


def _detail_page(conn, segment_id: int, back: str) -> bytes:
    from .render import segment_parts
    row = idx.get_segment(conn, segment_id)
    if row is None:
        return _shell("없는 문항", "<p>그런 문항이 없습니다.</p>")

    src = idx.segment_source(row)
    parts = [f'<div class="sub">{html.escape(src)} · p.{row["page"]} · '
             f'{html.escape(row["filename"])}</div>']
    if back:
        parts.append(f'<p><a href="/{html.escape(back)}">← 검색 결과로</a></p>')

    if os.path.exists(row["path"]):
        for i in range(segment_parts(row)):
            parts.append(f'<img class="clip" src="/img?id={segment_id}&i={i}" '
                         f'alt="{html.escape(src)} 발췌">')
        parts.append(f'<p class="sub"><a href="/img?id={segment_id}&full=1" '
                     f'target="_blank">이 문항이 있는 쪽 전체 보기</a></p>')
    else:
        parts.append('<p class="warn">원본 PDF를 찾을 수 없어 이미지를 만들 수 '
                     f'없습니다.<br><code>{html.escape(row["path"])}</code></p>')

    for tb in idx.tables_of(row):
        parts.append(_table_html(tb))

    parts.append("<h2 style='font-size:1rem'>추출된 텍스트</h2>")
    parts.append(f'<pre class="text">{html.escape(readable(row["text"]))}</pre>')
    return _shell(src, "".join(parts))


def _parse_multipart(body: bytes, boundary: bytes) -> list[tuple[str, bytes]]:
    """(파일명, 내용) 목록. 단순 파일 업로드만 다룬다."""
    out: list[tuple[str, bytes]] = []
    for part in body.split(b"--" + boundary):
        if b"\r\n\r\n" not in part:
            continue
        head, data = part.split(b"\r\n\r\n", 1)
        m = re.search(rb'filename="([^"]*)"', head)
        if not m or not m.group(1):
            continue
        out.append((m.group(1).decode("utf-8", "replace"), data.rstrip(b"\r\n-")))
    return out


class _Handler(BaseHTTPRequestHandler):
    db_path = idx.DEFAULT_DB
    server_version = "gichul"

    def log_message(self, fmt, *args):        # 조용히
        pass

    def _send(self, payload: bytes, code: int = 200,
              ctype: str = "text/html; charset=utf-8") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        conn = idx.connect(self.db_path)
        try:
            if u.path == "/":
                self._send(_search_page(conn, qs.get("q", [""])[0],
                                        qs.get("subject", [""])[0]))
            elif u.path == "/q":
                self._send(_detail_page(conn, int(qs.get("id", ["0"])[0]),
                                        qs.get("back", [""])[0]))
            elif u.path == "/img":
                self._send_image(conn, qs)
            else:
                self._send(b"not found", 404, "text/plain")
        except (ValueError, KeyError):
            self._send(b"bad request", 400, "text/plain")
        finally:
            conn.close()

    def _send_image(self, conn, qs: dict) -> None:
        from .render import render_page, render_segment
        row = idx.get_segment(conn, int(qs.get("id", ["0"])[0]))
        if row is None or not os.path.exists(row["path"]):
            self._send(b"no source pdf", 404, "text/plain")
            return
        if qs.get("full"):
            png = render_page(row["path"], row["page"])
        else:
            png = render_segment(row, int(qs.get("i", ["0"])[0]), zoom=2.0)
        self._send(png, 200, "image/png")

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/upload":
            self._send(b"not found", 404, "text/plain")
            return
        m = re.search(r"boundary=([^;]+)", self.headers.get("Content-Type", ""))
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if not m:
            self._send(b"bad request", 400, "text/plain")
            return

        os.makedirs(LIBRARY, exist_ok=True)
        conn = idx.connect(self.db_path)
        notes = []
        try:
            for filename, data in _parse_multipart(body, m.group(1).strip('"').encode()):
                safe = re.sub(r"[^\w.\-가-힣 ]", "_", os.path.basename(filename))
                dest = os.path.join(LIBRARY, safe)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(data)
                shutil.move(tmp.name, dest)
                r = ingest_file(conn, dest, force=False)
                if r.status == "failed":
                    notes.append(f"✗ {html.escape(safe)}: {html.escape(r.error or '')}")
                elif r.status == "skipped":
                    notes.append(f"– {html.escape(safe)}: 이미 색인된 파일")
                else:
                    src = r.meta.source_label("").rstrip(" ·") if r.meta else "출처미상"
                    warn = "".join(f"<br><small>! {html.escape(w)}</small>"
                                   for w in (r.warnings or []))
                    notes.append(f"✓ {html.escape(safe)} → {html.escape(src)} "
                                 f"· 문항 {r.n_questions}개{warn}")
            self._send(_search_page(conn, "", "", flash="<br>".join(notes) or "파일 없음"))
        finally:
            conn.close()


def serve(db_path: str = idx.DEFAULT_DB, host: str = "127.0.0.1", port: int = 8765) -> None:
    _Handler.db_path = db_path
    idx.connect(db_path).close()
    print(f"http://{host}:{port}  (Ctrl+C 로 종료)   DB: {db_path}")
    ThreadingHTTPServer((host, port), _Handler).serve_forever()
