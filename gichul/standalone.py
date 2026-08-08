"""색인을 파일 하나짜리 HTML로 묶는다.

문항 텍스트와 지면 이미지를 안에 넣어 두고 검색은 브라우저에서 돈다.
파이썬도 서버도 없이 열리므로, 남에게 보내거나 통째로 보관할 때 쓴다.

검색·표기 집계 규칙은 normalize.py / index.variants 와 같은 것을 자바스크립트로
옮겨 놓았다. 한쪽만 고치면 결과가 달라지므로 함께 손봐야 한다.
"""

from __future__ import annotations

import base64
import json
import os
import sqlite3

import pymupdf

from . import index as idx
from . import render

ZOOM, QUALITY = 1.5, 68        # 지면 이미지 해상도와 JPEG 품질

# 지면 이미지는 문항당 30~90 KiB 다. 과목을 늘려 가면 수천 문항이 되므로
# 예산을 넘으면 이미지를 빼고 텍스트만 담는다. 검색·용례는 그대로 된다.
DEFAULT_MAX_MB = 12
_EST_BYTES_PER_IMAGE = 55_000


def _clip_jpeg(row, part: int = 0) -> bytes | None:
    rs = render.rects_of(row)
    if not rs:
        return None
    page, x0, y0, x1, y1 = rs[min(part, len(rs) - 1)]
    doc = pymupdf.open(row["path"])
    try:
        p = doc.load_page(int(page) - 1)
        rect = pymupdf.Rect(x0, y0, x1, y1) & p.rect
        if rect.is_empty:
            return None
        pix = p.get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM), clip=rect)
        return pix.tobytes("jpeg", jpg_quality=QUALITY)
    finally:
        doc.close()


def build(conn: sqlite3.Connection, out_path: str, *,
          subject: str | None = None, year: int | None = None,
          exam: str | None = None, images: bool | None = None,
          max_mb: float = DEFAULT_MAX_MB,
          pdf_base_url: str | None = None, pdf_root: str | None = None,
          upload_url: str | None = None) -> dict:
    """자립형 HTML을 쓰고 요약을 돌려준다.

    images=None 이면 예산(max_mb)에 맞는지 보고 알아서 정한다.
    필터를 주면 그 범위만 담는다. 과목이 늘어나면 통째로 담는 대신
    `--subject 국어` 처럼 갈라 뽑는 쪽이 현실적이다.

    pdf_base_url + pdf_root 를 주면 각 문항에 원본 PDF 링크가 붙는다.
    (pdf_root 아래에 실제로 존재하는 파일만. 예: GitHub blob 주소)
    """
    from urllib.parse import quote

    from .meta import subject_aliases, subject_sort_key

    where, params = ["s.kind='question'"], []
    if subject:
        aliases = sorted(subject_aliases(subject))
        where.append("e.subject IN (%s)" % ",".join("?" * len(aliases)))
        params += aliases
    if year:
        where.append("e.year=?")
        params.append(year)
    if exam:
        where.append("e.exam LIKE ?")
        params.append(f"%{exam}%")
    clause = " AND ".join(where)

    n_questions = conn.execute(
        f"SELECT COUNT(*) FROM segments s JOIN exams e ON e.id=s.exam_id WHERE {clause}",
        params).fetchone()[0]
    if images is None:
        images = n_questions * _EST_BYTES_PER_IMAGE <= max_mb * 2 ** 20

    papers, items = {}, []
    total_bytes = 0

    for e in conn.execute(
            "SELECT DISTINCT e.* FROM exams e JOIN segments s ON s.exam_id=e.id "
            f"WHERE {clause} ORDER BY e.subject", params):
        papers[e["id"]] = {"subject": e["subject"], "year": e["year"],
                           "exam": e["exam"], "grade": e["grade"],
                           "pages": e["n_pages"], "questions": e["n_questions"]}

    rows = conn.execute(
        f"SELECT s.id FROM segments s JOIN exams e ON e.id=s.exam_id WHERE {clause} "
        "ORDER BY s.exam_id, s.number", params).fetchall()
    for r in rows:
        row = idx.get_segment(conn, r["id"])
        imgs = []
        # 원본 PDF를 지운 시험지는 텍스트만 담는다. 용량 정리로 PDF를 지워도
        # 색인 전체가 죽지 않아야 계속 쌓아 갈 수 있다.
        if images and os.path.exists(row["path"]):
            for part in range(render.segment_parts(row)):
                jpg = _clip_jpeg(row, part)
                if jpg:
                    total_bytes += len(jpg)
                    imgs.append("data:image/jpeg;base64,"
                                + base64.b64encode(jpg).decode())
        pdf_url = None
        if pdf_base_url and pdf_root and os.path.exists(row["path"]):
            rel = os.path.relpath(row["path"], pdf_root)
            if not rel.startswith(".."):
                rel = "/".join(quote(seg) for seg in rel.split(os.sep))
                pdf_url = f"{pdf_base_url}/{rel}"

        items.append({
            "id": row["id"],
            "pdf": pdf_url,
            "src": idx.segment_source(row),
            "subject": row["subject"],
            "num": row["number"],
            "page": row["page"],
            "text": row["text"],
            "tables": idx.tables_of(row),
            "imgs": imgs,
        })

    counts: dict[str, int] = {}
    for it in items:
        counts[it["subject"]] = counts.get(it["subject"], 0) + 1

    data = {"papers": list(papers.values()), "items": items, "counts": counts,
            "order": sorted(counts, key=subject_sort_key),
            "upload": upload_url, "images": bool(images)}
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    html = _TEMPLATE.replace("/*__DATA__*/", "window.GICHUL=" + payload + ";")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return {"questions": len(items), "papers": len(papers), "images": bool(images),
            "image_bytes": total_bytes, "size": os.path.getsize(out_path)}


