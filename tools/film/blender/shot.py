"""Draw one baked bedroom shot in Blender.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P tools/film/blender/shot.py -- wide
    ... -- wide --still 40 --preview        # one frame, half size, to look at

Reads renders/bedroom_blend/bake/<shot>.npz/.json (tools/film/blend_bake.py) and
builds the room, the crabs, their things and the camera, then renders PNG frames to
renders/bedroom_blend/<shot>/ and an MP4 next to them. Nothing moves here that the
bake did not record: every pose is the simulation's, keyed frame by frame.

The look: an evening bedroom. Low warm sun through the window, a soft ceiling fill,
real-world materials made procedurally (no image files, so nothing third-party):
oak floorboards with grain and varnish, walnut, painted plaster, cotton jersey,
ribbed knit, a wool rug, glossy white plastic on the robots, bevelled edges
everywhere so they catch the light.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["wide"]
SHOT = args[0]
FILM = args[args.index("--film") + 1] if "--film" in args else "bedroom"
BAKE = ROOT / "renders" / f"{FILM}_blend" / "bake"
STILL = int(args[args.index("--still") + 1]) if "--still" in args else None
PREVIEW = "--preview" in args

R = json.loads((BAKE / "room.json").read_text())
W, D = R["ROOM"]
H = R["WALL_H"]
_CLOTH_FILE = ROOT / "renders" / "bedroom_blend" / "bake" / "cloth.npz"  # shared by every film
CLOTH = np.load(_CLOTH_FILE) if _CLOTH_FILE.exists() else None
DAWN = R.get("film") == "rocky"  # UNDERCLAW is shot at sunrise
NIGHT = R.get("film") == "stealth"  # OPERATION: COOKIE at 2 a.m.


def lin(c):
    """sRGB 0-1 -> linear, for Blender colours."""
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c[:3]) + (1.0,)


# ── scene ─────────────────────────────────────────────────────────────────────

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
meta = json.loads((BAKE / f"{SHOT}.json").read_text())
bake = np.load(BAKE / f"{SHOT}.npz")
N = meta["frames"]
scene.render.fps = 30
scene.frame_start, scene.frame_end = 1, N
scene.render.resolution_x, scene.render.resolution_y = (960, 540) if PREVIEW else (1920, 1080)
for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        scene.render.engine = engine
        break
    except TypeError:
        continue
ee = scene.eevee
ee.taa_render_samples = 24 if PREVIEW else 48
for attr, val in (("use_raytracing", True), ("use_shadows", True), ("shadow_ray_count", 2),
                  ("shadow_step_count", 8), ("use_gtao", True), ("fast_gi_method", "GLOBAL_ILLUMINATION")):
    if hasattr(ee, attr):
        setattr(ee, attr, val)
if hasattr(ee, "ray_tracing_options"):
    ee.ray_tracing_options.resolution_scale = "2" if PREVIEW else "1"
scene.render.use_motion_blur = not PREVIEW
scene.view_settings.view_transform = "AgX"
try:
    scene.view_settings.look = "AgX - Medium High Contrast"
except TypeError:
    pass
scene.view_settings.exposure = 0.0
world = bpy.data.worlds.new("world")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = lin((0.55, 0.62, 0.75))
world.node_tree.nodes["Background"].inputs[1].default_value = 0.25


# ── materials ─────────────────────────────────────────────────────────────────


def _nodes(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    return m, nt, bsdf


def _set(bsdf, **kw):
    names = {"base": "Base Color", "rough": "Roughness", "metal": "Metallic", "sheen": "Sheen Weight",
             "sheen_rough": "Sheen Roughness", "coat": "Coat Weight", "coat_rough": "Coat Roughness",
             "emit": "Emission Color", "emit_strength": "Emission Strength", "spec": "Specular IOR Level",
             "sss": "Subsurface Weight", "transmission": "Transmission Weight", "alpha": "Alpha"}
    for k, v in kw.items():
        bsdf.inputs[names[k]].default_value = v


def _coord(nt, scale=(1, 1, 1), rot=(0, 0, 0), kind="Object"):
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = scale
    mp.inputs["Rotation"].default_value = rot
    nt.links.new(tc.outputs[kind], mp.inputs["Vector"])
    return mp.outputs["Vector"]


def _bump(nt, bsdf, height, strength, distance=0.002):
    b = nt.nodes.new("ShaderNodeBump")
    b.inputs["Strength"].default_value = strength
    b.inputs["Distance"].default_value = distance
    nt.links.new(height, b.inputs["Height"])
    nt.links.new(b.outputs["Normal"], bsdf.inputs["Normal"])


def _ramp(nt, fac, stops):
    r = nt.nodes.new("ShaderNodeValToRGB")
    els = r.color_ramp.elements
    els[0].position, els[0].color = stops[0][0], lin(stops[0][1])
    els[1].position, els[1].color = stops[-1][0], lin(stops[-1][1])
    for p, c in stops[1:-1]:
        e = els.new(p)
        e.color = lin(c)
    nt.links.new(fac, r.inputs["Fac"])
    return r.outputs["Color"]


def wood(name, light, dark, planks=True, along="y"):
    """Floorboards (planks along y, 16 cm wide, 1.2 m long, each its own tone) or a
    plain board, grain running `along` its length: fine streaks (noise squeezed
    across the grain), slow growth rings, a thin varnish coat."""
    m, nt, bsdf = _nodes(name)
    stretch = {"x": (1.5, 260.0, 260.0), "y": (260.0, 1.5, 260.0), "z": (260.0, 260.0, 1.5)}[along]
    streak = nt.nodes.new("ShaderNodeTexNoise")
    streak.inputs["Scale"].default_value = 1.0
    streak.inputs["Detail"].default_value = 10.0
    streak.inputs["Roughness"].default_value = 0.6
    nt.links.new(_coord(nt, scale=stretch), streak.inputs["Vector"])
    rings = nt.nodes.new("ShaderNodeTexWave")
    rings.wave_type, rings.bands_direction = "BANDS", {"x": "Y", "y": "X", "z": "X"}[along]
    rings.inputs["Scale"].default_value = 9.0
    rings.inputs["Distortion"].default_value = 3.0
    rings.inputs["Detail"].default_value = 2.0
    nt.links.new(_coord(nt, scale=tuple(0.2 + 0.8 * (v > 10) for v in stretch)), rings.inputs["Vector"])
    mixf = nt.nodes.new("ShaderNodeMix")
    mixf.data_type = "FLOAT"
    mixf.inputs["Factor"].default_value = 0.55
    nt.links.new(streak.outputs["Fac"], mixf.inputs[2])
    nt.links.new(rings.outputs["Fac"], mixf.inputs[3])
    fac = mixf.outputs[0]
    grain = _ramp(nt, fac, [(0.25, dark), (0.62, light), (1.0, light)])
    if planks:
        v = _coord(nt, rot=(0, 0, math.pi / 2))  # bricks laid along world y
        brick = nt.nodes.new("ShaderNodeTexBrick")
        brick.offset, brick.offset_frequency = 0.37, 1
        brick.inputs["Scale"].default_value = 1.0
        brick.inputs["Brick Width"].default_value = 1.2
        brick.inputs["Row Height"].default_value = 0.16
        brick.inputs["Mortar Size"].default_value = 0.0012
        brick.inputs["Mortar Smooth"].default_value = 0.6
        brick.inputs["Color1"].default_value = (1.0, 1.0, 1.0, 1)
        brick.inputs["Color2"].default_value = (0.80, 0.74, 0.68, 1)
        brick.inputs["Mortar"].default_value = (0.15, 0.10, 0.07, 1)
        nt.links.new(v, brick.inputs["Vector"])
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        nt.links.new(grain, mix.inputs[6])
        nt.links.new(brick.outputs["Color"], mix.inputs[7])
        nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
        inv = nt.nodes.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        nt.links.new(brick.outputs["Fac"], inv.inputs[1])
        add = nt.nodes.new("ShaderNodeMath")
        add.operation = "MULTIPLY_ADD"
        nt.links.new(fac, add.inputs[0])
        add.inputs[1].default_value = 0.01
        nt.links.new(inv.outputs[0], add.inputs[2])
        _bump(nt, bsdf, add.outputs[0], 0.3)
    else:
        nt.links.new(grain, bsdf.inputs["Base Color"])
        _bump(nt, bsdf, fac, 0.05)
    _set(bsdf, rough=0.42, coat=0.3, coat_rough=0.15)
    return m


def paint(name, colour, rough=0.88):
    m, nt, bsdf = _nodes(name)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 180.0
    noise.inputs["Detail"].default_value = 6.0
    nt.links.new(_coord(nt), noise.inputs["Vector"])
    base = tuple(c * 0.96 for c in colour[:3])
    col = _ramp(nt, noise.outputs["Fac"], [(0.3, base), (0.7, colour[:3])])
    nt.links.new(col, bsdf.inputs["Base Color"])
    _bump(nt, bsdf, noise.outputs["Fac"], 0.04)
    _set(bsdf, rough=rough)
    return m


def fabric(name, colour, weave=900.0, sheen=0.6, rough=0.92, rib=False, quilt=False):
    """Cotton jersey (a fine cross weave) or ribbed knit (`rib`: stripes along the
    object's x, the length of a sock); fuzz from sheen."""
    m, nt, bsdf = _nodes(name)
    v = _coord(nt)
    if rib:
        w = nt.nodes.new("ShaderNodeTexWave")
        w.wave_type, w.bands_direction = "BANDS", "Y"
        w.inputs["Scale"].default_value = 140.0
        w.inputs["Distortion"].default_value = 0.5
        nt.links.new(v, w.inputs["Vector"])
        height = w.outputs["Fac"]
        col = _ramp(nt, height, [(0.0, tuple(c * 0.72 for c in colour[:3])), (0.6, colour[:3])])
    else:
        a = nt.nodes.new("ShaderNodeTexWave")
        a.bands_direction = "X"
        b = nt.nodes.new("ShaderNodeTexWave")
        b.bands_direction = "Y"
        for t in (a, b):
            t.inputs["Scale"].default_value = weave
            nt.links.new(v, t.inputs["Vector"])
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        nt.links.new(a.outputs["Fac"], mul.inputs[0])
        nt.links.new(b.outputs["Fac"], mul.inputs[1])
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 60.0
        nt.links.new(v, noise.inputs["Vector"])
        height = mul.outputs[0]
        col = _ramp(nt, noise.outputs["Fac"], [(0.35, tuple(c * 0.85 for c in colour[:3])), (0.65, colour[:3])])
    nt.links.new(col, bsdf.inputs["Base Color"])
    if quilt:  # stitched squares, 25 cm
        q = nt.nodes.new("ShaderNodeTexWave")
        q.bands_direction = "DIAGONAL"
        q.inputs["Scale"].default_value = 2.0
        r = nt.nodes.new("ShaderNodeTexWave")
        r.bands_direction = "DIAGONAL"
        r.inputs["Scale"].default_value = 2.0
        nt.links.new(_coord(nt), q.inputs["Vector"])
        nt.links.new(_coord(nt, scale=(-1, 1, 1)), r.inputs["Vector"])
        mn = nt.nodes.new("ShaderNodeMath")
        mn.operation = "MINIMUM"
        nt.links.new(q.outputs["Fac"], mn.inputs[0])
        nt.links.new(r.outputs["Fac"], mn.inputs[1])
        ad = nt.nodes.new("ShaderNodeMath")
        ad.operation = "MULTIPLY_ADD"
        nt.links.new(height, ad.inputs[0])
        ad.inputs[1].default_value = 0.08
        nt.links.new(mn.outputs[0], ad.inputs[2])
        height = ad.outputs[0]
        _bump(nt, bsdf, height, 0.5, 0.01)
    else:
        _bump(nt, bsdf, height, 0.25, 0.001)
    _set(bsdf, rough=rough, sheen=sheen, sheen_rough=0.4, spec=0.3)
    return m


def wool(name, colour, ring):
    m, nt, bsdf = _nodes(name)
    v = _coord(nt)
    grad = nt.nodes.new("ShaderNodeTexGradient")
    grad.gradient_type = "SPHERICAL"
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / 1.05, 1 / 1.05, 1.0)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], grad.inputs["Vector"])
    col = _ramp(nt, grad.outputs["Fac"], [(0.0, colour), (0.17, colour), (0.19, ring), (0.26, ring),
                                          (0.28, colour), (1.0, colour)])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 420.0
    noise.inputs["Detail"].default_value = 8.0
    nt.links.new(v, noise.inputs["Vector"])
    nt.links.new(col, bsdf.inputs["Base Color"])
    _bump(nt, bsdf, noise.outputs["Fac"], 0.6, 0.003)
    _set(bsdf, rough=1.0, sheen=0.3, sheen_rough=0.5, spec=0.15)
    return m


