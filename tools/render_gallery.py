"""Render a gallery of what the committed Jumper policies already do, as MP4s.

    upstream/jumper/.venv/bin/python tools/render_gallery.py              # everything
    upstream/jumper/.venv/bin/python tools/render_gallery.py --only skills
    upstream/jumper/.venv/bin/python tools/render_gallery.py --list

Every clip is one run of upstream `scripts/play.py --video` (the repository's one
recorder) on a committed `tasks/<task>/out/example/` checkpoint, so nothing here
is trained. Upstream `tools/readme_media.py` does the same for the README at GIF
size in one scene; this file widens it to every scene and to several camera angles
so we can pick what reads best on video. Clips land in `renders/<group>/`.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JUMPER = ROOT / "upstream" / "jumper"
DESIGN = ROOT / "upstream" / "jumper-design"
PLAY = JUMPER / "scripts" / "play.py"
COMMANDS = Path(__file__).resolve().with_name("commands.py")
RECORDER = Path(__file__).resolve().with_name("pose_recorder.py")
DRAWER = Path(__file__).resolve().with_name("draw_poses.py")
FILM_DIR = Path(__file__).resolve().parent / "film"
#: The film's own scenes (`tools/film/<name>_scene.py`) and the props whose position
#: a command script steers by.
PROPS_FED = {"gold": ("gold",), "bedroom": ("item0", "item1"), "rocky": ("weight",), "stealth": ("cookie",)}
OUT = ROOT / "renders"

#: One render peaks at about 1.3 GB (torch + MuJoCo + offscreen GL), measured with
#: `/usr/bin/time -l` on dance_waist. Five at once plus pytest froze a 16 GB Mac that
#: was already 13 GB into swap. So the number of renders is capped by a memory budget
#: (`--budget-gb`, RENDER_GB each), no render starts while macOS reports less than
#: `--min-free-pct` free (`kern.memorystatus_level`), and renders run at lowered
#: priority so whatever else the machine serves keeps the CPU first.
RENDER_GB = 1.4
#: Drawing recorded poses loads only MuJoCo and the scene, no torch.
DRAW_GB = 0.5
DEFAULT_BUDGET_GB = 3.0
DEFAULT_MIN_FREE_PCT = 30
#: The policy is a small MLP; torch's default of one thread per core in every
#: process only oversubscribes the CPU when many renders run side by side.
SINGLE_THREAD = {"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                 "VECLIB_MAXIMUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}

#: 25 frames a second divides both control rates there are (50 Hz and 200 Hz).
FPS = 25
HD = (1280, 720)
VERTICAL = (720, 1280)


@dataclass(frozen=True)
class Camera:
    distance: float = 0.72
    azimuth: float = 140.0  # degrees from the robot's heading: 0 behind, 180 front
    elevation: float = -16.0
    height: float = 0.06  # look-at height for a fixed camera
    follow: bool = True


@dataclass(frozen=True)
class Clip:
    group: str
    name: str
    task: str
    skip: float  # seconds of rollout cut from the start (settling after reset)
    seconds: float | None  # None = the whole tracked recording
    scene: str = "studio"
    camera: Camera = field(default_factory=Camera)
    script: str | None = None  # a function in tools/commands.py
    size: tuple[int, int] = HD
    extra: tuple[str, ...] = ()  # task options for play.py, e.g. ("--objects", "--hold", "soap")
    start: tuple[float, float, float] | None = None  # fixed spawn (x, y, yaw deg) instead of random
    env: tuple[tuple[str, str], ...] = ()  # extra environment for the take (e.g. CREW=3)


# ── what gets drawn ───────────────────────────────────────────────────────────

FIXED = Camera(follow=False)
FRONT = Camera(azimuth=160.0, elevation=-12.0, follow=False)

SKILLS = [
    Clip("skills", "walk", "jumper.posture", 1.0, 5.0, script="walk"),
    Clip("skills", "posture", "jumper.posture", 1.0, 6.0, camera=FIXED, script="pose"),
    Clip("skills", "claw_walk", "jumper.five_foot", 1.0, 5.0, script="claw"),
    Clip("skills", "jump", "jumper.jump", 0.0, 1.76, camera=Camera(distance=0.85, height=0.17)),
    Clip("skills", "ref_free_jump", "jumper.ref_free_jump", 0.0, 3.0,
         camera=Camera(distance=0.9, height=0.17)),
    Clip("skills", "dance_crab", "jumper.dance", 2.0, None, camera=FRONT),
    Clip("skills", "dance_brazilian", "jumper.dance_brazilian", 0.0, None, camera=FRONT),
    Clip("skills", "dance_dream_wings", "jumper.dance_dream_wings", 0.0, None, camera=FRONT),
    Clip("skills", "dance_maze", "jumper.dance_maze", 0.0, None, camera=FRONT),
    Clip("skills", "dance_waist", "jumper.dance_waist", 0.0, None, camera=FRONT),
    Clip("skills", "gesture_hello", "jumper.gesture_hello", 0.0, None,
         camera=Camera(azimuth=205.0, follow=False)),
    Clip("skills", "gesture_bow", "jumper.gesture_bow", 0.0, None, camera=FRONT),
    Clip("skills", "gesture_paw", "jumper.gesture_paw", 0.0, None, camera=FRONT),
    Clip("skills", "gesture_salute", "jumper.gesture_salute", 0.0, None, camera=FRONT),
]

#: Built-in scenes meant for watching, plus the jumper-design library maps.
BUILTIN_SCENES = ["studio", "daylight", "beach", "football", "swing", "ice", "rubber"]
DESIGN_MAPS = ["home", "bedroom", "pingpong", "soccer", "plaza", "litter", "warehouse",
               "park-pump-track"]
WIDE = Camera(distance=1.1, azimuth=150.0, elevation=-18.0)
#: The library maps are furnished rooms and parks: at WIDE's low angle a sofa, a table
#: or a bush sat between the camera and the robot (home, pingpong, pump track on
#: 2026-10-25), so maps are framed closer and from higher up.
MAP_CAMERA = Camera(distance=0.8, azimuth=150.0, elevation=-38.0)

SCENES = [
    Clip("scenes", s, "jumper.posture", 1.0, 8.0, scene=s, camera=WIDE, script="tour")
    for s in BUILTIN_SCENES
] + [
    Clip("scenes", f"map-{m}", "jumper.posture", 1.0, 8.0,
         scene=str(DESIGN / "library" / "maps" / f"{m}.map"), camera=MAP_CAMERA,
         script="tour")
    for m in DESIGN_MAPS
]

_ANGLE_BASE = Clip("angles", "", "jumper.dance_brazilian", 0.0, 10.0, scene="daylight")
ANGLES = [
    replace(_ANGLE_BASE, name=n, camera=c)
    for n, c in [
        ("front", Camera(azimuth=180.0, elevation=-10.0, follow=False)),
        ("three_quarter", Camera(azimuth=140.0, elevation=-16.0, follow=False)),
        ("side", Camera(azimuth=90.0, elevation=-8.0, follow=False)),
        ("behind", Camera(azimuth=0.0, elevation=-14.0, follow=False)),
        ("low_hero", Camera(distance=0.45, azimuth=165.0, elevation=-3.0, height=0.08,
                            follow=False)),
        ("top_down", Camera(distance=0.9, azimuth=150.0, elevation=-65.0, follow=False)),
        ("wide", Camera(distance=1.6, azimuth=150.0, elevation=-20.0, follow=False)),
    ]
] + [
    replace(_ANGLE_BASE, name="vertical_9x16", size=VERTICAL,
            camera=Camera(distance=0.8, azimuth=165.0, elevation=-10.0, height=0.09,
                          follow=False)),
    replace(_ANGLE_BASE, name="walk_follow_low", task="jumper.posture", skip=1.0, seconds=5.0,
            script="walk", camera=Camera(distance=0.5, azimuth=200.0, elevation=-5.0)),
]

#: Raw takes for the heist film (`tools/film/shots.py` dresses and shoots them).
FILM = [
    Clip("film", "jump", "jumper.ref_free_jump", 0.0, 3.0, scene="plain"),
    # The vault run: one take down the obstacle course (tools/film/vault_scene.py).
    Clip("film", "course", "jumper.posture", 1.0, 24.0, scene="vault", script="course", start=(0.0, 0.0, 0.0)),
    # The gold: the crab turns to the ingot and the side door beyond it and shoves the
    # ingot out, steering to keep it centred ahead (tools/film/gold_scene.py).
    Clip("film", "push", "jumper.posture", 1.0, 26.0, scene="gold", script="push_gold", start=(0.0, 0.0, 0.0)),
]

CREW_TRIES = 6

ROCKY_TRIES = 3


def _rocky_clips() -> list[Clip]:
    """The third film, UNDERCLAW (tools/film/rocky_scene.py): each training take
    recorded ROCKY_TRIES times as rocky_<take>_<n>; pick_rocky.py keeps the best."""
    sys.path.insert(0, str(FILM_DIR))
    import rocky_scene as R

    takes = [("climb", R.CLIMB_START, 26.0, ()), ("fail", R.FAIL_START, 10.0, ()),
             ("push", R.PUSH_START, 16.0, (("ROCKY_PROPS", "weight"),)),
             ("shuffle", R.SHUFFLE_START, 11.0, ()), ("squats", R.SQUAT_START, 10.0, ())]
    return [Clip("rocky", f"rocky_{name}_{n}", "jumper.posture", 0.0, seconds, scene="rocky",
                 script=f"rocky_{name}", start=start, env=env)
            for name, start, seconds, env in takes for n in range(ROCKY_TRIES)]




STEALTH_TRIES = 4


def _stealth_clips() -> list[Clip]:
    """The fourth film, OPERATION: COOKIE (tools/film/stealth_scene.py): the crab's run
    past the patrolling vacuum, recorded STEALTH_TRIES times; check_stealth.py keeps the best."""
    sys.path.insert(0, str(FILM_DIR))
    import stealth_scene as T

    return [Clip("stealth", f"stealth_{n}", "jumper.posture", 0.0, round(T.END + 3.0, 1), scene="stealth",
                 script="stealth", start=T.START) for n in range(STEALTH_TRIES)]


def _crew_clips() -> list[Clip]:
    """The second film: one take per crab under the bed (tools/film/bedroom_scene.py)."""
    sys.path.insert(0, str(FILM_DIR))
    import bedroom_scene as B

    # crab0-5 clean up; crab6 is the coda, crab 3 again from where crab3 left things.
    # Each is recorded TRIES times as crab<k>_<n>; tools/film/pick_crew.py keeps the
    # best as crab<k>.
    return [Clip("crew", f"crab{k}_{n}", "jumper.posture", 0.0, round(B.end(k) + 2.0, 1), scene="bedroom",
                 script="tidy", start=B.start(k), env=(("CREW", str(k)),))
            for k in range(len(B.PLAN)) for n in range(CREW_TRIES)]


CREW = _crew_clips()
ROCKY = _rocky_clips()
STEALTH = _stealth_clips()

GROUPS = {"skills": SKILLS, "scenes": SCENES, "angles": ANGLES, "film": FILM, "crew": CREW, "rocky": ROCKY, "stealth": STEALTH}


# ── running ───────────────────────────────────────────────────────────────────


def _checkpoint(task: str) -> Path:
    found = sorted((JUMPER / "tasks" / Path(*task.split(".")) / "out" / "example").glob(
        "model_*.pt"))
    if len(found) != 1:
        raise SystemExit(f"error: {task} has {len(found)} example checkpoints, need one")
    return found[0]


def _rates(clip: Clip) -> tuple[float, float, int]:
    """(physics Hz, control Hz, control steps) of `clip`, read from the task config."""
    import tasks

    env_cfg = tasks.load_env_cfg(clip.task, play=True)
    step_dt = env_cfg.sim.mujoco.timestep * env_cfg.decimation
    if clip.seconds is None:
        import numpy as np

        motion = np.load(env_cfg.commands["motion"].motion_file)
        steps = int(motion["joint_pos"].shape[0]) - 1
    else:
        steps = round((clip.skip + clip.seconds) / step_dt)
    return 1.0 / env_cfg.sim.mujoco.timestep, 1.0 / step_dt, steps


def _key(clip: Clip) -> str:
    return f"{clip.group}/{clip.name}"


def _rates_in_child(clips: list[Clip], python: str) -> dict[str, tuple[float, float, int]]:
    """`_rates` for every clip, computed in a short-lived child.

    Reading a task config imports torch and mjlab (about 1 GB). Done in this
    process, that memory sat idle beside every render for the whole run.
    """
    out = subprocess.run([python, __file__, "--emit-rates", *[_key(c) for c in clips]],
                         cwd=JUMPER, check=True, capture_output=True, text=True).stdout
    return {k: tuple(v) for k, v in json.loads(out.strip().splitlines()[-1]).items()}


def _ffmpeg() -> str:
    """ffmpeg on PATH, else the one imageio-ffmpeg (a jumper dependency) ships."""
    import shutil

    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def _free_pct() -> int:
    out = subprocess.run(["sysctl", "-n", "kern.memorystatus_level"],
                         check=False, capture_output=True, text=True).stdout.strip()
    return int(out) if out.isdigit() else 100


_gate = threading.Lock()
MIN_FREE = {"pct": DEFAULT_MIN_FREE_PCT}


def _wait_for_memory() -> None:
    """Hold a render back while the machine is short of memory."""
    with _gate:
        while (free := _free_pct()) < MIN_FREE["pct"]:
            print(f"[memory] {free}% free, waiting for {MIN_FREE['pct']}%", flush=True)
            time.sleep(10)


def _result(clip: Clip, started: float, ok: bool) -> dict:
    return {"group": clip.group, "name": clip.name, "task": clip.task, "scene": clip.scene,
            "seconds_wall": round(time.monotonic() - started, 1), "ok": ok}


def _run_logged(command: list[str], log: Path, cwd: Path, env: dict | None = None) -> bool:
    with log.open("w") as fh:
        done = subprocess.run(["nice", "-n", "10", *command], check=False, cwd=cwd, stdout=fh,
                              stderr=subprocess.STDOUT, env={**os.environ, **(env or {})})
    return done.returncode == 0


def _simulate(clip: Clip, rates: tuple[float, float, int], python: str, stage: str) -> dict:
    """Run the policy. `direct` draws with MuJoCo's own renderer; `poses` records."""
    physics_hz, _, steps = rates
    _wait_for_memory()
    group_dir = OUT / clip.group
    group_dir.mkdir(parents=True, exist_ok=True)
    raw = group_dir / f".{clip.name}.raw.mp4"
    final = group_dir / f"{clip.name}.mp4"
    poses = group_dir / f"{clip.name}.npz"
    log = group_dir / f".{clip.name}.log"
    cam = clip.camera
    play = [
        str(PLAY), "--task", clip.task, "--checkpoint", str(_checkpoint(clip.task)),
        "--backend", "native", "--device", "cpu", "--num_envs", "1",
        "--headless", "--no-obs-noise", "--scene", clip.scene,
        "--physics-hz", f"{physics_hz:g}", "--steps", str(steps),
        "--video", str(raw), "--video-fps", str(FPS),
        "--video-width", str(clip.size[0]), "--video-height", str(clip.size[1]),
        "--video-distance", f"{cam.distance:g}", "--video-azimuth", f"{cam.azimuth:g}",
        "--video-elevation", f"{cam.elevation:g}",
    ]
    if not cam.follow:
        play += ["--no-video-follow", "--video-lookat-height", f"{cam.height:g}"]
    if clip.script is not None:
        play += ["--command-script", f"{COMMANDS}:{clip.script}"]
    play += list(clip.extra)
    env = dict(SINGLE_THREAD)
    env.update(dict(clip.env))
    if clip.start is not None:
        env["FIXED_START"] = ",".join(f"{v:g}" for v in clip.start)
    own_scene = FILM_DIR / f"{clip.scene}_scene.py"
    if own_scene.exists():
        env["SCENE_MODULE"] = str(own_scene)
        env["FEED_PROPS"] = ",".join(PROPS_FED.get(clip.scene, ()))
    if stage == "poses":
        command = [python, str(RECORDER), *play]
        env["POSES_OUT"] = str(poses)
    else:
        command = [python, *play]
    started = time.monotonic()
    ok = _run_logged(command, log, JUMPER, env)
    result = _result(clip, started, ok)
    if not ok:
        result["error"] = log.read_text()[-1500:]
        return result
    if stage == "poses":
        raw.unlink(missing_ok=True)  # the recorder's frames are blank by design
        result["file"] = str(poses.relative_to(ROOT))
    else:
        # Trim the settling and re-encode to H.264 that every browser and phone plays.
        cut = ["-ss", f"{clip.skip:g}"]
        if clip.seconds is not None:
            cut += ["-t", f"{clip.seconds:g}"]
        subprocess.run(["nice", "-n", "10", _ffmpeg(), "-y", "-loglevel", "error",
                        "-threads", "2", *cut, "-i", str(raw), "-c:v", "libx264", "-crf", "20",
                        "-preset", "medium", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                        "-an", str(final)], check=True)
        raw.unlink()
        result["file"] = str(final.relative_to(ROOT))
    log.unlink()
    result["mb"] = round((ROOT / result["file"]).stat().st_size / 1e6, 2)
    return result


