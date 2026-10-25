"""Foley for the heist film, made from the simulation itself.

    upstream/jumper/.venv/bin/python tools/film/foley.py            # every shot
    upstream/jumper/.venv/bin/python tools/film/foley.py --only crate

One stereo WAV per shot (`film/public/foley/<shot>.wav`, the shot's length), drawn
from the same recorded take and time map the picture uses, so every sound sits on
the frame that causes it:

  * servos: each limb's joint speed (rad/s, in film time, so slow motion is lower and
    a freeze is silent) drives a geared whine whose level and pitch follow it,
    panned to the limb's side;
  * footfalls: a tap at every limb's touchdown, found by MuJoCo's own contact
    detection between the robot and the floor, the course or a prop;
  * scrape: the crate and the gold ingot grind on the floor as fast as they slide;
  * lasers: a mains hum and fizz, louder as the camera nears a beam;
  * the lights: a breaker clunk and a fluorescent buzz as each bank strikes.

And `room_tone.wav`, the vault's low air, for under the whole film.
Sounds are synthesised here (numpy); nothing is sampled.
"""

from __future__ import annotations

import argparse
import math
import sys
import wave
from pathlib import Path

import mujoco
import numpy as np
from scipy import signal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shots as S
import vault_scene as V
from stage import Take

SR = 48000
STEP = 0.01  # kinematics sampled every 10 ms of film time
OUT = Path(__file__).resolve().parents[2] / "film" / "public" / "foley"
LIMBS = ("LF", "RF", "LM", "RM", "LR", "RR")
RNG = np.random.default_rng(11)
#: Timbre knobs, tuned by listening with earshot (docs/JOURNAL.md), softened on
#: Nikita's note that the servos were too loud: servo level,
#: drive (0 is a clean sine, higher is a buzzier gear whine), pitch range, gear
#: rattle depth; tap level, body pitch and how much click it has.
STYLE = {"servo_level": 0.045, "teeth_hz": 110.0, "teeth_span": 90.0, "gear_lo": 1400.0, "gear_hi": 2600.0,
         "whine": 0.9, "tap_level": 0.15, "tap_body_hz": 140.0, "tap_click": 0.45}


def _band(x: np.ndarray, lo: float, hi: float, order: int = 2) -> np.ndarray:
    sos = signal.butter(order, [lo, hi], btype="band", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def _low(x: np.ndarray, hi: float) -> np.ndarray:
    return signal.sosfilt(signal.butter(2, hi, btype="low", fs=SR, output="sos"), x)


def _upsample(values: np.ndarray, n: int) -> np.ndarray:
    return np.interp(np.arange(n) / SR, np.arange(len(values)) * STEP, values)


def _pan(mono: np.ndarray, side: float) -> np.ndarray:
    """side -1 left .. +1 right, constant power."""
    a = (side + 1) * math.pi / 4
    return np.stack([mono * math.cos(a), mono * math.sin(a)], axis=1)


# ── analysis ──────────────────────────────────────────────────────────────────


def analyse(shot) -> dict:
    take = Take(shot.take, shot.place)
    m, d = take.model, take.data
    m.opt.disableflags &= ~int(mujoco.mjtDisableBit.mjDSBL_CONTACT)
    limb_joints = {limb: [take.joint_qpos(f"robot/{limb}_J{i}_joint") for i in range(5)
                          if mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, f"robot/{limb}_J{i}_joint") >= 0]
                   for limb in LIMBS}
    robot = set(take.robot_geoms().tolist())
    geom_limb = {}
    for g in robot:
        name = (mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, g) or "").split("/")[-1]
        geom_limb[g] = name[:2] if name[:2] in LIMBS else None
    props = {p: take.body(f"{p}/{p}") for p in ("crate", "gold") if take.body(f"{p}/{p}") >= 0}
    n = round(shot.time.duration / STEP) + 1
    speed = {limb: np.zeros(n) for limb in LIMBS}
    touch = {limb: np.zeros(n, bool) for limb in LIMBS}
    slide = {p: np.zeros(n) for p in props}
    eye = np.zeros((n, 3))
    prev_q, prev_p = None, None
    for i in range(n):
        t_out = i * STEP
        t = shot.time(t_out)
        take.pose(t)
        mujoco.mj_forward(m, d)
        q = d.qpos.copy()
        pos = {p: d.xpos[b].copy() for p, b in props.items()}
        if prev_q is not None:
            for limb, idx in limb_joints.items():
                speed[limb][i] = np.abs(q[idx] - prev_q[idx]).sum() / STEP
            for p in props:
                slide[p][i] = np.linalg.norm(pos[p][:2] - prev_p[p][:2]) / STEP
        prev_q, prev_p = q, pos
        for c in range(d.ncon):
            con = d.contact[c]
            a, b = int(con.geom1), int(con.geom2)
            for g, other in ((a, b), (b, a)):
                if g in robot and other not in robot and geom_limb.get(g):
                    touch[geom_limb[g]][i] = True
        lookat, dist, az, el = shot.camera.at(t_out, d.xpos[take.root].copy())
        azr, elr = math.radians(az), math.radians(el)
        eye[i] = np.asarray(lookat) - dist * np.array([math.cos(elr) * math.cos(azr), math.cos(elr) * math.sin(azr),
                                                       math.sin(elr)])
    return {"n": n, "speed": speed, "touch": touch, "slide": slide, "eye": eye,
            "frozen": [shot.time((i + 1) * STEP) == shot.time(i * STEP) for i in range(n)]}


