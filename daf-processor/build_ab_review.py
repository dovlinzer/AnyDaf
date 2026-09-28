"""Blind A/B review page for testers: two versions of each daf's outline, labelled only A and B.

    python build_ab_review.py --tags opus55_medium opus55_high --out page.html \
        --dafim bekhorot_10 ... --key outline/ab_key.json

Per daf, which tag is A and which is B is random (seeded, so a rebuild keeps the same assignment)
and is written only to the --key file, never into the page. Editorial fields (judgment_calls,
coverage_notes, runners_up) are dropped, since testers shouldn't see them. Each daf has a vote
panel (overall, structure, charts, pictures, notes). Votes stay in the tester's browser; "Copy my
results" puts them on the clipboard as text to send back. Unblind with --key after collecting them.
Reuses build_outline_review.py's rendering, so outlines look exactly as on the other review pages.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import build_outline_review as R

HERE = Path(__file__).resolve().parent

EDITORIAL = ("judgment_calls", "coverage_notes", "runners_up")

VOTE_CSS = """
.vote{margin-top:18px;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px 14px;display:grid;gap:10px}
.vote h2{font:600 13px var(--sans);letter-spacing:.05em;text-transform:uppercase;color:var(--muted);margin:0}
.vrow{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center}
.vrow .lab{font:600 13px var(--sans);min-width:92px}
.vote textarea,.vote input[type=text]{width:100%;box-sizing:border-box;font:14px var(--sans);padding:7px 9px;border:1px solid var(--line);border-radius:6px;background:var(--ground);color:var(--ink)}
.vote textarea{min-height:70px;resize:vertical}
.vfoot{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;justify-content:space-between}
.prog{font-size:13px;color:var(--muted);font-variant-numeric:tabular-nums}
.btn{font:500 13px var(--sans);border:1px solid var(--blue);background:var(--blue);color:var(--panel);padding:6px 14px;border-radius:999px;cursor:pointer}
.btn.ghost{background:var(--panel);color:var(--blue)}
#copied{font-size:13px;color:var(--teal)}
#resultsBox{width:100%;min-height:160px;font:12.5px/1.45 ui-monospace,Menlo,monospace}
.how{font-size:13.5px;color:var(--muted);max-width:75ch;margin:8px 0 0}
"""

HOW_HTML = """
<p class="how">Each daf has two outlines, A and B, written from the same shiur and Gemara text. Read them side by side
("Compare headlines", "Compare charts", "Compare pictures") or one at a time, then say which serves you better. A and B are
shuffled from daf to daf. <span id="howSave">Your answers stay in this browser until you press <b>Copy my results</b> and send them back.</span></p>
"""

VOTE_HTML = """
<section class="vote" aria-labelledby="vh">
 <h2 id="vh">Your verdict on this daf</h2>
 <div id="vgrid"></div>
 <label for="vnote" class="lab" style="font:600 13px var(--sans)">Notes (optional: what made the difference, anything wrong or missing)</label>
 <textarea id="vnote"></textarea>
 <div class="vfoot">
  <span class="prog" id="prog"></span>
  <span style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
   <label for="vname" class="lab" style="min-width:0;font:600 13px var(--sans)">Your name</label>
   <input type="text" id="vname" style="width:180px">
   <button type="button" class="btn ghost" id="saveBtn" hidden>Save verdict</button>
   <button type="button" class="btn ghost" id="nextDaf">Next daf</button>
   <button type="button" class="btn" id="copyBtn">Copy my results</button>
   <span id="copied" aria-live="polite"></span>
  </span>
 </div>
 <textarea id="resultsBox" readonly hidden aria-label="Your results as text"></textarea>
</section>
"""

VOTE_JS = r"""
// ---------- blind votes: kept in this browser, copied out as text ----------
const ASPECTS=[['overall','Overall'],['structure','Structure'],['charts','Charts'],['pictures','Pictures']];
const CHOICES=[['A','A better'],['same','About the same'],['B','B better']];
let VOTES={};try{VOTES=JSON.parse(localStorage.getItem('ab-votes')||'{}')}catch(e){}
function saveVotes(){try{localStorage.setItem('ab-votes',JSON.stringify(VOTES))}catch(e){}}
function drawVote(){
 const d=dafSel.value, v=VOTES[d]||{};
 document.getElementById('vgrid').innerHTML=ASPECTS.map(([k,l])=>`<div class="vrow" role="radiogroup" aria-label="${l}"><span class="lab">${l}</span>${
  CHOICES.map(([c,cl])=>`<label class="tog"><input type="radio" name="v_${k}" value="${c}"${v[k]==c?' checked':''}> ${cl}</label>`).join('')}</div>`).join('');
 document.querySelectorAll('#vgrid input').forEach(i=>i.onchange=()=>{const k=i.name.slice(2);(VOTES[d]=VOTES[d]||{})[k]=i.value;saveVotes();prog();if(typeof FEEDBACK!=='undefined'&&FEEDBACK)savedState()});
 document.getElementById('vnote').value=v.note||'';
 prog()}
