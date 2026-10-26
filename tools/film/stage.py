"""The film's sound stage: draw a recorded take as a directed shot.

A take is what `tools/pose_recorder.py` wrote on the render host: the scene model
(`.mjb`) and, per recorded frame, the pose of everything in it. Nothing here
simulates. A shot re-times the take, moves its own camera, dresses the set with
geometry that exists only in the picture (walls, a floor grid, laser beams) and
lights it, and may pose things the policy does not drive (the carried arm, a prop
in the claw). The robot's walking, crouching and jumping are the recorded policy's
own motion; everything this file adds is set dressing and is said so in
`docs/JOURNAL.md`.

The pieces, each a plain function of time so a shot is a list of them:

  * `TimeMap`: output seconds -> take seconds, in segments (real time, slow motion,
    a freeze while the camera moves);
  * `CameraPath`: keyframes in the world or relative to the robot, eased;
  * set dressing: callables `(take_t) -> [Geom]`, drawn into the scene each frame;
  * `Lighting`: the model's own lights dimmed and coloured, plus added spots;
  * placement: takes recorded on an empty floor set down in the film's room.
"""

from __future__ import annotations

import math
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import mujoco
import numpy as np

RENDERS = Path(__file__).resolve().parents[2] / "renders"
TAKE_FPS = 25.0  # the recorder's frame rate (tools/render_gallery.py FPS)


def smooth(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3.0 - 2.0 * x)


def ramp(t: float, t0: float, t1: float) -> float:
    return smooth((t - t0) / (t1 - t0))


# ── the take ──────────────────────────────────────────────────────────────────


class Take:
    """A recorded take, posed at any time by interpolating between frames.

    `place=(x, y, yaw_deg)` sets the take down in the film's room: the robot's
    position at the start of the take goes to (x, y) and its heading there to
    `yaw_deg`, and everything free in the take moves rigidly with it. Takes
    recorded on an empty floor become parts of one continuous space this way. A
    fourth value lifts it: a take recorded on the floor set down on a flat top that
    high (the same rigid flat contact, raised).
    """

    def __init__(self, name: str, place: tuple[float, float, float] | None = None, group: str = "film"):
        if "/" in name:  # "group/name": a take from another folder (a gesture, a jump)
            group, name = name.split("/", 1)
        self.name = name
        npz = RENDERS / group / f"{name}.npz"
        self.rec = np.load(npz)
        self.model = mujoco.MjModel.from_binary_path(str(npz.with_suffix(".mjb")))
        self.data = mujoco.MjData(self.model)
        self.frames = len(self.rec["qpos"])
        self.duration = (self.frames - 1) / TAKE_FPS
        m = self.model
        self._quat_slices = [
            slice(m.jnt_qposadr[j] + 3, m.jnt_qposadr[j] + 7)
            for j in range(m.njnt) if m.jnt_type[j] == mujoco.mjtJoint.mjJNT_FREE
        ]
        self.root = self.body("robot/base_link")
        self._free = [int(m.jnt_qposadr[j]) for j in range(m.njnt) if m.jnt_type[j] == mujoco.mjtJoint.mjJNT_FREE]
        self._move = None
        if place is not None:
            q0 = self.rec["qpos"][0]
            adr = int(m.jnt_qposadr[m.body_jntadr[self.root]])
            w, x, y, z = q0[adr + 3:adr + 7]
            yaw0 = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
            turn = math.radians(place[2]) - yaw0
            self._move = (q0[adr:adr + 2].copy(), np.array(place[:2], float), turn,
                          float(place[3]) if len(place) > 3 else 0.0)

    def body(self, name: str) -> int:
        return mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, name)

    def joint_qpos(self, name: str) -> int:
        return int(self.model.jnt_qposadr[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, name)])

    def pose(self, t: float) -> None:
        """Set `data` to the take at `t` seconds and run kinematics."""
        f = min(max(t * TAKE_FPS, 0.0), self.frames - 1.0)
        i = min(int(f), self.frames - 2)
        a = f - i
        q = (1 - a) * self.rec["qpos"][i] + a * self.rec["qpos"][i + 1]
        for s in self._quat_slices:
            q[s] /= np.linalg.norm(q[s])
        if self._move is not None:
            origin, target, turn, lift = self._move
            c, s_ = math.cos(turn), math.sin(turn)
            rz = np.array([math.cos(turn / 2), 0.0, 0.0, math.sin(turn / 2)])
            for a in self._free:
                dx, dy = q[a] - origin[0], q[a + 1] - origin[1]
                q[a], q[a + 1] = target[0] + c * dx - s_ * dy, target[1] + s_ * dx + c * dy
                q[a + 2] += lift
                out = np.zeros(4)
                mujoco.mju_mulQuat(out, rz, q[a + 3:a + 7])
                q[a + 3:a + 7] = out
        self.data.qpos[:] = q
        if self.model.nmocap:
            self.data.mocap_pos[:] = self.rec["mocap_pos"][i]
            self.data.mocap_quat[:] = self.rec["mocap_quat"][i]
        mujoco.mj_kinematics(self.model, self.data)

    def robot_pos(self, t: float) -> np.ndarray:
        self.pose(t)
        return self.data.xpos[self.root].copy()

    def robot_geoms(self) -> np.ndarray:
        m = self.model
        inside = np.zeros(m.nbody, bool)
        inside[self.root] = True
        for b in range(self.root + 1, m.nbody):
            inside[b] = inside[m.body_parentid[b]]
        return np.flatnonzero(inside[m.geom_bodyid])


