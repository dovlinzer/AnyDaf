#!/usr/bin/env python3
"""build_outline_review.py — bundle 04_outline_*.json files into one review page.

Picks up every outline/results/<key>/04_outline_<tag>.json for the given keys and writes a single
self-contained HTML page with a daf picker, a model picker, a side-by-side "compare
headlines" view, and the same detail / shiur / chart toggles as the Chagigah 6 prototype.

Usage:
    python build_outline_review.py --dafim gittin_18 shabbat_21 --out outline/review.html
"""
import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
RESULTS = HERE / "outline" / "results"
SPRITE = HERE / "outline" / "sprite.svg"
MODEL_LABELS = {"sonnet5": "Sonnet 5", "opus5": "Opus 5", "opus55": "Opus 5.5"}

TEMPLATE = r"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Daf Outline Review</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,500;0,6..72,600;1,6..72,500&family=Public+Sans:wght@400;500;600&family=Frank+Ruhl+Libre:wght@500;700&display=swap">
<style>
:root{--ground:#F4F5F9;--panel:#FFFFFF;--ink:#1A1F2E;--muted:#5B6478;--line:#DCE0EA;--blue:#1B3A8A;--teal:#2C6A6E;--teal-line:#B9D3D4;--amber:#9A6212;--amber-soft:#FBF1DF;--grey-soft:#EEF0F4;--link:#6B4FA0;
--serif:"Newsreader",Georgia,"Times New Roman",serif;--sans:"Public Sans",system-ui,-apple-system,"Segoe UI",sans-serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--ground:#10131B;--panel:#181C27;--ink:#E6E9F2;--muted:#9AA3B8;--line:#2B3142;--blue:#8FA8EC;--teal:#7CC3C4;--teal-line:#2F4B4E;--amber:#E0B067;--amber-soft:#33291A;--grey-soft:#222735;--link:#B9A2E6}}
:root[data-theme="dark"]{color-scheme:dark;--ground:#10131B;--panel:#181C27;--ink:#E6E9F2;--muted:#9AA3B8;--line:#2B3142;--blue:#8FA8EC;--teal:#7CC3C4;--teal-line:#2F4B4E;--amber:#E0B067;--amber-soft:#33291A;--grey-soft:#222735;--link:#B9A2E6}
body{background:var(--ground);color:var(--ink);font:15px/1.55 var(--sans)}
.wrap{max-width:780px;margin:0 auto;padding-inline:16px;padding-block:24px 64px}
.wrap.wide{max-width:1680px}
h1{font:600 1.8rem/1.15 var(--serif);margin:0 0 4px}
.sub{color:var(--muted);margin:0}
.controls{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--ground);display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;padding-block:12px;margin-top:14px;border-bottom:1px solid var(--line)}
select{font:500 14px var(--sans);padding:6px 8px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--ink)}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:999px;background:var(--panel);padding:2px;flex-wrap:wrap}
.seg button{font:500 13px var(--sans);border:0;background:none;color:var(--muted);padding:6px 12px;border-radius:999px;cursor:pointer}
.seg button[aria-pressed="true"]{background:var(--blue);color:var(--panel)}
.tog{display:inline-flex;align-items:center;gap:6px;font-size:13px;color:var(--muted);cursor:pointer}
.tog input{accent-color:var(--blue)}
[hidden]{display:none!important}
#showBox{gap:4px 12px;flex-wrap:wrap}
button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
.meta{margin-top:18px;display:grid;gap:10px}
.meta details{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:10px 12px}
.meta summary{font:600 13px var(--sans);cursor:pointer}
.meta ul{margin-top:6px}
.scope{font-size:13px;color:var(--muted)}
.node{display:flex;flex-direction:column;gap:6px}
.l1{margin-top:28px}
.l2{margin-top:16px;padding-left:16px;border-left:2px solid var(--line)}
.l3,.l4,.l5{margin-top:14px;padding-left:14px;border-left:2px solid var(--teal-line)}
.l4,.l5{border-left-style:dotted}
.head{display:flex;gap:8px 10px;align-items:baseline;flex-wrap:wrap}
.l1>.head .t{font:600 1.35rem/1.25 var(--serif);color:var(--blue)}
.l2>.head .t{font:italic 500 1.12rem/1.3 var(--serif)}
.l3>.head .t{font:600 12.5px/1.35 var(--sans);letter-spacing:.06em;text-transform:uppercase;color:var(--teal)}
.l4>.head .t,.l5>.head .t{font:500 13.5px/1.35 var(--sans);color:var(--teal)}
.amud{font:600 11px var(--sans);letter-spacing:.06em;text-transform:uppercase;color:var(--muted);border:1px solid var(--line);border-radius:4px;padding:1px 6px}
.flag{font:600 11px var(--sans);color:var(--muted);background:var(--grey-soft);border-radius:4px;padding:2px 7px}
.ret{font:500 12px var(--sans);color:var(--link)}
.gist{margin:0;max-width:65ch}
.l2 .gist,.l3 .gist,.l4 .gist,.l5 .gist{color:var(--muted)}
ul{margin:0;padding-left:18px}
li{margin:3px 0;max-width:65ch}
li.d3{color:var(--muted);font-size:14px;list-style:circle;margin-left:16px}
li.s{background:var(--amber-soft);list-style:none;margin-left:-18px;padding:4px 8px 4px 10px;border-radius:4px;border-left:3px solid var(--amber)}
li.s::before{content:"Shiur  ";font:600 11px var(--sans);letter-spacing:.05em;text-transform:uppercase;color:var(--amber)}
.cont{font-size:13px;color:var(--muted);font-style:italic}
.chart{margin-top:6px;overflow-x:auto;background:var(--panel);border:1px solid var(--line);border-radius:6px}
.chart caption{caption-side:top;text-align:left;font:600 12px var(--sans);letter-spacing:.04em;text-transform:uppercase;color:var(--muted);padding:10px 12px 0}
table{border-collapse:collapse;width:100%;font-size:13.5px;min-width:480px}
th,td{padding:8px 12px;text-align:left;vertical-align:top;border-top:1px solid var(--line)}
thead th{font-weight:600;color:var(--muted);font-size:12px;border-top:0}
tbody td:first-child{font-weight:600}
[data-level="1"] #out ul{display:none}
figure.ill{margin:8px 0 2px}figure.ill .art{overflow-x:auto;border-radius:10px;border:1px solid var(--line)}
figure.ill svg{display:block;width:100%;min-width:600px;height:auto}
figure.ill figcaption{font-size:13px;color:var(--muted);margin-top:6px;max-width:68ch}
[data-noill] figure.ill{display:none}
.sprite{position:absolute;width:0;height:0;overflow:hidden}
[data-level="2"] li.d3{display:none}
[data-noshiur] li.s{display:none}
[data-nocharts] .chart{display:none}
.cmp{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px;margin-top:18px}
.cmp>section{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:4px 14px 16px;min-width:0}
.cmp h2{font:600 13px var(--sans);letter-spacing:.05em;text-transform:uppercase;color:var(--muted);margin:12px 0 0}
.cmp .l1{margin-top:16px}.cmp .l1>.head .t{font-size:1.1rem}
.err{color:var(--amber);margin-top:20px}
.citem{margin-top:16px}.citem .ctitle{font:600 13px var(--sans);color:var(--blue);margin-bottom:4px}
.citem .camud{font:500 11px var(--sans);color:var(--muted);margin-left:6px}
.cmp figure.ill svg{min-width:0}
.cmp .chart table{min-width:0;font-size:12.5px}
.none{color:var(--muted);font-size:13px;margin-top:14px}
/* fix-up flags (shown only when the page can store them) */
.fl{font:500 11px var(--sans);color:var(--muted);background:none;border:1px solid var(--line);border-radius:999px;padding:1px 8px;cursor:pointer}
.fl:hover{color:var(--blue);border-color:var(--blue)}
.fl.has{background:var(--amber-soft);border-color:var(--amber);color:var(--amber)}
body:not(.flags) .fl,body:not(.flags) #flagsBtn{display:none}
dialog{border:1px solid var(--line);border-radius:10px;background:var(--panel);color:var(--ink);padding:18px;width:min(460px,calc(100vw - 32px));box-shadow:0 12px 40px rgba(20,30,60,.2)}
dialog::backdrop{background:rgba(16,19,27,.35)}
dialog h3{margin:0 0 4px;font:600 1.05rem/1.3 var(--serif)}
dialog .where{font-size:12.5px;color:var(--muted);margin:0 0 12px}
dialog label{display:block;font:600 12px var(--sans);color:var(--muted);margin:10px 0 4px}
dialog select,dialog textarea{width:100%;box-sizing:border-box;font:14px var(--sans);padding:7px 9px;border:1px solid var(--line);border-radius:6px;background:var(--ground);color:var(--ink)}
dialog textarea{min-height:90px;resize:vertical}
dialog .row{display:flex;gap:8px;justify-content:flex-end;margin-top:14px}
dialog button{font:500 13px var(--sans);border:1px solid var(--line);background:var(--panel);color:var(--ink);padding:6px 14px;border-radius:999px;cursor:pointer}
dialog button.primary{background:var(--blue);border-color:var(--blue);color:var(--panel)}
dialog .old{margin:12px 0 0;padding:0;list-style:none;display:grid;gap:6px}
dialog .old li{font-size:13px;background:var(--ground);border-radius:6px;padding:6px 8px;display:flex;gap:8px;justify-content:space-between;max-width:none}
dialog .old li b{font-weight:600}
dialog .old button{font-size:11px;padding:1px 8px}
dialog .err{margin:8px 0 0;font-size:13px}
#flagsList{margin:0;padding:0;list-style:none;display:grid;gap:8px;max-height:60vh;overflow:auto}
#flagsList li{font-size:13.5px;background:var(--ground);border-radius:6px;padding:8px 10px;max-width:none}
#flagsList .k{font:600 11px var(--sans);letter-spacing:.05em;text-transform:uppercase;color:var(--amber)}
</style>
<div class="wrap" id="root" data-level="2">
<h1>Daf Outline Review</h1>
<p class="sub">Test run: the same instructions and Chagigah 6 example, three models. Compare structures side by side, or read one model's outline in full.</p>
<div class="controls">
 <select id="daf" aria-label="Daf"></select>
 <div class="seg" id="models" role="group" aria-label="Model"></div>
 <span class="tog" id="showBox" role="group" aria-label="Columns to compare"></span>
 <div class="seg" id="levels" role="group" aria-label="Detail level">
  <button data-lv="1">Headlines</button><button data-lv="2" aria-pressed="true">Standard</button><button data-lv="3">Detailed</button></div>
 <label class="tog"><input type="checkbox" id="shiurTog" checked> Shiur insights</label>
 <label class="tog"><input type="checkbox" id="chartTog" checked> Charts</label>
 <label class="tog"><input type="checkbox" id="illTog" checked> Illustrations</label>
 <button class="fl" id="flagsBtn" type="button">Fix-up notes</button>
