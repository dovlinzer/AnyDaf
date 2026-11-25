// Capture helpers for the iTalmud demo video.
// Frames come from the Chrome DevTools screencast (JPEG, at the device pixel ratio), timestamped, and are
// assembled by ffmpeg into a constant-frame-rate MP4. A cursor is drawn into the page (headless Chrome has
// none), and mouse moves and scrolls are eased so the footage reads smoothly.
import { chromium } from "playwright";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

export const SITE = "https://anydaf-outlines.vercel.app";
export const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

// the reader's settings for every take: outline beside the text, the text side at 40%
export const PREFS = { layout: "both", pane: "text", split: false, gemw: 42, collapse: true, foldOpen: false, xrMode: "margin", terms: false, nav: true };

const CURSOR = (touch) => `
(() => {
  const TOUCH = ${touch ? 'true' : 'false'};
  if (window.__demoCursor) return; window.__demoCursor = true;
  const c = document.createElement('div');
  c.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24"><path d="M4 2 L4 19 L8.5 14.8 L11.6 21.6 L14.3 20.4 L11.2 13.7 L17.5 13.7 Z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
  if (TOUCH) c.innerHTML = '<div style="width:30px;height:30px;margin:-15px 0 0 -15px;border-radius:50%;background:rgba(40,40,40,.28);border:2px solid rgba(255,255,255,.9);box-shadow:0 1px 4px rgba(0,0,0,.3)"></div>';
  Object.assign(c.style, {position:'fixed', left:'0', top:'0', zIndex:2147483647, pointerEvents:'none', transform:'translate(-200px,-200px)', filter:'drop-shadow(0 1px 2px rgba(0,0,0,.35))'});
  const ring = document.createElement('div');
  Object.assign(ring.style, {position:'fixed', width:'36px', height:'36px', margin:'-18px 0 0 -18px', borderRadius:'50%', border:'3px solid rgba(232,160,32,.9)', zIndex:2147483646, pointerEvents:'none', opacity:'0', left:'0', top:'0'});
  const add = () => { document.body.appendChild(c); document.body.appendChild(ring); };
  document.body ? add() : addEventListener('DOMContentLoaded', add);
  addEventListener('mousemove', (e) => { c.style.transform = TOUCH ? 'translate(' + e.clientX + 'px,' + e.clientY + 'px)' : 'translate(' + (e.clientX - 3) + 'px,' + (e.clientY - 2) + 'px)'; }, true);
  addEventListener('mousedown', (e) => {
    ring.style.left = e.clientX + 'px'; ring.style.top = e.clientY + 'px';
    ring.animate([{opacity:1, transform:'scale(.4)'}, {opacity:0, transform:'scale(1.4)'}], {duration: 550, easing: 'ease-out'});
  }, true);
})();`;

// hide things that belong to a particular day (the dedication) and the per-heading flags
const DEMO_CSS = `#dedLine{display:none!important} #dedDlg{display:none!important} #verSeg{visibility:hidden!important}`;

export async function open({ width = 1600, height = 900, scale = 2, mobile = false } = {}) {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: scale, isMobile: mobile, hasTouch: mobile });
  const today = new Date().toISOString().slice(0, 10);
  await ctx.addInitScript(({ prefs, today }) => {
    try {
      if (!sessionStorage.getItem("demoInit")) { localStorage.setItem("adw", JSON.stringify(prefs)); sessionStorage.setItem("demoInit", "1"); }
      localStorage.setItem("anydaf:lastDedicationShown", today);
    } catch (e) {}
  }, { prefs: PREFS, today });
  await ctx.addInitScript(CURSOR(mobile));
  const page = await ctx.newPage();
  page.on("pageerror", (e) => console.log("  page error:", e.message));
  const mouse = { x: width / 2, y: height / 2 };
  return { browser, ctx, page, mouse, width, height, scale };
}

export async function load(s, hash) {
  await s.page.goto(SITE + "/" + hash, { waitUntil: "networkidle" });
  await s.page.addStyleTag({ content: DEMO_CSS });
  await s.page.waitForFunction(() => typeof D !== "undefined" && D && typeof view !== "undefined" && view, null, { timeout: 30000 }).catch(() => {});
  await sleep(1200);
}

