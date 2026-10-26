import { loadFont as loadFredoka } from "@remotion/google-fonts/Fredoka";
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import React from "react";
import {
  AbsoluteFill, Audio, interpolate, OffthreadVideo, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig,
} from "remotion";
import { CUTS, Cut, END, FOLEY_VOLUME, FPS, INTRO, MUSIC, ROOM_TONE, SFX } from "./stealth-edit";

const { fontFamily: ROUND } = loadFredoka("normal", { weights: ["500", "700"], subsets: ["latin"] });
const { fontFamily: BODY } = loadInter("normal", { weights: ["400", "600"], subsets: ["latin"] });

const f = (s: number) => Math.round(s * FPS);
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const CREAM = "#fff7ea";
const SUN = "#ffb347";

// ── cards ─────────────────────────────────────────────────────────────────────

const Typed: React.FC<{ text: string; start: number; per: number; size: number; color: string }> = (
  { text, start, per, size, color },
) => {
  const t = useCurrentFrame() / FPS;
  const n = Math.max(0, Math.min(text.length, Math.floor((t - start) / per) + 1));
  return <div style={{ fontFamily: ROUND, fontWeight: 700, fontSize: size, color, letterSpacing: "0.08em" }}>
    {t >= start ? text.slice(0, n) : "\u00a0"}</div>;
};

const Intro: React.FC = () => (
  <AbsoluteFill style={{ background: "#05070d", justifyContent: "center", alignItems: "center", flexDirection: "column",
    gap: 18 }}>
    <Typed text={INTRO[0].text} start={INTRO[0].start} per={0.045} size={110} color={CREAM} />
    <Typed text={INTRO[1].text} start={INTRO[1].start} per={0.045} size={50} color={SUN} />
    <Typed text={INTRO[2].text} start={INTRO[2].start} per={0.045} size={50} color="#5fd0ff" />
  </AbsoluteFill>
);

const Alert: React.FC<{ at: number }> = ({ at }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - f(at), fps, config: { damping: 8, stiffness: 260 } });
  const out = interpolate(frame / fps, [at + 1.2, at + 1.6], [1, 0], clamp);
  if (frame < f(at)) return null;
  return (
    <div style={{ position: "absolute", left: "50%", top: 120, transform: `translateX(-50%) scale(${s})`,
      opacity: out, fontFamily: ROUND, fontWeight: 700, fontSize: 220, color: "#ff4d4f",
      textShadow: "0 0 40px rgba(255,60,60,0.7)" }}>!</div>
  );
};

const Title: React.FC<{ at: number }> = ({ at }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - f(at), fps, config: { damping: 11, stiffness: 140 } });
  const sub = spring({ frame: frame - f(at + 0.9), fps, config: { damping: 14 } });
  if (frame < f(at)) return null;
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", flexDirection: "column", paddingBottom: 110,
      background: "linear-gradient(transparent 55%, rgba(0,0,0,0.55))" }}>
      <div style={{ fontFamily: ROUND, fontWeight: 700, fontSize: 180, color: CREAM, transform: `scale(${s})`,
        letterSpacing: "0.04em", textShadow: "0 8px 40px rgba(0,0,0,0.6)" }}>OPERATION: COOKIE</div>
      <div style={{ fontFamily: ROUND, fontWeight: 500, fontSize: 46, color: SUN, opacity: sub, letterSpacing: "0.14em",
        transform: `translateY(${interpolate(sub, [0, 1], [16, 0])}px)` }}>MISSION ACCOMPLISHED</div>
    </AbsoluteFill>
  );
};