def plastic(name, colour, rough=0.3, coat=0.4):
    m, _nt, bsdf = _nodes(name)
    _set(bsdf, base=lin(colour), rough=rough, coat=coat, coat_rough=0.08, sss=0.05)
    return m


def emission(name, colour, strength):
    m, _nt, bsdf = _nodes(name)
    _set(bsdf, base=lin(colour), emit=lin(colour), emit_strength=strength)
    return m


OAK = wood("oak", (0.72, 0.58, 0.43), (0.63, 0.49, 0.35))
WALNUT = wood("walnut", (0.40, 0.27, 0.18), (0.22, 0.14, 0.09), planks=False, along="x")
PINE = wood("pine", (0.84, 0.70, 0.52), (0.68, 0.52, 0.36), planks=False, along="x")
WALL = paint("wall", lin((0.70, 0.76, 0.70))[:3])
ACCENT = paint("accent", lin((0.84, 0.78, 0.70))[:3])
TRIM = paint("trim", lin((0.95, 0.94, 0.90))[:3], rough=0.45)
DUVET = fabric("duvet", lin((0.36, 0.45, 0.58)), weave=700.0, sheen=0.5, quilt=True)
LINEN = fabric("linen", lin((0.95, 0.94, 0.91)), weave=650.0, sheen=0.4)
CUSHION = fabric("cushion", lin((0.90, 0.68, 0.24)), weave=500.0)
RUG = wool("rug", (0.66, 0.34, 0.28), (0.93, 0.85, 0.72))
SKY = emission("sky", (0.95, 0.78, 0.58), 3.0)
HALL = emission("hall", (1.0, 0.88, 0.70), 0.0)
BRASS = plastic("brass", (0.85, 0.66, 0.32), rough=0.25, coat=0.0)
BRASS.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 1.0
ROBOT = {"shell": plastic("shell", (0.93, 0.94, 0.95), rough=0.22, coat=0.6),
         "frame": plastic("frame", (0.78, 0.79, 0.80), rough=0.35, coat=0.2),
         "joint": plastic("joint", (0.05, 0.05, 0.06), rough=0.42, coat=0.2),
         "pad": plastic("pad", (0.30, 0.31, 0.33), rough=0.8, coat=0.0)}
