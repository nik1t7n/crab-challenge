"""Run upstream `scripts/play.py` with a renderer that records instead of drawing.

    POSES_OUT=clip.npz python tools/pose_recorder.py <play.py arguments...>

Why: the render host (a Mac Studio reached over SSH) has no window-server session
for our user, so MuJoCo's CGL context fails with "invalid CoreGraphics
connection", while the physics and the policies run fine there. Drawing a frame
needs only the render model, the pose and the camera, so this splits the work:
here every frame's pose and camera go to an .npz beside a copy of the render
model (.mjb), and `tools/draw_poses.py` draws them on a machine that has a
display, with plain MuJoCo and no torch.

The seam is `mujoco.Renderer`, the one class mjlab's offscreen renderer
constructs (`rl/mjlab/viewer/offscreen_renderer.py`); upstream code is untouched.
"""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

import mujoco
import numpy as np

OUT = Path(os.environ["POSES_OUT"])
PLAY = Path(sys.argv[1])

_CAMERA_FIELDS = ("type", "fixedcamid", "trackbodyid", "lookat", "distance", "azimuth",
                  "elevation", "orthographic")
_OPTION_FIELDS = ("label", "frame", "geomgroup", "sitegroup", "jointgroup", "tendongroup",
                  "actuatorgroup", "flexgroup", "skingroup", "flags")


class RecordingRenderer:
    """Same calls as `mujoco.Renderer`; keeps poses and cameras, draws nothing."""

    def __init__(self, model: mujoco.MjModel, height: int = 240, width: int = 320,
                 max_geom: int = 10000):
        self._model = model
        self._blank = np.zeros((height, width, 3), dtype=np.uint8)
        self._scene = mujoco.MjvScene(model, maxgeom=max_geom)
        self._frames: dict[str, list] = {"qpos": [], "mocap_pos": [], "mocap_quat": []}
        self._cams: dict[str, list] = {f: [] for f in _CAMERA_FIELDS}
        self._option: dict[str, np.ndarray] | None = None
        self.size = (width, height)

    @property
    def scene(self) -> mujoco.MjvScene:
        return self._scene

    def update_scene(self, data, camera=None, scene_option=None) -> None:
        if self._option is None:
            # The model is saved at the first frame, after mjlab has synced its
            # per-world fields into it, so colours and materials are the drawn ones.
            mujoco.mj_saveModel(self._model, str(OUT.with_suffix(".mjb")), None)
            opt = scene_option or mujoco.MjvOption()
            self._option = {f: np.array(getattr(opt, f)) for f in _OPTION_FIELDS}
        self._frames["qpos"].append(np.array(data.qpos))
        self._frames["mocap_pos"].append(np.array(data.mocap_pos))
        self._frames["mocap_quat"].append(np.array(data.mocap_quat))
        cam = camera if isinstance(camera, mujoco.MjvCamera) else mujoco.MjvCamera()
        for f in _CAMERA_FIELDS:
            self._cams[f].append(np.array(getattr(cam, f)))

    def render(self, *args, **kwargs) -> np.ndarray:
        return self._blank

    def close(self) -> None:
        if self._option is None:
            return
        np.savez_compressed(
            OUT,
            width=self.size[0], height=self.size[1],
            **{k: np.stack(v) for k, v in self._frames.items()},
            **{f"cam_{k}": np.stack(v) for k, v in self._cams.items()},
            **{f"opt_{k}": v for k, v in self._option.items()},
        )
        self._option = None

    def __del__(self):
        self.close()


mujoco.Renderer = RecordingRenderer


def _inject_scene() -> None:
    """`SCENE_MODULE=path.py` registers that file as `--scene <stem>`, without
    touching the upstream checkout: it is put in `sys.modules` as `scenes.<stem>`,
    which is where `scenes.registry` imports a scene from."""
    path = os.environ.get("SCENE_MODULE")
    if not path:
        return
    import importlib.util

    import scenes  # noqa: F401  (the package must exist before its child is added)
    from scenes.registry import register

    stem = Path(path).stem.removesuffix("_scene")
    loader = importlib.util.spec_from_file_location(f"scenes.{stem}", path)
    module = importlib.util.module_from_spec(loader)
    sys.modules[f"scenes.{stem}"] = module
    loader.loader.exec_module(module)
    register(stem, description="the heist film's set (tools/film)", use="watching")


def _fix_start() -> None:
    """`FIXED_START=x,y,yaw_deg` puts the robot there on every reset instead of
    the replay's random spot and heading, so a course can be laid out ahead of it.
    Every reset event with a `pose_range` is pinned (the velocity tasks' `reset_base`)."""
    spec = os.environ.get("FIXED_START")
    if not spec:
        return
    import math

    import tasks

    x, y, yaw = (float(v) for v in spec.split(","))
    load = tasks.load_env_cfg

    def pinned(*args, **kwargs):
        cfg = load(*args, **kwargs)
        for term in getattr(cfg, "events", {}).values():
            params = getattr(term, "params", None) or {}
            if params.get("pose_range"):
                params["pose_range"] = {"x": (x, x), "y": (y, y), "z": (0.01, 0.01),
                                        "yaw": (math.radians(yaw), math.radians(yaw))}
        return cfg

    tasks.load_env_cfg = pinned


def _feed_pose() -> None:
    """Hand a command script the robot's pose, so it can steer instead of guessing.

    A replay is not exactly repeatable (two runs of one open-loop script through the
    vault parted by 13 cm within ten seconds and one ended on a pillar), so a course
    is driven the way a robot is: a path follower on top of the walking policy. The
    script still returns velocity and posture commands, the policy still does the
    walking; before each call `builtins._crab_pose` is set to (x, y, yaw).
    """
    import builtins
    import math

    from mjrl import replay

    install = replay.script_commands

    def with_pose(env, script):
        data = env.scene["robot"].data

        props = [name for name in os.environ.get("FEED_PROPS", "").split(",") if name]

        def fed(t):
            p = data.root_link_pose_w[0].detach().cpu().numpy()
            w, x, y, z = (float(v) for v in p[3:7])
            builtins._crab_pose = (float(p[0]), float(p[1]),
                                   math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))
            # and the props it is working on (`FEED_PROPS=gold`), as (x, y)
            builtins._crab_props = {
                name: tuple(float(v) for v in env.scene[name].data.root_link_pose_w[0, :2].detach().cpu())
                for name in props
            }
            return script(t)

        return install(env, fed)

    replay.script_commands = with_pose


_inject_scene()
_fix_start()
_feed_pose()
sys.argv = sys.argv[1:]
sys.path.insert(0, str(PLAY.parent))
runpy.run_path(str(PLAY), run_name="__main__")
