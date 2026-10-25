"""Command scripts for `play.py --command-script tools/commands.py:<name>`.

Each is `(seconds since the clip began) -> {command term: values}`. `play.py` loads
this file by path without registering it as a module, so it stays plain functions
and the standard library (a dataclass here fails to build under that loader).
"""

import itertools
import math


def _ramp(t: float, t0: float, t1: float) -> float:
    x = min(1.0, max(0.0, (t - t0) / (t1 - t0)))
    return x * x * (3.0 - 2.0 * x)


_NEUTRAL = (0.0, 0.0, 0.0, float("nan"))


def walk(t: float) -> dict:
    """jumper.posture straight ahead at 0.5 m/s."""
    return {"twist": (0.5 * _ramp(t, 0.3, 1.3), 0.0, 0.0), "posture": _NEUTRAL}


def tour(t: float) -> dict:
    """jumper.posture: forward, a turn, a crab-walk sideways, a turn back."""
    vx = 0.4 * (_ramp(t, 0.5, 1.2) - _ramp(t, 3.0, 3.5))
    yaw = 1.2 * (_ramp(t, 3.0, 3.4) - _ramp(t, 4.6, 5.0))
    vy = 0.3 * (_ramp(t, 5.0, 5.4) - _ramp(t, 7.0, 7.4))
    return {"twist": (vx, vy, yaw), "posture": _NEUTRAL}


def pose(t: float) -> dict:
    """jumper.posture standing: pitch, roll, twist, then height, each back to rest."""
    def bump(t0: float) -> float:
        return _ramp(t, t0, t0 + 0.4) - _ramp(t, t0 + 1.0, t0 + 1.4)

    return {
        "twist": (0.0, 0.0, 0.0),
        "posture": (0.45 * bump(3.0), 0.30 * bump(0.2), 0.22 * bump(1.6), (0.14, bump(4.4))),
    }


def claw(t: float) -> dict:
    """jumper.five_foot forward at 0.35 m/s with the claw up."""
    return {"twist": (0.35 * _ramp(t, 0.3, 1.3), 0.0, 0.0)}


def spin(t: float) -> dict:
    """jumper.posture turning on the spot, for the scene sampler's showcase."""
    return {"twist": (0.0, 0.0, 1.0 * _ramp(t, 0.5, 1.0)), "posture": _NEUTRAL}


# ── the heist film ────────────────────────────────────────────────────────────







#: The vault run's path (tools/film/vault_scene.py): straight over the ramp and the
#: platform, a weave around the pillars, through the crate, along the laser gate.
COURSE_PATH = [(0.0, 0.0), (1.75, 0.0), (1.97, 0.30), (2.40, -0.30), (2.86, 0.30), (3.15, 0.0),
               (4.55, 0.0)]
COURSE_SPEED = 0.25
CROUCH_FROM_X, RISE_AT_X = (3.05, 3.35), (4.30, 4.45)


def _pursuit(pose, path, lookahead=0.22):
    """Pure pursuit: the point `lookahead` metres along the path past the nearest
    point to the robot, and how far along the whole path that nearest point is."""
    x, y = pose[0], pose[1]
    best, along, run = None, 0.0, 0.0
    for (ax, ay), (bx, by) in itertools.pairwise(path):
        dx, dy = bx - ax, by - ay
        seg = math.hypot(dx, dy)
        u = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (seg * seg)))
        px, py = ax + u * dx, ay + u * dy
        dist = math.hypot(x - px, y - py)
        if best is None or dist < best:
            best, along = dist, run + u * seg
        run += seg
    remaining = along + lookahead
    for (ax, ay), (bx, by) in itertools.pairwise(path):
        seg = math.hypot(bx - ax, by - ay)
        if remaining <= seg:
            u = remaining / seg
            return (ax + u * (bx - ax), ay + u * (by - ay)), along, run
        remaining -= seg
    return path[-1], along, run


def course(t: float) -> dict:
    """jumper.posture down the vault, steered by pure pursuit along `COURSE_PATH`.

    The command keeps the body pointing down the room (+x) and slides it sideways
    round the bends, the way a crab goes. The crouch is set by position, not time:
    full height down from x 3.35 until x 4.30, so the laser gate (x 3.55-3.95) is
    always met crouched. Without a pose (a plain replay) it stands still.
    """
    import builtins

    pose = getattr(builtins, "_crab_pose", None)
    if pose is None:
        return {"twist": (0.0, 0.0, 0.0), "posture": _NEUTRAL}
    x, y, yaw = pose
    (gx, gy), along, total = _pursuit(pose, COURSE_PATH)
    go = _ramp(t, 0.5, 1.2) * (1.0 - _ramp(along, total - 0.20, total - 0.02))
    dx, dy = gx - x, gy - y
    norm = math.hypot(dx, dy) or 1.0
    vwx, vwy = COURSE_SPEED * go * dx / norm, COURSE_SPEED * go * dy / norm
    vx = math.cos(yaw) * vwx + math.sin(yaw) * vwy
    vy = -math.sin(yaw) * vwx + math.cos(yaw) * vwy
    down = _ramp(x, *CROUCH_FROM_X) * (1.0 - _ramp(x, *RISE_AT_X))
    vx *= 1.0 - 0.3 * down
    return {"twist": (vx, max(-0.3, min(0.3, vy)), -1.5 * yaw), "posture": (0.0, 0.0, 0.0, (0.07, down))}


