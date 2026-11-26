import React from "react";
import { Composition } from "remotion";
import { Demo, EDITS, cardsOf, voiced } from "./Demo";
import { CALM } from "./calm";
import { FPS, totalFrames } from "./cut";

// 45 s (Demo16x9 / Demo9x16) and 90 s (Demo90-16x9 / Demo90-9x16) versions
export const Root: React.FC = () => (
  <>
    {(["45", "90"] as const).map((e) => {
      const n = totalFrames(EDITS[e]), id = e === "45" ? "Demo" : "Demo90-";
      return (
        <React.Fragment key={e}>
          <Composition id={`${id}${e === "45" ? "" : ""}16x9`} component={Demo} durationInFrames={n} fps={FPS} width={1920} height={1080} defaultProps={{ fmt: "wide" as const, W: 1920, H: 1080, edit: e }} />
          <Composition id={`${id}9x16`} component={Demo} durationInFrames={n} fps={FPS} width={1080} height={1920} defaultProps={{ fmt: "tall" as const, W: 1080, H: 1920, edit: e }} />
        </React.Fragment>
      );
    })}
    {/* the calm cuts: calm90-16x9, calm60-9x16, calm30study-16x9, ... */}
    {Object.keys(CALM).map((e) => { const c = cardsOf(e), n = totalFrames(EDITS[e], c.titleS, c.endS); return (
      <React.Fragment key={e}>
        <Composition id={`${e}-16x9`} component={Demo} durationInFrames={n} fps={FPS} width={1920} height={1080} defaultProps={{ fmt: "wide" as const, W: 1920, H: 1080, edit: e }} />
        <Composition id={`${e}-9x16`} component={Demo} durationInFrames={n} fps={FPS} width={1080} height={1920} defaultProps={{ fmt: "tall" as const, W: 1080, H: 1920, edit: e }} />
      </React.Fragment>); })}
    {/* calm90 with narration (public/voice/calm90) */}
    {(() => { const V = voiced("calm90"), n = totalFrames(V.scenes, V.titleS, V.endS); return (<>
      <Composition id="calm90v-16x9" component={Demo} durationInFrames={n} fps={FPS} width={1920} height={1080} defaultProps={{ fmt: "wide" as const, W: 1920, H: 1080, edit: "calm90", voice: true }} />
      <Composition id="calm90v-9x16" component={Demo} durationInFrames={n} fps={FPS} width={1080} height={1920} defaultProps={{ fmt: "tall" as const, W: 1080, H: 1920, edit: "calm90", voice: true }} />
    </>); })()}
    {/* the 90-second cut with narration (public/voice) */}
    {(() => { const V = voiced("90"), n = totalFrames(V.scenes, V.titleS, V.endS); return (<>
      <Composition id="Demo90v-16x9" component={Demo} durationInFrames={n} fps={FPS} width={1920} height={1080} defaultProps={{ fmt: "wide" as const, W: 1920, H: 1080, edit: "90", voice: true }} />
      <Composition id="Demo90v-9x16" component={Demo} durationInFrames={n} fps={FPS} width={1080} height={1920} defaultProps={{ fmt: "tall" as const, W: 1080, H: 1920, edit: "90", voice: true }} />
    </>); })()}
  </>
);
