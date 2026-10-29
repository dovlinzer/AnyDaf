/* Sages: relationship graph + info box. Shared by iTalmud and Illustrated Mishna (edit only here).
   A plain script, no libraries. The host page calls

     AnySages.init({base:'sages/', corpus:'bavli'|'mishnah', lang:'en'|'he',
                    link:(corpus, tractate, place) => url,      // place: '11a' or '3:4'
                    tractateName:(tractate) => label})          // optional
     AnySages.open(id)                                          // a slug from sages.json

   and the box opens over the page: the sage in the centre, teachers above (arrows down to him),
   students below (arrows down from him), colleagues beside him (dotted, no arrows), family
   under him, and an info box. Clicking another sage makes them the centre; the sages who stay in
   the picture glide to their new places. Data: sages.json (loaded on first open) and quoted.json
   (loaded when a reader opens "where quoted"). */
(function () {
  const S = { o: { base: 'sages/', corpus: 'bavli', lang: 'en' }, data: null, quoted: null, trail: [], cur: null,
              open: {}, nodes: new Map(), box: null, faceOf: new Map(), view: 'ts', famEdges: [] };
  const HE = () => S.o.lang === 'he';
  const W = {
    en: { title: 'Sages', rel: 'Relationships', back: 'Back', close: 'Close', teachers: 'Teachers', students: 'Students',
          colleagues: 'Colleagues', family: 'Family', more: '+{0} more', fewer: 'Fewer', tanna: 'Tanna', amora: 'Amora',
          zug: 'One of the Pairs (Zugot)', gen: '{0} generation', trans: 'transitional generation', ey: 'Eretz Yisrael',
          bavel: 'Bavel', about: 'about {0}', ce: 'CE', bce: 'BCE', born: 'born {0}', died: 'died {0}',
          quotedB: 'Named on {0} lines of the Talmud', quotedM: 'Named in {0} mishnayot', most: 'Most in:',
          all: 'All places', allT: 'All tractates', none: 'No teachers or students are recorded.',
          father: 'Father', mother: 'Mother', parents: 'Parent', children: 'Children', spouse: 'Wife', in_laws: 'Father-in-law',
          sons_in_law: 'Son-in-law', siblings: 'Brother', relatives: 'Relative', stories: 'Stories about him',
          sefaria: 'Sefaria', wiki: 'Wikipedia', approx: 'Dates are approximate, by generation.', loading: 'Loading…',
          keyT: 'teacher → student', keyC: 'colleagues', keyRT: 'teacher', keyRS: 'student', keyRC: 'colleague', keyTa: 'Tanna', keyEY: 'Amora, Eretz Yisrael',
          keyBV: 'Amora, Bavel', keyZ: 'Zugot', keyF: 'family', notes: 'Notes and sources',
          wifeOf: 'wife of', daughterOf: 'daughter of', sonOf: 'son of', moreAbout: 'More about him', vTS: 'Teachers & students', vFam: 'Family',
          alts: 'The sources give more than one name; each is a later identification or tradition.', est: 'a rough count: the name fits more than one sage' },
    he: { title: 'חכמים', rel: 'קשרים', back: 'חזרה', close: 'סגירה', teachers: 'רבותיו', students: 'תלמידיו',
          colleagues: 'בני דורו', family: 'משפחה', more: 'ועוד {0}', fewer: 'פחות', tanna: 'תנא', amora: 'אמורא',
          zug: 'מן הזוגות', gen: 'דור {0}', trans: 'דור המעבר', ey: 'ארץ ישראל', bavel: 'בבל', about: 'בערך {0}',
          ce: 'לספירה', bce: 'לפנה"ס', born: 'נולד {0}', died: 'נפטר {0}', quotedB: 'נזכר ב־{0} שורות בתלמוד',
          quotedM: 'נזכר ב־{0} משניות', most: 'בעיקר ב:', all: 'כל המקומות', allT: 'כל המסכתות',
          none: 'לא ידוע על רבותיו ותלמידיו.', father: 'אביו', mother: 'אמו', parents: 'הורה', children: 'ילדיו',
          spouse: 'אשתו', in_laws: 'חמיו', sons_in_law: 'חתנו', siblings: 'אחיו', relatives: 'קרוב משפחה',
          stories: 'סיפורים עליו', sefaria: 'ספריא', wiki: 'ויקיפדיה', approx: 'התאריכים משוערים, לפי הדור.',
          loading: 'טוען…', keyT: 'רב ← תלמיד', keyC: 'בני דורו', keyRT: 'רב', keyRS: 'תלמיד', keyRC: 'בן דורו', keyTa: 'תנא', keyEY: 'אמורא, ארץ ישראל',
          keyBV: 'אמורא, בבל', keyZ: 'זוגות', keyF: 'משפחה', notes: 'הערות ומקורות',
          wifeOf: 'אשת', daughterOf: 'בתו של', sonOf: 'בנו של', moreAbout: 'עוד עליו', vTS: 'רבותיו ותלמידיו', vFam: 'משפחה',
          alts: 'במקורות יותר משם אחד; כל אחד מהם זיהוי או מסורת מאוחרים.', est: 'מספר משוער: השם מתאים ליותר מחכם אחד' },
  };
  const t = (k, ...a) => (W[S.o.lang] || W.en)[k].replace(/\{(\d)\}/g, (_, i) => a[i]);
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const ORD = n => n + (n % 10 === 1 && n !== 11 ? 'st' : n % 10 === 2 && n !== 12 ? 'nd' : n % 10 === 3 && n !== 13 ? 'rd' : 'th');
  const HE_ORD = ['', 'ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שביעי', 'שמיני'];
  const sage = id => S.data.sages[id];
  // "Rabbi Yehudah [b. Il'ai]" -> "Rabbi Yehudah"; on a narrow screen "Rabbi" -> "R."
  let narrow = false;
  // "[Shimon] b. Azzai", known by his father's name alone: "Ben Azzai" (and "Shimon ben Azzai" in full)
  const benName = en => en.replace(/^\[[^\]]*\]\s*b\. /, 'Ben ');
  const shortName = x => HE() ? x.he || x.en
    : benName(x.en).replace(/\s*\[.*?\]|\s*\((?!Rebbe\)).*?\)/g, '').replace(narrow ? /^Rabbi /u : /^$/, 'R. ').trim();
  const fullName = x => HE() ? x.he || x.en : x.en.replace(/^\[([^\]]*)\]\s*b\. /, '$1 ben ').replace(/[\[\]]/g, '');
  // Colour: Zugot, tanna'im, amora'im of Eretz Yisrael, of Bavel (both: by the first listed).
  function group(x) {
    if (!x) return 'na';
    if (x.kind === 'zug') return 'zug';
    if (x.kind === 'tanna') return 'tanna';
    if (x.kind === 'amora') return (x.region || '').startsWith('Bavel') ? 'bavel' : 'ey';
    return 'na';
  }
  const year = y => y < 0 ? `${-y} ${t('bce')}` : `${y}${HE() ? '' : ''}`;
  function dates(x) {
    if (x.born && x.died) return t('about', `${year(x.born[0])}–${year(x.died[x.died.length - 1])}${x.died[0] > 0 ? ' ' + t('ce') : ''}`);
    if (x.died) return t('died', (x.died[0] !== x.died[1] ? t('about', '') : '') + year(x.died[x.died.length - 1])) + (x.died[0] > 0 ? ' ' + t('ce') : '');
    if (x.years) {
      const [a, b] = x.years;
      return t('about', a < 0 && b <= 0 ? `${-a}–${-b} ${t('bce')}` : a < 0 ? `${-a} ${t('bce')}–${b} ${t('ce')}` : `${a}–${b} ${t('ce')}`);
    }
    return '';
  }
  function meta(x) {
    const kind = x.kind ? t(x.kind) : '';
    const gen = x.gen == null ? '' : x.gen === 0 ? t('trans') : HE() ? t('gen', HE_ORD[x.gen] || x.gen) : t('gen', ORD(x.gen));
    const reg = (x.region || '').split(' / ').map(r => r.startsWith('Bavel') ? t('bavel') : t('ey')).join(' / ');
    return [kind && gen ? `${kind}, ${gen}` : kind || gen, x.region ? reg : '', dates(x)].filter(Boolean).join(' · ');
  }

  // ---------- data ----------
  async function load() {
    if (S.data) return;
    const r = await fetch(S.o.base + 'sages.json');
    S.data = await r.json();
  }
  async function loadQuoted() {
    if (S.quoted) return;
    S.quoted = await (await fetch(S.o.base + 'quoted.json')).json();
  }
  // tractates in the order of the books (Sefaria's spellings, and the variants the data uses), the rest last
  const SEDER = {
    mishnah: 'Berakhot,Peah,Demai,Kilayim,Sheviit,Terumot,Maasrot,Maaser Sheni,Challah,Orlah,Bikkurim,Shabbat,Eruvin,Pesachim,Shekalim,Yoma,Sukkah,Beitzah,Rosh Hashanah,Taanit,Megillah,Moed Katan,Chagigah,Yevamot,Ketubot,Nedarim,Nazir,Sotah,Gittin,Kiddushin,Bava Kamma,Bava Metzia,Bava Batra,Sanhedrin,Makkot,Shevuot,Eduyot,Avodah Zarah,Avot,Horayot,Zevachim,Menachot,Chullin,Bekhorot,Arakhin,Temurah,Keritot,Meilah,Tamid,Middot,Kinnim,Kelim,Oholot,Negaim,Parah,Tahorot,Mikvaot,Niddah,Makhshirin,Zavim,Tevul Yom,Yadayim,Oktzin',
    bavli: 'Berakhot,Shabbat,Eruvin,Pesachim,Shekalim,Yoma,Sukkah,Beitzah,Rosh Hashanah,Taanit,Megillah,Moed Katan,Chagigah,Yevamot,Ketubot,Nedarim,Nazir,Sotah,Gittin,Kiddushin,Bava Kamma,Bava Metzia,Bava Batra,Sanhedrin,Makkot,Shevuot,Avodah Zarah,Horayot,Zevachim,Menachot,Chullin,Bekhorot,Arakhin,Temurah,Keritot,Meilah,Kinnim,Tamid,Middot,Niddah' };
  const SEDER_ALT = { Eiruvin: 'Eruvin', Hullin: 'Chullin', "Ta'anit": 'Taanit' };   // the data's spellings -> the ones listed above
  const seder = tr => { const list = SEDER[S.o.corpus] || SEDER.bavli, k = SEDER_ALT[tr] || tr; const i = list.split(',').indexOf(k); return i < 0 ? 999 : i; };
  const byTractate = ([a], [b]) => seder(a) - seder(b) || a.localeCompare(b);
  const tierOf = x => S.o.corpus === 'mishnah' ? x.tier_mishnah : x.tier;
  const countOf = x => (x.count || {})[S.o.corpus] || 0;
  // a row's people, most important first; family keeps its relation as a label
  function people(id, rels) {
    const x = sage(id), out = [];
    for (const r of rels)
      for (const l of (x.links[r] || [])) {
        const y = l.id && sage(l.id);
        if (!y && r !== 'family' && !FAMILY.includes(r)) continue;   // a bare name only in the family row
        if (!y && !l.name) continue;                                  // unnamed ("his daughter"): info box only
        if (!y && l.alts) continue;                                   // several proposed names: info box only
        out.push({ key: (l.id || 'name:' + l.name) + '|' + r, id: y ? l.id : null, name: y ? shortName(y) : l.name,
                   rel: r, x: y, f: y ? y.f : l.f });
      }
    const named = p => (S.o.clay && !(p.x && countOf(p.x) > 0)) ? 1 : 0;   // clay: sages the Mishnah names come first
    out.sort((a, b) => named(a) - named(b) || (a.x ? tierOf(a.x) : 4) - (b.x ? tierOf(b.x) : 4) || (b.x ? countOf(b.x) : 0) - (a.x ? countOf(a.x) : 0));
    const seen = new Set();
    return out.filter(p => { const k = p.id || p.name; if (seen.has(k)) return false; seen.add(k); return true; });
  }
  const NOTES = { 'שנוי במחלוקת': 'Disputed.', 'לפי חלק מהדעות': 'By some accounts.', 'לפי המסורת': 'By tradition.',
                  'מסורת עממית': 'A folk tradition.', 'לפי הזוהר': 'According to the Zohar.',
                  'לפי חלקים מהזוהר': 'According to parts of the Zohar.', 'לפי חלק מהזוהר': 'According to part of the Zohar.',
                  'נינו': 'Great-grandson.' };
  const FAM_UP = ['grandparents', 'father', 'mother', 'parents', 'in_laws'];
  // the family word for a relation, by the relative's sex (and, for a spouse, the centre's)
  const FW = {
    en: { children: ['Son', 'Daughter', 'Sons', 'Daughters'], parents: ['Father', 'Mother'], father: ['Father', 'Mother'],
          mother: ['Mother', 'Mother'], siblings: ['Brother', 'Sister', 'Brothers', 'Sisters'], spouse: ['Wife', 'Husband'],
          in_laws: ['Father-in-law', 'Mother-in-law'], sons_in_law: ['Son-in-law', 'Son-in-law', 'Sons-in-law', 'Sons-in-law'],
          grandchildren: ['Grandson', 'Granddaughter', 'Grandsons', 'Granddaughters'],
          grandparents: ['Grandfather', 'Grandmother', 'Grandparents', 'Grandparents'] },
    he: { children: ['בנו', 'בתו', 'בניו', 'בנותיו'], parents: ['אביו', 'אמו'], father: ['אביו', 'אמו'], mother: ['אמו', 'אמו'],
          siblings: ['אחיו', 'אחותו', 'אחיו', 'אחיותיו'], spouse: ['אשתו', 'בעלה'], in_laws: ['חמיו', 'חמותו'],
          sons_in_law: ['חתנו', 'חתנו', 'חתניו', 'חתניו'],
          grandchildren: ['נכדו', 'נכדתו', 'נכדיו', 'נכדותיו'], grandparents: ['סבו', 'סבתו', 'סביו', 'סביו'] },
  };
  function famWord(rel, female, centreFemale, plural) {
    const w = (FW[S.o.lang] || FW.en)[rel];
    if (!w) return t(rel);
    if (rel === 'spouse') return w[centreFemale ? 1 : 0];
    const i = (female ? 1 : 0) + (plural && w.length > 2 ? 2 : 0);
    return w[i];
  }
  const FAMILY = ['grandparents', 'father', 'mother', 'parents', 'in_laws', 'spouse', 'siblings', 'children',
                  'sons_in_law', 'grandchildren'];

  // ---------- box ----------
  function build() {
    if (S.box) return;
    const b = document.createElement('div');
    b.className = 'sgx'; b.hidden = true; b.setAttribute('role', 'dialog'); b.setAttribute('aria-label', t('rel'));
    b.innerHTML = `<header class="sgx-bar"><h2>${t('rel')}</h2><nav class="sgx-trail" aria-label="${t('back')}"></nav>
      <button type="button" class="sgx-x" aria-label="${t('close')}">×</button></header>
      <div class="sgx-scroll"><div class="sgx-views" role="group" hidden><button type="button" data-view="ts"></button><button type="button" data-view="fam"></button></div><div class="sgx-graph"><svg class="sgx-lines" aria-hidden="true"><defs>
      <marker id="sgxArrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="11" markerHeight="11" markerUnits="userSpaceOnUse" orient="auto">
      <path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker>
      <marker id="sgxArrowT" class="t" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="11" markerHeight="11" markerUnits="userSpaceOnUse" orient="auto">
      <path d="M0,0 L10,5 L0,10 z"/></marker>
      <marker id="sgxArrowS" class="s" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="11" markerHeight="11" markerUnits="userSpaceOnUse" orient="auto">
      <path d="M0,0 L10,5 L0,10 z"/></marker></defs></svg></div>
      <p class="sgx-key"><span><i class="sw zug"></i>${t('keyZ')}</span><span><i class="sw tanna"></i>${t('keyTa')}</span>
      <span><i class="sw ey"></i>${t('keyEY')}</span><span><i class="sw bavel"></i>${t('keyBV')}</span>
      <span class="sgx-roles"><span><i class="sw role r-teachers"></i><svg class="sgx-lk t" width="30" height="12"><path d="M1,6 L15,6 L29,6" marker-mid="url(#sgxArrowT)"/></svg>${t('keyRT')}</span><span><i class="sw role r-students"></i><svg class="sgx-lk s" width="30" height="12"><path d="M1,6 L15,6 L29,6" marker-mid="url(#sgxArrowS)"/></svg>${t('keyRS')}</span><span><i class="sw role r-colleagues"></i>${t('keyRC')}</span></span>
      </p>
      <div class="sgx-info" aria-live="polite"></div></div>`;
    if (HE()) b.dir = 'rtl';
    document.body.appendChild(b);
    S.box = b;
    b.querySelector('.sgx-x').onclick = close;
    b.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
    // "More about him" opens below the pictures, often out of sight: bring what it opened into view
    b.addEventListener('toggle', e => { if (e.target.matches && e.target.matches('.sgx-moreinfo') && e.target.open) setTimeout(() => e.target.querySelector('summary').scrollIntoView({ block: 'start', behavior: 'smooth' }), 30); }, true);
    b.addEventListener('click', e => {
      const vb = e.target.closest('button[data-view]');   // (not the box itself, which carries data-view too)
      if (vb) { S.view = vb.dataset.view; fit(S.cur); draw(true); views(); return; }
      const nb = e.target.closest('.sgx-note');
      if (nb) { showNote(nb); return; }
      if (e.target.closest('.sgx-popx') || !e.target.closest('.sgx-pop')) S.box.querySelector('.sgx-pop')?.remove();
      const n = e.target.closest('[data-go]');
      if (n) { S.view = 'ts'; go(n.dataset.go); return; }   // a click always opens that sage's own page (teachers and students), even from the family tree
      const m = e.target.closest('[data-more]');
      if (m) { S.open[m.dataset.more] = !S.open[m.dataset.more]; draw(true); return; }
      const tr = e.target.closest('[data-tr]');
      if (tr) { showPlaces(tr.dataset.tr); return; }
      const bk = e.target.closest('[data-back]');
      if (bk) { const i = +bk.dataset.back; const id = S.trail[i]; S.trail = S.trail.slice(0, i); S.view = 'ts'; go(id, true); }
    });
    let rt; window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => !b.hidden && draw(false), 120); });
    // the box can be dragged to a new size (the corner handle); the sages spread out or close up to fit
    if (window.ResizeObserver) { new ResizeObserver(() => { if (S.o.clay && !b.hidden && S.autoW != null && Math.abs(b.offsetWidth - (S.autoW || Math.min(920, innerWidth - 16))) > 3 && !S.fitting) S.manualW = true; }).observe(b);
      let lw = 0, ro; new ResizeObserver(() => { const w = b.querySelector('.sgx-graph').clientWidth; if (b.hidden || !w || w === lw) return; lw = w; clearTimeout(ro); ro = setTimeout(() => draw(false), 80); }).observe(b.querySelector('.sgx-graph')); }
  }
  function close() { if (S.box) S.box.hidden = true; }

  async function open(id) {
    build();
    S.box.hidden = false;
    S.box.querySelector('.sgx-info').textContent = t('loading');
    await load();
    if (!sage(id)) { S.box.querySelector('.sgx-info').textContent = ''; return; }
    S.trail = []; S.cur = null; S.nodes.forEach(n => n.el.remove()); S.nodes.clear(); S.manualW = false; S.view = 'ts';
    go(id);
    S.box.querySelector('.sgx-x').focus({ preventScroll: true });
  }
  function go(id, fromTrail) {
    if (!sage(id) || id === S.cur) return;
    if (S.cur && !fromTrail) S.trail.push(S.cur);
    if (S.trail.length > 8) S.trail = S.trail.slice(-8);
    S.cur = id; S.open = {};
    pickView(id);
    fit(id);
    draw(true); views(); info();
    if (S.view === 'fam') centreFamily(); else S.box.querySelector('.sgx-scroll').scrollTo({ top: 0, behavior: 'smooth' });
  }

  // Clay look: when a sage has many teachers or students the box widens to show them in one row, as far as the window
  // allows; with few, it goes back to its usual width. Not once the reader has dragged the box to a size himself.
  function fit(id) {
    if (!S.o.clay || S.manualW || innerWidth < 700) return;
    let n = Math.min(8, Math.max(people(id, ['teachers']).length, people(id, ['students']).length)), w = n <= 3 ? 0 : Math.min(innerWidth - 16, 760 + 170 * (n - 3) + 32);
    if (S.view === 'fam') { const fg = famGraph(id), lay = famLayout(fg, 112, 138, 0); w = lay.need > 700 ? Math.min(innerWidth - 16, lay.need + 40) : 0; }
    S.autoW = w; S.box.style.width = w ? w + 'px' : '';
  }
  // ---------- graph ----------
  // Clay look (Mishnah): a clay picture with the name under it. The middle sage has his own picture; teachers and
  // students each have three, and a sage keeps the same one (from his name), moving on if it is already used in the row.
  const FACES = ['main', 'teacher-1', 'teacher-2', 'teacher-3', 'student-1', 'student-2', 'student-3', 'woman-1', 'woman-2'];
  const WOMEN = [7, 8], MEN = [0, 1, 2, 3, 4, 5, 6];   // a woman gets a woman's picture, a man a man's
  const WOMAN_FACE = { 'rachel-(rabbi-akiva)': 7, beruriah: 8 };
  const FACE_PREF = { centre: [0], teachers: [1, 2, 3], students: [4, 5, 6] };
  const isWoman = p => { const x = p.id && sage(p.id); return !!(x && (x.f === 1 || x.f === '1' || x.f === true)) || (!p.id && p.f === 1); };   // what a sage gets the first time, by his role
  const figHash = k => { let h = 5381; for (const c of String(k)) h = (h * 33 + c.charCodeAt(0)) >>> 0; return h; };
  // A sage keeps his picture when he moves (a student who is clicked glides to the middle with his own face);
  // among the sages on screen no two share one while there are pictures left.
  function assignFaces(placed) {
    const used = new Set(), row = { teachers: new Set(), students: new Set() }, faceOf = S.faceOf;
    const take = (p, f) => { used.add(f); if (row[p.rel]) row[p.rel].add(f); p.fig = f; };
    const ordered = [...placed].sort((a, b) => (b.centre ? 1 : 0) - (a.centre ? 1 : 0));   // the middle sage chooses first
    for (const p of ordered) { const f = faceOf.get(p.id || p.name); if (f != null && !used.has(f) && (WOMEN.includes(f) === isWoman(p))) take(p, f); }
    for (const p of ordered) {
      if (p.fig != null) continue;
      const k = p.id || p.name, w = isWoman(p);
      const pref = w ? WOMEN : (FACE_PREF[p.centre ? 'centre' : p.rel] || []), rest = (w ? WOMEN : MEN).filter(f => !pref.includes(f));
      const h = figHash(k);
      const order = [...(w && WOMAN_FACE[k] != null ? [WOMAN_FACE[k]] : []), ...pref.map((_, i) => pref[(h + i) % pref.length]), ...rest.map((_, i) => rest[(h + i) % rest.length])]
        .filter((f, i, a) => a.indexOf(f) === i);   // her or his own kind of picture first
      let f = order.find(c => !used.has(c));
      if (f != null) faceOf.set(k, f);                 // a picture nobody else on screen has: he keeps it from now on
      else {                                           // more sages than pictures: repeat one, but never within a row or with the middle sage
        const mid = placed.find(q => q.centre)?.fig;
        f = order.find(c => c !== mid && !(row[p.rel] && row[p.rel].has(c))) ?? order[0];
      }
      take(p, f);
    }
  }
  const SILHOUETTE = "data:image/svg+xml;utf8," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 100"><path d="M8 100C8 66 22 56 40 56s32 10 32 44z" fill="#9a8f80"/><ellipse cx="40" cy="32" rx="21" ry="26" fill="#b8ad9c"/><circle cx="40" cy="36" r="14" fill="#e6d3b8"/></svg>');
  function figure(n, colour) {   // colour: gold (the middle sage), blue (a teacher), green (a student): his own picture, dressed for his role
    // (the women's pictures are in gold only so far; until a picture exists a plain silhouette stands in)
    const c = WOMEN.includes(n) ? 'gold' : colour;
    return `<span class="sgx-ring"><img class="sgx-fig" src="${esc(S.o.base)}fig/${FACES[n % FACES.length]}-${c}.png" alt="" draggable="false" onerror="this.onerror=null;this.src='${SILHOUETTE}'"></span>`;
  }

  // ---------- the family tree ----------
  // The second view of the box (a pill above the chart): the sage in his family, up to four generations either way.
  // Parents and children are joined by lines; a spouse stands beside the person; a link we only know in general
  // (a grandfather, a son-in-law) is a dotted line.
  const REL_EN = { up: ['Parent', 'Father', 'Mother'], 'up2': ['Grandparent', 'Grandfather', 'Grandmother'], 'up3': ['Great-grandparent', 'Great-grandfather', 'Great-grandmother'],
                   'up4': ['Great-great-grandparent', 'Great-great-grandfather', 'Great-great-grandmother'],
                   down: ['Child', 'Son', 'Daughter'], 'down2': ['Grandchild', 'Grandson', 'Granddaughter'], 'down3': ['Great-grandchild', 'Great-grandson', 'Great-granddaughter'],
                   'down4': ['Great-great-grandchild', 'Great-great-grandson', 'Great-great-granddaughter'] };
  const REL_HE = { up: ['הורה', 'אביו', 'אמו'], up2: ['סב או סבתא', 'סבו', 'סבתו'], up3: ['אבי סבו', 'אבי סבו', 'אם סבתו'], up4: ['אבות אבותיו', 'אבות אבותיו', 'אבות אבותיו'],
                   down: ['ילד', 'בנו', 'בתו'], down2: ['נכד', 'נכדו', 'נכדתו'], down3: ['נין', 'נינו', 'נינתו'], down4: ['נין', 'נינו', 'נינתו'] };
  function relLabel(n, centre) {
    const d = n.gen; if (n.centre) return '';
    const sx = n.f ? 2 : 1, tab = HE() ? REL_HE : REL_EN;
    if (n.inlaw) return d < 0 ? famWord('in_laws', n.f, centre.f) : d > 0 ? famWord('sons_in_law', n.f, centre.f) : '';
    if (d === 0) return n.sib ? famWord('siblings', n.f, centre.f) : n.spouse ? famWord('spouse', n.f, centre.f) : '';
    const k = (d < 0 ? 'up' : 'down') + (Math.abs(d) > 1 ? Math.min(4, Math.abs(d)) : '');
    if (Math.abs(d) > 2 && !HE()) { const gr = 'Great' + '-great'.repeat(Math.abs(d) - 3) + '-'; return gr + (d < 0 ? (n.f ? 'grandmother' : 'grandfather') : (n.f ? 'granddaughter' : 'grandson')); }
    return (tab[k] || tab[d < 0 ? 'up4' : 'down4'])[sx];
  }
  const MAXGEN = 7;
  function famGraph(id) {
    const nodes = new Map(), edges = [];
    const S0 = sage(id);
    const C = { key: id, id, name: fullName(S0), gen: 0, centre: true, f: S0.f }; nodes.set(id, C);
    const mk = (l, gen, extra) => {
      const y = l.id && sage(l.id);
      if (!y && (!l.name || l.alts)) return null;                      // unnamed ("his daughter"), or several proposed names: the info box only
      const k = y ? l.id : 'name:' + l.name;
      if (!nodes.has(k)) nodes.set(k, { key: k, id: y ? l.id : null, name: y ? shortName(y) : l.name, gen, f: y ? y.f : l.f, ...extra });
      return nodes.get(k);
    };
    const edge = (a, b, type) => { if (a && b && a.key !== b.key && !edges.some(e => e.a === a.key && e.b === b.key && e.type === type)) edges.push({ a: a.key, b: b.key, type }); };
    const done = new Set();
    function expand(pn, up, down, depth) {
      const tag = pn.key + (up ? 'u' : '') + (down ? 'd' : ''); if (!pn.id || done.has(tag)) return; done.add(tag);
      const L = sage(pn.id).links, each = (rels, fn) => rels.forEach(r => (L[r] || []).forEach(l => fn(l, r)));
      if (up && depth < MAXGEN) {
        each(['father', 'mother', 'parents'], l => { const q = mk(l, pn.gen - 1); if (q) { edge(q, pn, 'pc');
          if (q.id) expand(q, true, false, depth + 1);
          else for (const [oid, o] of Object.entries(S.data.sages))   // a father we only have by name (Shimon b. Hillel): a sage who lists a child of that name is HIS father
            if ((o.links.children || []).some(c => !c.id && c.name === l.name)) { const g = mk({ id: oid }, q.gen - 1); if (g) { edge(g, q, 'pc'); expand(g, true, false, depth + 2); } } } });
        each(['grandparents'], l => { const q = mk(l, pn.gen - 2); if (q) edge(q, pn, 'far'); });
        each(['in_laws'], l => { const q = mk(l, pn.gen - 1, { inlaw: true }); if (q) edge(q, pn, 'far'); });
      }
      if (down && depth < MAXGEN) {
        each(['children'], l => { const q = mk(l, pn.gen + 1); if (q) { edge(pn, q, 'pc');
          if (q.id) expand(q, false, true, depth + 1);
          else for (const [oid, o] of Object.entries(S.data.sages))   // a child we only have by name: a sage who lists a father of that name is HIS child
            if (['father', 'parents'].some(r => (o.links[r] || []).some(c => !c.id && c.name === l.name))) { const g = mk({ id: oid }, q.gen + 1); if (g) { edge(q, g, 'pc'); expand(g, false, true, depth + 2); } } } });
        each(['sons_in_law'], l => { const q = mk(l, pn.gen + 1, { inlaw: true }); if (q) edge(pn, q, 'far'); });
        each(['grandchildren'], l => { const q = mk(l, pn.gen + 2); if (q) edge(pn, q, 'far'); });
      }
      each(['spouse'], l => { const q = mk(l, pn.gen, { spouse: pn.centre }); if (q) edge(pn, q, 'sp'); });
      if (pn.centre) each(['siblings'], l => { const q = mk(l, pn.gen, { sib: true }); if (q) edge(pn, q, 'sib'); });   // listed brothers and sisters (when the parents are not known)
    }
    expand(C, true, true, 0);
    // his brothers and sisters: the other children of his parents
    [...nodes.values()].filter(n => n.gen === -1 && n.id).forEach(par => (sage(par.id).links.children || []).forEach(l => {
      if (l.id === id) return; const q = mk(l, 0, { sib: true }); if (q) edge(par, q, 'pc'); }));
    return { nodes, edges };
  }
  // generations in rows, parents above children; each row ordered under its parents, a spouse next to her partner
  function famLayout(fg, nodeW, rowH, width) {
    const slot = nodeW + 24, all = [...fg.nodes.values()], gens = [...new Set(all.map(n => n.gen))].sort((a, b) => a - b);
    const par = n => fg.edges.filter(e => e.b === n.key && e.type === 'pc').map(e => fg.nodes.get(e.a));
    const mate = n => { const e = fg.edges.find(e => e.type === 'sp' && (e.a === n.key || e.b === n.key)); return e && fg.nodes.get(e.a === n.key ? e.b : e.a); };
    gens.forEach(gn => {
      let row = all.filter(n => n.gen === gn);
      row.forEach(n => { const ps = par(n).filter(q => q.x != null); n.want = ps.length ? ps.reduce((a, q) => a + q.x, 0) / ps.length : null; });
      row.forEach(n => { if (n.want == null) { const m = mate(n); if (m && m.want != null) n.want = m.want + 0.01; } });
      row.sort((a, b) => (a.want ?? 1e9) - (b.want ?? 1e9));
      const out = [];   // a spouse right after her partner
      row.forEach(n => { if (out.includes(n)) return; out.push(n); const m = mate(n); if (m && m.gen === gn && !out.includes(m)) out.push(m); });
      let prevX = -1e9;
      out.forEach((n, i) => { const w = n.want != null ? n.want : (i ? prevX + slot : 0); n.x = Math.max(w, prevX + slot); prevX = n.x; });
      // centre the row on what its members wanted
      const wants = out.filter(n => n.want != null);
      if (wants.length) { const sh = wants.reduce((a, n) => a + (n.want - n.x), 0) / wants.length; if (sh > 0) out.forEach(n => n.x += sh); }
      else { const m = (out[0].x + out[out.length - 1].x) / 2; out.forEach(n => n.x -= m); }
    });
    const minX = Math.min(...all.map(n => n.x)), maxX = Math.max(...all.map(n => n.x));
    const need = maxX - minX + slot + 16, off = Math.max(0, (width - need) / 2);
    all.forEach(n => { n.px = n.x - minX + slot / 2 + 8 + off; n.py = 62 + gens.indexOf(n.gen) * rowH; });
    return { need, height: 62 + (gens.length - 1) * rowH + rowH * 0.6, gens };
  }
  const famOk = id => famGraph(id).nodes.size > 1;
  const tsOk = id => ['teachers', 'students', 'colleagues'].some(r => people(id, [r]).some(p => p.id));
  function pickView(id) {
    const hasF = famOk(id), hasT = tsOk(id);
    if (S.view === 'fam' && !hasF) S.view = 'ts';
    if (S.view === 'ts' && !hasT && hasF) S.view = 'fam';
  }
  function views() {
    const box = S.box.querySelector('.sgx-views'), hasF = famOk(S.cur), hasT = tsOk(S.cur);
    box.hidden = !(hasF && hasT);   // one view only: nothing to choose
    const bs = box.querySelectorAll('button'); bs[0].textContent = t('vTS'); bs[1].textContent = t('vFam');
    bs.forEach(b => b.setAttribute('aria-pressed', String(b.dataset.view === S.view)));
  }
  function drawFamily(animate) {
    const g = S.box.querySelector('.sgx-graph'), svg = g.querySelector('svg'), clay = !!S.o.clay;
    S.box.dataset.view = 'fam'; g.classList.toggle('clay', clay); g.classList.add('famview');
    const sc = S.box.querySelector('.sgx-scroll'), avail = sc.clientWidth - 2 || 600, phone = avail < 560;
    const nodeW = clay ? (phone ? 92 : 112) : phone ? 88 : 118, rowH = clay ? (phone ? 128 : 138) : 74;
    const fg = famGraph(S.cur), lay = famLayout(fg, nodeW, rowH, avail), centre = fg.nodes.get(S.cur), cx = sage(S.cur);
    const width = Math.max(avail, lay.need);
    g.style.width = width + 'px';
    const X = x => HE() ? width - x : x;
    const place = [...fg.nodes.values()].map(n => ({
      key: n.key, id: n.id, name: n.name, x: X(n.px), y: n.py, centre: n.centre, f: n.f, famNode: true, maxW: nodeW,
      rel: n.gen < 0 ? 'teachers' : n.gen > 0 ? 'students' : 'centre',       // older: blue, younger: green, same generation: gold
      colour: n.gen < 0 ? 'blue' : n.gen > 0 ? 'green' : 'gold', label: relLabel(n, centre) }));
    S.famEdges = fg.edges;
    g.style.height = (lay.height + 70) + 'px';
    svg.setAttribute('width', width); svg.setAttribute('height', lay.height + 70);
    commit(place, [], animate, { g, clay, width, nodeW, cw: nodeW * 1.5, x: cx });
    centreFamily();
  }
  // a long tree opens with the chosen sage in the middle of what is shown (up and down, and sideways when it is wide)
  function centreFamily() {
    const go = () => {
      const n = S.nodes.get(S.cur), sc = S.box.querySelector('.sgx-scroll'); if (!n || S.view !== 'fam') return;
      const r = n.el.getBoundingClientRect(), b = sc.getBoundingClientRect();
      sc.scrollTop += (r.top + r.height / 2) - (b.top + b.height * 0.42);   // a little above the middle: his name and relatives below him show too
      sc.scrollLeft += (r.left + r.width / 2) - (b.left + b.width / 2);
    };
    requestAnimationFrame(go); setTimeout(go, 120); setTimeout(go, 700);
  }
  function draw(animate) {
    if (S.view === 'fam') return drawFamily(animate);
    S.box.dataset.view = 'ts'; S.box.querySelector('.sgx-graph').style.width = ''; S.box.querySelector('.sgx-graph').classList.remove('famview');
    const g = S.box.querySelector('.sgx-graph'), svg = g.querySelector('svg');
    const clay = !!S.o.clay, width = g.clientWidth || 600, phone = width < 560, cap = clay ? (phone ? 3 : 3 + Math.floor(Math.max(0, width - 760) / 170)) : phone ? 3 : Math.max(6, Math.floor(width / 150)), nodeW = clay ? (phone ? 96 : 120) : phone ? 92 : 124;
    g.classList.toggle('clay', clay);
    narrow = phone;
    const rtl = HE(), X = x => rtl ? width - x : x;
    const id = S.cur, x = sage(id);
    // a sage linked two ways appears once: teacher, then student, family, colleague
    const used = new Set();
    const row = (rels, keep) => people(id, rels).filter(p => {
      if (keep && !keep(p)) return false;
      if (!p.id && !HE()) return false;          // a name we only have in Hebrew stays in the info box
      const k = p.id || p.name; if (used.has(k)) return false; used.add(k); return true; });
    const rows = {};
    // Family: the generation above (father, mother, father-in-law) above him, the one below
    // (children, sons-in-law) and his wife and brothers below him, drawn lighter than the teachers
    // and students. A teacher who is also his father stays a teacher, labelled "Father".
    const famOf = {};
    // a relative listed two ways (son-in-law, and by one tradition father-in-law) is drawn by the
    // link with no qualifying note
    FAMILY.forEach(r => (x.links[r] || []).forEach(l => { if (l.id && !l.notes && !famOf[l.id]) famOf[l.id] = r; }));
    FAMILY.forEach(r => (x.links[r] || []).forEach(l => { if (l.id && !famOf[l.id]) famOf[l.id] = r; }));
    rows.teachers = row(['teachers']); rows.students = row(['students']);
    const famRow = rels => row(rels, p => !p.id || rels.includes(famOf[p.id]));
    rows.famUp = famRow(FAM_UP); rows.famDown = famRow(FAMILY.filter(r => !FAM_UP.includes(r)));
    rows.colleagues = row(['colleagues']);
    rows.famUp = []; rows.famDown = [];   // family has its own view (the pill above the chart); here it is only the label under a name
    if (clay) rows.colleagues = [];   // clay: teachers and students only
    [...rows.teachers, ...rows.students].forEach(p => { if (p.id && famOf[p.id]) p.famRel = famOf[p.id]; });
    const place = [];   // {key, id, name, x, y, cls, label}
    const more = [];    // "+N more" buttons
    let y = clay ? 76 : 50;
    function band(name, list, perLine, all) {
      if (!list.length) return null;
      // a "+1 more" button would take the space of the one it hides: show it instead
      const open = all || S.open[name] || list.length === perLine + 1, shown = open ? list : list.slice(0, perLine);
      const extra = list.length - shown.length;
      const lines = [];
      for (let i = 0; i < shown.length; i += perLine) lines.push(shown.slice(i, i + perLine));
      const ys = [];
      lines.forEach((ln, li) => {
        const btn = !all && li === lines.length - 1 && (extra > 0 || (S.open[name] && list.length > perLine + 1));
        const n = clay ? ln.length : ln.length + (btn ? 1 : 0);   // clay: the "+N more" button goes at the edge, so the sages stay symmetrical
        ln.forEach((p, i) => place.push({ ...p, x: X((i + 1) * width / (n + 1)), y, maxW: width / (n + 1) - 10 }));
        if (btn)
          more.push({ row: name, x: clay ? X(width - 34) : X(n * width / (n + 1)), y: clay ? y + (phone ? 92 : 20) : y, label: extra > 0 ? t('more', extra) : t('fewer') });
        ys.push(y); y += clay ? 124 : phone ? 58 : 64;
      });
      return ys;
    }
    const tY = band('teachers', rows.teachers, cap);
    if (tY) y += clay ? 98 : rows.famUp.length ? 8 : phone ? 40 : 62;
    if (rows.famUp.length) { band('famUp', rows.famUp, phone ? 3 : 5); y += 20; }
    const cY = y;
    place.push({ key: id, id, name: fullName(x), x: width / 2, y: cY, centre: true });
    // colleagues on both sides of the centre, nearest first
    // colleagues on both sides of the centre, nearest first; the rest (opened) wrap onto lines below
    const side = phone ? 1 : Math.max(3, Math.floor(width / 330)), cols = rows.colleagues, beside = cols.slice(0, side * 2);
    const cw = phone ? width * 0.36 : Math.min(width * 0.3, nodeW * 1.6), slot = (width / 2 - cw / 2 - 8) / side;
    beside.forEach((p, i) => {
      const dir = i % 2 === 0 ? -1 : 1, k = Math.floor(i / 2);
      place.push({ ...p, x: X(width / 2 + dir * (cw / 2 + 8 + slot * (k + 0.5))), y: cY, maxW: slot - 10 });
    });
    y += clay ? (phone ? 190 : 214) : phone ? 66 : 70;
    const restC = cols.slice(side * 2);
    if (restC.length === 1) band('colleagues_more', restC, cap, true);   // one more: just show him
    else if (restC.length) {
      if (S.open.colleagues) band('colleagues_more', restC.map(p => ({ ...p })), cap, true);
      more.push({ row: 'colleagues', x: X(width - slot / 2), y: cY + 32, small: true,
                  label: S.open.colleagues ? t('fewer') : t('more', restC.length) });
    }
    const fY = rows.famDown.length ? band('famDown', rows.famDown, phone ? 3 : 5) : null;
    if (fY) y += 6;
    if (rows.students.length) y += clay ? 0 : phone ? 36 : 56;
    const sY = band('students', rows.students, cap);
    g.style.height = (y + (sY ? 4 : 20)) + 'px';
    svg.setAttribute('width', width); svg.setAttribute('height', y + 20);

    commit(place, more, animate, { g, clay, width, nodeW, cw, x });
  }
  // put the nodes on screen (reusing those already there, so they glide), and the "+N more" buttons, and the lines
  function commit(place, more, animate, ctx) {
    const { g, clay, width, nodeW, cw, x } = ctx;
    if (clay) assignFaces(place);
    // nodes: reuse what is already on screen so it glides
    const want = new Map(place.map(p => [p.id || p.key, p]));
    const prev = S.nodes;
    const next = new Map();
    for (const [k, p] of want) {
      const sameSage = p.id ? prev.get(p.id) : prev.get(k);
      let el = sameSage && sameSage.el;
      if (!el) {
        el = document.createElement(p.id ? 'button' : 'span');
        if (p.id) { el.type = 'button'; el.dataset.go = p.id; }
        el.className = 'sgx-n';
        el.style.opacity = '0';
        el.style.transform = `translate(${p.x}px,${p.y}px) translate(-50%,-50%)`;
        g.appendChild(el);
      }
      const sx = p.centre ? x : p.id ? sage(p.id) : null;
      const fam = p.rel && FAMILY.includes(p.rel), famLabel = fam ? p.rel : p.famRel;
      el.className = `sgx-n g-${group(sx)} t${sx ? tierOf(sx) : 3} r-${p.centre ? 'centre' : p.rel}${p.centre ? ' centre' : ''}${p.id ? '' : ' plain'}${fam || p.famNode ? ' fam' : ''}`;
      el.innerHTML = (clay ? figure(p.fig, p.centre ? 'gold' : p.colour || (p.rel === 'teachers' ? 'blue' : 'green')) : '') + `${clay ? '<span class="sgx-nm">' : ''}${esc(p.centre ? fullName(x) : p.name)}${clay ? '</span>' : ''}${p.label ? `<small>${esc(p.label)}</small>` : famLabel ? `<small>${esc(famWord(famLabel, sx ? sx.f : p.f, x.f))}</small>` : ''}`;
      if (p.centre) el.removeAttribute('data-go'); else if (p.id) el.dataset.go = p.id;
      el.title = sx ? `${fullName(sx)} · ${meta(sx)}` : p.name;
      el.style.maxWidth = (p.centre ? (clay ? Math.min(width * 0.7, 220) : cw || nodeW * 1.5) : Math.min(nodeW, p.maxW || nodeW)) + 'px';
      requestAnimationFrame(() => {
        el.style.opacity = '1';
        el.style.transform = `translate(${p.x}px,${p.y}px) translate(-50%,-50%)`;
      });
      next.set(p.id || k, { el, p });
    }
    for (const [k, n] of prev) if (!next.has(k)) { n.el.style.opacity = '0'; setTimeout(() => n.el.remove(), 400); }
    S.nodes = next;
    g.querySelectorAll('.sgx-more').forEach(e => e.remove());
    for (const m of more) {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'sgx-more' + (m.small ? ' small' : ''); b.dataset.more = m.row; b.textContent = m.label;
      b.style.transform = `translate(${m.x}px,${m.y}px) translate(-50%,-50%)`;
      g.appendChild(b);
    }
    if (!animate) S.nodes.forEach(n => { n.el.style.transition = 'none'; requestAnimationFrame(() => n.el.style.transition = ''); });
    // lines follow the nodes while they move
    const t0 = performance.now();
    const tick = () => { lines(); if (performance.now() - t0 < 520) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  }
  function famLines(svg, gb) {
    const box = el => { const r = el.getBoundingClientRect(); return { x: r.left - gb.left + r.width / 2, y: r.top - gb.top + r.height / 2, w: r.width / 2, h: r.height / 2, t: r.top - gb.top, b: r.bottom - gb.top, l: r.left - gb.left, r: r.right - gb.left }; };
    let out = '';
    for (const e of S.famEdges) {
      const A = S.nodes.get(e.a), B = S.nodes.get(e.b); if (!A || !B) continue;
      const a = box(A.el), b = box(B.el);
      if (e.type === 'sib') { const lft = a.x < b.x ? a : b, rgt = a.x < b.x ? b : a; out += `<line class="dot" x1="${lft.r}" y1="${lft.y}" x2="${rgt.l}" y2="${rgt.y}"/>`; }
      else if (e.type === 'sp') { const lft = a.x < b.x ? a : b, rgt = a.x < b.x ? b : a; out += `<line class="fam sp" x1="${lft.r}" y1="${lft.y}" x2="${rgt.l}" y2="${rgt.y}"/>`; }
      else if (e.type === 'far') out += `<line class="dot" x1="${a.x}" y1="${a.b}" x2="${b.x}" y2="${b.t}"/>`;
      else { const m = (a.b + b.t) / 2; out += `<path class="tree" d="M${a.x},${a.b} V${m} H${b.x} V${b.t}"/>`; }
    }
    const defs = svg.querySelector('defs').outerHTML;
    svg.innerHTML = defs + out;
  }
  function lines() {
    const g = S.box.querySelector('.sgx-graph'), svg = g.querySelector('svg'), gb = g.getBoundingClientRect();
    const c = S.nodes.get(S.cur);
    if (!c) return;
    const box = el => { const r = el.getBoundingClientRect(); return { x: r.left - gb.left + r.width / 2, y: r.top - gb.top + r.height / 2, w: r.width / 2, h: r.height / 2 }; };
    if (S.view === 'fam') return famLines(svg, gb);
    const C = box(c.el);
    let out = '';
    for (const [k, n] of S.nodes) {
      if (k === S.cur) continue;
      const P = box(n.el), rel = n.p.rel;
      // an arrowhead halfway along each line, pointing from teacher to student, so the direction
      // reads even where many lines meet at the centre
      // teacher lines purple, student lines green, like the boxes
      const arrow = (x1, y1, x2, y2, k) => `<path class="${k}" d="M${x1},${y1} L${(x1 + x2) / 2},${(y1 + y2) / 2} L${x2},${y2}" marker-mid="url(#sgxArrow${k.toUpperCase()})"/>`;
      if (rel === 'teachers') out += arrow(P.x, P.y + P.h, C.x, C.y - C.h, 't');
      else if (rel === 'students') out += arrow(C.x, C.y + C.h, P.x, P.y - P.h, 's');
      else if (rel === 'colleagues') continue;   // no line: standing beside him at his level says it
      else if (P.y < C.y) out += `<line class="fam" x1="${P.x}" y1="${P.y + P.h}" x2="${C.x}" y2="${C.y - C.h}"/>`;
      else out += `<line class="fam" x1="${C.x}" y1="${C.y + C.h}" x2="${P.x}" y2="${P.y - P.h}"/>`;
    }
    const defs = svg.querySelector('defs').outerHTML;
    svg.innerHTML = defs + out;
  }

  // ---------- info box ----------
  // A small marker that opens the notes and sources behind an entry, so the box itself stays plain
  function noteMark(notes, alts) {
    const list = (notes || []).map(n => (!HE() && NOTES[n]) || n);
    if (!list.length && !alts) return '';
    const body = (alts ? [t('alts')] : []).concat(list);
    return `<button type="button" class="sgx-note" aria-label="${esc(t('notes'))}" data-note="${esc(JSON.stringify(body))}">i</button>`;
  }
  // Sefaria's bios link names as [R. Akiva](https://www.sefaria.org/topics/rabbi-akiva?tab=sources):
  // a sage we have opens in the box, anything else is plain text
  function bioHTML(bio) {
    let out = '', i = 0;
    const re = /\[([^\]]+)\]\(([^)\s]+)\)/g;
    let m;
    while ((m = re.exec(bio))) {
      out += esc(bio.slice(i, m.index));
      const slug = (m[2].match(/sefaria\.org(?:\.il)?\/topics\/([^?#/]+)/) || [])[1];
      const id = slug && decodeURIComponent(slug);
      out += id && sage(id) ? `<button type="button" data-go="${esc(id)}">${esc(m[1])}</button>` : esc(m[1]);
      i = m.index + m[0].length;
    }
    return (out + esc(bio.slice(i))).replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
  }
  function showNote(btn) {
    const old = S.box.querySelector('.sgx-pop');
    if (old) { const same = old._for === btn; old.remove(); if (same) return; }
    const pop = document.createElement('div');
    pop._for = btn;
    pop.className = 'sgx-pop';
    pop.innerHTML = JSON.parse(btn.dataset.note).map(n => `<p${/[\u05d0-\u05ea]/.test(n) ? ' lang="he" dir="rtl"' : ''}>${esc(n)}</p>`).join('')
      + `<button type="button" class="sgx-popx" aria-label="${esc(t('close'))}">×</button>`;
    const host = S.box.querySelector('.sgx-scroll');
    host.appendChild(pop);
    const hb = host.getBoundingClientRect(), bb = btn.getBoundingClientRect();
    pop.style.top = (bb.bottom - hb.top + host.scrollTop + 6) + 'px';
    pop.style.left = Math.max(8, Math.min(bb.left - hb.left - 20, hb.width - pop.offsetWidth - 8)) + 'px';
  }
  function info() {
    const x = sage(S.cur), box = S.box.querySelector('.sgx-info');
    S.box.querySelector('.sgx-trail').innerHTML = S.trail.map((id, i) =>
      `<button type="button" data-back="${i}">${esc(shortName(sage(id)))}</button>`).join('<span>›</span>');
    const n = countOf(x), q = (x.quoted || {})[S.o.corpus] || {};
    const top = Object.entries(q).slice(0, 5).sort(byTractate);   // the five he is named in most, in the order of the books
    const name = S.o.tractateName || (s => s);
    // one line per relation and sex: "Sons: …", "Daughter: …"
    const groups = [];
    FAMILY.forEach(r => [0, 1].forEach(f => {
      const ls = (x.links[r] || []).filter(l => ((l.id && sage(l.id)) ? sage(l.id).f : l.f) ? f : !f);
      if (ls.length) groups.push([famWord(r, f, x.f, ls.length > 1), ls]);
    }));
    const who = l => { const y = l.id && sage(l.id);
      return y ? `<button type="button" data-go="${esc(l.id)}">${esc(shortName(y))}</button>` : `<span lang="he" dir="rtl">${esc(l.name || '')}</span>`; };
    const fam = groups.map(([label, ls]) => `<span><b>${esc(label)}:</b> ${ls.map(l => {
      let txt;
      if (l.wife_of) txt = `${t('wifeOf')} ${who(l.wife_of)}`;
      else if (l.child_of) txt = `${t(l.f ? 'daughterOf' : 'sonOf')} ${who(l.child_of)}`;
      else txt = who(l);
      return txt + noteMark(l.notes, l.alts);
    }).join(', ')}</span>`).join('');
    const noRel = !['teachers', 'students', 'colleagues'].some(r => (x.links[r] || []).some(l => l.id));
    const bio = HE() && x.bio_he ? x.bio_he : x.bio;
    // the background in two short paragraphs, not one block: the first two sentences, then the rest
    const bioParas = !bio ? [] : (() => { const sent = bio.split(/(?<=[a-z0-9)\]\u201d"\u2019\u05d0-\u05ea][.!?])(?<!\bb\.)(?<!\bbar\.)(?<!\bvs\.)\s+(?=[A-Z"\u201c\u05d0-\u05ea])/);
      return sent.length > 2 ? [sent.slice(0, 2).join(' '), sent.slice(2).join(' ')] : [bio]; })();
    const bioLang = HE() && !x.bio_he ? ' lang="en" dir="ltr"' : '';
    const stories = x.stories && x.stories.length ? `<h4>${t('stories')}</h4><ul class="sgx-stories">${x.stories.map(s =>
        `<li><a href="${esc(S.o.link ? S.o.link(S.o.corpus, s.tractate, s.place) : '#')}">${esc(HE() && s.title_he ? s.title_he : s.title)}</a> <span>${esc(s.ref || '')}</span></li>`).join('')}</ul>` : '';
    const where = n ? `<h4>${t(S.o.corpus === 'mishnah' ? 'quotedM' : 'quotedB', n.toLocaleString())}${x.estimated_count ? ` <i title="${esc(t('est'))}">~</i>` : ''}</h4>
      <p class="sgx-where">${top.map(([tr, c]) => `<button type="button" data-tr="${esc(tr)}">${esc(name(tr))} <b>${c}</b></button>`).join('')}
      ${Object.keys(q).length > 5 ? `<button type="button" data-tr="*" class="all">${t('allT')}</button>` : ''}</p><div class="sgx-places"></div>` : '';
    const links = `<p class="sgx-links"><a href="https://www.sefaria.org${HE() ? '.il' : ''}/topics/${encodeURIComponent(x.sefaria)}" target="_blank" rel="noopener">${t('sefaria')}</a>
      ${x.wiki_he ? `<a href="${esc(x.wiki_he)}" target="_blank" rel="noopener">${t('wiki')}</a>` : ''}</p>`;
    if (S.o.clay) {
      box.innerHTML = `<h3>${esc(fullName(x))} <span lang="${HE() ? 'en' : 'he'}" dir="${HE() ? 'ltr' : 'rtl'}">${esc(HE() ? x.en : x.he)}</span></h3>
        <p class="sgx-meta">${esc(meta(x))}${x.years && !x.died ? ` <i title="${esc(t('approx'))}">*</i>` : ''}</p>
        ${bioParas.map(t => `<p class="sgx-bio"${bioLang}>${bioHTML(t)}</p>`).join('')}
        <details class="sgx-moreinfo"><summary>${t('moreAbout')}</summary>
        ${fam ? `<p class="sgx-fam">${fam}</p>` : ''}${stories}${where}${links}</details>`;
      return;
    }
    box.innerHTML = `<h3>${esc(fullName(x))} <span lang="${HE() ? 'en' : 'he'}" dir="${HE() ? 'ltr' : 'rtl'}">${esc(HE() ? x.en : x.he)}</span></h3>
      <p class="sgx-meta">${esc(meta(x))}${x.years && !x.died ? ` <i title="${esc(t('approx'))}">*</i>` : ''}</p>
      ${noRel ? `<p class="sgx-none">${t('none')}</p>` : ''}
      ${fam ? `<p class="sgx-fam">${fam}</p>` : ''}
      ${bio ? `<p class="sgx-bio"${HE() && !x.bio_he ? ' lang="en" dir="ltr"' : ''}>${bioHTML(bio)}</p>` : ''}
      ${x.stories && x.stories.length ? `<h4>${t('stories')}</h4><ul class="sgx-stories">${x.stories.map(s =>
        `<li><a href="${esc(S.o.link ? S.o.link(S.o.corpus, s.tractate, s.place) : '#')}">${esc(HE() && s.title_he ? s.title_he : s.title)}</a> <span>${esc(s.ref || '')}</span></li>`).join('')}</ul>` : ''}
      ${n ? `<h4>${t(S.o.corpus === 'mishnah' ? 'quotedM' : 'quotedB', n.toLocaleString())}${x.estimated_count ? ` <i title="${esc(t('est'))}">~</i>` : ''}</h4>
      <p class="sgx-where">${top.map(([tr, c]) => `<button type="button" data-tr="${esc(tr)}">${esc(name(tr))} <b>${c}</b></button>`).join('')}
      ${Object.keys(q).length > 5 ? `<button type="button" data-tr="*" class="all">${t('allT')}</button>` : ''}</p><div class="sgx-places"></div>` : ''}
      <p class="sgx-links"><a href="https://www.sefaria.org${HE() ? '.il' : ''}/topics/${encodeURIComponent(x.sefaria)}" target="_blank" rel="noopener">${t('sefaria')}</a>
      ${x.wiki_he ? `<a href="${esc(x.wiki_he)}" target="_blank" rel="noopener">${t('wiki')}</a>` : ''}</p>`;
  }
  async function showPlaces(tr) {
    const x = sage(S.cur), host = S.box.querySelector('.sgx-places'), name = S.o.tractateName || (s => s);
    if (tr === '*') {
      const q = (x.quoted || {})[S.o.corpus] || {};
      host.innerHTML = `<p class="sgx-where">${Object.entries(q).sort(byTractate).map(([k, c]) => `<button type="button" data-tr="${esc(k)}">${esc(name(k))} <b>${c}</b></button>`).join('')}</p>`;
      return;
    }
    host.textContent = t('loading');
    await loadQuoted();
    const places = (((S.quoted[S.cur] || {})[S.o.corpus] || {})[tr] || '').split(' ').filter(Boolean);
    const uniq = [...new Set(places)];
    host.innerHTML = `<p class="sgx-placelist"><b>${esc(name(tr))}:</b> ${uniq.map(p =>
      `<a href="${esc(S.o.link ? S.o.link(S.o.corpus, tr, p) : '#')}">${esc(p)}</a>`).join(' ')}</p>`;
  }


  // ---------- the Shas-wide chart ----------
  // Generations across (Zugot, tanna'im 1-6 and the transition, amora'im 1-8, then "unknown"),
  // Eretz Yisrael above and Bavel below. A cell shows its most quoted sages; "+N more" opens the
  // rest of the major ones and the next tier. Anyone at all is reached by search, which opens
  // the cell and marks the name. A name opens the relationship box.
  const C = { open: new Set(), show: new Set(), filter: 'all', host: null, hit: null };
  const CW = {
    en: { chart: 'Sages of the Talmud', search: 'Find a sage', all: 'All', tannaim: "Tanna'im", amoraim: "Amora'im",
          zugot: 'Zugot', unknown: 'Generation unknown', ey: 'Eretz Yisrael', bavel: 'Bavel', trans: 'Transition',
          more: '+{0} more', fewer: 'Fewer', nohit: 'No sage by that name.', moved: 'Moved between Bavel and Eretz Yisrael',
          chartM: 'Sages of the Mishnah', tipM: 'Tap a name to see his teachers and students.',
          sources: 'Sources: Sefaria (names, generations, bios) and Hebrew Wikipedia (family, teachers and students).',
          tip: 'In each box: the most quoted sages, A–Z (“more” adds the rest). Tap a name to see his teachers, students and colleagues.' },
    he: { chart: 'חכמי התלמוד', search: 'חיפוש חכם', all: 'הכול', tannaim: 'תנאים', amoraim: 'אמוראים',
          zugot: 'זוגות', unknown: 'דור לא ידוע', ey: 'ארץ ישראל', bavel: 'בבל', trans: 'מעבר',
          more: 'ועוד {0}', fewer: 'פחות', nohit: 'לא נמצא חכם בשם הזה.', moved: 'עבר בין בבל לארץ ישראל',
          chartM: 'חכמי המשנה', tipM: 'לחיצה על שם מציגה את רבותיו ותלמידיו.',
          sources: 'מקורות: ספריא (שמות, דורות, תולדות) וויקיפדיה העברית (משפחה, רבותיו ותלמידיו).',
          tip: 'בכל תא: החכמים המצוטטים ביותר, לפי א״ב (״עוד״ מוסיף את השאר). לחיצה על שם מציגה את רבותיו, תלמידיו ובני דורו.' },
  };
  const ct = (k, ...a) => (CW[S.o.lang] || CW.en)[k].replace(/\{(\d)\}/g, (_, i) => a[i]);
  // clay (Mishnah): only the sages the Mishnah names, and only the Zugot and the tanna'im
  const simple = () => !!S.o.clay;
  const inChart = x => ['tanna', 'amora', 'zug'].includes(x.kind) && !(simple() && (x.kind === 'amora' || (x.kind !== 'zug' && !countOf(x))));   // the Zugot all stand in the Mishnah (Avot 1, Eduyot, Chagigah 2:2), but their bare names (Hillel, Shammai) are not matched by the name counter, so their count is 0
  const COLS = ['Z', 'T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'TA', 'A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8', '?'];
  function colOf(x) {
    if (x.kind === 'zug') return 'Z';
    let c = (x.gen_code || '').split('/')[0];
    if (!c && x.gen != null) c = (x.kind === 'tanna' ? 'T' : 'A') + x.gen;
    if (c === 'T0') c = 'TA';
    return COLS.includes(c) ? c : '?';
  }
  const rowOf = x => x.kind === 'amora' && (x.region || '').startsWith('Bavel') ? 1 : 0;
  // the tanna'im and the Zugot were all in Eretz Yisrael: their columns are one tall cell
  const tall = c => /^[ZT]/.test(c);
  function colHead(c) {
    if (c === 'Z') return [ct('zugot'), yearsOf(['Z1', 'Z5'])];
    if (c === '?') return [ct('unknown'), ''];
    if (c === 'TA') return [ct('trans'), yearsOf(['TA'])];
    const n = +c.slice(1);
    return [HE() ? (c[0] === 'T' ? 'תנאים' : 'אמוראים') + ' ' + HE_ORD[n] : (c[0] === 'T' ? 'Tanna’im ' : 'Amora’im ') + n, yearsOf([c])];
  }
  function yearsOf(codes) {
    const g = S.data.gen_years, ys = codes.map(c => g[c]).filter(Boolean);
    if (!ys.length) return '';
    const a = Math.min(...ys.map(y => y[0])), b = Math.max(...ys.map(y => y[1]));
    const f = y => y < 0 ? `${-y}` : `${y}`;
    return a < 0 && b <= 0 ? `${f(a)}–${f(b)} ${t('bce')}` : a < 0 ? `${f(a)} ${t('bce')}–${b}` : `${a}–${b}`;
  }
  function cells() {
    const by = {};
    for (const [id, x] of Object.entries(S.data.sages)) {
      if (!inChart(x)) continue;
      const k = rowOf(x) + ':' + colOf(x);
      (by[k] = by[k] || []).push(id);
    }
    for (const k in by) by[k].sort((a, b) => k.endsWith(':Z') ? (sage(a).gen ?? 9) - (sage(b).gen ?? 9)   // the pairs in order
      : tierOf(sage(a)) - tierOf(sage(b)) || countOf(sage(b)) - countOf(sage(a)));
    return by;
  }
  // A–Z by the name itself, not the title: Rabbi Akiva under A, Rav Pappa under P
  const sortKey = x => HE() ? (x.he || '').replace(/^(?:רבי|רבן|רב|מר|ר')\s+/, '')
    : shortName(x).replace(/^(?:Rabbi|Rebbi|Rabban|Rav|Mar|R\.)\s+/, '').replace(/^\[|\]/g, '');
  const byName = (a, b) => sortKey(sage(a)).localeCompare(sortKey(sage(b)), HE() ? 'he' : 'en');
  function chartHTML() {
    const phone = (C.host.clientWidth || 800) < 560, first = simple() ? 5 : 6, by = cells();   // six on a phone too (author)
    const cols = COLS.filter(c => simple() ? /^(Z|T[1-6]|TA)$/.test(c) && (by['0:' + c] || []).length > 0 : false || C.filter === 'all' || (C.filter === 'tanna' ? /^[ZT]/.test(c) || c === '?' : /^A/.test(c) || c === '?'));
    const rows = simple() ? [ct('ey')] : [ct('ey'), ct('bavel')];
    // each cell's list: its most quoted (by Bavli or Mishnah count), then A–Z; opened, all of them A–Z.
    // The Zugot keep their historical order.
    const cell = {};
    rows.forEach((_, row) => cols.forEach(c => {
      if (row === 1 && tall(c)) return;
      const k = row + ':' + c, ids = (by[k] || []).filter(id => C.filter === 'all' || (C.filter === 'tanna' ? sage(id).kind !== 'amora' : sage(id).kind === 'amora'));
      const open = S.o.chartAllOpen ? !C.open.has(k) : C.open.has(k);   // with "show every sage", a click closes
      const major = simple() || c === 'Z' ? ids : ids.filter(id => tierOf(sage(id)) <= 2);
      const lim = c === 'Z' ? 12 : first;   // the ten Zugot are few: all of them, Hillel and Shammai included
      const pick = open || major.length <= lim + 1 ? major : major.slice(0, lim);
      const shown = c === 'Z' ? pick : [...pick].sort(byName);
      const extra = ids.filter(id => C.show.has(id) && !shown.includes(id));
      cell[k] = { open, major, shown, list: shown.concat(extra) };
    }));
    // a long list continues in a second column, and its generation's column widens for it
    const LONG = 12, wide = c => !phone && rows.some((_, row) => (cell[row + ':' + c]?.list.length || 0) > LONG);
    const w = phone ? 104 : 132;
    let h = `<div class="sgc-grid" style="grid-template-columns:${simple() ? '' : 'auto '}${cols.map(c => `minmax(${wide(c) ? 2 * w : w}px,${wide(c) ? 2 : 1}fr)`).join(' ')}">`;
    h += (simple() ? '' : `<div class="sgc-corner"></div>`) + cols.map(c => { const [a, b] = colHead(c);
      return `<div class="sgc-h${c[0] === 'A' ? ' am' : c === '?' ? ' unk' : ''}"><b>${esc(a)}</b>${b ? `<small>${esc(b)}</small>` : ''}</div>`; }).join('');
    rows.forEach((label, row) => {
      if (!simple()) h += `<div class="sgc-rh">${esc(label)}</div>`;
      for (const c of cols) {
        if (row === 1 && tall(c)) continue;
        const k = row + ':' + c, { open, major, shown, list } = cell[k];
        const more = major.length - shown.length, two = !phone && list.length > LONG;
        h += `<div class="sgc-cell${row === 0 && tall(c) ? ' tall' : ''}${two ? ' two' : ''}" data-k="${k}"${two ? ` style="--rows:${Math.ceil(list.length / 2)};--last:${Math.ceil(list.length / 2) + 1}"` : ''}>${list.map(id => { const x = sage(id);
          return `<button type="button" class="sgc-c g-${group(x)} t${tierOf(x)}${(x.region || '').includes('/') ? ' moved' : ''}${C.hit === id ? ' hit' : ''}" data-go="${esc(id)}" title="${esc(fullName(x))} · ${esc(meta(x))}">${esc(shortName(x))}</button>`; }).join('')}
          ${more > 0 ? `<button type="button" class="sgc-more" data-cell="${k}">${ct('more', more)}</button>` : open && major.length > first + 1 ? `<button type="button" class="sgc-more" data-cell="${k}">${ct('fewer')}</button>` : ''}</div>`;
      }
    });
    return h + '</div>';
  }
  function chartDraw() { C.host.querySelector('.sgc-body').innerHTML = chartHTML(); }
  function norm(s) { return String(s || '').toLowerCase().replace(/[֑-ׇ]/g, '').replace(/[^a-zא-ת ]/g, '').replace(/\s+/g, ' ').trim(); }
  function find(q) {
    q = norm(q); if (q.length < 2) return [];
    const out = [];
    for (const [id, x] of Object.entries(S.data.sages)) {
      if (!inChart(x)) continue;
      const names = [x.en, x.he, ...(x.alt_en || []), ...(x.alt_he || [])].map(norm);
      const exact = names.some(n => n === q), start = names.some(n => n.startsWith(q) || n.split(' ').some(w => w.startsWith(q)));
      if (exact || start || names.some(n => n.includes(q))) out.push([exact ? 0 : start ? 1 : 2, tierOf(x), -countOf(x), id]);
    }
    return out.sort((a, b) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2]).slice(0, 12).map(r => r[3]);
  }
  function reveal(id) {
    const x = sage(id), k = rowOf(x) + ':' + colOf(x);
    C.show.add(id); C.hit = id;
    if (C.filter !== 'all' && (C.filter === 'tanna') === (x.kind === 'amora')) { C.filter = 'all'; syncFilter(); }
    chartDraw();
    // On a phone the keyboard closes after a pick, which resizes the page and redraws the chart; a
    // smooth scroll would be cut off part way. So jump there, and again once the keyboard is gone.
    C.host.querySelector('input')?.blur();
    centreHit();
    setTimeout(centreHit, 450);
  }
  function centreHit() {
    const b = C.hit && C.host.querySelector(`.sgc-c[data-go="${CSS.escape(C.hit)}"]`);
    if (!b) return;
    const box = C.host.querySelector('.sgc-body'), bb = box.getBoundingClientRect(), r = b.getBoundingClientRect();
    box.scrollLeft += (r.left + r.width / 2) - (bb.left + bb.width / 2);
    box.scrollTop += (r.top + r.height / 2) - (bb.top + bb.height / 2);
    b.focus({ preventScroll: true });
  }
  function syncFilter() { C.host.querySelectorAll('.sgc-filter button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.f === C.filter))); }
  async function chart(el) {
    C.host = el;
    el.classList.add('sgc');
    if (HE()) el.dir = 'rtl';
    el.innerHTML = `<div class="sgc-tools"><div class="sgc-find"><input type="search" placeholder="${ct('search')}" aria-label="${ct('search')}"><div class="sgc-res" hidden></div></div>
      <div class="sgc-filter" role="group"${simple() ? ' hidden' : ''}><button type="button" data-f="all" aria-pressed="true">${ct('all')}</button><button type="button" data-f="tanna">${ct('tannaim')}</button><button type="button" data-f="amora">${ct('amoraim')}</button></div></div>
      <p class="sgc-tip">${ct(simple() ? 'tipM' : 'tip')} <span class="sgc-key"${simple() ? ' hidden' : ''}><i class="sw zug"></i>${t('keyZ')} <i class="sw tanna"></i>${t('keyTa')} <i class="sw ey"></i>${t('keyEY')} <i class="sw bavel"></i>${t('keyBV')} <i class="mv"></i>${ct('moved')}</span></p>
      <div class="sgc-body">${t('loading')}</div>
      <p class="sgc-credit">${ct('sources')}${S.o.credit ? ' · ' + S.o.credit : ''}</p>`;
    await load();
    chartDraw();
    const inp = el.querySelector('input'), res = el.querySelector('.sgc-res');
    inp.addEventListener('input', () => {
      const hits = find(inp.value);
      res.hidden = !inp.value.trim();
      res.innerHTML = hits.length ? hits.map(id => { const x = sage(id);
        return `<button type="button" data-pick="${esc(id)}"><b>${esc(fullName(x))}</b> <span>${esc(HE() ? x.en : x.he)}</span><small>${esc(meta(x))}</small></button>`; }).join('')
        : `<p>${ct('nohit')}</p>`;
    });
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') { const f = res.querySelector('[data-pick]'); if (f) f.click(); } if (e.key === 'Escape') { res.hidden = true; } });
    el.addEventListener('click', e => {
      const p = e.target.closest('[data-pick]');
      if (p) { res.hidden = true; inp.value = fullName(sage(p.dataset.pick)); reveal(p.dataset.pick); return; }
      const m = e.target.closest('[data-cell]');
      if (m) { const k = m.dataset.cell; C.open.has(k) ? C.open.delete(k) : C.open.add(k); chartDraw(); return; }
      const f = e.target.closest('[data-f]');
      if (f) { C.filter = f.dataset.f; syncFilter(); chartDraw(); return; }
      const g = e.target.closest('.sgc-c[data-go]');
      if (g) { C.hit = g.dataset.go; el.querySelectorAll('.sgc-c.hit').forEach(b => b.classList.remove('hit')); g.classList.add('hit'); open(g.dataset.go); }
    });
    // Move the chart by dragging it with the mouse, or with the arrow keys (Page Up / Down, Home / End
    // too). A drag that moves more than a few pixels does not count as a click on a name.
    const body = el.querySelector('.sgc-body');
    body.tabIndex = 0;
    let drag = null, dragged = false;
    body.addEventListener('pointerdown', e => {
      if (e.pointerType !== 'mouse' || e.button !== 0) return;
      drag = { x: e.clientX, y: e.clientY, l: body.scrollLeft, t: body.scrollTop }; dragged = false;
    });
    window.addEventListener('pointermove', e => {
      if (!drag) return;
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (!dragged && Math.hypot(dx, dy) < 5) return;
      if (!dragged) { dragged = true; body.classList.add('dragging'); }
      body.scrollLeft = drag.l - dx; body.scrollTop = drag.t - dy;
    });
    window.addEventListener('pointerup', () => { if (drag) { drag = null; body.classList.remove('dragging'); } });
    body.addEventListener('click', e => { if (dragged) { e.stopPropagation(); e.preventDefault(); dragged = false; } }, true);
    const keyMove = e => {
      if (!el.isConnected || el.closest('[hidden]') || e.target.closest?.('input,textarea,select')) return;
      if (S.box && !S.box.hidden) return;
      const st = 80, pg = body.clientHeight * 0.85, rtl = getComputedStyle(body).direction === 'rtl' ? -1 : 1;
      const mv = { ArrowLeft: [-st * rtl, 0], ArrowRight: [st * rtl, 0], ArrowUp: [0, -st], ArrowDown: [0, st],
                   PageUp: [0, -pg], PageDown: [0, pg] }[e.key];
      if (mv) { body.scrollBy({ left: mv[0], top: mv[1] }); e.preventDefault(); e.stopPropagation(); return; }
      if (e.key === 'Home' || e.key === 'End') { body.scrollTo({ top: e.key === 'Home' ? 0 : body.scrollHeight }); e.preventDefault(); e.stopPropagation(); }
    };
    document.addEventListener('keydown', keyMove, true);   // before the page's own arrow keys (next daf)
    // redraw on a real change of width only (not the phone keyboard opening or closing), keeping
    // the marked sage in view
    let rt, lastW = el.clientWidth;
    window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => {
      if (!C.host || C.host.clientWidth === lastW) return;
      lastW = C.host.clientWidth; chartDraw(); centreHit(); }, 150); });
  }
  let chartBox = null;
  function openChart() {
    if (!chartBox) {
      chartBox = document.createElement('div');
      chartBox.className = 'sgc-wrap'; chartBox.setAttribute('role', 'dialog'); chartBox.setAttribute('aria-label', ct('chart'));
      chartBox.innerHTML = `<header class="sgx-bar"><h2>${ct(simple() ? 'chartM' : 'chart')}</h2><span style="flex:1"></span><button type="button" class="sgx-x" aria-label="${t('close')}">×</button></header><div class="sgc-in"></div>`;
      if (HE()) chartBox.dir = 'rtl';
      document.body.appendChild(chartBox);
      chartBox.querySelector('.sgx-x').onclick = () => { chartBox.hidden = true; };
      chartBox.addEventListener('keydown', e => { if (e.key === 'Escape' && (!S.box || S.box.hidden)) chartBox.hidden = true; });
      chart(chartBox.querySelector('.sgc-in'));
    }
    chartBox.hidden = false;
    setTimeout(() => chartBox.querySelector('input')?.focus(), 50);
  }

  window.AnySages = {
    init(o) { Object.assign(S.o, o || {}); },
    open,
    close,
    // the chart opens with every sage listed (a host setting), redrawn if it is on screen
    setChartAllOpen(v) { S.o.chartAllOpen = !!v; C.open.clear(); if (C.host && S.data) chartDraw(); },
    chart,          // render the Shas-wide chart into an element (a page of its own)
    openChart,      // or open it over the page
    // for hosts that want the data (search, the timeline later)
    data: async () => { await load(); return S.data; },
  };
})();
