"""Foley for the bedroom film, from the simulation: every crab in the shot, not only
the camera's, heard from where the camera stands.

    upstream/jumper/.venv/bin/python tools/film/bedroom_foley.py            # every shot
    upstream/jumper/.venv/bin/python tools/film/bedroom_foley.py --only macro

One stereo WAV per shot (film/public/foley/bedroom/<shot>.wav). The voices are the
heist's (`foley.py`: geared servos from joint speed, a tap at each touchdown found by
MuJoCo's contact detection), here summed over the six takes in the picture, each at
a level falling off with its distance from the camera and panned by where it is in
the frame. Things sliding on the floor shuffle (cloth on wood, soft noise as fast as
they slide). Plus the coda's mother: the door's creak as it swings and her footsteps
in the hall, made from the door's baked angle.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import mujoco
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib

import bedroom_shots as S
import foley as F
from stage import Take

FILMS = {"bedroom": "bedroom_shots", "rocky": "rocky_shots"}
OUT = F.OUT / "bedroom"
STEP = F.STEP
SR = F.SR
RNG = np.random.default_rng(23)


def _camera(shot, t_out, take):
    lookat, dist, az, el = shot.camera.at(t_out, take.data.xpos[take.root].copy())
    a, e = math.radians(az), math.radians(el)
    fwd = np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])
    eye = np.asarray(lookat) - dist * fwd
    right = np.cross(fwd, [0.0, 0.0, 1.0])
    right /= np.linalg.norm(right) or 1.0
    return eye, right


def analyse(shot) -> list[dict]:
    """Per take in the shot: limb speeds and touchdowns, its things' slide speed, and
    its distance and side as the camera sees it."""
    takes = [Take(shot.take, shot.place, shot.group)] + [Take(n, shot.place, shot.group) for n in shot.crew]
    n = round(shot.time.duration / STEP) + 1
    out = []
    for j, take in enumerate(takes):
        m, d = take.model, take.data
        m.opt.disableflags &= ~int(mujoco.mjtDisableBit.mjDSBL_CONTACT)
        joints = {limb: [take.joint_qpos(f"robot/{limb}_J{i}_joint") for i in range(5)
                         if mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, f"robot/{limb}_J{i}_joint") >= 0]
                  for limb in F.LIMBS}
        robot = set(take.robot_geoms().tolist())
        limb_of = {}
        for g in robot:
            name = (mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, g) or "").split("/")[-1]
            limb_of[g] = name[:2] if name[:2] in F.LIMBS else None
        items = [take.body(p["body"]) for p in FILM.props(take)]
        heavy = any(p["kind"] == "book" for p in FILM.props(take))
        speed = {limb: np.zeros(n) for limb in F.LIMBS}
        touch = {limb: np.zeros(n, bool) for limb in F.LIMBS}
        slide = np.zeros(n)
        near, side = np.zeros(n), np.zeros(n)
        prev_q, prev_p = None, None
        for i in range(n):
            t_out = i * STEP
            t = shot.time(t_out)
            tt = t if j == 0 or shot.crew_time is None else shot.crew_time(j - 1, t)
            take.pose(tt)
            mujoco.mj_forward(m, d)
            q = d.qpos.copy()
            pos = np.array([d.xpos[b][:2] for b in items])
            if prev_q is not None:
                for limb, idx in joints.items():
                    speed[limb][i] = np.abs(q[idx] - prev_q[idx]).sum() / STEP
                slide[i] = np.linalg.norm(pos - prev_p, axis=1).max() / STEP if len(items) else 0.0
            prev_q, prev_p = q, pos
            for c in range(d.ncon):
                con = d.contact[c]
                for g, other in ((int(con.geom1), int(con.geom2)), (int(con.geom2), int(con.geom1))):
                    if g in robot and other not in robot and limb_of.get(g):
                        touch[limb_of[g]][i] = True
            main = takes[0]
            if j:
                main.pose(t)
            eye, right = _camera(shot, t_out, main)
            if j:
                take.pose(tt)
            rel = d.xpos[take.root] - eye
            dist = float(np.linalg.norm(rel))
            near[i] = 1.0 / (1.0 + max(0.0, dist - 0.4) / 0.6)
            side[i] = float(np.clip(np.dot(rel, right) / (dist or 1.0) * 1.6, -0.9, 0.9))
        frozen = [shot.time((i + 1) * STEP) == shot.time(i * STEP) for i in range(n)]
        out.append({"n": n, "speed": speed, "touch": touch, "slide": slide, "near": near, "side": side,
                    "frozen": frozen, "heavy": heavy})
    return out


def _place(stereo: np.ndarray, near: np.ndarray, side: np.ndarray) -> np.ndarray:
    """Scale by nearness and re-pan by side, per sample."""
    n = len(stereo)
    g = F._low(F._upsample(near, n), 6.0)
    s = F._low(F._upsample(side, n), 6.0)
    mono = stereo.sum(axis=1)
    a = (s + 1) * math.pi / 4
    return np.stack([mono * np.cos(a), mono * np.sin(a)], axis=1) * g[:, None]


def shuffle(info, n_audio: int) -> np.ndarray:
    """Cloth pushed over boards: a soft brushed noise, as loud as the thing is fast."""
    v = F._low(F._upsample(info["slide"], n_audio), 10.0)
    noise = RNG.standard_normal(n_audio)
    if info.get("heavy"):  # a 0.7 kg book dragged over boards: low, slow, effortful
        level = 0.5 * np.clip(v / 0.06, 0, 1) ** 0.7
        tone = F._band(noise, 90, 700) + 0.25 * F._band(noise, 1200, 2600)
    else:
        level = 0.22 * np.clip(v / 0.2, 0, 1) ** 0.8
        tone = F._band(noise, 300, 2400) + 0.3 * F._band(noise, 3000, 6000)
    grain = 0.7 + 0.3 * np.clip(F._low(RNG.standard_normal(n_audio), 40.0) * 8, 0, 1)
    return np.stack([level * tone * grain] * 2, axis=1) * 0.7


def creak(door_deg: np.ndarray, n_audio: int) -> np.ndarray:
    """A hinge's stick-slip: a buzzy tone whose pitch follows how fast the door swings."""
    w = np.abs(np.gradient(door_deg)) / STEP  # deg/s
    w = F._low(F._upsample(w, n_audio), 15.0)
    drive = np.clip(w / 60.0, 0, 1)
    f0 = 180 + 260 * drive + 40 * np.sin(np.cumsum(np.full(n_audio, 2 * np.pi * 3.0 / SR)))
    phase = 2 * np.pi * np.cumsum(f0) / SR
    tone = np.sign(np.sin(phase)) * 0.4 + np.sin(2 * phase) * 0.3 + np.sin(3.01 * phase) * 0.2
    tone = F._band(tone, 250, 4000)
    return F._pan(0.18 * drive ** 1.2 * tone, 0.6)