# ── time and camera ───────────────────────────────────────────────────────────


@dataclass
class TimeMap:
    """Output time -> take time. Each segment is (output seconds, take from, take to):
    equal ends hold a frame, a short take span over a long output is slow motion."""

    segments: Sequence[tuple[float, float, float]]

    @property
    def duration(self) -> float:
        return sum(s[0] for s in self.segments)

    def __call__(self, t: float) -> float:
        for dur, a, b in self.segments:
            if t <= dur:
                return a + (b - a) * (t / dur if dur else 1.0)
            t -= dur
        return self.segments[-1][2]


@dataclass
class Key:
    """A camera keyframe. `lookat` is world xyz, or None to look at the robot
    (plus `offset`). Azimuth is in world degrees (MuJoCo's: 0 looks along +x
    from -x... MuJoCo's free camera convention), elevation negative looks down."""

    t: float
    distance: float
    azimuth: float
    elevation: float
    lookat: tuple[float, float, float] | None = None
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)


class CameraPath:
    """Eased keyframes, plus an optional hand-held wobble of `shake` degrees: a few
    incommensurate sines, so it never repeats within a shot and renders the same
    every time."""

    def __init__(self, keys: Sequence[Key], shake: float = 0.0):
        self.keys = sorted(keys, key=lambda k: k.t)
        self.shake = shake

    def at(self, t: float, robot: np.ndarray) -> tuple[np.ndarray, float, float, float]:
        ks = self.keys
        if t <= ks[0].t or len(ks) == 1:
            a, b, w = ks[0], ks[0], 0.0
        elif t >= ks[-1].t:
            a, b, w = ks[-1], ks[-1], 0.0
        else:
            j = next(i for i in range(1, len(ks)) if ks[i].t >= t)
            a, b = ks[j - 1], ks[j]
            w = smooth((t - a.t) / (b.t - a.t))

        def look(k: Key) -> np.ndarray:
            base = robot if k.lookat is None else np.asarray(k.lookat, float)
            return base + np.asarray(k.offset, float)

        lookat = (1 - w) * look(a) + w * look(b)
        def mix(x, y):
            return (1 - w) * x + w * y
        az, el = mix(a.azimuth, b.azimuth), mix(a.elevation, b.elevation)
        if self.shake:
            az += self.shake * (math.sin(4.1 * t) + 0.6 * math.sin(9.7 * t + 1.3))
            el += 0.7 * self.shake * (math.sin(5.3 * t + 0.4) + 0.5 * math.sin(11.9 * t + 2.1))
        return lookat, mix(a.distance, b.distance), az, el


# ── set dressing ──────────────────────────────────────────────────────────────