document.getElementById('vnote').oninput=e=>{const d=dafSel.value;(VOTES[d]=VOTES[d]||{}).note=e.target.value;saveVotes();if(typeof FEEDBACK!=='undefined'&&FEEDBACK)savedState()};
const nameEl=document.getElementById('vname');try{nameEl.value=localStorage.getItem('ab-name')||''}catch(e){}
nameEl.oninput=()=>{try{localStorage.setItem('ab-name',nameEl.value)}catch(e){}};
function prog(){const n=Object.keys(DATA).filter(d=>VOTES[d]&&VOTES[d].overall).length;
 document.getElementById('prog').textContent=`${n} of ${Object.keys(DATA).length} dafim rated`}
function resultsText(){const lines=[`Outline A/B results${nameEl.value?' from '+nameEl.value:''}`,''];
 Object.keys(DATA).forEach(d=>{const v=VOTES[d];if(!v||!(v.overall||v.note))return;
  lines.push(`${DATA[d]._title}: overall ${v.overall||'-'}, structure ${v.structure||'-'}, charts ${v.charts||'-'}, pictures ${v.pictures||'-'}`);
  if(v.note)lines.push('  '+v.note.replace(/\s+/g,' '))});
 return lines.join('\n')}
document.getElementById('copyBtn').onclick=async()=>{const t=resultsText(),box=document.getElementById('resultsBox'),msg=document.getElementById('copied');
 box.value=t;
 try{await navigator.clipboard.writeText(t);msg.textContent='Copied. Paste it into an email or message.';box.hidden=true}
 catch(e){box.hidden=false;box.focus();box.select();msg.textContent='Select the text below and copy it.'}};
document.getElementById('nextDaf').onclick=async()=>{const ks=Object.keys(DATA),i=ks.indexOf(dafSel.value);
 if(typeof FEEDBACK!=='undefined'&&FEEDBACK){const v=VOTES[dafSel.value]||{};if((v.overall||v.note)&&!(await sendVote()))return}
 if(i<ks.length-1){dafSel.value=ks[i+1];save();draw();window.scrollTo({top:0})}};

// ---------- hosted test: votes go to Supabase (outline_ab_votes, insert only) ----------
const FEEDBACK=__FEEDBACK__, ROUND=__ROUND__;
let TID='';try{TID=localStorage.getItem('ab-tid')||''}catch(e){}
if(!TID){TID=(crypto.randomUUID?crypto.randomUUID():String(Math.random()).slice(2));try{localStorage.setItem('ab-tid',TID)}catch(e){}}
let SAVED={};try{SAVED=JSON.parse(localStorage.getItem('ab-saved')||'{}')}catch(e){}
function savedState(){const d=dafSel.value,v=VOTES[d]||{},sv=SAVED[d];const same=sv&&JSON.stringify(sv)===JSON.stringify(v);
 const msg=document.getElementById('copied');
 if(FEEDBACK)msg.textContent=same?'Saved.':(v.overall?'Not saved yet.':'')}
async function sendVote(){const d=dafSel.value,v=VOTES[d]||{},msg=document.getElementById('copied');
 if(!v.overall&&!v.note){msg.textContent='Choose A, B or about the same first.';return false}
 const row={round:ROUND,tester_id:TID,tester_name:nameEl.value.trim()||null,daf:d,overall:v.overall||null,structure:v.structure||null,
  charts:v.charts||null,pictures:v.pictures||null,note:(v.note||'').trim()||null};
 try{const r=await fetch(FEEDBACK.url+'/rest/v1/outline_ab_votes',{method:'POST',headers:{apikey:FEEDBACK.key,Authorization:'Bearer '+FEEDBACK.key,
   'Content-Type':'application/json',Prefer:'return=minimal'},body:JSON.stringify(row)});if(!r.ok)throw new Error(r.status)}
 catch(e){msg.textContent="Couldn't save. Check your connection and try again; your answers are kept here.";return false}
 SAVED[d]=JSON.parse(JSON.stringify(v));try{localStorage.setItem('ab-saved',JSON.stringify(SAVED))}catch(e){}
 msg.textContent='Saved.';return true}