EYE = emission("eye", (0.45, 0.88, 1.0), 9.0)
SOCK = [fabric(f"sock{i}", lin(c), rib=True, sheen=0.8) for i, c in enumerate(R["SOCKS"])]
SHIRT = [fabric(f"shirt{i}", lin(c), sheen=0.55) for i, c in enumerate(R["SHIRTS"])]
CUFF = fabric("cuff", lin((0.95, 0.94, 0.92)), rib=True, sheen=0.8)


# ── geometry ──────────────────────────────────────────────────────────────────

COLL = bpy.data.collections.new("set")
scene.collection.children.link(COLL)


def _obj(name, mesh, mat=None, smooth=False):
    ob = bpy.data.objects.new(name, mesh)
    COLL.objects.link(ob)
    if mat is not None:
        mesh.materials.append(mat)
    if smooth:
        mesh.polygons.foreach_set("use_smooth", np.ones(len(mesh.polygons), bool))
    return ob


def _mesh(name, v, f):
    me = bpy.data.meshes.new(name)
    tri = f[:, 2] == f[:, 3]
    faces = [list(q[:3]) if t_ else list(q) for q, t_ in zip(f.tolist(), tri, strict=True)]
    me.from_pydata(v.tolist(), [], faces)
    me.update()
    me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), bool))
    return me


def box(name, center, half, mat, bevel=0.004, rot_z=0.0, segments=3):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(2 * half[0], 2 * half[1], 2 * half[2]), verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    ob = _obj(name, me, mat)
    ob.location = center
    ob.rotation_euler = (0, 0, rot_z)
    if bevel:
        mod = ob.modifiers.new("bevel", "BEVEL")
        mod.width, mod.segments = min(bevel, 0.9 * min(half)), segments
        mod.harden_normals = True
    return ob


def soft(ob, level=2, squash=None):
    sub = ob.modifiers.new("soft", "SUBSURF")
    sub.levels = sub.render_levels = level
    ob.data.polygons.foreach_set("use_smooth", np.ones(len(ob.data.polygons), bool))
    return ob


def bumpy(ob, strength, size, seed=0):
    tex = bpy.data.textures.new(f"{ob.name}_clouds", "CLOUDS")
    tex.noise_scale = size
    tex.noise_depth = 2
    d = ob.modifiers.new("lumps", "DISPLACE")
    d.texture, d.strength, d.mid_level = tex, strength, 0.5
    d.texture_coords = "GLOBAL"
    return ob


def cylinder(name, center, radius, half_h, mat, bevel=0.003):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=radius, radius2=radius, depth=2 * half_h)
    bm.to_mesh(me)
    bm.free()
    ob = _obj(name, me, mat, smooth=True)
    ob.location = center
    if bevel:
        mod = ob.modifiers.new("bevel", "BEVEL")
        mod.width, mod.segments = bevel, 3
        mod.harden_normals = True
    return ob


# The room. Walls the camera stands behind are left out of its view (they still
# cast shadows and block light), as a set does.
cam_eye = bake["cam"][:, :3]


def wall(name, center, half, mat, axis, plane):
    ob = box(name, center, half, mat, bevel=0.0)
    beyond = (cam_eye[:, axis] - plane) * (1.0 if plane > 0 else -1.0) > 0
    if beyond.any():
        ob.visible_camera = False
    return ob


t = 0.06
ext = 1.4  # the floor runs out under the door into the hall
floor = box("floor", (W / 2 + ext / 2, D / 2, -0.01), ((W + ext) / 2, D / 2, 0.01), OAK, bevel=0.0)
dy0, dy1 = R["DOOR"][1] - R["DOOR"][2], R["DOOR"][1] + R["DOOR"][2]
door_h = 2.05
wx0, wx1 = R["BENCH"][0] + 0.35, R["BENCH"][1] - 0.35
wz0, wz1 = 0.95, 2.05
wall("wall_front", (W / 2, -t, H / 2), (W / 2 + 2 * t, t, H / 2), WALL, 1, -t)
wall("wall_left", (-t, D / 2, H / 2), (t, D / 2 + 2 * t, H / 2), WALL, 0, -t)
wall("wall_right_a", (W + t, (dy1 + D) / 2, H / 2), (t, (D - dy1) / 2 + t, H / 2), WALL, 0, W + t)
wall("wall_right_b", (W + t, dy0 / 2, H / 2), (t, dy0 / 2 + t, H / 2), WALL, 0, W + t)
wall("wall_right_c", (W + t, R["DOOR"][1], (door_h + H) / 2), (t, R["DOOR"][2], (H - door_h) / 2), WALL, 0, W + t)
# the back wall, round the window
wall("wall_back_a", (wx0 / 2, D + t, H / 2), (wx0 / 2 + t, t, H / 2), ACCENT, 1, D + t)
wall("wall_back_b", ((wx1 + W) / 2, D + t, H / 2), ((W - wx1) / 2 + t, t, H / 2), ACCENT, 1, D + t)
wall("wall_back_c", ((wx0 + wx1) / 2, D + t, wz0 / 2), ((wx1 - wx0) / 2, t, wz0 / 2), ACCENT, 1, D + t)
wall("wall_back_d", ((wx0 + wx1) / 2, D + t, (wz1 + H) / 2), ((wx1 - wx0) / 2, t, (H - wz1) / 2), ACCENT, 1, D + t)
wall("ceiling", (W / 2, D / 2, H + t), (W / 2 + 2 * t, D / 2 + 2 * t, t), TRIM, 2, H + t)
# skirting
box("skirt_back", (W / 2, D - 0.008, 0.05), (W / 2, 0.008, 0.05), TRIM, bevel=0.003)
box("skirt_left", (0.008, D / 2, 0.05), (0.008, D / 2, 0.05), TRIM, bevel=0.003)
wall("skirt_front", (W / 2, 0.008, 0.05), (W / 2, 0.008, 0.05), TRIM, 1, -t)
# the window: frame, glazing bars, sill, the evening sky behind
wcx, wcz = (wx0 + wx1) / 2, (wz0 + wz1) / 2
for n_, c_, h_ in (("win_top", (wcx, D + 0.02, wz1), ((wx1 - wx0) / 2 + 0.04, 0.03, 0.035)),
                   ("win_bot", (wcx, D + 0.02, wz0), ((wx1 - wx0) / 2 + 0.04, 0.03, 0.035)),
                   ("win_l", (wx0, D + 0.02, wcz), (0.035, 0.03, (wz1 - wz0) / 2)),
                   ("win_r", (wx1, D + 0.02, wcz), (0.035, 0.03, (wz1 - wz0) / 2)),
                   ("win_mid", (wcx, D + 0.03, wcz), (0.018, 0.02, (wz1 - wz0) / 2)),
                   ("win_bar", (wcx, D + 0.03, wcz + 0.15), ((wx1 - wx0) / 2, 0.02, 0.016)),
                   ("sill", (wcx, D - 0.05, wz0 - 0.03), ((wx1 - wx0) / 2 + 0.10, 0.08, 0.02))):
    box(n_, c_, h_, TRIM, bevel=0.006)
