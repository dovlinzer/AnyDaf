// The demo's takes, one per scene, on Bava Metzia 3 (the example outline).
//   node capture/scenes.mjs 1 2 3      (takes to record; all if none given)
import * as L from "./lib.mjs";

const DAF = "#Bava_Metzia/3/Example";
const head = (id) => `#outline .ado-node[data-id="${id}"] > .ado-head`;
const fold = (id) => `${head(id)} .ado-fold`;

const SCENES = {
  // 1. The outline: title and summary, a section opened, then the daf summary at the end
  async s1(s) {
    const p = s.page;
    await L.record(s, "s1_outline", async () => {
      await L.sleep(1200);
      await L.click(s, p.locator(fold("s1")), { ms: 900 });
      await L.sleep(3000);
      await L.click(s, p.locator(fold("s1")), { ms: 700 });
      await L.sleep(500);
      await L.click(s, p.locator("#outHead [data-sum]"), { ms: 800 });
      await L.sleep(3200);
    });
  },
  // 2. A chart, then an illustration
  async s2(s) {
    const p = s.page;
    await p.evaluate(() => { view.open("s2"); view.open("s3"); });
    await L.scrollToEl(s, "#outPane", `#outline .ado-node[data-id="s2"] .ado-chartw`, 0.1, 10);
    await L.sleep(800);
    await L.record(s, "s2_visuals", async () => {
      await L.glide(s, [500, 520], 900);
      await L.sleep(2600);
      await L.scrollToEl(s, "#outPane", `#outline .ado-node[data-id="s3"] .ado-ill`, 0.06, 1800);
      await L.glide(s, [560, 600], 800);
      await L.sleep(3400);
    });
  },
  // 3. A key term, a sage and his relationships, a measure
  async s3(s) {
    const p = s.page;
    await p.evaluate(() => { view.open("s2"); view.open("s3"); });
    await L.scrollToEl(s, "#outPane", head("s2"), 0.02, 10);
    await L.sleep(800);
    await L.record(s, "s3_reference", async () => {
      await L.sleep(500);
      await L.click(s, p.locator(`#outline .ado-node[data-id="s2"] .ado-term`).first(), { ms: 900 });
      await L.sleep(2600);
      await L.click(s, p.locator("#gwin button", { hasText: "×" }).first(), { ms: 600 });
      await L.sleep(300);
      await L.click(s, p.locator(`#outline .ado-node[data-id="s2"] .ado-sage`).first(), { ms: 800 });
      await L.sleep(1800);
      await L.click(s, p.locator('.relbtn[data-rel="rabbi-yose-b-chalafta"]'), { ms: 800 });
      await L.sleep(3000);
      await L.click(s, p.locator(".sgx-x"), { ms: 600 });
      await p.evaluate(() => $("swinClose").click());
      await L.sleep(200);
      await L.scrollToEl(s, "#outPane", "#outline .mu", 0.45, 900);
      await L.click(s, p.locator("#outline .mu").first(), { ms: 800 });
      await L.sleep(3200);
    });
  },
  // 4. The quiz: an answer, then its place in the outline and on the daf
  async s4(s) {
    const p = s.page;
    await L.record(s, "s4_quiz", async () => {
      await L.sleep(500);
      await L.click(s, p.locator("#practiceBtn"), { ms: 900 });
      await L.sleep(900);
      await L.click(s, p.locator('#pgames [data-g="quiz"]'), { ms: 700 });
      await L.sleep(2200);
      await L.click(s, p.locator('#pgames .adg-opt[data-k="0"]'), { ms: 800 });
      await L.sleep(2400);
      await L.click(s, p.locator("#pgames .adg-after [data-rev]"), { ms: 700 });
      await L.sleep(2400);
      await L.click(s, p.locator("#pgames .adg-after [data-daf]"), { ms: 700 });
      await L.sleep(3400);
    });
  },
  // 5. Outline and Talmud in sync: section -> Gemara, Gemara line -> outline, the daf page, a margin source
  async s5(s) {
    const p = s.page;
    const at = await p.evaluate(() => {
      const sec = (id) => secs.find((x) => x.id === id);
      const lineIn = (id, k = 0) => { const s = sec(id); const ls = D.items.map((it) => it.l).filter((l) => D.order[l] >= s.a && D.order[l] <= s.b); return ls[Math.min(k, ls.length - 1)]; };
      return { gem: lineIn("s15", 1) };
    });
    console.log("  lines:", at);
    await L.record(s, "s5_sync", async () => {
      await L.sleep(500);
      await L.click(s, p.locator(`${head("s9")} .ado-t`), { ms: 900 });
      await L.sleep(2200);
      const item = p.locator(`#text .item:has(.lab:text-is("${at.gem}"))`);
      await item.scrollIntoViewIfNeeded().catch(() => {});
      await L.click(s, item.locator(".he"), { ms: 900 });
      await L.sleep(2200);
      await L.click(s, p.locator('#paneSeg button[data-p="page"]'), { ms: 800 });
      await L.sleep(2400);
      const tap = await p.evaluate(() => {   // a line on the amud in view, in another section, about mid-page
        const L = layOf(amudShown), cur = secs.find((x) => x.id === current);
        const ls = Object.keys(L.g).filter((l) => { const o = D.order[l]; return o != null && !(o >= cur.a && o <= cur.b); });
        const mid = ls.map((l) => [l, Math.abs(L.g[l][0][1] - 0.4)]).sort((a, b) => a[1] - b[1]);
        return mid.length ? mid[0][0] : null;
      });
      console.log("  tap:", tap);
      await L.click(s, p.locator(`#pageLay rect.g[data-l="${tap}"]`).first(), { ms: 1000 });
      await L.sleep(2200);
      await L.click(s, p.locator("#pageImg a[data-ref^='Mishneh Torah']").first(), { ms: 1000 });
      await L.sleep(3200);
    });
  },
};

const want = process.argv.slice(2);
for (const [k, fn] of Object.entries(SCENES)) {
  if (want.length && !want.includes(k.slice(1))) continue;
  const s = await L.open();
  await L.load(s, DAF);
  console.log(k);
  try { await fn(s); await L.still(s, `${k}_end`); } finally { await s.browser.close(); }
}
