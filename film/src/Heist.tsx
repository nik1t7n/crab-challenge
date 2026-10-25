import { loadFont as loadAnton } from "@remotion/google-fonts/Anton";
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";
import React from "react";
import {
  AbsoluteFill, Audio, Easing, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame,
} from "remotion";
import { COLD_OPEN, CUTS, Cut, END, FOLEY_VOLUME, FPS, Hud, MUSIC, ROOM_TONE, SFX, Tone } from "./edit";

const { fontFamily: DISPLAY } = loadAnton();
const { fontFamily: BODY } = loadInter("normal", { weights: ["400", "600"], subsets: ["latin"] });
const { fontFamily: MONO } = loadMono("normal", { weights: ["500", "700"], subsets: ["latin"] });

const TONE: Record<Tone, string> = { red: "#ff3b30", gold: "#ffc53d", cool: "#9fc4ff", white: "#f2f4f8" };
// 2.39:1 inside 16:9: the bars carry the film look.
const BAR = Math.round((1080 - 1920 / 2.39) / 2);
const f = (s: number) => Math.round(s * FPS);
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

// ── pieces ────────────────────────────────────────────────────────────────────

const Typed: React.FC<{ text: string; start: number; perChar: number; size: number; color: string }> = (
  { text, start, perChar, size, color },
) => {
  const t = useCurrentFrame() / FPS;
  const shown = Math.max(0, Math.min(text.length, Math.floor((t - start) / perChar) + 1));
  const caret = t > start && Math.floor(t * 3) % 2 === 0;
  return (
    <div style={{ fontFamily: MONO, fontWeight: 500, fontSize: size, color, letterSpacing: "0.12em", minHeight: size * 1.3 }}>
      {t >= start ? text.slice(0, shown) : ""}
      <span style={{ opacity: caret && shown < text.length + 1 ? 1 : 0 }}>▌</span>
    </div>
  );
};

const ColdOpen: React.FC = () => (
  <AbsoluteFill style={{ background: "#030405", justifyContent: "center", alignItems: "center", gap: 18,
    flexDirection: "column" }}>
    {COLD_OPEN.map((line, i) => (
      <Typed key={i} text={line.text} start={line.start} perChar={line.perChar} size={line.size}
        color={TONE[line.tone]} />
    ))}
  </AbsoluteFill>
);

const HudLine: React.FC<{ hud: Hud; index: number; length: number }> = ({ hud, index, length }) => {
  const t = useCurrentFrame() / FPS - hud.at;
  if (t < 0) return null;
  let text = hud.text;
  if (hud.count) {
    const n = interpolate(t, [0, length - hud.at], [hud.count.from, hud.count.to], clamp);
    text = text.replace("{n}", n.toFixed(hud.count.digits));
  }
  const chars = hud.count ? text.length : Math.min(text.length, Math.floor(t / 0.022) + 1);
  const color = TONE[hud.tone ?? "white"];
  return (
    <div style={{ position: "absolute", left: 96, top: BAR + 48 + index * 52, display: "flex", alignItems: "center",
      gap: 14, fontFamily: MONO, fontWeight: 700, fontSize: 30, letterSpacing: "0.14em", color }}>
      <span style={{ width: 10, height: 10, background: color, boxShadow: `0 0 12px ${color}` }} />
      {text.slice(0, chars)}
    </div>
  );
};

const Callout: React.FC<{ c: NonNullable<Cut["callout"]> }> = ({ c }) => {
  const t = useCurrentFrame() / FPS;
  const o = interpolate(t, [c.at, c.at + 0.25, c.until - 0.25, c.until], [0, 1, 1, 0], clamp);
  const x = c.x * 1920, y = c.y * 1080;
  return (
    <div style={{ position: "absolute", left: x, top: y, opacity: o }}>
      <div style={{ position: "absolute", left: -6, top: -6, width: 12, height: 12, borderRadius: 6,
        border: `2px solid ${TONE.gold}` }} />
      <div style={{ position: "absolute", left: 6, top: 0, width: 150, height: 2, background: TONE.gold,
        transform: "rotate(-28deg)", transformOrigin: "0 0" }} />
      <div style={{ position: "absolute", left: 140, top: -96, fontFamily: MONO, fontWeight: 700, fontSize: 40,
        letterSpacing: "0.12em", color: TONE.gold, whiteSpace: "nowrap" }}>{c.text}</div>
    </div>
  );
};

