"""The second film's shots, "ROOM: CLEAN*": mom is 30 seconds away and six crabs tidy
the bedroom by shoving everything under the bed.

    upstream/jumper/.venv/bin/python tools/film/bedroom_shots.py              # every shot, 1080p
    upstream/jumper/.venv/bin/python tools/film/bedroom_shots.py --only wide --preview

The room is `tools/film/bedroom_scene.py`: six crabs, each its own physical take
(`renders/crew/crab<k>`), drawn into one picture (`Shot.crew`) along the plan that
keeps them apart (`tools/film/check_crew.py` measures it). Every sock and shirt moves
because a crab's legs and body push it. The walls, the bed above its legs, the bench,
the rug, the window and the door are drawn; the furniture's legs are physical.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bedroom_scene as B
from stage import (
    CameraPath,
    Geom,
    Key,
    Look,
    Shot,
    Spot,
    TimeMap,
    paint_crab,
    ramp,
    render,
)

OUT = Path(__file__).resolve().parents[2] / "renders" / "bedroom_shots"
CREW = tuple(f"crab{k}" for k in range(1, len(B.LANES)))

# ── the look ──────────────────────────────────────────────────────────────────

#: An afternoon room: warm ambient, the window's daylight, air that fades to cream.
ROOM_LOOK = Look((0.20, 0.19, 0.17), (0.14, 0.13, 0.12), (0.0, 0.0, 0.0), (0.93, 0.89, 0.82, 1.0), specular=0.08)

OAK = (0.66, 0.48, 0.32, 1.0)
SEAM = (0.47, 0.32, 0.21, 1.0)
WALL = (0.78, 0.84, 0.78, 1.0)
ACCENT = (0.95, 0.80, 0.68, 1.0)
TRIM = (0.96, 0.95, 0.91, 1.0)
WALNUT = (0.40, 0.26, 0.17, 1.0)
PINE = (0.80, 0.64, 0.45, 1.0)
DUVET = (0.33, 0.47, 0.78, 1.0)
DUVET_STRIPE = (0.93, 0.93, 0.95, 1.0)
LINEN = (0.97, 0.96, 0.93, 1.0)
RUG = (0.93, 0.58, 0.52, 1.0)
RUG_RING = (0.98, 0.84, 0.72, 1.0)
CUSHION = (0.95, 0.74, 0.27, 1.0)
SKY = (0.72, 0.86, 1.0, 1.0)

#: The things, by crab: socks bright and odd, shirts in plain colours.
SOCKS = [(0.95, 0.35, 0.40, 1), (0.30, 0.75, 0.45, 1), (0.98, 0.80, 0.20, 1),
         (0.55, 0.40, 0.85, 1), (0.20, 0.70, 0.85, 1), (0.98, 0.55, 0.20, 1)]
SHIRTS = [(0.20, 0.30, 0.55, 1), (0.85, 0.20, 0.25, 1), (0.25, 0.55, 0.35, 1),
          (0.95, 0.95, 0.95, 1), (0.30, 0.30, 0.32, 1), (0.60, 0.75, 0.90, 1)]


def bedroom_look(model, take) -> None:
    import mujoco

    paint_crab(model, take)
    for g in range(model.ngeom):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, g) or ""
        if name == "terrain":
            model.geom_rgba[g] = OAK
        elif name.startswith("leg_"):
            model.geom_rgba[g] = WALNUT
        elif name.endswith("/item"):
            model.geom_rgba[g][3] = 0.0  # the box is the physics; `clothes` draws the cloth


def _crab_index(take) -> int:
    return int(take.name[4:]) if take.name.startswith("crab") and take.name[4:].isdigit() else 3


def _frame(take, body: int):
    import numpy as np

    d = take.data
    return np.asarray(d.xpos[body]), np.asarray(d.xmat[body]).reshape(3, 3)


def _local(p, R, x, y, z):
    import numpy as np

    return tuple(p + R @ np.array([x, y, z]))


def _turned(R, yaw_deg: float, roll_deg: float = 0.0):
    import numpy as np

    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    cr, sr = math.cos(math.radians(roll_deg)), math.sin(math.radians(roll_deg))
    yaw = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    roll = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return tuple((R @ yaw @ roll).ravel())


def shirt(p, R, half, rgba) -> list[Geom]:
    """A crumpled T-shirt the size of its box: a body, two sleeves, a fold, a collar."""
    hx, hy, hz = half
    dark = tuple(0.8 * c for c in rgba[:3]) + (1.0,)
    return [
        Geom("ellipsoid", rgba, pos=_local(p, R, 0.0, 0.0, -0.2 * hz), size=(0.85 * hx, 0.80 * hy, 0.75 * hz),
             mat=_turned(R, 0), specular=0.05),
        Geom("ellipsoid", rgba, pos=_local(p, R, 0.35 * hx, 0.75 * hy, -0.35 * hz), size=(0.40 * hx, 0.28 * hy, 0.5 * hz),
             mat=_turned(R, 35), specular=0.05),
        Geom("ellipsoid", rgba, pos=_local(p, R, 0.30 * hx, -0.78 * hy, -0.35 * hz), size=(0.38 * hx, 0.26 * hy, 0.5 * hz),
             mat=_turned(R, -28), specular=0.05),
        Geom("ellipsoid", dark, pos=_local(p, R, -0.15 * hx, 0.1 * hy, 0.35 * hz), size=(0.55 * hx, 0.18 * hy, 0.45 * hz),
             mat=_turned(R, 18), specular=0.05),
        Geom("ellipsoid", dark, pos=_local(p, R, 0.72 * hx, 0.0, 0.1 * hz), size=(0.12 * hx, 0.30 * hy, 0.35 * hz),
             mat=_turned(R, 0), specular=0.05),
    ]


def sock(p, R, half, rgba) -> list[Geom]:
    """A sock lying flat: the leg along the box, the foot turned at the heel, a white
    cuff, a stripe and a toe."""
    hx, hy, hz = half
    flat = 0.75 * hz
    z = -hz + flat
    leg = (-0.25 * hx, -0.40 * hy)
    out = [Geom("ellipsoid", rgba, pos=_local(p, R, *leg, z), size=(0.72 * hx, 0.42 * hy, flat), mat=_turned(R, 0)),
           Geom("ellipsoid", rgba, pos=_local(p, R, 0.50 * hx, 0.22 * hy, z), size=(0.62 * hx, 0.36 * hy, 0.9 * flat),
                mat=_turned(R, 62)),
           Geom("ellipsoid", TRIM, pos=_local(p, R, -0.88 * hx, -0.40 * hy, z + 0.002),
                size=(0.12 * hx, 0.40 * hy, 0.92 * flat), mat=_turned(R, 0)),
           Geom("ellipsoid", TRIM, pos=_local(p, R, -0.50 * hx, -0.40 * hy, z + 0.002),
                size=(0.07 * hx, 0.43 * hy, 0.95 * flat), mat=_turned(R, 0)),
           Geom("ellipsoid", TRIM, pos=_local(p, R, 0.78 * hx, 0.72 * hy, z), size=(0.20 * hx, 0.30 * hy, 0.85 * flat),
                mat=_turned(R, 62))]
    for g in out:
        g.specular = 0.05
    return out


def props(take) -> list[dict]:
    """The take's things for blend_bake: each sock and shirt, its kind, colour and box."""
    k = _crab_index(take)
    colour = B.SNEAK_OF if k == B.SNEAK else k
    return [{"body": f"item{i}/item", "kind": kind, "colour": colour, "half": list(B.KINDS[kind][0]),
             "seed": 7 * colour + i} for i, (kind, *_rest) in enumerate(B.items(k))]


