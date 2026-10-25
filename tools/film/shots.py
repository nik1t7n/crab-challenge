"""The heist film's shots, in order (second cut: the vault and its obstacle course).

    upstream/jumper/.venv/bin/python tools/film/shots.py              # every shot, 1080p
    upstream/jumper/.venv/bin/python tools/film/shots.py --only crate --preview

One room, `tools/film/vault_scene.py`: a 7 m vault, the course down its middle
(ramp and platform, three pillars, a crate, a laser gate), a sweeping beam, the
gold on a lit spot at the far end and a side door out. The course run is one
physical take in that room (`renders/film/course`), checked by
`tools/film/check_course.py`. The jump and the grab were recorded on an empty
floor and are set down in the room (`Shot.place`), with the parts of the room
they did not have drawn in: the course, the crate where the run left it, the gold.
The push was recorded in `gold_scene.py` and is set down so its ingot lies at GOLD_AT.

Everything in it moves by physics and the robot's trained policies: the crab climbs,
weaves, shoves the crate, ducks the beams, jumps the sweep and pushes the gold ingot
out of the side door with its claws (`renders/film/push`, `tools/film/check_prop.py`).
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vault_scene as V
from stage import (
    CameraPath,
    Geom,
    Key,
    Shot,
    Spot,
    TimeMap,
    laser,
    paint_crab,
    ramp,
    render,
)

OUT = Path(__file__).resolve().parents[2] / "renders" / "film_shots"

# ── the look ──────────────────────────────────────────────────────────────────

GOLD = (1.0, 0.76, 0.18, 1.0)
FLOOR = (0.035, 0.04, 0.055, 1.0)
STEEL = (0.075, 0.085, 0.105, 1.0)
COURSE = (0.20, 0.22, 0.27, 1.0)
CRATE_RGBA = (0.55, 0.38, 0.20, 1.0)


def heist_look(model, take) -> None:
    import mujoco

    robot = set(take.robot_geoms().tolist())
    paint_crab(model, take)
    for g in range(model.ngeom):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, g) or ""
        body = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, model.geom_bodyid[g]) or ""
        if g in robot:
            continue
        if body.startswith("gold/"):
            model.geom_rgba[g] = GOLD
        elif name == "terrain":
            model.geom_rgba[g] = FLOOR
        elif name.startswith(("ramp_", "platform", "pillar_")):
            model.geom_rgba[g] = COURSE
        elif body.startswith("crate/"):
            model.geom_rgba[g] = CRATE_RGBA


# ── the room, drawn ───────────────────────────────────────────────────────────

CRATE_REST = (4.03, -0.30)  # where the run leaves it (check_course.py, 2026-10-25)


def _walls() -> list[Geom]:
    x0, x1 = V.ROOM_X
    cx, half_x = (x0 + x1) / 2, (x1 - x0) / 2
    w, h = V.ROOM_HALF_W, V.WALL_H
    dx0, dx1 = V.DOOR[0] - V.DOOR[1], V.DOOR[0] + V.DOOR[1]
    out = [
        Geom("box", STEEL, pos=(cx, -w, h), size=(half_x, 0.02, h), cull=(1, -w)),
        Geom("box", STEEL, pos=(x0, 0, h), size=(0.02, w, h), cull=(0, x0)),
        Geom("box", STEEL, pos=(x1, 0, h), size=(0.02, w, h), cull=(0, x1)),
        # the +y wall, with the door
        Geom("box", STEEL, pos=((x0 + dx0) / 2, w, h), size=((dx0 - x0) / 2, 0.02, h), cull=(1, w)),
        Geom("box", STEEL, pos=((dx1 + x1) / 2, w, h), size=((x1 - dx1) / 2, 0.02, h), cull=(1, w)),
        Geom("box", (0.6, 0.12, 0.08, 1), pos=(V.DOOR[0], w, 2 * h - 0.03), size=(V.DOOR[1], 0.025, 0.012),
             emission=0.6, cull=(1, w)),
    ]
    grid = (0.25, 0.75, 1.0, 0.10)
    x = x0
    while x <= x1:
        out.append(Geom("box", grid, pos=(x, 0, 0.0006), size=(0.0012, w, 0.0005), emission=0.5))
        x += 0.25
    for y in (-0.5, -0.25, 0.0, 0.25, 0.5):
        out.append(Geom("box", grid, pos=(cx, y, 0.0006), size=(half_x, 0.0012, 0.0005), emission=0.5))
    return out


WALLS = _walls()


def _course_pieces() -> list[Geom]:
    """The physical course, drawn, for takes recorded without it."""
    out = []
    for (x0, x1), up in ((V.RAMP_UP, True), (V.RAMP_DOWN, False)):
        run = x1 - x0
        slope = math.atan2(V.PLATFORM_H, run)
        t = 0.01
        cx = (x0 + x1) / 2 + (t * math.sin(slope) * (1 if up else -1)) / 2
        cz = V.PLATFORM_H / 2 - t * math.cos(slope) / 2
        out.append(Geom("box", COURSE, pos=(cx, 0, cz),
                        size=(math.hypot(run, V.PLATFORM_H) / 2, V.COURSE_HALF_W, t / 2),
                        pitch=-math.degrees(slope) if up else math.degrees(slope)))
    x0, x1 = V.PLATFORM
    out.append(Geom("box", COURSE, pos=((x0 + x1) / 2, 0, V.PLATFORM_H / 2),
                    size=((x1 - x0) / 2, V.COURSE_HALF_W, V.PLATFORM_H / 2)))
    out += [Geom("cylinder", COURSE, pos=(x, y, V.PILLAR_H / 2), size=(V.PILLAR_R, V.PILLAR_H / 2, 0))
            for x, y in V.PILLARS]
    out.append(Geom("box", CRATE_RGBA, pos=(*CRATE_REST, V.CRATE_HALF), size=(V.CRATE_HALF,) * 3, yaw=12))
    return out


COURSE_PIECES = _course_pieces()


def gate(t: float) -> list[Geom]:
    out = []
    for x in V.GATE_X:
        out += laser((x, -V.ROOM_HALF_W + 0.03, V.BEAM_Z), (x, V.ROOM_HALF_W - 0.03, V.BEAM_Z))
        for y in (-V.ROOM_HALF_W + 0.025, V.ROOM_HALF_W - 0.025):
            out.append(Geom("box", (0.15, 0.15, 0.17, 1), pos=(x, y, V.BEAM_Z), size=(0.012, 0.008, 0.02),
                            emission=0.1))
    return out


def gold_spot(t: float) -> list[Geom]:
    gx, gy = V.GOLD_AT
    return [Geom("cylinder", (1.0, 0.75, 0.25, 0.22), pos=(gx, gy, 0.0008), size=(0.10, 0.0007, 0), emission=0.8)]


def gold_bar(t: float) -> list[Geom]:
    """The ingot where it lies before the crab gets to it (takes recorded without it)."""
    from gold_scene import INGOT_HALF

    gx, gy = V.GOLD_AT
    return [Geom("box", GOLD, pos=(gx, gy, INGOT_HALF[2]), size=INGOT_HALF, specular=0.8)]


def room(*extra):
    """Set dressing for a take: walls and grid, the gold's spot, the gate, plus `extra`."""
    def dress(t: float) -> list[Geom]:
        out = list(WALLS) + gold_spot(t) + gate(t)
        for e in extra:
            out += e(t) if callable(e) else e
        return out
    return dress


