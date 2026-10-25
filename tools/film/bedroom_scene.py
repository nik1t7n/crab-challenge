"""The second film's set: a messy bedroom, a bed and a long bench against the back
wall, and six crabs who live under them.

A jumper scene injected by `tools/pose_recorder.py` as `--scene bedroom`; `CREW=<n>`
picks the crab. Each crab is its own physical take: the furniture's legs are in every
take, and only that crab's things lie on its floor. The six takes cannot feel each
other, so they are never left to meet: the choreography is planned here, as a
time-indexed path per crab (`reference`), and each take tracks its path in time
(`tools/commands.py:tidy`).

The plan, conflict-free by construction:
  * six lanes 0.6 m apart across the room, one per crab, its two things in its lane;
  * out from under the furniture, single file along the side walls and the front
    wall to the foot of its lane, where nothing lies (`plan` picks each crab's start
    so that no two are ever closer than SPACING);
  * everyone turns at once and sweeps up its lane, pushing its things ahead under
    the furniture, then turns round to face the room.
A first plan, where each crab went for its things on its own and yielded to the
ones recorded before it, jammed and still crossed (docs/JOURNAL.md, 2026-10-25).

Real scale: the crab is 0.40 m across and 0.18 m tall; the furniture stands 0.30 m
off the floor, so a crab walks under it at full height.
World: x across the room, y from the front wall (0) to the back wall, z up.
"""

from __future__ import annotations

import itertools
import math
import os
from typing import Any

ROOM = (4.8, 3.6)
WALL_H = 1.2
LANES = tuple(round(0.75 + 0.66 * k, 2) for k in range(6))

#: Furniture against the back wall, both 0.30 m off the floor: a bed (left) and a
#: long low bench (right). Footprints (x0, x1, y0, y1).
BED = (0.20, 2.40, 2.20, 3.55)
BENCH = (2.40, 4.60, 2.20, 3.55)
CLEAR = 0.30
BED_TOP, BENCH_TOP = 0.55, 0.45
LEG_R = 0.035
#: The legs: corners, and the shared back one. A front middle leg would stand on a
#: lane boundary a few cm from two sweeping crabs, so the frames span without one.
LEGS = [(0.25, 2.25), (0.25, 3.50), (4.55, 2.25), (4.55, 3.50), (2.40, 3.50)]
DOOR = (4.8, 0.75, 0.40)  # in the x = 4.8 wall: (x, y centre, half width)

#: Things on the floor: (half size x, y, z), mass kg, friction.
KINDS = {
    "sock": ((0.050, 0.040, 0.025), 0.045, 0.8),
    "shirt": ((0.115, 0.090, 0.030), 0.150, 0.7),
}
#: Per lane: two things, (kind, x offset from the lane, y, yaw), one behind the other
#: and nearly square to the lane. The crab pushes the near one into the far one and
#: then both as a train, face on face, so the wider one goes first: a sock pushing a
#: shirt meets it off-centre and turns it away (two of three such trains lost the
#: shirt, every shirt-first train held, 2026-10-25). Side by side or turned, the two
#: split apart on the crab's rounded front and slid into the next lane. Offsets stay
#: within OFFSET, so a crab centring its train never leaves its lane by more.
OFFSET = 0.06
#: How far off its lane a crab may go to stay behind its train.
DRIFT = 0.06
#: The crab's pushing face is its two claws, 4 cm apart at the front, and walking,
#: the left one leads by 6 mm on average (measured over three sweeps, 2026-10-25):
#: a front turned 8 degrees, on which a 23 cm shirt pivots and slides off to the
#: crab's right. Sweeping, the crab turns that much to its left, squaring its claws
#: to the lane, and still walks straight up it.
SQUARE = float(os.environ.get("CRAB_SQUARE", "0.14"))
ITEMS = [
    [("shirt", 0.04, 0.95, 0.10), ("sock", 0.04, 1.55, -0.12)],
    [("shirt", -0.05, 1.00, 0.12), ("sock", -0.05, 1.50, -0.08)],
    [("sock", 0.03, 0.90, -0.10), ("sock", 0.03, 1.45, 0.14)],
    [("shirt", -0.04, 1.00, -0.12), ("sock", -0.04, 1.60, 0.10)],
    [("shirt", 0.05, 0.95, 0.08), ("sock", 0.05, 1.45, -0.10)],
    [("shirt", -0.03, 1.05, 0.14), ("sock", -0.03, 1.55, -0.06)],
]

HOME_Y = 2.80        # under the furniture
EXIT_Y = 2.00        # the corridor in front of it, clear of the things
FRONT_Y = 0.32       # the corridor along the front wall
WALL_X = (0.25, ROOM[0] - 0.25)
WALK, SWEEP = 0.40, 0.22
SPACING = 0.60
DEPART = 1.0         # the policy settles first
SWEEP_END = 2.78