def clothes(take) -> list[Geom]:
    k = _crab_index(take)
    colour = B.SNEAK_OF if k == B.SNEAK else k
    out = []
    for i, (kind, *_rest) in enumerate(B.items(k)):
        body = take.body(f"item{i}/item")
        if body < 0:
            continue
        p, R = _frame(take, body)
        half = B.KINDS[kind][0]
        out += shirt(p, R, half, SHIRTS[colour]) if kind == "shirt" else sock(p, R, half, SOCKS[colour])
    return out


# ── the room, drawn ───────────────────────────────────────────────────────────

W, D = B.ROOM
H = 2.5


def _walls() -> list[Geom]:
    t = 0.03
    door_y0, door_y1 = B.DOOR[1] - B.DOOR[2], B.DOOR[1] + B.DOOR[2]
    door_h = 2.05
    out = [
        Geom("box", WALL, pos=(W / 2, -t, H / 2), size=(W / 2 + t, t, H / 2), cull=(1, -t)),
        Geom("box", ACCENT, pos=(W / 2, D + t, H / 2), size=(W / 2 + t, t, H / 2), cull=(1, D + t)),
        Geom("box", WALL, pos=(-t, D / 2, H / 2), size=(t, D / 2, H / 2), cull=(0, -t)),
        # the door wall, round the opening
        Geom("box", WALL, pos=(W + t, (door_y1 + D) / 2, H / 2), size=(t, (D - door_y1) / 2, H / 2), cull=(0, W + t)),
        Geom("box", WALL, pos=(W + t, door_y0 / 2, H / 2), size=(t, door_y0 / 2, H / 2), cull=(0, W + t)),
        Geom("box", WALL, pos=(W + t, B.DOOR[1], (door_h + H) / 2), size=(t, B.DOOR[2], (H - door_h) / 2),
             cull=(0, W + t)),
    ]
    # skirting boards
    out += [Geom("box", TRIM, pos=(W / 2, 0.006, 0.04), size=(W / 2, 0.006, 0.04), cull=(1, -t)),
            Geom("box", TRIM, pos=(0.006, D / 2, 0.04), size=(0.006, D / 2, 0.04), cull=(0, -t)),
            Geom("box", TRIM, pos=(W / 2, D - 0.006, 0.04), size=(W / 2, 0.006, 0.04))]
    # floorboards along y, 16 cm wide
    x = 0.16
    while x < W:
        out.append(Geom("box", SEAM, pos=(x, D / 2, 0.0004), size=(0.0015, D / 2, 0.0004), specular=0.1))
        x += 0.16
    return out


