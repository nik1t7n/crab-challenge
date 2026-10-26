// The cut of "OPERATION: COOKIE": 2 a.m., three cookies, a vacuum on patrol.
//
// Film seconds. The music (audio/alex-morgan-sneaky-tiptoe-music-579470.mp3, Pixabay
// licence, 89 BPM, tools/film/beats.py) starts at MUSIC.at so that its first downbeat
// (0.743 s) lands on the first shot at 3.40; every cut is a whole number of beats
// (0.673 s). The music ducks while the vacuum turns and comes back along the bed
// (close_call) and returns full when the crab is home.
// Shots: tools/film/stealth_shots.py, drawn in Blender (renders/stealth_blend/); foley:
// tools/film/bedroom_foley.py --film stealth (film/public/foley/stealth/).

export const FPS = 30;
const BEAT = 60 / 89.1;
const b = (n: number) => Math.round((3.4 + n * BEAT) * 100) / 100;

export type Cut = {
  shot?: string;
  card?: "intro" | "end";
  start: number;
  end: number;
  from?: number;
  alert?: number;   // a "!" pops at this many seconds into the cut
  title?: number;
};

export const CUTS: Cut[] = [
  { card: "intro", start: 0, end: b(0) },
  { shot: "lair", start: b(0), end: b(3), from: 0.3 },
  { shot: "target", start: b(3), end: b(6), from: 0.2 },
  { shot: "patrol", start: b(6), end: b(9), from: 0.4 },
  { shot: "sneak", start: b(9), end: b(12), from: 0.4 },
  { shot: "hide", start: b(12), end: b(16), from: 0.3 },
  { shot: "slip", start: b(16), end: b(19), from: 0.4 },
  { shot: "grab", start: b(19), end: b(22), from: 0.4 },
  { shot: "race", start: b(22), end: b(26), from: 0.1 },
  { shot: "close_call", start: b(26), end: b(32), from: 0.4, alert: 0.5 },
  { shot: "safe", start: b(32), end: b(36), from: 0.5 },
  { shot: "title", start: b(36), end: b(41), title: BEAT },
  { card: "end", start: b(41), end: b(49) },
];
export const END = b(49);

export type Sfx = { file: string; at: number; peak: number; volume: number };

const lines = [{ text: "02:14 AM", start: 0.2 }, { text: "TARGET: 3 COOKIES", start: 1.0 }, { text: "THREAT: VACUUM BOT", start: 2.1 }];
export const INTRO = lines;
const typing = lines.flatMap((l) => [...l.text].flatMap((ch, i) => (ch === " " ? [] : [l.start + i * 0.045])));

export const SFX: Sfx[] = [
  ...typing.map((at) => ({ file: "tick", at, peak: 0.004, volume: 0.3 })),
  { file: "spot", at: b(3) + 0.4, peak: 0.011, volume: 0.45 },
  ...[b(6), b(9), b(16), b(22), b(32)].map((at) => ({ file: "swish", at, peak: 0.13, volume: 0.3 })),
  { file: "pop", at: b(26) + 0.5, peak: 0.019, volume: 0.7 },
  { file: "stop", at: b(26) + 0.5, peak: 0.021, volume: 0.6 },
  { file: "sting", at: b(36) + BEAT, peak: 0.175, volume: 0.55 },
  { file: "boop", at: b(36) + BEAT + 1.0, peak: 0.004, volume: 0.55 },
];

export const MUSIC = { file: "audio/alex-morgan-sneaky-tiptoe-music-579470.mp3", at: 3.4 - 0.743, volume: 0.55,
  duckFrom: b(26) + 0.4, duckTo: b(32), duck: 0.12, fadeOutFrom: END - 2.0 };
export const ROOM_TONE = { file: "foley/room_tone.wav", volume: 0.3 };
export const FOLEY_VOLUME = 1.1;
export const totalFrames = () => Math.round(END * FPS);