</div>
<dialog id="flagDlg"><form method="dialog" id="flagForm">
 <h3>Flag for a fix-up</h3><p class="where" id="flagWhere"></p>
 <label for="flagKind">What should change</label>
 <select id="flagKind">
  <option value="heading">Better heading</option><option value="gist">Better gist</option>
  <option value="structure">Structure: make it a subsection, move, merge or split</option>
  <option value="add_chart">Add a chart</option><option value="fix_chart">Fix this chart</option>
  <option value="add_picture">Add a picture</option><option value="fix_picture">Fix this picture</option>
  <option value="content">Content or wording</option><option value="other">Other</option>
 </select>
 <label for="flagNote">Note (what you want, in a sentence or two)</label>
 <textarea id="flagNote" required></textarea>
 <ul class="old" id="flagOld"></ul><p class="err" id="flagErr" hidden></p>
 <div class="row"><button value="cancel" formnovalidate>Cancel</button><button class="primary" id="flagSave" value="save">Save note</button></div>
</form></dialog>
<dialog id="flagsDlg"><h3>Fix-up notes for this daf</h3><p class="where">Saved here for the fix-up pass. Notes marked applied have been worked in.</p>
 <ul id="flagsList"></ul><div class="row"><button type="button" id="flagsClose">Close</button></div></dialog>
