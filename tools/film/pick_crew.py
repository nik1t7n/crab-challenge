"""Keep each bedroom crab's best take: of the takes `crab<k>_<n>` recorded for crab k,
the one that kept closest to its planned path and left its things where they belong,
copied to `crab<k>`.

    upstream/jumper/.venv/bin/python tools/film/pick_crew.py            # crabs 0-5
    upstream/jumper/.venv/bin/python tools/film/pick_crew.py 6          # the coda

Pushing loose things with walking legs is noisy: the same plan and controller put
every thing under the bed in one recording and lost a shirt in the next, so each crab
is recorded several times, the way a scene is shot in several takes. A take counts
when both its things end fully under the furniture and inside the crab's own lane
(where no other crab parks or walks); among those, the one that kept closest to its
path wins. The pick is measured, never chosen by eye; check_crew.py then measures
the six chosen takes together.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bedroom_scene as B
from stage import RENDERS, TAKE_FPS, Take

#: A thing must end this far inside its lane's middle (m): a neighbour parks 0.66 m
#: away and is 0.20 m wide, a shirt 0.115 m.
LANE_HALF = 0.30
EDGE = 0.03


def score(k: int, take: Take) -> tuple[bool, float, str]:
    d = take.data
    t_end = (take.frames - 1) / TAKE_FPS
    lag = []
    for f in range(take.frames):
        take.pose(f / TAKE_FPS)
        lag.append(np.linalg.norm(d.xpos[take.root][:2] - np.array(B.reference(k, f / TAKE_FPS)[:2])))
    take.pose(t_end)
    lane = B.reference(k, B.SWEEPS[k][1])[0]
    notes, ok = [], True
    for i, (kind, *_rest) in enumerate(B.items(k)):
        body = take.body(f"item{i}/item")
        p = d.xpos[body].copy()
        if k == B.SNEAK and i == 0:  # crab 3's parked shirt: the coda must not move it
            take.pose(0.0)
            moved = float(np.linalg.norm(d.xpos[body][:2] - p[:2]))
            take.pose(t_end)
            ok &= moved < 0.05
            notes.append(f"parked {kind} moved {moved * 100:.0f} cm")
            continue
        under = p[1] - B.KINDS[kind][0][1] - B.BED[2]
        off = abs(p[0] - lane)
        good = under > EDGE and off < LANE_HALF
        ok &= good
        notes.append(f"{kind} {under * 100:+.0f} cm in, {off * 100:.0f} cm off lane")
    worst = float(max(lag))
    return ok, worst, "; ".join(notes) + f"; path worst {worst * 100:.1f} cm"


def main() -> int:
    crew = [int(a) for a in sys.argv[1:]] or list(range(len(B.LANES)))
    folder = RENDERS / "crew"
    bad = 0
    for k in crew:
        tries = sorted(folder.glob(f"crab{k}_*.npz"))
        rated = []
        for npz in tries:
            ok, worst, note = score(k, Take(npz.stem, group="crew"))
            rated.append((not ok, worst, npz, note))
            print(f"  {npz.stem}: {'ok ' if ok else 'bad'} {note}")
        if not rated:
            print(f"crab{k}: no takes")
            bad += 1
            continue
        failed, _, best, _ = min(rated, key=lambda r: (r[0], r[1]))
        for ext in (".npz", ".mjb"):
            shutil.copyfile(best.with_suffix(ext), folder / f"crab{k}{ext}")
        print(f"crab{k} <- {best.stem}{'  (no take passed)' if failed else ''}")
        bad += failed
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