def _furniture() -> list[Geom]:
    bx0, bx1, by0, by1 = B.BED
    cx, cy, hx, hy = (bx0 + bx1) / 2, (by0 + by1) / 2, (bx1 - bx0) / 2, (by1 - by0) / 2
    c = B.CLEAR
    out = [
        Geom("box", WALNUT, pos=(cx, cy, c + 0.04), size=(hx, hy, 0.04)),                  # frame
        Geom("box", LINEN, pos=(cx, cy + 0.02, c + 0.14), size=(hx - 0.03, hy - 0.03, 0.06)),  # mattress
        Geom("box", DUVET, pos=(cx, cy - 0.12, B.BED_TOP - 0.01), size=(hx + 0.02, hy - 0.10, 0.035)),
        Geom("box", DUVET, pos=(cx, by0 - 0.005, c + 0.15), size=(hx + 0.02, 0.012, 0.075)),  # the duvet's front fall
        Geom("box", LINEN, pos=(cx - 0.45, by1 - 0.20, B.BED_TOP + 0.05), size=(0.32, 0.13, 0.06)),
        Geom("box", LINEN, pos=(cx + 0.45, by1 - 0.20, B.BED_TOP + 0.05), size=(0.32, 0.13, 0.06)),
        Geom("box", WALNUT, pos=(cx, D - 0.03, 0.55), size=(hx, 0.025, 0.55)),             # headboard
    ]
    for k in range(-3, 4):
        out.append(Geom("box", DUVET_STRIPE, pos=(cx + 0.27 * k, cy - 0.12, B.BED_TOP + 0.026),
                        size=(0.03, hy - 0.10, 0.001)))
    nx0, nx1, ny0, ny1 = B.BENCH
    ncx, ncy, nhx, nhy = (nx0 + nx1) / 2, (ny0 + ny1) / 2, (nx1 - nx0) / 2, (ny1 - ny0) / 2
    out += [
        Geom("box", PINE, pos=(ncx, ncy, c + 0.03), size=(nhx, nhy, 0.03)),
        Geom("box", PINE, pos=(ncx, ny0 + 0.01, c + 0.015), size=(nhx, 0.01, 0.015)),
        Geom("box", CUSHION, pos=(ncx - 0.45, ncy + 0.05, c + 0.09), size=(0.42, 0.40, 0.03)),
        Geom("box", (0.85, 0.30, 0.30, 1), pos=(ncx + 0.55, ncy + 0.25, c + 0.08), size=(0.14, 0.10, 0.02)),
        Geom("box", (0.25, 0.45, 0.70, 1), pos=(ncx + 0.55, ncy + 0.25, c + 0.115), size=(0.13, 0.09, 0.015), yaw=8),
        Geom("box", (0.95, 0.90, 0.60, 1), pos=(ncx + 0.56, ncy + 0.25, c + 0.14), size=(0.11, 0.08, 0.01), yaw=-5),
    ]
    # the window over the bench, and the rug in the middle of the floor
    wx, wz = ncx, 1.45
    out += [Geom("box", SKY, pos=(wx, D - 0.005, wz), size=(0.70, 0.004, 0.55), emission=0.7, specular=0.0),
            Geom("box", TRIM, pos=(wx, D - 0.012, wz), size=(0.76, 0.01, 0.61)),
            Geom("box", TRIM, pos=(wx, D - 0.02, wz), size=(0.02, 0.012, 0.55)),
            Geom("box", TRIM, pos=(wx, D - 0.02, wz), size=(0.70, 0.012, 0.02)),
            Geom("box", TRIM, pos=(wx, D - 0.05, wz - 0.62), size=(0.80, 0.05, 0.015))]
    out += [Geom("cylinder", RUG, pos=(W / 2, 1.15, 0.0009), size=(1.05, 0.0009, 0), specular=0.0),
            Geom("cylinder", RUG_RING, pos=(W / 2, 1.15, 0.0012), size=(0.85, 0.0009, 0), specular=0.0),
            Geom("cylinder", RUG, pos=(W / 2, 1.15, 0.0015), size=(0.78, 0.0009, 0), specular=0.0)]
    # pictures on the side wall
    out += [Geom("box", TRIM, pos=(0.012, 1.0, 1.55), size=(0.008, 0.30, 0.22)),
            Geom("box", (0.40, 0.65, 0.80, 1), pos=(0.02, 1.0, 1.55), size=(0.004, 0.25, 0.17), emission=0.1),
            Geom("box", TRIM, pos=(0.012, 1.85, 1.40), size=(0.008, 0.18, 0.24)),
            Geom("box", (0.95, 0.65, 0.40, 1), pos=(0.02, 1.85, 1.40), size=(0.004, 0.14, 0.20), emission=0.1)]
    return out


