// The cut of "ROOM: CLEAN*": mom is 30 seconds away; six crabs shove the mess under the bed.
//
// Film seconds. The music (audio/alex-morgan-cartoon-bouncy-chase-antics-578472.mp3,
// Pixabay licence, 133 BPM, `earshot timeline`) starts at MUSIC.at so that its bars
// fall on the cuts: downbeats at film 3.53 + 1.805 k. Every cut is a whole number of
// beats (0.451 s). The countdown runs from 0:30 at the first shot to 0:00 on the
// downbeat at 23.38, the frame the last thing goes fully under the bed
// (bedroom_shots.LAST_T); the music stops dead there and the film runs on in silence
// until the title, where the track comes back at its drum-and-bass section (43.98).
// Shots: tools/film/bedroom_shots.py, drawn in Blender (renders/bedroom_blend/);
// foley: tools/film/bedroom_foley.py (film/public/foley/bedroom/).

export const FPS = 30;

export type Cut = {
  shot?: string;
  card?: "sms" | "end";
  start: number;
  end: number;
  from?: number;  // seconds into the shot (picture and foley) where this cut begins
  title?: boolean;
  // a push-in to the frame's centre over [at, until] (seconds into the cut)
  zoom?: { at: number; until: number; scale: number };
};

export const ZERO = 23.38;
export const COUNT_FROM = 3.53;

export const CUTS: Cut[] = [
  { card: "sms", start: 0, end: 3.53 },
  { shot: "wide", start: 3.53, end: 6.24, from: 0.05 },
  { shot: "popout", start: 6.24, end: 8.49, from: 0.1 },
  { shot: "near_miss", start: 8.49, end: 10.74, from: 0.3 },
  { shot: "convoy", start: 10.74, end: 14.35, from: 0.1 },
  { shot: "sweep", start: 14.35, end: 17.96 },
  { shot: "macro", start: 17.96, end: 19.76, from: 0.1 },
  { shot: "bulldozer", start: 19.76, end: 22.18, from: 0.1 },
  // the last thing crosses the bed's edge 1.2 s into last_in: on ZERO
  { shot: "last_in", start: 22.18, end: 23.98 },
  { shot: "door", start: 23.98, end: 26.58 },
  // mom's eyes stop on the sock: the camera ends on it, and the frame pushes in
  { shot: "mom_pov", start: 26.58, end: 30.58, zoom: { at: 2.9, until: 3.7, scale: 2.2 } },
  { shot: "guilty", start: 30.58, end: 35.38 },
  { shot: "title", start: 35.38, end: 38.78, title: true },
  { card: "end", start: 38.78, end: 44.2 },
];
export const END = 44.2;

export type Sfx = { file: string; at: number; peak: number; volume: number };

// the countdown's ticks: one per displayed second, brighter for the last three
const RATE = 30 / (ZERO - COUNT_FROM);
const ticks: Sfx[] = Array.from({ length: 30 }, (_, i) => {
  const at = COUNT_FROM + (i + 1) / RATE;
  const left = 29 - i;
  return left > 0 && left <= 3 ? { file: "tick_hi", at, peak: 0.005, volume: 0.55 }
    : left > 0 ? { file: "tick", at, peak: 0.004, volume: 0.22 } : null;
}).filter((s): s is Sfx => s !== null);

export const SFX: Sfx[] = [
  { file: "sms", at: 0.75, peak: 0.004, volume: 0.7 },
  ...ticks,
  { file: "pop", at: 6.24 + 0.55, peak: 0.019, volume: 0.6 },
  { file: "spot", at: 8.49 + 0.45, peak: 0.011, volume: 0.45 },
  ...[10.74, 14.35, 17.96, 19.76].map((at) => ({ file: "swish", at, peak: 0.13, volume: 0.35 })),
  { file: "stop", at: ZERO, peak: 0.021, volume: 0.8 },
  { file: "spot", at: 26.58 + 3.75, peak: 0.011, volume: 0.5 },
  { file: "guilty", at: 30.58 + 0.5, peak: 0.103, volume: 0.45 },
  { file: "sting", at: 35.38 + 0.1, peak: 0.175, volume: 0.6 },
  { file: "boop", at: 35.38 + 1.4, peak: 0.004, volume: 0.6 },
  { file: "tok", at: 38.78 + 0.1, peak: 0.011, volume: 0.5 },
];

export const MUSIC = { file: "audio/alex-morgan-cartoon-bouncy-chase-antics-578472.mp3", at: 2.86, stop: ZERO, volume: 0.55 };
// the reprise: from the track's drum-and-bass section, on the title
export const REPRISE = { from: 43.98, at: 35.38, fadeOutFrom: 42.6, volume: 0.6 };
export const ROOM_TONE = { file: "foley/room_tone.wav", volume: 0.25 };
export const FOLEY_VOLUME = 1.0;

export const countAt = (t: number) => Math.max(0, Math.ceil(30 - (t - COUNT_FROM) * RATE - 1e-6));
export const totalFrames = () => Math.round(END * FPS);
