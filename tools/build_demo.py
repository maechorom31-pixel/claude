"""색인 DB -> 자립형 데모 HTML 생성.

  python3 tools/build_demo.py [색인DB] [출력.html]

파일 하나로 끝나는 HTML을 만든다. 문항 텍스트와 지면 이미지를 안에 넣어 두고
검색은 브라우저에서 돈다. 서버 없이 남에게 보여 주거나 보관할 때 쓴다.
검색·표기 집계 규칙은 gichul/normalize.py 와 같게 옮겨 두었다.
"""
from __future__ import annotations

import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymupdf

from gichul import index as idx, render

DB = sys.argv[1] if len(sys.argv) > 1 else idx.DEFAULT_DB
OUT = sys.argv[2] if len(sys.argv) > 2 else "gichul-demo.html"
ZOOM, QUALITY = 1.5, 68


def clip_jpeg(row, part=0):
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


def main() -> None:
    conn = idx.connect(DB)
    papers, items = {}, []
    total_bytes = 0

    for e in conn.execute("SELECT * FROM exams ORDER BY subject"):
        papers[e["id"]] = {"subject": e["subject"], "year": e["year"],
                           "exam": e["exam"], "grade": e["grade"],
                           "pages": e["n_pages"], "questions": e["n_questions"]}

    rows = conn.execute(
        "SELECT id FROM segments WHERE kind='question' ORDER BY exam_id, number").fetchall()
    for r in rows:
        row = idx.get_segment(conn, r["id"])
        imgs = []
        for part in range(render.segment_parts(row)):
            jpg = clip_jpeg(row, part)
            if jpg:
                total_bytes += len(jpg)
                imgs.append("data:image/jpeg;base64," + base64.b64encode(jpg).decode())
        items.append({
            "id": row["id"],
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

    data = {"papers": list(papers.values()), "items": items, "counts": counts}
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    html = TEMPLATE.replace("/*__DATA__*/", "window.GICHUL=" + payload + ";")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"문항 {len(items)}개 · 이미지 {total_bytes/2**20:.1f} MiB "
          f"· HTML {os.path.getsize(OUT)/2**20:.1f} MiB -> {OUT}")


TEMPLATE = r"""<title>기출 문항 검색 — 띄어쓰기를 몰라도 찾는다</title>
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
  <p class="eyebrow">기출 문항 검색기 · 데모</p>
  <h1><span class="hl">빛에너지</span>로 찾으면 <span class="hl">빛 에너지</span>도 나온다</h1>
  <p class="lede">
    2026학년도 7월 고3 전국연합학력평가 과학탐구 4과목, <b>문항 80개</b>를 실제로
    색인한 결과입니다. 띄어쓰기를 무시해 찾고, <b>어느 표기가 몇 번 쓰였는지</b>
    세어 주고, 누르면 원본 지면을 그대로 보여줍니다.
  </p>

  <div class="search">
    <form class="field" id="form">
      <input id="q" type="search" placeholder="찾을 낱말이나 표현" autocomplete="off"
             aria-label="찾을 낱말이나 표현">
      <button class="go" type="submit">찾기</button>
    </form>
    <p class="rowlabel">예시</p>
    <div class="chips" id="examples"></div>
    <p class="rowlabel">과목</p>
    <div class="chips" id="subjects"></div>
  </div>

  <div class="summary" id="summary"></div>
  <div class="results" id="results"></div>

  <footer>
    <p><b>이 데모는 실제 파서의 출력입니다.</b> 검색·표기 집계 방식은 파이썬 쪽
       <code>normalize.py</code> 와 같은 규칙을 옮긴 것이고, 문항 이미지는
       원본 PDF에서 좌표로 오려낸 것입니다.</p>
    <p><b>□ 는 읽지 못한 수식 자리입니다.</b> 시험지는 수식을 전용 글꼴로 찍어
       유니코드 매핑이 없습니다. 화학Ⅰ 10.7%, 물리학Ⅰ 4.9%, 생명과학Ⅰ 0.5%,
       지구과학Ⅰ 0.2%. 그래서 원본 지면 보기가 필요합니다.</p>
    <p>실제 도구는 명령줄과 로컬 웹 UI로 돌아가고, 시험지 500개를 쌓아도
       색인은 21–72 MiB 입니다.</p>
  </footer>
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

  function findSpans(text, query){
    const key = queryKey(query);
    if (!key) return [];
    const m = nospaceMap(text), out = [];
    let from = 0;
    for (;;){
      const pos = m.key.indexOf(key, from);
      if (pos < 0) break;
      out.push([m.idx[pos], m.idx[pos + key.length - 1] + 1]);
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
      const spans = findSpans(it.text, query);
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

  function renderResults(hits){
    if (!hits.length) return;
    elResults.innerHTML = hits.map(h => {
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
        + '<p class="rowlabel">원본 지면</p>' + imgs
        + (tables ? '<p class="rowlabel">표</p>' + tables : "")
        + '<p class="rowlabel">추출된 텍스트</p>'
        + '<pre class="raw">' + esc(readable(it.text)) + "</pre>"
        + "</div></details>";
    }).join("");

    // 이미지는 열 때 붙인다. 80장을 한꺼번에 그리면 첫 화면이 느려진다.
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

  // 예시는 이 4과목에서 실제로 무언가 보여 주는 것만 골랐다.
  const EXAMPLES = ["옳은것만을", "상리공생", "질량결손", "마그마", "적절한것은",
                    "3점", "화석연료"];
  document.getElementById("examples").innerHTML = EXAMPLES.map(e =>
    '<button class="chip" type="button" data-ex="' + esc(e) + '">'
    + esc(e) + "</button>").join("");
  document.getElementById("examples").addEventListener("click", ev => {
    const b = ev.target.closest("[data-ex]");
    if (!b) return;
    elQ.value = b.dataset.ex;
    run();
  });

  const subs = Object.keys(DATA.counts).sort();
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
  elQ.addEventListener("input", run);

  elQ.value = "옳은것만을";
  run();
})();
</script>
"""

if __name__ == "__main__":
    main()