@dataclass
class Geom:
    """One piece of picture-only geometry. A capsule `beam` from `a` to `b`, or a
    box/sphere/cylinder at `pos` with half-`size` and optional yaw (degrees)."""

    kind: str
    rgba: tuple[float, float, float, float]
    pos: tuple[float, float, float] = (0, 0, 0)
    size: tuple[float, float, float] = (0, 0, 0)
    yaw: float = 0.0
    pitch: float = 0.0
    a: tuple[float, float, float] | None = None
    b: tuple[float, float, float] | None = None
    width: float = 0.002
    emission: float = 0.0
    specular: float = 0.3
    #: (axis, plane): a wall at that plane is left out while the camera stands
    #: beyond it, the way a set takes out the wall the camera shoots through.
    cull: tuple[int, float] | None = None
    mat: tuple[float, ...] | None = None  # a full orientation, overriding yaw and pitch


_TYPES = {"box": mujoco.mjtGeom.mjGEOM_BOX, "sphere": mujoco.mjtGeom.mjGEOM_SPHERE,
          "ellipsoid": mujoco.mjtGeom.mjGEOM_ELLIPSOID,
          "cylinder": mujoco.mjtGeom.mjGEOM_CYLINDER, "beam": mujoco.mjtGeom.mjGEOM_CAPSULE}


def add_geoms(scene: mujoco.MjvScene, geoms: Sequence[Geom], camera: np.ndarray | None = None) -> None:
    for g in geoms:
        if g.cull is not None and camera is not None:
            axis, plane = g.cull
            if (camera[axis] - plane) * (1.0 if plane > 0 else -1.0) > 0:
                continue
        if scene.ngeom >= scene.maxgeom:
            raise RuntimeError("scene full: raise max_geom")
        v = scene.geoms[scene.ngeom]
        if g.kind == "beam":
            mujoco.mjv_initGeom(v, _TYPES["beam"], np.zeros(3), np.zeros(3), np.eye(3).ravel(),
                                np.asarray(g.rgba, np.float32))
            mujoco.mjv_connector(v, _TYPES["beam"], g.width, np.asarray(g.a, float), np.asarray(g.b, float))
        else:
            c, s = math.cos(math.radians(g.yaw)), math.sin(math.radians(g.yaw))
            cp, sp = math.cos(math.radians(g.pitch)), math.sin(math.radians(g.pitch))
            yaw_m = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], float)
            pitch_m = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]], float)
            mat = np.asarray(g.mat, float) if g.mat is not None else (yaw_m @ pitch_m).ravel()
            mujoco.mjv_initGeom(v, _TYPES[g.kind], np.asarray(g.size, float), np.asarray(g.pos, float),
                                mat, np.asarray(g.rgba, np.float32))
        v.emission = g.emission
        v.specular = g.specular
        scene.ngeom += 1


def laser(a, b, color=(1.0, 0.08, 0.05), core=0.0015, halo=0.006, alpha=1.0) -> list[Geom]:
    """A beam: a bright core and a faint halo around it."""
    return [Geom("beam", (*color, alpha), a=a, b=b, width=core, emission=1.0, specular=0.0),
            Geom("beam", (*color, 0.18 * alpha), a=a, b=b, width=halo, emission=1.0, specular=0.0)]


def vault(center=(0.0, 0.0), half=1.6, wall_h=0.45, grid=0.25,
          floor_lines=(0.25, 0.75, 1.0, 0.10)) -> list[Geom]:
    """Walls of dark steel around `center` and a faint grid on the floor."""
    cx, cy = center
    steel = (0.07, 0.08, 0.10, 1.0)
    out = [
        Geom("box", steel, pos=(cx + half, cy, wall_h), size=(0.02, half, wall_h)),
        Geom("box", steel, pos=(cx - half, cy, wall_h), size=(0.02, half, wall_h)),
        Geom("box", steel, pos=(cx, cy + half, wall_h), size=(half, 0.02, wall_h)),
        Geom("box", steel, pos=(cx, cy - half, wall_h), size=(half, 0.02, wall_h)),
    ]
    n = int(half / grid)
    for k in range(-n, n + 1):
        d = k * grid
        out.append(Geom("box", floor_lines, pos=(cx + d, cy, 0.0006), size=(0.0012, half, 0.0005), emission=0.6))
        out.append(Geom("box", floor_lines, pos=(cx, cy + d, 0.0006), size=(half, 0.0012, 0.0005), emission=0.6))
    return out


