"""The fourth film's set, "OPERATION: COOKIE": the bedroom at night, a cookie on the
floor, and a robot vacuum on patrol between it and the crab's home under the bed.

A jumper scene injected by `tools/pose_recorder.py` as `--scene stealth`; world
coordinates are the bedroom's. Physical here:

  * the vacuum: a 34 cm disc, 9 cm tall, a mocap body moved along `vacuum(t)` every
    step (`MOCAP`), so it is kinematic and would shove anything in its way;
  * the cookies: a stack of three 11 cm biscuits, 4 cm and 90 g, free on the floor;
  * a pile of books the crab hides behind, and the furniture's legs.

The crab follows `reference(t)`, a timetable planned against the vacuum's: it waits,
sneaks crouched to cover while the vacuum is on the far lane, freezes as it passes,
slips round behind the cookie, and pushes it home across the vacuum's lane a moment
before the vacuum comes back along it. `tools/film/check_stealth.py` measures that
the two never touch and the cookie ends under the bed.
"""

from __future__ import annotations

import itertools
import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))  # injected as scenes.stealth: find its siblings
from bedroom_scene import BED, BENCH, CLEAR, LEG_R, LEGS  # noqa: F401  (shared set)

VAC_R, VAC_H = 0.17, 0.09
#: The prize: a stack of three cookies, 4 cm tall. A single 1.2 cm cookie slid under
#: the claws (their pads ride 2-5 cm off the floor) and the crab walked over it.
COOKIE_R, COOKIE_H, COOKIE_MASS = 0.055, 0.040, 0.09
COOKIE_AT = (2.90, 0.95)
COVER = ((1.95, 1.30), (0.16, 0.10, 0.05))  # centre, half size: books 10 cm high
HOME = (1.60, 2.75)
CREEP, WALK, PUSH = 0.30, 0.40, 0.18
CROUCH = {"sneak", "hide"}

#: The vacuum's patrol: keyframes (t, x, y, heading). East along the far lane, north up
#: the right side, back west along the near lane, turning on the spot at corners.
SOUTH_Y, NORTH_Y, EAST_X = 0.45, 1.85, 3.90
#: Its corner turn is slow and the north leg late enough that it crosses the crab's
#: path home 0.55 m (centre to centre, 16 cm clear) behind it: searched over delays of
#: 1-4 s, 2026-10-26; at 0 s it ran into the crab.
VAC_KEYS = [(0.0, 0.50, SOUTH_Y, 0.0), (15.45, EAST_X, SOUTH_Y, 0.0), (18.5, EAST_X, SOUTH_Y, math.pi / 2),
            (26.4, EAST_X, NORTH_Y, math.pi / 2), (27.9, EAST_X, NORTH_Y, math.pi),
            (37.0, 0.70, NORTH_Y, math.pi)]