__SPRITE__
<div id="body"></div>
</div>
<script>
const DATA=__DATA__;const LABELS=__LABELS__;
const esc=s=>String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const md=s=>esc(s).replace(/\*\*([^*]+)\*\*/g,'<b>$1</b>').replace(/\*([^*]+)\*/g,'<i>$1</i>');
function titles(o){const m={};(function w(a){(a||[]).forEach(n=>{m[n.id]=n.title;w(n.children)})})(o.sections);return m}
function chartHTML(n){return `<div class="chart"><table><caption>${md(n.chart.caption)}</caption><thead><tr>${(n.chart.columns||[]).map(h=>`<th>${md(h)}</th>`).join('')}</tr></thead><tbody>${(n.chart.rows||[]).map(r=>`<tr>${r.map((x,i)=>i?`<td>${md(x)}</td>`:`<th>${md(x)}</th>`).join('')}</tr>`).join('')}</tbody></table></div>`}
function illHTML(n){return `<figure class="ill"><div class="art">${n.illustration.svg}</div><figcaption>${md(n.illustration.caption)}</figcaption></figure>`}
function flat(ns){const a=[];(function w(x){(x||[]).forEach(n=>{a.push(n);w(n.children)})})(ns);return a}
function items(o,kind,tag){const f=kind=='charts'?n=>n.chart&&chartHTML(n):n=>n.illustration&&illHTML(n);
 const got=flat(o.sections).filter(n=>kind=='charts'?n.chart:n.illustration);
 return got.length?got.map(n=>`<div class="citem"><div class="ctitle">${md(n.title)}<span class="camud">${esc(n.amud)}</span> ${flagBtn(tag,n,kind=='charts'?'fix_chart':'fix_picture')}</div>${f(n)}</div>`).join(''):`<p class="none">No ${kind} in this outline.</p>`}
