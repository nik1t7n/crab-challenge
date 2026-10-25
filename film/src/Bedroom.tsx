import { loadFont as loadFredoka } from "@remotion/google-fonts/Fredoka";
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import React from "react";
import {
  AbsoluteFill, Audio, Easing, interpolate, OffthreadVideo, Sequence, spring, staticFile, useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {
  COUNT_FROM, countAt, CUTS, Cut, END, FOLEY_VOLUME, FPS, MUSIC, REPRISE, ROOM_TONE, SFX, ZERO,
} from "./bedroom-edit";

const { fontFamily: ROUND } = loadFredoka("normal", { weights: ["500", "700"], subsets: ["latin"] });
const { fontFamily: BODY } = loadInter("normal", { weights: ["400", "600"], subsets: ["latin"] });

const f = (s: number) => Math.round(s * FPS);
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const RED = "#ff4d4f";
const CREAM = "#fff7ea";

// ── pieces ────────────────────────────────────────────────────────────────────

const Sms: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const drop = spring({ frame: frame - f(0.7), fps, config: { damping: 14, stiffness: 160 } });
  const shake = t > 0.7 && t < 1.3 ? Math.sin(t * 90) * 6 * (1.3 - t) : 0;
  const out = interpolate(t, [3.2, 3.53], [1, 0], clamp);
  return (
    <AbsoluteFill style={{ background: "#0b0d12" }}>
      <AbsoluteFill style={{ opacity: 0.55, filter: "blur(18px) brightness(0.6)" }}>
        <OffthreadVideo src={staticFile("bedroom/wide.mp4")} muted style={{ width: "100%", height: "100%" }} />
      </AbsoluteFill>
      <div style={{ position: "absolute", left: "50%", top: 130, transform: "translateX(-50%)", fontFamily: ROUND,
        fontWeight: 500, fontSize: 150, color: CREAM, opacity: 0.9 * out, letterSpacing: "0.02em" }}>16:58</div>
      <div style={{ position: "absolute", left: "50%", top: 330, width: 1040, opacity: out,
        transform: `translate(calc(-50% + ${shake}px), ${interpolate(drop, [0, 1], [-260, 0])}px)` }}>
        <div style={{ background: "rgba(250,250,252,0.94)", borderRadius: 44, padding: "34px 40px",
          boxShadow: "0 30px 80px rgba(0,0,0,0.45)", display: "flex", gap: 28, alignItems: "flex-start" }}>
          <div style={{ width: 96, height: 96, borderRadius: 24, background: "linear-gradient(#5ef06e,#25c43c)",
            display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            <div style={{ width: 54, height: 44, borderRadius: 22, background: "#fff" }} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontFamily: BODY, fontSize: 34,
              color: "#666" }}>
              <span style={{ fontWeight: 600, color: "#111", fontSize: 40 }}>Mom ❤️</span><span>now</span>
            </div>
            <div style={{ fontFamily: BODY, fontSize: 46, color: "#111", marginTop: 10, lineHeight: 1.25 }}>
              Home in 30 seconds. Room better be clean.
            </div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

const Timer: React.FC = () => {
  const t = useCurrentFrame() / FPS;
  if (t < COUNT_FROM || t > ZERO + 0.9) return null;
  const n = countAt(t);
  const urgent = n <= 3;
  const beat = (t - COUNT_FROM) * (30 / (ZERO - COUNT_FROM)) % 1;
  const pulse = urgent ? 1 + 0.12 * Math.exp(-beat * 6) : 1;
  const pop = interpolate(t, [COUNT_FROM, COUNT_FROM + 0.25], [0.6, 1], { ...clamp, easing: Easing.out(Easing.back(2)) });
  return (
    <div style={{ position: "absolute", right: 70, top: 60, transform: `scale(${pop * pulse})`,
      transformOrigin: "right top", background: urgent ? RED : "rgba(12,14,20,0.72)", borderRadius: 999,
      padding: "14px 34px", fontFamily: ROUND, fontWeight: 700, fontSize: 68, color: CREAM,
      boxShadow: "0 10px 30px rgba(0,0,0,0.35)", display: "flex", alignItems: "center", gap: 18 }}>
      <span style={{ fontSize: 46 }}>⏱</span>0:{String(n).padStart(2, "0")}
    </div>
  );
};

const Title: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - 3, fps, config: { damping: 11, stiffness: 140 } });
  const star = spring({ frame: frame - f(1.4), fps, config: { damping: 12 } });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", flexDirection: "column",
      background: "radial-gradient(ellipse at center, rgba(0,0,0,0.25), rgba(0,0,0,0.55))" }}>
      <div style={{ fontFamily: ROUND, fontWeight: 700, fontSize: 190, color: CREAM, transform: `scale(${s})`,
        textShadow: "0 8px 40px rgba(0,0,0,0.55)", letterSpacing: "0.02em" }}>
        ROOM: CLEAN<span style={{ color: "#ffd166" }}>*</span>
      </div>
      <div style={{ fontFamily: ROUND, fontWeight: 500, fontSize: 56, color: "#ffd166", opacity: star,
        transform: `translateY(${interpolate(star, [0, 1], [20, 0])}px)`, textShadow: "0 4px 20px rgba(0,0,0,0.6)" }}>
        *under the bed
      </div>
    </AbsoluteFill>
  );
};