#: The two middle crabs come out side by side, turn to face each other, freeze for
#: a beat and turn away: the film's polite near miss (0.66 m centre to centre).
MEET = {2: 0.0, 3: math.pi}
MEET_HOLD = 1.2


def _legs_for(k: int):
    """Waypoints (x, y); (x, y, heading, hold) turns on the spot and waits; (x, y,
    "keep") moves there without turning."""
    x = LANES[k]
    wall = WALL_X[0 if k < 3 else 1]
    meet = [(x, EXIT_Y, MEET[k], MEET_HOLD)] if k in MEET else []
    return [(x, HOME_Y), (x, EXIT_Y), *meet, (wall, EXIT_Y), (wall, FRONT_Y), (x, FRONT_Y)]


def _turn_time(a: float, b: float) -> float:
    turn = abs(math.atan2(math.sin(b - a), math.cos(b - a)))
    return 0.3 + turn / 1.6 if turn > 0.05 else 0.0


def _walk(points, t0: float, speed: float):
    """Keyframes (t, x, y, heading) along `points`, turning on the spot at corners."""
    heading = math.atan2(points[1][1] - points[0][1], points[1][0] - points[0][0])
    t = t0
    out = [(t, *points[0][:2], heading)]
    for a, b in itertools.pairwise(points):
        if len(b) == 3:  # move there without turning (backing out)
            t += math.hypot(b[0] - a[0], b[1] - a[1]) / speed
            out.append((t, *b[:2], heading))
            continue
        if len(b) == 4:  # turn here and hold
            t += _turn_time(heading, b[2])
            heading = b[2]
            out.append((t, *b[:2], heading))
            t += b[3]
            out.append((t, *b[:2], heading))
            continue
        new = math.atan2(b[1] - a[1], b[0] - a[0])
        dt = _turn_time(heading, new)
        if dt:
            t += dt
            out.append((t, *a[:2], new))
        heading = new
        t += math.hypot(b[0] - a[0], b[1] - a[1]) / speed
        out.append((t, *b[:2], heading))
    return out


def _sample(keys, t: float):
    if t <= keys[0][0]:
        return keys[0][1:]
    for a, b in itertools.pairwise(keys):
        if t <= b[0]:
            w = (t - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 1.0
            dh = math.atan2(math.sin(b[3] - a[3]), math.cos(b[3] - a[3]))
            return (a[1] + w * (b[1] - a[1]), a[2] + w * (b[2] - a[2]), a[3] + w * dh)
    return keys[-1][1:]


def plan():
    """Every crab's keyframes. On each side the crab going farthest leaves first and
    each next one waits the least that keeps it SPACING from everyone planned so
    far; then they all sweep together."""
    order = [2, 3, 1, 4, 0, 5]
    walks: dict[int, list] = {}
    for k in order:
        delay = DEPART
        while True:
            keys = _walk(_legs_for(k), delay, WALK)
            t, ok = 0.0, True
            until = max([keys[-1][0]] + [w[-1][0] for w in walks.values()]) + 1.0
            while ok and t <= until:
                me = _sample(keys, t)
                ok = all(math.hypot(me[0] - o[0], me[1] - o[1]) >= SPACING
                         for o in (_sample(w, t) for w in walks.values()))
                t += 0.05
            if ok:
                break
            delay += 0.1
        walks[k] = keys
    sweep_at = max(w[-1][0] for w in walks.values()) + 0.6
    north, south = math.pi / 2, -math.pi / 2
    out = []
    for k, x in enumerate(LANES):
        keys = list(walks[k])
        keys.append((sweep_at, x, FRONT_Y, keys[-1][3]))
        keys.append((sweep_at + 1.4, x, FRONT_Y, north))
        t_in = sweep_at + 1.4 + (SWEEP_END - FRONT_Y) / SWEEP
        keys.append((t_in, x, SWEEP_END, north))
        keys.append((t_in + 0.6, x, SWEEP_END - 0.08, north))  # step back off the pile
        keys.append((t_in + 3.0, x, SWEEP_END - 0.08, south + 1e-3))
        out.append(keys)
    return out


PLAN = plan()
SWEEP_AT = PLAN[0][-5][0]
END = PLAN[0][-1][0]
#: Per crab: (sweep from, sweep to) take seconds, the stretch it pushes its train.
SWEEPS = [(SWEEP_AT + 1.4, END - 3.0)] * len(LANES)

#: The coda's take: crab 3 again, from where it parked, with its shirt where it left
#: it and a sock that slid out at the bed's edge between it and crab 4. It slips out,
#: comes round behind the sock, shoves it back under, backs off and goes home. The
#: sock lies 0.33 m off its lane, so walking out the crab's legs (0.20 m) pass it; it
#: pushes only to the bed's edge, where it is still 0.6 m clear of crab 4. CREW=6.
SNEAK = 6
SNEAK_OF = 3
SOCK_OUT = (LANES[SNEAK_OF] + 0.33, BED[2] - 0.03, 0.4)


def _sneak_plan():
    x = LANES[SNEAK_OF]
    sx, sy = SOCK_OUT[:2]
    north, south = math.pi / 2, -math.pi / 2
    out_y, push_y = 1.80, sy - 0.07
    home = (x, HOME_Y - 0.08)
    keys = _walk([home, (x, out_y), (sx, out_y), (sx, out_y, north, 0.4), (sx, push_y),
                  (sx, out_y, "keep"), (x, out_y), home, (*home, south, 0.6)], DEPART, WALK)
    push = next(i for i, kf in enumerate(keys) if abs(kf[2] - push_y) < 1e-9)
    return keys, (keys[push - 1][0], keys[push][0] + 0.3)


_sneak, _sneak_sweep = _sneak_plan()
PLAN.append(_sneak)
SWEEPS.append(_sneak_sweep)


def reference(k: int, t: float):
    """Where crab k should be at take time t: (x, y, heading)."""
    return _sample(PLAN[k], t)


def phase(k: int, t: float) -> str:
    t0, t1 = SWEEPS[k]
    return "home" if t < PLAN[k][0][0] else "walk" if t < t0 else "sweep" if t < t1 else "park"


def end(k: int) -> float:
    return PLAN[k][-1][0]


def start(k: int) -> tuple[float, float, float]:
    if k == SNEAK:
        return (LANES[SNEAK_OF], HOME_Y - 0.08, -90.0)
    return (LANES[k], HOME_Y, -90.0)


def _parked_shirt():
    """Crab SNEAK_OF's shirt where its recorded take left it: (x, y, z, quat)."""
    from pathlib import Path

    import mujoco
    import numpy as np

    npz = Path(os.environ.get("CREW_DIR", Path(__file__).resolve().parents[2] / "renders" / "crew")) / f"crab{SNEAK_OF}.npz"
    m = mujoco.MjModel.from_binary_path(str(npz.with_suffix(".mjb")))
    j = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, "item0/")
    if j < 0:
        j = next(i for i in range(m.njnt) if m.jnt_type[i] == mujoco.mjtJoint.mjJNT_FREE
                 and (mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, m.jnt_bodyid[i]) or "").startswith("item0"))
    a = int(m.jnt_qposadr[j])
    return np.load(npz)["qpos"][-1][a:a + 7]


