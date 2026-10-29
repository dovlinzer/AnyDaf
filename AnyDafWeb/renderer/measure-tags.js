/* Measure markers for the Gemara's English (the William Davidson translation).
   tag(html, hebrew) wraps a unit of measure in <span class="mu" data-m="key">, which the
   Reference popup (measures.js) opens. Keys are the unit ids in measures.json.

   A unit is marked only when
   - a number comes right before it ("four cubits", "a quarter-log", "two hundred dinars"),
     since that is where the size matters; "a"/"an" counts only for units that are
     unambiguous in English (not "a finger", "a bath", "a span");
   - the Hebrew of the same line has the unit's own word (so "the sea", "a log of wood",
     "a finger" are left alone); and
   - it is the unit's first occurrence in the passage: one line of Gemara, or, given a `seen` set,
     one outline section.
   The input is the renderer's md() output, so the only tags in it are <b> and <i>. */
(function (root) {
  const NUM = "\\d[\\d,]*(?:\\.\\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|half|halves|third|thirds|quarter|quarters|fifth|fifths|sixth|sixths|seventh|eighth|tenth|several|many|few";
  const AP = "[’']";
  // key, English (longest forms first), Hebrew root, whether "a"/"an" counts as a number.
  // The Hebrew check applies only to the English words in AMBIGUOUS (the sea, a log of wood, a
  // bath, a finger); Davidson often restates a unit the Hebrew line abbreviates ("ten
  // handbreadths" for כו׳), so an unambiguous unit with a number before it is marked as is.
  const UNITS = [
    ["maneh", "hundred dinars", "מנה|מנים|מנין|מנא", false],
    ["beitseah", `beit se${AP}a`, "בית\\s+(?:סאה|סאתים|סאתיים|סאה)", true],
    ["beitkor", "beit kor", "בית\\s+(?:כור|כורים)", true],
    ["beitkav", "beit kav", "בית\\s+(?:קב|קבים)", true],
    ["dinarzahav", "gold(?:en)? dinars?", "(?:דינר|דינרי|דינרין)\\s+זה(?:ב|וב)|זהובים?", true],
    ["revit", "quarter-logs?|quarter of a log", "רביעית|רביעיות|רביעתא", true],
    ["amah", "cubits?", "אמה|אמות|אמתא|אמין|אמתים|אמתיים|אמתו", true],
    // the outlines' transliteration; "an amah" is usually an amah ivriyah (a maidservant), so only
    // a real number counts
    ["amah", "amot|ammot|amah(?!(?:\\s|</?[bi]>)+ivri)", "אמה|אמות|אמתא|אמין|אמתים|אמתיים|אמתו", false],
    ["tefach", "handbreadths?|tefachim|tefach", "טפח|טפחים|טפחיים|טפחי|טפחא", true],
    ["etzba", "fingerbreadths?|fingers?|etzba(?:ot)?", "אצבע|אצבעות|אצבעו|אצבעא|אצבעתא", false],
    ["zeret", "spans?", "זרת|זרתות|זרתא", false],
    ["seah", `se${AP}ahs?|se${AP}in|se${AP}as?|seahs?|seas?`, "סאה|סאין|סאתים|סאתיים|סאתא|סאוין", true],
    ["kav", "kav(?:in|s)?|kabin", "קב|קבין|קבים|קבא", true],
    ["log", "logs?", "לוג|לוגין|לוגים|לוגא|לגין", true],
    ["hin", "hins?", "הין", true],
    ["bath", "baths?", "בת|בתים", false],
    ["ephah", "ephahs?|eiphas?", "איפה|איפות|אפה", true],
    ["kor", "kors?", "כור|כורין|כורים|כורא", true],
    ["perutah", "perutot|perutas?|perutah", "פרוטה|פרוטות|פרוטא|פרוטי", true],
    ["issar", "issars?|issarim", "איסר|איסרין|איסרא|איסרות", true],
    ["pundion", "pundeyons?|pundeyonin|pondions?", "פונדיון|פונדיונין|פונדיונא|פנדיון", true],
    ["maah", `ma${AP}as?|ma${AP}ahs?`, "מעה|מעין|מעות|מעי|מעתא", true],
    ["dinar", "dinars?|dinarim|zuz(?:im)?", "דינר|דינרין|דינרים|דינרא|דינרי|זוז|זוזי|זוזים|זוזא", true],
    ["shekel", "shekels?", "שקל|שקלים|שקלין|שקלא", true],
    ["sela", "sela(?:im|s)?", "סלע|סלעים|סלעין|סלעא|סלעי", true],
    ["maneh", "maneh|manim|minas?", "מנה|מנים|מנין|מנא|מאני", true],
    ["ris", "ris", "ריס|ריסין|ריסים", true],
    ["mil", "mils?", "מיל|מילין|מילים|מילא", true],
    ["parsah", "parasangs?", "פרסה|פרסאות|פרסי|פרסא|פרסה", true],
    ["ezayit", "olive-bulks?|ke(?:[’']|-)?zayit|kezeitim", "זית|כזית|זיתים", true],
    ["ebeitzah", "egg-bulks?|ke(?:[’']|-)?beitzah", "ביצה|כביצה|ביצים|כביצים", true],
    ["egrogeret", "dried fig-bulks?|fig-bulks?|dried fig(?!s)|ki(?:[’']|-)?grogeret", "גרוגרת|גרוגרות|כגרוגרת", true],
    ["elugmav", "cheekfuls?", "לוגמ", true],
    ["eperas", "half-loaf|half-loaves", "פרס", true],
  ];
  const AMBIGUOUS = /^(?:seas?|seahs?|logs?|baths?|fingers?|spans?|hins?|dried fig|shekels?|ris|mils?)$/i;
  const SEP = "((?:\\s|</?[bi]>)+|-)";
  const TG = "(?:</?[bi]>)*";
  // Davidson italicizes and bolds inside a unit ("a **quarter**-*log*"), so tags may sit at its joints
  const joints = (en) => en.replace(/-/g, `${TG}-${TG}`).replace(/ /g, "(?:\\s|</?[bi]>)+");
  const RULES = UNITS.map(([key, en, he, a]) => ({
    key,
    re: new RegExp(`\\b(${NUM}${a ? "|a|an|A|An" : ""})${SEP}(${joints(en)})\\b`, "gi"),
    he: new RegExp(`(?:^|[^א-ת])[והבלמשכד]{0,3}(?:${he})(?![א-ת])`),
  }));
  const plain = (he) => String(he || "").replace(/[֑-ׇ]|<[^>]+>/g, "");
  // the longest end of s whose <b>/<i> tags open and close inside it, so the marker nests
  const tail = (s) => {
    for (;;) {
      const st = [];
      let cut = -1;
      for (const m of s.matchAll(/<(\/?)([bi])>/g)) {
        if (!m[1]) st.push(m.index);
        else if (st.length) st.pop();
        else { cut = m.index + m[0].length; break; }
      }
      if (cut < 0 && !st.length) return s.replace(/^[\s-]+/, "");
      s = cut >= 0 ? s.slice(cut) : s.slice(st[st.length - 1] + 3);   // after an unclosed <b>/<i>
    }
  };
  const span = (key, s) => `<span class="mu" data-m="${key}" tabindex="0" role="button" title="Tap for sizes">${s}</span>`;

  /* Returns the html with its measures marked, plus the keys marked (for the corpus report). */
  function tagWith(html, hebrew, seen) {
    const he = plain(hebrew), keys = [];
    if (!html) return { html: "", keys };
    let out = html;
    const bible = /\((?:I{1,2} )?[A-Z][a-z]+ \d+:\d+\)|sacred shekel/.test(html);
    for (const r of RULES) {
      const heOk = r.he.test(he);
      r.re.lastIndex = 0;
      let done = !!(seen && seen.has(r.key));
      out = out.replace(r.re, (m, n, sep, unit, off, s) => {
        if (done || r.key === "log" && /^quarter/i.test(n)) return m;   // "quarter-log" is a revi'it
        if (AMBIGUOUS.test(unit) && !heOk) return m;
        // a shekel in a verse is the sacred shekel, a sela; the chart's shekel is half a sela
        if (r.key === "shekel" && bible) return m;
        // "hundred dinars" for מנה is a maneh only when the Hebrew says so
        if (r.key === "maneh" && /dinars/.test(unit) && (!heOk || !/^(?:a|an|one)$/i.test(n))) return m;
        // inside a marker already placed (a unit name within another's span)
        const before = s.slice(0, off);
        if (before.lastIndexOf('<span class="mu"') > before.lastIndexOf("</span>")) return m;
        done = true; keys.push(r.key); if (seen) seen.add(r.key);
        const w = tail(m);
        return m.slice(0, m.length - w.length) + span(r.key, w);
      });
    }
    return { html: out, keys };
  }
  const api = { tag: (html, hebrew, seen) => tagWith(html, hebrew, seen).html, tagWith, UNITS };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.AnyDafMeasures = api;
})(typeof window !== "undefined" ? window : this);
