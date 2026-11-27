import React from "react";
import { AbsoluteFill, Audio, Img, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame, Easing } from "remotion";
import { END_S, FPS, Key, SCENES, SRC, Scene, Seg, TITLE_S, VOICE_IN, XFADE, fitToVoice, sceneFrames, segFrames } from "./cut";
import VOICE from "../public/voice/durations.json";
import VOICE_CALM90 from "../public/voice/calm90/durations.json";
import VOICE_CALM120 from "../public/voice/calm120/durations.json";
import { SCENES90 } from "./cut90";
import { CALM } from "./calm";
import { FEAT_ADD, FEAT_VOICE_IN, layout } from "./pieces";

export const EDITS: Record<string, Scene[]> = { "45": SCENES, "90": SCENES90, ...Object.fromEntries(Object.entries(CALM).map(([k, e]) => [k, e.scenes])) };
export const cardsOf = (edit: string) => (CALM[edit] ? { titleS: CALM[edit].titleS, endS: CALM[edit].endS } : { titleS: TITLE_S, endS: END_S });
// an edit with narration: the 90-second cut fitted to the voice
// each narrated edit has its own recordings: public/voice/<dir>/<id>.wav
// endBeats: when the recorded end line says each word (voice/import.py finds them), so the card shows each as it is said
const vo = (dir: string, j: Record<string, unknown>) => { const { end_beats, ...dur } = j; return { dir, dur: dur as Record<string, number>, endBeats: end_beats as number[] | undefined }; };
export const VOICES: Record<string, { dir: string; dur: Record<string, number>; endBeats?: number[] }> = {
  "90": vo("voice", VOICE), calm90: vo("voice/calm90", VOICE_CALM90), calm120: vo("voice/calm120", VOICE_CALM120) };
export const featuresOf = (edit: string) => !!CALM[edit]?.features;
// the whole timeline of an edit (silent or voiced): pieces and total frames
export const timeline = (edit: string, voice = false) => {
  const V = voice ? voiced(edit) : null, C0 = cardsOf(edit);
  return layout(V ? V.scenes : EDITS[edit], V ? V.titleS : C0.titleS, V ? V.endS : C0.endS, featuresOf(edit), V ? VOICES[edit].dur : {});
};
export const voiced = (edit: string) => {
  const v = fitToVoice(EDITS[edit], VOICES[edit].dur);
  return CALM[edit] ? { ...v, titleS: Math.max(CALM[edit].titleS, v.titleS), endS: Math.max(CALM[edit].endS, v.endS) } : v;
};

export type Format = "wide" | "tall";
const NAVY = "#1B3A8A", AMBER = "#E8A020", CREAM = "#F7F3EA", INK = "#1d2433";
const SERIF = "'Iowan Old Style', 'Palatino Linotype', Palatino, Georgia, serif";
const SANS = "-apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif";
const TALL_CAP = 360;   // height of the caption panel above the video in 9:16

// ---------- the camera ----------
const smooth = (t: number) => t * t * (3 - 2 * t);
function camAt(keys: Key[], t: number): Key {
  if (t <= keys[0].t) return keys[0];
  for (let i = 1; i < keys.length; i++) {
    const a = keys[i - 1], b = keys[i];
    if (t <= b.t) { const u = smooth((t - a.t) / Math.max(1e-6, b.t - a.t)); return { t, x: a.x + (b.x - a.x) * u, y: a.y + (b.y - a.y) * u, w: a.w + (b.w - a.w) * u }; }
  }
  return keys[keys.length - 1];
}