@dataclass
class Spot:
    """A spot light. `on_at` (output seconds) switches it on with a short flicker,
    for a room lit bank by bank; `follow` keeps `pos` and `aim` relative to the
    robot (a key light that rides along with the hero)."""

    pos: tuple[float, float, float]
    aim: tuple[float, float, float]
    color: tuple[float, float, float]
    cutoff: float = 25.0
    exponent: float = 8.0
    shadow: bool = True
    on_at: float | None = None
    follow: bool = False

    def level(self, t_out: float) -> float:
        if self.on_at is None:
            return 1.0
        x = t_out - self.on_at
        if x < 0:
            return 0.0
        # a fluorescent strike: on, a dip, then full
        return 1.0 if x > 0.16 else (0.9 if x < 0.05 else 0.25 if x < 0.09 else 0.8)


def light_scene(scene: mujoco.MjvScene, spots: Sequence[Spot], t_out: float = 0.0,
                robot: np.ndarray | None = None) -> None:
    for s in spots:
        level = s.level(t_out)
        if level <= 0 or scene.nlight >= 8:  # MuJoCo's renderer lights 8 at most
            continue
        lt = scene.lights[scene.nlight]
        base = robot if (s.follow and robot is not None) else np.zeros(3)
        pos = base + np.asarray(s.pos, float)
        aim = base + np.asarray(s.aim, float)
        lt.type = mujoco.mjtLightType.mjLIGHT_SPOT
        lt.pos[:] = pos
        d = aim - pos
        lt.dir[:] = d / np.linalg.norm(d)
        lt.diffuse[:] = [c * level for c in s.color]
        lt.specular[:] = [c * 0.5 * level for c in s.color]
        lt.ambient[:] = 0
        lt.attenuation[:] = [1, 0, 0]
        lt.cutoff = s.cutoff
        lt.exponent = s.exponent
        lt.castshadow = s.shadow
        lt.headlight = 0
        lt.intensity = 1.0
        lt.range = 10.0
        scene.nlight += 1


#: The crab in white so it reads against any room; its black joints and grey pads
#: keep the shape legible.
SHELL = (0.93, 0.94, 0.96, 1.0)
PADS = (0.62, 0.65, 0.70, 1.0)


def paint_crab(model, take) -> None:
    """The model's red shell parts white and its white pads grey."""
    for g in take.robot_geoms():
        r, gr, b, _ = model.geom_rgba[g]
        if r > 0.6 and gr < 0.3 and b < 0.3:
            model.geom_rgba[g] = SHELL
        elif r > 0.7 and gr > 0.7 and b > 0.7:
            model.geom_rgba[g] = PADS


ARM = ("robot/LF_J0_joint", "robot/LF_J1_joint", "robot/LF_J2_joint", "robot/LF_J3_joint")

# ── the face ──────────────────────────────────────────────────────────────────

#: The robot's display module, in the trunk's frame (measured on the model: centre
#: (0.079, 0, 0.048), half extent (0.013, 0.054, 0.017)); the eyes sit on its face.
SCREEN_X, SCREEN_Z, EYE_Y = 0.0935, 0.049, 0.024

#: Expressions: eye half width (y) and height (z), a vertical offset, a sideways
#: gaze and a tilt (deg, + raises the outer corners). Real Jumper has two round TFT
#: eyes on this face; the model's screen is blank, so the film draws them.
FACES = {
    "open": {"w": 0.011, "h": 0.013, "dz": 0.0, "dy": 0.0, "tilt": 0.0},
    "panic": {"w": 0.014, "h": 0.016, "dz": 0.001, "dy": 0.0, "tilt": 0.0},
    "focus": {"w": 0.012, "h": 0.006, "dz": 0.0, "dy": 0.0, "tilt": -18.0},
    "happy": {"w": 0.012, "h": 0.004, "dz": 0.005, "dy": 0.0, "tilt": 12.0},
    "guilty": {"w": 0.010, "h": 0.008, "dz": -0.007, "dy": 0.0, "tilt": 16.0},
}
EYE_GLOW = (0.45, 0.88, 1.0, 1.0)


