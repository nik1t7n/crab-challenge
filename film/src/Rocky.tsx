import { loadFont as loadFredoka } from "@remotion/google-fonts/Fredoka";
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import React from "react";
import {
  AbsoluteFill, Audio, interpolate, OffthreadVideo, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig,
} from "remotion";
import { CUTS, Cut, END, FOLEY_VOLUME, FPS, MUSIC, ROOM_TONE, SFX } from "./rocky-edit";

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

const Day1: React.FC = () => (
  <AbsoluteFill style={{ background: "#07090f", justifyContent: "center", alignItems: "center", flexDirection: "column",
    gap: 14 }}>
    <Typed text="DAY 1" start={0.35} per={0.09} size={150} color={CREAM} />
    <Typed text="5:47 AM" start={1.1} per={0.06} size={44} color="#8fa3c8" />
  </AbsoluteFill>
);

const Day30: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame, fps, config: { damping: 12, stiffness: 170 } });
  const glow = interpolate(frame / fps, [0, 1.9], [0.2, 0.9], clamp);
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", flexDirection: "column", gap: 10,
      background: `radial-gradient(ellipse at 50% 120%, rgba(255,150,60,${glow}) 0%, #120c12 60%)` }}>
      <div style={{ fontFamily: ROUND, fontWeight: 700, fontSize: 200, color: CREAM, transform: `scale(${s})`,
        letterSpacing: "0.06em", textShadow: "0 10px 50px rgba(255,140,40,0.45)" }}>DAY 30</div>
    </AbsoluteFill>
  );
};

const Stamp: React.FC<{ text: string }> = ({ text }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - f(0.2), fps, config: { damping: 9, stiffness: 220 } });
  return (
    <div style={{ position: "absolute", left: 80, top: 70, transform: `scale(${interpolate(s, [0, 1], [2.2, 1])}) rotate(-6deg)`,
      opacity: s, transformOrigin: "left top", border: `6px solid ${SUN}`, borderRadius: 14, padding: "8px 26px",
      fontFamily: ROUND, fontWeight: 700, fontSize: 64, color: SUN, letterSpacing: "0.08em",
      textShadow: "0 4px 16px rgba(0,0,0,0.5)", boxShadow: "0 4px 16px rgba(0,0,0,0.35)" }}>{text}</div>
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
        letterSpacing: "0.05em", textShadow: "0 8px 40px rgba(0,0,0,0.6)" }}>UNDERCLAW</div>
      <div style={{ fontFamily: ROUND, fontWeight: 500, fontSize: 46, color: SUN, opacity: sub, letterSpacing: "0.14em",
        transform: `translateY(${interpolate(sub, [0, 1], [16, 0])}px)` }}>EVERY CHAMPION STARTS SMALL</div>
    </AbsoluteFill>
  );
};

const EndCard: React.FC = () => {
  const t = useCurrentFrame() / FPS;
  const step = (a: number) => ({ opacity: interpolate(t, [a, a + 0.5], [0, 1], clamp),
    transform: `translateY(${interpolate(t, [a, a + 0.5], [16, 0], clamp)}px)` });
  return (
    <AbsoluteFill style={{ background: "#120f10", justifyContent: "center", alignItems: "center", gap: 22,
      flexDirection: "column", textAlign: "center" }}>
      <div style={{ ...step(0.1), fontFamily: ROUND, fontWeight: 700, fontSize: 160, color: CREAM,
        letterSpacing: "0.06em" }}>JUMPER</div>
      <div style={{ ...step(0.6), fontFamily: BODY, fontWeight: 600, fontSize: 40, color: CREAM }}>
        The open-source crab robot by KingKong Robotics</div>
      <div style={{ ...step(1.1), fontFamily: BODY, fontSize: 28, color: "#b9ad9c", maxWidth: 1300 }}>
        Every squat, shove, step and jump is a trained RL policy in MuJoCo physics</div>
      <div style={{ ...step(1.8), fontFamily: ROUND, fontWeight: 700, fontSize: 38, color: SUN,
        letterSpacing: "0.08em", marginTop: 20 }}>#Jumper  #CrabRobot  #OpenSourceRobot</div>
    </AbsoluteFill>
  );
};

const Shot: React.FC<{ cut: Cut }> = ({ cut }) => (
  <AbsoluteFill style={{ background: "#000" }}>
    <AbsoluteFill style={{ filter: "contrast(1.08) saturate(1.08)" }}>
      <OffthreadVideo src={staticFile(`rocky/${cut.shot}.mp4`)} startFrom={f(cut.from ?? 0)} muted
        style={{ width: "100%", height: "100%", objectFit: "cover" }} />
    </AbsoluteFill>
    <AbsoluteFill style={{ background: "radial-gradient(ellipse at center, transparent 58%, rgba(0,0,0,0.4) 100%)" }} />
    <Audio src={staticFile(`foley/rocky/${cut.shot}.wav`)} startFrom={f(cut.from ?? 0)} volume={FOLEY_VOLUME} />
    {cut.stamp && <Stamp text={cut.stamp} />}
    {cut.title !== undefined && <Title at={cut.title} />}
  </AbsoluteFill>
);

const Frame: React.FC<{ cut: Cut }> = ({ cut }) =>
  cut.card === "day1" ? <Day1 /> : cut.card === "day30" ? <Day30 /> : cut.card === "end" ? <EndCard />
    : <Shot cut={cut} />;

const Sound: React.FC = () => (
  <>
    <Audio src={staticFile(ROOM_TONE.file)} volume={(fr) =>
      interpolate(fr / FPS, [0, 0.8, END - 2, END], [0, ROOM_TONE.volume, ROOM_TONE.volume, 0], clamp)} />
    <Audio src={staticFile(MUSIC.file)} startFrom={f(MUSIC.from)} volume={(fr) =>
      interpolate(fr / FPS, [0, 0.4, MUSIC.fadeOutFrom, END], [0, MUSIC.volume, MUSIC.volume, 0], clamp)} />
    {SFX.map((s, i) => (
      <Sequence key={i} from={f(Math.max(0, s.at - s.peak))}>
        <Audio src={staticFile(`sfx/rocky/${s.file}.wav`)} volume={s.volume} />
      </Sequence>
    ))}
  </>
);

export const Rocky: React.FC = () => (
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
