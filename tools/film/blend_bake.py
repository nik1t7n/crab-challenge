"""Bake the bedroom film's shots for Blender: per output frame, where every crab part,
every sock and shirt, every eye and the camera are.

    upstream/jumper/.venv/bin/python tools/film/blend_bake.py               # every shot
    upstream/jumper/.venv/bin/python tools/film/blend_bake.py --only wide

MuJoCo's own renderer draws the heist well (a dark vault, hard spots), but a lit
bedroom in it reads as flat plastic. So the bedroom is drawn in Blender
(`tools/film/blender/shot.py`): the motion is still the recorded physics, posed here
exactly as `stage.render` poses it (the same TimeMap, crew clocks and camera path),
and only the picture changes. Written to renders/bedroom_blend/bake/:

  * meshes.npz: the robot's visual meshes (vertices, faces), once;
  * <shot>.npz + <shot>.json: per frame the pose of each visual robot geom and each
    thing (position, quaternion), the eyes, the camera, the door's angle;
  * room.json: the set's dimensions from bedroom_scene.py.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import mujoco
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bedroom_scene as B
import bedroom_shots as S
from stage import FACES, RENDERS, Take, blink_at, eye_geoms, ramp

OUT = RENDERS / "bedroom_blend" / "bake"
FPS = 30.0
#: The model's colours, sorted into the film's materials (stage.paint_crab's rule).
VISIBLE_GROUP = 2


def _material(rgba) -> str:
    r, g, b, _ = rgba
    if r > 0.6 and g < 0.3 and b < 0.3:
        return "shell"
    if r < 0.1 and g < 0.1 and b < 0.1:
        return "joint"
    if r > 0.75:
        return "frame"
    return "pad"


def _quat(mat9) -> np.ndarray:
    q = np.zeros(4)
    mujoco.mju_mat2Quat(q, np.asarray(mat9, float).ravel())
    return q


def visual_geoms(take: Take) -> list[int]:
    m = take.model
    return [int(g) for g in take.robot_geoms() if m.geom_group[g] == VISIBLE_GROUP
            and m.geom_type[g] == mujoco.mjtGeom.mjGEOM_MESH]


def export_meshes(take: Take) -> None:
    m = take.model
    out = {}
    for g in visual_geoms(take):
        mid = int(m.geom_dataid[g])
        v0, nv = m.mesh_vertadr[mid], m.mesh_vertnum[mid]
        f0, nf = m.mesh_faceadr[mid], m.mesh_facenum[mid]
        out[f"v{mid}"] = m.mesh_vert[v0:v0 + nv].astype(np.float32)
        out[f"f{mid}"] = m.mesh_face[f0:f0 + nf].astype(np.int32)
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT / "meshes.npz", **out)


def _door_angle(shot, t: float) -> float:
    """The door's opening in degrees at take time t, as `bedroom_shots.door` draws it."""
    at = getattr(shot, "door_at", None)
    return 0.0 if at is None else 80.0 * ramp(t, at, at + 1.6)


def bake(shot) -> None:
    takes = [Take(shot.take, shot.place, shot.group)] + [Take(n, shot.place, shot.group) for n in shot.crew]
    n = round(shot.time.duration * FPS)
    objects = []
    for j, take in enumerate(takes):
        m = take.model
        for g in visual_geoms(take):
            objects.append({"crab": j, "kind": "mesh", "mesh": int(m.geom_dataid[g]),
                            "material": _material(m.geom_rgba[g])})
        k = S._crab_index(take)
        colour = B.SNEAK_OF if k == B.SNEAK else k
        for i, (kind, *_rest) in enumerate(B.items(k)):
            objects.append({"crab": j, "kind": kind, "colour": colour, "half": list(B.KINDS[kind][0]),
                            "seed": 7 * colour + i})
        objects.append({"crab": j, "kind": "eye", "side": 1})
        objects.append({"crab": j, "kind": "eye", "side": -1})
    pos = np.zeros((n, len(objects), 3), np.float32)
    quat = np.zeros((n, len(objects), 4), np.float32)
    scale = np.ones((n, len(objects), 3), np.float32)
    cam = np.zeros((n, 6), np.float32)  # eye xyz, lookat xyz
    door = np.zeros(n, np.float32)
    for f in range(n):
        t_out = f / FPS
        t = shot.time(t_out)
        o = 0
        for j, take in enumerate(takes):
            tt = t if j == 0 or shot.crew_time is None else shot.crew_time(j - 1, t)
            take.pose(tt)
            d = take.data
            for g in visual_geoms(take):
                pos[f, o] = d.geom_xpos[g]
                quat[f, o] = _quat(d.geom_xmat[g])
                o += 1
            k = S._crab_index(take)
            for i in range(len(B.items(k))):
                b = take.body(f"item{i}/item")
                pos[f, o] = d.xpos[b]
                quat[f, o] = d.xquat[b]
                o += 1
            face = FACES[shot.eyes(t_out, j)] if shot.eyes is not None else FACES["open"]
            for e in eye_geoms(d, take.root, face, blink_at(t_out, 0.7 * j)):
                pos[f, o] = e.pos
                quat[f, o] = _quat(e.mat)
                scale[f, o] = e.size
                o += 1
        lookat, dist, az, el = shot.camera.at(t_out, takes[0].data.xpos[takes[0].root].copy())
        a, e = math.radians(az), math.radians(el)
        eye = np.asarray(lookat) - dist * np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])
        cam[f] = [*eye, *lookat]
        door[f] = _door_angle(shot, t)
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT / f"{shot.name}.npz", pos=pos, quat=quat, scale=scale, cam=cam, door=door)
    meta = {"name": shot.name, "frames": n, "fps": FPS, "fovy": shot.fovy, "objects": objects,
            "door_light": getattr(shot, "door_at", None) is not None}
    (OUT / f"{shot.name}.json").write_text(json.dumps(meta))


def room() -> None:
    keys = ["ROOM", "BED", "BENCH", "CLEAR", "BED_TOP", "BENCH_TOP", "LEG_R", "LEGS", "DOOR", "LANES"]
    data = {k: getattr(B, k) for k in keys}
    data["WALL_H"] = S.H
    data["SOCKS"], data["SHIRTS"] = S.SOCKS, S.SHIRTS
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "room.json").write_text(json.dumps(data))


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--only", nargs="+")
    args = ap.parse_args()
    room()
    if not (OUT / "meshes.npz").exists():
        export_meshes(Take("crab0", group="crew"))
    for shot in S.SHOTS:
        if args.only and shot.name not in args.only:
            continue
        bake(shot)
        print(f"[bake] {shot.name}  {round(shot.time.duration * FPS)} frames", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