// an eased glide of the cursor to (x, y) or to the centre of a locator
export async function glide(s, to, ms = 700) {
  let x, y;
  if (typeof to === "object" && to.boundingBox) { const b = await to.boundingBox(); if (!b) throw new Error("glide: not visible"); x = b.x + b.width / 2; y = b.y + b.height / 2; }
  else [x, y] = to;
  const x0 = s.mouse.x, y0 = s.mouse.y, n = Math.max(8, Math.round(ms / 16));
  for (let i = 1; i <= n; i++) { const t = ease(i / n); await s.page.mouse.move(x0 + (x - x0) * t, y0 + (y - y0) * t); await sleep(ms / n); }
  s.mouse.x = x; s.mouse.y = y;
}
export async function click(s, to, { ms = 650, pause = 180 } = {}) {
  if (typeof to === "object" && to.scrollIntoViewIfNeeded) { await to.scrollIntoViewIfNeeded({ timeout: 5000 }).catch(() => {}); await sleep(150); }
  await glide(s, to, ms); await sleep(pause);
  await s.page.mouse.down(); await sleep(70); await s.page.mouse.up();
}
// a smooth scroll of a scrolling element by dy pixels (or to a target scrollTop)
export async function scrollBy(s, selector, dy, ms = 1200) {
  await s.page.evaluate(async ({ selector, dy, ms }) => {
    const el = document.querySelector(selector); const y0 = el.scrollTop, t0 = performance.now();
    const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
    await new Promise((res) => { const step = (now) => { const t = Math.min(1, (now - t0) / ms); el.scrollTop = y0 + dy * ease(t); t < 1 ? requestAnimationFrame(step) : res(); }; requestAnimationFrame(step); });
  }, { selector, dy, ms });
}
// scroll an element into a pane so it sits `frac` of the way down
export async function scrollToEl(s, paneSel, elSel, frac = 0.15, ms = 1200) {
  const dy = await s.page.evaluate(({ paneSel, elSel, frac }) => {
    const p = document.querySelector(paneSel), e = typeof elSel === "string" ? document.querySelector(elSel) : null;
    if (!p || !e) return 0; const pr = p.getBoundingClientRect(), r = e.getBoundingClientRect();
    return r.top - pr.top - p.clientHeight * frac;
  }, { paneSel, elSel, frac });
  if (Math.abs(dy) > 2) await scrollBy(s, paneSel, dy, ms);
}

// ---------- recording ----------
export async function record(s, name, fn, { fps = 30 } = {}) {
  const dir = path.join(ROOT, "captures", name); fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(dir, { recursive: true });
  const cdp = await s.ctx.newCDPSession(s.page), frames = [];
  cdp.on("Page.screencastFrame", async (f) => {
    frames.push({ t: f.metadata.timestamp, data: f.data });
    try { await cdp.send("Page.screencastFrameAck", { sessionId: f.sessionId }); } catch (e) {}
  });
  // a heartbeat repaint so static stretches still get frames
  await s.page.evaluate(() => { const d = document.createElement('div'); d.id = '__hb'; Object.assign(d.style, {position:'fixed', right:'0', bottom:'0', width:'1px', height:'1px', opacity:'0.01', pointerEvents:'none'}); document.body.appendChild(d); let k = 0; window.__hbT = setInterval(() => { d.style.background = (k++ % 2) ? '#fff' : '#fefefe'; }, 33); });
  await cdp.send("Page.startScreencast", { format: "jpeg", quality: 92, maxWidth: s.width * s.scale, maxHeight: s.height * s.scale, everyNthFrame: 1 });
  const t0 = Date.now() / 1000;
  await fn();
  const t1 = Date.now() / 1000;
  await cdp.send("Page.stopScreencast");
  await s.page.evaluate(() => clearInterval(window.__hbT));
  // write the frames with their durations, then a constant-rate MP4
  const lines = [];
  frames.forEach((f, i) => {
    const file = `f${String(i).padStart(5, "0")}.jpg`; fs.writeFileSync(path.join(dir, file), Buffer.from(f.data, "base64"));
    const next = i + 1 < frames.length ? frames[i + 1].t : Math.max(f.t + 1 / fps, f.t + (t1 - (frames.at(-1).t)));
    lines.push(`file '${file}'`, `duration ${Math.max(0.001, next - f.t).toFixed(4)}`);
  });
  lines.push(`file 'f${String(frames.length - 1).padStart(5, "0")}.jpg'`);
  fs.writeFileSync(path.join(dir, "list.txt"), lines.join("\n"));
  const out = path.join(ROOT, "public", "clips", `${name}.mp4`); fs.mkdirSync(path.dirname(out), { recursive: true });
  const r = spawnSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "list.txt", "-vf", `fps=${fps},scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p`, "-c:v", "libx264", "-preset", "slow", "-crf", "14", out], { cwd: dir });
  if (r.status) throw new Error(r.stderr.toString());
  const span = frames.length ? frames.at(-1).t - frames[0].t : 0;
  console.log(`  ${name}: ${frames.length} frames over ${span.toFixed(1)}s (${(frames.length / Math.max(span, 0.01)).toFixed(1)} fps captured), ${(t1 - t0).toFixed(1)}s take -> ${path.relative(ROOT, out)}`);
  return out;
}

// a still of the page, for checking a take
export async function still(s, name) { const f = path.join(ROOT, "captures", `${name}.png`); fs.mkdirSync(path.dirname(f), { recursive: true }); await s.page.screenshot({ path: f }); return f; }