ROOM = _walls() + _furniture()

#: The door: hinged at the front end of its opening, it swings into the hall.
DOOR_FROM = None  # take time the door starts to open, set per shot


def door(opens_at: float | None, seconds: float = 1.6):
    y0 = B.DOOR[1] - B.DOOR[2]
    width, h = 2 * B.DOOR[2], 2.05

    def dress(t: float) -> list[Geom]:
        a = 0.0 if opens_at is None else 80.0 * ramp(t, opens_at, opens_at + seconds)
        r = math.radians(a)
        cx, cy = W + 0.02 + math.sin(r) * width / 2, y0 + math.cos(r) * width / 2
        out = [Geom("box", TRIM, pos=(cx, cy, h / 2), size=(0.02, width / 2, h / 2), yaw=-a),
               Geom("sphere", (0.85, 0.70, 0.35, 1), pos=(cx - 0.03 * math.cos(r) + math.sin(r) * 0.33,
                                                         cy + math.cos(r) * 0.33 + 0.03 * math.sin(r), 1.0),
                    size=(0.025, 0, 0), specular=0.9)]
        # the hall beyond: a bright warm floor and wall
        out += [Geom("box", (0.98, 0.93, 0.80, 1), pos=(W + 0.9, B.DOOR[1], 0.001), size=(0.9, 1.2, 0.001),
                     emission=0.5 * a / 80.0),
                Geom("box", (0.98, 0.92, 0.82, 1), pos=(W + 1.8, B.DOOR[1], H / 2), size=(0.02, 1.2, H / 2),
                     emission=0.6 * a / 80.0)]
        return out
    return dress