def eye_geoms(data, root: int, face: dict, blink: float = 0.0) -> list[Geom]:
    """The two eyes for one crab, as glowing ellipsoids on its screen."""
    R = data.xmat[root].reshape(3, 3)
    p = data.xpos[root]
    out = []
    for side in (1.0, -1.0):
        local = np.array([SCREEN_X, side * EYE_Y + face["dy"], SCREEN_Z + face["dz"]])
        pos = p + R @ local
        tilt = math.radians(face["tilt"]) * side
        roll = np.array([[1, 0, 0], [0, math.cos(tilt), -math.sin(tilt)], [0, math.sin(tilt), math.cos(tilt)]])
        mat = R @ roll
        h = max(0.0008, face["h"] * (1.0 - blink))
        out.append(Geom("ellipsoid", EYE_GLOW, pos=tuple(pos), size=(0.0025, face["w"], h), emission=1.0,
                        specular=0.0, mat=tuple(mat.ravel())))
    return out


def blink_at(t: float, phase: float) -> float:
    """1 while the eyes are shut: a 0.12 s blink every 3.4 s, offset per crab."""
    x = (t + phase) % 3.4
    return 1.0 if x < 0.12 else 0.0


# ── the shot ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Look:
    """The base light and air of a film: the headlight, the scene's own overhead
    light, and the fog colour the far distance fades into."""

    head_ambient: tuple[float, float, float]
    head_diffuse: tuple[float, float, float]
    overhead: tuple[float, float, float]
    fog_rgba: tuple[float, float, float, float]
    specular: float = 0.05


#: The heist: a dark vault, a cool overhead, fog to black.
VAULT = Look((0.13, 0.13, 0.16), (0.42, 0.42, 0.48), (0.30, 0.34, 0.46), (0.01, 0.012, 0.02, 1.0))


@dataclass
class Shot:
    name: str
    take: str
    time: TimeMap
    camera: CameraPath
    dressing: Sequence[Callable[[float], list[Geom]]] = ()
    spots: Sequence[Spot] = ()
    recolor: Callable[[mujoco.MjModel, Take], None] | None = None
    #: The room's base light (headlight and overhead) as a share of full, by
    #: output time: a reveal starts dark and comes up with its lights.
    ambient: Callable[[float], float] | None = None
    fovy: float = 40.0
    #: Leave out the walls the camera stands behind (False keeps them: a shot through
    #: a doorway from outside wants the wall around the opening).
    cull: bool = True
    place: tuple[float, ...] | None = None  # (x, y, yaw deg[, lift]): see Take
    group: str = "film"  # where the take lives under renders/
    #: More takes drawn into the same picture (their robots and things; the room is
    #: the main take's): the bedroom crew, six simulations on one floor.
    crew: tuple[str, ...] = ()
    #: `(crew index, main take time) -> that take's time`, for a crew that is not on
    #: the main take's clock (the crabs parked while one more take plays).
    crew_time: Callable[[int, float], float] | None = None
    #: `take -> [Geom]`, called on every take (the main one and the crew) once it is
    #: posed: a picture-only skin over a prop's collision shape (a sock over its box).
    skin: Callable[[Take], list[Geom]] | None = None
    #: `(t_out, crab index) -> FACES key`; None draws no eyes. Index 0 is the main take.
    eyes: Callable[[float, int], str] | None = None
    fog: tuple[float, float] = (0.6, 3.0)
    look: Look = VAULT