function node(n,lv,T,full,tag){
 const b=full&&n.bullets?`<ul>${n.bullets.map(x=>`<li class="${x.detail==3?'d3':''} ${x.source=='shiur'?'s':''}">${md(x.text)}</li>`).join('')}</ul>`:'';
 const r=(n.returns_to||[]).map(x=>`<span class="ret">↩ returns to: ${md(T[x.id]||x.id)}${x.note?' — '+md(x.note):''}</span>`).join('');
 const c=full&&n.chart?chartHTML(n):'';
 const il=full&&n.illustration?illHTML(n):'';
 return `<div class="node l${Math.min(lv,5)}"><div class="head"><span class="t">${md(n.title)}</span><span class="amud">${esc(n.amud)}</span>${n.flag?`<span class="flag">${esc(n.flag)}</span>`:''}${n.chart&&!full?'<span class="flag">chart</span>':''}${n.illustration&&!full?'<span class="flag">picture</span>':''}${flagBtn(tag,n)}</div>${r}<p class="gist">${md(n.gist)}</p>${b}${c}${il}${n.continues?`<p class="cont">${md(n.continues)}</p>`:''}${(n.children||[]).map(k=>node(k,lv+1,T,full,tag)).join('')}</div>`}
function meta(o){const L=(h,a,raw)=>a&&a.length?`<details open><summary>${h} (${a.length})</summary><ul>${a.map(x=>`<li>${raw?x:md(x)}</li>`).join('')}</ul></details>`:'';
 const T=titles(o),kt=(o.key_terms||[]).map(t=>`<b>${esc(t.term)}</b> <span lang="he">${esc(t.hebrew)}</span> — <i>${esc(t.sense)}</i>. ${md(t.definition)} <span class="scope">On this daf: ${md(t.on_this_daf)}</span>`);
 const ru=k=>((o.runners_up||{})[k]||[]).map(r=>`${md(r.subject)} <span class="scope">(${md(T[r.section]||r.section)})</span> — ${md(r.why_not)}`);
 return `<div class="meta"><p class="scope"><b>Scope:</b> ${md(o.scope?.start)} → ${md(o.scope?.end)}</p>${L('Key terms',kt,1)}${L('Charts considered, not made',ru('charts'),1)}${L('Pictures considered, not drawn',ru('illustrations'),1)}${L('Judgment calls',o.judgment_calls)}${L('Coverage notes',o.coverage_notes)}</div>`}
