/* AnyDaf study-outline renderer — shared by the web app and the iOS/Android WebViews.
 *
 * Framework-free on purpose: the web app wraps it in a React component, and the phone apps
 * load it into WKWebView / Android WebView as-is. Everything it draws is scoped under `.ado`
 * (outline-renderer.css). Input is the per-daf JSON from daf-processor's outline pass
 * (04_outline_*.json) plus, optionally, its key terms (05_key_terms_*.json).
 *
 *   const view = AnyDafOutline.render(el, { outline, keyTerms, onTerm, onSection, sages, onSage });
 *   view.setLevel(1|2|3); view.setOption("shiur"|"charts"|"pictures"|"sages", bool);
 *   // Key terms and sages link at their first mention on the daf.
 *   // sages: [{aliases: [English spellings]}] -> each sage's first mention on the daf becomes a
 *   // button (.ado-sage, data-sage = index); onSage(i) opens the host's sages panel
 *   view.setGlanceDepth(1..5) // levels shown in the inline "At a glance" list (default 2)
 *   // the inline list starts folded (glanceOpen: false); onGlanceOpen(bool) reports the reader's choice
 *   view.sections            // [{id, title, from, to, depth, el, head}] in document order
 *   view.scrollToSection(id)
 *   view.markCurrent(id)
 *
 * The outline opens with an "At a glance" list of its section titles (turn off with glance:false),
 * so a major discussion nested a level down still shows up in the bird's-eye view. The list has
 * its own depth control (1–5; glanceDepth / onGlanceDepth). A host with room can show the same
 * list in its own panel instead, where it stays in view:
 *
 *   const g = AnyDafOutline.glance(el, outline, { onSection, depth, onDepth });  g.mark(id); g.setDepth(n)
 *
 *   AnyDafOutline.glossary(el, keyTerms, { titles, onSection, order })  -> { focus(i), setOrder('daf'|'alpha'), filter(q) }
 *
 * Model-written SVG must be sanitized before it reaches here (build step: clean_svg +
 * uniquify_ids in daf-processor/build_outline_review.py). The renderer inserts it as markup.
 */
