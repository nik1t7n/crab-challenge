"""Make the bedroom's cloth once, by Blender's cloth simulation: six crumpled T-shirts
and the duvet draped over the bed. Saved to renders/bedroom_blend/bake/cloth.npz for
`shot.py`.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P tools/film/blender/cloth.py

Drawn by hand (a T outline heaped by a few ridges) a shirt read as cardboard. Here
a real-size T-shirt (50 x 40 cm) with a little seeded noise lies on the floor and the
simulation shrinks its cloth by a third (`shrink_min` is the share taken off), so it buckles into folds the way a dropped
shirt does; the result is fitted to the shirt's collision box (the physics' shape,
which is what the crabs push). The duvet is a 2.4 x 1.7 m sheet dropped over the
mattress, so it falls over its edges.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import bmesh
import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
BAKE = ROOT / "renders" / "bedroom_blend" / "bake"
R = json.loads((BAKE / "room.json").read_text())


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def grid(name, sx, sy, nx, ny, keep=None, z=0.0):
    bm = bmesh.new()
    verts = {}
    for i in range(nx + 1):
        for j in range(ny + 1):
            verts[i, j] = bm.verts.new((-sx / 2 + sx * i / nx, -sy / 2 + sy * j / ny, z))
    for i in range(nx):
        for j in range(ny):
            cx, cy = -sx / 2 + sx * (i + 0.5) / nx, -sy / 2 + sy * (j + 0.5) / ny
            if keep is None or keep(cx, cy):
                bm.faces.new((verts[i, j], verts[i + 1, j], verts[i + 1, j + 1], verts[i, j + 1]))
    for v in [v for v in bm.verts if not v.link_faces]:
        bm.verts.remove(v)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def collider(ob, thickness=0.004):
    m = ob.modifiers.new("col", "COLLISION")
    m.settings.thickness_outer = thickness
    return ob


def solid_box(name, center, half):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=tuple(2 * h for h in half), verts=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = center
    return ob


def simulate(ob, frames, **settings):
    scene = bpy.context.scene
    mod = ob.modifiers.new("cloth", "CLOTH")
    s = mod.settings
    for k, v in settings.items():
        setattr(s, k, v)
    mod.collision_settings.use_self_collision = True
    mod.collision_settings.self_distance_min = 0.002
    mod.collision_settings.distance_min = 0.002
    mod.point_cache.frame_start, mod.point_cache.frame_end = 1, frames
    scene.frame_start, scene.frame_end = 1, frames
    for f in range(1, frames + 1):
        scene.frame_set(f)
    deps = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(deps))
    v = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", v)
    v = v.reshape(-1, 3) @ np.array(ob.matrix_world)[:3, :3].T + np.array(ob.matrix_world)[:3, 3]
    f = [list(p.vertices) for p in me.polygons]
    return v.astype(np.float32), f


def tee(cx, cy):
    """A T-shirt outline, 50 cm across the shoulders: the body and two sleeves."""
    body = abs(cx + 0.02) < 0.15 and abs(cy) < 0.115
    sleeves = 0.06 < cx < 0.19 and abs(cy) < 0.25
    collar = (cx - 0.19) ** 2 + cy ** 2 < 0.05 ** 2
    return (body or sleeves) and not collar


def quads(f):
    flat = [i for p in f for i in (p + p[-1:] * (4 - len(p)))]  # pad triangles to quads
    return np.array(flat, np.int32).reshape(-1, 4)


out = {}
for seed in range(6):
    reset()
    rng = np.random.default_rng(100 + seed)
    floor = collider(grid("floor", 2.0, 2.0, 1, 1))
    del floor
    ob = grid("shirt", 0.42, 0.52, 42, 52, keep=tee, z=0.01)
    co = np.zeros(len(ob.data.vertices) * 3)
    ob.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    for _ in range(3):  # a few seeded rucks to start from
        th, k, ph = rng.uniform(0, math.pi), rng.uniform(18, 40), rng.uniform(0, 6.3)
        co[:, 2] += 0.012 * (1 + np.sin(k * (co[:, 0] * math.cos(th) + co[:, 1] * math.sin(th)) + ph))
    ob.data.vertices.foreach_set("co", co.ravel())
    ob.rotation_euler = (0, 0, rng.uniform(-0.3, 0.3))
    v, f = simulate(ob, 70, quality=8, mass=0.15, tension_stiffness=8, compression_stiffness=8,
                    bending_stiffness=0.05, shrink_min=0.35, air_damping=2.0)
    v -= v.mean(0) * np.array([1, 1, 0])
    out[f"shirt{seed}_v"], out[f"shirt{seed}_f"] = v, quads(f)
    print(f"[cloth] shirt {seed}: {len(v)} verts, {np.ptp(v, 0).round(3)} m")

reset()
bx0, bx1, by0, by1 = R["BED"]
c = R["CLEAR"]
bcx, bcy, bhx, bhy = (bx0 + bx1) / 2, (by0 + by1) / 2, (bx1 - bx0) / 2, (by1 - by0) / 2
collider(solid_box("frame", (bcx, bcy, c + 0.045), (bhx, bhy, 0.045)))
collider(solid_box("mattress", (bcx, bcy + 0.02, c + 0.16), (bhx - 0.03, bhy - 0.04, 0.07)))
collider(solid_box("headboard", (bcx, R["ROOM"][1] - 0.035, 0.6), (bhx + 0.02, 0.03, 0.6)))
collider(grid("floor", 8, 8, 1, 1))
# Folded back at the pillows and pinned there, it hangs 6 cm over the front edge, so
# the crabs under the bed stay in view (left free, it slid off the front to the floor).
depth = 2 * bhy - 0.30
duvet = grid("duvet", 2 * bhx + 0.30, depth, 96, 56, z=0.0)
duvet.location = (bcx, by0 - 0.06 + depth / 2, c + 0.25)
pin = duvet.vertex_groups.new(name="pin")
pin.add([v.index for v in duvet.data.vertices if v.co.y > depth / 2 - 0.02], 1.0, "REPLACE")
v, f = simulate(duvet, 40, quality=6, mass=0.4, tension_stiffness=20, bending_stiffness=0.6, air_damping=1.0,
                vertex_group_mass="pin")
out["duvet_v"], out["duvet_f"] = v, quads(f)
print(f"[cloth] duvet: {len(v)} verts, z {v[:, 2].min():.3f}-{v[:, 2].max():.3f}")
np.savez_compressed(BAKE / "cloth.npz", **out)
