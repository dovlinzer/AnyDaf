import * as L from "./lib.mjs";
const s = await L.open();
await L.load(s, "#Bava_Metzia/3/Example");
await L.still(s, "probe_start");
await L.record(s, "probe", async () => {
  await L.glide(s, [400, 400], 600);
  await L.scrollBy(s, "#outPane", 600, 1500);
  await L.sleep(500);
  await L.scrollBy(s, "#outPane", -600, 1200);
  await L.sleep(300);
});
await s.browser.close();