def items(k: int):
    """(kind, (x, y), yaw) of crab k's things."""
    if k == SNEAK:
        return [(ITEMS[SNEAK_OF][0][0], None, None), ("sock", SOCK_OUT[:2], SOCK_OUT[2])]
    return [(kind, (LANES[k] + dx, y), yaw) for kind, dx, y, yaw in ITEMS[k]]


def decorate(spec: Any) -> None:
    """The furniture's legs are physical (a crab or a sock can meet one); the rest of
    the room is drawn."""
    for i, (x, y) in enumerate(LEGS):
        spec.worldbody.add_geom(name=f"leg_{i}", type=5, size=[LEG_R, CLEAR / 2, 0.0],
                                pos=[x, y, CLEAR / 2], rgba=[0.35, 0.25, 0.18, 1.0],
                                contype=1, conaffinity=1, condim=3, group=2)


def _item_spec(kind: str):
    import mujoco

    half, mass, friction = KINDS[kind]

    def build():
        spec = mujoco.MjSpec()
        body = spec.worldbody.add_body(name="item", pos=[0.0, 0.0, 0.0])
        body.add_freejoint()
        body.add_geom(name="item", type=mujoco.mjtGeom.mjGEOM_BOX, size=list(half), mass=mass,
                      rgba=[0.8, 0.3, 0.4, 1.0], condim=3, friction=[friction, 0.005, 0.0001],
                      contype=1, conaffinity=1, group=2)
        return spec
    return build


def scene() -> Any:
    from mjlab.entity import EntityCfg
    from scenes.registry import Headlight, Scene

    k = int(os.environ.get("CREW", "0"))
    props = {}
    for i, (kind, at, yaw) in enumerate(items(k)):
        half = KINDS[kind][0]
        if at is None:  # where a recorded take left it
            q = _parked_shirt()
            pos, rot = tuple(q[:3]), tuple(q[3:])
        else:
            pos, rot = (at[0], at[1], half[2]), (math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2))
        props[f"item{i}"] = EntityCfg(spec_fn=_item_spec(kind),
                                      init_state=EntityCfg.InitialStateCfg(pos=pos, rot=rot))
    return Scene(headlight=Headlight(ambient=(0.3, 0.3, 0.3), diffuse=(0.5, 0.5, 0.5)), decorate=decorate,
                 props=props)
