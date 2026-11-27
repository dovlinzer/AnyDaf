// Render the calm cuts, narrated or silent, choosing which:
//   node tools/render.mjs                         every narrated cut (calm120, calm60, the three 30 s), 16:9 and 9:16
//   node tools/render.mjs calm30study calm60      just these
//   node tools/render.mjs --skip calm120          all but these
//   node tools/render.mjs --silent ...            the silent versions instead
//   node tools/render.mjs --only 16x9 ...         one format
// The 2-minute cut also gets its chapter markers.
import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ALL = ["calm120", "calm60", "calm30study", "calm30reference", "calm30practice"];
const args = process.argv.slice(2), skip = [], pick = [];
let silent = false, fmts = ["16x9", "9x16"];
for (let i = 0; i < args.length; i++) {
  const a = args[i];
  if (a === "--silent") silent = true;
  else if (a === "--skip") skip.push(...args[++i].split(","));
  else if (a === "--only") fmts = [args[++i]];
  else pick.push(...a.split(","));
}
const bad = [...pick, ...skip].filter((e) => !ALL.includes(e));
if (bad.length) { console.error(`unknown cut: ${bad.join(", ")} (cuts: ${ALL.join(", ")})`); process.exit(1); }
const cuts = (pick.length ? pick : ALL).filter((e) => !skip.includes(e));
const run = (cmd, a) => execFileSync(cmd, a, { cwd: ROOT, stdio: "inherit" });
for (const e of cuts) {
  const outs = [];
  for (const f of fmts) {
    const out = `out/italmud-${e}${silent ? "" : "-voice"}-${f}.mp4`;
    console.log(`\n${e}${silent ? "" : " (narrated)"} ${f} -> ${out}`);
    run("npx", ["remotion", "render", "src/index.ts", `${e}${silent ? "" : "v"}-${f}`, out, "--log=error"]);
    outs.push(out);
  }
  if (e === "calm120") run("node", ["tools/chapters.mjs", silent ? "calm120" : "calm120v", ...outs]);
}