def _draw(clip: Clip, python: str) -> dict:
    """Draw a clip from poses recorded on the render host."""
    group_dir = OUT / clip.group
    final = group_dir / f"{clip.name}.mp4"
    log = group_dir / f".{clip.name}.draw.log"
    command = [python, str(DRAWER), str(group_dir / f"{clip.name}.npz"), str(final),
               "--fps", str(FPS), "--skip", f"{clip.skip:g}"]
    if clip.seconds is not None:
        command += ["--seconds", f"{clip.seconds:g}"]
    started = time.monotonic()
    ok = _run_logged(command, log, ROOT, SINGLE_THREAD)
    result = _result(clip, started, ok)
    if not ok:
        result["error"] = log.read_text()[-1500:]
        return result
    log.unlink()
    result["file"] = str(final.relative_to(ROOT))
    result["mb"] = round(final.stat().st_size / 1e6, 2)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--only", nargs="+", metavar="GROUP_OR_CLIP",
                    help="groups (skills, scenes, angles) or clip names")
    ap.add_argument("--budget-gb", type=float, default=DEFAULT_BUDGET_GB,
                    help=f"memory for renders; one takes about {RENDER_GB} GB")
    ap.add_argument("--min-free-pct", type=int, default=DEFAULT_MIN_FREE_PCT,
                    help="start no render while macOS reports less free memory than this")
    ap.add_argument("--force", action="store_true", help="redraw clips that already exist")
    ap.add_argument("--stage", choices=["direct", "poses", "draw"], default="direct",
                    help="direct: simulate and draw here; poses: simulate and record poses "
                    "(a host without a display); draw: draw recorded poses (light, no torch)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--emit-rates", nargs="+", help=argparse.SUPPRESS)
    args = ap.parse_args()

    clips = [c for g in GROUPS.values() for c in g]
    if args.emit_rates:
        sys.path.insert(0, str(JUMPER))
        by_key = {_key(c): c for c in clips}
        print(json.dumps({k: _rates(by_key[k]) for k in args.emit_rates}))
        return 0
    if args.only:
        clips = [c for c in clips if c.group in args.only or c.name in args.only]
    if args.list:
        for c in clips:
            print(f"{c.group:<7} {c.name:<20} {c.task:<26} {Path(c.scene).stem}")
        return 0

    suffix = ".npz" if args.stage == "poses" else ".mp4"
    if not args.force:
        clips = [c for c in clips if not (OUT / c.group / f"{c.name}{suffix}").exists()]
    if args.stage == "draw":
        clips = [c for c in clips if (OUT / c.group / f"{c.name}.npz").exists()]
    if not clips:
        print("nothing to draw; --force redraws existing clips")
        return 0
    python = str(JUMPER / ".venv" / "bin" / "python")
    results = []
    MIN_FREE["pct"] = args.min_free_pct
    per_job = DRAW_GB if args.stage == "draw" else RENDER_GB
    jobs = max(1, min(len(clips), int(args.budget_gb // per_job)))
    print(f"[plan] {args.stage}: {len(clips)} clips, {jobs} at once "
          f"({args.budget_gb:g} GB budget)", flush=True)
    if args.stage == "draw":
        work = lambda c: _draw(c, python)
    else:
        rates = _rates_in_child(clips, python)
        work = lambda c: _simulate(c, rates[_key(c)], python, args.stage)
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for r in pool.map(work, clips):
            status = f"{r['mb']} MB" if r["ok"] else "FAILED"
            print(f"[{r['group']}/{r['name']}] {status} in {r['seconds_wall']} s", flush=True)
            results.append(r)
    index = OUT / "index.json"
    previous = json.loads(index.read_text()) if index.exists() else []
    merged = {(r["group"], r["name"]): r for r in previous + results}
    index.write_text(json.dumps(list(merged.values()), indent=2, ensure_ascii=False))
    failed = [r for r in results if not r["ok"]]
    for r in failed:
        print(f"\n--- {r['group']}/{r['name']} failed ---\n{r['error']}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
