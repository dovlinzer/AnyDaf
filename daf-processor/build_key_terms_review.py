#!/usr/bin/env python3
"""Side-by-side review page for the key-terms pilot (Sonnet 5 vs Opus 5.5). Local only.

    venv/bin/python build_key_terms_review.py --dafim gittin_18 ... --out page.html
"""
import argparse
import json
from pathlib import Path

from build_master_glossary import fold
from build_outline_review import title_of

HERE = Path(__file__).parent
RESULTS = HERE / "outline" / "results"
EXAMPLE = HERE / "outline" / "key_terms_example_chagigah_6.json"
MODELS = {"sonnet5": "Sonnet 5", "opus55": "Opus 5.5"}

TEMPLATE = r"""<title>Key Terms Pilot</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,500;0,6..72,600;1,6..72,500&family=Public+Sans:wght@400;500;600&family=Frank+Ruhl+Libre:wght@500&display=swap">
<style>
:root{--ground:#F4F5F9;--panel:#FFFFFF;--ink:#1A1F2E;--muted:#5B6478;--line:#DCE0EA;--blue:#1B3A8A;--teal:#2C6A6E;--both:#E3F0EC;--both-ink:#2C6A6E;--grey-soft:#EEF0F4;--link:#6B4FA0;
--serif:"Newsreader",Georgia,serif;--sans:"Public Sans",system-ui,-apple-system,"Segoe UI",sans-serif;--hebrew:"Frank Ruhl Libre","Times New Roman",serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--ground:#10131B;--panel:#181C27;--ink:#E6E9F2;--muted:#9AA3B8;--line:#2B3142;--blue:#8FA8EC;--teal:#7CC3C4;--both:#1E3432;--both-ink:#7CC3C4;--grey-soft:#222735;--link:#B9A2E6}}
:root[data-theme="dark"]{color-scheme:dark;--ground:#10131B;--panel:#181C27;--ink:#E6E9F2;--muted:#9AA3B8;--line:#2B3142;--blue:#8FA8EC;--teal:#7CC3C4;--both:#1E3432;--both-ink:#7CC3C4;--grey-soft:#222735;--link:#B9A2E6}
body{background:var(--ground);color:var(--ink);font:15px/1.55 var(--sans)}
.wrap{max-width:1180px;margin:0 auto;padding-inline:16px;padding-block:24px 64px}
h1{font:600 1.8rem/1.15 var(--serif);margin:0 0 4px}
.sub{color:var(--muted);margin:0;max-width:75ch}
.controls{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--ground);display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;padding-block:12px;margin-top:14px;border-bottom:1px solid var(--line)}
select{font:500 14px var(--sans);padding:6px 8px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--ink)}
.key{font-size:13px;color:var(--muted)}.key b{background:var(--both);color:var(--both-ink);font-weight:600;padding:1px 7px;border-radius:999px}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px;margin-top:18px}
.cols>section{min-width:0}
.cols h2{font:600 13px var(--sans);letter-spacing:.05em;text-transform:uppercase;color:var(--muted);margin:0 0 8px}
.term{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin-bottom:10px}
.term h3{margin:0;display:flex;justify-content:space-between;gap:12px;align-items:baseline;flex-wrap:wrap}
.name{font:600 1.08rem/1.3 var(--serif);color:var(--blue)}
.heb{font:500 1.05rem var(--hebrew)}
.tag{font:600 11px var(--sans);letter-spacing:.04em;background:var(--both);color:var(--both-ink);border-radius:999px;padding:1px 8px;margin-left:8px;vertical-align:2px}
.sense{font-size:13px;color:var(--muted);font-style:italic;margin:2px 0 6px}
.term p{margin:4px 0;max-width:62ch}
.lbl{display:block;font:600 11px var(--sans);letter-spacing:.05em;text-transform:uppercase;color:var(--muted);margin-top:8px}
.secs{display:flex;flex-wrap:wrap;gap:5px;margin-top:6px}
.secs span{font:500 12px var(--sans);color:var(--link);background:var(--grey-soft);border-radius:999px;padding:2px 8px}
.alias{font-size:12.5px;color:var(--muted);margin-top:6px}
.none{color:var(--muted)}
</style>
<div class="wrap">
<h1>Key Terms Pilot</h1>
<p class="sub">12 test dafim, the same instructions and Chagigah 6 example, two models. Terms both models chose are marked. Section chips name the Opus 5.5 outline's sections each term was attached to.</p>
<div class="controls"><select id="daf" aria-label="Daf"></select><span class="key"><b>both</b> = chosen by both models</span></div>
<div class="cols" id="cols"></div>
</div>
<script>
const DATA=__DATA__,MODELS=__MODELS__;
const esc=s=>String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const md=s=>esc(s).replace(/\*([^*]+)\*/g,'<i>$1</i>');
const sel=document.getElementById('daf');
Object.keys(DATA).forEach(k=>sel.insertAdjacentHTML('beforeend',`<option value="${k}">${esc(DATA[k].title)}</option>`));
function draw(){const d=DATA[sel.value];
 document.getElementById('cols').innerHTML=Object.keys(MODELS).map(m=>{const ts=d[m]||[];
  return `<section><h2>${MODELS[m]} · ${ts.length} terms</h2>${ts.length?ts.map(t=>`<article class="term">
   <h3><span><span class="name">${esc(t.term)}</span>${t.both?'<span class="tag">both</span>':''}</span><span class="heb" lang="he" dir="rtl">${esc(t.hebrew)}</span></h3>
   <p class="sense">${esc(t.sense)}</p><p>${md(t.definition)}</p>
   <span class="lbl">On this daf</span><p>${md(t.on_this_daf)}</p>
   <div class="secs">${(t.sections||[]).map(s=>`<span>${esc(d.titles[s]||s)}</span>`).join('')}</div>
   <p class="alias">Highlighted as: ${(t.aliases||[]).map(esc).join(' · ')||'—'}</p></article>`).join(''):'<p class="none">No output.</p>'}</section>`}).join('')}
sel.onchange=()=>{try{localStorage.setItem('ktr',sel.value)}catch(e){}draw()};
try{const v=localStorage.getItem('ktr');if(v&&DATA[v])sel.value=v}catch(e){}
draw();
</script>
"""


def titles(outline):
    out = {}

    def walk(ns):
        for n in ns or []:
            out[n["id"]] = n["title"]
            walk(n.get("children"))

    walk(outline.get("sections"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dafim", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    data = {}
    for key in args.dafim:
        entry = {"title": title_of(key)}
        outline_p = RESULTS / key / "04_outline_opus55.json"
        entry["titles"] = titles(json.loads(outline_p.read_text())) if outline_p.exists() else {}
        for tag in MODELS:
            p = RESULTS / key / f"05_key_terms_{tag}.json"
            entry[tag] = json.loads(p.read_text()).get("key_terms", []) if p.exists() else []
        folds = {tag: {fold(t["term"]) for t in entry[tag]} for tag in MODELS}
        for tag in MODELS:
            other = set().union(*(f for t2, f in folds.items() if t2 != tag))
            for t in entry[tag]:
                t["both"] = fold(t["term"]) in other
        data[key] = entry
    html = (TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
                    .replace("__MODELS__", json.dumps(MODELS)))
    Path(args.out).write_text(html, encoding="utf-8")
    print(f"wrote {args.out} ({len(html):,} chars)")


if __name__ == "__main__":
    main()
