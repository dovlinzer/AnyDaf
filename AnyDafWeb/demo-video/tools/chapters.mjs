// Chapter markers for an edit with Features cards: one chapter per feature, starting at its Features card.
//   node tools/chapters.mjs calm120                 -> prints the chapters (and writes out/<edit>.chapters.txt)
//   node tools/chapters.mjs calm120 out/a.mp4 ...   -> also embeds them in each video (in place, streams copied)
// The .txt is YouTube's format (first chapter at 0:00; YouTube wants each chapter at least 10 s long, so a
// shorter one is folded into the one before it there; the embedded markers keep every chapter).
import { build } from "esbuild";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const [edit = "calm120", ...videos] = process.argv.slice(2);
const voice = edit.endsWith("v");   // calm120v: the narrated calm120

// the bundle sits inside the project so its imports (react, remotion) resolve
const tmp = fs.mkdtempSync(path.join(ROOT, "out", ".chapters-"));
const outfile = path.join(tmp, "t.mjs");
await build({
  stdin: { contents: `export { timeline } from "./src/Demo";\nexport { FPS } from "./src/cut";`, resolveDir: ROOT, loader: "ts" },
  bundle: true, format: "esm", platform: "node", outfile, logLevel: "error",
  external: ["remotion", "react", "react/jsx-runtime"], jsx: "automatic",
});
const { timeline, FPS } = await import(pathToFileURL(outfile));
const { pieces, total } = timeline(voice ? edit.slice(0, -1) : edit, voice);
const marks = pieces.filter((p) => p.chapter).map((p) => ({ t: p.from / FPS, title: p.chapter }));
const end = total / FPS;
const ts = (s) => { s = Math.floor(s); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };

// YouTube list: fold a chapter under 10 s into the one before it, working from the end
const yt = [...marks];
for (let i = yt.length - 1; i > 0; i--) if ((yt[i + 1]?.t ?? end) - yt[i].t < 10) yt.splice(i, 1);
const txt = yt.map((m, i) => `${i === 0 ? "0:00" : ts(m.t)} ${m.title}`).join("\n");
fs.writeFileSync(path.join(ROOT, "out", `${edit}.chapters.txt`), txt + "\n");
if (process.env.PIECES) console.log(pieces.map((p) => `  ${p.id.padEnd(5)} ${(p.len / FPS).toFixed(1)}s  ${p.scene?.clip || ""}`).join("\n"));
console.log(`${edit}: ${end.toFixed(2)} s\n` + marks.map((m) => `  ${ts(m.t)}  ${m.title}`).join("\n"));

for (const v of videos) {
  const meta = path.join(tmp, "meta.txt");
  const ms = (s) => Math.round(s * 1000);
  fs.writeFileSync(meta, ";FFMETADATA1\n" + marks.map((m, i) =>
    `[CHAPTER]\nTIMEBASE=1/1000\nSTART=${ms(m.t)}\nEND=${ms(marks[i + 1]?.t ?? end)}\ntitle=${m.title.replace(/([=;#\\])/g, "\\$1")}\n`).join(""));
  const tmpv = v.replace(/\.mp4$/, ".tmp.mp4");
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", v, "-i", meta, "-map", "0", "-map_metadata", "1", "-map_chapters", "1", "-c", "copy", tmpv]);
  fs.renameSync(tmpv, v);
  console.log("chapters embedded:", v);
}
fs.rmSync(tmp, { recursive: true, force: true });