// One stretch of a take: plays from seg.from at seg.rate, framed by the camera into a W x H window.
const Shot: React.FC<{ clip: string; seg: Seg; keys: Key[]; W: number; H: number }> = ({ clip, seg, keys, W, H }) => {
  const f = useCurrentFrame();
  const t = seg.from + (f / FPS) * seg.rate;
  const c = camAt(keys, t);
  const w = Math.min(SRC.w, c.w), k = W / w;              // screen pixels per CSS pixel
  const visH = H / k;                                     // CSS pixels of height the window shows
  const left = Math.max(0, Math.min(SRC.w - w, c.x - w / 2));
  const top = visH >= SRC.h ? -(visH - SRC.h) / 2 : Math.max(0, Math.min(SRC.h - visH, c.y - visH / 2));
  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", background: CREAM }}>
      <OffthreadVideo
        src={staticFile(`clips/${clip}.mp4`)}
        trimBefore={Math.round(seg.from * FPS)}
        playbackRate={seg.rate}
        muted
        style={{ position: "absolute", width: SRC.w * k, height: SRC.h * k, left: -left * k, top: -top * k, boxShadow: "0 0 40px rgba(0,0,0,.12)" }}
      />
    </div>
  );
};

// ---------- captions ----------
// kicker: the scene's label (it fades in only with the scene); text: the caption, which can change per segment
const Caption: React.FC<{ scene: Scene; text: string; first: boolean; last: boolean; fmt: Format; total: number; contIn?: boolean; contOut?: boolean }> = ({ scene, text, first, last, fmt, total, contIn, contOut }) => {
  const f = useCurrentFrame();
  const inn = interpolate(f, first ? [4, 18] : [0, 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const out = interpolate(f, [total - (last ? 10 : 6), total], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  let kick = first ? inn * (last ? out : 1) : last ? out : 1;
  if (contIn || contOut) kick = (first && !contIn ? inn : 1) * (last && !contOut ? out : 1);
  const boxIn = first && !contIn;   // the box (not the text) slides in
  if (fmt === "tall") {
    return (
      <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: TALL_CAP, background: NAVY, color: "white", padding: "70px 64px 0", boxSizing: "border-box", fontFamily: SANS }}>
        <div style={{ color: AMBER, fontWeight: 700, letterSpacing: 3, fontSize: 30, textTransform: "uppercase", marginBottom: 16, opacity: kick }}>{scene.kicker}</div>
        <div style={{ fontSize: text.length > 90 ? 42 : 48, lineHeight: 1.22, fontWeight: 600, opacity: inn * out, transform: `translateY(${(1 - inn) * 14}px)` }}>{text}</div>
      </div>
    );
  }
  return (
    <div style={{ position: "absolute", left: 56, bottom: 52, maxWidth: 1180, opacity: kick, transform: `translateY(${(1 - (boxIn ? inn : 1)) * 24}px)`, fontFamily: SANS }}>
      <div style={{ background: "rgba(27,58,138,.96)", color: "white", borderRadius: 20, padding: "24px 34px 26px", boxShadow: "0 12px 40px rgba(10,20,60,.35)" }}>
        <div style={{ color: AMBER, fontWeight: 700, letterSpacing: 2.5, fontSize: 22, textTransform: "uppercase", marginBottom: 8 }}>{scene.kicker}</div>
        <div style={{ fontSize: text.length > 90 ? 34 : 38, lineHeight: 1.25, fontWeight: 600, opacity: (contIn || contOut) ? inn * out : first ? (last ? 1 : out) : inn * out }}>{text}</div>
      </div>
    </div>
  );
};

const SceneView: React.FC<{ scene: Scene; fmt: Format; W: number; H: number; contIn?: boolean; contOut?: boolean }> = ({ scene, fmt, W, H, contIn, contOut }) => {
  const top = fmt === "tall" ? TALL_CAP : 0, vh = H - top;
  let at = 0;
  return (
    <AbsoluteFill style={{ background: CREAM }}>
      <div style={{ position: "absolute", left: 0, top, width: W, height: vh, overflow: "hidden" }}>
        {scene.segs.map((g, i) => { const from = at; at += segFrames(g);
          return <Sequence key={i} from={from} durationInFrames={segFrames(g)}><Shot clip={scene.clip} seg={g} keys={fmt === "tall" ? scene.tall : scene.wide} W={W} H={vh} /></Sequence>; })}
      </div>
      {scene.segs.map((g, i) => { const from = scene.segs.slice(0, i).reduce((n, x) => n + segFrames(x), 0), n = scene.segs.length;
        const text = g.note || scene.caption, same = (j: number) => (scene.segs[j].note || scene.caption) === text;
        // a caption that runs on unchanged into the next segment is drawn once across both
        if (i > 0 && same(i - 1)) return null;
        let len = segFrames(g), j = i + 1; while (j < n && same(j)) { len += segFrames(scene.segs[j]); j++; }
        return <Sequence key={"c" + i} from={from} durationInFrames={len}><Caption scene={scene} text={text} first={i === 0} last={j === n} fmt={fmt} total={len} contIn={i === 0 && contIn} contOut={j === n && contOut} /></Sequence>; })}
    </AbsoluteFill>
  );
};

// ---------- title and end cards ----------
const TitleCard: React.FC<{ fmt: Format }> = ({ fmt }) => {
  const f = useCurrentFrame(), tall = fmt === "tall";
  const a = interpolate(f, [0, 16], [0, 1], { extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const b = interpolate(f, [10, 28], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  return (
    <AbsoluteFill style={{ background: CREAM, alignItems: "center", justifyContent: "center", fontFamily: SERIF, color: NAVY, textAlign: "center" }}>
      <Img src={staticFile("brand/yct-logo-color.png")} style={{ width: tall ? 380 : 330, opacity: a, transform: `translateY(${(1 - a) * 20}px)`, marginBottom: tall ? 70 : 44 }} />
      <div style={{ fontSize: tall ? 150 : 150, fontWeight: 600, letterSpacing: -2, opacity: a, transform: `scale(${0.94 + 0.06 * a})` }}>iTalmud</div>
      <div style={{ fontSize: tall ? 62 : 58, fontStyle: "italic", marginTop: 6, opacity: b, color: INK }}>The Illustrated Talmud</div>
      <div style={{ width: 120, height: 4, background: AMBER, marginTop: tall ? 56 : 40, opacity: b, borderRadius: 2 }} />
    </AbsoluteFill>
  );
};

// The end card: "The Talmud" / Explicated. / Annotated. / Illustrated. / iTalmud.com, each fading in on its own beat
// (END_BEATS, seconds into the card; the draft narration speaks each word as it appears).
export const END_BEATS = [0.45, 1.3, 2.1, 2.9, 3.8];
const END_VOICE_IN = 0.4;   // the end line starts this far into the card
const EndCard: React.FC<{ fmt: Format; beats?: number[] }> = ({ fmt, beats = END_BEATS }) => {
  const f = useCurrentFrame(), tall = fmt === "tall";
  const fade = (t: number) => interpolate(f, [t * FPS, t * FPS + 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const a = interpolate(f, [XFADE, XFADE + 16], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const [t0, ...tw] = beats, words = ["Explicated.", "Annotated.", "Illustrated."];
  const rise = (t: number) => ({ opacity: fade(t), transform: `translateY(${(1 - fade(t)) * 14}px)` });
  return (
    <AbsoluteFill style={{ background: NAVY, alignItems: "center", justifyContent: "center", color: "white", fontFamily: SANS, textAlign: "center" }}>
      <Img src={staticFile("brand/yct-logo-white.png")} style={{ width: tall ? 320 : 250, opacity: a, marginBottom: tall ? 70 : 40 }} />
      <div style={{ fontFamily: SERIF, fontSize: tall ? 84 : 72, fontWeight: 600, ...rise(t0) }}>The Talmud</div>
      <div style={{ display: "flex", flexDirection: tall ? "column" : "row", gap: tall ? 6 : 44, marginTop: tall ? 18 : 10, fontFamily: SERIF, fontStyle: "italic", fontSize: tall ? 74 : 62, color: "#F4D58A" }}>
        {words.map((w, i) => <div key={w} style={rise(tw[i])}>{w}</div>)}
      </div>
      <div style={{ fontSize: tall ? 112 : 104, fontWeight: 700, letterSpacing: -1, marginTop: tall ? 56 : 36, ...rise(tw[3]) }}>iTalmud.com</div>
      <div style={{ position: "absolute", bottom: tall ? 110 : 48, left: 60, right: 60, fontSize: tall ? 26 : 22, opacity: 0.75 * a, lineHeight: 1.4 }}>
        English translation: The William Davidson Talmud (CC BY-NC), via Sefaria
      </div>
    </AbsoluteFill>
  );
};

// ---------- the Features card ----------
// "Features", then the list so far; the newest line fades in (adding), or the whole list shows (the recap)
const FeaturesCard: React.FC<{ fmt: Format; items: string[]; shown: number; adding: boolean }> = ({ fmt, items, shown, adding }) => {
  const f = useCurrentFrame(), tall = fmt === "tall";
  const t0 = Math.round(FEAT_ADD * FPS);
  const add = adding ? interpolate(f, [t0, t0 + 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) }) : 1;
  const fs = tall ? 60 : 54, gap = tall ? 30 : 18;
  return (
    <AbsoluteFill style={{ background: CREAM, alignItems: "center", justifyContent: "center", fontFamily: SERIF, color: NAVY }}>
      <div style={{ width: tall ? 860 : 1100 }}>
        <div style={{ fontSize: tall ? 110 : 96, fontWeight: 600, letterSpacing: -1 }}>Features</div>
        <div style={{ width: 120, height: 4, background: AMBER, margin: tall ? "28px 0 56px" : "18px 0 40px", borderRadius: 2 }} />
        {/* every line is laid out from the start, so adding one never moves the others */}
        {items.map((it, i) => {
          const isNew = adding && i === shown - 1, vis = i < shown ? (isNew ? add : 1) : 0;
          const past = adding && i < shown - 1;
          return (
            <div key={it} style={{ display: "flex", alignItems: "baseline", gap: 22, fontSize: fs, lineHeight: 1.15, marginBottom: gap,
              opacity: vis * (past ? 0.5 : 1), transform: `translateX(${(1 - vis) * 24}px)`, fontWeight: isNew ? 600 : 500 }}>
              <span style={{ color: AMBER, fontFamily: SANS, fontWeight: 700, fontSize: fs * 0.8, minWidth: fs * 0.9, textAlign: "right" }}>{i + 1}.</span>
              <span>{it}</span>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// a cross-fade in at the start of each piece after the first
const FadeIn: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const f = useCurrentFrame();
  return <AbsoluteFill style={{ opacity: interpolate(f, [0, XFADE], [0, 1], { extrapolateRight: "clamp" }) }}>{children}</AbsoluteFill>;
};

export const Demo: React.FC<{ fmt: Format; W: number; H: number; edit?: string; voice?: boolean }> = ({ fmt, W, H, edit = "45", voice = false }) => {
  const { pieces } = timeline(edit, voice);
  const dur: Record<string, number> = voice ? VOICES[edit].dur : {};
  const el = (p: (typeof pieces)[number]) =>
    p.kind === "title" ? <TitleCard fmt={fmt} /> :
    p.kind === "end" ? <EndCard fmt={fmt} beats={voice && VOICES[edit].endBeats ? VOICES[edit].endBeats!.map((b) => END_VOICE_IN - 0.1 + b) : undefined} /> :
    p.kind === "features" ? <FeaturesCard fmt={fmt} items={p.features!} shown={p.shown!} adding={!!p.adding} /> :
    <SceneView scene={p.scene!} fmt={fmt} W={W} H={H} contIn={p.contIn} contOut={p.contOut} />;
  return (
    <AbsoluteFill style={{ background: CREAM }}>
      {pieces.map((p, i) => {
        const vin = Math.round((p.kind === "title" ? 0.3 : p.kind === "end" ? END_VOICE_IN : p.kind === "features" ? FEAT_VOICE_IN : VOICE_IN) * FPS);
        return <React.Fragment key={i}>
          <Sequence from={p.from} durationInFrames={p.len}>{i === 0 ? el(p) : <FadeIn>{el(p)}</FadeIn>}</Sequence>
          {voice && (dur[p.id] || 0) > 0 && <Sequence from={p.from + vin}><Audio src={staticFile(`${VOICES[edit].dir}/${p.id}.wav`)} /></Sequence>}
        </React.Fragment>; })}
    </AbsoluteFill>
  );
};