sky = box("sky", (wcx, D + 1.5, wcz + 0.3), ((wx1 - wx0) / 2 + 1.5, 0.01, 1.2), SKY, bevel=0.0)
sky.visible_shadow = False

# curtains either side of the window, gathered in folds
CURTAIN = fabric("curtain", lin((0.86, 0.82, 0.74)), weave=500.0, sheen=0.4)
for side, x0 in ((-1, wx0 - 0.30), (1, wx1 + 0.30)):
    z0, z1 = wz0 - 0.25, H - 0.08
    me = bpy.data.meshes.new("curtain")
    nx_, nz_ = 60, 30
    verts = [(x0 - 0.26 + 0.52 * i / nx_, D - 0.07 + 0.03 * math.sin(2 * math.pi * 0.52 * i / nx_ / 0.09)
              * (0.7 + 0.3 * k / nz_), z0 + (z1 - z0) * k / nz_) for k in range(nz_ + 1) for i in range(nx_ + 1)]
    faces = [(k * (nx_ + 1) + i, k * (nx_ + 1) + i + 1, (k + 1) * (nx_ + 1) + i + 1, (k + 1) * (nx_ + 1) + i)
             for k in range(nz_) for i in range(nx_)]
    me.from_pydata(verts, [], faces)
    cur = _obj(f"curtain{side}", me, CURTAIN, smooth=True)
    cur.modifiers.new("thick", "SOLIDIFY").thickness = 0.004
box("rail", (wcx, D - 0.07, H - 0.07), ((wx1 - wx0) / 2 + 0.62, 0.012, 0.012), WALNUT, bevel=0.004)
# a poster over the bed
box("poster_frame", (0.95, D - 0.012, 1.62), (0.36, 0.01, 0.26), WALNUT, bevel=0.004)
POSTER = paint("poster", lin((0.20, 0.32, 0.45))[:3], rough=0.5)
box("poster", (0.95, D - 0.024, 1.62), (0.32, 0.003, 0.22), POSTER, bevel=0.0)
box("poster_moon", (1.08, D - 0.03, 1.70), (0.06, 0.003, 0.06), paint("moon", lin((0.95, 0.85, 0.55))[:3]),
    bevel=0.0).rotation_euler = (0, 0, 0)

# the bed: walnut frame on its physical legs, mattress, a soft duvet, pillows
bx0, bx1, by0, by1 = R["BED"]
c = R["CLEAR"]
bcx, bcy, bhx, bhy = (bx0 + bx1) / 2, (by0 + by1) / 2, (bx1 - bx0) / 2, (by1 - by0) / 2
box("bed_frame", (bcx, bcy, c + 0.045), (bhx, bhy, 0.045), WALNUT, bevel=0.012)
box("headboard", (bcx, D - 0.035, 0.6), (bhx + 0.02, 0.03, 0.6), WALNUT, bevel=0.015)
soft(box("mattress", (bcx, bcy + 0.02, c + 0.16), (bhx - 0.03, bhy - 0.04, 0.07), LINEN, bevel=0.03), 1)
if CLOTH is not None:  # the simulated drape (cloth.py)
    duvet = _obj("duvet", _mesh("duvet", CLOTH["duvet_v"], CLOTH["duvet_f"]), DUVET)
    th = duvet.modifiers.new("thick", "SOLIDIFY")
    th.thickness, th.offset = 0.03, 1
    soft(duvet, 1)
else:
    duvet = box("duvet", (bcx, bcy - 0.10, R["BED_TOP"] - 0.01), (bhx + 0.06, bhy - 0.06, 0.045), DUVET, bevel=0.04)
    soft(duvet, 2)
for side in (-1, 1):
    pil = box(f"pillow{side}", (bcx + 0.47 * side, by1 - 0.24, R["BED_TOP"] + 0.06), (0.33, 0.21, 0.055), LINEN,
              bevel=0.035)
    soft(pil, 2)
    bumpy(pil, 0.015, 0.06)
# the bench: pine top and apron, a cushion, a stack of books
nx0, nx1, ny0, ny1 = R["BENCH"]
ncx, ncy, nhx, nhy = (nx0 + nx1) / 2, (ny0 + ny1) / 2, (nx1 - nx0) / 2, (ny1 - ny0) / 2
box("bench_top", (ncx, ncy, c + 0.03), (nhx, nhy, 0.03), PINE, bevel=0.008)
box("bench_apron", (ncx, ny0 + 0.012, c - 0.02), (nhx - 0.02, 0.012, 0.03), PINE, bevel=0.004)
soft(box("bench_cushion", (ncx - 0.45, ncy + 0.05, c + 0.10), (0.44, 0.42, 0.04), CUSHION, bevel=0.03), 2)
for i, (col, h_, yaw) in enumerate((((0.70, 0.22, 0.22), 0.022, 0.0), ((0.20, 0.38, 0.62), 0.018, 0.14),
                                     ((0.92, 0.86, 0.55), 0.012, -0.08))):
    box(f"book{i}", (ncx + 0.55, ncy + 0.25, c + 0.06 + 0.04 * i + h_), (0.14 - 0.01 * i, 0.10 - 0.01 * i, h_),
        plastic(f"book{i}", col, rough=0.6, coat=0.1), bevel=0.003, rot_z=yaw)
# a lamp on the bench, warm
lx, ly = ncx + 0.75, ncy - 0.05
cylinder("lamp_base", (lx, ly, c + 0.07), 0.07, 0.01, BRASS)
cylinder("lamp_stem", (lx, ly, c + 0.22), 0.008, 0.15, BRASS)
SHADE = emission("shade", (1.0, 0.86, 0.62), 1.2)
cylinder("lamp_shade", (lx, ly, c + 0.42), 0.13, 0.08, SHADE, bevel=0.0)

