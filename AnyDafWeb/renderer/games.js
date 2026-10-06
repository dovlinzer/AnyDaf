/* AnyDaf study games — shared by the web app and (later) the phone WebViews.
 *
 *   const g = AnyDafGames.mount(el, { outline, keyTerms, sages, title }, { lang });
 *   g.destroy();
 *
 * Nothing is stored and nothing is at stake: right answers light up, wrong ones bounce back.
 * Games draw only on what the daf's data already holds (no API calls). See GAMES.md.
 *
 *   Fill in the chart  outline sections' `chart` (empty cells, cards to drag or tap into place)
 *   Term match         `keyTerms` (term + hebrew  <->  sense), memory-card style
 *   Who said it        chart rows that are parties (sages, schools) matched to the position each holds in one column
 *   Kosher or pasul    short verdict cells of the charts (chart.tones, else the renderer's cellTone): swipe or tap the ruling
 */
(function (global) {
  "use strict";
  const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const md = (s) => esc(s).replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/\*([^*]+)\*/g, "<i>$1</i>").replace(/\n/g, "<br>");
  const plain = (s) => String(s ?? "").replace(/\*+/g, "").trim();
  const shuffle = (a) => { a = a.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
  const WORDS = {
    en: { title: "Practice", back: "‹ All games", chart: "Fill in the chart", chartD: "Drag each card to its place in the chart.", match: "Term match", matchD: "Flip two cards: a term and what it means.",
      none: "Nothing to practice here yet.", again: "Play again", next: "Next chart", done: "Done!", slips: (n) => n ? `${n} slip${n > 1 ? "s" : ""}` : "no slips",
      tray: "Cards", hint: "Tap a card, then tap its place, or drag it there.", pairs: "pairs found", tries: "tries", chartN: (i, n) => `Chart ${i} of ${n}`, all: "All matched",
      kp: "Kosher or pasul", kpD: "Swipe right or left, or tap, for each case.", round: (i, n) => `${i} of ${n}`, right: "Right!", wrong: "Not quite", score: (a, n) => `${a} of ${n} right`, swipe: "← swipe →",
      who: "Who said it", whoD: "Match each sage or school to the position they hold.", whoQ: "Who holds this?", roundN: (i, n) => `Round ${i} of ${n}`, nextR: "Next round", review: "See it in the outline:", next1: "Next ›", peek: "See it in the outline", according: "According to", navPrev: "Previous", navNext: "Skip to the next", skipped: (n) => n ? ` ${n} skipped.` : "" },
    he: { title: "תרגול", back: "› כל המשחקים", chart: "השלימו את הטבלה", chartD: "גררו כל כרטיס למקומו בטבלה.", match: "התאמת מושגים", matchD: "הפכו שני כרטיסים: מושג והפירוש שלו.",
      none: "אין עדיין מה לתרגל כאן.", again: "שוב", next: "הטבלה הבאה", done: "סיימתם!", slips: (n) => n ? `${n} טעויות` : "בלי טעויות",
      tray: "כרטיסים", hint: "הקישו על כרטיס ואז על מקומו, או גררו אותו.", pairs: "זוגות", tries: "ניסיונות", chartN: (i, n) => `טבלה ${i} מתוך ${n}`, all: "הכול הותאם",
      kp: "כשר או פסול", kpD: "החליקו ימינה או שמאלה, או הקישו, על כל מקרה.", round: (i, n) => `${i} מתוך ${n}`, right: "נכון!", wrong: "לא בדיוק", score: (a, n) => `${a} מתוך ${n} נכונות`, swipe: "← החליקו →",
      who: "מי אמר", whoD: "התאימו כל חכם או בית מדרש לעמדה שלו.", whoQ: "מי סבור כך?", roundN: (i, n) => `סבב ${i} מתוך ${n}`, nextR: "הסבב הבא", review: "ראו בסכמה:", next1: "‹ הבא", peek: "ראו בסכמה", according: "לדעת", navPrev: "הקודם", navNext: "דלגו לבא", skipped: (n) => n ? ` ${n} דולגו.` : "" },
  };

  // Every chart with the section it sits in: id (so a game can send the reader there) and a short trail of
  // section titles (the context a bare chart row lacks).
  function chartSections(outline) {
    const out = [];
    (function walk(ns, trail) { (ns || []).forEach((n) => {
      const t = trail.concat(plain(n.title));
      if (n.chart && (n.chart.rows || []).length) out.push({ c: n.chart, id: n.id, crumb: t.slice(-2).join(" › "), title: plain(n.title) });
      walk(n.children || n.sections, t); }); })(outline && outline.sections, []);
    return out;
  }
  const charts = (outline) => chartSections(outline).filter((x) => x.c.rows.length >= 2 && (x.c.columns || []).length >= 3);

  // Who-said-it rounds: a chart whose every row is a party (a sage or a school) and a column whose cells
  // (the positions) are all different and short. Rows that name a case are not parties, so the chart is skipped.
  const PARTY = /^(R\.|Rabbi|Rav\b|Rabbah|Rava\b|Abaye|Beit|Bet\b|Tanna|Chachamim|The Sages|Ulla|Shmuel|Rebbi|Ravina|Rabban|Reish|Resh|Rebbe|Tosefta|Mishnah|Gemara|Rashi|Tosafot|Rambam)/i;
  function partyRounds(outline, sages) {
    const names = new Set((sages || []).map((x) => plain(x.en).replace(/\s*\[.*?\]/g, "").trim()).filter(Boolean)), out = [];
    chartSections(outline).forEach(({ c, id, crumb }) => {
      if (c.rows.length < 2 || !c.rows.every((r) => PARTY.test(plain(r[0])) || names.has(plain(r[0])))) return;
      const labs = c.rows.map((r) => plain(r[0]));
      if (new Set(labs).size !== labs.length) return;
      for (let ci = 1; ci < c.columns.length; ci++) {
        const cells = c.rows.map((r) => r[ci]);
        if (new Set(cells.map(plain)).size === cells.length && cells.every((t) => t && plain(t).split(/\s+/).length <= 18 && !/\n/.test(t)))
          out.push({ id, crumb, q: plain(c.columns[ci]), caption: c.caption, pairs: c.rows.map((r) => ({ who: r[0], pos: r[ci] })).slice(0, 5) });
      }
    });
    return out;
  }

  // Verdict items: chart cells that state a ruling. The card gives the section, the chart's caption, and the
  // row and column the cell sits under; the answer is the cell's tone, and the two buttons are named for what
  // the ruling is about (Betrothed / Not betrothed, Valid / Not valid ...), found in the cell itself first and
  // then in its column heading, the caption and the section title. Where no such pair can be found the cell is
  // left out: a bare Yes / No leaves the reader guessing what is being asked.
  const DYADS = [[/betroth/i, "Betrothed", "Not betrothed"], [/divorc/i, "Divorced", "Not divorced"], [/valid/i, "Valid", "Not valid"],
    [/acquir/i, "Acquired", "Not acquired"], [/effective|take[s]? effect/i, "Takes effect", "Does not take effect"], [/permit|forbid|prohibit|allowed/i, "Permitted", "Forbidden"]];
  const dyadIn = (...texts) => { for (const t of texts) { const d = DYADS.find(([re]) => re.test(t || "")); if (d) return d; } return null; };
  const GENERIC_COL = /^(ruling|result|outcome|verdict|law|halakha|conclusion|ruling and basis)\b/i;
  function verdicts(outline) {
    const O = global.AnyDafOutline, out = [];
    chartSections(outline).forEach(({ c, id, crumb, title }) => {
      c.rows.forEach((r, ri) => r.forEach((x, ci) => {
        if (!ci || /\n/.test(x)) return;
        const lead = plain(x).split(/[:;]/)[0];
        // a cell is a verdict when it is short, or when it opens with the verdict and then gives its reason
        if (plain(x).split(/\s+/).length > 7 && !(lead.split(/\s+/).length <= 4 && dyadIn(lead))) return;
        const given = Array.isArray(c.tones) ? (c.tones[ri] || [])[ci] : undefined;
        const tone = given !== undefined ? given : (O && O.cellTone ? O.cellTone(O.md(x)) : null);
        if (tone !== "ok" && tone !== "no") return;
        const head = plain(c.columns[ci]), d = dyadIn(lead, head, c.caption, title);
        if (!d) return;
        const who = plain(r[0]);
        out.push({ id, crumb, caption: plain(c.caption), who, party: PARTY.test(who), what: GENERIC_COL.test(head) ? "" : head, ok: tone === "ok", said: x, labels: [d[1], d[2]] });
      }));
    });
    return out;
  }

  // Drag-or-tap placing of tray cards onto slots, shared by the games that match cards to places.
  // place(card, slot) returns true when the card was placed. A press that doesn't move is a tap:
  // tap a card, then tap its place (also by keyboard); pointer events make dragging work on touch too.
  function placer(tray, slots, place) {
    let picked = null, drag = null;
    const select = (card) => { tray.querySelectorAll(".sel").forEach((x) => x.classList.remove("sel")); picked = card; if (card) card.classList.add("sel"); };
    const tryIt = (card, slot) => { if (place(card, slot)) select(null); };
    tray.addEventListener("click", (e) => { const k = e.target.closest(".adg-card"); if (k && !drag) select(picked === k ? null : k); });
    slots.forEach((s) => { s.onclick = () => { if (picked) tryIt(picked, s); }; s.onkeydown = (e) => { if ((e.key === "Enter" || e.key === " ") && picked) { e.preventDefault(); tryIt(picked, s); } }; });
    tray.addEventListener("keydown", (e) => { const k = e.target.closest(".adg-card"); if (k && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); select(picked === k ? null : k); } });
    tray.addEventListener("pointerdown", (e) => {
      const k = e.target.closest(".adg-card"); if (!k) return;
      drag = { k, x: e.clientX, y: e.clientY, ghost: null, moved: false }; k.setPointerCapture(e.pointerId);
    });
    tray.addEventListener("pointermove", (e) => {
      if (!drag) return;
      if (!drag.moved && Math.hypot(e.clientX - drag.x, e.clientY - drag.y) < 6) return;
      if (!drag.moved) { drag.moved = true; const g = drag.k.cloneNode(true); g.classList.add("adg-ghost"); g.style.width = drag.k.offsetWidth + "px"; document.body.appendChild(g); drag.ghost = g; drag.k.classList.add("lifted"); }
      drag.ghost.style.left = e.clientX - drag.ghost.offsetWidth / 2 + "px"; drag.ghost.style.top = e.clientY - 16 + "px";
      const over = slotAt(e.clientX, e.clientY); slots.forEach((s) => s.classList.toggle("over", s === over));
    });
    const slotAt = (x, y) => slots.find((s) => { const r = s.getBoundingClientRect(); return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom; });
    const endDrag = (e) => {
      if (!drag) return; const d = drag; drag = null; slots.forEach((s) => s.classList.remove("over"));
      if (d.ghost) { d.ghost.remove(); d.k.classList.remove("lifted"); tryIt(d.k, slotAt(e.clientX, e.clientY)); }
    };
    tray.addEventListener("pointerup", endDrag); tray.addEventListener("pointercancel", () => { if (drag && drag.ghost) drag.ghost.remove(); if (drag) drag.k.classList.remove("lifted"); drag = null; });
  }

  function mount(el, data, opts = {}) {
    const lang = opts.lang === "he" ? "he" : "en", W = WORDS[lang];
    el.classList.add("adg"); el.setAttribute("dir", lang === "he" ? "rtl" : "ltr"); if (lang === "he") el.lang = "he";
    const chartList = charts(data.outline);
    const terms = (data.keyTerms || []).filter((t) => t.term && (t.sense || t.definition));
    const verdictList = verdicts(data.outline), roundList = partyRounds(data.outline, data.sages);
    const games = [
      { id: "chart", name: W.chart, desc: W.chartD, ok: chartList.length > 0, start: () => chartGame(0) },
      { id: "match", name: W.match, desc: W.matchD, ok: terms.length >= 3, start: matchGame },
      { id: "who", name: W.who, desc: W.whoD, ok: roundList.length > 0, start: () => whoGame() },
      { id: "kp", name: W.kp, desc: W.kpD, ok: verdictList.length >= 4, start: kosherGame },
    ].filter((g) => g.ok);
    let teardown = null;
    // After a game, "See this in the outline" buttons for what was missed (or, for charts, always).
    const reviewHTML = (m) => m.size ? `<div class="adg-rev">${[...m.values()].every((t) => t === W.peek) ? "" : `<span>${W.review}</span>`}${[...m].map(([id, t]) => `<button type="button" class="adg-btn" data-rev="${esc(id)}">${esc(t)}</button>`).join("")}</div>` : "";
    // ‹ › in a game's bar: move to the preceding or following round (a chart that is too hard, material not yet covered)
    const navHTML = () => `<span class="adg-nav"><button type="button" data-nav="-1" aria-label="${W.navPrev}" title="${W.navPrev}">‹</button><button type="button" data-nav="1" aria-label="${W.navNext}" title="${W.navNext}">›</button></span>`;
    const wireNav = (prev, next) => el.querySelectorAll("[data-nav]").forEach((b) => b.onclick = () => (+b.dataset.nav < 0 ? prev : next)());
    const wireReview = (root) => root.querySelectorAll("[data-rev]").forEach((b) => b.onclick = () => opts.onReview && opts.onReview(b.dataset.rev));
    const clear = () => { if (teardown) teardown(); teardown = null; };

    function menu() {
      clear();
      el.innerHTML = `<div class="adg-menu"><p class="adg-sub">${esc(data.title || "")}</p>${games.length ? games.map((g) =>
        `<button type="button" class="adg-game" data-g="${g.id}"><b>${esc(g.name)}</b><span>${esc(g.desc)}</span></button>`).join("") : `<p>${W.none}</p>`}</div>`;
      el.querySelectorAll("[data-g]").forEach((b) => b.onclick = () => games.find((g) => g.id === b.dataset.g).start());
    }
    function shell(name, inner, side = "") {
      clear();
      el.innerHTML = `<div class="adg-bar"><button type="button" class="adg-back">${W.back}</button><b>${esc(name)}</b><span class="adg-side">${side}</span></div><div class="adg-body">${inner}</div>`;
      el.querySelector(".adg-back").onclick = menu;
      return el.querySelector(".adg-body");
    }

    // ---------- Fill in the chart ----------
    function chartGame(idx) {
      const item = chartList[idx], c = item.c, cols = c.columns, rows = c.rows;
      // every body cell is a blank, but never more than ~9, so a card tray stays easy to scan
      let cells = [];
      rows.forEach((r, ri) => r.forEach((x, ci) => { if (ci) cells.push({ ri, ci, text: x }); }));
      const given = new Set();
      if (cells.length > 9) shuffle(cells).slice(0, cells.length - 9).forEach((x) => given.add(x.ri + "," + x.ci));
      const blanks = cells.filter((x) => !given.has(x.ri + "," + x.ci));
      let slips = 0, placed = 0;
      const body = shell(W.chart,
        `<p class="adg-crumb">${esc(item.crumb)}</p><p class="adg-cap">${md(c.caption)}</p><p class="adg-hint">${W.hint}</p>
         <div class="adg-chart"><table><thead><tr>${cols.map((h) => `<th scope="col">${md(h)}</th>`).join("")}</tr></thead><tbody>${rows.map((r, ri) =>
           `<tr>${r.map((x, ci) => ci === 0 ? `<th scope="row">${md(x)}</th>` : given.has(ri + "," + ci) ? `<td class="given">${md(x)}</td>`
             : `<td class="slot" data-r="${ri}" data-c="${ci}" tabindex="0"></td>`).join("")}</tr>`).join("")}</tbody></table></div>
         <div class="adg-tray" aria-label="${W.tray}"></div><div class="adg-end" hidden></div>`,
        chartList.length > 1 ? `<span>${W.chartN(idx + 1, chartList.length)}</span>${navHTML()}` : "");
      if (chartList.length > 1) wireNav(() => chartGame((idx + chartList.length - 1) % chartList.length), () => chartGame((idx + 1) % chartList.length));
      const tray = body.querySelector(".adg-tray");
      // cards are distinct texts; two blanks with the same text share one card each, any slot with that text accepts it
      shuffle(blanks).forEach((b, i) => { const k = document.createElement("div"); k.className = "adg-card"; k.dataset.i = i; k.dataset.t = plain(b.text); k.tabIndex = 0; k.innerHTML = md(b.text); tray.appendChild(k); });
      const slots = [...body.querySelectorAll(".slot")];
      const want = (s) => plain(rows[+s.dataset.r][+s.dataset.c]);
      function tryPlace(card, slot) {
        if (!card || !slot || slot.classList.contains("full")) return false;
        if (want(slot) === card.dataset.t) {
          slot.innerHTML = card.innerHTML; slot.classList.add("full", "good"); card.remove(); placed++;
          if (placed === blanks.length) finish();
          return true;
        }
        slips++; slot.classList.add("bad"); card.classList.add("bad"); setTimeout(() => { slot.classList.remove("bad"); card.classList.remove("bad"); }, 450);
        return false;
      }
      function finish() {
        const e = body.querySelector(".adg-end"); e.hidden = false; tray.hidden = true; body.querySelector(".adg-hint").hidden = true;
        const more = idx + 1 < chartList.length;
        e.innerHTML = `<p><b>${W.done}</b> ${W.slips(slips)}.</p><button type="button" class="adg-btn" id="adgAgain">${W.again}</button>${more ? `<button type="button" class="adg-btn pri" id="adgNext">${W.next}</button>` : ""}${reviewHTML(new Map([[item.id, W.peek]]))}`; wireReview(e);
        e.querySelector("#adgAgain").onclick = () => chartGame(idx);
        if (more) e.querySelector("#adgNext").onclick = () => chartGame(idx + 1);
      }
      placer(tray, slots, tryPlace);
      teardown = () => { document.querySelectorAll(".adg-ghost").forEach((g) => g.remove()); };
    }

    // ---------- Term match ----------
    function matchGame() {
      const pick = shuffle(terms).slice(0, 6);
      const cards = shuffle(pick.flatMap((t, i) => [
        { i, kind: "term", html: `<b>${esc(t.term)}</b>${t.hebrew && t.hebrew !== t.term ? `<span lang="he" class="he">${esc(t.hebrew)}</span>` : ""}` },
        { i, kind: "sense", html: md(t.sense || String(t.definition).split(/(?<=[.!?])\s/)[0]) }]));
      let open = [], found = 0, tries = 0, lock = false;
      const body = shell(W.match, `<div class="adg-grid" style="--n:${pick.length > 4 ? 3 : 2}">${cards.map((c, n) =>
        `<button type="button" class="adg-flip ${c.kind}" data-n="${n}" aria-label="card ${n + 1}"><span class="face back">?</span><span class="face front">${c.html}</span></button>`).join("")}</div>
        <p class="adg-note" aria-live="polite"></p><div class="adg-end" hidden></div>`, `<span class="adg-sc"></span>`);
      const sc = el.querySelector(".adg-sc"), note = body.querySelector(".adg-note");
      const score = () => { sc.textContent = `${found}/${pick.length} ${W.pairs} · ${tries} ${W.tries}`; }; score();
      body.querySelector(".adg-grid").addEventListener("click", (e) => {
        const b = e.target.closest(".adg-flip"); if (!b || lock || b.classList.contains("up") || b.classList.contains("got")) return;
        b.classList.add("up"); open.push(b);
        if (open.length < 2) return;
        tries++; const [a, c] = open, A = cards[+a.dataset.n], C = cards[+c.dataset.n];
        if (A.i === C.i && A.kind !== C.kind) {
          found++; open = []; [a, c].forEach((x) => { x.classList.remove("up"); x.classList.add("got"); });
          const t = pick[A.i]; note.innerHTML = `<b>${esc(t.term)}</b> — ${esc(String(t.definition || "").split(/(?<=[.!?])\s/).slice(0, 2).join(" "))}`;
          if (found === pick.length) { const en = body.querySelector(".adg-end"); en.hidden = false; en.innerHTML = `<p><b>${W.all}</b> · ${tries} ${W.tries}</p><button type="button" class="adg-btn pri" id="adgAgain">${W.again}</button>`; en.querySelector("#adgAgain").onclick = matchGame; }
        } else { lock = true; [a, c].forEach((x) => x.classList.add("miss")); setTimeout(() => { [a, c].forEach((x) => x.classList.remove("up", "miss")); open = []; lock = false; }, 2400); }
        score();
      });
    }

    // ---------- Who said it ----------
    function whoGame(rounds, r = 0) {
      rounds = rounds || shuffle(roundList).slice(0, 3);
      const R = rounds[r]; let slips = 0, placed = 0; if (!r) whoGame.slips = 0;
      const body = shell(W.who, `<p class="adg-crumb">${esc(R.crumb)}</p><p class="adg-cap">${md(R.caption)}</p>
        <p class="adg-q">${W.whoQ} <b>${md(R.q)}</b></p><p class="adg-hint">${W.hint}</p>
        <div class="adg-who-slots">${shuffle(R.pairs).map((p) => `<div class="adg-pos"><p>${md(p.pos)}</p><div class="slot" data-w="${esc(plain(p.who))}" tabindex="0" aria-label="${W.whoQ}"></div></div>`).join("")}</div>
        <div class="adg-tray" aria-label="${W.tray}"></div><div class="adg-end" hidden></div>`, rounds.length > 1 ? `<span>${W.roundN(r + 1, rounds.length)}</span>${navHTML()}` : "");
      if (rounds.length > 1) wireNav(() => whoGame(rounds, (r + rounds.length - 1) % rounds.length), () => whoGame(rounds, (r + 1) % rounds.length));
      const tray = body.querySelector(".adg-tray"), slots = [...body.querySelectorAll(".slot")];
      shuffle(R.pairs).forEach((p) => { const k = document.createElement("div"); k.className = "adg-card"; k.dataset.t = plain(p.who); k.tabIndex = 0; k.innerHTML = md(p.who); tray.appendChild(k); });
      placer(tray, slots, (card, slot) => {
        if (!card || !slot || slot.classList.contains("full")) return false;
        if (slot.dataset.w === card.dataset.t) {
          slot.innerHTML = card.innerHTML; slot.classList.add("full", "good"); card.remove();
          if (++placed === R.pairs.length) done();
          return true;
        }
        slips++; whoGame.slips++; slot.classList.add("bad"); card.classList.add("bad"); setTimeout(() => { slot.classList.remove("bad"); card.classList.remove("bad"); }, 450);
        return false;
      });
      function done() {
        const e = body.querySelector(".adg-end"); e.hidden = false; tray.hidden = true; body.querySelector(".adg-hint").hidden = true;
        const more = r + 1 < rounds.length;
        e.innerHTML = `<p><b>${W.done}</b> ${W.slips(more ? slips : whoGame.slips)}.</p>${more ? `<button type="button" class="adg-btn pri" id="adgNext">${W.nextR}</button>` : `<button type="button" class="adg-btn pri" id="adgAgain">${W.again}</button>`}${reviewHTML(new Map([[R.id, W.peek]]))}`;
        if (more) e.querySelector("#adgNext").onclick = () => whoGame(rounds, r + 1); else e.querySelector("#adgAgain").onclick = () => whoGame();
        wireReview(e);
      }
    }

    // ---------- Kosher or pasul ----------
    function kosherGame() {
      const items = shuffle(verdictList).slice(0, 8), res = [];
      let i = 0, busy = false, streak = 0, timer = null;
      const body = shell(W.kp, `<div class="adg-kp"><p class="adg-hint">${W.swipe}</p><div class="adg-stage"><div class="adg-case" tabindex="0"></div></div>
        <div class="adg-verdicts"><button type="button" class="adg-v no" data-a="no"></button><button type="button" class="adg-v ok" data-a="ok"></button></div>
        <p class="adg-fb" aria-live="polite"></p><div class="adg-after" hidden></div></div><div class="adg-end" hidden></div>`, `<span class="adg-sc"></span>${navHTML()}`);
      const card = body.querySelector(".adg-case"), fb = body.querySelector(".adg-fb"), after = body.querySelector(".adg-after"), sc = el.querySelector(".adg-sc"), btns = [...body.querySelectorAll(".adg-v")];
      function show() {
        const it = items[i]; busy = false; clearTimeout(timer); body.querySelector(".adg-kp").hidden = false; body.querySelector(".adg-end").hidden = true; fb.textContent = ""; fb.className = "adg-fb"; after.hidden = true;
        card.className = "adg-case"; card.style.transform = "";
        card.innerHTML = `<span class="adg-crumb">${esc(it.crumb)}</span><span class="adg-scn">${esc(it.caption)}</span>`
          + (it.party ? `<span class="adg-acc">${W.according} <b>${esc(it.who)}</b></span>` : `<span class="adg-who">${esc(it.who)}</span>`)
          + (it.what ? `<span class="adg-what">${esc(it.what)}</span>` : "");
        btns[0].textContent = "✗ " + it.labels[1]; btns[1].textContent = "✓ " + it.labels[0];
        btns.forEach((b) => b.disabled = false); sc.textContent = W.round(i + 1, items.length) + (streak > 1 ? " · 🔥 " + streak : "");
      }
      const advance = () => { clearTimeout(timer); if (!card.isConnected) return; i++; i < items.length ? show() : finish(); };
      wireNav(() => { if (i > 0) { i--; show(); } }, () => { if (i < items.length) advance(); });
      function answer(a) {
        if (busy) return; busy = true; const it = items[i], good = (a === "ok") === it.ok, shown = it.labels[it.ok ? 0 : 1];
        btns.forEach((b) => b.disabled = true);
        res[i] = good; streak = good ? streak + 1 : 0;
        card.classList.add(good ? "good" : "bad", it.ok ? "isok" : "isno");
        fb.className = "adg-fb " + (good ? "good" : "bad");
        fb.innerHTML = `<b>${good ? W.right : W.wrong}</b> ${esc(shown)}${plain(it.said).toLowerCase() === shown.toLowerCase() ? "" : " — " + md(it.said)}`;
        if (good) timer = setTimeout(advance, 1100);
        else {   // a miss waits for the reader: read the reason, or go and look at the discussion
          after.hidden = false; after.innerHTML = `<button type="button" class="adg-btn" data-rev="${esc(it.id)}">${W.peek}</button><button type="button" class="adg-btn pri" id="adgNext1">${W.next1}</button>`;
          wireReview(after); after.querySelector("#adgNext1").onclick = advance;
        }
      }
      function finish() {
        body.querySelector(".adg-kp").hidden = true; const e = body.querySelector(".adg-end"); e.hidden = false;
        const missed = new Map(); items.forEach((it, k) => { if (res[k] === false) missed.set(it.id, it.crumb); });
        const answered = res.filter((x) => x !== undefined).length;
        e.innerHTML = `<p><b>${W.done}</b> ${W.score(res.filter(Boolean).length, answered)}.${W.skipped(items.length - answered)}</p><button type="button" class="adg-btn pri" id="adgAgain">${W.again}</button>${reviewHTML(missed)}`;
        e.querySelector("#adgAgain").onclick = kosherGame; wireReview(e);
      }
      btns.forEach((b) => b.onclick = () => answer(b.dataset.a));
      const key = (e) => { if (e.key === "ArrowRight") answer("ok"); else if (e.key === "ArrowLeft") answer("no"); else if (e.key === "Enter" && !after.hidden) advance(); };
      el.addEventListener("keydown", key); teardown = () => { clearTimeout(timer); el.removeEventListener("keydown", key); };
      // swipe: drag the card sideways past 70px
      let sx = null;
      card.addEventListener("pointerdown", (e) => { if (busy) return; sx = e.clientX; card.setPointerCapture(e.pointerId); });
      card.addEventListener("pointermove", (e) => { if (sx == null) return; const dx = e.clientX - sx; card.style.transform = `translateX(${dx}px) rotate(${dx / 25}deg)`;
        card.classList.toggle("lean-ok", dx > 30); card.classList.toggle("lean-no", dx < -30); });
      const up = (e) => { if (sx == null) return; const dx = e.clientX - sx; sx = null; card.classList.remove("lean-ok", "lean-no");
        if (Math.abs(dx) > 70) { card.style.transform = ""; answer(dx > 0 ? "ok" : "no"); } else card.style.transform = ""; };
      card.addEventListener("pointerup", up); card.addEventListener("pointercancel", () => { sx = null; card.style.transform = ""; });
      show();
    }

    menu();
    return { destroy() { clear(); el.innerHTML = ""; el.classList.remove("adg"); }, menu, hasGames: games.length > 0 };
  }

  global.AnyDafGames = { mount, _items: { verdicts, partyRounds } };
})(typeof window !== "undefined" ? window : globalThis);
