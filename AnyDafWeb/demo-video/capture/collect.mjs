// Gathers the calm takes' timings into src/beats.gen.json for the edit: each clip's length, click times and
// camera targets (from public/clips/C_*.marks.json and .cam.json).
import fs from "node:fs";
import path from "node:path";
import { ROOT } from "./lib.mjs";

const dir = path.join(ROOT, "public", "clips"), out = {};
for (const f of fs.readdirSync(dir).filter((f) => /^C_.*\.mp4$/.test(f)).sort()) {
  const name = f.replace(/\.mp4$/, ""), rd = (ext) => { try { return JSON.parse(fs.readFileSync(path.join(dir, name + ext), "utf8")); } catch { return []; } };
  const marks = rd(".marks.json"), end = marks.find((m) => m[0] === "end");
  out[name] = { dur: end ? end[1] : 0, marks: marks.filter((m) => m[0] !== "end").map((m) => m[1]), focus: rd(".cam.json") };
}
fs.writeFileSync(path.join(ROOT, "src", "beats.gen.json"), JSON.stringify(out, null, 1));
console.log(Object.entries(out).map(([k, v]) => `${k} ${v.dur}s, ${v.focus.length} camera targets`).join("\n"));