def _sample(keys, t: float):
    if t <= keys[0][0]:
        return keys[0][1:4]
    for a, b in itertools.pairwise(keys):
        if t <= b[0]:
            w = (t - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 1.0
            dh = math.atan2(math.sin(b[3] - a[3]), math.cos(b[3] - a[3]))
            return (a[1] + w * (b[1] - a[1]), a[2] + w * (b[2] - a[2]), a[3] + w * dh)
    return keys[-1][1:4]


def vacuum(t: float):
    return _sample(VAC_KEYS, t)


def _turn(a: float, b: float) -> float:
    d = abs(math.atan2(math.sin(b - a), math.cos(b - a)))
    return 0.3 + d / 1.6 if d > 0.05 else 0.0


def _plan():
    """The crab's timetable: (t, x, y, heading, phase) keyframes."""
    south, north = -math.pi / 2, math.pi / 2
    cx, cy = COVER[0]
    keys = [(0.0, *HOME, south, "home"), (2.0, *HOME, south, "home")]

    def go(to, speed, phase, heading=None):
        t, x, y, h, _ = keys[-1]
        new = math.atan2(to[1] - y, to[0] - x) if heading is None else heading
        dt = _turn(h, new)
        if dt:
            t += dt
            keys.append((t, x, y, new, phase))
        t += math.hypot(to[0] - x, to[1] - y) / speed
        keys.append((t, *to, new, phase))

    def hold(until, phase, heading=None):
        t, x, y, h, _ = keys[-1]
        if heading is not None and _turn(h, heading):
            t += _turn(h, heading)
            keys.append((t, x, y, heading, phase))
        keys.append((max(until, t), x, y, heading if heading is not None else h, phase))

    go((cx, cy + 0.34), CREEP, "sneak")              # out, crouched, behind the books
    hold(9.0, "hide", south)                          # frozen as the vacuum goes by
    side = cx + COVER[1][0] + 0.31                    # clear of the books' east end
    go((side, cy + 0.34), CREEP, "sneak")             # along the books (straight at the cookie
    go((side, 0.62), CREEP, "sneak")                  # ran into them and stuck, 2026-10-26)
    hold(14.2, "hide")                                # waits for the vacuum to clear
    go((COOKIE_AT[0], COOKIE_AT[1] - 0.36), WALK, "walk")  # round behind the cookie
    hold(0.0, "walk", north)                          # face home
    go((COOKIE_AT[0], HOME[1] - 0.12), PUSH, "push", heading=north)  # and push it home
    hold(keys[-1][0] + 0.6, "push")
    hold(keys[-1][0] + 2.0, "home", south)            # turn round, safe
    return keys


PLAN = _plan()
END = PLAN[-1][0]
START = (*HOME, -90.0)


def reference(t: float):
    """(x, y, heading) the crab should be at, and its phase."""
    keys = PLAN
    if t <= keys[0][0]:
        return (*keys[0][1:4], keys[0][4])
    for a, b in itertools.pairwise(keys):
        if t <= b[0]:
            w = (t - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 1.0
            dh = math.atan2(math.sin(b[3] - a[3]), math.cos(b[3] - a[3]))
            return (a[1] + w * (b[1] - a[1]), a[2] + w * (b[2] - a[2]), a[3] + w * dh, b[4])
    return (*keys[-1][1:4], keys[-1][4])


def decorate(spec: Any) -> None:
    for i, (x, y) in enumerate(LEGS):
        spec.worldbody.add_geom(name=f"leg_{i}", type=5, size=[LEG_R, CLEAR / 2, 0.0], pos=[x, y, CLEAR / 2],
                                rgba=[0.35, 0.25, 0.18, 1.0], contype=1, conaffinity=1, condim=3, group=2)
    (x, y), half = COVER
    spec.worldbody.add_geom(name="cover", type=6, size=list(half), pos=[x, y, half[2]],
                            rgba=[0.3, 0.2, 0.15, 1.0], contype=1, conaffinity=1, condim=3, group=2)


def _vacuum_spec():
    import mujoco

    spec = mujoco.MjSpec()
    body = spec.worldbody.add_body(name="vacuum", pos=[0.0, 0.0, 0.0])
    body.add_geom(name="vacuum", type=mujoco.mjtGeom.mjGEOM_CYLINDER, size=[VAC_R, VAC_H / 2, 0.0],
                  pos=[0.0, 0.0, VAC_H / 2 + 0.004], rgba=[0.15, 0.15, 0.17, 1.0], condim=3,
                  contype=1, conaffinity=1, group=2)
    return spec


def _cookie_spec():
    import mujoco

    spec = mujoco.MjSpec()
    body = spec.worldbody.add_body(name="cookie", pos=[0.0, 0.0, 0.0])
    body.add_freejoint()
    body.add_geom(name="cookie", type=mujoco.mjtGeom.mjGEOM_CYLINDER, size=[COOKIE_R, COOKIE_H / 2, 0.0],
                  mass=COOKIE_MASS, rgba=[0.75, 0.52, 0.28, 1.0], condim=3, friction=[0.6, 0.005, 0.0001],
                  contype=1, conaffinity=1, group=2)
    return spec


#: Mocap entities and their pose by script time, for pose_recorder: name -> t -> (x, y, yaw).
MOCAP = {"vacuum": vacuum}


def scene() -> Any:
    from mjlab.entity import EntityCfg
    from scenes.registry import Headlight, Scene

    x, y, h = vacuum(0.0)
    props = {
        "vacuum": EntityCfg(spec_fn=_vacuum_spec, init_state=EntityCfg.InitialStateCfg(
            pos=(x, y, 0.0), rot=(math.cos(h / 2), 0.0, 0.0, math.sin(h / 2)))),
        "cookie": EntityCfg(spec_fn=_cookie_spec, init_state=EntityCfg.InitialStateCfg(
            pos=(COOKIE_AT[0], COOKIE_AT[1], COOKIE_H / 2))),
    }
    return Scene(headlight=Headlight(ambient=(0.3, 0.3, 0.3), diffuse=(0.5, 0.5, 0.5)), decorate=decorate,
                 props=props)