def room(*extra):
    def dress(t: float) -> list[Geom]:
        out = list(ROOM)
        for e in extra:
            out += e(t) if callable(e) else e
        return out
    return dress


# ── lights ────────────────────────────────────────────────────────────────────


def lights(door_at: float | None = None) -> list[Spot]:
    """Daylight through the window, a soft ceiling lamp, a fill from the front; the
    hall's light comes in when the door opens."""
    wx = (B.BENCH[0] + B.BENCH[1]) / 2
    out = [Spot(pos=(wx, D + 1.2, 2.3), aim=(W / 2 - 0.4, 1.0, 0.0), color=(0.95, 0.88, 0.72), cutoff=48, exponent=2),
           Spot(pos=(W / 2, D / 2, 2.45), aim=(W / 2, D / 2 - 0.2, 0.0), color=(0.42, 0.40, 0.36), cutoff=70,
                exponent=1, shadow=False),
           Spot(pos=(W / 2, -1.5, 1.6), aim=(W / 2, 2.0, 0.1), color=(0.30, 0.31, 0.34), cutoff=45, exponent=1,
                shadow=False)]
    if door_at is not None:
        out.append(Spot(pos=(W + 1.6, B.DOOR[1], 1.7), aim=(W - 1.2, B.DOOR[1] + 0.3, 0.0),
                        color=(1.0, 0.85, 0.60), cutoff=35, exponent=3, on_at=door_at))
    return out


LIT = lights()

# ── eyes ──────────────────────────────────────────────────────────────────────


def faces(*beats: tuple[float, str], per_crab: dict[int, list[tuple[float, str]]] | None = None):
    """`(t_out from, face)` beats for everyone, optionally overridden per crab."""
    def at(t: float, k: int) -> str:
        seq = (per_crab or {}).get(k, beats)
        face = seq[0][1]
        for t0, f in seq:
            if t >= t0:
                face = f
        return face
    return at


# ── the shots ─────────────────────────────────────────────────────────────────


def shot(name: str, time: TimeMap, camera: CameraPath, *, hero: int = 0, coda: bool = False, eyes=None,
         door_at=None, fovy=45.0, **kw) -> Shot:
    """A shot of the whole crew. The camera's robot is crab `hero`; in the coda the
    main take is the sneak (crab 3 again) and the other five sit parked at their ends."""
    crabs = range(len(B.LANES))
    if coda:
        ids = [B.SNEAK_OF] + [k for k in crabs if k != B.SNEAK_OF]
        main = f"crab{B.SNEAK}"
        kw.setdefault("crew_time", lambda j, t: 1e3)  # past the end: parked
    else:
        ids = [hero] + [k for k in crabs if k != hero]
        main = f"crab{hero}"
    crew = tuple(f"crab{k}" for k in ids[1:])
    face = (lambda t, i: eyes(t, ids[i])) if eyes is not None else None
    out = Shot(name, main, time, camera, dressing=[room(door(door_at))], spots=lights(door_at),
               recolor=bedroom_look, group="crew", crew=crew, eyes=face, skin=clothes, look=ROOM_LOOK, fovy=fovy,
               fog=(6.0, 16.0), **kw)
    out.door_at = door_at  # for blend_bake.py
    return out


