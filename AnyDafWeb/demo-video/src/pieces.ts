// The order of an edit's pieces (title, Features cards, scenes, end) and where each starts, shared by the
// video (Demo.tsx), the compositions' lengths (Root.tsx) and the chapter markers (tools/chapters.mjs).
import { FPS, Scene, XFADE, sceneFrames } from "./cut";

// The Features card's list: one line per kicker, in the order the scenes first reach it
export const FEATURE_LABEL: Record<string, string> = {
  "Outline and Talmud in step": "Outline and Talmud in Step",
  "Terms, sages, measures": "Terms, Sages, Measures",
  "Charts & illustrations": "Charts & Illustrations",
  "Quizzes & games": "Quizzes & Games",
};
export const featureLabel = (kicker: string) => FEATURE_LABEL[kicker] || kicker;

export const FEAT_S = 2.1;        // a Features card that adds a line (the line fades in at FEAT_ADD)
export const FEAT_ADD = 0.55;
export const FEAT_ALL_S = 2.8;    // the whole list once more, after the last feature

export type Piece = {
  kind: "title" | "topic" | "scene" | "features" | "end";
  id: string;            // voice file id: title, s1.., f1.., end
  len: number;           // frames
  from: number;          // first frame (pieces after the first overlap the one before by XFADE)
  scene?: Scene; contIn?: boolean; contOut?: boolean;
  features?: string[]; shown?: number; adding?: boolean; topic?: string;   // Features card: the list, lines shown, last one fading in
  chapter?: string;      // a chapter starts here
};

// voice: the narration's line lengths; a Features card stretches to fit its line (FEAT_VOICE_IN after the card starts)
export const FEAT_VOICE_IN = 0.25;
export const TOPIC_S = 2.2;   // the card naming a short cut's part of the whole
export function layout(scenes: Scene[], titleS: number, endS: number, features = false, voice: Record<string, number> = {}, topic?: string): { pieces: Piece[]; total: number } {
  const featLen = (id: string, s: number) => Math.round(Math.max(s, voice[id] ? FEAT_VOICE_IN + voice[id] + 0.45 : 0) * FPS);
  const groups: string[] = [];
  if (features) scenes.forEach((s) => { if (!groups.includes(s.kicker)) groups.push(s.kicker); });
  const labels = groups.map(featureLabel);
  const out: Omit<Piece, "from">[] = [{ kind: "title", id: "title", len: Math.round(titleS * FPS), chapter: "iTalmud" }];
  if (topic) out.push({ kind: "topic", id: "topic", len: Math.round(Math.max(TOPIC_S, voice.topic ? FEAT_VOICE_IN + voice.topic + 0.45 : 0) * FPS), topic });
  let f = 0;
  scenes.forEach((s, i) => {
    const prev = scenes[i - 1], next = scenes[i + 1];
    if (features && (!prev || prev.kicker !== s.kicker)) {
      const n = groups.indexOf(s.kicker) + 1;
      f++; out.push({ kind: "features", id: "f" + f, len: featLen("f" + f, FEAT_S), features: labels, shown: n, adding: true, chapter: `${n}. ${labels[n - 1]}` });
    }
    out.push({ kind: "scene", id: "s" + (i + 1), len: sceneFrames(s), scene: s,
      contIn: !!prev && prev.kicker === s.kicker, contOut: !!next && next.kicker === s.kicker });
  });
  if (features) { f++; out.push({ kind: "features", id: "f" + f, len: featLen("f" + f, FEAT_ALL_S), features: labels, shown: labels.length, adding: false, chapter: "Features" }); }
  out.push({ kind: "end", id: "end", len: Math.round(endS * FPS) });
  let at = 0;
  const pieces = out.map((p, i) => { const from = i === 0 ? 0 : at - XFADE; at = from + p.len; return { ...p, from }; });
  return { pieces, total: at };
}