const Secam: React.FC<{ cam: string; clock: number }> = ({ cam, clock }) => {
  const frame = useCurrentFrame();
  const secs = 12 * 60 + 7 + clock + frame / FPS;
  const stamp = `03:${String(Math.floor(secs / 60)).padStart(2, "0")}:${String(Math.floor(secs % 60)).padStart(2, "0")}`;
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ background: "repeating-linear-gradient(0deg, rgba(0,0,0,0.22) 0 2px, transparent 2px 4px)" }} />
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.65) 100%)" }} />
      <div style={{ position: "absolute", left: 96, top: BAR + 40, fontFamily: MONO, fontWeight: 700, fontSize: 30,
        color: "#d8e6d8", letterSpacing: "0.12em", display: "flex", gap: 18, alignItems: "center" }}>
        <span style={{ width: 16, height: 16, borderRadius: 8, background: TONE.red,
          opacity: Math.floor(frame / 15) % 2 ? 1 : 0.15 }} />
        REC · {cam}
      </div>
      <div style={{ position: "absolute", right: 96, bottom: BAR + 36, fontFamily: MONO, fontSize: 28,
        color: "#d8e6d8", letterSpacing: "0.1em" }}>{stamp}</div>
    </AbsoluteFill>
  );
};

const SignalLost: React.FC<{ at: number }> = ({ at }) => {
  const t = useCurrentFrame() / FPS - at;
  if (t < 0) return null;
  const jitter = Math.sin(t * 90) * 14;
  return (
    <AbsoluteFill style={{ background: `rgba(10,12,14,${Math.min(1, t * 3)})`, justifyContent: "center",
      alignItems: "center" }}>
      <div style={{ fontFamily: MONO, fontWeight: 700, fontSize: 64, color: "#e9efe9", letterSpacing: "0.3em",
        transform: `translateX(${jitter}px)`, textShadow: `-4px 0 ${TONE.red}, 4px 0 #3ad1ff` }}>SIGNAL LOST</div>
    </AbsoluteFill>
  );
};

const Shot: React.FC<{ cut: Cut }> = ({ cut }) => (
  <AbsoluteFill style={{ background: "#000" }}>
    <AbsoluteFill style={{ filter: cut.look === "secam"
      ? "grayscale(0.85) sepia(0.25) hue-rotate(60deg) brightness(2.1) contrast(1.15)"
      : "contrast(1.1) brightness(1.12) saturate(1.1)" }}>
      <OffthreadVideo src={staticFile(`shots/${cut.shot}.mp4`)} startFrom={f(cut.from ?? 0)} muted
        style={{ width: "100%", height: "100%", objectFit: "cover" }} />
    </AbsoluteFill>
    {cut.look === "secam" && <Secam cam={cut.cam ?? "CAM 01"} clock={cut.start} />}
    {cut.lost !== undefined && <SignalLost at={cut.lost - cut.start} />}
    <Audio src={staticFile(`foley/${cut.shot}.wav`)} startFrom={f(cut.from ?? 0)} volume={FOLEY_VOLUME} />
    {(cut.hud ?? []).map((h, i) => <HudLine key={i} hud={h} index={i} length={cut.end - cut.start} />)}
    {cut.callout && <Callout c={cut.callout} />}
  </AbsoluteFill>
);