def pov(t: float, eye, at) -> Key:
    """A camera key from where the camera stands and what it looks at."""
    dx, dy, dz = (a - e for a, e in zip(at, eye, strict=True))
    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
    return Key(t, dist, math.degrees(math.atan2(dy, dx)), math.degrees(math.asin(dz / dist)), lookat=tuple(at))


def _last_in() -> tuple[int, float]:
    """The crab whose thing goes fully under last, and when (take s): the beat the
    countdown hits zero on."""
    from stage import TAKE_FPS, Take

    best = (0, 0.0)
    for k in range(len(B.LANES)):
        take = Take(f"crab{k}", group="crew")
        for i, (kind, *_rest) in enumerate(B.items(k)):
            body = take.body(f"item{i}/item")
            last_out = 0.0
            for f in range(take.frames):
                take.pose(f / TAKE_FPS)
                if take.data.xpos[body][1] - B.KINDS[kind][0][1] < B.BED[2]:
                    last_out = f / TAKE_FPS
            if last_out > best[1]:
                best = (k, last_out)
    return best


E = B.END
LAST_K, LAST_T = _last_in()
LAST_X = B.LANES[LAST_K]
SNEAK_END = B.end(B.SNEAK)
# the crabs that meet face to face, and when (take s)
MEET_AT = next(kf[0] for kf in B.PLAN[2] if abs(kf[3]) < 1e-6)

#: Eyes: everyone panics at the text, focuses on the job; the two who meet are
#: startled, then pleased; under the bed afterwards, guilty; the title, happy.
WORK = faces((0.0, "focus"))

