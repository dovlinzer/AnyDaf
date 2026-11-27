// The calm edits: built from one-feature takes (capture/beats.mjs) played at about 1x, one caption per feature.
// The camera follows the targets each take logged (src/beats.gen.json, from capture/collect.mjs).
import { Key, Scene } from "./cut";
import GEN from "./beats.gen.json";

type Gen = { dur: number; marks: number[]; focus: (number | string)[][] };
const G = GEN as Record<string, Gen>;

// rate: this beat's own speed (else the edit's); hold: seconds to hold its last frame
export type Beat = { kicker: string; caption: string; from?: number; to?: number; rate?: number; hold?: number };
export const BEATS: Record<string, Beat> = {
  outline:      { kicker: "Study Outline", caption: "Every daf has a study outline. Open a section for its steps and the shiur's insights." },
  summary:      { kicker: "Study Outline", caption: "A summary of the whole daf, each point linked to its section." },
  chart:        { kicker: "Charts & illustrations", caption: "Charts set the cases side by side, with an icon for each ruling." },
  illustration: { kicker: "Charts & illustrations", caption: "Illustrations draw each case, and how each opinion rules on it." },
  reference:    { kicker: "Terms, sages, measures", caption: "Tap a key term for its definition, or a measure to see it on a scale." },
  sages:        { kicker: "Terms, sages, measures", caption: "Tap a sage to meet him, his teachers and his students." },
  quiz:         { kicker: "Quizzes & games", caption: "A quiz on every daf. Each answer links to its place on the daf." },
  fillchart:    { kicker: "Quizzes & games", caption: "Or rebuild a chart: drag each card to its place." },
  textsync:     { kicker: "Outline and Talmud in step", caption: "Tap a section, and the Gemara goes there, in Hebrew, English or both." },
  linesync:     { kicker: "Outline and Talmud in step", caption: "Tap a line of Gemara, and the outline follows." },
  dafsync:      { kicker: "Study Outline", caption: "Tap a section, and the daf page goes there. Tap a passage on the daf, and the outline follows." },
  memory:       { kicker: "Quizzes & games", caption: "Or play term match: flip two cards to pair each term with its meaning.", rate: 1.4 },
  links:        { kicker: "Links to Tanakh, Shas and Halakha", caption: "Every passage on the daf links to its sources: the verses in Tanakh, parallels in Shas, and rulings in Rambam and Shulchan Arukh. Each opens in place, in its context.", rate: 1.35 },
  xrefs:        { kicker: "Links to Tanakh, Shas and Halakha", caption: "Every line links to its sources: the verse in Tanakh, the parallels in Shas, the Rambam and Shulchan Arukh." },
  dafpage:      { kicker: "Links to Tanakh, Shas and Halakha", caption: "On the daf page too, the sources in the margin. Tap a passage, and the outline goes there." },
  // a Gemara word (Jastrow), then a word from the verse the baraita quotes (BDB); a little slower than the rest
  words:        { kicker: "Word Definitions", caption: "Right-click a line on the daf, then tap any word for its meaning and its entry in the dictionary: Jastrow for the Gemara, BDB for a verse.", rate: 1.2, hold: 0.8 },
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

// 16:9: hold the whole screen until `at` (seconds of the take), then move in to wherever the take's camera is by then
function openWide(keys: Key[], at: number): Key[] {
  const FULL = { x: 800, y: 450, w: 1600 }, k = [...keys].reverse().find((x) => x.t <= at + MOVE) || keys[0];
  return [{ t: 0, ...FULL }, { t: at, ...FULL }, { t: at + MOVE, x: k.x, y: k.y, w: k.w }, ...keys.filter((x) => x.t > at + MOVE)];
}

// name, or name@from-to to play only part of the take, or name@a-b,c-d to play two parts of it (cut together);
// a trailing "|wide" starts the scene on the whole screen (16:9) and moves in a second later
export const beatScene = (spec0: string, rate: number): Scene => {
  const [spec, opt] = spec0.split("|"), [name, part] = spec.split("@"), g = G["C_" + name];
  const b = { ...BEATS[name] };
  const parts = part ? part.split(",").map((x) => x.split("-").map(Number)) : [[b.from ?? 0.3, b.to ?? Math.max(1, (g?.dur || 8) - 0.15)]];
  if (name === "reference" && parts.length === 1 && parts[0][1] < 6.5) b.caption = "Tap a key term for its definition.";
  // a glimpse (under 4 s of the take): a caption short enough to read in that time
  if (name === "chart" && parts.length === 1 && parts[0][1] - parts[0][0] < 4) b.caption = "Charts set the cases side by side.";
  const r = b.rate ?? rate, to = parts[parts.length - 1][1];
  return {
    clip: "C_" + name, kicker: b.kicker, caption: b.caption,
    segs: [...parts.map(([from, t]) => ({ from, to: t, rate: r })),
      // a hold: the last frame, played very slowly
      ...(b.hold ? [{ from: to - 0.03, to, rate: 0.03 / b.hold }] : [])],
    wide: opt === "wide" ? openWide(camera("C_" + name, "wide"), parts[0][0] + 1.0) : camera("C_" + name, "wide"), tall: camera("C_" + name, "tall"),
  };
};

// features: a Features card before each feature; endPad: with narration, the end card holds this long after the end line
// topic: a card after the title naming what this cut shows (the 30-second cuts each show one part of the whole)
export type Edit = { scenes: Scene[]; titleS: number; endS: number; features?: boolean; endPad?: number; topic?: string };
const edit = (names: string[], rate: number, titleS = 2.6, endS = 5.6, features = false, endPad?: number, topic?: string): Edit => ({ scenes: names.map((n) => beatScene(n, rate)), titleS, endS, features, endPad, topic });

export const CALM: Record<string, Edit> = {
  // about two minutes: every feature, each introduced by the Features card
  calm120: edit(["outline", "summary@0.8-11.6", "dafsync@1.0-10.6", "chart@0.8-10.6", "illustration", "reference", "sages", "quiz@0.5-16.3", "fillchart@0.3-5.6", "memory@0.5-14.0", "links@0.3-19.2", "words"], 1.25, 2.6, 5.6, true),
  calm90: edit(["outline", "summary@0.8-11.6", "chart@0.8-11.6", "illustration", "reference", "sages", "quiz@0.5-16.3", "textsync", "dafpage", "words"], 1.25),
  // the short cuts are trimmed so each scene runs about as long as its narrated line
  calm60: edit(["outline", "chart@0.8-3.8", "illustration", "reference@1.5-5.0", "sages@1.5-11.6", "quiz@1.2-14.0", "links@0.3-19.2", "words@0.6-7.4,9.6-14.4|wide"], 1.2, 2.6, 5.6, false, 0.8),
  // three 30-second cuts, each with its own features
  calm30study: edit(["outline", "chart@0.8-7.8", "illustration"], 1.2, 2.2, 5.0, false, 0.8, "Study Outlines,\nCharts and Illustrations"),
  calm30reference: edit(["reference@1.5-5.0,7.6-12.0", "sages@1.5-9.6", "words@0.6-7.4,9.6-14.4|wide"], 1.25, 2.2, 5.0, false, 0.8, "Terms, Measures,\nSages, Definitions"),
  calm30practice: edit(["quiz@1.2-13.6", "fillchart@0.3-5.6", "memory@2.2-14.0"], 1.3, 2.2, 5.0, false, 0.8, "Quizzes and Games"),
};
