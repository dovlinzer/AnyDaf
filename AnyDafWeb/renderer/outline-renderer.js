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
  // שוטה is "a person with psychosis", never Davidson's "imbecile"; "fool" where the Gemara uses it
  // as an insult. Same rules as daf-processor/term_fixes.py (keep the two in step).
  const art = (a) => ({ an: "a", An: "A" })[a] || a;
  const S = String.raw`(\s+\**|\**\s+|\s+)`, NOUNS = "(man|woman|partner|priest|wife|husband|person|son|daughter|girl|boy|slave)";
  const STARS = (sep) => (sep.includes("*") ? "**" : "");
  const DEVELOP = { became: "developed", become: "develop", becomes: "develops" };
  const ANIMAL = "a *shoteh* (disoriented)";   // an animal that is a shoteh (Bava Kamma 52-54)
  const TERM_RULES = [
    [/\b(ox|animal)([\s*]+that[\s*]+(?:is|was)(?:[\s*]+impaired by being)?[\s*]+(?:deaf,[\s*]+)?)an imbecile\b/g, `$1$2${ANIMAL}`],
    [/\b([Aa])n imbecile among animals\b/g, "$1 *shoteh* (a disoriented one) among animals"],
    [/\(imbecile\)(?=,? or \*katan\* \(minor\) ox)/g, "(disoriented)"],
    [/(:\s*\**)Imbeciles\b/g, "$1Fools"],
    [/(:\s*\**)Imbecile\b(?=\**\s*[,!])/g, "$1Fool"],
    [/\b([Gg])reatest imbecile\b/g, "$1reatest fool"],
    [/\bcertain imbecile named\b/g, "certain fool named"],
    [/\b(merely|essentially) an imbecile\b/g, "$1 a fool"],
    [/\b(became|become)( \**| )imbecilic\b/g, (m, v, s) => DEVELOP[v] + s + "psychosis"],
    [/\b(became|become|becomes)( \**| )an( \**| )imbecile\b/g, (m, v, s) => DEVELOP[v] + s + "psychosis"],
    [/\btimes imbecilic\b/g, "times in a state of psychosis"],
    [new RegExp(String.raw`\b(an|An|the|The|this|This|that|That|a|A)${S}imbecil(?:ic|e)${S}${NOUNS}\b`, "g"),
      (m, a, s1, s2, n) => art(a) + s1 + n + " with psychosis" + STARS(s2)],
    [new RegExp(String.raw`\bimbecilic${S}${NOUNS}\b`, "g"), (m, s1, n) => n + " with psychosis" + STARS(s1)],
    [/\(imbecile\)/g, "(a person with psychosis)"],
    [/\bImbeciles\b/g, "People with psychosis"],
    [/\bimbeciles\b/g, "people with psychosis"],
    [/\b(an|An)(\s+\**|\**\s+|\s+)imbecile\b/g, (m, a, s) => art(a) + s + "person with psychosis"],
    [/\bImbecile\b/g, "Person with psychosis"],
    [/\bimbecile\b/g, "person with psychosis"],
    [/\b(is|was|are|were|be|being)( \**| )imbecilic\b/g, "$1$2in a state of psychosis"],
    [/\bimbecility\b/g, "psychosis"],
  ];
  const fixTerms = (s) => {
    s = String(s ?? "");
    if (!s.includes("mbecil")) return s;
    for (const [re, to] of TERM_RULES) s = s.replace(re, to);
    return s;
  };
  // **bold** may hold *italics* ("**not a *bekhor***")
  const md = (s) => esc(fixTerms(s)).replace(/\*\*((?:[^*]|\*[^*]+\*)+)\*\*/g, "<b>$1</b>").replace(/\*([^*]+)\*/g, "<i>$1</i>");

  // Interface words, by the outline's language (outline.lang: "he" lays the outline out right to left).
  const WORDS = {
    en: { chart: "Chart", picture: "Illustration", key: "Key", openAll: "Open all", closeAll: "Collapse all", fold: "Show or hide this section", glance: "At a glance", depth: "Depth", depthLabel: "Contents depth", returns: "Returns to", onDaf: "On this daf", onOther: "On", noTerms: "No key terms for this daf.", summary: "Daf summary", takeaways: "Key takeaways", debates: "Key debates", sumTerms: "Key terms", see: "See", outcome: "Outcome", daf: "Daf" },
    he: { chart: "טבלה", picture: "איור", key: "מקרא", openAll: "פתיחת הכול", closeAll: "קיפול הכול", fold: "הצגה או הסתרה של הקטע", glance: "במבט על", depth: "עומק", depthLabel: "עומק התוכן", returns: "חוזר אל", onDaf: "בדף זה", onOther: "ב", noTerms: "אין מושגי מפתח לדף זה.", summary: "סיכום הדף", takeaways: "עיקרי הדברים", debates: "מחלוקות מרכזיות", sumTerms: "מושגי מפתח", see: "ראו", outcome: "הכרעה", daf: "דף" },
  };
  const words = (lang) => WORDS[lang] || WORDS.en;
  const isHe = (o) => (o && o.lang) === "he";
  function setDir(container, lang) {
    if (lang === "he") { container.setAttribute("dir", "rtl"); container.setAttribute("lang", "he"); }
    // stated, not left unset, so an English outline stays left to right on a right-to-left page
    else { container.setAttribute("dir", "ltr"); container.setAttribute("lang", "en"); }
  }
  const HEB = /[\u05D0-\u05EA]/;

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
    const q = (a) => a.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const lat = pairs.filter(([a]) => !HEB.test(a)), heb = pairs.filter(([a]) => HEB.test(a));
    const parts = [];
    if (lat.length) parts.push(`(?<![\\w'’])(?:${lat.map(([a]) => q(a)).join("|")})(?![\\w'’])`);
    if (heb.length) parts.push(`(?<![\\u05D0-\\u05EA])(?:[ובלמשכה]{0,2})(?:${heb.map(([a]) => q(a)).join("|")})(?![\\u05D0-\\u05EA])`);
    const re = new RegExp(`(${parts.join("|")})`, "gi");
    const HE_NEG = /(?:^|[\s(])(?:שלא|לא|אין|שאין|אינו|אינה|שאינו|שאינה)\s+[ובלמשכה]{0,2}$/;
    const strip = (m) => (HEB.test(m) && !byAlias.has(m) ? m.replace(/^[ובלמשכה]{1,2}/, (pre) => {
      for (let k = pre.length; k >= 1; k--) if (byAlias.has(m.slice(k))) return pre.slice(0, k); return ""; }) : "");
    return function mark(html, seen) {
      return html.split(/(<[^>]+>)/).map((part) => part.startsWith("<") ? part : part.replace(re, (m, _g, off, whole) => {
        const pre = strip(m), core = m.slice(pre.length);
        const i = byAlias.get(core.toLowerCase());
        if (i === undefined || seen.has(i)) return m;
        if (HEB.test(core) && HE_NEG.test(whole.slice(Math.max(0, off - 12), off) + pre)) return m;
        // a term right after a negation is its opposite (shelo lishmah, she'ein mesurin): not this entry
        if (/(?:^|[\s(*])(?:shelo|she['’]lo|she['’]ein|she['’]eino|she['’]einah|lo|ein|eino|einah)\s+$/i.test(whole.slice(Math.max(0, off - 12), off))) return m;
        seen.add(i);
        return `${pre}<button type="button" class="ado-term" data-term="${i}">${core}</button>`;
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
  function hebSageMatcher(sages) {
    const byName = new Map();
    (sages || []).forEach((sg, i) => [sg.he, ...(sg.aliases || [])].forEach((a) => {
      if (!a || !HEB.test(a)) return;
      [a, a.replace(/^רבי /, "ר' "), a.replace(/^ר' /, "רבי ")].forEach((v) => byName.has(v) || byName.set(v, i));
    }));
    if (!byName.size) return null;
    const names = [...byName.keys()].sort((x, y) => y.length - x.length).map((a) => a.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    const re = new RegExp(`(?<![\\u05D0-\\u05EA'])([ובלמשכה]?)(${names.join("|")})(?![\\u05D0-\\u05EA])`, "g");
    return function markSages(html, seen) {
      let inButton = 0;
      return html.split(/(<[^>]+>)/).map((part) => {
        if (part.startsWith("<")) { if (/^<button/.test(part)) inButton++; else if (/^<\/button/.test(part)) inButton--; return part; }
        if (inButton) return part;
        return part.replace(re, (m, pre, name) => {
          const i = byName.get(name);
          if (i === undefined || seen.has("s" + i)) return m;
          seen.add("s" + i);
          return `${pre}<button type="button" class="ado-sage" data-sage="${i}">${name}</button>`;
        });
      }).join("");
    };
  }

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
        return part.replace(NAME_RE, (m, ...args) => {
          // A book of the Bible, not a sage: "(I Shmuel 1:22)", "Daniel 6:11". A numbered book
          // before the name, or chapter:verse after it, marks a verse citation.
          const at = args[args.length - 2], str = args[args.length - 1];
          if (/(?:^|[\s(])(?:I{1,2}|[12])\s+$/.test(str.slice(Math.max(0, at - 6), at)) ||
              /^\s+\d+:\d+/.test(str.slice(at + m.length))) return m;
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
  // Outcome tags (chart.tags): a closed list the outline pass picks from. Each has its word, the colour of
  // the cell (null = neutral: whether paying or swearing is the good outcome depends on the case) and the
  // badge drawn for it in the figure library (null = no artwork yet: the word alone). Shares follow a
  // colon, one per party ("divides:1/2,1/2", "divides:3/4,1/4"). In a cell the badge is the icon alone (plus
  // any shares), the word only as a tooltip; the key under the chart pairs each icon with its word. The
  // cell's text always shows; the badges can be turned off (setOption("badges", false)).
  const TAGS = {
    pays: ["Pays", "משלם", null, "pays"], exempt: ["Exempt", "פטור", null, "exempt"],
    oath: ["Swears", "נשבע", null, "oath"], "no-oath": ["No oath", "אינו נשבע", null, "no-oath"],
    divides: ["Divides", "חולקים", null, "divides"], takes: ["Takes", "נוטל", null, "acquires"],
    "no-claim": ["Has no claim", "אין לו טענה", "no", "no-claim"], keeps: ["Keeps it", "מחזיק בו", null, "acquires"],
    returns: ["Returns it", "מחזיר", "ok", "returns"], "not-returned": ["Does not return it", "אינו מחזיר", "no", "not-returned"], holds: ["Holds it", "יהא מונח", "hold", "holds"],
    acquires: ["Acquires", "קנה", "ok", "acquires"], "not-acquired": ["Not acquired", "לא קנה", "no", "not-acquired"],
    permitted: ["Permitted", "מותר", "ok", "permitted"], forbidden: ["Forbidden", "אסור", "no", "forbidden"],
    valid: ["Valid", "כשר", "ok", "permitted"], invalid: ["Invalid", "פסול", "no", "forbidden"],
    effective: ["Takes effect", "חל", "ok", "permitted"], "not-effective": ["No effect", "לא חל", "no", "forbidden"],
  };
  // outcomes that are neither good nor bad take a contrasting pair with no verdict, as in the pictures:
  // blue for one side, amber for its opposite (the ruling words in a cell; see cellHTML)
  const PAIR = { pays: "a", exempt: "b", oath: "a", "no-oath": "b", divides: "a", keeps: "b", takes: "a", holds: "b" };
  // shares show full size ("3/4"): the single fraction characters read too small (author, 2026-10-18)
  const FRAC = {};
  function tagInfo(tag, he) {
    if (!tag) return null;
    const [name, share] = String(tag).split(":"), t = TAGS[name];
    if (!t) return null;
    const shares = share ? share.split(/[,|]/).map((x) => FRAC[x.trim()] || x.trim()).join(", ") : "";
    return { name, word: he ? t[1] : t[0], shares, tone: t[2], art: t[3], pair: PAIR[name] || null };
  }
  // a cell may carry two outcomes that go together: "oath+takes", "no-oath+divides:1/2,1/2"
  const tagsOf = (tag, he) => tag ? String(tag).split("+").map((x) => tagInfo(x.trim(), he)).filter(Boolean) : [];
  const svgOf = (t) => `<svg viewBox="0 0 40 40" aria-hidden="true"><use href="#badge-${t.art}"/></svg>`;
  // in a cell: the icon and any shares, nothing else (a tag with no artwork yet falls back to its word)
  const badgeHTML = (t) => t.art
    ? `<span class="ado-badge ado-b-${esc(t.name)}" title="${esc(t.word)}" role="img" aria-label="${esc(t.word + (t.shares ? " " + t.shares : ""))}">${svgOf(t)}${t.shares ? `<span class="ado-share">${esc(t.shares)}</span>` : ""}</span>`
    : `<span class="ado-badge ado-badge-w ado-b-${esc(t.name)}"><span>${esc(t.word)}</span></span>`;
  // in the key: icon and word
  const keyHTML = (t) => `<span class="ado-kitem">${t.art ? svgOf(t) : ""}<span>${esc(t.word)}</span></span>`;
  function cellHTML(x, given, tag) {
    // the outline's own marking (chart.tags, or the older chart.tones) when it has one; reading the
    // words only for outlines made before either. A cell may list several items, one per line.
    const h = md(x).replace(/\n/g, "<br>");
    if (tag && tag.length) {
      // the ruling's own words (**…** in the cell) a little larger, in the outcome's colour
      const lead = tag.find((x) => x.tone === "ok" || x.tone === "no") || tag.find((x) => x.pair) || tag[0];
      const rc = lead.tone === "ok" || lead.tone === "no" ? lead.tone : lead.pair ? `p${lead.pair}` : "";
      const marked = /<b>/.test(h);
      const body = marked ? h.replace(/<b>/g, `<b class="ado-rul${rc ? " ado-rul-" + rc : ""}">`) : h;
      // a cell with marked ruling words keeps its text plain; otherwise its outcome colours it whole
      // (green/red for a good/bad outcome, blue/amber for a pair such as swears / no oath)
      const tc = !marked && rc ? ` class="ado-cell-${rc}"` : "";
      return `<td${tc}><span class="ado-badges">${tag.map(badgeHTML).join("")}</span>${body}</td>`;
    }
    const tone = given !== undefined ? given : cellTone(h);
    return tone ? `<td class="ado-cell-${tone}">${h}</td>` : `<td>${rulings(h)}</td>`;
  }

  // Charts and pictures carry a title and a number the page assigns in order ("Chart 2", "Illustration 3").
  function chartHTML(c, num, W, he) {
    const cols = (c.columns || []).map((h) => `<th scope="col">${md(h)}</th>`).join("");
    const tags = Array.isArray(c.tags) ? c.tags : null, tones = !tags && Array.isArray(c.tones) ? c.tones : null;
    const used = new Map();
    const rows = (c.rows || []).map((r, ri) =>
      `<tr>${r.map((x, i) => {
        if (!i) return `<th scope="row">${md(x)}</th>`;
        const t = tags ? tagsOf((tags[ri] || [])[i], he) : null;
        if (t) t.forEach((x) => used.set(x.name, x));
        return cellHTML(x, tones ? ((tones[ri] || [])[i] ?? null) : (tags ? null : undefined), t);
      }).join("")}</tr>`).join("");
    const title = c.title || c.caption || "";
    const note = c.title && c.caption ? `<p class="ado-cnote">${md(c.caption)}</p>` : "";
    // tags sharing one icon (keeps it / permitted) share one key entry: "✓ Permitted / Keeps it"
    const byArt = new Map();
    for (const t of used.values()) { const k = t.art || t.name, e = byArt.get(k); if (e) e.word += " / " + t.word; else byArt.set(k, { ...t }); }
    // in the list's order, so opposites sit side by side (Swears, No oath; Acquires, Not acquired)
    const ORDER = Object.keys(TAGS), entries = [...byArt.values()].sort((x, y) => ORDER.indexOf(x.name) - ORDER.indexOf(y.name));
    const key = entries.length ? `<div class="ado-key"><span class="ado-keyl">${W.key}:</span>${entries.map(keyHTML).join("")}</div>` : "";
    // the key sits in a box of its own just below the chart
    return `<div class="ado-chartw"><div class="ado-chart"><table><caption><span class="ado-num">${W.chart} ${num}</span>${md(title)}</caption><thead><tr>${cols}</tr></thead><tbody>${rows}</tbody></table>${note}</div>${key}</div>`;
  }

  function illHTML(il, num, W) {
    return `<figure class="ado-ill"><div class="ado-ibox"><div class="ado-ihead"><span class="ado-num">${W.picture} ${num}</span>${il.title ? md(il.title) : ""}</div><div class="ado-art">${il.svg}</div></div><figcaption>${md(il.caption)}</figcaption></figure>`;
  }

  // The amud a section starts on ("6b" from "6b.3"), and how a divider names it: "Daf 6b",
  // or in Hebrew "דף ו:" (a dot for amud a, a colon for amud b).
  function startAmud(n) {
    const m = /^(\d+)([ab])\./.exec((n.text && n.text.from) || "");
    return m ? { daf: +m[1], side: m[2], key: m[1] + m[2] } : null;
  }
  function hebNum(x) {
    const ones = "אבגדהוזחט", tens = "יכלמנסעפצ", hund = "קרשת";
    let s = "";
    for (; x >= 400; x -= 400) s += "ת";
    if (x >= 100) { s += hund[Math.floor(x / 100) - 1]; x %= 100; }
    if (x === 15) return s + "טו";
    if (x === 16) return s + "טז";
    if (x >= 10) { s += tens[Math.floor(x / 10) - 1]; x %= 10; }
    return x ? s + ones[x - 1] : s;
  }
  function amudDivider(a, W, he) {
    const name = he ? `${hebNum(a.daf)}${a.side === "a" ? "." : ":"}` : a.key;
    return `<div class="ado-amudline" role="separator" aria-label="${esc(W.daf + " " + name)}"><span>${esc(W.daf)} ${esc(name)}</span></div>`;
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
    const W = words(outline.lang);
    const tops = outline.sections || [];
    if (tops.length < 2 && !(tops[0]?.children || []).length) return "";
    const max = outlineDepth(outline);
    const d = Math.min(depth, max);
    const cls = (lv) => "ado-gl" + (lv >= 2 ? " ado-gl2" : "") + (lv >= 3 ? " ado-gl3" : "");
    const item = (n, lv) => `<li><button type="button" class="${cls(lv)}" data-goto="${esc(n.id)}">${md(n.title)}</button>` +
      `${lv === 1 ? `<span class="ado-glam">${esc(n.amud)}</span>` : ""}` +
      `${lv < d && (n.children || []).length ? `<ol>${n.children.map((c) => item(c, lv + 1)).join("")}</ol>` : ""}</li>`;
    const ctl = `<div class="ado-gldepth" role="group" aria-label="${W.depthLabel}"><span>${W.depth}</span>${[1, 2, 3, 4, 5].map((k) =>
      `<button type="button" data-gd="${k}" aria-pressed="${k === d}"${k > max ? " disabled" : ""}>${k}</button>`).join("")}</div>`;
    const list = `<ol>${tops.map((n) => item(n, 1)).join("")}</ol>`;
    return foldable
      ? `<nav class="ado-glance" aria-label="${W.glance}"><details${open ? " open" : ""}><summary>${W.glance}</summary>${ctl}${list}</details></nav>`
      : `<nav class="ado-glance" aria-label="${W.glance}"><div class="ado-glhead"><h2 class="ado-glh">${W.glance}</h2>${ctl}</div>${list}</nav>`;
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
    setDir(container, outline.lang);
    return mountGlance(container, outline, { foldable: false, depth, onSection, onDepth, scroll: true });
  }

  function render(container, opts) {
    const { outline, keyTerms = [], onTerm, onSection, glance = true, glanceDepth = 2, onGlanceDepth,
            glanceOpen = false, onGlanceOpen, sages = [], onSage, collapsible = false, measures = null } = opts;
    const W = words(outline.lang);
    const markTerms = termMatcher(keyTerms), markSages = isHe(outline) ? hebSageMatcher(sages) : sageMatcher(sages);
    const mark = markTerms || markSages
      ? (html, seen, sageSeen) => { if (markTerms) html = markTerms(html, seen); return markSages ? markSages(html, sageSeen) : html; }
      : null;
    const titles = {};
    flat(outline.sections).forEach(({ n }) => (titles[n.id] = n.title));

    // Key terms and sages link once per daf, at the first mention. Text the reader can hide
    // (Detailed bullets, shiur insights) gets a link without using up that first mention, so the
    // first one always stays visible.
    const termsSeen = new Set(), sagesSeen = new Set();
    let chartN = 0, picN = 0, lastAmud = null;
    function nodeHTML(n, depth) {
      // A dotted line where the outline moves to a new amud, before the first section that starts
      // on it, mirroring the page. Sections are visited in reading order, parents before children.
      const a = startAmud(n);
      let divider = "";
      if (a) {
        if (lastAmud && a.key !== lastAmud) divider = amudDivider(a, W, isHe(outline));
        lastAmud = a.key;
      }
      // measures(html, seen): marks units of measure for the Reference popup (the page's
      // measure-tags.js), each at its first mention in this section; text the reader can hide
      // marks without using that mention up, as with key terms
      const measSeen = new Set();
      const mm = (h, hideable) => (measures ? measures(h, hideable ? new Set(measSeen) : measSeen) : h);
      const m = (s, hideable) => mm(mark ? mark(md(s), hideable ? new Set(termsSeen) : termsSeen,
                                               hideable ? new Set(sagesSeen) : sagesSeen) : md(s), hideable);
      const ret = (n.returns_to || []).map((x) =>
        `<button type="button" class="ado-ret" data-goto="${esc(x.id)}">↩ ${W.returns} ${md(titles[x.id] || x.id)}${x.note ? ` — ${md(x.note)}` : ""}</button>`).join("");
      // The gist is marked before the bullets: a name or term links where the reader meets it first.
      const gist = n.gist ? `<p class="ado-gist">${m(n.gist)}</p>` : "";
      const bullets = (n.bullets || []).length
        ? `<ul>${n.bullets.map((b) => {
            const cls = [b.detail == 3 ? "ado-d3" : "", b.source === "shiur" ? "ado-shiur" : ""].join(" ").trim();
            return `<li${cls ? ` class="${cls}"` : ""}>${m(b.text, b.detail == 3 || b.source === "shiur")}</li>`;
          }).join("")}</ul>` : "";
      // Collapsible: every heading shows, at every depth; a section's own text, charts and pictures
      // (not its subsections) sit in .ado-body, shown when the section is open.
      const own = !!(ret || gist || bullets || n.chart || n.illustration || n.continues);
      const fold = collapsible && own
        ? `<button type="button" class="ado-fold" aria-expanded="false" aria-label="${W.fold}" title="${W.fold}"></button>` : "";
      return `${divider}<section class="ado-node ado-l${Math.min(depth, 5)}" data-id="${esc(n.id)}">
        <div class="ado-head">${fold}<h${Math.min(depth + 1, 6)} class="ado-t">${md(n.title)}</h${Math.min(depth + 1, 6)}>
          <span class="ado-amud" title="${esc(rangeLabel(n.text))}">${esc(n.amud)}</span>
          ${n.flag ? `<span class="ado-flag">${esc(n.flag)}</span>` : ""}</div>
        ${collapsible ? `<div class="ado-body">` : ""}
        ${ret}
        ${gist}
        ${bullets}
        ${n.chart ? chartHTML(n.chart, ++chartN, W, isHe(outline)) : ""}
        ${n.illustration ? illHTML(n.illustration, ++picN, W) : ""}
        ${n.continues ? `<p class="ado-cont">${md(n.continues)}</p>` : ""}
        ${collapsible ? `</div>` : ""}
        ${(n.children || []).map((k) => nodeHTML(k, depth + 1)).join("")}
      </section>`;
    }

    container.classList.add("ado");
    setDir(container, outline.lang);
    container.dataset.level = container.dataset.level || "2";
    container.classList.toggle("ado-collapsible", !!collapsible);
    const foldbar = collapsible
      ? `<div class="ado-foldbar"><button type="button" data-foldall="1">${W.openAll}</button><button type="button" data-foldall="0">${W.closeAll}</button></div>` : "";
    // The daf summary (outline.daf_summary): a closed panel after the last section. Takeaways and
    // debates link to the sections they come from; its key terms are a few of the daf's own.
    function summaryHTML(ds) {
      if (!ds || !((ds.takeaways || []).length || (ds.debates || []).length)) return "";
      const see = (ids) => (ids || []).filter((id) => titles[id]).length
        ? `<span class="ado-see">${W.see}: ${(ids || []).filter((id) => titles[id]).map((id) =>
            `<button type="button" class="ado-sgo" data-goto="${esc(id)}">${md(titles[id])}</button>`).join(" · ")}</span>` : "";
      const tk = (ds.takeaways || []).length ? `<div class="ado-sumsec"><h3>${W.takeaways}</h3><ul class="ado-tk">${ds.takeaways.map((t) =>
        `<li>${md(t.text)} ${see(t.sections)}</li>`).join("")}</ul></div>` : "";
      const db = (ds.debates || []).length ? `<div class="ado-sumsec"><h3>${W.debates}</h3>${ds.debates.map((d) => `<div class="ado-deb">
          <p class="ado-debq">${md(d.question)}</p>
          <ul class="ado-sides">${(d.sides || []).map((x) => `<li><b>${md(x.who)}:</b> ${md(x.view)}</li>`).join("")}</ul>
          ${d.outcome ? `<p class="ado-debo"><b>${W.outcome}:</b> ${md(d.outcome)}</p>` : ""}${see(d.sections)}</div>`).join("")}</div>` : "";
      const terms = (ds.key_terms || []).map((name) => {
        const i = keyTerms.findIndex((t) => t.term === name);
        const t = keyTerms[i];
        if (!t) return "";
        const short = String(t.definition || "").split(/(?<=[.!?])\s/)[0];
        return `<dt>${t.hebrew ? `<span class="ado-heb" lang="he" dir="rtl">${esc(t.hebrew)}</span>, ` : ""}<button type="button" class="ado-term ado-sumterm" data-term="${i}"><i>${esc(t.term)}</i></button></dt><dd>${md(short)}</dd>`;
      }).join("");
      return `<section class="ado-sum"><button type="button" class="ado-sumtog" aria-expanded="false">${W.summary}</button>
        <div class="ado-sumbody" hidden>${tk}${db}${terms ? `<div class="ado-sumsec"><h3>${W.sumTerms}</h3><dl class="ado-sumterms">${terms}</dl></div>` : ""}</div></section>`;
    }

    container.innerHTML = (glance && !collapsible ? `<div class="ado-glwrap"></div>` : "") + foldbar
      + (outline.sections || []).map((n) => nodeHTML(n, 1)).join("") + summaryHTML(outline.daf_summary);

    const sections = flat(outline.sections).map(({ n, depth }) => {
      const el = container.querySelector(`.ado-node[data-id="${CSS.escape(n.id)}"]`);
      return { id: n.id, title: n.title, amud: n.amud, from: n.text?.from, to: n.text?.to || n.text?.from,
               depth, el, head: el.querySelector(":scope > .ado-head") };
    });
    const byId = Object.fromEntries(sections.map((s) => [s.id, s]));
    const inline = glance && !collapsible ? mountGlance(container.querySelector(".ado-glwrap"), outline, {
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
      const f = e.target.closest(".ado-fold");
      if (f) { toggle(f.closest(".ado-node")); return; }
      const fa = e.target.closest("[data-foldall]");
      if (fa) { setAll(fa.dataset.foldall === "1"); return; }
      const st = e.target.closest(".ado-sumtog");
      if (st) { setSummary(st.getAttribute("aria-expanded") !== "true"); return; }
      const sgo = e.target.closest(".ado-sgo");
      if (sgo) { const id = sgo.dataset.goto; if (collapsible && byId[id]) setOpen(byId[id].el, true);
                 scrollToSection(id); onSection && onSection(id); return; }
      const g = e.target.closest(".ado-ret");
      if (g) { scrollToSection(g.dataset.goto); onSection && onSection(g.dataset.goto); return; }
      const h = e.target.closest(".ado-head");
      if (h && onSection) onSection(h.parentElement.dataset.id);
    };
    container.addEventListener("click", container._adoClick);

    function setOpen(el, on) {
      if (!el) return;
      el.classList.toggle("ado-open", on);
      const b = el.querySelector(":scope > .ado-head > .ado-fold");
      if (b) b.setAttribute("aria-expanded", String(on));
    }
    function toggle(el) { setOpen(el, !el.classList.contains("ado-open")); }
    function setSummary(on) {
      const b = container.querySelector(".ado-sumtog"), body = container.querySelector(".ado-sumbody");
      if (!b) return false;
      b.setAttribute("aria-expanded", String(on));
      body.hidden = !on;
      return true;
    }
    function setAll(on) { sections.forEach((s) => setOpen(s.el, on)); }

    return {
      sections,
      scrollToSection,
      setLevel(lv) { container.dataset.level = String(lv); },
      setGlanceDepth(d) { inline && inline.setDepth(d); },
      hasSummary: !!container.querySelector(".ado-sum"),
      // open the daf summary and bring it into view
      openSummary() { if (setSummary(true)) container.querySelector(".ado-sum").scrollIntoView({ behavior: "smooth", block: "start" }); },
      setOption(name, on) { container.toggleAttribute(`data-no-${name}`, !on); },
      // collapsible outlines: open a section (its own text), or open / fold them all
      open(id) { if (collapsible && byId[id]) setOpen(byId[id].el, true); },
      setAll(on) { if (collapsible) setAll(on); },
      markCurrent(id) {
        container.querySelectorAll(".ado-current").forEach((x) => x.classList.remove("ado-current"));
        if (byId[id]) byId[id].el.classList.add("ado-current");
        inline && inline.mark(id);
      },
    };
  }

  /* The glossary list: used in a pop-out panel on the web and a bottom sheet in the apps. */
  function glossary(container, keyTerms, { titles = {}, onSection, order = "daf", lang } = {}) {
    container.classList.add("ado", "ado-gloss");
    setDir(container, lang);
    const W = words(lang);
    // "daf": in the order the terms first come up in the outline; "alpha": A–Z by transliteration.
    const secOrder = Object.keys(titles);
    const firstAt = (t) => Math.min(...(t.sections || []).map((id) => { const k = secOrder.indexOf(id); return k < 0 ? 1e9 : k; }), 1e9);
    const alphaKey = (t) => String(t.term || "").normalize("NFKD").replace(/[^A-Za-z \u05D0-\u05EA]/g, "").toLowerCase();
    const items = (keyTerms || []).map((t, i) => `
      <article class="ado-gterm" data-i="${i}" tabindex="-1">
        <h3><span class="ado-gname">${esc(t.term)}</span>${t.hebrew && t.hebrew !== t.term ? `<span class="ado-heb" lang="he" dir="rtl">${esc(t.hebrew)}</span>` : ""}</h3>
        <p class="ado-gsense">${esc(t.sense)}</p>
        <p>${md(t.definition)}</p>
        <p class="ado-gdaf"><span>${t.from ? `${W.onOther} ${esc(t.from)}` : W.onDaf}</span>${md(t.on_this_daf)}</p>
        <p class="ado-gsecs">${(t.sections || []).map((id) =>
          `<button type="button" data-goto="${esc(id)}">${md(titles[id] || id)}</button>`).join("")}</p>
      </article>`).join("");
    container.innerHTML = items || `<p class="ado-none">${W.noTerms}</p>`;
    function sortBy(o) {
      const els = [...container.querySelectorAll(".ado-gterm")];
      const key = (el) => { const t = keyTerms[+el.dataset.i]; return o === "alpha" ? alphaKey(t) : [firstAt(t), +el.dataset.i]; };
      els.sort((a, b) => { const x = key(a), y = key(b);
        return o === "alpha" ? x.localeCompare(y, lang === "he" ? "he" : "en") : (x[0] - y[0]) || (x[1] - y[1]); });
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

  global.AnyDafOutline = { render, glance, glossary, md, esc, fixTerms, cellTone, RULING };
})(typeof window !== "undefined" ? window : globalThis);
