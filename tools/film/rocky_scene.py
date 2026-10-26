"""The third film's set, "UNDERCLAW": a training montage in the bedroom at dawn, and a
stair of books to the top.

A jumper scene injected by `tools/pose_recorder.py` as `--scene rocky`. World
coordinates are the bedroom's (`bedroom_scene.py`: x across the room, y from the
front wall, z up), so every take of this film lands in one room. Physical here:

  * the stair: three 4 cm tiers of stacked books joined by ramps (hardcovers laid
    as ramps), up to a 12 cm summit. The heist proved a 3.5 cm ramp rise; each step
    here is 4 cm over 0.30 m (7.6 degrees);
  * the summit's south face, a 12 cm wall the crab first tries to walk up;
  * `ROCKY_PROPS=weight`: a heavy dictionary on the floor to push (0.7 kg; at 1.2 kg the
    crab only crept it along at 1.5 cm/s).

The jumps and the claw raised at the top are takes recorded on a flat floor and set
down on the summit's flat top (`stage.Take` with a height): the same flat rigid
contact, at a different height.
"""

from __future__ import annotations

import math
import os
from typing import Any

#: The stair runs along +x at y = STAIR_Y.
STAIR_Y = 1.15
HALF_W = 0.32
RISE = 0.04
#: (x0, x1, height) of the flat tiers; ramps join each to the next.
TIERS = [(1.40, 1.85, 0.04), (2.15, 2.60, 0.08), (2.90, 3.60, 0.12)]
RAMPS = [(1.10, 1.40, 0.00, 0.04), (1.85, 2.15, 0.04, 0.08), (2.60, 2.90, 0.08, 0.12)]
SUMMIT = TIERS[-1]
SUMMIT_TOP = (3.25, STAIR_Y, SUMMIT[2])

#: Where each take starts: (x, y, yaw degrees).
CLIMB_START = (0.80, STAIR_Y, 0.0)
FAIL_START = (3.25, 0.30, 90.0)
PUSH_START = (0.55, 0.45, 0.0)
SHUFFLE_START = (1.10, 1.85, -90.0)
SQUAT_START = (4.10, 1.55, 200.0)

#: The heavy book: half size, mass, friction.
WEIGHT_HALF = (0.12, 0.09, 0.035)
WEIGHT_MASS = 0.7
WEIGHT_AT = (0.95, 0.45)

BOOK = (0.42, 0.30, 0.22, 1.0)


def _box(spec: Any, name: str, pos, half, pitch: float = 0.0) -> None:
    c, s = math.cos(pitch / 2), math.sin(pitch / 2)
    spec.worldbody.add_geom(name=name, type=6, size=list(half), pos=list(pos), quat=[c, 0.0, s, 0.0],
                            rgba=list(BOOK), contype=1, conaffinity=1, condim=3,
                            friction=[1.0, 0.005, 0.0001], group=2)


def decorate(spec: Any) -> None:
    """The stair, physical (a replay with one environment; never used to train)."""
    for i, (x0, x1, h) in enumerate(TIERS):
        _box(spec, f"tier_{i}", ((x0 + x1) / 2, STAIR_Y, h / 2), ((x1 - x0) / 2, HALF_W, h / 2))
    for i, (x0, x1, z0, z1) in enumerate(RAMPS):
        run, rise = x1 - x0, z1 - z0
        slope = math.atan2(rise, run)
        length = math.hypot(run, rise)
        t = 0.01
        # a slab whose top face runs from z0 at x0 to z1 at x1
        cx = (x0 + x1) / 2 + t * math.sin(slope) / 2
        cz = (z0 + z1) / 2 - t * math.cos(slope) / 2
        _box(spec, f"ramp_{i}", (cx, STAIR_Y, cz), (length / 2, HALF_W, t / 2), pitch=-slope)
        if z0 > 0:  # the tier under the ramp's low end carries it
            _box(spec, f"ramp_{i}_base", ((x0 + x1) / 2, STAIR_Y, z0 / 2 - 0.0005), (run / 2, HALF_W, z0 / 2 - 0.0005))


def _weight_spec() -> Any:
    import mujoco

    spec = mujoco.MjSpec()
    body = spec.worldbody.add_body(name="weight", pos=[0.0, 0.0, 0.0])
    body.add_freejoint()
    body.add_geom(name="weight", type=mujoco.mjtGeom.mjGEOM_BOX, size=list(WEIGHT_HALF), mass=WEIGHT_MASS,
                  rgba=[0.55, 0.12, 0.12, 1.0], condim=3, friction=[0.5, 0.005, 0.0001],
                  contype=1, conaffinity=1, group=2)
    return spec


def scene() -> Any:
    from mjlab.entity import EntityCfg
    from scenes.registry import Headlight, Scene

    props = {}
    if "weight" in os.environ.get("ROCKY_PROPS", ""):
        props["weight"] = EntityCfg(spec_fn=_weight_spec, init_state=EntityCfg.InitialStateCfg(
            pos=(WEIGHT_AT[0], WEIGHT_AT[1], WEIGHT_HALF[2])))
    return Scene(headlight=Headlight(ambient=(0.3, 0.3, 0.3), diffuse=(0.5, 0.5, 0.5)), decorate=decorate,
                 props=props)