def _ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def render(shot: Shot, out: Path, size=(1920, 1080), fps=30.0) -> Path:
    take = Take(shot.take, shot.place, shot.group)
    m = take.model
    w, h = size
    m.vis.global_.offwidth = max(m.vis.global_.offwidth, w)
    m.vis.global_.offheight = max(m.vis.global_.offheight, h)
    m.vis.quality.offsamples = 8
    m.vis.quality.shadowsize = 4096
    m.vis.global_.fovy = shot.fovy
    look = shot.look
    head_amb = np.array(look.head_ambient)
    head_dif = np.array(look.head_diffuse)
    over_dif = np.array(look.overhead)
    m.vis.headlight.specular[:] = [look.specular] * 3
    m.light_specular[:] = [0.1, 0.1, 0.15]
    m.light_castshadow[:] = 1
    m.vis.rgba.fog[:] = look.fog_rgba
    m.vis.map.fogstart, m.vis.map.fogend = shot.fog
    m.vis.map.znear = 0.005
    if shot.recolor is not None:
        shot.recolor(m, take)

    renderer = mujoco.Renderer(m, height=h, width=w, max_geom=4000)
    opt = mujoco.MjvOption()
    for key in take.rec.files:
        if key.startswith("opt_"):
            v = take.rec[key]
            if v.ndim:
                getattr(opt, key[4:])[...] = v
            else:
                setattr(opt, key[4:], v.item())
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE

    # The crew: each other take draws only its robot and its things (everything else
    # is moved to geom group 5, which their option leaves out).
    others = []
    for name in shot.crew:
        other = Take(name, shot.place, shot.group)
        om = other.model
        if shot.recolor is not None:
            shot.recolor(om, other)
        mine = set(other.robot_geoms().tolist())
        for g in range(om.ngeom):
            body = mujoco.mj_id2name(om, mujoco.mjtObj.mjOBJ_BODY, om.geom_bodyid[g]) or ""
            if g not in mine and not body.startswith("item"):
                om.geom_group[g] = 5
        oopt = mujoco.MjvOption()
        oopt.geomgroup[:] = opt.geomgroup
        oopt.geomgroup[5] = 0
        others.append((other, oopt))
    pert = mujoco.MjvPerturb()

    out.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [_ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{w}x{h}", "-r", f"{fps:g}", "-i", "-", "-c:v", "libx264", "-crf", "16",
         "-preset", "medium", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
        stdin=subprocess.PIPE,
    )
    n = round(shot.time.duration * fps)
    for i in range(n):
        t_out = i / fps
        t = shot.time(t_out)
        level = 1.0 if shot.ambient is None else shot.ambient(t_out)
        m.vis.headlight.ambient[:] = head_amb * level
        m.vis.headlight.diffuse[:] = head_dif * level
        m.light_diffuse[:] = over_dif * level
        take.pose(t)
        lookat, dist, az, el = shot.camera.at(t_out, take.data.xpos[take.root].copy())
        cam.lookat[:] = lookat
        cam.distance, cam.azimuth, cam.elevation = dist, az, el
        renderer.update_scene(take.data, camera=cam, scene_option=opt)
        scn = renderer.scene
        for j, (other, oopt) in enumerate(others):
            other.pose(t if shot.crew_time is None else shot.crew_time(j, t))
            mujoco.mjv_addGeoms(other.model, other.data, oopt, pert, int(mujoco.mjtCatBit.mjCAT_ALL), scn)
        if shot.skin is not None:
            for crab in [take] + [o for o, _ in others]:
                add_geoms(scn, shot.skin(crab))
        if shot.eyes is not None:
            for k, crab in enumerate([take] + [o for o, _ in others]):
                face = FACES[shot.eyes(t_out, k)]
                add_geoms(scn, eye_geoms(crab.data, crab.root, face, blink_at(t_out, 0.7 * k)))
        scn.flags[mujoco.mjtRndFlag.mjRND_FOG] = 1
        scn.flags[mujoco.mjtRndFlag.mjRND_SHADOW] = 1
        scn.flags[mujoco.mjtRndFlag.mjRND_REFLECTION] = 1
        az, el = math.radians(cam.azimuth), math.radians(cam.elevation)
        eye = np.asarray(lookat) - cam.distance * np.array([math.cos(el) * math.cos(az),
                                                            math.cos(el) * math.sin(az), math.sin(el)])
        for dress in shot.dressing:
            add_geoms(scn, dress(t), eye if shot.cull else None)
        light_scene(scn, shot.spots, t_out, take.data.xpos[take.root].copy())
        proc.stdin.write(renderer.render().tobytes())
    proc.stdin.close()
    renderer.close()
    if proc.wait():
        raise RuntimeError(f"ffmpeg failed on {out}")
    return out
