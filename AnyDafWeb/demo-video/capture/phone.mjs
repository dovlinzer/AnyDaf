// The demo's takes in the phone layout, for the 9:16 version (432x768 at 3x).
// On a phone the outline and the text take turns on the screen; the switch on the bar flips them.
//   node capture/phone.mjs 1 2 3      (takes to record; all if none given)
import * as L from "./lib.mjs";

const DAF = "#Bava_Metzia/3/Example";
const head = (id) => `#outline .ado-node[data-id="${id}"] > .ado-head`;
const fold = (id) => `${head(id)} .ado-fold`;
const seg = (p) => `#paneSeg button[data-p="${p}"]`;

const SCENES = {
  async s1(s) {
    const p = s.page;
    await L.record(s, "p1_outline", async () => {
      await L.sleep(1400);
      await L.click(s, p.locator(fold("s1")), { ms: 800 });
      await L.sleep(800);
      await L.scrollToEl(s, "#outPane", head("s1"), 0.02, 900);
      await L.sleep(2200);
      await L.scrollBy(s, "#outPane", -3000, 700);
      await L.click(s, p.locator("#outHead [data-sum]"), { ms: 800 });
      await L.sleep(3400);
    });
  },
  async s2(s) {
    const p = s.page;
    await p.evaluate(() => { view.open("s2"); view.open("s3"); });
    await L.scrollToEl(s, "#outPane", `#outline .ado-node[data-id="s2"] .ado-chartw`, 0.06, 10);
    await L.sleep(800);
    await L.record(s, "p2_visuals", async () => {
      await L.glide(s, [220, 420], 800);
      await L.sleep(2800);
      await L.scrollToEl(s, "#outPane", `#outline .ado-node[data-id="s3"] .ado-ill`, 0.04, 1800);
      await L.sleep(3400);
    });
  },
  async s3(s) {
    const p = s.page;
    await p.evaluate(() => { view.open("s2"); view.open("s3"); });
    await L.scrollToEl(s, "#outPane", head("s2"), 0.02, 10);
    await L.sleep(800);
    await L.record(s, "p3_reference", async () => {
      await L.sleep(500);
      await L.click(s, p.locator(`#outline .ado-node[data-id="s2"] .ado-term`).first(), { ms: 800 });
      await L.sleep(2600);
      await L.click(s, p.locator("#gwin button", { hasText: "×" }).first(), { ms: 600 });
      await L.sleep(300);
      await L.click(s, p.locator(`#outline .ado-node[data-id="s2"] .ado-sage`).first(), { ms: 800 });
      await L.sleep(1800);
      await L.click(s, p.locator('.relbtn[data-rel="rabbi-yose-b-chalafta"]'), { ms: 800 });
      await L.sleep(3200);
      await L.click(s, p.locator(".sgx-x"), { ms: 600 });
      await p.evaluate(() => $("swinClose").click());
      await L.sleep(200);
      await L.scrollToEl(s, "#outPane", "#outline .mu", 0.4, 900);
      await L.click(s, p.locator("#outline .mu").first(), { ms: 800 });
      await L.sleep(3200);
    });
  },
  async s4(s) {
    const p = s.page;
    await L.record(s, "p4_quiz", async () => {
      await L.sleep(500);
      await L.click(s, p.locator("#practiceBtn"), { ms: 800 });
      await L.sleep(900);
      await L.click(s, p.locator('#pgames [data-g="quiz"]'), { ms: 700 });
      await L.sleep(2200);
      await L.click(s, p.locator('#pgames .adg-opt[data-k="0"]'), { ms: 800 });
      await L.sleep(2600);
      await L.click(s, p.locator("#pgames .adg-after [data-daf]"), { ms: 700 });
      await L.sleep(3600);
    });
  },
  async s5(s) {
    const p = s.page;
    const at = await p.evaluate(() => {
      const sec = (id) => secs.find((x) => x.id === id);
      const lineIn = (id, k = 0) => { const s = sec(id); const ls = D.items.map((it) => it.l).filter((l) => D.order[l] >= s.a && D.order[l] <= s.b); return ls[Math.min(k, ls.length - 1)]; };
      return { gem: lineIn("s15", 1) };
    });
    await L.record(s, "p5_sync", async () => {
      await L.sleep(500);
      await L.click(s, p.locator(`${head("s9")} .ado-t`), { ms: 800 });
      await L.sleep(900);
      await L.click(s, p.locator(seg("text")), { ms: 800 });
      await L.sleep(2000);
      const item = p.locator(`#text .item:has(.lab:text-is("${at.gem}"))`);
      await L.click(s, item.locator(".he"), { ms: 900 });
      await L.sleep(800);
      await L.click(s, p.locator(seg("outline")), { ms: 800 });
      await L.sleep(2000);
      await L.click(s, p.locator(seg("page")), { ms: 800 });
      await L.sleep(2600);
      await L.click(s, p.locator("#pageImg a[data-ref^='Mishneh Torah']").first(), { ms: 900 });
      await L.sleep(3200);
    });
  },
};

const want = process.argv.slice(2);
for (const [k, fn] of Object.entries(SCENES)) {
  if (want.length && !want.includes(k.slice(1))) continue;
  const s = await L.open({ width: 432, height: 768, scale: 3, mobile: true });
  await L.load(s, DAF);
  console.log(k);
  try { await fn(s); await L.still(s, `p${k}_end`); } catch (e) { console.log("  FAILED:", e.message.split("\n")[0]); await L.still(s, `p${k}_fail`); } finally { await s.browser.close(); }
}