const root=document.getElementById('root'),dafSel=document.getElementById('daf'),mSeg=document.getElementById('models');
let model='compare';let hidden=new Set();
Object.keys(DATA).forEach(d=>dafSel.insertAdjacentHTML('beforeend',`<option value="${d}">${esc(DATA[d]._title)}</option>`));
function draw(){
 const d=DATA[dafSel.value];
 {const n=(typeof FLAGS!=='undefined'?FLAGS:[]).filter(f=>f.daf==dafSel.value).length;document.getElementById('flagsBtn').textContent=n?`Fix-up notes (${n})`:'Fix-up notes'}const all=Object.keys(LABELS).filter(t=>d[t]);
 // Comparison views show only the checked columns; fewer columns means wider pictures.
 const box=document.getElementById('showBox');
 box.innerHTML='Compare:'+all.map(t=>`<label class="tog"><input type="checkbox" data-t="${t}"${hidden.has(t)?'':' checked'}> ${LABELS[t]}</label>`).join('');
 box.querySelectorAll('input').forEach(i=>i.onchange=()=>{i.checked?hidden.delete(i.dataset.t):hidden.add(i.dataset.t);save();draw()});
 const tags=all.filter(t=>!hidden.has(t));
 mSeg.innerHTML=[['compare','Compare headlines'],['cmpcharts','Compare charts'],['cmpills','Compare pictures'],...all.map(t=>[t,LABELS[t]])].map(([k,l])=>`<button data-m="${k}" aria-pressed="${k==model}">${l}</button>`).join('');
 mSeg.querySelectorAll('button').forEach(b=>b.onclick=()=>{model=b.dataset.m;save();draw()});
 const body=document.getElementById('body');
 const cmp=model=='compare'||model=='cmpcharts'||model=='cmpills';
 document.querySelector('.wrap').classList.toggle('wide',cmp);
 document.getElementById('levels').hidden=cmp;box.hidden=!cmp;
 if(model=='cmpcharts'||model=='cmpills'){const k=model=='cmpcharts'?'charts':'pictures';
  body.innerHTML=`<div class="cmp">${tags.map(t=>`<section><h2>${LABELS[t]}</h2>${items(d[t],k,t)}</section>`).join('')}</div>`;return}
 if(model=='compare'){body.innerHTML=`<div class="cmp">${tags.map(t=>{const o=d[t];const T=titles(o);return `<section><h2>${LABELS[t]}</h2>${(o.sections||[]).map(n=>node(n,1,T,false,t)).join('')}${meta(o)}</section>`}).join('')}</div>`;return}
 const o=d[model];if(!o){body.innerHTML='<p class="err">No output for this model.</p>';return}
 const T=titles(o);body.innerHTML=`<div id="out">${(o.sections||[]).map(n=>node(n,1,T,true,model)).join('')}</div>${meta(o)}`}
function save(){try{localStorage.setItem('rv',JSON.stringify({d:dafSel.value,m:model,h:[...hidden]}))}catch(e){}}
dafSel.onchange=()=>{save();draw()};
document.querySelectorAll('#levels button').forEach(b=>b.onclick=()=>{root.dataset.level=b.dataset.lv;document.querySelectorAll('#levels button').forEach(x=>x.setAttribute('aria-pressed',x==b))});
const st=document.getElementById('shiurTog'),ct=document.getElementById('chartTog');
st.onchange=()=>st.checked?root.removeAttribute('data-noshiur'):root.setAttribute('data-noshiur','');
ct.onchange=()=>ct.checked?root.removeAttribute('data-nocharts'):root.setAttribute('data-nocharts','');
const it=document.getElementById('illTog');it.onchange=()=>it.checked?root.removeAttribute('data-noill'):root.setAttribute('data-noill','');
try{const s=JSON.parse(localStorage.getItem('rv')||'{}');if(s.d&&DATA[s.d])dafSel.value=s.d;if(s.m)model=s.m;if(s.h)hidden=new Set(s.h)}catch(e){}
// ---------- fix-up flags: stored with the page (db), read back for the fix-up pass ----------
// One document per note in "flags": {daf, tag, section, title, kind, note, status, at}.
let db=null,FLAGS=[],flagCtx=null;
const KIND={heading:'Better heading',gist:'Better gist',structure:'Structure',add_chart:'Add a chart',fix_chart:'Fix chart',
 add_picture:'Add a picture',fix_picture:'Fix picture',content:'Content or wording',other:'Other'};
const mine=(tag,id)=>FLAGS.filter(f=>f.daf==dafSel.value&&f.tag==tag&&f.section==id);
function flagBtn(tag,n,kind){if(!tag)return '';const k=mine(tag,n.id).length;
 return `<button type="button" class="fl${k?' has':''}" data-flag="${esc(tag)}|${esc(n.id)}"${kind?` data-kind="${kind}"`:''} title="Flag this for a fix-up">${k?k+' note'+(k>1?'s':''):'Flag'}</button>`}