# ── lights ────────────────────────────────────────────────────────────────────

BANK_X = (0.4, 1.9, 3.4, 4.8)


def lights(on: dict[str, float] | None = None) -> list[Spot]:
    """Four ceiling banks down the room, the gold's warm spot and a key light that
    rides with the crab: with the headlight and the overhead, MuJoCo's eight."""
    on = on or {}
    out = [Spot(pos=(x, 0.0, 1.35), aim=(x + 0.15, 0.0, 0.0), color=(0.62, 0.68, 0.82), cutoff=34,
                exponent=6, on_at=on.get(f"bank{i}")) for i, x in enumerate(BANK_X)]
    gx, gy = V.GOLD_AT
    out.append(Spot(pos=(gx, gy, 1.0), aim=(gx, gy, 0.0), color=(1.0, 0.82, 0.5), cutoff=13, exponent=4,
                    on_at=on.get("gold")))
    out.append(Spot(pos=(-0.45, -0.55, 0.65), aim=(0.0, 0.0, 0.08), color=(0.75, 0.78, 0.85), cutoff=22,
                    exponent=3, shadow=False, follow=True, on_at=on.get("key")))
    return out


LIT = lights()

# ── takes set down in the room ────────────────────────────────────────────────

JUMP_PLACE = V.JUMP_AT
PUSH_PLACE = V.PUSH_AT

_cache: dict[str, object] = {}


def _take(name: str, place):
    from stage import Take

    key = f"{name}@{place}"
    if key not in _cache:
        _cache[key] = Take(name, place)
    return _cache[key]


# ── the sweeping beam (jump take, set down at JUMP_AT) ────────────────────────

PEAK_T, SWEEP_V, SWEEP_Z = 0.48, 2.0, 0.08


def sweep(t: float) -> list[Geom]:
    if "peak_x" not in _cache:
        _cache["peak_x"] = float(_take("jump", JUMP_PLACE).robot_pos(PEAK_T)[0])
    x = _cache["peak_x"] + SWEEP_V * (PEAK_T - t)
    w = V.ROOM_HALF_W - 0.03
    out = laser((x, -w, SWEEP_Z), (x, w, SWEEP_Z), core=0.002, halo=0.009)
    out += [Geom("box", (0.15, 0.15, 0.17, 1), pos=(x, y, SWEEP_Z), size=(0.015, 0.008, 0.025)) for y in (-w, w)]
    return out


