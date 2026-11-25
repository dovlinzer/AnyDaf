// Takes for the 90-second version (Bava Metzia 3, plus Hullin 88a for the word lookups).
//   node capture/scenes90.mjs 1 2 3      (takes to record; all if none given)
import * as L from "./lib.mjs";

const DAF = "#Bava_Metzia/3/Example";
const head = (id) => `#outline .ado-node[data-id="${id}"] > .ado-head`;
const fold = (id) => `${head(id)} .ado-fold`;

// drag a games card onto a slot with an eased glide
async function drag(s, from, to, ms = 900) {
  await L.glide(s, from, 600); await L.sleep(150);
  await s.page.mouse.down(); await L.sleep(120);
  await L.glide(s, to, ms); await L.sleep(120);
  await s.page.mouse.up(); await L.sleep(350);
}

const SCENES = {
  // 1. The outline: a section with its summary, bullets and shiur insight; Open all; the daf summary and a link back
  async s1(s) {
    const p = s.page;
    await L.record(s, "L1_outline", async () => {
      await L.sleep(1400);
      await L.click(s, p.locator(fold("s1")), { ms: 900 });
      await L.sleep(2600);
      await L.glide(s, [420, 600], 700);   // over the shiur insight
      await L.sleep(1600);
      await L.click(s, p.locator(fold("s1")), { ms: 700 });
      await L.sleep(600);
      await L.click(s, p.locator('#outHead [data-foldall="1"]'), { ms: 800 });
      await L.sleep(1200);
      await L.scrollBy(s, "#outPane", 2600, 2600);
      await L.sleep(500);
      await L.scrollBy(s, "#outPane", -2600, 700);
      await L.click(s, p.locator("#outHead [data-sum]"), { ms: 800 });
      await L.sleep(2800);
      await L.click(s, p.locator('.ado-sgo[data-goto="s4"]').first(), { ms: 900 });
      await L.sleep(2800);
    });
  },
  // 2. A chart (icons, key, ruling words), then two illustrations
  async s2(s) {
    const p = s.page;
    await p.evaluate(() => { ["s2", "s3", "s8"].forEach((id) => view.open(id)); });
    await L.scrollToEl(s, "#outPane", `#outline .ado-node[data-id="s2"] .ado-chartw`, 0.08, 10);
    await L.sleep(800);
    await L.record(s, "L2_visuals", async () => {
      await L.glide(s, [180, 300], 700);
      await L.sleep(800);
      await L.glide(s, [500, 300], 1400);   // across a row
      await L.sleep(500);
      await L.glide(s, [560, 470], 1200);   // down the ruling column
      await L.sleep(600);
      await L.glide(s, [200, 520], 900);    // the key
      await L.sleep(1400);
      await L.scrollToEl(s, "#outPane", `#outline .ado-node[data-id="s3"] .ado-ill`, 0.05, 1600);
      await L.glide(s, [330, 280], 800);    // the case band
      await L.sleep(1600);
      await L.glide(s, [400, 450], 900);    // the ruling band
      await L.sleep(1800);
      await L.scrollToEl(s, "#outPane", `#outline .ado-node[data-id="s8"] .ado-ill`, 0.05, 1600);
      await L.glide(s, [420, 380], 900);
      await L.sleep(2600);
    });
  },
  // 3. A key term, the Sages window, the relationships graph re-centring, the family tree, the coin scale
  async s3(s) {
    const p = s.page;
    await p.evaluate(() => { view.open("s2"); view.open("s3"); });
    await L.scrollToEl(s, "#outPane", head("s2"), 0.02, 10);
    await L.sleep(800);
    await L.record(s, "L3_reference", async () => {
      await L.sleep(400);
      await L.click(s, p.locator(`#outline .ado-node[data-id="s2"] .ado-term`).first(), { ms: 800 });
      await L.sleep(2800);
      await L.click(s, p.locator("#gwinClose"), { ms: 600 });
      await L.sleep(300);
      await L.click(s, p.locator(`#outline .ado-node[data-id="s2"] .ado-sage`).first(), { ms: 800 });
      await L.sleep(2400);
      await L.click(s, p.locator('.relbtn[data-rel="rabbi-yose-b-chalafta"]'), { ms: 800 });
      await L.sleep(2200);
      await L.click(s, p.locator('.sgx-n[data-go="rabbi-akiva"]').first(), { ms: 900 });
      await L.sleep(2600);
      await L.click(s, p.locator('.sgx-n[data-go="rabbi-meir"]').first(), { ms: 900 });
      await L.sleep(2600);
      await L.click(s, p.locator('.sgx button[data-view="fam"]'), { ms: 800 });
      await L.sleep(2800);
      await L.click(s, p.locator(".sgx-x"), { ms: 600 });
      await p.evaluate(() => $("swinClose").click());
      await L.sleep(200);
      await L.scrollToEl(s, "#outPane", "#outline .mu", 0.45, 900);
      await L.click(s, p.locator("#outline .mu").first(), { ms: 800 });
      await L.sleep(2000);
      await L.click(s, p.locator('.mpop g[data-k="sela"]').first(), { ms: 800 });
      await L.sleep(2600);
    });
  },
  // 4. Quiz (with Show in the daf), Fill in the chart (one wrong drop), Term match (one miss, two pairs)
  async s4(s) {
    const p = s.page;
    await L.record(s, "L4_games", async () => {
      await L.sleep(400);
      await L.click(s, p.locator("#practiceBtn"), { ms: 800 });
      await L.sleep(1400);
      await L.click(s, p.locator('#pgames [data-g="quiz"]'), { ms: 700 });
      await L.sleep(2200);
      await L.click(s, p.locator('#pgames .adg-opt[data-k="0"]'), { ms: 800 });
      await L.sleep(2200);
      await L.click(s, p.locator("#pgames .adg-after [data-rev]"), { ms: 700 });
      await L.sleep(1800);
      await L.click(s, p.locator("#pgames .adg-after [data-daf]"), { ms: 700 });
      await L.sleep(2800);
      // Fill in the chart
      await L.click(s, p.locator("#pgames .adg-back"), { ms: 700 });
      await L.sleep(500);
      await L.click(s, p.locator('#pgames [data-g="chart"]'), { ms: 700 });
      await L.sleep(1800);
      const plan = await p.evaluate(() => {
        const strip = (t) => String(t).replace(/\*+/g, "").replace(/\s+/g, " ").trim();
        const cap = document.querySelector("#pgames .adg-cap").textContent.trim();
        const all = []; (function walk(ns) { (ns || []).forEach((n) => { (n.charts || (n.chart ? [n.chart] : [])).forEach((c) => all.push(c)); walk(n.children || n.sections); }); })(D.outline.sections);
        const c = all.find((x) => cap.startsWith(strip(x.caption).slice(0, 30))) || all[0];
        const cards = [...document.querySelectorAll("#pgames .adg-card")];
        const used = new Set();
        return [...document.querySelectorAll("#pgames .slot")].map((sl) => {
          const want = strip(c.rows[+sl.dataset.r][+sl.dataset.c]);
          const k = cards.find((x) => !used.has(x) && (strip(x.textContent) === want || strip(x.textContent).startsWith(want.slice(0, 18))));
          if (k) used.add(k);
          return { r: sl.dataset.r, c: sl.dataset.c, i: k ? k.dataset.i : null };
        });
      });
      console.log("  chart plan:", plan.filter((x) => x.i == null).length, "unmatched of", plan.length);
      const ok = plan.filter((x) => x.i != null);
      const slot = (x) => p.locator(`#pgames .slot[data-r="${x.r}"][data-c="${x.c}"]`);
      const card = (x) => p.locator(`#pgames .adg-card[data-i="${x.i}"]`);
      // one wrong drop: the first card onto the second's slot
      if (ok.length > 1) await drag(s, card(ok[0]), slot(ok[1]));
      await L.sleep(500);
      for (const x of ok.slice(0, 5)) await drag(s, card(x), slot(x), 700);
      await L.sleep(1200);
      // Term match
      await L.click(s, p.locator("#pgames .adg-back"), { ms: 700 });
      await L.sleep(500);
      await L.click(s, p.locator('#pgames [data-g="match"]'), { ms: 700 });
      await L.sleep(1400);
      const pairs = await p.evaluate(() => {
        const strip = (t) => String(t).replace(/\*+/g, "").replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
        const kt = D.keyTerms || [];
        const cs = [...document.querySelectorAll("#pgames .adg-flip")];
        const tcards = cs.filter((b) => b.classList.contains("term")), senses = cs.filter((b) => b.classList.contains("sense"));
        return tcards.map((t) => {
          const name = t.querySelector(".front b").textContent.trim(), k = kt.find((x) => x.term === name);
          const want = k ? strip(k.sense || String(k.definition).split(/(?<=[.!?])\s/)[0]) : "";
          const sn = senses.find((x) => strip(x.querySelector(".front").textContent) === want);
          return [t.dataset.n, sn ? sn.dataset.n : null];
        }).filter((x) => x[1] != null);
      });
      console.log("  match pairs:", pairs.length);
      const flip = (n) => p.locator(`#pgames .adg-flip[data-n="${n}"]`);
      if (pairs.length >= 3) {
        await L.click(s, flip(pairs[0][0]), { ms: 600 }); await L.sleep(500);
        await L.click(s, flip(pairs[1][1]), { ms: 600 }); await L.sleep(2700);   // a miss: they turn back
      }
      for (const [a, b] of pairs.slice(0, 3)) { await L.click(s, flip(a), { ms: 600 }); await L.sleep(450); await L.click(s, flip(b), { ms: 600 }); await L.sleep(1300); }
      await L.sleep(1200);
    });
  },
  // 5. Outline and Talmud: section -> Gemara, the language switch, a line -> outline, a Shas source, the daf page
  async s5(s) {
    const p = s.page;
    const at = await p.evaluate(() => {
      const sec = (id) => secs.find((x) => x.id === id);
      const lineIn = (id, k = 0) => { const s = sec(id); const ls = D.items.map((it) => it.l).filter((l) => D.order[l] >= s.a && D.order[l] <= s.b); return ls[Math.min(k, ls.length - 1)]; };
      return { gem: lineIn("s15", 1) };
    });
    await L.record(s, "L5_sync", async () => {
      await L.sleep(500);
      await L.click(s, p.locator(`${head("s2")} .ado-t`), { ms: 900 });
      await L.sleep(2000);
      await L.click(s, p.locator('#langSeg button[data-l="he"]'), { ms: 800 }); await L.sleep(1300);
      await L.click(s, p.locator('#langSeg button[data-l="en"]'), { ms: 500 }); await L.sleep(1300);
      await L.click(s, p.locator('#langSeg button[data-l="both"]'), { ms: 500 }); await L.sleep(900);
      await L.click(s, p.locator('#textPane a[data-ref="Bava Metzia 37a:6"]').first(), { ms: 900 });
      await L.sleep(3000);
      await p.keyboard.press("Escape"); await L.sleep(400);
      await p.evaluate(() => { const x = [...document.querySelectorAll('dialog[open]')]; x.forEach((d) => d.close && d.close()); });
      const item = p.locator(`#text .item:has(.lab:text-is("${at.gem}"))`);
      await L.click(s, item.locator(".he"), { ms: 900 });
      await L.sleep(2200);
      await L.click(s, p.locator('#paneSeg button[data-p="page"]'), { ms: 800 });
      await L.sleep(2400);
      const tap = await p.evaluate(() => {
        const L = layOf(amudShown), cur = secs.find((x) => x.id === current);
        const ls = Object.keys(L.g).filter((l) => { const o = D.order[l]; return o != null && !(o >= cur.a && o <= cur.b); });
        const mid = ls.map((l) => [l, Math.abs(L.g[l][0][1] - 0.4)]).sort((a, b) => a[1] - b[1]);
        return mid.length ? mid[0][0] : null;
      });
      await L.click(s, p.locator(`#pageLay rect.g[data-l="${tap}"]`).first(), { ms: 1000 });
      await L.sleep(2200);
      await L.click(s, p.locator("#pageImg a[data-ref^='Mishneh Torah']").first(), { ms: 1000 });
      await L.sleep(3000);
    });
  },
  // 6. Every word: right-click a line on the daf page (Hullin 88a), a word's Jastrow entry, a verse word's BDB entry
  async s6(s) {
    const p = s.page;
    await L.load(s, "#Hullin/88");
    await p.evaluate(() => { setPane("page"); showAmud("88a"); });
    await L.sleep(3500);
    await L.record(s, "L6_words", async () => {
      await L.sleep(500);
      const r = p.locator('#pageLay rect.g[data-l="88a.10"]').first();
      await L.glide(s, r, 900); await L.sleep(300);
      await p.mouse.down({ button: "right" }); await L.sleep(60); await p.mouse.up({ button: "right" });
      await L.sleep(2200);
      await L.click(s, p.locator(".hw", { hasText: "זֶבֶל" }).first(), { ms: 900 });
      await L.sleep(3400);
      await L.click(s, p.locator(".hw", { hasText: "וְכִסָּהוּ" }).first(), { ms: 900 });
      await L.sleep(3800);
    });
  },
};

const want = process.argv.slice(2);
for (const [k, fn] of Object.entries(SCENES)) {
  if (want.length && !want.includes(k.slice(1))) continue;
  const s = await L.open();
  await L.load(s, DAF);
  console.log(k);
  try { await fn(s); await L.still(s, `L${k}_end`); } catch (e) { console.log("  FAILED:", e.message.split("\n")[0]); await L.still(s, `L${k}_fail`); } finally { await s.browser.close(); }
}