_TEMPLATE = r"""<title>기출 용례 검색</title>
<style>
/* ── 팔레트: 시험지 지면에서 가져왔다.
      바탕은 인쇄 용지, 글자는 잉크, 강조는 형광펜 연두, 소수 표기는 첨삭 빨강. */
:root{
  --paper:#F6F7F4; --card:#FFFFFF; --sunken:#EEF0EA;
  --ink:#1A1C18; --ink-soft:#5B6058; --ink-faint:#858C80;
  --rule:#D5D9D0; --rule-strong:#B9BFB2;
  --mark:#C8E24B; --mark-ink:#1A1C18;
  --pen:#C33A2C;
  --focus:#5C7A1E;
  --serif:"Nanum Myeongjo","AppleMyungjo","Batang",Batang,"Times New Roman",serif;
  --sans:"Pretendard","Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",
         system-ui,-apple-system,sans-serif;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --paper:#141713; --card:#1C201A; --sunken:#22261F;
    --ink:#E9ECE4; --ink-soft:#9AA396; --ink-faint:#767E71;
    --rule:#333A30; --rule-strong:#4A533F;
    --mark:#AFC93A; --mark-ink:#12150F;
    --pen:#E87766;
    --focus:#B6D24F;
  }
}
:root[data-theme="dark"]{
  --paper:#141713; --card:#1C201A; --sunken:#22261F;
  --ink:#E9ECE4; --ink-soft:#9AA396; --ink-faint:#767E71;
  --rule:#333A30; --rule-strong:#4A533F;
  --mark:#AFC93A; --mark-ink:#12150F;
  --pen:#E87766;
  --focus:#B6D24F;
}

*{box-sizing:border-box}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font:16px/1.6 var(--sans);
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:60rem;margin:0 auto;padding:2.5rem 1.25rem 5rem}

/* ── 머리 */
.eyebrow{
  font-size:.72rem; letter-spacing:.14em; text-transform:uppercase;
  color:var(--ink-faint); margin:0 0 .6rem;
}
h1{
  font:600 clamp(1.6rem,4vw,2.3rem)/1.2 var(--serif);
  margin:0 0 .5rem; text-wrap:balance; letter-spacing:-.01em;
}
h1 .hl{background:var(--mark);color:var(--mark-ink);padding:0 .12em}
.lede{
  margin:0 0 2rem; max-width:38em; color:var(--ink-soft); font-size:1rem;
}
.lede b{color:var(--ink);font-weight:600}

/* ── 검색부 */
.search{
  position:sticky; top:0; z-index:5;
  background:var(--paper);
  padding:.9rem 0 1rem; margin-bottom:.5rem;
  border-bottom:1px solid var(--rule);
}
.field{display:flex; gap:.5rem; align-items:stretch}
#q{
  flex:1; min-width:0; font:1.05rem/1 var(--sans); color:var(--ink);
  padding:.75rem .9rem; background:var(--card);
  border:1px solid var(--rule-strong); border-radius:2px;
}
#q::placeholder{color:var(--ink-faint)}
#q:focus-visible,button:focus-visible,summary:focus-visible,.chip:focus-visible{
  outline:2px solid var(--focus); outline-offset:2px;
}
button.go{
  font:600 .95rem var(--sans); color:var(--mark-ink); background:var(--mark);
  border:1px solid transparent; border-radius:2px; padding:.75rem 1.2rem;
  cursor:pointer;
}
.rowlabel{
  font-size:.72rem; letter-spacing:.1em; text-transform:uppercase;
  color:var(--ink-faint); margin:.9rem 0 .4rem;
}
.chips{display:flex; flex-wrap:wrap; gap:.35rem}
.chip{
  font:.85rem var(--sans); color:var(--ink-soft); cursor:pointer;
  background:transparent; border:1px solid var(--rule-strong);
  border-radius:2px; padding:.3rem .6rem;
}
.chip:hover{border-color:var(--ink-soft); color:var(--ink)}
.chip[aria-pressed="true"]{
  background:var(--ink); color:var(--paper); border-color:var(--ink);
}
.chip .n{color:var(--ink-faint); font-variant-numeric:tabular-nums; margin-left:.3em}
.chip[aria-pressed="true"] .n{color:var(--rule-strong)}

/* ── 요약: 표기 분포 */
.summary{margin:1.6rem 0 0}
.count{font-size:.95rem; color:var(--ink-soft); margin:0 0 .9rem}
.count b{color:var(--ink); font-variant-numeric:tabular-nums}
.dist{border:1px solid var(--rule); background:var(--card); border-radius:2px;
  padding:1rem 1.1rem; margin:0 0 1.6rem}
.dist h2{font:600 .8rem/1 var(--sans); letter-spacing:.08em; text-transform:uppercase;
  color:var(--ink-faint); margin:0 0 .8rem}
.bar{display:flex; height:.6rem; border-radius:1px; overflow:hidden;
  background:var(--sunken); margin-bottom:.9rem}
.bar span{display:block}
.forms{list-style:none; margin:0; padding:0; display:grid; gap:.45rem}
.forms li{display:grid; grid-template-columns:auto 1fr auto; gap:.7rem;
  align-items:baseline; font-size:.92rem}
.swatch{width:.7rem;height:.7rem;border-radius:1px;align-self:center}
.form{font-family:var(--serif); font-size:1.02rem}
.form.dominant{background:var(--mark); color:var(--mark-ink); padding:0 .2em}
.pct{color:var(--ink-soft); font-variant-numeric:tabular-nums; font-size:.86rem}
.caveat{margin:.9rem 0 0; padding-top:.75rem; border-top:1px solid var(--rule);
  font-size:.82rem; color:var(--ink-soft)}
.caveat b{color:var(--pen); font-weight:600}
.verdict{margin:.9rem 0 0; font-size:.95rem}
.verdict .lead{color:var(--ink-faint)}

/* ── 결과 */
.results{display:grid; gap:.6rem; margin-top:.4rem}
details.hit{
  background:var(--card); border:1px solid var(--rule); border-radius:2px;
}
details.hit[open]{border-color:var(--rule-strong)}
summary.head{
  cursor:pointer; padding:.75rem .95rem; display:grid; gap:.3rem;
  list-style:none;
}
summary.head::-webkit-details-marker{display:none}
summary.head:hover{background:var(--sunken)}
.src{display:flex; flex-wrap:wrap; gap:.5rem; align-items:baseline}
.srctext{font:600 .92rem var(--sans)}
.qno{
  font:600 .78rem var(--sans); font-variant-numeric:tabular-nums;
  background:var(--sunken); color:var(--ink-soft);
  border:1px solid var(--rule); border-radius:1px; padding:.05rem .4rem;
}
.where{font-size:.78rem; color:var(--ink-faint); font-variant-numeric:tabular-nums}
.snip{font-family:var(--serif); font-size:1rem; line-height:1.55; color:var(--ink-soft)}
.snip mark{background:var(--mark); color:var(--mark-ink); padding:0 .1em; border-radius:0}
.body{padding:0 .95rem 1.1rem; border-top:1px solid var(--rule)}
.body .rowlabel{margin-top:1rem}
img.clip{
  display:block; max-width:100%; height:auto; background:#fff;
  border:1px solid var(--rule); border-radius:1px;
}
.tblwrap{overflow-x:auto}
table{border-collapse:collapse; font-size:.86rem; font-variant-numeric:tabular-nums}
th,td{border:1px solid var(--rule-strong); padding:.3rem .55rem; text-align:left}
th{background:var(--sunken); font-weight:600}
pre.raw{
  white-space:pre-wrap; word-break:break-word; margin:0;
  background:var(--sunken); border-radius:2px; padding:.8rem;
  font:.82rem/1.6 ui-monospace,SFMono-Regular,Menlo,monospace; color:var(--ink-soft);
  max-height:22rem; overflow:auto;
}
.empty{color:var(--ink-soft); padding:2rem 0; font-size:.95rem}
.empty code{background:var(--sunken); padding:.1em .35em}

footer{
  margin-top:3.5rem; padding-top:1.2rem; border-top:1px solid var(--rule);
  font-size:.82rem; color:var(--ink-faint);
}
footer p{margin:.35rem 0}
footer b{color:var(--ink-soft); font-weight:600}
@media (prefers-reduced-motion:no-preference){
  details.hit{transition:border-color .15s ease}
}
</style>

<div class="wrap">
  <p class="eyebrow">평가원·교육청 기출</p>
  <h1>기출 <span class="hl">용례</span> 검색</h1>
  <p class="lede" id="lede"></p>

  <div class="search">
    <form class="field" id="form">
      <input id="q" type="search" placeholder="찾을 낱말이나 표현" autocomplete="off"
             aria-label="찾을 낱말이나 표현">
      <button class="go" type="submit">찾기</button>
    </form>
    <p class="rowlabel">과목</p>
    <div class="chips" id="subjects"></div>
  </div>

  <div class="summary" id="summary"></div>
  <div class="results" id="results"></div>

  <footer id="foot"></footer>
</div>

<script>
/*__DATA__*/
</script>
<script>
(function(){
  "use strict";
  const DATA = window.GICHUL;
  const OBJ = "￼";
  const FOLD = {"‐":"-","‑":"-","‒":"-","–":"-","—":"-",
    "―":"-","−":"-","‘":"'","’":"'","“":'"',"”":'"',
    "～":"~","〜":"~"};

  // normalize.py 의 nospace_map 과 같은 규칙: 공백과 '읽지 못한 자리'를 빼고,
  // 키의 각 글자가 원문 몇 번째였는지 함께 들고 다닌다.
  function nospaceMap(text){
    const buf = [], idx = [];
    for (let i = 0; i < text.length; i++){
      const ch = text[i];
      if (ch === OBJ || /\s/.test(ch)) continue;
      buf.push(FOLD[ch] || ch);
      idx.push(i);
    }
    return {key: buf.join(""), idx: idx};
  }
  function queryKey(q){ return nospaceMap(q.normalize("NFC")).key; }

  // 문항마다 정규화를 매번 다시 하면 수천 문항에서 글자 하나에 1초가 넘게
  // 걸린다. 키와 위치 매핑을 로드 때 한 번만 만들어 둔다.
  for (const it of DATA.items){
    const m = nospaceMap(it.text);
    it._key = m.key;
    it._idx = m.idx;
  }

  function findSpans(it, query){
    const key = queryKey(query);
    if (!key) return [];
    const out = [];
    let from = 0;
    for (;;){
      const pos = it._key.indexOf(key, from);
      if (pos < 0) break;
      out.push([it._idx[pos], it._idx[pos + key.length - 1] + 1]);
      from = pos + 1;
    }
    return out;
  }

  const readable = t => t.split(OBJ).join("□");
  const esc = t => t.replace(/[&<>"]/g, c =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

  function search(query, subject){
    const out = [];
    for (const it of DATA.items){
      if (subject && it.subject !== subject) continue;
      const spans = findSpans(it, query);
      if (spans.length) out.push({it: it, spans: spans});
    }
    return out;
  }

  // 줄바꿈이나 읽지 못한 수식을 사이에 둔 경우는 띄어쓰기를 판정할 수 없다.
  function variants(hits){
    const counts = new Map(), where = new Map();
    let ambiguous = 0;
    for (const h of hits){
      for (const [a, b] of h.spans){
        const raw = h.it.text.slice(a, b);
        if (raw.includes("\n") || raw.includes(OBJ)){ ambiguous++; continue; }
        const form = raw.replace(/[ \t]+/g, " ");
        counts.set(form, (counts.get(form) || 0) + 1);
        if (!where.has(form)) where.set(form, []);
        const w = where.get(form);
        if (w.length < 3 && !w.includes(h.it.src)) w.push(h.it.src);
      }
    }
    const forms = [...counts.entries()]
      .map(([f, c]) => ({form: f, count: c, where: where.get(f)}))
      .sort((x, y) => y.count - x.count || x.form.localeCompare(y.form));
    return {forms: forms, ambiguous: ambiguous};
  }

  function snippet(text, spans, width){
    const [a, b] = spans[0];
    const lo = Math.max(0, a - width), hi = Math.min(text.length, b + width);
    return (lo > 0 ? "…" : "")
      + esc(readable(text.slice(lo, a))) + "<mark>"
      + esc(readable(text.slice(a, b))) + "</mark>"
      + esc(readable(text.slice(b, hi)))
      + (hi < text.length ? "…" : "");
  }

  const SHADES = ["var(--mark)", "var(--rule-strong)", "var(--ink-faint)",
                  "var(--pen)", "var(--sunken)"];

  const elQ = document.getElementById("q");
  const elSummary = document.getElementById("summary");
  const elResults = document.getElementById("results");
  let subject = "";

  function renderSummary(query, hits){
    if (!query){ elSummary.innerHTML = ""; return; }
    if (!hits.length){
      elSummary.innerHTML = "";
      elResults.innerHTML = '<p class="empty">‘' + esc(query)
        + '’ 는 이 4과목에 없습니다. <code>옳은것만을</code>, <code>마그마</code>'
        + ' 같은 낱말로 해 보세요.</p>';
      return;
    }
    const v = variants(hits);
    const total = v.forms.reduce((s, f) => s + f.count, 0);
    let html = '<p class="count"><b>' + hits.length + '</b>개 문항에서 <b>'
      + (total + v.ambiguous) + '</b>회 등장</p>';

    if (v.forms.length){
      const bar = v.forms.map((f, i) =>
        '<span style="width:' + (f.count * 100 / total) + '%;background:'
        + SHADES[Math.min(i, SHADES.length - 1)] + '"></span>').join("");
      const rows = v.forms.map((f, i) =>
        '<li><span class="swatch" style="background:'
        + SHADES[Math.min(i, SHADES.length - 1)] + '"></span>'
        + '<span class="form' + (i === 0 && v.forms.length > 1 ? " dominant" : "")
        + '">' + esc(readable(f.form)) + '</span>'
        + '<span class="pct">' + f.count + '회 · '
        + Math.round(f.count * 100 / total) + '%</span></li>').join("");

      const heading = v.ambiguous
        ? "실제로 어떻게 적혀 있었나 · 판정 가능한 " + total + "회"
        : "실제로 어떻게 적혀 있었나";
      html += '<div class="dist"><h2>' + heading + "</h2>"
        + '<div class="bar" role="presentation">' + bar + '</div>'
        + '<ul class="forms">' + rows + '</ul>';

      if (v.forms.length > 1){
        html += '<p class="verdict"><span class="lead">우세 표기 &rarr;</span> '
          + '<b>' + esc(readable(v.forms[0].form)) + '</b> '
          + '<span class="pct">(' + v.forms[0].where[0] + ' 등)</span></p>';
      }
      if (v.ambiguous){
        html += '<p class="caveat"><b>' + v.ambiguous + '회는 판정에서 빼두었습니다.</b> '
          + '줄바꿈이나 수식이 사이에 끼어, 원래 붙여 쓴 건지 띄어 쓴 건지 '
          + '지면만 봐서는 알 수 없는 자리입니다.</p>';
      }
      html += "</div>";
    }
    elSummary.innerHTML = html;
  }

  const RENDER_CAP = 200;   // 카드 수천 장을 그리면 그리기 자체가 1초를 넘긴다

  function renderResults(hits){
    if (!hits.length) return;
    const shown = hits.slice(0, RENDER_CAP);
    const more = hits.length - shown.length;
    elResults.innerHTML = shown.map(h => {
      const it = h.it;
      const imgs = it.imgs.map((_, i) =>
        '<img class="clip" data-src="' + i + '" data-id="' + it.id
        + '" alt="' + esc(it.src) + ' 지면">').join("");
      const tables = (it.tables || []).map(tb => {
        const ncol = Math.max.apply(null, tb.map(r => r.length));
        const rows = tb.map((r, ri) => {
          const tag = ri === 0 ? "th" : "td";
          let cells = "";
          for (let j = 0; j < ncol; j++)
            cells += "<" + tag + ">" + esc(readable(r[j] || "")) + "</" + tag + ">";
          return "<tr>" + cells + "</tr>";
        }).join("");
        return '<div class="tblwrap"><table>' + rows + "</table></div>";
      }).join("");

      return '<details class="hit"><summary class="head">'
        + '<span class="src"><span class="qno">' + it.num + '번</span>'
        + '<span class="srctext">' + esc(it.src) + "</span>"
        + '<span class="where">p.' + it.page + "</span></span>"
        + '<span class="snip">' + snippet(it.text, h.spans, 55) + "</span>"
        + "</summary><div class='body'>"
        + (imgs ? '<p class="rowlabel">원본 지면</p>' + imgs : "")
        + (it.pdf ? '<p class="sub"><a class="orig" target="_blank" rel="noopener" href="'
            + esc(it.pdf) + '#page=' + it.page
            + '">원본 PDF에서 이 쪽 펼치기 (p.' + it.page + ')</a></p>' : "")
        + (tables ? '<p class="rowlabel">표</p>' + tables : "")
        + '<p class="rowlabel">추출된 텍스트</p>'
        + '<pre class="raw">' + esc(readable(it.text)) + "</pre>"
        + "</div></details>";
    }).join("") + (more ? '<p class="empty">' + more
      + '개 문항이 더 있습니다. 검색어를 좁히거나 과목을 고르세요.</p>' : "");

    // 이미지는 열 때 붙인다. 한꺼번에 그리면 첫 화면이 느려진다.
    const byId = new Map(DATA.items.map(i => [i.id, i]));
    elResults.querySelectorAll("details.hit").forEach(d => {
      d.addEventListener("toggle", () => {
        if (!d.open) return;
        d.querySelectorAll("img.clip[data-src]").forEach(img => {
          const it = byId.get(Number(img.dataset.id));
          img.src = it.imgs[Number(img.dataset.src)];
          img.removeAttribute("data-src");
        });
      });
    });
  }

  function run(){
    const query = elQ.value.trim();
    const hits = query ? search(query, subject) : [];
    if (!query){
      elSummary.innerHTML = "";
      elResults.innerHTML = '<p class="empty">위에 낱말을 넣거나 예시를 눌러 보세요.</p>';
      return;
    }
    renderSummary(query, hits);
    renderResults(hits);
  }

  // 머리말과 꼬리말은 실제로 담긴 내용에서 만든다. 과목이 늘어나도 문구가 어긋나지 않게.
  (function describe(){
    const papers = DATA.papers, n = DATA.items.length;
    const years = papers.map(p => p.year).filter(Boolean);
    const span = years.length
      ? (Math.min.apply(null, years) === Math.max.apply(null, years)
          ? Math.min.apply(null, years) + "학년도"
          : Math.min.apply(null, years) + "–" + Math.max.apply(null, years) + "학년도")
      : "";
    const subs = Object.keys(DATA.counts);
    document.getElementById("lede").innerHTML =
      (span ? esc(span) + " " : "") + "시험지 <b>" + papers.length + "개</b>, 과목 <b>"
      + subs.length + "개</b>, 문항 <b>" + n + "개</b>를 색인했습니다. "
      + "<code>빛에너지</code>로 찾으면 <code>빛 에너지</code>도 나오고, "
      + "<b>어느 표기가 몇 번 쓰였는지</b> 세어 줍니다."
      + (DATA.images ? " 문항을 누르면 원본 지면이 그대로 나옵니다." : "");

    const notes = [
      "<p><b>□ 는 읽지 못한 수식 자리입니다.</b> 시험지는 수식을 전용 글꼴로 찍어 "
      + "유니코드 매핑이 없습니다. 수학·화학·물리처럼 수식이 많은 과목에서 두드러지고, "
      + "국어·영어·사탐은 거의 영향이 없습니다.</p>",
    ];
    if (DATA.upload){
      notes.push('<p><a class="orig" href="' + esc(DATA.upload)
        + '">PDF 추가하기</a> — 올리면 1~2분 뒤 자동 반영됩니다. '
        + '같은 파일은 알아서 건너뜁니다.</p>');
    }
    if (!DATA.images){
      notes.unshift("<p><b>이 파일에는 지면 이미지가 없습니다.</b> 문항 수가 많아 "
        + "텍스트만 담았습니다. 지면을 보려면 <code>gichul web</code> 을 쓰거나 "
        + "<code>--subject</code> 로 갈라 뽑으세요.</p>");
    }
    document.getElementById("foot").innerHTML = notes.join("");
  })();

  const subs = DATA.order || Object.keys(DATA.counts).sort();
  document.getElementById("subjects").innerHTML =
    '<button class="chip" type="button" data-sub="" aria-pressed="true">전체'
    + '<span class="n">' + DATA.items.length + "</span></button>"
    + subs.map(s => '<button class="chip" type="button" data-sub="' + esc(s)
        + '" aria-pressed="false">' + esc(s)
        + '<span class="n">' + DATA.counts[s] + "</span></button>").join("");
  document.getElementById("subjects").addEventListener("click", ev => {
    const b = ev.target.closest("[data-sub]");
    if (!b) return;
    subject = b.dataset.sub;
    document.querySelectorAll("[data-sub]").forEach(x =>
      x.setAttribute("aria-pressed", String(x === b)));
    run();
  });

  document.getElementById("form").addEventListener("submit", ev => {
    ev.preventDefault();
    run();
  });
  let pending = null;
  elQ.addEventListener("input", () => {
    clearTimeout(pending);
    pending = setTimeout(run, 120);
  });

  run();
})();
</script>
"""
