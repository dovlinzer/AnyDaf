import React from "react";
import { AbsoluteFill, Audio, Img, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame, Easing } from "remotion";
import { END_S, FPS, Key, SCENES, SRC, Scene, Seg, TITLE_S, VOICE_IN, XFADE, fitToVoice, sceneFrames, segFrames } from "./cut";
import VOICE from "../public/voice/durations.json";
import { SCENES90 } from "./cut90";

export const EDITS: Record<string, Scene[]> = { "45": SCENES, "90": SCENES90 };
// an edit with narration: the 90-second cut fitted to the voice
export const voiced = (edit: string) => fitToVoice(EDITS[edit], VOICE as Record<string, number>);

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
const Caption: React.FC<{ scene: Scene; text: string; first: boolean; last: boolean; fmt: Format; total: number }> = ({ scene, text, first, last, fmt, total }) => {
  const f = useCurrentFrame();
  const inn = interpolate(f, first ? [4, 18] : [0, 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const out = interpolate(f, [total - (last ? 10 : 6), total], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const kick = first ? inn * (last ? out : 1) : last ? out : 1;
  if (fmt === "tall") {
    return (
      <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: TALL_CAP, background: NAVY, color: "white", padding: "70px 64px 0", boxSizing: "border-box", fontFamily: SANS }}>
        <div style={{ color: AMBER, fontWeight: 700, letterSpacing: 3, fontSize: 30, textTransform: "uppercase", marginBottom: 16, opacity: kick }}>{scene.kicker}</div>
        <div style={{ fontSize: text.length > 90 ? 42 : 48, lineHeight: 1.22, fontWeight: 600, opacity: inn * out, transform: `translateY(${(1 - inn) * 14}px)` }}>{text}</div>
      </div>
    );
  }
  return (
    <div style={{ position: "absolute", left: 56, bottom: 52, maxWidth: 1180, opacity: kick, transform: `translateY(${(1 - (first ? inn : 1)) * 24}px)`, fontFamily: SANS }}>
      <div style={{ background: "rgba(27,58,138,.96)", color: "white", borderRadius: 20, padding: "24px 34px 26px", boxShadow: "0 12px 40px rgba(10,20,60,.35)" }}>
        <div style={{ color: AMBER, fontWeight: 700, letterSpacing: 2.5, fontSize: 22, textTransform: "uppercase", marginBottom: 8 }}>{scene.kicker}</div>
        <div style={{ fontSize: text.length > 90 ? 34 : 38, lineHeight: 1.25, fontWeight: 600, opacity: first ? (last ? 1 : out) : inn * out }}>{text}</div>
      </div>
    </div>
  );
};

const SceneView: React.FC<{ scene: Scene; fmt: Format; W: number; H: number }> = ({ scene, fmt, W, H }) => {
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
        return <Sequence key={"c" + i} from={from} durationInFrames={len}><Caption scene={scene} text={text} first={i === 0} last={j === n} fmt={fmt} total={len} /></Sequence>; })}
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

const EndCard: React.FC<{ fmt: Format }> = ({ fmt }) => {
  const f = useCurrentFrame(), tall = fmt === "tall";
  const a = interpolate(f, [XFADE, XFADE + 16], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  return (
    <AbsoluteFill style={{ background: NAVY, alignItems: "center", justifyContent: "center", color: "white", fontFamily: SANS, textAlign: "center" }}>
      <Img src={staticFile("brand/yct-logo-white.png")} style={{ width: tall ? 340 : 280, opacity: a, marginBottom: tall ? 80 : 46 }} />
      <div style={{ fontFamily: SERIF, fontSize: tall ? 64 : 56, opacity: a }}>Learn the daf at</div>
      <div style={{ fontSize: tall ? 116 : 112, fontWeight: 700, letterSpacing: -1, marginTop: 10, opacity: a, transform: `scale(${0.95 + 0.05 * a})` }}>italmud.com</div>
      <div style={{ position: "absolute", bottom: tall ? 110 : 48, left: 60, right: 60, fontSize: tall ? 26 : 22, opacity: 0.75 * a, lineHeight: 1.4 }}>
        English translation: The William Davidson Talmud (CC BY-NC), via Sefaria
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
  const V = voice ? voiced(edit) : null;
  const SC = V ? V.scenes : EDITS[edit], titleS = V ? V.titleS : TITLE_S, endS = V ? V.endS : END_S;
  const pieces: { len: number; el: React.ReactNode; id: string }[] = [
    { len: Math.round(titleS * FPS), el: <TitleCard fmt={fmt} />, id: "title" },
    ...SC.map((s, i) => ({ len: sceneFrames(s), el: <SceneView scene={s} fmt={fmt} W={W} H={H} />, id: "s" + (i + 1) })),
    { len: Math.round(endS * FPS), el: <EndCard fmt={fmt} />, id: "end" },
  ];
  let at = 0;
  return (
    <AbsoluteFill style={{ background: CREAM }}>
      {pieces.map((p, i) => { const from = i === 0 ? 0 : at - XFADE; at = from + p.len;
        const vin = Math.round((p.id === "title" ? 0.3 : p.id === "end" ? 0.4 : VOICE_IN) * FPS);
        return <React.Fragment key={i}>
          <Sequence from={from} durationInFrames={p.len}>{i === 0 ? p.el : <FadeIn>{p.el}</FadeIn>}</Sequence>
          {voice && <Sequence from={from + vin}><Audio src={staticFile(`voice/${p.id}.wav`)} /></Sequence>}
        </React.Fragment>; })}
    </AbsoluteFill>
  );
};