# the furniture legs: where the physics has them
for i, (x, y) in enumerate(R["LEGS"]):
    cylinder(f"leg{i}", (x, y, c / 2), R["LEG_R"], c / 2, WALNUT)
# the rug
cylinder("rug", (W / 2, 1.15, 0.004), 1.05, 0.004, RUG, bevel=0.003)
# pictures on the left wall
for i, (y, z, hy, hz, col) in enumerate(((1.0, 1.55, 0.30, 0.22, (0.35, 0.55, 0.70)),
                                         (1.85, 1.40, 0.18, 0.24, (0.90, 0.60, 0.38)))):
    box(f"frame{i}", (0.015, y, z), (0.012, hy, hz), WALNUT, bevel=0.004)
    box(f"print{i}", (0.03, y, z), (0.003, hy - 0.03, hz - 0.03), paint(f"print{i}", lin(col)[:3], rough=0.6),
        bevel=0.0)

# the door, hinged at the front end of its opening; the hall beyond
hinge = bpy.data.objects.new("hinge", None)
COLL.objects.link(hinge)
hinge.location = (W + 0.02, dy0, 0.0)
leaf = box("door", (0.0, R["DOOR"][2], door_h / 2), (0.022, R["DOOR"][2] - 0.005, door_h / 2 - 0.005), TRIM,
           bevel=0.006)
leaf.parent = hinge
for z0, z1 in ((0.15, 0.95), (1.10, 1.90)):
    p = box("panel", (-0.024, R["DOOR"][2], (z0 + z1) / 2), (0.004, R["DOOR"][2] - 0.12, (z1 - z0) / 2), TRIM,
            bevel=0.004)
    p.parent = hinge
knob = cylinder("knob", (-0.05, 2 * R["DOOR"][2] - 0.08, 1.0), 0.028, 0.02, BRASS)
knob.rotation_euler = (0, math.pi / 2, 0)
knob.parent = hinge
for n_, c_, h_ in (("jamb_a", (W + 0.01, dy0 - 0.03, door_h / 2), (0.07, 0.03, door_h / 2)),
                   ("jamb_b", (W + 0.01, dy1 + 0.03, door_h / 2), (0.07, 0.03, door_h / 2)),
                   ("lintel", (W + 0.01, R["DOOR"][1], door_h + 0.03), (0.07, R["DOOR"][2] + 0.06, 0.03))):
    box(n_, c_, h_, TRIM, bevel=0.006)
hall_wall = box("hall_wall", (W + 1.6, R["DOOR"][1], H / 2), (0.02, 1.5, H / 2), HALL, bevel=0.0)


# ── books (UNDERCLAW's stair, the heavy dictionary) ──────────────────────────


def paper():
    m, nt, bsdf = _nodes("pages")
    w = nt.nodes.new("ShaderNodeTexWave")
    w.bands_direction = "Z"
    w.inputs["Scale"].default_value = 900.0
    w.inputs["Distortion"].default_value = 0.3
    nt.links.new(_coord(nt), w.inputs["Vector"])
    col = _ramp(nt, w.outputs["Fac"], [(0.0, (0.82, 0.79, 0.70)), (0.6, (0.96, 0.94, 0.88))])
    nt.links.new(col, bsdf.inputs["Base Color"])
    _bump(nt, bsdf, w.outputs["Fac"], 0.2, 0.0005)
    _set(bsdf, rough=0.8)
    return m


PAGES = paper()
_covers: dict = {}


def cover(tone):
    key_ = tuple(round(v, 3) for v in tone[:3])
    if key_ not in _covers:
        m = fabric(f"cover{len(_covers)}", lin(tone), weave=380.0, sheen=0.2, rough=0.55)
        m.node_tree.nodes["Principled BSDF"].inputs["Coat Weight"].default_value = 0.2
        _covers[key_] = m
    return _covers[key_]


def book(name, center, half, tone, link=True, yaw=0.0):
    """A hardcover: boards a little larger than the page block, the pages cream and
    lined on three sides, the spine on -x."""
    hx, hy, hz = half
    boards = box(name, center, half, cover(tone), bevel=min(0.003, hz * 0.4), rot_z=yaw)
    pages = box(f"{name}_pages", (0.004, 0.0, 0.0), (hx - 0.006, hy - 0.004, hz * 0.84), PAGES, bevel=0.0005)
    pages.parent = boards
    if not link:  # a cast object: animated, so out of the static set
        for o_ in (boards, pages):
            COLL.objects.unlink(o_)
        cast_books.append(pages)
    return boards


cast_books: list = []
if DAWN:
    RK = R["rocky"]
    sy, hw = RK["STAIR_Y"], RK["HALF_W"]
    tones = RK["BOOK_TONES"]
    k = 0
    for x0, x1, h in RK["TIERS"]:
        for i in range(round(h / 0.02)):
            # each layer one or two books, a little askew, as stacked by hand
            for part, (ya, yb) in enumerate(((sy - hw, sy + 0.02), (sy + 0.02, sy + hw))
                                            if (k % 3) else ((sy - hw, sy + hw),)):
                jit = 0.012 * math.sin(7.1 * k + part)
                book(f"tier{k}_{part}", ((x0 + x1) / 2 + jit, (ya + yb) / 2, 0.01 + 0.02 * i),
                     ((x1 - x0) / 2, (yb - ya) / 2, 0.0098), tones[(k + part) % len(tones)], yaw=1.2 * jit)
            k += 1
    for j, (x0, x1, z0, z1) in enumerate(RK["RAMPS"]):
        run, rise = x1 - x0, z1 - z0
        slope = math.atan2(rise, run)
        ob = box(f"ramp{j}", ((x0 + x1) / 2 + 0.005 * math.sin(slope), sy, (z0 + z1) / 2 - 0.005 * math.cos(slope)),
                 (math.hypot(run, rise) / 2, hw, 0.005), cover(tones[(j + 3) % len(tones)]), bevel=0.002)
        ob.rotation_euler = (0, -slope, 0)  # +x end up
        if z0 > 0:
            book(f"ramp{j}_base", ((x0 + x1) / 2, sy, z0 / 2), (run / 2, hw, z0 / 2 - 0.0005),
                 tones[(j + 1) % len(tones)])
    # the flag: a cork, a pole, a little yellow pennant
    fx, fy = RK["FLAG_AT"]
    fz = RK["TIERS"][-1][2]
    CORK = fabric("cork", lin((0.72, 0.55, 0.36)), weave=150.0, sheen=0.0, rough=0.9)
    cylinder("cork", (fx, fy, fz + 0.015), 0.018, 0.015, CORK)
    cylinder("pole", (fx, fy, fz + 0.17), 0.0035, 0.155, BRASS, bevel=0.0)
    PENNANT = fabric("pennant", lin((0.98, 0.76, 0.16)), weave=400.0, sheen=0.3)
    pen = box("pennant", (fx, fy - 0.065, fz + 0.28), (0.0015, 0.065, 0.042), PENNANT, bevel=0.0)
    pen.modifiers.new("sub", "SUBSURF").levels = 2
    if meta.get("weight_rest"):
        wx, wy = RK["WEIGHT_AT"]
        book("dictionary", (wx, wy, RK["WEIGHT_HALF"][2]), RK["WEIGHT_HALF"], (0.55, 0.12, 0.12))


