"""Review page for aligned amudim: the page image with the aligned text laid over it.

    python -m page_layout.viewer --out DIR "Bava Metzia" 2a-11b Kiddushin 3a-12b

Writes DIR/index.html + DIR/img/<amud>.jpg (downscaled). Modes: image with hidden selectable text,
word boxes, text only, text over faded image. Clicking a word highlights every line its Gemara
segment or comment covers (the unit the apps will highlight as the audio plays) and shows its ref.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

from . import fetch
from .run import OUT, parse_amudim

VIEW_W = 1400  # width of the published page images


def build(specs: list[tuple[str, list[tuple[int, str]]]], out: Path) -> Path:
    """specs: [(tractate, [(daf, amud), ...]), ...]"""
    (out / "img").mkdir(parents=True, exist_ok=True)
    pages = []
    for tractate, amudim in specs:
      for daf, amud in amudim:
        p = OUT / tractate / f"{daf}{amud}.json"
        if not p.exists():
            continue
        j = json.loads(p.read_text())
        W, H = j["image"]["w"], j["image"]["h"]
        im = cv2.imread(str(fetch.page_image(tractate, daf, amud)), cv2.IMREAD_GRAYSCALE)
        k = VIEW_W / W
        pid = f"{tractate.replace(' ', '_')}_{daf}{amud}"
        cv2.imwrite(str(out / "img" / f"{pid}.jpg"), cv2.resize(im, (VIEW_W, round(H * k)), interpolation=cv2.INTER_AREA),
                    [cv2.IMWRITE_JPEG_QUALITY, 60])

        def sc(b):
            return [round(v * k, 1) for v in b]
        streams = {}
        for s in ("gemara", "rashi", "tosafot"):
            streams[s] = [dict(b=sc(L["box"]), w=[[w["text"], sc(w["box"]), int(w.get("dh") or 0),
                                                   (w.get("toks") or [[None]])[0][0]]
                                                  for w in L["words"] if w.get("text")]) for L in j[s]]
        qc = j["qc"]
        pages.append(dict(id=pid, label=f"{tractate} {daf}{amud}", W=VIEW_W, H=round(H * k), s=streams,
                          seg={r: [sc(b) for b in bs] for r, bs in j["segments"].items()},
                          flags=qc["flags"],
                          stats={s: qc[s] for s in ("gemara", "rashi", "tosafot")}))
    html = TEMPLATE.replace("__DATA__", json.dumps(pages, ensure_ascii=False))
    (out / "index.html").write_text(html, encoding="utf-8")
    return out / "index.html"


TEMPLATE = r"""<title>Live-Text Daf</title>
<link href="https://fonts.googleapis.com/css2?family=Frank+Ruhl+Libre:wght@400;700&family=Noto+Rashi+Hebrew:wght@400;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#f6f4ef;--fg:#1d1b18;--muted:#6b665d;--card:#fff;--line:#ddd6c8;--gem:#2f6fd6;--rashi:#c2410c;--tos:#15803d;--hl:rgba(250,204,21,.5);--bad:#b42318}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#171614;--fg:#ece8df;--muted:#a39d91;--card:#211f1c;--line:#3a3630;--bad:#f97066}}
:root[data-theme=dark]{--bg:#171614;--fg:#ece8df;--muted:#a39d91;--card:#211f1c;--line:#3a3630;--bad:#f97066}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);padding-inline:16px;color:var(--fg);font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
header{padding-block:16px;max-width:1500px;margin:auto}
h1{font-size:20px;margin:0 0 4px}
p.sub{margin:0;color:var(--muted)}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:12px}
select,.seg{border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg);font:inherit}
select{padding:6px 8px}
.seg{display:inline-flex;overflow:hidden}
.seg button{border:0;background:none;color:var(--fg);padding:7px 12px;cursor:pointer;font:inherit}
.seg button.on{background:var(--fg);color:var(--bg)}
.nav{border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:8px;padding:6px 10px;cursor:pointer;font:inherit}
.chip{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border:1px solid var(--line);border-radius:99px;background:var(--card);cursor:pointer;user-select:none}
.chip i{width:10px;height:10px;border-radius:50%;display:inline-block}
.chip.off{opacity:.45}
main{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:16px;padding-bottom:24px;max-width:1500px;margin:auto}
@media (max-width:900px){main{grid-template-columns:1fr}}
#page{position:relative;width:100%;background:#fff;border:1px solid var(--line);border-radius:6px;overflow:hidden}
#page img{position:absolute;inset:0;width:100%;height:100%;user-select:none;-webkit-user-drag:none}
#layer,#hl{position:absolute;inset:0}
#layer{direction:rtl}
#hl div{position:absolute;background:var(--hl);border-radius:2px;pointer-events:none;mix-blend-mode:multiply}
.w{position:absolute;white-space:nowrap;color:transparent;line-height:1;transform-origin:right top;cursor:pointer;border-radius:2px}
.w::selection{background:rgba(47,111,214,.35);color:transparent}
.gemara .w{font-family:'Frank Ruhl Libre',serif}
.rashi .w,.tosafot .w{font-family:'Noto Rashi Hebrew','Frank Ruhl Libre',serif}
.w.dh{font-family:'Frank Ruhl Libre',serif;font-weight:700}
.w:hover{background:rgba(250,204,21,.3)}
body.show .gemara .w{outline:1px solid color-mix(in srgb,var(--gem) 60%,transparent);background:color-mix(in srgb,var(--gem) 10%,transparent)}
body.show .rashi .w{outline:1px solid color-mix(in srgb,var(--rashi) 60%,transparent);background:color-mix(in srgb,var(--rashi) 10%,transparent)}
body.show .tosafot .w{outline:1px solid color-mix(in srgb,var(--tos) 60%,transparent);background:color-mix(in srgb,var(--tos) 10%,transparent)}
body.live #page img{opacity:0}
body.live .w{color:#111}
body.live.cmp #page img{opacity:.2}
body.live.cmp .w{color:rgba(160,20,20,.85)}
.hide{display:none}
aside{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px;align-self:start;position:sticky;top:12px}
aside h2{font-size:13px;margin:0 0 8px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.04em}
#ref{font-weight:600}
#sel{direction:rtl;font-family:'Frank Ruhl Libre',serif;font-size:18px;min-height:40px;white-space:pre-wrap;margin-top:6px}
table{border-collapse:collapse;font-size:13px;width:100%}
td,th{padding:3px 4px;text-align:right;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}
.flags{color:var(--bad);font-size:13px;margin:8px 0 0;padding-inline-start:18px}
.ok{color:var(--muted);font-size:13px;margin-top:8px}
</style>
<header>
<h1>Live-text daf: review</h1>
<p class="sub">Sefaria text aligned automatically to the page image by word widths (no OCR). Click a word to highlight its whole Gemara segment or comment on the page.</p>
<div class="bar">
 <button class="nav" id="prev" aria-label="Previous amud">‹</button><select id="pick"></select><button class="nav" id="next" aria-label="Next amud">›</button>
 <div class="seg" id="mode"><button data-m="img" class="on">Image</button><button data-m="show">Word boxes</button><button data-m="live">Text only</button><button data-m="cmp">Text over image</button></div>
 <span class="chip" data-s="gemara"><i style="background:var(--gem)"></i>Gemara</span>
 <span class="chip" data-s="rashi"><i style="background:var(--rashi)"></i>Rashi</span>
 <span class="chip" data-s="tosafot"><i style="background:var(--tos)"></i>Tosafot</span>
</div>
</header>
<main>
<div id="page"><img id="im" alt=""><div id="hl"></div><div id="layer"></div></div>
<aside>
<h2>Selected</h2>
<div id="ref">Click a word.</div>
<div id="sel"></div>
<h2 style="margin-top:16px">Alignment on this amud</h2>
<table id="stats"></table>
<div id="flags"></div>
</aside>
</main>
<script>
const PAGES=__DATA__;
const $=id=>document.getElementById(id);
const pick=$('pick'), layer=$('layer'), hl=$('hl'), page=$('page');
PAGES.forEach((p,i)=>{const o=document.createElement('option');o.value=i;o.textContent=p.label+(p.flags.length?'  ⚑':'');pick.appendChild(o)});
let cur=null, spans=[], hidden=new Set();
function show(i){
  cur=PAGES[i]; pick.value=i;
  page.style.aspectRatio=cur.W+'/'+cur.H; $('im').src='img/'+cur.id+'.jpg'; $('im').alt=cur.label;
  layer.innerHTML=''; hl.innerHTML=''; spans=[]; $('ref').textContent='Click a word.'; $('sel').textContent='';
  for(const s of ['gemara','rashi','tosafot']){
    const g=document.createElement('div'); g.className=s+(hidden.has(s)?' hide':''); layer.appendChild(g);
    const hs=cur.s[s].map(l=>l.b[3]).sort((a,b)=>a-b), fh=hs[hs.length>>1]||10;
    cur.s[s].forEach(ln=>{
      ln.w.forEach(([t,b0,dh,ref],wi)=>{
        const b=[b0[0], ln.b[1]+(ln.b[3]-fh)/2, b0[2], fh];
        const e=document.createElement('span'); e.className='w'+(dh?' dh':''); e.textContent=t;
        e.style.right=(100*(cur.W-b[0]-b[2])/cur.W)+'%'; e.style.top=(100*b[1]/cur.H)+'%';
        e.dataset.ref=ref||''; e.b=b; g.appendChild(e); spans.push(e);
        if(wi<ln.w.length-1) g.appendChild(document.createTextNode(' '));
      });
      g.appendChild(document.createTextNode('\n'));
    });
  }
  fit();
  const st=cur.stats, cols=[['img_words','printed'],['tokens','text'],['one_to_one','1:1'],['skip_txt','unplaced'],['cost_per_word','cost']];
  $('stats').innerHTML='<tr><th></th>'+cols.map(c=>'<th>'+c[1]+'</th>').join('')+'</tr>'+
    ['gemara','rashi','tosafot'].map(s=>'<tr><td>'+s+'</td>'+cols.map(c=>'<td>'+st[s][c[0]]+'</td>').join('')+'</tr>').join('');
  $('flags').innerHTML=cur.flags.length?'<ul class="flags">'+cur.flags.map(f=>'<li>'+f.replace(/</g,'&lt;')+'</li>').join('')+'</ul>':'<div class="ok">No QC flags.</div>';
  try{localStorage.setItem('ltd-amud',i)}catch(e){}
}
function fit(){
  const k=layer.clientWidth/cur.W;
  for(const e of spans){
    const b=e.b; e.style.transform='none';
    e.style.fontSize=(b[3]*k*0.78)+'px'; e.style.height=(b[3]*k)+'px'; e.style.lineHeight=(b[3]*k)+'px';
    const nat=e.scrollWidth||1; e.style.transform=`scaleX(${(b[2]*k)/nat})`;
  }
}
document.fonts.ready.then(()=>cur&&fit()); new ResizeObserver(()=>cur&&fit()).observe(layer);
pick.onchange=()=>show(+pick.value);
$('prev').onclick=()=>show(Math.max(0,+pick.value-1)); $('next').onclick=()=>show(Math.min(PAGES.length-1,+pick.value+1));
document.querySelectorAll('#mode button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('#mode button').forEach(x=>x.classList.toggle('on',x===b));
  const m=b.dataset.m; document.body.classList.toggle('show',m==='show');
  document.body.classList.toggle('live',m==='live'||m==='cmp'); document.body.classList.toggle('cmp',m==='cmp');
});
document.querySelectorAll('.chip').forEach(c=>c.onclick=()=>{
  c.classList.toggle('off'); const s=c.dataset.s; c.classList.contains('off')?hidden.add(s):hidden.delete(s);
  layer.querySelector('.'+s).classList.toggle('hide',hidden.has(s));
});
layer.addEventListener('click',ev=>{
  const e=ev.target.closest('.w'); if(!e||String(getSelection()).trim()) return;
  const ref=e.dataset.ref; hl.innerHTML='';
  for(const b of (cur.seg[ref]||[])){
    const d=document.createElement('div');
    d.style.left=(100*b[0]/cur.W)+'%'; d.style.top=(100*b[1]/cur.H)+'%'; d.style.width=(100*b[2]/cur.W)+'%'; d.style.height=(100*b[3]/cur.H)+'%';
    hl.appendChild(d);
  }
  $('ref').textContent=/^\d/.test(ref)?'Gemara '+ref:ref;
  $('sel').textContent=spans.filter(x=>x.dataset.ref===ref).map(x=>x.textContent).join(' ');
});
let start=0; try{start=+localStorage.getItem('ltd-amud')||0}catch(e){}
show(Math.min(start,PAGES.length-1));
</script>"""


def main():
    ap = argparse.ArgumentParser(description="e.g. viewer --out DIR 'Bava Metzia' 2a-11b Kiddushin 3a-12b")
    ap.add_argument("--out", required=True)
    ap.add_argument("specs", nargs="+", help="tractate then amud ranges, repeated")
    a = ap.parse_args()
    specs, cur = [], None
    for x in a.specs:
        if x[0].isdigit():
            cur[1].extend(parse_amudim([x]))
        else:
            cur = (x.replace("_", " "), []); specs.append(cur)
    print(build(specs, Path(a.out)))


if __name__ == "__main__":
    main()
