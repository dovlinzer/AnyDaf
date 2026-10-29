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
              open: {}, nodes: new Map(), box: null };
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
          keyT: 'teacher → student', keyC: 'colleagues', keyTa: 'Tanna', keyEY: 'Amora, Eretz Yisrael',
          keyBV: 'Amora, Bavel', keyZ: 'Zugot', est: 'a rough count: the name fits more than one sage' },
    he: { title: 'חכמים', rel: 'קשרים', back: 'חזרה', close: 'סגירה', teachers: 'רבותיו', students: 'תלמידיו',
          colleagues: 'בני דורו', family: 'משפחה', more: 'ועוד {0}', fewer: 'פחות', tanna: 'תנא', amora: 'אמורא',
          zug: 'מן הזוגות', gen: 'דור {0}', trans: 'דור המעבר', ey: 'ארץ ישראל', bavel: 'בבל', about: 'בערך {0}',
          ce: 'לספירה', bce: 'לפנה"ס', born: 'נולד {0}', died: 'נפטר {0}', quotedB: 'נזכר ב־{0} שורות בתלמוד',
          quotedM: 'נזכר ב־{0} משניות', most: 'בעיקר ב:', all: 'כל המקומות', allT: 'כל המסכתות',
          none: 'לא ידוע על רבותיו ותלמידיו.', father: 'אביו', mother: 'אמו', parents: 'הורה', children: 'ילדיו',
          spouse: 'אשתו', in_laws: 'חמיו', sons_in_law: 'חתנו', siblings: 'אחיו', relatives: 'קרוב משפחה',
          stories: 'סיפורים עליו', sefaria: 'ספריא', wiki: 'ויקיפדיה', approx: 'התאריכים משוערים, לפי הדור.',
          loading: 'טוען…', keyT: 'רב ← תלמיד', keyC: 'בני דורו', keyTa: 'תנא', keyEY: 'אמורא, ארץ ישראל',
          keyBV: 'אמורא, בבל', keyZ: 'זוגות', est: 'מספר משוער: השם מתאים ליותר מחכם אחד' },
  };
  const t = (k, ...a) => (W[S.o.lang] || W.en)[k].replace(/\{(\d)\}/g, (_, i) => a[i]);
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const ORD = n => n + (n % 10 === 1 && n !== 11 ? 'st' : n % 10 === 2 && n !== 12 ? 'nd' : n % 10 === 3 && n !== 13 ? 'rd' : 'th');
  const HE_ORD = ['', 'ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שביעי', 'שמיני'];
  const sage = id => S.data.sages[id];
  // "Rabbi Yehudah [b. Il'ai]" -> "Rabbi Yehudah"; on a narrow screen "Rabbi" -> "R."
  let narrow = false;
  const shortName = x => HE() ? x.he || x.en
    : x.en.replace(/\s*\[.*?\]|\s*\(.*?\)/g, '').replace(narrow ? /^Rabbi /u : /^$/, 'R. ').trim();
  const fullName = x => HE() ? x.he || x.en : x.en.replace(/[\[\]]/g, '');
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
  const tierOf = x => S.o.corpus === 'mishnah' ? x.tier_mishnah : x.tier;
  const countOf = x => (x.count || {})[S.o.corpus] || 0;
  // a row's people, most important first; family keeps its relation as a label
  function people(id, rels) {
    const x = sage(id), out = [];
    for (const r of rels)
      for (const l of (x.links[r] || [])) {
        const y = l.id && sage(l.id);
        if (!y && r !== 'family' && !FAMILY.includes(r)) continue;   // a bare name only in the family row
        out.push({ key: (l.id || 'name:' + l.name) + '|' + r, id: y ? l.id : null, name: y ? shortName(y) : l.name,
                   rel: r, x: y });
      }
    out.sort((a, b) => (a.x ? tierOf(a.x) : 4) - (b.x ? tierOf(b.x) : 4) || (b.x ? countOf(b.x) : 0) - (a.x ? countOf(a.x) : 0));
    const seen = new Set();
    return out.filter(p => { const k = p.id || p.name; if (seen.has(k)) return false; seen.add(k); return true; });
  }
  const NOTES = { 'שנוי במחלוקת': 'disputed', 'לפי חלק מהדעות': 'by some accounts', 'לפי המסורת': 'by tradition' };
  const FAMILY = ['father', 'mother', 'parents', 'children', 'spouse', 'in_laws', 'sons_in_law', 'siblings'];

  // ---------- box ----------
  function build() {
    if (S.box) return;
    const b = document.createElement('div');
    b.className = 'sgx'; b.hidden = true; b.setAttribute('role', 'dialog'); b.setAttribute('aria-label', t('rel'));
    b.innerHTML = `<header class="sgx-bar"><h2>${t('rel')}</h2><nav class="sgx-trail" aria-label="${t('back')}"></nav>
      <button type="button" class="sgx-x" aria-label="${t('close')}">×</button></header>
      <div class="sgx-scroll"><div class="sgx-graph"><svg class="sgx-lines" aria-hidden="true"><defs>
      <marker id="sgxArrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs></svg></div>
      <p class="sgx-key"><span><i class="sw tanna"></i>${t('keyTa')}</span><span><i class="sw ey"></i>${t('keyEY')}</span>
      <span><i class="sw bavel"></i>${t('keyBV')}</span><span><i class="sw zug"></i>${t('keyZ')}</span>
      <span><svg width="26" height="10"><line x1="1" y1="5" x2="22" y2="5" stroke="currentColor" stroke-width="1.6" marker-end="url(#sgxArrow)"/></svg>${t('keyT')}</span>
      <span><svg width="26" height="10"><line x1="1" y1="5" x2="25" y2="5" stroke="currentColor" stroke-width="1.6" stroke-dasharray="3 3"/></svg>${t('keyC')}</span></p>
      <div class="sgx-info" aria-live="polite"></div></div>`;
    if (HE()) b.dir = 'rtl';
    document.body.appendChild(b);
    S.box = b;
    b.querySelector('.sgx-x').onclick = close;
    b.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
    b.addEventListener('click', e => {
      const n = e.target.closest('[data-go]');
      if (n) { go(n.dataset.go); return; }
      const m = e.target.closest('[data-more]');
      if (m) { S.open[m.dataset.more] = !S.open[m.dataset.more]; draw(true); return; }
      const tr = e.target.closest('[data-tr]');
      if (tr) { showPlaces(tr.dataset.tr); return; }
      const bk = e.target.closest('[data-back]');
      if (bk) { const i = +bk.dataset.back; const id = S.trail[i]; S.trail = S.trail.slice(0, i); go(id, true); }
    });
    let rt; window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => !b.hidden && draw(false), 120); });
  }
  function close() { if (S.box) S.box.hidden = true; }

  async function open(id) {
    build();
    S.box.hidden = false;
    S.box.querySelector('.sgx-info').textContent = t('loading');
    await load();
    if (!sage(id)) { S.box.querySelector('.sgx-info').textContent = ''; return; }
    S.trail = []; S.cur = null; S.nodes.forEach(n => n.el.remove()); S.nodes.clear();
    go(id);
    S.box.querySelector('.sgx-x').focus({ preventScroll: true });
  }
  function go(id, fromTrail) {
    if (!sage(id) || id === S.cur) return;
    if (S.cur && !fromTrail) S.trail.push(S.cur);
    if (S.trail.length > 8) S.trail = S.trail.slice(-8);
    S.cur = id; S.open = {};
    draw(true); info();
    S.box.querySelector('.sgx-scroll').scrollTo({ top: 0, behavior: 'smooth' });
  }

  // ---------- graph ----------
  function draw(animate) {
    const g = S.box.querySelector('.sgx-graph'), svg = g.querySelector('svg');
    const width = g.clientWidth || 600, phone = width < 560, cap = phone ? 3 : 6, nodeW = phone ? 92 : 124;
    narrow = phone;
    const rtl = HE(), X = x => rtl ? width - x : x;
    const id = S.cur, x = sage(id);
    // a sage linked two ways appears once: teacher, then student, family, colleague
    const used = new Set();
    const row = rels => people(id, rels).filter(p => {
      if (!p.id && !HE()) return false;          // a name we only have in Hebrew stays in the info box
      const k = p.id || p.name; if (used.has(k)) return false; used.add(k); return true; });
    const rows = {};
    rows.teachers = row(['teachers']); rows.students = row(['students']);
    rows.family = row(FAMILY); rows.colleagues = row(['colleagues']);
    const place = [];   // {key, id, name, x, y, cls, label}
    const more = [];    // "+N more" buttons
    let y = 34;
    function band(name, list, perLine, all) {
      if (!list.length) return null;
      const open = all || S.open[name], shown = open ? list : list.slice(0, perLine);
      const extra = list.length - shown.length;
      const lines = [];
      for (let i = 0; i < shown.length; i += perLine) lines.push(shown.slice(i, i + perLine));
      const ys = [];
      lines.forEach((ln, li) => {
        const btn = !all && li === lines.length - 1 && (extra > 0 || (open && list.length > perLine));
        const n = ln.length + (btn ? 1 : 0);
        ln.forEach((p, i) => place.push({ ...p, x: X((i + 1) * width / (n + 1)), y, maxW: width / (n + 1) - 10 }));
        if (btn)
          more.push({ row: name, x: X(n * width / (n + 1)), y, label: extra > 0 ? t('more', extra) : t('fewer') });
        ys.push(y); y += 56;
      });
      return ys;
    }
    const tY = band('teachers', rows.teachers, cap);
    if (tY) y += 34;
    const cY = y;
    place.push({ key: id, id, name: fullName(x), x: width / 2, y: cY, centre: true });
    // colleagues on both sides of the centre, nearest first
    // colleagues on both sides of the centre, nearest first; the rest (opened) wrap onto lines below
    const side = phone ? 1 : 3, cols = rows.colleagues, beside = cols.slice(0, side * 2);
    const cw = phone ? width * 0.36 : Math.min(width * 0.3, nodeW * 1.6), slot = (width / 2 - cw / 2 - 8) / side;
    beside.forEach((p, i) => {
      const dir = i % 2 === 0 ? -1 : 1, k = Math.floor(i / 2);
      place.push({ ...p, x: X(width / 2 + dir * (cw / 2 + 8 + slot * (k + 0.5))), y: cY, maxW: slot - 10 });
    });
    y += phone ? 66 : 58;
    const restC = cols.slice(side * 2);
    if (restC.length) {
      if (S.open.colleagues) band('colleagues_more', restC.map(p => ({ ...p })), cap, true);
      more.push({ row: 'colleagues', x: X(width - slot / 2), y: cY + 32, small: true,
                  label: S.open.colleagues ? t('fewer') : t('more', restC.length) });
    }
    const fY = rows.family.length ? band('family', rows.family, phone ? 3 : 5) : null;
    if (fY) y += 6;
    if (rows.students.length) y += 30;
    const sY = band('students', rows.students, cap);
    g.style.height = (y + (sY ? 4 : 20)) + 'px';
    svg.setAttribute('width', width); svg.setAttribute('height', y + 20);

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
      el.className = `sgx-n g-${group(sx)} t${sx ? tierOf(sx) : 3}${p.centre ? ' centre' : ''}${p.id ? '' : ' plain'}`;
      el.innerHTML = `${esc(p.centre ? fullName(x) : p.name)}${p.rel && FAMILY.includes(p.rel) ? `<small>${esc(t(p.rel))}</small>` : ''}`;
      if (p.centre) el.removeAttribute('data-go'); else if (p.id) el.dataset.go = p.id;
      el.title = sx ? `${fullName(sx)} · ${meta(sx)}` : p.name;
      el.style.maxWidth = (p.centre ? cw : Math.min(nodeW, p.maxW || nodeW)) + 'px';
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
  function lines() {
    const g = S.box.querySelector('.sgx-graph'), svg = g.querySelector('svg'), gb = g.getBoundingClientRect();
    const c = S.nodes.get(S.cur);
    if (!c) return;
    const box = el => { const r = el.getBoundingClientRect(); return { x: r.left - gb.left + r.width / 2, y: r.top - gb.top + r.height / 2, w: r.width / 2, h: r.height / 2 }; };
    const C = box(c.el);
    let out = '';
    for (const [k, n] of S.nodes) {
      if (k === S.cur) continue;
      const P = box(n.el), rel = n.p.rel;
      if (rel === 'teachers') out += `<line x1="${P.x}" y1="${P.y + P.h}" x2="${C.x}" y2="${C.y - C.h - 2}" marker-end="url(#sgxArrow)"/>`;
      else if (rel === 'students') out += `<line x1="${C.x}" y1="${C.y + C.h}" x2="${P.x}" y2="${P.y - P.h - 2}" marker-end="url(#sgxArrow)"/>`;
      else if (rel === 'colleagues') {
        const dir = P.x < C.x ? 1 : -1;
        out += `<line class="dot" x1="${P.x + dir * P.w}" y1="${P.y}" x2="${C.x - dir * C.w}" y2="${C.y}"/>`;
      } else out += `<line class="fam" x1="${C.x}" y1="${C.y + C.h}" x2="${P.x}" y2="${P.y - P.h}"/>`;
    }
    const defs = svg.querySelector('defs').outerHTML;
    svg.innerHTML = defs + out;
  }

  // ---------- info box ----------
  function info() {
    const x = sage(S.cur), box = S.box.querySelector('.sgx-info');
    S.box.querySelector('.sgx-trail').innerHTML = S.trail.map((id, i) =>
      `<button type="button" data-back="${i}">${esc(shortName(sage(id)))}</button>`).join('<span>›</span>');
    const n = countOf(x), q = (x.quoted || {})[S.o.corpus] || {};
    const top = Object.entries(q).slice(0, 5);
    const name = S.o.tractateName || (s => s);
    const fam = FAMILY.filter(r => (x.links[r] || []).length).map(r => `<span><b>${esc(t(r))}:</b> ${x.links[r].map(l => {
      const y = l.id && sage(l.id), nm = y ? shortName(y) : l.name;
      const note = l.note ? (HE() ? l.note : NOTES[l.note] || '') : '';
      return (y ? `<button type="button" data-go="${esc(l.id)}">${esc(nm)}</button>` : `<span lang="he" dir="rtl">${esc(nm)}</span>`)
        + (note ? ` <i>(${esc(note)})</i>` : '');
    }).join(', ')}</span>`).join('');
    const noRel = !['teachers', 'students', 'colleagues'].some(r => (x.links[r] || []).some(l => l.id));
    const bio = HE() && x.bio_he ? x.bio_he : x.bio;
    box.innerHTML = `<h3>${esc(fullName(x))} <span lang="${HE() ? 'en' : 'he'}" dir="${HE() ? 'ltr' : 'rtl'}">${esc(HE() ? x.en : x.he)}</span></h3>
      <p class="sgx-meta">${esc(meta(x))}${x.years && !x.died ? ` <i title="${esc(t('approx'))}">*</i>` : ''}</p>
      ${noRel ? `<p class="sgx-none">${t('none')}</p>` : ''}
      ${fam ? `<p class="sgx-fam">${fam}</p>` : ''}
      ${bio ? `<p class="sgx-bio"${HE() && !x.bio_he ? ' lang="en" dir="ltr"' : ''}>${esc(bio)}</p>` : ''}
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
      host.innerHTML = `<p class="sgx-where">${Object.entries(q).map(([k, c]) => `<button type="button" data-tr="${esc(k)}">${esc(name(k))} <b>${c}</b></button>`).join('')}</p>`;
      return;
    }
    host.textContent = t('loading');
    await loadQuoted();
    const places = (((S.quoted[S.cur] || {})[S.o.corpus] || {})[tr] || '').split(' ').filter(Boolean);
    const uniq = [...new Set(places)];
    host.innerHTML = `<p class="sgx-placelist"><b>${esc(name(tr))}:</b> ${uniq.map(p =>
      `<a href="${esc(S.o.link ? S.o.link(S.o.corpus, tr, p) : '#')}">${esc(p)}</a>`).join(' ')}</p>`;
  }

  window.AnySages = {
    init(o) { Object.assign(S.o, o || {}); },
    open,
    close,
    // for hosts that want the data (search, the timeline later)
    data: async () => { await load(); return S.data; },
  };
})();
