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


# ── UNDERCLAW, the training montage (jumper.posture in tools/film/rocky_scene.py) ──
# Positions are the bedroom's; each script reads the crab's pose and steers it.

_ROCKY: dict = {}


def _rocky():
    import importlib.util
    from pathlib import Path

    if "m" not in _ROCKY:
        path = Path(__file__).with_name("film") / "rocky_scene.py"
        spec = importlib.util.spec_from_file_location("_rocky_scene", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _ROCKY["m"] = module
    return _ROCKY["m"]


def _pose():
    import builtins

    return getattr(builtins, "_crab_pose", None)


def _steer(pose, vwx, vwy, heading, limit=0.35, turn_gain=2.0):
    x, y, yaw = pose
    vx = math.cos(yaw) * vwx + math.sin(yaw) * vwy
    vy = -math.sin(yaw) * vwx + math.cos(yaw) * vwy
    err = math.atan2(math.sin(heading - yaw), math.cos(heading - yaw))
    return (vx, max(-limit, min(limit, vy)), max(-1.4, min(1.4, turn_gain * err)))


def rocky_climb(t: float) -> dict:
    """Day 30: up the three ramps to the summit (0.28 m/s commanded, about 0.15 made
    good on the ramps), body along the
    stair; on top it stops and turns to face the room (south)."""
    pose = _pose()
    if pose is None or t < 0.6:
        return {"twist": (0.0, 0.0, 0.0), "posture": _NEUTRAL}
    m = _rocky()
    x, y, yaw = pose
    tx, ty, _ = m.SUMMIT_TOP
    path = [(m.CLIMB_START[0], m.STAIR_Y), (tx, ty)]
    (gx, gy), along, total = _pursuit(pose, path, lookahead=0.20)
    left = total - along
    if left > 0.03 and "top" not in _ROCKY:
        go = 0.28 * _ramp(t, 0.6, 1.4) * min(1.0, left / 0.15)
        dx, dy = gx - x, gy - y
        n = math.hypot(dx, dy) or 1.0
        return {"twist": _steer(pose, go * dx / n, go * dy / n, 0.0), "posture": _NEUTRAL}
    _ROCKY["top"] = True
    hold = (1.2 * (tx - x), 1.2 * (ty - y))
    return {"twist": _steer(pose, *hold, -math.pi / 2, turn_gain=1.6), "posture": _NEUTRAL}


def rocky_fail(t: float) -> dict:
    """Day 1: straight at the summit's 12 cm south face, keeps trying for 3 s, backs
    off and turns away."""
    pose = _pose()
    if pose is None or t < 0.6:
        return {"twist": (0.0, 0.0, 0.0), "posture": _NEUTRAL}
    north = math.pi / 2
    if t < 5.5:  # at the wall and against it
        return {"twist": _steer(pose, 0.0, 0.28 * _ramp(t, 0.6, 1.2), north), "posture": _NEUTRAL}
    if t < 7.0:  # back off
        return {"twist": _steer(pose, 0.0, -0.18, north), "posture": _NEUTRAL}
    # turn away, a little crouched: dejected
    return {"twist": _steer(pose, 0.0, 0.0, -math.pi / 2, turn_gain=1.0),
            "posture": (0.0, 0.0, 0.0, (0.07, 0.6 * _ramp(t, 7.0, 8.0)))}


def rocky_squats(t: float) -> dict:
    """Squats: full crouch (0.07 m) and up, one rep every 1.4 s, standing still."""
    if t < 0.8:
        return {"twist": (0.0, 0.0, 0.0), "posture": _NEUTRAL}
    share = 0.5 - 0.5 * math.cos(2 * math.pi * (t - 0.8) / 1.4)
    return {"twist": (0.0, 0.0, 0.0), "posture": (0.0, 0.0, 0.0, (0.07, share))}


def rocky_shuffle(t: float) -> dict:
    """Agility drill: sideways between two marks 0.6 m apart, facing the room, a
    change of direction every 1.5 s."""
    pose = _pose()
    if pose is None or t < 0.6:
        return {"twist": (0.0, 0.0, 0.0), "posture": _NEUTRAL}
    m = _rocky()
    x0, y0, _ = m.SHUFFLE_START
    leg = int((t - 0.6) / 1.5)
    tx = x0 + (0.6 if leg % 2 == 0 else 0.0)
    x, y, _ = pose
    vwx = max(-0.4, min(0.4, 2.5 * (tx - x)))
    return {"twist": _steer(pose, vwx, 1.5 * (y0 - y), -math.pi / 2, limit=0.4), "posture": _NEUTRAL}


def rocky_push(t: float) -> dict:
    """The heavy book: walk into it and keep driving, slowly, the book centred in front
    (the bedroom's squared claws, 8 degrees left)."""
    import builtins

    pose = _pose()
    book = getattr(builtins, "_crab_props", {}).get("weight")
    if pose is None or book is None or t < 0.6:
        return {"twist": (0.0, 0.0, 0.0), "posture": _NEUTRAL}
    x, y, yaw = pose
    go = 0.16 * _ramp(t, 0.6, 1.4)
    vwy = 2.0 * (book[1] - y)
    return {"twist": _steer(pose, go, max(-0.1, min(0.1, vwy)), 0.14), "posture": _NEUTRAL}


# ── OPERATION: COOKIE (jumper.posture in tools/film/stealth_scene.py) ─────────────

_STEALTH: dict = {}


def stealth(t: float) -> dict:
    """Keep to the timetable planned against the vacuum's patrol
    (`stealth_scene.reference`): feed-forward on the path plus a pull back onto it.
    Crouched (0.07 m) while sneaking and hiding. Pushing the cookie home, it keeps
    square behind it (the bedroom's 8-degree claw squaring) within 6 cm of its line."""
    import builtins
    import importlib.util
    from pathlib import Path

    pose = getattr(builtins, "_crab_pose", None)
    props = getattr(builtins, "_crab_props", {})
    if pose is None or t < 0.5:
        return {"twist": (0.0, 0.0, 0.0), "posture": _NEUTRAL}
    if "m" not in _STEALTH:
        path = Path(__file__).with_name("film") / "stealth_scene.py"
        spec = importlib.util.spec_from_file_location("_stealth_scene", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _STEALTH["m"] = module
        _STEALTH["low"] = 0.0
    m = _STEALTH["m"]
    x, y, yaw = pose
    rx, ry, rh, phase = m.reference(t)
    ax, ay, _, _ = m.reference(t + 0.2)
    vwx = (ax - rx) / 0.2 + 1.8 * (rx - x)
    vwy = (ay - ry) / 0.2 + 1.8 * (ry - y)
    heading = rh
    if phase == "push":
        heading = rh + 0.14
        cookie = props.get("cookie")
        if cookie is not None and 0.0 < cookie[1] - y < 0.45:
            want = min(max(cookie[0], m.COOKIE_AT[0] - 0.06), m.COOKIE_AT[0] + 0.06)
            vwx = 1.8 * (want - x)
    norm = math.hypot(vwx, vwy)
    if norm > 0.5:
        vwx, vwy = vwx * 0.5 / norm, vwy * 0.5 / norm
    # crouch eases in and out over half a second
    target = 1.0 if phase in m.CROUCH else 0.0
    _STEALTH["low"] += max(-0.04, min(0.04, target - _STEALTH["low"]))
    return {"twist": _steer(pose, vwx, vwy, heading, limit=0.35, turn_gain=2.5),
            "posture": (0.0, 0.0, 0.0, (0.07, _STEALTH["low"]))}