# ── the gold (jumper.posture in tools/film/gold_scene.py, start at the origin facing +x) ──

PUSH_HEADING = math.pi / 2   # toward the ingot and the side door beyond it
PUSH_SPEED = 0.25


def push_gold(t: float) -> dict:
    """Turn left to face the ingot, then walk at it and keep walking: the ingot goes
    ahead of the crab out of the door. The crab slides sideways to keep the ingot
    centred in front of it, the way a bulldozer is steered."""
    import builtins

    pose = getattr(builtins, "_crab_pose", None)
    gold = getattr(builtins, "_crab_props", {}).get("gold")
    if pose is None or gold is None:
        return {"twist": (0.0, 0.0, 0.0), "posture": _NEUTRAL}
    x, y, yaw = pose
    err = math.atan2(math.sin(PUSH_HEADING - yaw), math.cos(PUSH_HEADING - yaw))
    turn = max(-0.8, min(0.8, 2.0 * err)) * _ramp(t, 0.5, 0.9)
    # how far the ingot lies to the crab's left of its centre line (body frame)
    left = -math.sin(yaw) * (gold[0] - x) + math.cos(yaw) * (gold[1] - y)
    go = PUSH_SPEED * _ramp(t, 2.6, 3.2) * max(0.0, math.cos(err))
    return {"twist": (go, max(-0.12, min(0.12, 1.5 * left)) * _ramp(t, 2.6, 3.2), turn),
            "posture": _NEUTRAL}


# ── the bedroom (jumper.posture in tools/film/bedroom_scene.py, CREW=<n>) ─────────

_TIDY: dict = {}


def _crew():
    import importlib.util
    import os
    from pathlib import Path

    path = Path(__file__).with_name("film") / "bedroom_scene.py"
    spec = importlib.util.spec_from_file_location("_bedroom_scene", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, int(os.environ.get("CREW", "0"))


def _wrap(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))


def _body(pose, vwx, vwy):
    _x, _y, yaw = pose
    return math.cos(yaw) * vwx + math.sin(yaw) * vwy, -math.sin(yaw) * vwx + math.cos(yaw) * vwy


def tidy(t: float) -> dict:
    """One crab's part of the planned clean-up (`bedroom_scene.plan`): track its
    time-indexed path, feed-forward on the path's own velocity plus a pull back onto
    it, so it is where the plan says when the plan says. The six takes never feel
    each other; keeping to the plan in time is what keeps them apart. Sweeping up
    its lane, it keeps square behind the thing it touches (within DRIFT of the lane),
    its claws squared to the lane (`bedroom_scene.SQUARE`). Aiming its heading at the lane's end like a cue
    made it pivot into its own train and lost four of twelve things; a wider DRIFT
    (12 cm) let neighbours crowd each other. Pushing loose things with walking legs
    stays noisy from take to take, so each crab is recorded several times and the
    best take kept (`tools/film/pick_crew.py`). Steered by the crab's and its
    things' positions; the walking is jumper.posture's."""
    import builtins

    pose = getattr(builtins, "_crab_pose", None)
    props = getattr(builtins, "_crab_props", {})
    rest = {"twist": (0.0, 0.0, 0.0), "posture": _NEUTRAL}
    if pose is None or t < 0.5:
        return rest
    st = _TIDY
    if not st:
        st["module"], st["k"] = _crew()
    module, k = st["module"], st["k"]
    x, y, yaw = pose
    rx, ry, rh = module.reference(k, t)
    ax, ay, _ = module.reference(k, t + 0.2)
    vwx = (ax - rx) / 0.2 + 1.8 * (rx - x)
    vwy = (ay - ry) / 0.2 + 1.8 * (ry - y)
    heading = rh
    if module.phase(k, t) == "sweep":
        heading = rh + module.SQUARE
        ahead = [p for p in props.values() if 0.0 < p[1] - y < 0.45 and abs(p[0] - x) < 0.30]
        if ahead:  # stay square behind the one it touches; the rest of the train follows it
            lead = min(ahead, key=lambda p: p[1])
            lane = module.reference(k, module.SWEEPS[k][1])[0]
            want = min(max(lead[0], lane - module.DRIFT), lane + module.DRIFT)
            vwx = 1.8 * (want - x)
    norm = math.hypot(vwx, vwy)
    if norm > 0.6:
        vwx, vwy = vwx * 0.6 / norm, vwy * 0.6 / norm
    if module.phase(k, t) == "park" and t > module.end(k) and math.hypot(rx - x, ry - y) < 0.03:
        vwx = vwy = 0.0
    vx, vy = _body(pose, vwx, vwy)
    turn = max(-1.6, min(1.6, 2.5 * _wrap(heading - yaw)))
    return {"twist": (vx, max(-0.35, min(0.35, vy)), turn), "posture": _NEUTRAL}
