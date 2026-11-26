// The edit: which parts of each take play, how fast, what the camera frames, and the captions.
//
// Times are in seconds of the take (the clip). Camera keyframes are in the page's CSS pixels: the takes were
// recorded at 1600x900 CSS (3200x1800 video), and a keyframe {t, x, y, w} frames a box centred on (x, y),
// w CSS pixels wide (its height follows the format's aspect). Between keyframes the camera eases.

export const FPS = 30;
export const SRC = { w: 1600, h: 900, scale: 2 };   // CSS size of the takes, and video pixels per CSS pixel

export type Seg = { from: number; to: number; rate: number; note?: string };   // note: the caption while it plays (else the scene's)
export type Key = { t: number; x: number; y: number; w: number };
export type Scene = {
  clip: string;
  kicker: string;
  caption: string;
  segs: Seg[];
  wide: Key[];   // 16:9
  tall: Key[];   // 9:16 (the video window under the caption)
};

const FULL = (t: number): Key => ({ t, x: 800, y: 450, w: 1600 });

export const SCENES: Scene[] = [
  {
    clip: "s1_outline",
    kicker: "The study outline",
    caption: "Every daf, organized: a study outline from the first line to a summary at the end.",
    segs: [{ from: 1.4, to: 7.6, rate: 1.6 }, { from: 8.6, to: 13.4, rate: 1.7 }],
    wide: [FULL(1.4), FULL(2.4), { t: 3.6, x: 470, y: 330, w: 980 }, { t: 8.0, x: 470, y: 330, w: 980 }, FULL(9.4), FULL(10.4), { t: 11.4, x: 450, y: 300, w: 940 }],
    tall: [{ t: 1.4, x: 300, y: 330, w: 600 }, { t: 2.6, x: 300, y: 330, w: 600 }, { t: 3.6, x: 300, y: 420, w: 600 }, { t: 9.0, x: 300, y: 420, w: 600 }, { t: 10.6, x: 300, y: 380, w: 600 }],
  },
  {
    clip: "s2_visuals",
    kicker: "Charts & illustrations",
    caption: "The sugya at a glance: illustrations and charts of every case.",
    segs: [{ from: 0.6, to: 3.6, rate: 1.2 }, { from: 3.6, to: 6.2, rate: 1.7 }, { from: 6.2, to: 9.6, rate: 1.3 }],
    wide: [{ t: 0.6, x: 470, y: 470, w: 1000 }, { t: 3.6, x: 470, y: 470, w: 1000 }, { t: 5.6, x: 520, y: 470, w: 1000 }, { t: 9.6, x: 540, y: 470, w: 900 }],
    tall: [{ t: 0.6, x: 463, y: 383, w: 870 }, { t: 3.6, x: 463, y: 383, w: 870 }, { t: 5.4, x: 476, y: 380, w: 750 }, { t: 9.6, x: 476, y: 380, w: 750 }],
  },
  {
    clip: "s3_reference",
    kicker: "Terms, sages, measures",
    caption: "Every term, every sage, every measure, a tap away.",
    segs: [{ from: 2.2, to: 6.4, rate: 1.8 }, { from: 8.2, to: 12.4, rate: 2.0 }, { from: 12.4, to: 16.4, rate: 1.6 }, { from: 19.2, to: 22.8, rate: 1.6 }],
    wide: [FULL(2.2), { t: 3.4, x: 1100, y: 280, w: 1100 }, { t: 6.4, x: 1100, y: 280, w: 1100 }, { t: 8.6, x: 1050, y: 380, w: 1150 }, { t: 12.4, x: 1050, y: 380, w: 1150 }, { t: 13.2, x: 700, y: 520, w: 1300 }, { t: 16.4, x: 700, y: 520, w: 1300 }, { t: 19.2, x: 820, y: 330, w: 1250 }, { t: 22.8, x: 820, y: 330, w: 1150 }],
    tall: [{ t: 2.2, x: 300, y: 300, w: 600 }, { t: 3.4, x: 1385, y: 365, w: 440 }, { t: 6.4, x: 1385, y: 365, w: 440 }, { t: 8.4, x: 1271, y: 429, w: 600 }, { t: 12.4, x: 1271, y: 429, w: 600 }, { t: 13.2, x: 800, y: 300, w: 720 }, { t: 16.4, x: 800, y: 300, w: 720 }, { t: 19.2, x: 800, y: 268, w: 820 }, { t: 22.8, x: 800, y: 268, w: 820 }],
  },
  {
    clip: "s4_quiz",
    kicker: "Quizzes & games",
    caption: "Test yourself, then see each answer in the outline and on the daf.",
    segs: [{ from: 2.6, to: 5.4, rate: 1.6 }, { from: 8.2, to: 11.4, rate: 1.4 }, { from: 11.6, to: 14.2, rate: 1.6 }, { from: 15.6, to: 20.4, rate: 1.6 }],
    wide: [FULL(2.6), { t: 4.6, x: 1180, y: 300, w: 1150 }, { t: 11.4, x: 1180, y: 300, w: 1150 }, { t: 12.4, x: 800, y: 450, w: 1600 }, { t: 16.0, x: 800, y: 450, w: 1600 }, { t: 17.6, x: 1000, y: 380, w: 1250 }, { t: 20.4, x: 1000, y: 380, w: 1250 }],
    tall: [{ t: 2.6, x: 1380, y: 300, w: 600 }, { t: 4.2, x: 1207, y: 417, w: 680 }, { t: 11.4, x: 1207, y: 417, w: 680 }, { t: 12.2, x: 330, y: 400, w: 680 }, { t: 15.6, x: 330, y: 400, w: 680 }, { t: 17.0, x: 1265, y: 420, w: 660 }, { t: 20.4, x: 1265, y: 420, w: 660 }],
  },
  {
    clip: "s5_sync",
    kicker: "Outline and Talmud in step",
    caption: "Outline and Talmud move together, on the text and on the daf, with sources in the margin.",
    segs: [{ from: 2.4, to: 4.8, rate: 1.4 }, { from: 5.4, to: 8.8, rate: 1.5 }, { from: 10.4, to: 13.0, rate: 1.4 }, { from: 14.2, to: 16.8, rate: 1.4 }, { from: 17.8, to: 21.6, rate: 1.6 }],
    wide: [FULL(2.4), FULL(8.8), FULL(10.4), { t: 11.6, x: 1180, y: 450, w: 1000 }, { t: 16.8, x: 1180, y: 450, w: 1000 }, { t: 18.6, x: 800, y: 450, w: 1150 }, { t: 21.6, x: 800, y: 450, w: 1100 }],
    tall: [{ t: 2.4, x: 300, y: 300, w: 600 }, { t: 3.6, x: 300, y: 300, w: 600 }, { t: 4.4, x: 1150, y: 450, w: 640 }, { t: 4.8, x: 1150, y: 450, w: 640 }, { t: 5.4, x: 1150, y: 450, w: 640 }, { t: 6.8, x: 1150, y: 450, w: 640 }, { t: 7.6, x: 330, y: 450, w: 640 }, { t: 8.8, x: 330, y: 450, w: 640 }, { t: 10.4, x: 1265, y: 500, w: 660 }, { t: 16.8, x: 1265, y: 500, w: 660 }, { t: 18.2, x: 800, y: 450, w: 680 }, { t: 21.6, x: 800, y: 450, w: 680 }],
  },
];