if NIGHT:
    (cx_, cy_), (chx, chy, chz) = R["stealth"]["COVER"]
    for i, tone in enumerate(((0.20, 0.30, 0.50), (0.55, 0.18, 0.15), (0.80, 0.66, 0.35))):
        book(f"cover{i}", (cx_ + 0.01 * (i - 1), cy_, (2 * i + 1) * chz / 3), (chx - 0.008 * i, chy, chz / 3 - 0.0008),
             tone, yaw=math.radians(4 * (i - 1)))

VAC_BODY = plastic("vacuum", (0.10, 0.10, 0.11), rough=0.18, coat=0.8)
VAC_BUMPER = plastic("bumper", (0.62, 0.64, 0.68), rough=0.25, coat=0.3)
VAC_BUMPER.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 0.8
VAC_LED = emission("led", (0.25, 0.75, 1.0), 12.0)
COOKIE = None


def cookie_mat():
    """Golden-brown dough with chocolate chips: dark where a coarse noise is high."""
    m, nt, bsdf = _nodes("cookie")
    v = _coord(nt)
    chips = nt.nodes.new("ShaderNodeTexVoronoi")
    chips.inputs["Scale"].default_value = 90.0
    nt.links.new(v, chips.inputs["Vector"])
    crumb = nt.nodes.new("ShaderNodeTexNoise")
    crumb.inputs["Scale"].default_value = 260.0
    crumb.inputs["Detail"].default_value = 8.0
    nt.links.new(v, crumb.inputs["Vector"])
    dough = _ramp(nt, crumb.outputs["Fac"], [(0.35, (0.62, 0.40, 0.20)), (0.65, (0.82, 0.60, 0.32))])
    mask = _ramp(nt, chips.outputs["Distance"], [(0.0, (1, 1, 1)), (0.18, (1, 1, 1)), (0.22, (0, 0, 0)), (1.0, (0, 0, 0))])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(mask, mix.inputs["Factor"])
    nt.links.new(dough, mix.inputs[6])
    mix.inputs[7].default_value = lin((0.16, 0.08, 0.04))
    nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    _bump(nt, bsdf, crumb.outputs["Fac"], 0.6, 0.002)
    _set(bsdf, rough=0.75, sheen=0.2)
    return m


def _child(parent, ob):
    COLL.objects.unlink(ob)
    ob.parent = parent
    cast_books.append(ob)
    return ob


def vacuum_obj(name, half):
    """A robot vacuum: a glossy black disc, a silver bumper round its lower half, a
    lidar puck on top, a glowing ring; its origin on the floor at its centre."""
    r, _, hh = half
    root = bpy.data.objects.new(name, None)
    _child(root, cylinder(f"{name}_bumper", (0, 0, 0.004 + hh * 0.7), r, hh * 0.7, VAC_BUMPER, bevel=0.008))
    _child(root, cylinder(f"{name}_top", (0, 0, 0.004 + 1.55 * hh), r - 0.008, 0.45 * hh, VAC_BODY, bevel=0.012))
    _child(root, cylinder(f"{name}_lidar", (0.06, 0, 0.004 + 2 * hh + 0.012), 0.04, 0.012, VAC_BODY, bevel=0.004))
    cu = bpy.data.curves.new(f"{name}_ring", "CURVE")
    cu.dimensions = "3D"
    sp = cu.splines.new("NURBS")
    pts = [(math.cos(a_) * (r - 0.03), math.sin(a_) * (r - 0.03), 0.0, 1.0)
           for a_ in (2 * math.pi * k_ / 24 for k_ in range(24))]
    sp.points.add(len(pts) - 1)
    for pt, co in zip(sp.points, pts, strict=True):
        pt.co = co
    sp.use_cyclic_u = True
    cu.bevel_depth, cu.bevel_resolution = 0.003, 3
    ring_ob = bpy.data.objects.new(f"{name}_ring", cu)
    COLL.objects.link(ring_ob)
    cu.materials.append(VAC_LED)
    ring_ob.location = (0, 0, 0.004 + 2 * hh + 0.001)
    _child(root, ring_ob)
    glow = bpy.data.lights.new(f"{name}_glow", "POINT")
    glow.energy, glow.color, glow.shadow_soft_size = 3.0, (0.3, 0.75, 1.0), 0.1
    glow_ob = bpy.data.objects.new(f"{name}_glow", glow)
    glow_ob.location = (0, 0, 0.004 + 2 * hh + 0.03)
    glow_ob.parent = root
    cast_books.append(glow_ob)
    return root


def cookies_obj(name, half):
    """Three cookies stacked, a little askew; origin at the stack's centre."""
    global COOKIE
    COOKIE = COOKIE or cookie_mat()
    r, _, hh = half
    root = bpy.data.objects.new(name, None)
    n = 3
    for i in range(n):
        h = 2 * hh / n
        c = cylinder(f"{name}_{i}", (0.004 * (i - 1), 0.003 * (1 - i), -hh + h * (i + 0.5)), r * (1 - 0.03 * i),
                     h / 2 - 0.0006, COOKIE, bevel=0.0035)
        c.rotation_euler = (0.03 * (i - 1), -0.02 * i, 0.7 * i)
        bumpy(c, 0.0015, 0.01)
        _child(root, c)
    return root


# ── lights ────────────────────────────────────────────────────────────────────


def light(name, kind, loc, energy, colour, size=None, rot=None, spot=None):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = colour
    if size is not None:
        if kind == "AREA":
            ld.size = size
        else:
            ld.shadow_soft_size = size
    if spot is not None:
        ld.spot_size, ld.spot_blend = spot
    ob = bpy.data.objects.new(name, ld)
    COLL.objects.link(ob)
    ob.location = loc
    if rot is not None:
        ob.rotation_euler = rot
    return ob


def aim(ob, target):
    from mathutils import Vector

    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


if NIGHT:
    # 2 a.m.: moonlight through the window, cold and low; a faint blue fill; the lamp
    # off; a cool pool of light on the cookies, as if the moon picked them out.
    sun = light("sun", "SUN", (wcx, D + 2.5, 3.2), 2.2, (0.55, 0.68, 1.0), size=0.6)
    aim(sun, (2.6, 1.0, 0.0))
    win = light("window", "AREA", (wcx, D - 0.05, wcz), 12.0, (0.55, 0.68, 1.0), size=1.2)
    aim(win, (2.6, 0.8, 0.1))
    fill = light("fill", "AREA", (W / 2, -0.5, 1.2), 6.0, (0.40, 0.50, 0.90), size=3.0)
    aim(fill, (W / 2, 1.6, 0.2))
    ck = R["stealth"]["COOKIE_AT"]
    pool = light("cookie_pool", "SPOT", (ck[0] + 0.2, ck[1] + 0.3, 1.6), 30.0, (0.70, 0.80, 1.0), spot=(0.35, 0.6))
    aim(pool, (ck[0], ck[1], 0.0))
    world.node_tree.nodes["Background"].inputs[0].default_value = lin((0.10, 0.14, 0.28))
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.12
    SKY.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = lin((0.12, 0.17, 0.32))
    SKY.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.6
    SHADE.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.0
    scene.view_settings.exposure = 0.9