def _beam_distance(shot, eye: np.ndarray) -> np.ndarray:
    """Distance from the camera to the nearest laser beam, per sample."""
    beams = [((x, -V.ROOM_HALF_W, V.BEAM_Z), (x, V.ROOM_HALF_W, V.BEAM_Z)) for x in V.GATE_X]
    out = np.full(len(eye), 9.0)
    for i, e in enumerate(eye):
        segs = list(beams)
        if shot.take == "jump":
            x = S.sweep(shot.time(i * STEP))[0].a[0]
            segs.append(((x, -V.ROOM_HALF_W, S.SWEEP_Z), (x, V.ROOM_HALF_W, S.SWEEP_Z)))
        for a, b in segs:
            a, b = np.asarray(a), np.asarray(b)
            u = np.clip(np.dot(e - a, b - a) / np.dot(b - a, b - a), 0, 1)
            out[i] = min(out[i], np.linalg.norm(e - (a + u * (b - a))))
    return out


# ── synthesis ─────────────────────────────────────────────────────────────────


def servos(info, n_audio: int) -> np.ndarray:
    """A geared servo buzzes rather than whistles: broadband gear noise chopped by the
    tooth rate, which rises with the joint's speed, over a faint motor whine. (A clean
    tone, tried first, read to earshot as a kettle whistle and a balloon squeak.)"""
    out = np.zeros((n_audio, 2))
    for k, limb in enumerate(LIMBS):
        s = _low(_upsample(info["speed"][limb], n_audio), 25.0)
        drive = np.clip(s / 6.0, 0, 1)
        level = STYLE["servo_level"] * drive ** 0.9
        teeth = STYLE["teeth_hz"] + STYLE["teeth_span"] * drive + 9 * k
        phase = 2 * np.pi * np.cumsum(teeth) / SR
        chop = 0.5 + 0.5 * np.tanh(4 * np.sin(phase))
        gear = _band(RNG.standard_normal(n_audio), STYLE["gear_lo"], STYLE["gear_hi"]) * chop
        whine = np.sin(4 * phase) * STYLE["whine"]
        mono = _band(level * (gear + whine), 150, 9000)
        out += _pan(mono, -0.35 if limb[0] == "L" else 0.35)
    return out


def _tap(length: float = 0.08, pitch: float = 1.0) -> np.ndarray:
    """A plastic foot on a steel floor: a dull thump and a short click, no ring."""
    n = int(length * SR)
    t = np.arange(n) / SR
    click = _low(RNG.standard_normal(n), 2800.0) * np.exp(-t / 0.004)
    body = np.sin(2 * np.pi * STYLE["tap_body_hz"] * pitch * t) * np.exp(-t / 0.018)
    c = STYLE["tap_click"]
    return c * click + (1 - c) * body


def touchdowns(touch: np.ndarray, air: float = 0.06) -> np.ndarray:
    """Sample indices where a limb lands: contact after at least `air` seconds off the
    ground. The soft contact model makes a planted foot flicker in and out of contact
    for a step or two; without this every footfall clicked two or three times and the
    walk sounded like a snare roll."""
    out, last_off = [], -10**9
    for i in range(1, len(touch)):
        if touch[i] and not touch[i - 1] and (i - last_off) * STEP >= air:
            out.append(i)
        if not touch[i] and touch[i - 1]:
            last_off = i
    return np.asarray(out, int)


def footfalls(info, n_audio: int) -> np.ndarray:
    out = np.zeros((n_audio, 2))
    for limb in LIMBS:
        onsets = touchdowns(info["touch"][limb])
        for i in onsets:
            if info["frozen"][i]:
                continue
            start = int(i * STEP * SR)
            tap = _tap(pitch=0.9 + 0.2 * RNG.random()) * STYLE["tap_level"] * (1.0 + 0.4 * RNG.random())
            end = min(n_audio, start + len(tap))
            out[start:end] += _pan(tap[: end - start], -0.3 if limb[0] == "L" else 0.3)
    return out


