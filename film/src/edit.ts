// The cut of "MISSION: CLAWSSIBLE", second version: the vault and its obstacle course.
//
// Film seconds. The music (audio/the_mountain-epic-508009.mp3) enters at MUSIC.at,
// with the crab's first step, so its beat grid (~102 BPM, `earshot timeline`,
// audio/epic.timeline.json) sits 10 s later in the film: the 2.48 s orchestral stab
// lands on the first course cut at 12.48, and the percussion entry at 26.72 on the
// title at 36.72, right after the crab's claws meet the gold. Before the music the
// film runs on room tone, typing and the lights striking.
// Shot files: tools/film/shots.py (renders/film_shots/); foley: tools/film/foley.py
// (film/public/foley/), one stem per shot, cut with the picture.

export const FPS = 30;
export const END = 51.79;

export type Tone = "red" | "gold" | "cool" | "white";
// A HUD line; with `count` its number runs from `from` to `to` over the cut (a distance
// closing in), printed into `text` where it says {n}.
export type Hud = { at: number; text: string; tone?: Tone; count?: { from: number; to: number; digits: number } };

export type Cut = {
  shot?: string;
  card?: "cold-open" | "title" | "end";
  start: number;
  end: number;
  from?: number;          // seconds into the shot (picture and foley) where this cut begins
  look?: "secam";
  cam?: string;
  hud?: Hud[];            // times relative to the cut's start
  callout?: { at: number; until: number; text: string; x: number; y: number };
  lost?: number;          // film time of "SIGNAL LOST"
};

export const CUTS: Cut[] = [
  { card: "cold-open", start: 0, end: 3.6 },
  { shot: "reveal", start: 3.6, end: 10.0, hud: [{ at: 4.9, text: "TARGET  ·  1 GOLD INGOT", tone: "gold" }] },
  { shot: "secam", start: 10.0, end: 12.48, look: "secam", cam: "CAM 03" },
  { shot: "ramp", start: 12.48, end: 15.33, hud: [{ at: 0.6, text: "CLIMB  3.5 CM", tone: "cool" }] },
  { shot: "platform", start: 15.33, end: 17.7 },
  { shot: "slalom", start: 17.7, end: 21.24, hud: [{ at: 0.4, text: "PILLARS  ·  CLOSEST 54 MM", tone: "cool" }] },
  { shot: "crate", start: 21.24, end: 22.41, hud: [{ at: 0.3, text: "CRATE IN THE WAY", tone: "cool" }] },
  { shot: "duck", start: 22.41, end: 26.31,
    hud: [{ at: 0.2, text: "TOP 18 CM  ·  BEAM 16 CM", tone: "red" }, { at: 2.5, text: "TOP 14 CM  ·  UNDER", tone: "cool" }] },
  { shot: "gate_out", start: 26.31, end: 27.49 },
  { shot: "pov", start: 27.49, end: 28.69, from: 0.4,
    hud: [{ at: 0.0, text: "SWEEP  {n} M", tone: "red", count: { from: 1.84, to: 0.76, digits: 1 } }] },
  { shot: "jump_side", start: 28.69, end: 30.42, from: 0.37 },
  { shot: "bullet", start: 30.42, end: 32.79, callout: { at: 0.3, until: 2.2, text: "AIR  23 CM", x: 0.6, y: 0.36 } },
  { shot: "land", start: 32.79, end: 34.0 },
  { shot: "gold_turn", start: 34.0, end: 35.18 },
  { shot: "push_contact", start: 35.18, end: 36.72, from: 0.18 },
  { card: "title", start: 36.72, end: 39.24 },
  { shot: "push_door", start: 39.24, end: 43.36, hud: [{ at: 0.5, text: "EXTRACTION", tone: "gold" }] },
  { shot: "escape_secam", start: 43.36, end: 46.5, look: "secam", cam: "CAM 01", lost: 46.15 },
  { card: "end", start: 46.5, end: END },
];

// The cold open types three lines; each visible character gets a key tick.
export const COLD_OPEN = [
  { text: "OCT 25, 2026  ·  03:12 AM", start: 0.2, perChar: 0.045, tone: "white" as Tone, size: 56 },
  { text: "VAULT 7  ·  SUB-LEVEL B", start: 1.45, perChar: 0.04, tone: "red" as Tone, size: 34 },
  { text: "OBJECTIVE: THE GOLD", start: 2.5, perChar: 0.045, tone: "gold" as Tone, size: 40 },
];
const typing = COLD_OPEN.flatMap((line) =>
  [...line.text].flatMap((ch, i) => (ch === " " || ch === "·" ? [] : [line.start + i * line.perChar])));

// Sound effects from earshot's code-made bank (film/public/sfx, `earshot sfx render`).
// `at` is when the sound's loudest moment lands; `peak` is where that sits in the
// file (`earshot sfx list`), so the file starts at `at - peak`.
export type Sfx = { file: string; at: number; peak: number; volume: number };

const hud = (at: number): Sfx => ({ file: "hud", at, peak: 0.004, volume: 0.45 });

export const SFX: Sfx[] = [
  ...typing.map((at) => ({ file: "tick", at, peak: 0.007, volume: 0.32 })),
  hud(3.6 + 4.9),
  { file: "glitch_in", at: 10.02, peak: 0.038, volume: 0.35 },
  hud(12.48 + 0.6), hud(17.7 + 0.4), hud(21.24 + 0.3), hud(22.41 + 0.2), hud(22.41 + 2.5), hud(27.49), hud(39.24 + 0.5),
  // An accent on every cut that has none of its own (earshot critique); whoosh peaks
  // land on the cut, and the cuts that need a hard edge get a short hit.
  ...[12.48, 17.7, 26.31, 34.0, 39.24].map((at) => ({ file: "cut_whoosh", at, peak: 0.162, volume: 0.4 })),
  ...[21.24, 22.41].map((at) => ({ file: "cut_swish", at, peak: 0.11, volume: 0.4 })),
  ...[3.6, 15.33, 27.49, 28.69, 32.79, 35.18, 43.36].map((at) => ({ file: "cut_air", at, peak: 0.043, volume: 0.45 })),
  // The jump: tension builds to the freeze at the top, the beam rushes under the crab
  // just before it, time stops, and the landing hits on the touchdown (take 0.70 s).
  { file: "tension", at: 30.42, peak: 2.771, volume: 0.45 },
  { file: "whip", at: 30.3, peak: 0.116, volume: 0.55 },
  { file: "timestop", at: 30.5, peak: 0.468, volume: 0.75 },
  { file: "reverse", at: 32.79, peak: 0.57, volume: 0.4 },
  { file: "land", at: 33.57, peak: 0.058, volume: 0.6 },
  { file: "knock", at: 36.6, peak: 0.042, volume: 0.7 },
  { file: "impact", at: 36.72, peak: 0.117, volume: 0.85 },
  { file: "sub", at: 36.72, peak: 0.021, volume: 0.7 },
  { file: "shutter", at: 43.36, peak: 0.1, volume: 0.35 },
  { file: "lost", at: 46.15, peak: 0.649, volume: 0.55 },
  { file: "sting", at: 46.7, peak: 0.175, volume: 0.5 },
];

export const MUSIC = { file: "audio/the_mountain-epic-508009.mp3", at: 10.0, fadeOutFrom: 49.4, volume: 0.7 };
export const ROOM_TONE = { file: "foley/room_tone.wav", volume: 0.55 };
export const FOLEY_VOLUME = 1.0;

export const totalFrames = () => Math.round(END * FPS);