SHOTS: list[Shot] = [
    # The mess; the crabs' eyes in the dark under the bed. The countdown starts.
    shot("wide", TimeMap([(2.8, 0.0, 0.0)]),
         CameraPath([Key(0.0, 2.7, 74, -27, lookat=(2.4, 1.95, 0.2)),
                     Key(2.8, 2.45, 77, -24, lookat=(2.4, 2.1, 0.18))]),
         eyes=faces((0.0, "open"), (1.2, "panic")), fovy=62),
    # From the floor: the first two burst out at the lens.
    shot("popout", TimeMap([(2.4, 0.9, 3.3)]),
         CameraPath([Key(0.0, 1.30, 90, -3, lookat=(2.4, 2.45, 0.09)),
                     Key(2.4, 1.10, 90, -3, lookat=(2.4, 2.30, 0.09))], shake=0.3),
         eyes=faces((0.0, "panic"), (1.4, "focus")), fovy=52),
    # Face to face, a polite beat, and off each its own way.
    shot("near_miss", TimeMap([(2.6, 3.3, 7.8)]),
         CameraPath([Key(0.0, 0.95, 90, -4, lookat=(2.4, 2.0, 0.08)),
                     Key(2.6, 0.85, 90, -4, lookat=(2.4, 2.0, 0.08))], shake=0.25),
         eyes=faces((0.0, "focus"), per_crab={
             2: [(0.0, "focus"), (0.45, "open"), (1.1, "happy"), (2.0, "focus")],
             3: [(0.0, "focus"), (0.5, "open"), (1.15, "happy"), (2.0, "focus")]}), fovy=50),
    # From above: the single file along the walls, fast.
    shot("convoy", TimeMap([(3.8, 7.8, B.SWEEP_AT)]),
         CameraPath([Key(0.0, 3.9, 90, -88, lookat=(2.4, 1.55, 0.0)),
                     Key(3.8, 3.7, 90, -88, lookat=(2.4, 1.60, 0.0))]),
         eyes=WORK, fovy=50),
    # Everyone turns at once and sweeps up the room in a line.
    shot("sweep", TimeMap([(3.6, B.SWEEP_AT, B.SWEEP_AT + 8.0)]),
         CameraPath([Key(0.0, 3.3, 90, -42, lookat=(2.4, 1.4, 0.0)),
                     Key(3.6, 3.0, 90, -38, lookat=(2.4, 1.7, 0.0))]),
         eyes=WORK, fovy=50),
    # Close in: a claw on a shirt.
    shot("macro", TimeMap([(2.0, 33.0, 35.0)]),
         CameraPath([Key(0.0, 0.55, -60, -12, offset=(0.0, 0.25, 0.04)),
                     Key(2.0, 0.50, -70, -10, offset=(0.0, 0.25, 0.04))], shake=0.3),
         hero=3, eyes=WORK, fovy=42),
    # From under the bed: the piles come at the lens.
    shot("bulldozer", TimeMap([(2.6, 36.0, 40.0)]),
         CameraPath([Key(0.0, 1.6, -90, -2, lookat=(2.4, 1.6, 0.08)),
                     Key(2.6, 1.6, -90, -2, lookat=(2.4, 1.9, 0.08))], shake=0.2),
         eyes=WORK, fovy=60),
    # The last thing goes under: the countdown's zero.
    shot("last_in", TimeMap([(1.8, LAST_T - 0.6, LAST_T + 0.3)]),
         CameraPath([Key(0.0, 0.75, 70, -6, lookat=(LAST_X, B.BED[2], 0.05)),
                     Key(1.8, 0.70, 72, -6, lookat=(LAST_X, B.BED[2], 0.05))]),
         hero=LAST_K, eyes=WORK, fovy=45),
    # Silence. The door.
    shot("door", TimeMap([(2.6, E + 1.0, E + 3.6)]),
         CameraPath([pov(0.0, (2.3, 1.7, 0.55), (4.8, 0.75, 1.0)),
                     pov(2.6, (2.4, 1.65, 0.55), (4.8, 0.75, 1.0))]),
         door_at=E + 1.6, fovy=50),
    # Mom's eyes: a clean room. Then, at the bed's edge, a sock.
    shot("mom_pov", TimeMap([(4.0, 0.0, 0.0)]),
         CameraPath([pov(0.0, (4.55, 0.80, 1.60), (3.6, 2.6, 0.45)),
                     pov(1.6, (4.55, 0.80, 1.60), (2.2, 2.4, 0.35)),
                     pov(2.6, (4.55, 0.80, 1.60), (2.6, 2.3, 0.15)),
                     pov(4.0, (4.55, 0.80, 1.60), (B.SOCK_OUT[0], B.SOCK_OUT[1], 0.02))]),
         coda=True, door_at=-100.0, eyes=faces((0.0, "open")), fovy=46),
    # Under the bed: six guilty faces, and one sneaks out and shoves it back.
    shot("guilty", TimeMap([(0.8, 0.0, 0.0), (4.0, 0.0, SNEAK_END)]),
         CameraPath([Key(0.0, 1.5, 90, -3, lookat=(2.7, 2.55, 0.08)),
                     Key(4.8, 1.4, 90, -3, lookat=(2.7, 2.55, 0.08))]),
         coda=True, door_at=-100.0, fovy=55,
         eyes=faces((0.0, "guilty"), per_crab={B.SNEAK_OF: [(0.0, "guilty"), (0.9, "focus"), (4.5, "guilty")]})),
    # ROOM: CLEAN* (the title is laid over in the edit)
    shot("title", TimeMap([(3.4, SNEAK_END + 1.0, SNEAK_END + 1.0)]),
         CameraPath([Key(0.0, 1.4, 90, -3, lookat=(2.7, 2.55, 0.08)),
                     Key(3.4, 1.25, 90, -3, lookat=(2.7, 2.55, 0.08))]),
         coda=True, door_at=-100.0, fovy=55, eyes=faces((0.0, "guilty"), (0.9, "happy"))),
]


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