def steps(starts: list[float], n_audio: int, side: float = 0.6, level: float = 0.5) -> np.ndarray:
    """A grown-up's footsteps on a wooden hall floor: low thuds with a heel click."""
    out = np.zeros((n_audio, 2))
    for k, at in enumerate(starts):
        i = int(at * SR)
        if not 0 <= i < n_audio:
            continue
        n = min(n_audio - i, int(0.35 * SR))
        t = np.arange(n) / SR
        thud = np.sin(2 * np.pi * (70 + 8 * (k % 2)) * t) * np.exp(-t / 0.07)
        knock = F._band(RNG.standard_normal(n), 400, 2500) * np.exp(-t / 0.012) * 0.5
        out[i:i + n] += F._pan(level * (thud + knock) * (0.85 + 0.15 * (k % 2)), side)
    return out


def render(shot) -> np.ndarray:
    infos = analyse(shot)
    n_audio = round(shot.time.duration * SR)
    mix = np.zeros((n_audio, 2))
    for info in infos:
        voice = F.servos(info, n_audio) + F.footfalls(info, n_audio)
        mix += _place(voice, info["near"], info["side"])
        mix += _place(shuffle(info, n_audio), info["near"], info["side"])
    door_at = getattr(shot, "door_at", None)
    if shot.name == "door" and door_at is not None:
        n = round(shot.time.duration / STEP) + 1
        deg = np.array([0.0 if door_at is None else 80.0 * S.ramp(shot.time(i * STEP), door_at, door_at + 1.6)
                        for i in range(n)])
        mix += creak(deg, n_audio)
        opens = next(i for i, v in enumerate(deg) if v > 0.5) * STEP
        mix += steps([opens - 0.9 + 0.48 * k for k in range(2)], n_audio, level=0.35)
        mix += steps([opens + 1.2 + 0.5 * k for k in range(3)], n_audio, side=0.4, level=0.55)
    return mix


FILM = S


def main() -> int:
    global FILM, OUT
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--film", default="bedroom", choices=sorted(FILMS))
    ap.add_argument("--only", nargs="+")
    args = ap.parse_args()
    FILM = importlib.import_module(FILMS[args.film])
    OUT = F.OUT / args.film
    for shot in FILM.SHOTS:
        if args.only and shot.name not in args.only:
            continue
        F.write(OUT / f"{shot.name}.wav", render(shot))
        print(f"[foley] {args.film}/{shot.name}.wav  {shot.time.duration:.1f} s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