elif DAWN:
    # Sunrise: the sun just over the sill, deep orange, raking the floor and the stair;
    # the rest of the room still blue; the lamp left on from the night.
    # (through the window at 1.5 m and down onto the stair: 31 degrees up)
    sun = light("sun", "SUN", (3.6, D + 2.5, 3.0), 8.0, (1.0, 0.55, 0.28), size=0.6)
    aim(sun, (2.9, 1.1, 0.0))
    sun.data.angle = math.radians(1.0)
    win = light("window", "AREA", (wcx, D - 0.05, wcz), 45.0, (1.0, 0.62, 0.42), size=1.2)
    aim(win, (2.8, 0.8, 0.1))
    light("ceiling", "AREA", (W / 2, D / 2, H - 0.02), 22.0, (0.60, 0.68, 1.0), size=2.0)
    fill = light("fill", "AREA", (W / 2, -0.5, 1.2), 30.0, (0.50, 0.62, 1.0), size=3.0)
    aim(fill, (W / 2, 1.6, 0.2))
    light("lamp", "POINT", (lx, ly, c + 0.40), 18.0, (1.0, 0.72, 0.44), size=0.05)
    world.node_tree.nodes["Background"].inputs[0].default_value = lin((0.30, 0.38, 0.62))
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.18
    SKY.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = lin((1.0, 0.50, 0.30))
    SKY.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 1.6
    scene.view_settings.exposure = 0.6
else:
    # Low evening sun through the window, warm; it lays the window's shape on the floor.
    sun = light("sun", "SUN", (wcx, D + 3, 3), 7.0, (1.0, 0.76, 0.52), size=0.6)
    aim(sun, (wcx - 0.6, D - 1.6, 0.0))
    sun.data.angle = math.radians(1.5)
    # The sky's soft light from the window, a dim ceiling fill, a cool bounce from the front.
    win = light("window", "AREA", (wcx, D - 0.05, wcz), 60.0, (1.0, 0.86, 0.70), size=1.2)
    aim(win, (wcx, 0.0, 0.2))
    light("ceiling", "AREA", (W / 2, D / 2, H - 0.02), 35.0, (1.0, 0.93, 0.84), size=1.6)
    fill = light("fill", "AREA", (W / 2, -0.5, 1.4), 22.0, (0.75, 0.82, 1.0), size=2.5)
    aim(fill, (W / 2, 2.2, 0.2))
    light("lamp", "POINT", (lx, ly, c + 0.40), 25.0, (1.0, 0.78, 0.50), size=0.05)
hall_light = light("hall", "AREA", (W + 1.2, R["DOOR"][1], 1.8), 0.0, (1.0, 0.86, 0.66), size=1.0)
aim(hall_light, (W - 0.8, R["DOOR"][1] + 0.4, 0.0))


# ── the cast ──────────────────────────────────────────────────────────────────

meshes = np.load(BAKE / "meshes.npz")
_mesh_cache: dict[str, bpy.types.Mesh] = {}


def robot_mesh(mid: str):
    if mid in _mesh_cache:
        return _mesh_cache[mid]
    v, f = meshes[f"v:{mid}"], meshes[f"f:{mid}"]
    me = bpy.data.meshes.new(f"robot_{mid}")
    me.vertices.add(len(v))
    me.vertices.foreach_set("co", v.ravel())
    me.loops.add(len(f) * 3)
    me.loops.foreach_set("vertex_index", f.ravel())
    me.polygons.add(len(f))
    me.polygons.foreach_set("loop_start", np.arange(0, len(f) * 3, 3, dtype=np.int32))
    me.polygons.foreach_set("loop_total", np.full(len(f), 3, np.int32))
    me.update()
    me.polygons.foreach_set("use_smooth", np.ones(len(f), bool))
    if hasattr(me, "set_sharp_from_angle"):
        me.set_sharp_from_angle(angle=math.radians(35))
    _mesh_cache[mid] = me
    return me


def shirt_mesh(half, seed):
    """A crumpled T-shirt the size of its box: a T outline on a grid, heaped and folded
    by a few seeded ridges, given thickness."""
    hx, hy, hz = half
    rng = np.random.default_rng(seed)
    bm = bmesh.new()
    nx, ny = 28, 24
    grid = {}
    for i in range(nx + 1):
        for j in range(ny + 1):
            x, y = -hx + 2 * hx * i / nx, -hy + 2 * hy * j / ny
            grid[i, j] = (x, y)
    def inside(x, y):
        body = abs(x + 0.1 * hx) < 0.82 * hx and abs(y) < 0.58 * hy
        sleeve = 0.2 * hx < x < 0.80 * hx and abs(y) < 0.98 * hy
        return body or sleeve
    ridges = [(rng.uniform(0, math.pi), rng.uniform(25, 60), rng.uniform(0, 6.3), rng.uniform(0.15, 0.35))
              for _ in range(5)]
    verts = {}
    for (i, j), (x, y) in grid.items():
        heap = math.exp(-((x / (0.9 * hx)) ** 2 + (y / (0.9 * hy)) ** 2))
        fold = sum(a * math.sin(k * (x * math.cos(th) + y * math.sin(th)) + ph) for th, k, ph, a in ridges)
        z = -hz + 0.004 + (2 * hz - 0.01) * max(0.0, 0.55 * heap + 0.45 * heap * (0.5 + 0.5 * fold))
        verts[i, j] = bm.verts.new((x, y, z))
    for i in range(nx):
        for j in range(ny):
            cx, cy = -hx + 2 * hx * (i + 0.5) / nx, -hy + 2 * hy * (j + 0.5) / ny
            if inside(cx, cy):
                bm.faces.new((verts[i, j], verts[i + 1, j], verts[i + 1, j + 1], verts[i, j + 1]))
    for v in [v for v in bm.verts if not v.link_faces]:
        bm.verts.remove(v)
    me = bpy.data.meshes.new("shirt")
    bm.to_mesh(me)
    bm.free()
    return me


def cloth_shirt(half, seed):
    """A simulated crumpled shirt (cloth.py) fitted to its collision box."""
    hx, hy, hz = half
    v = CLOTH[f"shirt{seed % 6}_v"].copy()
    lo, hi = v.min(0), v.max(0)
    v[:, 0] = (v[:, 0] - (lo[0] + hi[0]) / 2) * (1.9 * hx / (hi[0] - lo[0]))
    v[:, 1] = (v[:, 1] - (lo[1] + hi[1]) / 2) * (1.9 * hy / (hi[1] - lo[1]))
    v[:, 2] = (v[:, 2] - lo[2]) * ((2 * hz - 0.004) / (hi[2] - lo[2])) - hz + 0.002
    return _mesh("shirt", v, CLOTH[f"shirt{seed % 6}_f"])