function flagTitle(tag,id){const f=flat((DATA[dafSel.value][tag]||{}).sections).find(n=>n.id==id);return f?f.title:id}
document.addEventListener('click',e=>{const b=e.target.closest('[data-flag]');if(!b)return;
 const [tag,id]=b.dataset.flag.split('|');flagCtx={tag,id};
 document.getElementById('flagWhere').innerHTML=`${esc(DATA[dafSel.value]._title)} · ${esc(LABELS[tag]||tag)} · <b>${md(flagTitle(tag,id))}</b>`;
 document.getElementById('flagKind').value=b.dataset.kind||'heading';document.getElementById('flagNote').value='';
 document.getElementById('flagErr').hidden=true;
 document.getElementById('flagOld').innerHTML=mine(tag,id).map(f=>`<li><span><b>${esc(KIND[f.kind]||f.kind)}</b>: ${esc(f.note)}${f.status=='applied'?' <i>(applied)</i>':''}</span><button type="button" data-del="${esc(f._id)}">Remove</button></li>`).join('');
 document.getElementById('flagDlg').showModal()});
document.getElementById('flagOld').addEventListener('click',async e=>{const b=e.target.closest('[data-del]');if(!b||!db)return;
 try{await db.doc('flags/'+b.dataset.del).delete();b.closest('li').remove()}catch(err){showFlagErr(err)}});
function showFlagErr(err){const p=document.getElementById('flagErr');p.hidden=false;
 p.textContent=err&&err.code==='quota_exceeded'?'The note store is full; remove some old notes first.':"Couldn't save the note. Try again in a moment."}
document.getElementById('flagForm').addEventListener('submit',async e=>{
 if(e.submitter&&e.submitter.value!=='save')return;e.preventDefault();
 const note=document.getElementById('flagNote').value.trim();if(!note||!db||!flagCtx)return;
 const btn=document.getElementById('flagSave');btn.disabled=true;
 try{await db.collection('flags').add({daf:dafSel.value,tag:flagCtx.tag,section:flagCtx.id,title:flagTitle(flagCtx.tag,flagCtx.id),
   kind:document.getElementById('flagKind').value,note,status:'open',at:new Date().toISOString()});
  document.getElementById('flagDlg').close()}catch(err){showFlagErr(err)}finally{btn.disabled=false}});
document.getElementById('flagsBtn').onclick=()=>{const here=FLAGS.filter(f=>f.daf==dafSel.value);
 document.getElementById('flagsList').innerHTML=here.length?here.map(f=>`<li><span class="k">${esc(KIND[f.kind]||f.kind)}${f.status=='applied'?' · applied':''}</span><br>${esc(LABELS[f.tag]||f.tag)} · <b>${md(f.title)}</b><br>${esc(f.note)}</li>`).join(''):'<li>No notes on this daf yet.</li>';
 document.getElementById('flagsDlg').showModal()};
document.getElementById('flagsClose').onclick=()=>document.getElementById('flagsDlg').close();
(async()=>{try{db=await window.claude?.use?.('db')}catch(e){db=null}
 if(!db)return;document.body.classList.add('flags');
 db.collection('flags').onSnapshot(snap=>{FLAGS=snap.docs.map(d=>({...d.data(),_id:d.id}));
  draw()},()=>{})})();
