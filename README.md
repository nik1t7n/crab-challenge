# Crab Challenge

Our entry for the KingKong **Crab Robot Open-source Challenge** (Jumper, 2026-09-30 to
2026-11-30, round 1 closes 2026-10-30). Contest page:
https://beunlimited.me/en/events/crab-robot-challenge-2026

## The films

Two short films of the Jumper crab robot. Every step, crouch, jump and shove in them is
KingKong's own trained RL policy running in MuJoCo physics; nothing is keyframed, and
props move only because a crab pushes them.

**ROOM: CLEAN\*** (44 s). Mom texts: home in 30 seconds. Six crabs come out from under the
bed and shove the whole mess under it before the countdown hits zero. Six separate
simulations follow one time-planned choreography (tools/film/bedroom_scene.py), each crab
recorded several times and the best take picked by measurement (tools/film/pick_crew.py);
tools/film/check_crew.py proves no two crabs ever overlap and all 12 things end under the
bed. Drawn in Blender with procedural materials and simulated cloth
(tools/film/blend_bake.py, tools/film/blender/), sound made from the simulation's own joint
speeds and contacts (tools/film/bedroom_foley.py), cut in Remotion (film/src/Bedroom.tsx).

**MISSION: CLAWSSIBLE** (52 s). A heist: the crab climbs, weaves, ducks under lasers with
12.5 mm to spare, jumps a sweeping beam and pushes a gold ingot out of the vault
(tools/film/vault_scene.py, shots.py, foley.py, film/src/Heist.tsx).

How we got there, with the numbers and the dead ends: docs/JOURNAL.md (in Russian).

## Layout

```
upstream/jumper/          KingKongRobotics/jumper, own .venv (gitignored)
upstream/jumper-design/   KingKongRobotics/jumper-design, own .venv, Git LFS (gitignored)
tools/render_gallery.py   renders every committed policy across scenes and camera angles
renders/<group>/*.mp4     output of the gallery (regenerated, not committed)
```

`jumper-design` is a sibling checkout of `jumper` on purpose: its docs forbid nesting it
inside `jumper` or adding it as a submodule.

## Setup (macOS, Apple Silicon, no NVIDIA)

```bash
mkdir upstream && cd upstream
git clone https://github.com/KingKongRobotics/jumper.git
git clone https://github.com/KingKongRobotics/jumper-design.git
cd jumper && uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python torch torchvision     # CPU build
uv pip install --python .venv/bin/python -e ".[dev]"           # editable is mandatory
cd ../jumper-design && git lfs pull && uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[sim,dev]"
```

## Rendering what already exists

```bash
upstream/jumper/.venv/bin/python tools/render_gallery.py --list
upstream/jumper/.venv/bin/python tools/render_gallery.py --only skills
upstream/jumper/.venv/bin/python tools/render_gallery.py            # everything
```

Three groups: `skills` (each of the 13 committed checkpoints in the studio), `scenes`
(one walking tour in every built-in viewing scene and in the jumper-design library maps),
`angles` (one dance from seven camera positions, plus a 9:16 vertical and a low follow shot).

## Decisions

- **Render committed checkpoints, train nothing for round 1.** `tasks/*/out/example/` holds
  13 trained policies (walk, posture, five-foot claw, two jumps, five dances, four gestures);
  the machine has no NVIDIA GPU, so training is a Colab job for later rounds.
- **One recorder.** Every clip goes through upstream `scripts/play.py --video`, the same
  recorder upstream's own README media uses (`tools/readme_media.py`), so what we see is what
  the upstream pipeline produces. Our script only widens the scene and camera matrix.
- **25 fps, 1280x720.** 25 divides both control rates (50 Hz and 200 Hz) so frames are real
  control steps; H.264 yuv420p re-encode so clips play in any browser and phone.
- **Never use the branded skins** in `jumper-design/library/skins/` (doraemon, spiderman,
  snoopy, mr-krabs, raphael-turtle): the contest disqualifies IP infringement.