const Title: React.FC = () => {
  const t = useCurrentFrame() / FPS;
  const slam = interpolate(t, [0, 0.18], [1.18, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  const blur = interpolate(t, [0, 0.18], [14, 0], clamp);
  const flash = interpolate(t, [0, 0.12], [0.9, 0], clamp);
  const beam = interpolate(t, [0.05, 0.6], [0, 1], { ...clamp, easing: Easing.inOut(Easing.cubic) });
  const sub = interpolate(t, [1.63, 2.0], [0, 1], clamp); // the uplifter at 28.35 s
  return (
    <AbsoluteFill style={{ background: "#040506", justifyContent: "center", alignItems: "center" }}>
      <div style={{ fontFamily: DISPLAY, fontSize: 168, color: TONE.white, letterSpacing: "0.04em",
        transform: `scale(${slam})`, filter: `blur(${blur}px)` }}>
        MISSION: <span style={{ color: TONE.red }}>CLAWSSIBLE</span>
      </div>
      <div style={{ width: 1100 * beam, height: 3, background: TONE.red, boxShadow: `0 0 18px ${TONE.red}`,
        marginTop: 8 }} />
      <div style={{ marginTop: 34, fontFamily: MONO, fontWeight: 500, fontSize: 32, letterSpacing: "0.5em",
        color: TONE.gold, opacity: sub }}>A JUMPER HEIST</div>
      <AbsoluteFill style={{ background: "#fff", opacity: flash }} />
    </AbsoluteFill>
  );
};

const EndCard: React.FC = () => {
  const t = useCurrentFrame() / FPS;
  const step = (a: number) => ({ opacity: interpolate(t, [a, a + 0.5], [0, 1], clamp),
    transform: `translateY(${interpolate(t, [a, a + 0.5], [16, 0], clamp)}px)` });
  return (
    <AbsoluteFill style={{ background: "#040506", justifyContent: "center", alignItems: "center", gap: 22,
      flexDirection: "column", textAlign: "center" }}>
      <div style={{ ...step(0.1), fontFamily: DISPLAY, fontSize: 150, color: TONE.white, letterSpacing: "0.08em" }}>
        JUMPER</div>
      <div style={{ ...step(0.6), fontFamily: BODY, fontWeight: 600, fontSize: 40, color: TONE.white }}>
        The open-source crab robot by KingKong Robotics</div>
      <div style={{ ...step(1.1), fontFamily: BODY, fontSize: 28, color: "#9aa3b2", maxWidth: 1200 }}>
        Every step, crouch, jump and shove: trained RL policies in MuJoCo physics</div>
      <div style={{ ...step(1.8), fontFamily: MONO, fontWeight: 700, fontSize: 34, color: TONE.gold,
        letterSpacing: "0.12em", marginTop: 20 }}>#Jumper  #CrabRobot  #OpenSourceRobot</div>
    </AbsoluteFill>
  );
};

const Frame: React.FC<{ cut: Cut }> = ({ cut }) =>
  cut.card === "cold-open" ? <ColdOpen /> : cut.card === "title" ? <Title /> : cut.card === "end" ? <EndCard />
    : <Shot cut={cut} />;

// ── the film ──────────────────────────────────────────────────────────────────

const Picture: React.FC = () => (
  <>
    {CUTS.map((cut) => (
      <Sequence key={`${cut.shot ?? cut.card}-${cut.start}`} from={f(cut.start)} durationInFrames={f(cut.end) - f(cut.start)}>
        <Frame cut={cut} />
      </Sequence>
    ))}
  </>
);

const Sound: React.FC = () => (
  <>
    <Audio src={staticFile(ROOM_TONE.file)} volume={(fr) =>
      interpolate(fr / FPS, [0, 0.8, END - 2, END], [0, ROOM_TONE.volume, ROOM_TONE.volume, 0], clamp)} />
    <Sequence from={f(MUSIC.at)}>
      <Audio src={staticFile(MUSIC.file)} volume={(fr) =>
        interpolate(fr / FPS + MUSIC.at, [MUSIC.at, MUSIC.at + 0.6, MUSIC.fadeOutFrom, END],
          [0, MUSIC.volume, MUSIC.volume, 0], clamp)} />
    </Sequence>
    {SFX.map((s, i) => {
      const start = Math.max(0, s.at - s.peak);
      return (
        <Sequence key={i} from={f(start)}>
          <Audio src={staticFile(`sfx/${s.file}.wav`)} volume={s.volume} />
        </Sequence>
      );
    })}
  </>
);

export const Heist: React.FC = () => (
  <AbsoluteFill style={{ background: "#000" }}>
    <Picture />
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: BAR, background: "#000" }} />
      <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: BAR, background: "#000" }} />
    </AbsoluteFill>
    <Sound />
  </AbsoluteFill>
);
