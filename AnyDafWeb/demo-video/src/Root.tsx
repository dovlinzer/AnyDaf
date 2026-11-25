import React from "react";
import { Composition } from "remotion";
import { Demo } from "./Demo";
import { FPS, totalFrames } from "./cut";

export const Root: React.FC = () => (
  <>
    <Composition id="Demo16x9" component={Demo} durationInFrames={totalFrames()} fps={FPS} width={1920} height={1080} defaultProps={{ fmt: "wide" as const, W: 1920, H: 1080 }} />
    <Composition id="Demo9x16" component={Demo} durationInFrames={totalFrames()} fps={FPS} width={1080} height={1920} defaultProps={{ fmt: "tall" as const, W: 1080, H: 1920 }} />
  </>
);
