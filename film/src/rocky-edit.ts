// The cut of "UNDERCLAW": a little crab, a stair of books, a month of training.
//
// Film seconds. The music (audio/royaltyfreemusicstudio-radiant-victory-479709.mp3,
// Pixabay licence, 125 BPM, `earshot timeline`) runs from its 17.98 s at film 0, so its
// sad opening strings carry day 1, its 1.4 s stop-down (music 28.75-30.15) falls as the
// crab turns away from the wall, and its triumphant section enters on the downbeat at
// music 29.78 = film 11.80, the first cut of the training montage. From there every cut
// sits on a downbeat (bars of 1.92 s): film 11.80 + 1.92 k.
// Shots: tools/film/rocky_shots.py, drawn in Blender (renders/rocky_blend/); foley:
// tools/film/bedroom_foley.py --film rocky (film/public/foley/rocky/).

export const FPS = 30;

export type Cut = {
  shot?: string;
  card?: "day1" | "day30" | "end";
  start: number;
  end: number;
  from?: number;
  stamp?: string;   // a training-day stamp in the corner
  title?: number;   // the title slams in this many seconds into the cut
};

export const CUTS: Cut[] = [
  { card: "day1", start: 0, end: 2.4 },
  { shot: "summit_reveal", start: 2.4, end: 5.4 },
  { shot: "fail", start: 5.4, end: 8.8 },
  { shot: "defeat", start: 8.8, end: 11.8 },
  { shot: "squats", start: 11.8, end: 13.72, from: 0.4, stamp: "DAY 4" },
  { shot: "shuffle", start: 13.72, end: 15.63, from: 0.5, stamp: "DAY 11" },
  { shot: "push", start: 15.63, end: 17.55, from: 0.6, stamp: "DAY 19" },
  { shot: "jump_practice", start: 17.55, end: 19.47, from: 0.3, stamp: "DAY 26" },
  { card: "day30", start: 19.47, end: 21.39 },
  { shot: "climb_low", start: 21.39, end: 23.32, from: 0.3 },
  { shot: "climb_side", start: 23.32, end: 25.23, from: 0.6 },
  { shot: "climb_top", start: 25.23, end: 27.16, from: 0.9 },
  { shot: "summit_turn", start: 27.16, end: 29.07 },
  { shot: "summit_jump", start: 29.07, end: 32.92 },
  { shot: "victory", start: 32.92, end: 36.76, title: 1.92 },
  { card: "end", start: 36.76, end: 42.52 },
];
export const END = 42.52;

export type Sfx = { file: string; at: number; peak: number; volume: number };

const day1Ticks = [..."DAY 1"].map((ch, i) => (ch === " " ? null : 0.35 + i * 0.09)).filter((t): t is number => t !== null);

export const SFX: Sfx[] = [
  ...day1Ticks.map((at) => ({ file: "tick", at, peak: 0.004, volume: 0.35 })),
  ...[11.8, 13.72, 15.63, 17.55].map((at) => ({ file: "stamp", at: at + 0.25, peak: 0.058, volume: 0.45 })),
  ...[13.72, 15.63, 17.55, 21.39, 23.32, 25.23, 27.16].map((at) => ({ file: "swish", at, peak: 0.13, volume: 0.3 })),
  { file: "impact", at: 19.47, peak: 0.117, volume: 0.55 },
  { file: "sub", at: 29.07 + 0.7, peak: 0.021, volume: 0.6 },
  { file: "flourish", at: 32.92 + 0.6, peak: 0.051, volume: 0.45 },
  { file: "sting", at: 32.92 + 1.92, peak: 0.298, volume: 0.55 },
];

export const MUSIC = { file: "audio/royaltyfreemusicstudio-radiant-victory-479709.mp3", from: 17.98, volume: 0.6,
  fadeOutFrom: 40.6 };
export const ROOM_TONE = { file: "foley/room_tone.wav", volume: 0.22 };
export const FOLEY_VOLUME = 1.0;
export const totalFrames = () => Math.round(END * FPS);
