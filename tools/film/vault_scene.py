"""The heist's vault: one long room, an obstacle course down its middle, gold at the end.

A jumper scene (the shape of upstream `scenes/football.py`), injected by
`tools/pose_recorder.py` as `scenes.vault` so the upstream checkout is untouched.
Only what the robot touches is physical here: the ramp and platform it climbs, the
pillars it weaves between, the crate it shoves. Walls, beams, lights and the gold
are drawn by `tools/film/stage.py`, which reads the same numbers from this file, so
the room the policy walked through and the room on screen are one description.

The robot starts at the origin facing +x (`FIXED_START` in the recorder) and the
course runs along +x. Sizes are the robot's: it stands 0.18 m tall and about 0.40 m
across, so a 4 cm platform is a curb to it and a 0.6 m-wide room is an alley.
"""

from __future__ import annotations

import math
from typing import Any

#: The room, picture-only: x from ROOM_X[0] to ROOM_X[1], walls at +-ROOM_HALF_W.
ROOM_X = (-0.9, 6.3)
ROOM_HALF_W = 0.70
WALL_H = 0.55

#: Ramp up, platform, ramp down: (x start, x end, height at end).
PLATFORM_H = 0.035
RAMP_UP = (0.55, 0.90)
PLATFORM = (0.90, 1.40)
RAMP_DOWN = (1.40, 1.75)
COURSE_HALF_W = 0.36

#: Pillars to weave between: (x, y). Set against the recorded path of a run
#: without them (docs/JOURNAL.md), so the policy's own path clears them.
#: Each pillar stands on the far side of one bend of the path the run is steered
#: along (`tools/commands.py::COURSE_PATH` aims +-0.30; the robot, lagging the bends, swings about +-0.10).
PILLARS: list[tuple[float, float]] = [(1.97, -0.25), (2.40, 0.25), (2.86, -0.25)]
PILLAR_R, PILLAR_H = 0.045, 0.32

#: The crate in the way: centre (x, y), half size, mass.
CRATE = (3.30, 0.0)
CRATE_HALF = 0.055
CRATE_MASS = 0.10

#: The laser gate (picture-only beams across x at these stations, BEAM_Z high).
#: The run is fully crouched from x 3.35 until it starts to rise at x 4.30
#: (`tools/commands.py::CROUCH_FROM_X`, `RISE_AT_X`) and reaches about 0.20 m ahead and
#: behind its centre, so the beams sit in [3.55, 4.10]: passable crouched only.
GATE_X = (3.55, 3.75, 3.95)
BEAM_Z = 0.160

#: Where the other takes are set down in the room (x, y, yaw degrees of their origin).
JUMP_AT = (4.95, 0.0, 0.0)
DOOR = (5.55, 0.30)      # side door in the +y wall: x centre, half width
#: The gold ingot lies on the line from the crab to the door: the push take
#: (`gold_scene.py`) starts the crab 0.34 m short of it, facing down the room.
GOLD_AT = (DOOR[0], 0.0)
PUSH_AT = (GOLD_AT[0], GOLD_AT[1] - 0.34, 0.0)


def _box(spec: Any, name: str, pos, half, pitch: float = 0.0, rgba=(0.2, 0.2, 0.22, 1.0)) -> None:
    c, s = math.cos(pitch / 2), math.sin(pitch / 2)
    spec.worldbody.add_geom(
        name=name, type=6, size=list(half), pos=list(pos), quat=[c, 0.0, s, 0.0],
        rgba=list(rgba), contype=1, conaffinity=1, condim=3, friction=[1.0, 0.005, 0.0001],
        group=2,
    )


def decorate(spec: Any) -> None:
    """The physical course: ramps, platform, pillars.

    Upstream asks `decorate` geometry to be visual-only, because in training with
    thousands of environments only the robot at the origin could reach it. These
    takes are replays with one environment at the origin, so the course is
    physical on purpose; the scene is never used to train.
    """
    for name, (x0, x1), up in (("ramp_up", RAMP_UP, True), ("ramp_down", RAMP_DOWN, False)):
        run = x1 - x0
        slope = math.atan2(PLATFORM_H, run)
        length = math.hypot(run, PLATFORM_H)
        # A slab whose top face runs from the floor to the platform: centred so
        # the top edge meets the floor at one end and the platform at the other.
        t = 0.01
        cx = (x0 + x1) / 2 + (t * math.sin(slope) * (1 if up else -1)) / 2
        cz = PLATFORM_H / 2 - t * math.cos(slope) / 2
        _box(spec, name, (cx, 0.0, cz), (length / 2, COURSE_HALF_W, t / 2),
             pitch=-slope if up else slope)
    x0, x1 = PLATFORM
    _box(spec, "platform", ((x0 + x1) / 2, 0.0, PLATFORM_H / 2), ((x1 - x0) / 2, COURSE_HALF_W, PLATFORM_H / 2))
    for i, (x, y) in enumerate(PILLARS):
        spec.worldbody.add_geom(
            name=f"pillar_{i}", type=5, size=[PILLAR_R, PILLAR_H / 2, 0.0], pos=[x, y, PILLAR_H / 2],
            rgba=[0.3, 0.3, 0.33, 1.0], contype=1, conaffinity=1, condim=3, group=2,
        )


def _crate_spec() -> Any:
    import mujoco

    spec = mujoco.MjSpec()
    body = spec.worldbody.add_body(name="crate", pos=[0.0, 0.0, 0.0])
    body.add_freejoint()
    body.add_geom(
        name="crate", type=mujoco.mjtGeom.mjGEOM_BOX, size=[CRATE_HALF] * 3, mass=CRATE_MASS,
        rgba=[0.55, 0.42, 0.28, 1.0], condim=3, friction=[0.6, 0.005, 0.0001],
        contype=1, conaffinity=1, group=2,
    )
    return spec


def _crate() -> Any:
    from mjlab.entity import EntityCfg

    return EntityCfg(spec_fn=_crate_spec,
                     init_state=EntityCfg.InitialStateCfg(pos=(CRATE[0], CRATE[1], CRATE_HALF)))


def scene() -> Any:
    from scenes.registry import Headlight, Scene

    return Scene(headlight=Headlight(ambient=(0.3, 0.3, 0.3), diffuse=(0.5, 0.5, 0.5)),
                 decorate=decorate, props={"crate": _crate()})
