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
  links:        { kicker: "Links to Tanakh, Shas and Halakha", caption: "Every passage on the daf links to its sources: the parallels in Shas, the Rambam and the Shulchan Arukh. Each opens in place, in its context.", rate: 1.35 },
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

// name, or name@from-to to play only part of the take
export const beatScene = (spec: string, rate: number): Scene => {
  const [name, part] = spec.split("@"), [pf, pt] = part ? part.split("-").map(Number) : [];
  const b = { ...BEATS[name], ...(part ? { from: pf, to: pt } : {}) }, g = G["C_" + name];
  if (name === "reference" && part && pt < 6.5) b.caption = "Tap a key term for its definition.";
  return {
    clip: "C_" + name, kicker: b.kicker, caption: b.caption,
    segs: ((to) => [{ from: b.from ?? 0.3, to, rate: b.rate ?? rate },
      // a hold: the last frame, played very slowly
      ...(b.hold ? [{ from: to - 0.03, to, rate: 0.03 / b.hold }] : [])])(b.to ?? Math.max(1, (g?.dur || 8) - 0.15)),
    wide: camera("C_" + name, "wide"), tall: camera("C_" + name, "tall"),
  };
};

export type Edit = { scenes: Scene[]; titleS: number; endS: number; features?: boolean };   // features: a Features card before each feature
const edit = (names: string[], rate: number, titleS = 2.6, endS = 5.6, features = false): Edit => ({ scenes: names.map((n) => beatScene(n, rate)), titleS, endS, features });

export const CALM: Record<string, Edit> = {
  // about two minutes: every feature, each introduced by the Features card
  calm120: edit(["outline", "summary@0.8-11.6", "dafsync@1.0-10.6", "chart@0.8-10.6", "illustration", "reference", "sages", "quiz@0.5-16.3", "fillchart@0.3-5.6", "memory@8.9-19.9", "links@0.3-25.6", "words"], 1.25, 2.6, 5.6, true),
  calm90: edit(["outline", "summary@0.8-11.6", "chart@0.8-11.6", "illustration", "reference", "sages", "quiz@0.5-16.3", "textsync", "dafpage", "words"], 1.25),
  calm60: edit(["outline", "illustration", "sages", "quiz@0.5-16.3", "dafpage", "words"], 1.2),
  // three 30-second cuts, each with its own features
  calm30study: edit(["outline", "chart@0.8-11.6", "illustration"], 1.2, 2.2, 5.0),
  calm30reference: edit(["reference@0.3-5.6", "sages", "words"], 1.25, 2.2, 5.0),
  calm30practice: edit(["quiz@0.5-16.3", "textsync", "linesync"], 1.25, 2.2, 5.0),
};
