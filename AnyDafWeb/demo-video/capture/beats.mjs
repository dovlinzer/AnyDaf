// Calm takes: one short clip per feature ("beat"), recorded at an unhurried pace and meant to play at about 1x.
// Every edit (90 s, 60 s, 30 s...) is built from these. Each clip saves its click times (<clip>.marks.json)
// and where the camera should look (<clip>.cam.json).
//   node capture/beats.mjs                 all beats
//   node capture/beats.mjs chart quiz      just these
import * as L from "./lib.mjs";

const DAF = "#Bava_Metzia/3/Example";
const head = (id) => `#outline .ado-node[data-id="${id}"] > .ado-head`;
const fold = (id) => `${head(id)} .ado-fold`;
const node = (id) => `#outline .ado-node[data-id="${id}"]`;
const OUT = [0, 60, 940, 840];   // the outline column, roughly
const C = { ms: 1000, pause: 250 };   // a calm click

async function drag(s, from, to) {
  await L.glide(s, from, 900); await L.sleep(250);
  await s.page.mouse.down(); await L.sleep(150);
  await L.glide(s, to, 1300); await L.sleep(150);
  await s.page.mouse.up(); await L.sleep(900);
}

const BEATS = {
  // a section opens to its summary, its steps and an insight from the shiur
  async outline(s) {
    const p = s.page;
    await L.record(s, "C_outline", async () => {
      await L.focus(s, OUT); await L.sleep(1500);
      await L.focus(s, head("s1"), { pad: 60 });
      await L.click(s, p.locator(fold("s1")), C);
      await L.sleep(500); await L.focus(s, node("s1"), { pad: 20 });
      await L.sleep(2100);
      await L.glide(s, [420, 600], 1300); await L.sleep(2100);
    });
  },
  // the daf summary at the end, and a link back to its section
  async summary(s) {
    const p = s.page;
    await L.record(s, "C_summary", async () => {
      await L.focus(s, OUT); await L.sleep(1000);
      await L.click(s, p.locator("#outHead [data-sum]"), C);
      await L.sleep(1200); await L.focus(s, "#outline .ado-sum", { pad: 20 });
      await L.sleep(2400);
      const link = p.locator('.ado-sgo[data-goto="s4"]').first();
      await L.glide(s, link, 1200); await L.sleep(600);
      await L.click(s, link, { ms: 300, pause: 200 });
      await L.sleep(900); await L.focus(s, node("s4"), { pad: 20 });
      await L.sleep(2100);
    });
  },
  // a chart: the cases side by side, an icon for each ruling, and the key
  async chart(s) {
    const p = s.page, ch = `${node("s2")} .ado-chartw`;
    await p.evaluate(() => view.open("s2"));
    await L.scrollToEl(s, "#outPane", ch, 0.08, 10); await L.sleep(800);
    await L.record(s, "C_chart", async () => {
      await L.focus(s, ch, { pad: 30 }); await L.sleep(1200);
      await L.glide(s, [180, 300], 1000); await L.sleep(900);
      await L.glide(s, [520, 300], 2000); await L.sleep(900);    // across a row
      await L.glide(s, [560, 470], 1600); await L.sleep(1000);   // down the ruling column
      await L.glide(s, [200, 520], 1200); await L.sleep(1800);   // the key
    });
  },
  // an illustration: the case, then each opinion's ruling
  async illustration(s) {
    const p = s.page, ill = `${node("s3")} .ado-ill`;
    await p.evaluate(() => view.open("s3"));
    await L.scrollToEl(s, "#outPane", ill, 0.05, 10); await L.sleep(800);
    await L.record(s, "C_illustration", async () => {
      await L.focus(s, ill, { pad: 20 }); await L.sleep(1400);
      await L.glide(s, [330, 280], 1200); await L.sleep(1800);   // the case
      await L.glide(s, [400, 450], 1200); await L.sleep(2200);   // the rulings
    });
  },
  // a key term's definition, then a measure on the scale of weights and coins
  async reference(s) {
    const p = s.page, t = p.locator(`${node("s2")} .ado-term`).first();
    const mid = await p.evaluate(() => { const m = document.querySelector("#outline .mu"); const n = m && m.closest(".ado-node"); return n ? n.dataset.id : null; });
    await p.evaluate((mid) => { view.open("s2"); if (mid) view.open(mid); }, mid);
    await L.scrollToEl(s, "#outPane", head("s2"), 0.02, 10); await L.sleep(800);
    await L.record(s, "C_reference", async () => {
      await L.focus(s, t, { pad: 160 }); await L.sleep(500);
      await L.click(s, t, C);
      await L.sleep(500); await L.focus(s, "#gwin", { pad: 20 });
      await L.sleep(2100);
      await L.click(s, p.locator("#gwinClose"), { ms: 700 });
      await L.scrollToEl(s, "#outPane", "#outline .mu", 0.45, 900);
      const mu = p.locator("#outline .mu").first();
      await L.focus(s, mu, { pad: 160 });
      await L.click(s, mu, C);
      await L.sleep(600); await L.focus(s, ".mpop", { pad: 20 });
      await L.sleep(1200);
      await L.click(s, p.locator('.mpop g[data-k="sela"]').first(), C);
      await L.sleep(1900);
    });
  },
  // a sage: his card, his teachers and students, and the diagram re-centring on one of them
  async sages(s) {
    const p = s.page, sg = p.locator(`${node("s2")} .ado-sage`).first();
    await p.evaluate(() => view.open("s2"));
    await L.scrollToEl(s, "#outPane", head("s2"), 0.02, 10); await L.sleep(800);
    await L.record(s, "C_sages", async () => {
      await L.focus(s, sg, { pad: 160 }); await L.sleep(900);
      await L.click(s, sg, C);
      await L.sleep(700); await L.focus(s, "#swin", { pad: 20 });
      await L.sleep(1900);
      await L.click(s, p.locator('.relbtn[data-rel="rabbi-yose-b-chalafta"]'), C);
      await L.sleep(800); await L.focus(s, ".sgx", { pad: 10 });
      await L.sleep(1900);
      await L.click(s, p.locator('.sgx-n[data-go="rabbi-akiva"]').first(), C);
      await L.sleep(2900);
    });
  },
  // a quiz question, its reason, and its place on the daf
  async quiz(s) {
    const p = s.page;
    await L.record(s, "C_quiz", async () => {
      await L.focus(s, [0, 0, 1600, 900], { fmt: "wide" }); await L.focus(s, "#practiceBtn", { pad: 200, fmt: "tall" }); await L.sleep(800);
      await L.click(s, p.locator("#practiceBtn"), C);
      await L.sleep(1000); await L.focus(s, "#pwin", { pad: 10 });
      await L.click(s, p.locator('#pgames [data-g="quiz"]'), C);
      await L.sleep(2100);
      await L.click(s, p.locator('#pgames .adg-opt[data-k="0"]'), C);
      await L.sleep(2700);
      const b = p.locator("#pgames .adg-after [data-daf]");
      await L.click(s, b, C);
      await L.sleep(900); await L.focus(s, [0, 0, 1600, 900], { fmt: "wide" });
      await L.sleep(400); await L.focus(s, "#gem", { fmt: "tall" });
      await L.sleep(2400);
    });
  },
  // fill in the chart: drag a few cards into place
  async fillchart(s) {
    const p = s.page;
    await p.locator("#practiceBtn").click(); await L.sleep(800);
    await p.locator('#pgames [data-g="chart"]').click(); await L.sleep(1500);
    const plan = await p.evaluate(() => {
      const strip = (t) => String(t).replace(/\*+/g, "").replace(/\s+/g, " ").trim();
      const cap = document.querySelector("#pgames .adg-cap").textContent.trim();
      const all = []; (function walk(ns) { (ns || []).forEach((n) => { (n.charts || (n.chart ? [n.chart] : [])).forEach((c) => all.push(c)); walk(n.children || n.sections); }); })(D.outline.sections);
      const c = all.find((x) => cap.startsWith(strip(x.caption).slice(0, 30))) || all[0];
      const cards = [...document.querySelectorAll("#pgames .adg-card")], used = new Set();
      return [...document.querySelectorAll("#pgames .slot")].map((sl) => {
        const want = strip(c.rows[+sl.dataset.r][+sl.dataset.c]);
        const k = cards.find((x) => !used.has(x) && (strip(x.textContent) === want || strip(x.textContent).startsWith(want.slice(0, 18))));
        if (k) used.add(k);
        return { r: sl.dataset.r, c: sl.dataset.c, i: k ? k.dataset.i : null };
      }).filter((x) => x.i != null);
    });
    await L.record(s, "C_fillchart", async () => {
      await L.focus(s, "#pwin", { pad: 10 }); await L.sleep(1500);
      for (const x of plan.slice(0, 3)) await drag(s, p.locator(`#pgames .adg-card[data-i="${x.i}"]`), p.locator(`#pgames .slot[data-r="${x.r}"][data-c="${x.c}"]`));
      await L.sleep(1600);
    });
  },
  // tap a section: the Gemara moves to it; then Hebrew, English or both
  async textsync(s) {
    const p = s.page;
    await L.record(s, "C_textsync", async () => {
      await L.focus(s, [0, 0, 1600, 900], { fmt: "wide" }); await L.focus(s, head("s2"), { pad: 120, fmt: "tall" }); await L.sleep(900);
      await L.click(s, p.locator(`${head("s2")} .ado-t`), C);
      await L.sleep(500); await L.focus(s, "#gem", { fmt: "tall" });
      await L.sleep(1800);
      await L.click(s, p.locator('#langSeg button[data-l="he"]'), C); await L.sleep(1600);
      await L.click(s, p.locator('#langSeg button[data-l="both"]'), C); await L.sleep(1900);
    });
  },
  // tap a line of Gemara: the outline moves to it
  async linesync(s) {
    const p = s.page;
    const gem = await p.evaluate(() => { const s = secs.find((x) => x.id === "s15"); return D.items.map((it) => it.l).filter((l) => D.order[l] >= s.a && D.order[l] <= s.b)[1]; });
    await L.record(s, "C_linesync", async () => {
      const item = p.locator(`#text .item:has(.lab:text-is("${gem}"))`);
      await L.focus(s, [0, 0, 1600, 900], { fmt: "wide" }); await L.focus(s, item, { pad: 40, fmt: "tall" }); await L.sleep(900);
      await L.click(s, item.locator(".he"), C);
      await L.sleep(900); await L.focus(s, head(await p.evaluate(() => current)), { pad: 200, fmt: "tall" });
      await L.sleep(2200);
    });
  },
  // the daf page: tap a line and the outline follows; the Rambam in the margin opens in place
  async dafpage(s) {
    const p = s.page;
    await p.locator('#paneSeg button[data-p="page"]').click(); await L.sleep(2500);
    const tap = await p.evaluate(() => {
      const L = layOf(amudShown), cur = secs.find((x) => x.id === current);
      const ls = Object.keys(L.g).filter((l) => { const o = D.order[l]; return o != null && !(o >= cur.a && o <= cur.b); });
      return ls.map((l) => [l, Math.abs(L.g[l][0][1] - 0.4)]).sort((a, b) => a[1] - b[1])[0][0];
    });
    await L.record(s, "C_dafpage", async () => {
      const r = p.locator(`#pageLay rect.g[data-l="${tap}"]`).first();
      await L.focus(s, [0, 0, 1600, 900], { fmt: "wide" }); await L.focus(s, "#gem", { fmt: "tall" }); await L.sleep(1000);
      await L.click(s, r, C);
      await L.sleep(900); await L.focus(s, head(await p.evaluate(() => current)), { pad: 200, fmt: "tall" });
      await L.sleep(1900);
      const rm = p.locator("#pageImg a[data-ref^='Mishneh Torah']").first();
      await L.focus(s, "#gem", { fmt: "tall" });
      await L.click(s, rm, C);
      await L.sleep(700); await L.focus(s, "dialog.xsrc[open]", { pad: 20 });
      await L.sleep(2400);
    });
  },
  // a word on the daf: its meaning and its dictionary entry (Hullin 88a)
  async words(s) {
    const p = s.page;
    await L.load(s, "#Hullin/88");
    await p.evaluate(() => { setPane("page"); showAmud("88a"); });
    await L.sleep(3500);
    await L.record(s, "C_words", async () => {
      await L.focus(s, "#gem", { pad: 0 }); await L.sleep(800);
      const r = p.locator('#pageLay rect.g[data-l="88a.10"]').first();
      await L.glide(s, r, 1200); await L.sleep(500);
      await p.mouse.down({ button: "right" }); await L.sleep(60); await p.mouse.up({ button: "right" });
      await L.sleep(1000); await L.focus(s, "dialog.xsrc[open]", { pad: 20 });
      await L.sleep(1400);
      await L.click(s, p.locator(".hw", { hasText: "זֶבֶל" }).first(), C);
      await L.sleep(3400);
    });
  },
};

const want = process.argv.slice(2);
for (const [k, fn] of Object.entries(BEATS)) {
  if (want.length && !want.includes(k)) continue;
  const s = await L.open();
  await L.load(s, DAF);
  console.log(k);
  try { await fn(s); await L.still(s, `C_${k}_end`); } catch (e) { console.log("  FAILED:", e.message.split("\n")[0]); await L.still(s, `C_${k}_fail`); } finally { await s.browser.close(); }
}