# ── the shots ─────────────────────────────────────────────────────────────────

REVEAL_ON = {"bank0": 0.9, "bank1": 1.6, "bank2": 2.3, "bank3": 3.0, "gold": 3.9, "key": 0.9}


def _reveal_ambient(t: float) -> float:
    return 0.06 + 0.94 * ramp(t, 0.9, 3.4)


COURSE_SET = room()
ELSEWHERE = room(COURSE_PIECES)
JUMPSET = room(COURSE_PIECES, sweep, gold_bar)
FAR = room(COURSE_PIECES, gold_bar)

SHOTS: list[Shot] = [
    # Dark room; the banks strike one by one down to the gold.
    Shot("reveal", "course", TimeMap([(6.8, 0.0, 0.0)]),
         # The camera stands at the start wall (x -0.75, 0.55 m up) with a 60 degree
         # lens and lifts its gaze from the crab to the far end as each bank strikes:
         # the crab 31 degrees below the eye, the gold 4 degrees, both in frame.
         CameraPath([Key(0.0, 1.0, 0, -30, lookat=(0.116, 0.0, 0.05)),
                     Key(1.2, 1.0, 0, -30, lookat=(0.116, 0.0, 0.05)),
                     Key(6.8, 3.0, 0, -17, lookat=(2.119, 0.0, -0.327))]),
         fovy=60,
         dressing=[room(gold_bar)], spots=lights(REVEAL_ON), recolor=heist_look, ambient=_reveal_ambient,
         fog=(3.0, 12.0)),
    # The course, one take.
    Shot("secam", "course", TimeMap([(2.9, 0.3, 3.4)]),
         CameraPath([Key(0.0, 1.55, 35, -36, lookat=(0.6, 0.0, 0.05)),
                     Key(2.9, 1.45, 28, -34, lookat=(0.8, 0.0, 0.05))]),
         fovy=58, dressing=[room(gold_bar)], spots=LIT, recolor=heist_look, fog=(1.5, 6.0)),
    Shot("ramp", "course", TimeMap([(3.3, 3.4, 6.4)]),
         CameraPath([Key(0.0, 0.62, 90, -1), Key(3.3, 0.55, 75, 0)], shake=0.4),
         dressing=[room(gold_bar)], spots=LIT, recolor=heist_look),
    Shot("platform", "course", TimeMap([(2.8, 6.4, 9.0)]),
         CameraPath([Key(0.0, 0.62, 200, -6, offset=(0, 0, 0.02)),
                     Key(2.8, 0.52, 175, -3, offset=(0, 0, 0.02))], shake=0.4),
         dressing=[room(gold_bar)], spots=LIT, recolor=heist_look),
    Shot("slalom", "course", TimeMap([(3.9, 9.0, 15.0)]),
         CameraPath([Key(0.0, 1.35, 90, -88, lookat=(1.95, 0.0, 0.0)),
                     Key(3.9, 1.35, 90, -88, lookat=(2.85, 0.0, 0.0))]),
         dressing=[room(gold_bar)], spots=LIT, recolor=heist_look),
    Shot("crate", "course", TimeMap([(1.5, 14.7, 15.9)]),
         CameraPath([Key(0.0, 0.62, 150, -14, offset=(0.12, 0, 0.0)),
                     Key(1.5, 0.66, 138, -15, offset=(0.12, 0, 0.0))], shake=0.5),
         dressing=[room(gold_bar)], spots=LIT, recolor=heist_look),
    # The duck, made obvious. The camera stands beyond the gate exactly at beam height
    # (16 cm) with a long lens, a little to the side of the crate's path: every point at
    # that height, the beams and the top of a 16 cm crab alike, falls on one horizontal
    # line. Standing, the crab's top (17.5-18 cm) shows above the line; in slow motion it
    # drops below it (crouching between x 3.05 and 3.35, take 15.9-17.5 s) and goes under.
    Shot("duck", "course", TimeMap([(0.6, 15.9, 16.2), (2.6, 16.2, 17.5), (1.1, 17.5, 18.6)]),
         CameraPath([Key(0.0, 1.24, 194, 0, lookat=(3.20, 0.0, V.BEAM_Z)),
                     Key(4.3, 1.05, 194, 0, lookat=(3.42, 0.0, V.BEAM_Z))], shake=0.15),
         fovy=17, dressing=[room(gold_bar)], spots=LIT, recolor=heist_look),
    Shot("gate_out", "course", TimeMap([(1.6, 21.0, 23.0)]),
         CameraPath([Key(0.0, 0.62, 15, -5), Key(1.6, 0.70, 5, -6)], shake=0.4),
         dressing=[room(gold_bar)], spots=LIT, recolor=heist_look),
    # The sweeping beam. First the crab's own view: the beam coming at it down the
    # room (take time below zero holds the crab on its first frame while the beam,
    # which runs on take time, is still far off).
    Shot("pov", "jump", TimeMap([(1.6, -0.62, 0.10)]),
         CameraPath([Key(0.0, 0.50, 0, -2, offset=(0.65, 0, -0.02)),
                     Key(1.6, 0.50, 0, -1, offset=(0.65, 0, -0.02))], shake=0.6),
         place=JUMP_PLACE, dressing=[JUMPSET], spots=LIT, recolor=heist_look),
    # Then from the side and three-quarters front, about seven times slower: it waits,
    # and jumps at the last moment; time stops at the top of the jump, the camera goes
    # round it, and it lands.
    Shot("jump_side", "jump", TimeMap([(2.1, 0.10, 0.46)]),
         CameraPath([Key(0.0, 0.85, 30, 3, offset=(0, 0, 0.0)),
                     Key(2.1, 0.80, 30, 5, lookat=None, offset=(0, 0, 0.0))]),
         place=JUMP_PLACE, dressing=[JUMPSET], spots=LIT, recolor=heist_look),
    Shot("bullet", "jump", TimeMap([(2.7, 0.46, 0.46)]),
         CameraPath([Key(0.0, 0.80, 30, 5), Key(2.7, 0.80, 210, -12)]),
         place=JUMP_PLACE, dressing=[JUMPSET], spots=LIT, recolor=heist_look),
    Shot("land", "jump", TimeMap([(1.6, 0.46, 0.95)]),
         CameraPath([Key(0.0, 0.80, 210, -12), Key(1.6, 0.95, 216, -8, offset=(0, 0, -0.08))], shake=0.4),
         place=JUMP_PLACE, dressing=[JUMPSET], spots=LIT, recolor=heist_look),
    # The gold: the crab turns to it, claws meet it, and it goes out of the door.
    Shot("gold_turn", "push", TimeMap([(1.6, 0.6, 3.4)]),
         CameraPath([Key(0.0, 0.85, 90, -86, lookat=(V.GOLD_AT[0], V.GOLD_AT[1] - 0.16, 0.0)),
                     Key(1.6, 0.75, 90, -86, lookat=(V.GOLD_AT[0], V.GOLD_AT[1] - 0.14, 0.0))]),
         place=PUSH_PLACE, dressing=[ELSEWHERE], spots=LIT, recolor=heist_look),
    Shot("push_contact", "push", TimeMap([(2.0, 3.0, 4.75)]),
         CameraPath([Key(0.0, 0.42, 200, -6, lookat=(V.GOLD_AT[0], V.GOLD_AT[1] - 0.06, 0.04)),
                     Key(2.0, 0.36, 210, -5, lookat=(V.GOLD_AT[0], V.GOLD_AT[1] - 0.02, 0.04))], shake=0.3),
         place=PUSH_PLACE, dressing=[ELSEWHERE], spots=LIT, recolor=heist_look),
    # From outside the door, the gold coming at the lens with the crab behind it.
    Shot("push_door", "push", TimeMap([(4.6, 4.6, 11.0)]),
         CameraPath([Key(0.0, 1.10, -90, -9, lookat=(V.DOOR[0], 0.45, 0.06)),
                     Key(4.6, 0.85, -90, -7, lookat=(V.DOOR[0] + 0.02, 0.62, 0.06))], shake=0.4),
         place=PUSH_PLACE, dressing=[ELSEWHERE], spots=LIT, recolor=heist_look, cull=False),
    Shot("escape_secam", "push", TimeMap([(3.6, 9.5, 16.0)]),
         CameraPath([Key(0.0, 1.15, 120, -32, lookat=(V.DOOR[0], 0.50, 0.05)),
                     Key(3.6, 1.15, 110, -30, lookat=(V.DOOR[0], 0.75, 0.05))]),
         fovy=58, place=PUSH_PLACE, dressing=[ELSEWHERE], spots=LIT, recolor=heist_look, fog=(1.5, 6.0)),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--only", nargs="+")
    ap.add_argument("--preview", action="store_true", help="640x360 for a quick look")
    args = ap.parse_args()
    size = (640, 360) if args.preview else (1920, 1080)
    for shot in SHOTS:
        if args.only and shot.name not in args.only:
            continue
        out = OUT / ("preview" if args.preview else "") / f"{shot.name}.mp4"
        render(shot, out, size=size)
        print(f"[film] {out.relative_to(OUT.parents[1])}  {shot.time.duration:.1f} s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
