"""The third film's shots, "UNDERCLAW": a little crab, a mountain of books, a month of
training, the top at sunrise.

    upstream/jumper/.venv/bin/python tools/film/rocky_shots.py --preview     # cheap MuJoCo look
    upstream/jumper/.venv/bin/python tools/film/blend_bake.py --film rocky   # then Blender

The set is the bedroom (`bedroom_shots.ROOM`) with the stair of books from
`rocky_scene.py` in the middle of the floor. Takes: renders/rocky/rocky_<kind> (picked
by `pick_rocky.py`), plus two recorded on a flat floor and set down where the story
needs them: the jump (`skills/ref_free_jump`, on the floor for practice and on the
summit's flat top for the finale) and the raised claw (`skills/gesture_salute`, on the
summit). Every motion is a trained policy in MuJoCo physics.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bedroom_shots as BS
import rocky_scene as R
from stage import CameraPath, Geom, Key, Shot, TimeMap, render

OUT = Path(__file__).resolve().parents[2] / "renders" / "rocky_shots"

BOOK_TONES = [(0.55, 0.16, 0.14, 1), (0.16, 0.30, 0.48, 1), (0.82, 0.66, 0.30, 1), (0.22, 0.42, 0.28, 1),
              (0.92, 0.90, 0.84, 1), (0.40, 0.26, 0.44, 1)]
PAGES = (0.95, 0.93, 0.86, 1)


def stair() -> list[Geom]:
    """The stair drawn as what it is: stacks of books (each tier is 4 cm, two books of
    2 cm), hardcovers laid as ramps."""
    out = []
    k = 0
    for x0, x1, h in R.TIERS:
        n = round(h / 0.02)
        for i in range(n):
            tone = BOOK_TONES[k % len(BOOK_TONES)]
            k += 1
            out.append(Geom("box", tone, pos=((x0 + x1) / 2, R.STAIR_Y, 0.01 + 0.02 * i),
                            size=((x1 - x0) / 2, R.HALF_W, 0.0098)))
            out.append(Geom("box", PAGES, pos=((x0 + x1) / 2 + 0.004, R.STAIR_Y, 0.01 + 0.02 * i),
                            size=((x1 - x0) / 2 - 0.006, R.HALF_W + 0.001, 0.0085)))
    import math

    for j, (x0, x1, z0, z1) in enumerate(R.RAMPS):
        run, rise = x1 - x0, z1 - z0
        slope = math.atan2(rise, run)
        cx = (x0 + x1) / 2 + 0.005 * math.sin(slope)
        cz = (z0 + z1) / 2 - 0.005 * math.cos(slope)
        out.append(Geom("box", BOOK_TONES[(j + 3) % len(BOOK_TONES)], pos=(cx, R.STAIR_Y, cz),
                        size=(math.hypot(run, rise) / 2, R.HALF_W, 0.005), pitch=-math.degrees(slope)))
        if z0 > 0:
            out.append(Geom("box", BOOK_TONES[(j + 1) % len(BOOK_TONES)], pos=((x0 + x1) / 2, R.STAIR_Y, z0 / 2),
                            size=(run / 2, R.HALF_W, z0 / 2 - 0.0005)))
    return out


#: The prize at the top: a little flag in a cork, at the summit's back corner (the
#: crab stands 0.37 m from it).
FLAG_AT = (3.52, R.STAIR_Y + 0.25)


def flag() -> list[Geom]:
    x, y = FLAG_AT
    z = R.SUMMIT[2]
    return [Geom("cylinder", (0.72, 0.55, 0.36, 1), pos=(x, y, z + 0.015), size=(0.018, 0.015, 0)),
            Geom("cylinder", (0.85, 0.85, 0.85, 1), pos=(x, y, z + 0.17), size=(0.0035, 0.155, 0)),
            Geom("box", (0.95, 0.75, 0.15, 1), pos=(x, y - 0.065, z + 0.28), size=(0.002, 0.065, 0.042),
                 emission=0.15)]


def legs() -> list[Geom]:
    from bedroom_scene import CLEAR, LEG_R, LEGS

    return [Geom("cylinder", BS.WALNUT, pos=(x, y, CLEAR / 2), size=(LEG_R, CLEAR / 2, 0)) for x, y in LEGS]


def weight_at_rest() -> list[Geom]:
    """The heavy book where it lies before the push (in takes that do not have it)."""
    return [Geom("box", (0.55, 0.12, 0.12, 1), pos=(*R.WEIGHT_AT, R.WEIGHT_HALF[2]), size=R.WEIGHT_HALF)]


SET = [*stair(), *flag(), *legs()]


def rocky_look(model, take) -> None:
    import mujoco

    BS.bedroom_look(model, take)
    for g in range(model.ngeom):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, g) or ""
        if name.startswith(("tier_", "ramp_")):
            model.geom_rgba[g][3] = 0.0  # drawn as books by `stair`
        elif name == "weight":
            model.geom_rgba[g] = (0.55, 0.12, 0.12, 1)


def faces(*beats):
    return BS.faces(*beats)


def shot(name, take, time, camera, *, place=None, weight=False, eyes=None, fovy=45.0, **kw) -> Shot:
    extra = [SET] + ([] if weight else [weight_at_rest()])
    out = Shot(name, take, time, camera, dressing=[BS.room(*extra)], spots=BS.lights(), recolor=rocky_look,
               group="rocky", eyes=eyes, look=BS.ROOM_LOOK, fovy=fovy, fog=(6.0, 16.0), place=place, **kw)
    out.door_at = None
    out.film = "rocky"
    out.weight_rest = not weight  # the dictionary lies at rest in takes without it
    return out


TOP = (*R.SUMMIT_TOP[:2], -90.0, R.SUMMIT[2])
#: Flat-floor drills set down where the stair is not in the camera's way.
SQUAT_SPOT = (4.10, 0.55, 200.0)
SHUFFLE_SPOT = (0.35, 1.85, -90.0)
JUMP_FLOOR = (4.0, 0.95, 200.0)

SHOTS: list[Shot] = [
    # Dawn, day 1. Low behind the crab: a tiny crab, a mountain, the flag on top.
    # (from behind the crab at the foot of the stair, at its eye level: the books
    # tower over it; seen from the side, 12 cm of books read as a step)
    shot("summit_reveal", "rocky_climb", TimeMap([(3.0, 0.0, 0.4)]),
         CameraPath([BS.pov(0.0, (0.06, 0.66, 0.05), (2.60, 1.22, 0.15)),
                     BS.pov(3.0, (0.12, 0.72, 0.05), (2.70, 1.22, 0.16))]),
         eyes=faces((0.0, "open"), (1.5, "focus")), fovy=50),
    # It walks straight at the wall and tries to climb it.
    shot("fail", "rocky_fail", TimeMap([(3.4, 0.9, 5.5)]),
         CameraPath([Key(0.0, 0.75, 180, -6, offset=(0, 0.15, 0.02)),
                     Key(3.4, 0.70, 175, -5, offset=(0, 0.20, 0.03))], shake=0.3),
         eyes=faces((0.0, "focus"), (1.6, "panic"), (2.8, "focus")), fovy=45),
    # Backs off, turns away, deflated.
    shot("defeat", "rocky_fail", TimeMap([(3.0, 5.5, 9.8)]),
         CameraPath([BS.pov(0.0, (2.62, -0.05, 0.14), (3.25, 0.50, 0.06)),
                     BS.pov(3.0, (2.70, 0.00, 0.12), (3.25, 0.45, 0.06))]),
         eyes=faces((0.0, "guilty")), fovy=45),
    # The montage.
    shot("squats", "rocky_squats", TimeMap([(2.8, 1.2, 6.8)]),
         CameraPath([Key(0.0, 0.62, 20, -2), Key(2.8, 0.58, 30, -1)], shake=0.3),
         place=SQUAT_SPOT, eyes=faces((0.0, "focus")), fovy=42),
    shot("shuffle", "rocky_shuffle", TimeMap([(2.8, 1.0, 7.6)]),
         CameraPath([Key(0.0, 1.05, 90, -18, lookat=(0.65, 1.85, 0.05)),
                     Key(2.8, 1.00, 90, -16, lookat=(0.65, 1.85, 0.05))]),
         place=SHUFFLE_SPOT, eyes=faces((0.0, "focus")), fovy=48),
    shot("push", "rocky_push", TimeMap([(3.0, 1.5, 15.0)]),
         CameraPath([Key(0.0, 0.70, 200, -6, offset=(0.25, 0, 0.02)),
                     Key(3.0, 0.66, 210, -5, offset=(0.25, 0, 0.02))], shake=0.3),
         weight=True, eyes=faces((0.0, "focus")), fovy=45),
    shot("jump_practice", "skills/ref_free_jump", TimeMap([(0.6, 0.0, 0.3), (1.6, 0.3, 0.6), (0.6, 0.6, 1.4)]),
         CameraPath([Key(0.0, 0.85, 120, 2), Key(2.8, 0.80, 110, 3)]),
         place=JUMP_FLOOR, eyes=faces((0.0, "focus"), (0.8, "happy")), fovy=45),
    # Day 30, sunrise: up the books.
    shot("climb_low", "rocky_climb", TimeMap([(2.6, 2.2, 5.2)]),
         CameraPath([Key(0.0, 0.70, 160, -2, offset=(0.05, 0, 0.0)),
                     Key(2.6, 0.62, 150, -1, offset=(0.05, 0, 0.0))], shake=0.25),
         eyes=faces((0.0, "focus")), fovy=42),
    shot("climb_side", "rocky_climb", TimeMap([(3.0, 5.2, 11.2)]),
         CameraPath([Key(0.0, 1.10, 90, -10, offset=(0, 0, 0.02)),
                     Key(3.0, 1.10, 90, -10, offset=(0, 0, 0.02))]),
         eyes=faces((0.0, "focus")), fovy=45),
    shot("climb_top", "rocky_climb", TimeMap([(3.0, 11.2, 14.2)]),
         CameraPath([Key(0.0, 0.80, 0, -20, offset=(0, 0, 0.02)),
                     Key(3.0, 0.70, 20, -16, offset=(0, 0, 0.02))], shake=0.2),
         eyes=faces((0.0, "focus"), (2.4, "open")), fovy=45),
    # On top: it turns to the room and jumps; time stops at the top of the jump.
    shot("summit_turn", "rocky_climb", TimeMap([(2.0, 14.0, 19.0)]),
         CameraPath([Key(0.0, 0.95, 90, 4, offset=(0, 0, 0.05)), Key(2.0, 0.90, 92, 5, offset=(0, 0, 0.05))]),
         eyes=faces((0.0, "open"), (1.2, "happy")), fovy=45),
    shot("summit_jump", "skills/ref_free_jump", TimeMap([(0.7, 0.0, 0.40), (2.4, 0.48, 0.48), (0.9, 0.48, 1.3)]),
         CameraPath([Key(0.0, 0.95, 90, 4), Key(0.7, 0.95, 90, 4), Key(3.1, 0.95, 230, 2), Key(4.0, 1.0, 240, 0)]),
         place=TOP, eyes=faces((0.0, "happy")), fovy=45),
    # The claw goes up against the sunrise.
    shot("victory", "skills/gesture_salute", TimeMap([(4.2, 1.2, 4.2)]),
         CameraPath([Key(0.0, 0.80, 90, 14, offset=(0, 0, 0.10)), Key(4.2, 0.95, 92, 18, offset=(0, 0, 0.12))]),
         place=TOP, eyes=faces((0.0, "happy")), fovy=50),
]


def props(take) -> list[dict]:
    """The take's loose things for blend_bake: the heavy book, if the take has it."""
    b = take.body("weight/weight")
    return [{"body": "weight/weight", "kind": "book", "half": list(R.WEIGHT_HALF)}] if b >= 0 else []


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--only", nargs="+")
    ap.add_argument("--preview", action="store_true", help="640x360 for a quick look")
    args = ap.parse_args()
    size = (640, 360) if args.preview else (1920, 1080)
    for s in SHOTS:
        if args.only and s.name not in args.only:
            continue
        out = OUT / ("preview" if args.preview else "") / f"{s.name}.mp4"
        render(s, out, size=size)
        print(f"[film] {out.relative_to(OUT.parents[1])}  {s.time.duration:.1f} s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