def sock_mesh(half, seed):
    """A sock lying flat: a knit tube along an L (leg, heel, foot), pressed flat, a
    white ribbed cuff at the open end (material slot 1)."""
    hx, hy, hz = half
    cu = bpy.data.curves.new("sock", "CURVE")
    cu.dimensions = "3D"
    sp = cu.splines.new("BEZIER")
    pts = [(-0.98 * hx, -0.45 * hy, 0), (0.30 * hx, -0.50 * hy, 0), (0.62 * hx, 0.72 * hy, 0)]
    sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts, strict=True):
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    r = 0.52 * hy
    cu.bevel_depth = r
    cu.bevel_resolution = 6
    cu.resolution_u = 20
    cu.use_fill_caps = True
    tmp = bpy.data.objects.new("tmp", cu)
    COLL.objects.link(tmp)
    deps = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(deps))
    bpy.data.objects.remove(tmp)
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    flat = 0.024 / (2 * r)  # a sock lies 2.4 cm high, under its 5 cm box
    co[:, 2] = co[:, 2] * flat - hz + r * flat + 0.002
    me.vertices.foreach_set("co", co.ravel())
    me.update()
    cuff = np.array([me.vertices[p.vertices[0]].co.x < -0.72 * hx for p in me.polygons])
    me.polygons.foreach_set("material_index", cuff.astype(np.int32))
    me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), bool))
    return me


def eye_mesh():
    me = bpy.data.meshes.new("eye")
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=1.0)
    bm.to_mesh(me)
    bm.free()
    me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), bool))
    return me


EYE_MESH = eye_mesh()
pos, quat, scale = bake["pos"], bake["quat"], bake["scale"]
frames = np.arange(1, N + 1, dtype=np.float32)


def key(ob, path, values, interp=1):
    """Key `path` (n x k values) on every frame, linear."""
    ob.animation_data_create()
    if ob.animation_data.action is None:
        ob.animation_data.action = bpy.data.actions.new(f"{ob.name}_act")
    act = ob.animation_data.action
    for i in range(values.shape[1]):
        if hasattr(act, "fcurve_ensure_for_datablock"):
            fc = act.fcurve_ensure_for_datablock(ob, path, index=i)
        else:
            fc = act.fcurves.new(path, index=i)
        fc.keyframe_points.add(N)
        co = np.empty(2 * N, np.float32)
        co[0::2], co[1::2] = frames, values[:, i]
        fc.keyframe_points.foreach_set("co", co)
        fc.keyframe_points.foreach_set("interpolation", np.full(N, interp, np.int32))
        fc.update()


cast = bpy.data.collections.new("cast")
scene.collection.children.link(cast)
for o, info in enumerate(meta["objects"]):
    kind = info["kind"]
    if kind == "mesh":
        me = robot_mesh(info["mesh"])  # shared by every crab: one part, one material
        if not me.materials:
            me.materials.append(ROBOT[info["material"]])
        ob = bpy.data.objects.new(f"crab{info['crab']}_{o}", me)
    elif kind == "shirt":
        me = cloth_shirt(info["half"], info["colour"]) if CLOTH is not None else shirt_mesh(info["half"], info["seed"])
        ob = bpy.data.objects.new(f"shirt_{o}", me)
        ob.data.materials.append(SHIRT[info["colour"]])
        so = ob.modifiers.new("thick", "SOLIDIFY")
        so.thickness, so.offset = 0.004, -1
        soft(ob, 1)
    elif kind == "vacuum":
        ob = vacuum_obj(f"vacuum_{o}", info["half"])
    elif kind == "cookies":
        ob = cookies_obj(f"cookies_{o}", info["half"])
    elif kind == "book":
        ob = book(f"book_{o}", (0.0, 0.0, 0.0), info["half"], (0.55, 0.12, 0.12), link=False)
    elif kind == "sock":
        ob = bpy.data.objects.new(f"sock_{o}", sock_mesh(info["half"], info["seed"]))
        ob.data.materials.append(SOCK[info["colour"]])
        ob.data.materials.append(CUFF)
    else:  # eye
        ob = bpy.data.objects.new(f"eye_{o}", EYE_MESH)
        if not EYE_MESH.materials:
            EYE_MESH.materials.append(EYE)
        ob.visible_shadow = False
        key(ob, "scale", scale[:, o])
    cast.objects.link(ob)
    ob.rotation_mode = "QUATERNION"
    key(ob, "location", pos[:, o])
    key(ob, "rotation_quaternion", quat[:, o])
for ob in cast_books:  # a cast book's page block rides on its boards
    cast.objects.link(ob)

# the door and the hall's light
door = bake["door"]
key(hinge, "rotation_euler", np.stack([np.zeros(N), np.zeros(N), np.radians(-door)], 1))
open_ = door / 80.0
key(hall_light.data, "energy", (2500.0 * open_)[:, None])
HALL.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.0
if meta.get("door_light"):
    em = HALL.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
    for f, v in enumerate(open_):
        em.default_value = float(2.5 * v)
        em.keyframe_insert("default_value", frame=f + 1)

# ── camera ────────────────────────────────────────────────────────────────────

cd = bpy.data.cameras.new("cam")
cd.sensor_fit = "VERTICAL"
cd.angle_y = math.radians(meta["fovy"])
cd.clip_start = 0.005
cam = bpy.data.objects.new("cam", cd)
scene.collection.objects.link(cam)
scene.camera = cam
target = bpy.data.objects.new("target", None)
scene.collection.objects.link(target)
key(cam, "location", bake["cam"][:, :3])
key(target, "location", bake["cam"][:, 3:])
tr = cam.constraints.new("TRACK_TO")
tr.target, tr.track_axis, tr.up_axis = target, "TRACK_NEGATIVE_Z", "UP_Y"
dist = np.linalg.norm(bake["cam"][:, 3:] - bake["cam"][:, :3], axis=1)
cd.dof.use_dof = True
cd.dof.focus_object = target
cd.dof.aperture_fstop = 2.8 if dist.mean() < 1.0 else 5.6 if dist.mean() < 2.0 else 11.0

# ── render ────────────────────────────────────────────────────────────────────

out = ROOT / "renders" / f"{FILM}_blend" / ("preview" if PREVIEW else "") / SHOT
out.mkdir(parents=True, exist_ok=True)
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False
if STILL is not None:
    scene.frame_set(STILL)
    scene.render.filepath = str(out / f"still_{STILL:04d}.png")
    bpy.ops.render.render(write_still=True)
else:
    scene.render.filepath = str(out / "f_")
    bpy.ops.render.render(animation=True)
    mp4 = out.parent / f"{SHOT}.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", "30", "-i", str(out / "f_%04d.png"),
                    "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", str(mp4)], check=True)
    print(f"[blend] {mp4}")
