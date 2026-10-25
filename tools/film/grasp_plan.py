"""Plan a real grasp of the gold bar with jumper.five_foot's carried claw.

    upstream/jumper/.venv/bin/python tools/film/grasp_plan.py

The claw's own geometry comes from upstream (`tasks/jumper/five_foot/mdp/grasp.py`):
the anvil (the point on the fixed jaw the moving jaw closes onto), the closing
direction and the level direction into the mouth, all in the palm's frame. A prop
is held the way upstream seats one: its near face `SEAT_CLEARANCE` off the anvil on
the moving jaw's side and `HOLD_DEPTH` into the mouth.

Solved here, with the base where the recorded approach stops:
  * GRASP: arm angles that put the seat on the floor-standing bar with the jaws
    closing level, and the bar's position and yaw that match (its 40 mm side across
    the jaws);
  * PRE: the same claw backed out along the mouth's inward direction, so the bar is
    outside the jaws and slides in as the arm goes from PRE to GRASP;
  * LIFT: the seat raised with the bar, jaws still level.
Then the bar's clearance from every robot part over the whole approach is checked.
Prints the constants `tools/commands.py` uses.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import mujoco
import numpy as np
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stage import ARM, Take

BAR_HALF = np.array([0.020, 0.030, 0.050])  # the soap bar: 40 x 60 x 100 mm
BACK_OFF = 0.07
OVER = 0.13   # above the bar's 100 mm top on the way over
LIFT = 0.06


def main(pedestal: float = 0.0) -> int:
    from tasks.jumper.five_foot.mdp.grasp import (
        HOLD_DEPTH,
        SEAT_CLEARANCE,
        _closing_in_palm,
        _inward_in_palm,
        _mouth_in_palm,
    )

    take = Take("approach")
    m, d = take.model, take.data
    anvil_p, closing_p, inward_p = _mouth_in_palm(m), _closing_in_palm(m), _inward_in_palm(m)
    palm = take.body("robot/LF_palm_link")
    adr = [take.joint_qpos(j) for j in ARM]
    rng = [tuple(m.jnt_range[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, j)]) for j in ARM]
    T = 3.4  # the base has stopped
    take.pose(T)
    base_q = d.qpos.copy()
    stow = base_q[adr].copy()

    def frame(q):
        d.qpos[:] = base_q
        d.qpos[adr] = q
        mujoco.mj_kinematics(m, d)
        R = d.xmat[palm].reshape(3, 3)
        anvil = d.xpos[palm] + R @ anvil_p
        closing, inward = R @ closing_p, R @ inward_p
        seat = anvil + closing * (SEAT_CLEARANCE + BAR_HALF[0]) + inward * HOLD_DEPTH
        return seat, closing, inward

    # GRASP: seat at bar height, jaws closing level, inward level, as low-effort as possible.
    def cost_grasp(q):
        seat, closing, inward = frame(q)
        return (50 * (seat[2] - pedestal - BAR_HALF[2]) ** 2 + 2 * closing[2] ** 2 + 2 * inward[2] ** 2
                + 1e-3 * np.sum((q - stow) ** 2))

    def solve_to(target, q0, closing_ref):
        def cost(q):
            sp, c, _ = frame(q)
            return 200 * np.sum((sp - target) ** 2) + 2 * np.sum((c - closing_ref) ** 2) + 1e-4 * np.sum((q - q0) ** 2)
        return minimize(cost, q0, bounds=rng, method="L-BFGS-B").x

    bar_body = take.body("soap/soap")
    bar_geom = next(g for g in range(m.ngeom) if m.geom_bodyid[g] == bar_body)
    bar_adr = m.jnt_qposadr[m.body_jntadr[bar_body]]
    robot = [g for g in take.robot_geoms() if m.geom_contype[g] or m.geom_conaffinity[g]]
    walk_frames = []
    for t in np.arange(0, 3.6, 0.08):
        take.pose(t)
        walk_frames.append(d.qpos.copy())

    def clearance(qpos, bar_q):
        d.qpos[:] = qpos
        d.qpos[bar_adr:bar_adr + 7] = bar_q
        mujoco.mj_kinematics(m, d)
        return min(mujoco.mj_geomDistance(m, d, bar_geom, g, 0.2, None) for g in robot)

    def arm_path(a, b, n=16):
        out = []
        for w in np.linspace(0, 1, n):
            q = base_q.copy()
            q[adr] = a + w * (b - a)
            out.append(q)
        return out

    rnd = np.random.default_rng(7)
    rejected = {"pose": 0, "walk": 0}
    near = []
    plans = []
    for k in range(60):
        start = rnd.uniform([a for a, _ in rng], [b for _, b in rng])
        r = minimize(cost_grasp, start, bounds=rng, method="L-BFGS-B")
        grasp = r.x
        seat, closing, inward = frame(grasp)
        if abs(seat[2] - pedestal - BAR_HALF[2]) > 0.015 or abs(closing[2]) > 0.15:
            rejected["pose"] += 1
            continue
        bar = np.array([seat[0], seat[1], pedestal + BAR_HALF[2]])
        yaw = math.degrees(math.atan2(closing[1], closing[0]))
        h = math.radians(yaw) / 2
        bar_q = np.array([*bar, math.cos(h), 0, 0, math.sin(h)])
        # the bar, and the pedestal under it (the bar's own shape moved down onto it)
        low = bar_q.copy()
        low[2] -= pedestal
        walk = min(min(clearance(q, bar_q), clearance(q, low) if pedestal else 1.0) for q in walk_frames)
        if walk < 0.012:
            rejected["walk"] += 1
            near.append((round(walk * 1000, 1), np.round(bar[:2], 3).tolist()))
            continue
        pre = solve_to(seat - inward * BACK_OFF, grasp, closing)
        over = solve_to(seat - inward * BACK_OFF + np.array([0, 0, OVER]), grasp, closing)
        lift = solve_to(seat + np.array([0, 0, LIFT]), grasp, closing)
        path = arm_path(stow, over) + arm_path(over, pre)
        reach_clear = min(clearance(q, bar_q) for q in path)
        insert = arm_path(pre, grasp)
        # the insertion may touch only in its last quarter, as the bar seats
        early = min(clearance(q, bar_q) for q in insert[: len(insert) * 3 // 4])
        plans.append((min(walk, reach_clear, early), walk, reach_clear, early, bar, yaw, over, pre, grasp, lift,
                      closing, inward))
    if not plans:
        print("no feasible grasp found", rejected, sorted(near)[-6:])
        return 1
    plans.sort(key=lambda p: -p[0])
    _score, walk, reach_clear, early, bar, yaw, over, pre, grasp, lift, closing, inward = plans[0]
    print(f"{len(plans)} feasible of 60 starts")

    take.pose(T)
    print(f"base at {d.xpos[take.root].round(3)}")
    print(f"PEDESTAL = {pedestal:.3f}")
    print(f"BAR = ({bar[0]:.4f}, {bar[1]:.4f}, {bar[2]:.4f})  yaw {yaw:.2f} deg")
    print(f"closing {closing.round(3)}  inward {inward.round(3)}")
    print(f"ARM_OVER = {tuple(float(v) for v in np.round(over, 4))}")
    print(f"ARM_PRE = {tuple(float(v) for v in np.round(pre, 4))}")
    print(f"ARM_GRASP = {tuple(float(v) for v in np.round(grasp, 4))}")
    print(f"ARM_LIFT = {tuple(float(v) for v in np.round(lift, 4))}")
    print(f"clearance: walking up {walk * 1000:.1f} mm, arm over and down {reach_clear * 1000:.1f} mm, "
          f"first 3/4 of the insertion {early * 1000:.1f} mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(float(sys.argv[1]) if len(sys.argv) > 1 else 0.0))
