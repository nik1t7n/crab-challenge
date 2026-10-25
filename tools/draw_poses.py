"""Draw an MP4 from poses recorded by `tools/pose_recorder.py`.

    python tools/draw_poses.py clip.npz clip.mp4 --fps 25 [--skip 1.0] [--seconds 5]

Needs only MuJoCo and NumPy (no torch, no physics): each frame sets the recorded
pose, runs kinematics and draws it with the recorded camera and visibility
options, so a machine with a display draws what the render host simulated.
Frames stream straight into ffmpeg as H.264.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

import mujoco
import numpy as np


def _ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("poses", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--fps", type=float, required=True)
    ap.add_argument("--skip", type=float, default=0.0, help="seconds dropped from the start")
    ap.add_argument("--seconds", type=float, default=None, help="length kept")
    args = ap.parse_args()

    rec = np.load(args.poses)
    model = mujoco.MjModel.from_binary_path(str(args.poses.with_suffix(".mjb")))
    data = mujoco.MjData(model)
    width, height = int(rec["width"]), int(rec["height"])
    model.vis.global_.offwidth = max(model.vis.global_.offwidth, width)
    model.vis.global_.offheight = max(model.vis.global_.offheight, height)
    renderer = mujoco.Renderer(model, height=height, width=width)

    opt = mujoco.MjvOption()
    for key in rec.files:
        if key.startswith("opt_"):
            value = rec[key]
            if value.ndim:
                getattr(opt, key[4:])[...] = value
            else:
                setattr(opt, key[4:], value.item())
    cam = mujoco.MjvCamera()

    first = round(args.skip * args.fps)
    last = len(rec["qpos"]) if args.seconds is None else first + round(args.seconds * args.fps)
    frames = range(first, min(last, len(rec["qpos"])))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = subprocess.Popen(
        [_ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{width}x{height}", "-r", f"{args.fps:g}", "-i", "-",
         "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", str(args.out)],
        stdin=subprocess.PIPE,
    )
    for i in frames:
        data.qpos[:] = rec["qpos"][i]
        if model.nmocap:
            data.mocap_pos[:] = rec["mocap_pos"][i]
            data.mocap_quat[:] = rec["mocap_quat"][i]
        mujoco.mj_forward(model, data)
        for key in rec.files:
            if key.startswith("cam_"):
                value = rec[key][i]
                setattr(cam, key[4:], value if value.ndim else value.item())
        renderer.update_scene(data, camera=cam, scene_option=opt)
        ffmpeg.stdin.write(renderer.render().tobytes())
    ffmpeg.stdin.close()
    renderer.close()
    return ffmpeg.wait()


if __name__ == "__main__":
    raise SystemExit(main())