const EndCard: React.FC = () => {
  const t = useCurrentFrame() / FPS;
  const step = (a: number) => ({ opacity: interpolate(t, [a, a + 0.5], [0, 1], clamp),
    transform: `translateY(${interpolate(t, [a, a + 0.5], [16, 0], clamp)}px)` });
  return (
    <AbsoluteFill style={{ background: "#0b0d14", justifyContent: "center", alignItems: "center", gap: 22,
      flexDirection: "column", textAlign: "center" }}>
      <div style={{ ...step(0.1), fontFamily: ROUND, fontWeight: 700, fontSize: 160, color: CREAM,
        letterSpacing: "0.06em" }}>JUMPER</div>
      <div style={{ ...step(0.6), fontFamily: BODY, fontWeight: 600, fontSize: 40, color: CREAM }}>
        The open-source crab robot by KingKong Robotics</div>
      <div style={{ ...step(1.1), fontFamily: BODY, fontSize: 28, color: "#b9ad9c", maxWidth: 1300 }}>
        Every sneak, freeze and shove is a trained RL policy in MuJoCo physics</div>
      <div style={{ ...step(1.8), fontFamily: ROUND, fontWeight: 700, fontSize: 38, color: SUN,
        letterSpacing: "0.08em", marginTop: 20 }}>#Jumper  #CrabRobot  #OpenSourceRobot</div>
    </AbsoluteFill>
  );
};

const Shot: React.FC<{ cut: Cut }> = ({ cut }) => (
  <AbsoluteFill style={{ background: "#000" }}>
    <AbsoluteFill style={{ filter: "contrast(1.08) saturate(1.08)" }}>
      <OffthreadVideo src={staticFile(`stealth/${cut.shot}.mp4`)} startFrom={f(cut.from ?? 0)} muted
        style={{ width: "100%", height: "100%", objectFit: "cover" }} />
    </AbsoluteFill>
    <AbsoluteFill style={{ background: "radial-gradient(ellipse at center, transparent 58%, rgba(0,0,0,0.4) 100%)" }} />
    <Audio src={staticFile(`foley/stealth/${cut.shot}.wav`)} startFrom={f(cut.from ?? 0)} volume={FOLEY_VOLUME} />
    {cut.alert !== undefined && <Alert at={cut.alert} />}
    {cut.title !== undefined && <Title at={cut.title} />}
  </AbsoluteFill>
);

const Frame: React.FC<{ cut: Cut }> = ({ cut }) =>
  cut.card === "intro" ? <Intro /> : cut.card === "end" ? <EndCard />
    : <Shot cut={cut} />;

const Sound: React.FC = () => (
  <>
    <Audio src={staticFile(ROOM_TONE.file)} volume={(fr) =>
      interpolate(fr / FPS, [0, 0.8, END - 2, END], [0, ROOM_TONE.volume, ROOM_TONE.volume, 0], clamp)} />
    <Sequence from={f(MUSIC.at)}>
      <Audio src={staticFile(MUSIC.file)} volume={(fr) => {
        const t = fr / FPS + MUSIC.at;
        const duck = interpolate(t, [MUSIC.duckFrom, MUSIC.duckFrom + 0.2, MUSIC.duckTo - 0.1, MUSIC.duckTo],
          [1, MUSIC.duck, MUSIC.duck, 1], clamp);
        return MUSIC.volume * duck * interpolate(t, [MUSIC.at, MUSIC.at + 0.3, MUSIC.fadeOutFrom, END], [0, 1, 1, 0], clamp);
      }} />
    </Sequence>
    {SFX.map((s, i) => (
      <Sequence key={i} from={f(Math.max(0, s.at - s.peak))}>
        <Audio src={staticFile(`sfx/stealth/${s.file}.wav`)} volume={s.volume} />
      </Sequence>
    ))}
  </>
);

export const Stealth: React.FC = () => (
  <AbsoluteFill style={{ background: "#000" }}>
    {CUTS.map((cut) => (
      <Sequence key={`${cut.shot ?? cut.card}-${cut.start}`} from={f(cut.start)}
        durationInFrames={f(cut.end) - f(cut.start)}>
        <Frame cut={cut} />
      </Sequence>
    ))}
    <Sound />
  </AbsoluteFill>
);