draw();
</script>
"""


def title_of(key: str) -> str:
    textonly = key.endswith("_textonly")
    parts = key.removesuffix("_textonly").split("_")
    name = " ".join(p.capitalize() for p in parts[:-1]) + " " + parts[-1]
    if textonly:
        return name + " (shiur withheld)"
    return name + (" (no shiur)" if not (HERE / "output" / key).is_dir() else "")


def clean_svg(svg: str) -> str:
    """Model-written SVG goes into the page as markup: strip anything executable or external."""
    svg = re.sub(r"(?is)<script.*?</script>|<foreignObject.*?</foreignObject>|<style.*?</style>", "", svg)
    svg = re.sub(r"(?i)\son\w+\s*=\s*(\"[^\"]*\"|'[^']*')", "", svg)
    svg = re.sub(r"(?i)(href\s*=\s*)([\"'])(?!#)[^\"']*\2", r"\1\2#\2", svg)
    return fix_hebrew_direction(svg)


_HEB = re.compile(r"[\u05D0-\u05EA]")
_LAT = re.compile(r"[A-Za-z]")
_ANCHOR_FLIP = {"start": "end", "end": "start", "middle": "middle"}


def fix_hebrew_direction(svg: str) -> str:
    """Mark mostly-Hebrew <text> labels right-to-left. SVG lays text out left to right unless told
    otherwise, which moves punctuation at the edges of a Hebrew line to the wrong end ("?" after
    the first word, a verse citation's parentheses reversed). With direction="rtl", text-anchor's
    start/end refer to the right/left edge instead, so they are swapped to keep each label where
    it was drawn (a missing text-anchor means "start")."""
    def fix(m):
        attrs, body = m.group(1), m.group(2)
        plain = re.sub(r"<[^>]+>", "", body)
        if re.search(r"\bdirection\s*=", attrs) or len(_HEB.findall(plain)) <= len(_LAT.findall(plain)):
            return m.group(0)
        am = re.search(r'\btext-anchor\s*=\s*"(\w+)"', attrs)
        if am:
            attrs = attrs[:am.start()] + f'text-anchor="{_ANCHOR_FLIP.get(am.group(1), am.group(1))}"' + attrs[am.end():]
        else:
            attrs += ' text-anchor="end"'
        return f'<text{attrs} direction="rtl">{body}</text>'
    return re.sub(r"(?s)<text\b([^>]*)>(.*?)</text>", fix, svg)


_svg_counter = [0]


def uniquify_ids(svg: str) -> str:
    """Prefix ids an SVG defines itself (and their url(#)/href="#" references) so drawings shown
    side by side can't steal each other's gradients. Sprite ids (#sage, #lamb...) are untouched
    because the model never defines them."""
    _svg_counter[0] += 1
    pre = f"m{_svg_counter[0]}-"
    local = set(re.findall(r'\bid\s*=\s*"([^"]+)"', svg))
    for x in local:
        e = re.escape(x)
        svg = re.sub(rf'\bid\s*=\s*"{e}"', f'id="{pre}{x}"', svg)
        svg = re.sub(rf'url\(\s*#{e}\s*\)', f'url(#{pre}{x})', svg)
        svg = re.sub(rf'(href\s*=\s*")#{e}"', rf'\1#{pre}{x}"', svg)
    return svg


def clean_tree(nodes):
    for n in nodes or []:
        if isinstance(n.get("illustration"), dict) and "svg" in n["illustration"]:
            n["illustration"]["svg"] = uniquify_ids(clean_svg(n["illustration"]["svg"]))
        clean_tree(n.get("children"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dafim", nargs="+", required=True)
    ap.add_argument("--out", default=str(HERE / "outline" / "review.html"))
    ap.add_argument("--tags", nargs="+", metavar="TAG=Label",
                    help="result tags to compare, e.g. opus55_high='High effort' (default: the three models)")
    ap.add_argument("--title", help="page heading (default: Daf Outline Review)")
    ap.add_argument("--sub", help="subtitle under the heading")
    args = ap.parse_args()
    labels = dict(t.split("=", 1) for t in args.tags) if args.tags else MODEL_LABELS
    data = {}
    for daf in args.dafim:
        entry = {"_title": title_of(daf)}
        for tag in labels:
            p = RESULTS / daf / f"04_outline_{tag}.json"
            if p.exists():
                o = json.loads(p.read_text(encoding="utf-8"))
                clean_tree(o.get("sections"))
                entry[tag] = o
        data[daf] = entry
    html = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")) \
                   .replace("__LABELS__", json.dumps(labels)) \
                   .replace("__SPRITE__", SPRITE.read_text(encoding="utf-8"))
    if args.title:
        html = html.replace("<title>Daf Outline Review</title>", f"<title>{args.title}</title>") \
                   .replace("<h1>Daf Outline Review</h1>", f"<h1>{args.title}</h1>")
    if args.sub:
        html = re.sub(r'<p class="sub">.*?</p>', lambda m: f'<p class="sub">{args.sub}</p>', html, count=1, flags=re.S)
    Path(args.out).write_text(html, encoding="utf-8")
    print(f"wrote {args.out} ({len(html):,} chars)")


if __name__ == "__main__":
    main()