(function (global) {
  "use strict";

  const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const md = (s) => esc(s).replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/\*([^*]+)\*/g, "<i>$1</i>");

  function flat(nodes, depth = 1, out = []) {
    (nodes || []).forEach((n) => { out.push({ n, depth }); flat(n.children, depth + 1, out); });
    return out;
  }

  /* Key-term highlighting: the first occurrence of each term's aliases on the daf (gists and
   * bullets) becomes a button. Matching runs over text between tags only, so it never breaks the
   * <i>/<b> markup, and aliases are tried longest first ("olat tamid" before "tamid"). */
  function termMatcher(keyTerms) {
    const pairs = [];
    // The term itself always counts, and every spelling is also tried with the prefix mark written
    // either way (u-ketumah / u'ketumah / u’ketumah): older outlines used dashes, newer apostrophes.
    (keyTerms || []).forEach((t, i) => [t.term, ...(t.aliases || [])].forEach((a) => {
      if (!a) return;
      new Set([a, a.replace(/-/g, "'"), a.replace(/'/g, "’"), a.replace(/-/g, "’")]).forEach((v) => pairs.push([v, i]));
    }));
    if (!pairs.length) return null;
    pairs.sort((x, y) => y[0].length - x[0].length);
    const byAlias = new Map(pairs.map(([a, i]) => [a.toLowerCase(), i]));
    const alt = pairs.map(([a]) => a.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|");
    const re = new RegExp(`(?<![\\w'’])(${alt})(?![\\w'’])`, "gi");
    return function mark(html, seen) {
      return html.split(/(<[^>]+>)/).map((part) => part.startsWith("<") ? part : part.replace(re, (m, _g, off, whole) => {
        const i = byAlias.get(m.toLowerCase());
        if (i === undefined || seen.has(i)) return m;
        // a term right after a negation is its opposite (shelo lishmah, she'ein mesurin): not this entry
        if (/(?:^|[\s(*])(?:shelo|she['’]lo|she['’]ein|she['’]eino|she['’]einah|lo|ein|eino|einah)\s+$/i.test(whole.slice(Math.max(0, off - 12), off))) return m;
        seen.add(i);
        return `<button type="button" class="ado-term" data-term="${i}">${m}</button>`;
      })).join("");
    };
  }

  /* Sage highlighting. Spellings vary between the outline and the sages' name lists (R./Rabbi,
   * Yochanan/Yohanan, Yosei/Yose/Yossi, Yirmeya/Yirmeyah), so names are compared by a folded
   * skeleton: title words normalized, then per word the first letter, the consonants after it,
   * and whether it ends in a vowel ("Rav" and "Rava" stay apart). Candidates in the text are a
   * title plus capitalized words, or a one-word name; the longest candidate that folds to a
   * sage on this daf wins, trimming words from the end ("R. Abba's Challenge" -> "R. Abba"). */
  const TITLE = { r: "r", rabbi: "r", rebbi: "r", "r.": "r" };
  function foldWord(w) {
    w = w.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[’'`]/g, "");
    if (TITLE[w]) return TITLE[w];
    if (w === "b." || w === "ben" || w === "bar" || w === "b") return "b";
    w = w.replace(/kh|ch/g, "h").replace(/([aeiou])h$/, "$1").replace(/(.)\1+/g, "$1");
    const end = /[aeiouy]$/.test(w) && w.length > 1 ? "V" : "";
    return w[0] + w.slice(1).replace(/[aeiouy]/g, "") + end;
  }
  // "son of R. X", "bar R. X", "b. Rabbi X" all fold to "b X".
  const foldName = (name) => name.replace(/[’']s$/, "").replace(/\bson of\b/g, "b").replace(/^#/, "")
    .split(/\s+/).filter(Boolean).map(foldWord).join(" ").replace(/\bb r\b/g, "b");
  const NAME_RE = /(?<![\w'’])(?:R\.|Rabbi|Rebbi|Rav|Rabban|Rabbah|Rabba|Mar|Bar|Reish)(?:\s+(?:b\.|ben|bar|son of|[A-Z][\w'’-]*)){1,6}|(?<![\w'’])[A-Z][a-z'’-]{2,}/g;
  function sageMatcher(sages) {
    const byFold = new Map();
    (sages || []).forEach((sg, i) => (sg.aliases || []).forEach((a) => {
      const f = foldName(a);
      if (f && !byFold.has(f)) byFold.set(f, i);
    }));
    if (!byFold.size) return null;
    return function markSages(html, seen) {
      let inButton = 0;
      return html.split(/(<[^>]+>)/).map((part) => {
        if (part.startsWith("<")) { if (/^<button/.test(part)) inButton++; else if (/^<\/button/.test(part)) inButton--; return part; }
        if (inButton) return part;
        return part.replace(NAME_RE, (m) => {
          const words = m.split(/\s+/);
          for (let n = words.length; n >= 1; n--) {
            const head = words.slice(0, n).join(" "), bare = head.replace(/[’']s$/, "");
            // Trimming may drop a trailing ordinary word ("Challenge"), but never part of a longer
            // name: not a patronymic ("Rabbah | bar Rav Huna"), and not the name after a bare
            // title ("Rav | Nachman bar Yitzchak" is not Rav).
            if (n < words.length && (/^(b\.|ben|bar|son)$/.test(words[n]) || /^(R\.|Rabbi|Rebbi|Rav|Rabban|Mar|Reish)$/.test(bare))) continue;
            const i = byFold.get(foldName(bare));
            if (i === undefined) continue;
            const rest = m.slice(bare.length);
            if (seen.has("s" + i)) return m;
            seen.add("s" + i);
            return `<button type="button" class="ado-sage" data-sage="${i}">${bare}</button>${rest}`;
          }
          return m;
        });
      }).join("");
    };
  }

  // Rulings and outcomes in chart cells read at a glance: permitted / valid / acquired / succeeds in
  // green, forbidden / invalid / not acquired / fails in red (the same colours as the pictures'
  // check and X marks). Negative forms are matched first, so "not acquired" never turns green.
  // Liable / exempt are left alone: whether liability is the good or bad outcome depends on the case.
  const NO = String.raw`not\s+permitted|not\s+allowed|forbidden|prohibited|invalid|not\s+valid|ineffective|not\s+effective|` +
    String.raw`fails|failed|does\s+not\s+(?:succeed|acquire|take\s+effect)|doesn['’]t\s+(?:succeed|acquire|take\s+effect)|` +
    String.raw`not\s+acquired|no\s+acquisition|not\s+betrothed|no\s+betrothal`;
  const OK = String.raw`permitted|allowed|valid|effective|succeeds|succeeded|acquires|acquired|takes\s+effect|betrothed`;
  const RULING = new RegExp(String.raw`(^|[^\w'’-])(` + NO + String.raw`)(?![\w-])|(^|[^\w'’-])(` + OK + String.raw`)(?![\w-])`, "gi");
  function rulings(html) {
    // only outside tags: split on tags and color the text runs
    return html.split(/(<[^>]+>)/).map((part) => part.startsWith("<") ? part :
      part.replace(RULING, (m, p1, no, p2, ok) => no ? `${p1}<span class="ado-no">${no}</span>` : `${p2}<span class="ado-ok">${ok}</span>`)).join("");
  }

  // A cell that states one ruling is coloured whole, sentence and all, whether or not it uses the
  // keyword ("Fully cooked food may be eaten even if left intentionally" is green; "Beit Hillel
  // permit leaving the food" is green). A cell that says both ("permitted on Shabbat, forbidden on
  // Yom Tov") stays plain, with only its ruling words coloured.
  const CELL_NO = new RegExp(String.raw`(?:^|[^\w'’-])(?:` + NO +
    String.raw`|may\s+not|must\s+not|may\s+no\s+longer|cannot\s+be\s+(?:eaten|used|redeemed)|forbids?|prohibits?)(?![\w-])`, "gi");
  const CELL_OK = new RegExp(String.raw`(?:^|[^\w'’-])(?:` + OK +
    String.raw`|permits?|may(?=\s+(?:be\s+\w+(?:ed|en|wn|lt|ld|ne|ut|ft|ght)\b|(?!(?:not|no|be|have|also|well|seem|mean|come|still)\b)\w+))|can\s+be\s+(?:eaten|used|redeemed))(?![\w-])`, "gi");
  function cellTone(html) {
    const text = html.replace(/<[^>]+>/g, " ")
      .replace(/[“"][^”"]*[”"]/g, " ")                                   // quoted formulas and verses
      .replace(/\b(?:that|lest|in\s+case)\s+(?:\S+\s+){0,2}may\b/gi, " ")   // "concern that he may sin"
      .replace(/\b(?:answer|proof|argument|reading|objection|question|explanation|challenge|source|derivation|analogy|attempt|comparison)s?\s+(?:\S+\s+)?fail(?:s|ed)?\b/gi, " ");
    const no = (text.match(CELL_NO) || []).length;
    const ok = (text.replace(CELL_NO, " ").match(CELL_OK) || []).length;
    return no && !ok ? "no" : ok && !no ? "ok" : null;
  }
  function cellHTML(x, given) {
    // the outline's own marking (chart.tones) when it has one; reading the words only for older outlines
    const h = md(x), tone = given !== undefined ? given : cellTone(h);
    return tone ? `<td class="ado-cell-${tone}">${h}</td>` : `<td>${rulings(h)}</td>`;
  }

  function chartHTML(c) {
    const cols = (c.columns || []).map((h) => `<th scope="col">${md(h)}</th>`).join("");
    const tones = Array.isArray(c.tones) ? c.tones : null;
    const rows = (c.rows || []).map((r, ri) =>
      `<tr>${r.map((x, i) => (i ? cellHTML(x, tones ? ((tones[ri] || [])[i] ?? null) : undefined)
                                 : `<th scope="row">${md(x)}</th>`)).join("")}</tr>`).join("");
    return `<div class="ado-chart"><table><caption>${md(c.caption)}</caption><thead><tr>${cols}</tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  function illHTML(il) {
    return `<figure class="ado-ill"><div class="ado-art">${il.svg}</div><figcaption>${md(il.caption)}</figcaption></figure>`;
  }

  function rangeLabel(t) {
    if (!t || !t.from) return "";
    return t.from === t.to || !t.to ? t.from : `${t.from}–${t.to}`;
  }

  function outlineDepth(outline) {
    const d = (ns) => Math.max(0, ...(ns || []).map((n) => 1 + d(n.children)));
    return Math.max(1, d(outline.sections));
  }

  /* "At a glance": the outline's section titles, down to a chosen depth (1–5, default 2). The
   * depth control sits in the list's own header and changes only the list, never the outline.
   * Inline at the top of the outline it can fold away; in its own panel (which the host shows or
   * hides as a whole) it is always open. */
  function glanceHTML(outline, foldable, depth, open) {
    const tops = outline.sections || [];
    if (tops.length < 2 && !(tops[0]?.children || []).length) return "";
    const max = outlineDepth(outline);
    const d = Math.min(depth, max);
    const cls = (lv) => "ado-gl" + (lv >= 2 ? " ado-gl2" : "") + (lv >= 3 ? " ado-gl3" : "");
    const item = (n, lv) => `<li><button type="button" class="${cls(lv)}" data-goto="${esc(n.id)}">${md(n.title)}</button>` +
      `${lv === 1 ? `<span class="ado-glam">${esc(n.amud)}</span>` : ""}` +
      `${lv < d && (n.children || []).length ? `<ol>${n.children.map((c) => item(c, lv + 1)).join("")}</ol>` : ""}</li>`;
    const ctl = `<div class="ado-gldepth" role="group" aria-label="Contents depth"><span>Depth</span>${[1, 2, 3, 4, 5].map((k) =>
      `<button type="button" data-gd="${k}" aria-pressed="${k === d}"${k > max ? " disabled" : ""}>${k}</button>`).join("")}</div>`;
    const list = `<ol>${tops.map((n) => item(n, 1)).join("")}</ol>`;
    return foldable
      ? `<nav class="ado-glance" aria-label="At a glance"><details${open ? " open" : ""}><summary>At a glance</summary>${ctl}${list}</details></nav>`
      : `<nav class="ado-glance" aria-label="At a glance"><div class="ado-glhead"><h2 class="ado-glh">At a glance</h2>${ctl}</div>${list}</nav>`;
  }

  // For each section id: itself and all its ancestors; whichever are listed get highlighted.
  function glanceOwners(outline) {
    const owners = {};
    (function walk(ns, chain) {
      (ns || []).forEach((n) => { owners[n.id] = [...chain, n.id]; walk(n.children, owners[n.id]); });
    })(outline.sections, []);
    return owners;
  }

  function markGlance(root, owners, id, scroll) {
    root.querySelectorAll(".ado-gl.ado-on").forEach((x) => x.classList.remove("ado-on"));
    let last = null;
    (owners[id] || []).forEach((gid) => {
      const b = root.querySelector(`.ado-gl[data-goto="${CSS.escape(gid)}"]`);
      if (b) { b.classList.add("ado-on"); last = b; }
    });
    if (scroll && last) last.scrollIntoView({ block: "nearest" });
  }

  function mountGlance(el, outline, { foldable, depth = 2, open = false, onSection, onDepth, onOpen, scroll }) {
    const owners = glanceOwners(outline);
    let d = depth, marked = null, isOpen = open;
    const draw = () => { el.innerHTML = glanceHTML(outline, foldable, d, isOpen); if (marked) markGlance(el, owners, marked, false); };
    draw();
    // "toggle" doesn't bubble, so listen in the capture phase; the open state survives redraws.
    if (el._adoToggle) el.removeEventListener("toggle", el._adoToggle, true);
    el._adoToggle = (e) => { if (e.target.tagName !== "DETAILS") return; isOpen = e.target.open; onOpen && onOpen(isOpen); };
    el.addEventListener("toggle", el._adoToggle, true);
    if (el._adoGlance) el.removeEventListener("click", el._adoGlance);
    el._adoGlance = (e) => {
      const k = e.target.closest("[data-gd]");
      if (k && !k.disabled) { d = +k.dataset.gd; draw(); onDepth && onDepth(d); return; }
      const b = e.target.closest(".ado-gl");
      if (b && onSection) onSection(b.dataset.goto);
    };
    el.addEventListener("click", el._adoGlance);
    return {
      mark(id) { marked = id; markGlance(el, owners, id, scroll); },
      setDepth(n) { if (n !== d) { d = n; draw(); } },
    };
  }

  /* The glance in a panel of its own (web: a side column that stays in view). */
  function glance(container, outline, { onSection, depth, onDepth } = {}) {
    container.classList.add("ado", "ado-glance-panel");
    return mountGlance(container, outline, { foldable: false, depth, onSection, onDepth, scroll: true });
  }

  function render(container, opts) {
    const { outline, keyTerms = [], onTerm, onSection, glance = true, glanceDepth = 2, onGlanceDepth,
            glanceOpen = false, onGlanceOpen, sages = [], onSage } = opts;
    const markTerms = termMatcher(keyTerms), markSages = sageMatcher(sages);
    const mark = markTerms || markSages
      ? (html, seen, sageSeen) => { if (markTerms) html = markTerms(html, seen); return markSages ? markSages(html, sageSeen) : html; }
      : null;
    const titles = {};
    flat(outline.sections).forEach(({ n }) => (titles[n.id] = n.title));

    // Key terms and sages link once per daf, at the first mention. Text the reader can hide
    // (Detailed bullets, shiur insights) gets a link without using up that first mention, so the
    // first one always stays visible.
    const termsSeen = new Set(), sagesSeen = new Set();
    function nodeHTML(n, depth) {
      const m = (s, hideable) => (mark ? mark(md(s), hideable ? new Set(termsSeen) : termsSeen,
                                               hideable ? new Set(sagesSeen) : sagesSeen) : md(s));
      const ret = (n.returns_to || []).map((x) =>
        `<button type="button" class="ado-ret" data-goto="${esc(x.id)}">↩ Returns to ${md(titles[x.id] || x.id)}${x.note ? ` — ${md(x.note)}` : ""}</button>`).join("");
      // The gist is marked before the bullets: a name or term links where the reader meets it first.
      const gist = n.gist ? `<p class="ado-gist">${m(n.gist)}</p>` : "";
      const bullets = (n.bullets || []).length
        ? `<ul>${n.bullets.map((b) => {
            const cls = [b.detail == 3 ? "ado-d3" : "", b.source === "shiur" ? "ado-shiur" : ""].join(" ").trim();
            return `<li${cls ? ` class="${cls}"` : ""}>${m(b.text, b.detail == 3 || b.source === "shiur")}</li>`;
          }).join("")}</ul>` : "";
      return `<section class="ado-node ado-l${Math.min(depth, 5)}" data-id="${esc(n.id)}">
        <div class="ado-head"><h${Math.min(depth + 1, 6)} class="ado-t">${md(n.title)}</h${Math.min(depth + 1, 6)}>
          <span class="ado-amud" title="${esc(rangeLabel(n.text))}">${esc(n.amud)}</span>
          ${n.flag ? `<span class="ado-flag">${esc(n.flag)}</span>` : ""}</div>
        ${ret}
        ${gist}
        ${bullets}
        ${n.chart ? chartHTML(n.chart) : ""}
        ${n.illustration ? illHTML(n.illustration) : ""}
        ${n.continues ? `<p class="ado-cont">${md(n.continues)}</p>` : ""}
        ${(n.children || []).map((k) => nodeHTML(k, depth + 1)).join("")}
      </section>`;
    }

    container.classList.add("ado");
    container.dataset.level = container.dataset.level || "2";
    container.innerHTML = (glance ? `<div class="ado-glwrap"></div>` : "") + (outline.sections || []).map((n) => nodeHTML(n, 1)).join("");

    const sections = flat(outline.sections).map(({ n, depth }) => {
      const el = container.querySelector(`.ado-node[data-id="${CSS.escape(n.id)}"]`);
      return { id: n.id, title: n.title, amud: n.amud, from: n.text?.from, to: n.text?.to || n.text?.from,
               depth, el, head: el.querySelector(":scope > .ado-head") };
    });
    const byId = Object.fromEntries(sections.map((s) => [s.id, s]));
    const inline = glance ? mountGlance(container.querySelector(".ado-glwrap"), outline, {
      foldable: true, depth: glanceDepth, onDepth: onGlanceDepth, open: glanceOpen, onOpen: onGlanceOpen,
      onSection: (id) => { scrollToSection(id); onSection && onSection(id); } }) : null;

    function scrollToSection(id, behavior = "smooth") {
      const s = byId[id];
      if (s) s.el.scrollIntoView({ behavior, block: "start" });
    }

    // One listener per container, replaced on re-render (the page swaps dafim in place).
    if (container._adoClick) container.removeEventListener("click", container._adoClick);
    container._adoClick = (e) => {
      const t = e.target.closest(".ado-term");
      if (t) { onTerm && onTerm(+t.dataset.term, t); return; }
      const sg = e.target.closest(".ado-sage");
      if (sg) { onSage && onSage(+sg.dataset.sage, sg); return; }
      if (e.target.closest(".ado-glwrap")) return;   // the glance handles its own clicks
      const g = e.target.closest(".ado-ret");
      if (g) { scrollToSection(g.dataset.goto); onSection && onSection(g.dataset.goto); return; }
      const h = e.target.closest(".ado-head");
      if (h && onSection) onSection(h.parentElement.dataset.id);
    };
    container.addEventListener("click", container._adoClick);

    return {
      sections,
      scrollToSection,
      setLevel(lv) { container.dataset.level = String(lv); },
      setGlanceDepth(d) { inline && inline.setDepth(d); },
      setOption(name, on) { container.toggleAttribute(`data-no-${name}`, !on); },
      markCurrent(id) {
        container.querySelectorAll(".ado-current").forEach((x) => x.classList.remove("ado-current"));
        if (byId[id]) byId[id].el.classList.add("ado-current");
        inline && inline.mark(id);
      },
    };
  }

  /* The glossary list: used in a pop-out panel on the web and a bottom sheet in the apps. */
  function glossary(container, keyTerms, { titles = {}, onSection, order = "daf" } = {}) {
    container.classList.add("ado", "ado-gloss");
    // "daf": in the order the terms first come up in the outline; "alpha": A–Z by transliteration.
    const secOrder = Object.keys(titles);
    const firstAt = (t) => Math.min(...(t.sections || []).map((id) => { const k = secOrder.indexOf(id); return k < 0 ? 1e9 : k; }), 1e9);
    const alphaKey = (t) => String(t.term || "").normalize("NFKD").replace(/[^A-Za-z ]/g, "").toLowerCase();
    const items = (keyTerms || []).map((t, i) => `
      <article class="ado-gterm" data-i="${i}" tabindex="-1">
        <h3><span class="ado-gname">${esc(t.term)}</span><span class="ado-heb" lang="he" dir="rtl">${esc(t.hebrew)}</span></h3>
        <p class="ado-gsense">${esc(t.sense)}</p>
        <p>${md(t.definition)}</p>
        <p class="ado-gdaf"><span>On this daf</span>${md(t.on_this_daf)}</p>
        <p class="ado-gsecs">${(t.sections || []).map((id) =>
          `<button type="button" data-goto="${esc(id)}">${md(titles[id] || id)}</button>`).join("")}</p>
      </article>`).join("");
    container.innerHTML = items || `<p class="ado-none">No key terms for this daf.</p>`;
    function sortBy(o) {
      const els = [...container.querySelectorAll(".ado-gterm")];
      const key = (el) => { const t = keyTerms[+el.dataset.i]; return o === "alpha" ? alphaKey(t) : [firstAt(t), +el.dataset.i]; };
      els.sort((a, b) => { const x = key(a), y = key(b);
        return o === "alpha" ? x.localeCompare(y) : (x[0] - y[0]) || (x[1] - y[1]); });
      els.forEach((el) => container.appendChild(el));
    }
    sortBy(order);
    if (container._adoClick) container.removeEventListener("click", container._adoClick);
    container._adoClick = (e) => {
      const b = e.target.closest("[data-goto]");
      if (b && onSection) onSection(b.dataset.goto);
    };
    container.addEventListener("click", container._adoClick);
    return {
      focus(i) {
        container.querySelectorAll(".ado-gterm.ado-hit").forEach((x) => x.classList.remove("ado-hit"));
        const el = container.querySelector(`.ado-gterm[data-i="${i}"]`);
        if (!el) return;
        el.classList.add("ado-hit");
        el.scrollIntoView({ block: "nearest", behavior: "smooth" });
        el.focus({ preventScroll: true });
      },
      setOrder(o) { sortBy(o); },
      filter(q) {
        const s = q.trim().toLowerCase();
        container.querySelectorAll(".ado-gterm").forEach((el) => {
          el.hidden = !!s && !el.textContent.toLowerCase().includes(s);
        });
      },
    };
  }

  global.AnyDafOutline = { render, glance, glossary, md, esc };
})(typeof window !== "undefined" ? window : globalThis);
