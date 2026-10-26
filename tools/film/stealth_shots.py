"""The fourth film's shots, "OPERATION: COOKIE": 2 a.m., three cookies on the floor, a
robot vacuum on patrol, and a crab under the bed who wants them.

    upstream/jumper/.venv/bin/python tools/film/stealth_shots.py --preview      # cheap MuJoCo look
    upstream/jumper/.venv/bin/python tools/film/blend_bake.py --film stealth    # then Blender

One take (renders/stealth/stealth, picked by check_stealth.py): the crab's run in
tools/film/stealth_scene.py against the vacuum's patrol, both in one simulation. The
vacuum is a kinematic body on its path, the crab the walking policy steered to its
timetable, the cookies pushed home by the crab's claws.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bedroom_shots as BS
import stealth_scene as T
from stage import CameraPath, Geom, Key, Shot, TimeMap, render

OUT = Path(__file__).resolve().parents[2] / "renders" / "stealth_shots"


def cover() -> list[Geom]:
    (x, y), (hx, hy, hz) = T.COVER
    tones = [(0.20, 0.30, 0.50, 1), (0.55, 0.18, 0.15, 1), (0.80, 0.66, 0.35, 1)]
    n = 3
    return [Geom("box", tones[i], pos=(x + 0.01 * (i - 1), y, (2 * i + 1) * hz / n), size=(hx - 0.008 * i, hy, hz / n - 0.0008),
                 yaw=4 * (i - 1)) for i in range(n)]


def legs() -> list[Geom]:
    return [Geom("cylinder", BS.WALNUT, pos=(x, y, T.CLEAR / 2), size=(T.LEG_R, T.CLEAR / 2, 0)) for x, y in T.LEGS]


SET = [*cover(), *legs()]


def stealth_look(model, take) -> None:
    import mujoco

    BS.bedroom_look(model, take)
    for g in range(model.ngeom):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, g) or ""
        if name == "cover":
            model.geom_rgba[g][3] = 0.0  # drawn as books
        elif name.endswith("vacuum"):
            model.geom_rgba[g] = (0.18, 0.18, 0.20, 1)
        elif name.endswith("cookie"):
            model.geom_rgba[g] = (0.78, 0.55, 0.30, 1)


def shot(name, time, camera, *, eyes=None, fovy=45.0, **kw) -> Shot:
    out = Shot(name, "stealth", time, camera, dressing=[BS.room(SET)], spots=BS.lights(), recolor=stealth_look,
               group="stealth", eyes=eyes, look=BS.ROOM_LOOK, fovy=fovy, fog=(6.0, 16.0), **kw)
    out.door_at = None
    out.film = "stealth"
    return out


faces = BS.faces
pov = BS.pov
CX, CY = T.COOKIE_AT

SHOTS: list[Shot] = [
    # Eyes in the dark under the bed.
    shot("lair", TimeMap([(2.6, 0.0, 1.8)]),
         CameraPath([pov(0.0, (1.60, 1.70, 0.10), (1.60, 2.75, 0.10)), pov(2.6, (1.60, 1.95, 0.09), (1.60, 2.75, 0.10))]),
         eyes=faces((0.0, "open"), (1.3, "focus")), fovy=40),
    # The target: three cookies in the moonlight.
    shot("target", TimeMap([(2.4, 0.0, 0.0)]),
         CameraPath([pov(0.0, (CX - 0.30, CY - 0.45, 0.08), (CX, CY, 0.02)), pov(2.4, (CX - 0.22, CY - 0.34, 0.07), (CX, CY, 0.02))]),
         fovy=40),
    # The threat: the vacuum on its rounds, from the floor.
    shot("patrol", TimeMap([(2.6, 1.5, 5.0)]),
         CameraPath([pov(0.0, (2.15, 0.15, 0.05), (1.00, 0.45, 0.06)), pov(2.6, (2.15, 0.15, 0.05), (1.55, 0.45, 0.06))]),
         eyes=faces((0.0, "focus")), fovy=40),
    # Out from under the bed, crouched.
    shot("sneak", TimeMap([(2.6, 2.3, 6.4)]),
         CameraPath([Key(0.0, 0.85, 200, -8, offset=(0, 0, 0.0)), Key(2.6, 0.80, 190, -6, offset=(0, 0, 0.0))]),
         eyes=faces((0.0, "focus")), fovy=42),
    # Frozen behind the books as the vacuum goes by beyond them.
    shot("hide", TimeMap([(3.2, 5.6, 9.2)]),
         CameraPath([pov(0.0, (1.70, 2.05, 0.12), (2.05, 0.60, 0.05)), pov(3.2, (1.74, 2.00, 0.12), (2.15, 0.60, 0.05))]),
         eyes=faces((0.0, "focus"), (0.6, "panic"), (2.6, "open")), fovy=46),
    # From above: round the books and down toward the cookies, the vacuum far off.
    shot("slip", TimeMap([(2.6, 9.2, 18.0)]),
         CameraPath([Key(0.0, 3.6, 90, -88, lookat=(2.35, 1.25, 0.0)), Key(2.6, 3.4, 90, -88, lookat=(2.55, 1.15, 0.0))]),
         eyes=faces((0.0, "focus")), fovy=50),
    # Behind the cookies; the push begins.
    shot("grab", TimeMap([(2.6, 18.4, 22.6)]),
         CameraPath([pov(0.0, (CX + 0.05, CY + 0.55, 0.06), (CX, CY - 0.1, 0.06)), pov(2.6, (CX + 0.05, CY + 0.70, 0.06), (CX, CY + 0.1, 0.06))]),
         eyes=faces((0.0, "focus"), (1.6, "happy"), (2.2, "focus")), fovy=42),
    # Side by side: the crab pushing home, the vacuum heading the same way a metre off.
    shot("race", TimeMap([(2.8, 22.0, 26.6)]),
         CameraPath([pov(0.0, (4.60, 0.55, 0.16), (3.40, 1.30, 0.06)), pov(2.8, (4.60, 0.75, 0.16), (3.40, 1.75, 0.06))]),
         eyes=faces((0.0, "focus")), fovy=48),
    # It turns; it comes back along the bed; the crab is not home yet.
    shot("close_call", TimeMap([(1.2, 27.4, 28.6), (2.6, 28.6, 30.4), (0.8, 30.4, 31.4)]),
         CameraPath([pov(0.0, (2.55, 3.30, 0.10), (3.20, 1.80, 0.06)), pov(4.6, (2.60, 3.30, 0.10), (2.80, 1.80, 0.06))]),
         eyes=faces((0.0, "focus"), (1.4, "panic"), (3.8, "focus")), fovy=52),
    # Home: under the bench with the cookies.
    shot("safe", TimeMap([(3.4, 31.0, 35.0)]),
         CameraPath([pov(0.0, (2.90, 1.75, 0.08), (2.90, 2.70, 0.09)), pov(3.4, (2.90, 1.95, 0.08), (2.90, 2.70, 0.09))]),
         eyes=faces((0.0, "focus"), (1.8, "happy")), fovy=42),
    # The vacuum rolls off none the wiser (the title sits over this).
    shot("title", TimeMap([(3.6, 34.5, 37.4)]),
         CameraPath([pov(0.0, (2.90, 1.85, 0.08), (2.40, 2.60, 0.10)), pov(3.6, (2.92, 1.90, 0.08), (2.40, 2.60, 0.10))]),
         eyes=faces((0.0, "happy")), fovy=50),
]


def props(take) -> list[dict]:
    """The take's loose and driven things for blend_bake: the vacuum and the cookies."""
    out = []
    if take.body("vacuum/vacuum") >= 0:
        out.append({"body": "vacuum/vacuum", "kind": "vacuum", "half": [T.VAC_R, T.VAC_R, T.VAC_H / 2]})
    if take.body("cookie/cookie") >= 0:
        out.append({"body": "cookie/cookie", "kind": "cookies", "half": [T.COOKIE_R, T.COOKIE_R, T.COOKIE_H / 2]})
    return out


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