export const TITLE_S = 2.6;
export const END_S = 5.6;   // the end card's words fade in one by one (END_BEATS in Demo.tsx), then hold
export const XFADE = 8;   // frames of cross-fade between scenes

export const segFrames = (g: Seg) => Math.round(((g.to - g.from) / g.rate) * FPS);
export const sceneFrames = (s: Scene) => s.segs.reduce((n, g) => n + segFrames(g), 0);
export const totalFrames = (scenes: Scene[] = SCENES, titleS = TITLE_S, endS = END_S) =>
  Math.round(titleS * FPS) + scenes.reduce((n, s) => n + sceneFrames(s), 0) + Math.round(endS * FPS) - XFADE * (scenes.length + 1);

// ---------- narration ----------
// public/voice/<id>.wav, one per piece (title, s1..sN, end), and their lengths in public/voice/durations.json.
// Each scene's voice starts VOICE_IN after the scene does; a scene too short for its line is slowed down to fit.
export const VOICE_IN = 0.35, VOICE_PAD = 0.5;
export type Voiced = { scenes: Scene[]; titleS: number; endS: number; ids: string[] };
export function fitToVoice(scenes: Scene[], dur: Record<string, number>): Voiced {
  const ids = scenes.map((_, i) => "s" + (i + 1));
  const fitted = scenes.map((s, i) => {
    const need = VOICE_IN + (dur[ids[i]] || 0) + VOICE_PAD, have = sceneFrames(s) / FPS;
    if (have >= need) return s;
    const k = have / need;   // slow every stretch of the scene by the same factor
    return { ...s, segs: s.segs.map((g) => ({ ...g, rate: g.rate * k })) };
  });
  return { scenes: fitted, titleS: Math.max(TITLE_S, 0.3 + (dur.title || 0) + 0.6), endS: Math.max(END_S, (dur.end || 0) + 1.4), ids };
}
