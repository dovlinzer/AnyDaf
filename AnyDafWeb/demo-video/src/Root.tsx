import React from "react";
import { Composition } from "remotion";
import { Demo, EDITS } from "./Demo";
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
  </>
);