def scrape(info, n_audio: int) -> np.ndarray:
    out = np.zeros((n_audio, 2))
    for prop, v in info["slide"].items():
        v = _low(_upsample(v, n_audio), 12.0)
        level = 0.35 * np.clip(v / 0.15, 0, 1) ** 0.8
        noise = RNG.standard_normal(n_audio)
        if prop == "gold":   # heavy metal on steel: a low grind with a bright edge
            tone = _band(noise, 120, 900) + 0.35 * _band(noise, 2200, 3200)
        else:                # a light wooden crate
            tone = _band(noise, 250, 1600)
        chatter = 0.6 + 0.4 * np.clip(_low(RNG.standard_normal(n_audio), 30.0) * 8, 0, 1)  # stick-slip
        out += _pan(level * tone * chatter, 0.0)
    return out


def hum(shot, info, n_audio: int) -> np.ndarray:
    dist = _beam_distance(shot, info["eye"])
    level = 0.06 * np.clip(1.0 - dist / 1.6, 0, 1) ** 1.4
    if shot.name == "reveal":
        level *= 0.0
    level = _low(_upsample(level, n_audio), 8.0)
    t = np.arange(n_audio) / SR
    mains = (np.sin(2 * np.pi * 100 * t) + 0.5 * np.sin(2 * np.pi * 200 * t) + 0.25 * np.sin(2 * np.pi * 300 * t))
    fizz = _band(RNG.standard_normal(n_audio), 4000, 7000) * 0.3
    wobble = 1 + 0.15 * np.sin(2 * np.pi * 6.5 * t)
    return _pan(level * (mains + fizz) * wobble, 0.0)


def lights(shot, n_audio: int) -> np.ndarray:
    out = np.zeros((n_audio, 2))
    t_all = np.arange(n_audio) / SR
    for k, spot in enumerate(shot.spots):
        if spot.on_at is None or spot.follow:
            continue
        start = int(spot.on_at * SR)
        n = min(n_audio - start, int(0.9 * SR))
        t = np.arange(n) / SR
        thump = np.sin(2 * np.pi * 55 * t) * np.exp(-t / 0.18)
        clack = _band(RNG.standard_normal(n), 1500, 6000) * np.exp(-t / 0.006)
        ring = (np.sin(2 * np.pi * 870 * t) + 0.6 * np.sin(2 * np.pi * 1330 * t)) * np.exp(-t / 0.25) * 0.12
        clunk = 0.5 * thump + 0.4 * clack + ring
        side = -0.4 + 0.25 * k
        out[start:start + n] += _pan(clunk * 0.7, side)
        # the bank's buzz from then on
        on = t_all >= spot.on_at
        buzz = (np.sin(2 * np.pi * 100 * t_all) * 0.6 + _band(RNG.standard_normal(n_audio), 3000, 6000) * 0.4)
        out += _pan(buzz * on * 0.012, side)
    return out


def write(path: Path, stereo: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    peak = np.max(np.abs(stereo)) or 1.0
    if peak > 0.98:
        stereo = stereo * (0.98 / peak)
    data = (np.clip(stereo, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def room_tone(seconds: float = 60.0) -> np.ndarray:
    n = int(seconds * SR)
    brown = np.cumsum(RNG.standard_normal(n))
    brown = _low(brown - _low(brown, 5.0), 160.0)
    brown /= np.max(np.abs(brown))
    t = np.arange(n) / SR
    air = 0.6 * brown + 0.05 * np.sin(2 * np.pi * 50 * t)
    return np.stack([air, 0.8 * air + 0.2 * np.roll(air, 480)], axis=1) * 0.18


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--only", nargs="+")
    args = ap.parse_args()
    for shot in S.SHOTS:
        if args.only and shot.name not in args.only:
            continue
        info = analyse(shot)
        n_audio = round(shot.time.duration * SR)
        mix = servos(info, n_audio) + footfalls(info, n_audio) + scrape(info, n_audio) + hum(shot, info, n_audio)
        mix += lights(shot, n_audio)
        write(OUT / f"{shot.name}.wav", mix)
        taps = sum(len(touchdowns(info["touch"][limb])) for limb in LIMBS)
        print(f"[foley] {shot.name:13s} {shot.time.duration:4.1f} s  {taps:3d} footfalls  "
              f"peak servo {max(v.max() for v in info['speed'].values()):5.1f} rad/s", flush=True)
    if not args.only:
        write(OUT / "room_tone.wav", room_tone())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
