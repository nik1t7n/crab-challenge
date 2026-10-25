"""The heist's last room: the gold ingot, and the floor to shove it across.

A jumper scene injected by `tools/pose_recorder.py` as `--scene gold` (see
`vault_scene.py` for the mechanism). One physical prop, the ingot, lying flat in
front-left of where the crab starts; the crab turns to face it and the side door
beyond it, and pushes it out. Nothing is attached or animated: the ingot moves only
because the robot's legs and body push it.

Why a push and not a grasp: with jumper.five_foot's arm, a level grasp of a bar
standing on the floor is only reachable where the walking legs and the stowed claw
pass on the way in (`tools/film/grasp_plan.py`, searched on 2026-10-25 over bar
positions and pedestal heights 0-9 cm: every level grasp lay inside the swept
volume). A real pick-up needs a trained reach-and-grasp policy.

Coordinates are the take's: the robot starts at the origin facing +x.
"""

from __future__ import annotations

from typing import Any

#: The ingot: half size (x, y, z) and mass. A 100 x 60 x 36 mm bar, lying flat.
INGOT_HALF = (0.050, 0.030, 0.018)
INGOT_MASS = 0.35
#: Where it lies, relative to the crab's start: ahead of it once it has turned left.
INGOT_AT = (0.0, 0.34)


def _ingot_spec() -> Any:
    import mujoco

    spec = mujoco.MjSpec()
    body = spec.worldbody.add_body(name="gold", pos=[0.0, 0.0, 0.0])
    body.add_freejoint()
    body.add_geom(
        name="gold", type=mujoco.mjtGeom.mjGEOM_BOX, size=list(INGOT_HALF), mass=INGOT_MASS,
        rgba=[1.0, 0.76, 0.18, 1.0], condim=3, friction=[0.5, 0.005, 0.0001],
        contype=1, conaffinity=1, group=2,
    )
    return spec


def scene() -> Any:
    from mjlab.entity import EntityCfg
    from scenes.registry import Headlight, Scene

    ingot = EntityCfg(spec_fn=_ingot_spec,
                      init_state=EntityCfg.InitialStateCfg(pos=(INGOT_AT[0], INGOT_AT[1], INGOT_HALF[2])))
    return Scene(headlight=Headlight(ambient=(0.3, 0.3, 0.3), diffuse=(0.5, 0.5, 0.5)), props={"gold": ingot})