if(FEEDBACK){const sb=document.getElementById('saveBtn');sb.hidden=false;sb.onclick=sendVote;
 document.getElementById('nextDaf').textContent='Save and next daf';
 document.getElementById('howSave').innerHTML='Press <b>Save verdict</b> (or <b>Save and next daf</b>) on each daf; your answers are sent to the AnyDaf team.';
 document.getElementById('copyBtn').classList.add('ghost')}
const _draw=draw;draw=function(){_draw();drawVote();if(FEEDBACK)savedState()};
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dafim", nargs="+", required=True)
    ap.add_argument("--tags", nargs=2, required=True, metavar="TAG")
    ap.add_argument("--out", required=True)
    ap.add_argument("--key", required=True, help="where to write which tag is A/B per daf (keep private)")
    ap.add_argument("--title", default="Outline Taste Test")
    ap.add_argument("--seed", type=int, default=5786)
    ap.add_argument("--round", default="round3", help="stored with each vote; names the key used to unblind")
    ap.add_argument("--hosted", metavar="DIR", help="also write a stand-alone site to DIR (index.html + vercel.json) "
                    "whose votes go to Supabase outline_ab_votes")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    data, key = {}, {}
    for daf in a.dafim:
        pair = list(a.tags)
        rng.shuffle(pair)
        entry = {"_title": R.title_of(daf)}
        for label, tag in zip("AB", pair):
            o = json.loads((R.RESULTS / daf / f"04_outline_{tag}.json").read_text(encoding="utf-8"))
            for k in EDITORIAL:
                o.pop(k, None)
            R.clean_tree(o.get("sections"))
            entry[label] = o
        data[daf] = entry
        key[daf] = {"A": pair[0], "B": pair[1]}
    labels = {"A": "Version A", "B": "Version B"}
    html = R.TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")) \
                     .replace("__LABELS__", json.dumps(labels)) \
                     .replace("__SPRITE__", R.SPRITE.read_text(encoding="utf-8"))
    # the artifact skeleton supplies doctype and meta tags
    html = html.replace('<!doctype html>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n', "")
    html = html.replace("<title>Daf Outline Review</title>", f"<title>{a.title}</title>") \
               .replace("<h1>Daf Outline Review</h1>", f"<h1>{a.title}</h1>")
    html = html.replace(html[html.index('<p class="sub">'):html.index("</p>", html.index('<p class="sub">')) + 4],
                        '<p class="sub">Two outlines of each daf, A and B. Which helps you learn the daf better?</p>' + HOW_HTML, 1)
    html = html.replace('<div id="body"></div>', '<div id="body"></div>' + VOTE_HTML, 1)
    html = html.replace("</style>", VOTE_CSS + "</style>", 1)
    html = html.replace("draw();\n</script>", VOTE_JS + "draw();\n</script>")
    for tag in a.tags:                                                 # nothing may reveal the versions
        assert tag not in html, f"{tag} leaked into the page"
    page = html.replace("__ROUND__", json.dumps(a.round))
    Path(a.out).write_text(page.replace("__FEEDBACK__", "null"), encoding="utf-8")
    if a.hosted:
        import sys
        sys.path.insert(0, str(HERE.parent / "AnyDafWeb" / "prototype"))
        from build_prototype import SUPABASE_URL, anon_key
        d = Path(a.hosted); d.mkdir(parents=True, exist_ok=True)
        site = ('<!doctype html>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n'
                '<meta name="robots" content="noindex, nofollow">\n'
                '<style>[hidden]{display:none!important}body{margin:0}img{max-width:100%}</style>\n')
        site += page.replace("__FEEDBACK__", json.dumps({"url": SUPABASE_URL, "key": anon_key()}))
        (d / "index.html").write_text(site, encoding="utf-8")
        (d / "vercel.json").write_text(json.dumps({"headers": [{"source": "/(.*)", "headers": [
            {"key": "X-Robots-Tag", "value": "noindex, nofollow"}]}]}, indent=1))
        print(f"wrote hosted site {d}/index.html")
    Path(a.key).write_text(json.dumps(key, indent=1))
    print(f"wrote {a.out} ({len(html):,} chars) and key {a.key}")


if __name__ == "__main__":
    main()
