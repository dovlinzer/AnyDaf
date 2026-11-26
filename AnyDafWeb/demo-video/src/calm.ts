// The calm edits: built from one-feature takes (capture/beats.mjs) played at about 1x, one caption per feature.
// The camera follows the targets each take logged (src/beats.gen.json, from capture/collect.mjs).
import { Key, Scene } from "./cut";
import GEN from "./beats.gen.json";

type Gen = { dur: number; marks: number[]; focus: (number | string)[][] };
const G = GEN as Record<string, Gen>;

export type Beat = { kicker: string; caption: string; from?: number; to?: number };
export const BEATS: Record<string, Beat> = {
  outline:      { kicker: "The study outline", caption: "Every daf has a study outline. Open a section for its steps and the shiur's insights." },
  summary:      { kicker: "The study outline", caption: "A summary of the whole daf, each point linked to its section." },
  chart:        { kicker: "Charts & illustrations", caption: "Charts set the cases side by side, with an icon for each ruling." },
  illustration: { kicker: "Charts & illustrations", caption: "Illustrations draw each case, and how each opinion rules on it." },
  reference:    { kicker: "Terms, sages, measures", caption: "Tap a key term for its definition, or a measure to see it on a scale." },
  sages:        { kicker: "Terms, sages, measures", caption: "Tap a sage to meet him, his teachers and his students." },
  quiz:         { kicker: "Quizzes & games", caption: "A quiz on every daf. Each answer links to its place on the daf." },
  fillchart:    { kicker: "Quizzes & games", caption: "Or rebuild a chart: drag each card to its place." },
  textsync:     { kicker: "Outline and Talmud in step", caption: "Tap a section, and the Gemara goes there, in Hebrew, English or both." },
  linesync:     { kicker: "Outline and Talmud in step", caption: "Tap a line of Gemara, and the outline follows." },
  dafpage:      { kicker: "Outline and Talmud in step", caption: "On the daf page too, with the Rambam and Shulchan Arukh in the margin." },
  words:        { kicker: "Every word", caption: "Right-click a line on the daf, then tap any word for its meaning and its dictionary entry." },
};

// ---------- the camera, from a take's targets ----------
const TALL_ASPECT = 1080 / (1920 - 360);   // the 9:16 video window under the caption
const MOVE = 0.9;                          // seconds the camera takes to reach a new target
function frame(r: number[], fmt: "wide" | "tall"): Omit<Key, "t"> {
  const [x, y, w, h] = r, cx = x + w / 2, cy = y + h / 2;
  if (fmt === "wide") {
    const cw = Math.max(w * 1.15, h * (16 / 9) * 1.05, 1000);
    return cw > 1450 ? { x: 800, y: 450, w: 1600 } : { x: cx, y: cy, w: cw };
  }
  // 9:16: keep the text readable on a phone; a wide target is cut, a tall one is shown from its top
  const cw = Math.min(620, Math.max(500, w * 1.06)), visH = cw / TALL_ASPECT;
  const fx = w * 1.06 <= cw ? cx : x < 60 ? x + cw / 2 - 10 : cx;
  const fy = h * 1.04 <= visH ? cy : y + visH / 2 - 10;
  return { x: fx, y: fy, w: cw };
}
function camera(clip: string, fmt: "wide" | "tall"): Key[] {
  const fs = (G[clip]?.focus || []).filter((f) => f.length < 6 || f[5] === fmt);
  const keys: Key[] = [];
  fs.forEach((f, i) => {
    const [t, ...r] = f as number[], k = frame(r.slice(0, 4), fmt);
    if (i === 0) { keys.push({ t: 0, ...k }); return; }
    keys.push({ ...keys[keys.length - 1], t: Math.max(t, keys[keys.length - 1].t + 0.01) }, { t: t + MOVE, ...k });
  });
  return keys.length ? keys : [{ t: 0, x: 800, y: 450, w: 1600 }];
}

// name, or name@from-to to play only part of the take
export const beatScene = (spec: string, rate: number): Scene => {
  const [name, part] = spec.split("@"), [pf, pt] = part ? part.split("-").map(Number) : [];
  const b = { ...BEATS[name], ...(part ? { from: pf, to: pt } : {}) }, g = G["C_" + name];
  if (name === "reference" && part && pt < 6.5) b.caption = "Tap a key term for its definition.";
  return {
    clip: "C_" + name, kicker: b.kicker, caption: b.caption,
    segs: [{ from: b.from ?? 0.3, to: b.to ?? Math.max(1, (g?.dur || 8) - 0.15), rate }],
    wide: camera("C_" + name, "wide"), tall: camera("C_" + name, "tall"),
  };
};

export type Edit = { scenes: Scene[]; titleS: number; endS: number };
const edit = (names: string[], rate: number, titleS = 2.6, endS = 5.6): Edit => ({ scenes: names.map((n) => beatScene(n, rate)), titleS, endS });

export const CALM: Record<string, Edit> = {
  calm90: edit(["outline", "summary@0.8-11.6", "chart@0.8-11.6", "illustration", "reference", "sages", "quiz@0.5-16.3", "textsync", "dafpage", "words"], 1.25),
  calm60: edit(["outline", "illustration", "sages", "quiz@0.5-16.3", "dafpage", "words"], 1.2),
  // three 30-second cuts, each with its own features
  calm30study: edit(["outline", "chart@0.8-11.6", "illustration"], 1.2, 2.2, 5.0),
  calm30reference: edit(["reference@0.3-5.6", "sages", "words"], 1.25, 2.2, 5.0),
  calm30practice: edit(["quiz@0.5-16.3", "textsync", "linesync"], 1.25, 2.2, 5.0),
};