const EndCard: React.FC = () => {
  const t = useCurrentFrame() / FPS;
  const step = (a: number) => ({ opacity: interpolate(t, [a, a + 0.5], [0, 1], clamp),
    transform: `translateY(${interpolate(t, [a, a + 0.5], [16, 0], clamp)}px)` });
  return (
    <AbsoluteFill style={{ background: "#14110f", justifyContent: "center", alignItems: "center", gap: 22,
      flexDirection: "column", textAlign: "center" }}>
      <div style={{ ...step(0.1), fontFamily: ROUND, fontWeight: 700, fontSize: 160, color: CREAM,
        letterSpacing: "0.06em" }}>JUMPER</div>
      <div style={{ ...step(0.6), fontFamily: BODY, fontWeight: 600, fontSize: 40, color: CREAM }}>
        The open-source crab robot by KingKong Robotics</div>
      <div style={{ ...step(1.1), fontFamily: BODY, fontSize: 28, color: "#b9ad9c", maxWidth: 1300 }}>
        Six crabs, one plan: every step and every shove is a trained RL policy in MuJoCo physics</div>
      <div style={{ ...step(1.8), fontFamily: ROUND, fontWeight: 700, fontSize: 38, color: "#ffd166",
        letterSpacing: "0.08em", marginTop: 20 }}>#Jumper  #CrabRobot  #OpenSourceRobot</div>
    </AbsoluteFill>
  );
};

const Shot: React.FC<{ cut: Cut }> = ({ cut }) => {
  const t = useCurrentFrame() / FPS;
  const z = cut.zoom
    ? interpolate(t, [cut.zoom.at, cut.zoom.until], [1, cut.zoom.scale], { ...clamp, easing: Easing.inOut(Easing.cubic) })
    : 1;
  return (
  <AbsoluteFill style={{ background: "#000" }}>
    <AbsoluteFill style={{ filter: "contrast(1.06) saturate(1.06)", transform: `scale(${z})` }}>
      <OffthreadVideo src={staticFile(`bedroom/${cut.shot}.mp4`)} startFrom={f(cut.from ?? 0)} muted
        style={{ width: "100%", height: "100%", objectFit: "cover" }} />
    </AbsoluteFill>
    <AbsoluteFill style={{ background: "radial-gradient(ellipse at center, transparent 60%, rgba(0,0,0,0.35) 100%)" }} />
    <Audio src={staticFile(`foley/bedroom/${cut.shot}.wav`)} startFrom={f(cut.from ?? 0)} volume={FOLEY_VOLUME} />
    {cut.title && <Title />}
  </AbsoluteFill>
  );
};

const Frame: React.FC<{ cut: Cut }> = ({ cut }) =>
  cut.card === "sms" ? <Sms /> : cut.card === "end" ? <EndCard /> : <Shot cut={cut} />;

// ── the film ──────────────────────────────────────────────────────────────────

const Sound: React.FC = () => (
  <>
    <Audio src={staticFile(ROOM_TONE.file)} volume={(fr) =>
      interpolate(fr / FPS, [0, 0.8, END - 2, END], [0, ROOM_TONE.volume, ROOM_TONE.volume, 0], clamp)} />
    <Sequence from={f(MUSIC.at)} durationInFrames={f(MUSIC.stop) - f(MUSIC.at)}>
      <Audio src={staticFile(MUSIC.file)} volume={MUSIC.volume} />
    </Sequence>
    <Sequence from={f(REPRISE.at)}>
      <Audio src={staticFile(MUSIC.file)} startFrom={f(REPRISE.from)} volume={(fr) =>
        interpolate(fr / FPS + REPRISE.at, [REPRISE.at, REPRISE.at + 0.05, REPRISE.fadeOutFrom, END],
          [0, REPRISE.volume, REPRISE.volume, 0], clamp)} />
    </Sequence>
    {SFX.map((s, i) => (
      <Sequence key={i} from={f(Math.max(0, s.at - s.peak))}>
        <Audio src={staticFile(`sfx/bedroom/${s.file}.wav`)} volume={s.volume} />
      </Sequence>
    ))}
  </>
);

export const Bedroom: React.FC = () => (
  <AbsoluteFill style={{ background: "#000" }}>
    {CUTS.map((cut) => (
      <Sequence key={`${cut.shot ?? cut.card}-${cut.start}`} from={f(cut.start)}
        durationInFrames={f(cut.end) - f(cut.start)}>
        <Frame cut={cut} />
      </Sequence>
    ))}
    <Timer />
    <Sound />
  </AbsoluteFill>
);
