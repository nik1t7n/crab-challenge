#!/usr/bin/env bash
# Bring up the render environment on a render host (the Mac Studio) in one isolated folder.
# Everything lives under $ROOT: upstream clones, their uv venvs, our tools, the renders.
# Nothing is installed system-wide, so `rm -rf $ROOT` removes every trace.
#
#   ROOT=~/isolated/crab-challenge bash remote_bootstrap.sh
set -euo pipefail
ROOT=${ROOT:-$HOME/isolated/crab-challenge}
mkdir -p "$ROOT/upstream" "$ROOT/tools"
cd "$ROOT/upstream"

UV=$(command -v uv || true)
if [ -z "$UV" ]; then
  # uv into the isolated folder itself, not ~/.local
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$ROOT/.bin" UV_NO_MODIFY_PATH=1 sh
  UV="$ROOT/.bin/uv"
fi
export UV_CACHE_DIR="$ROOT/.uv-cache" UV_PYTHON_INSTALL_DIR="$ROOT/.python"

[ -d jumper ] || git clone -q https://github.com/KingKongRobotics/jumper.git
[ -d jumper-design ] || GIT_LFS_SKIP_SMUDGE=1 git clone -q https://github.com/KingKongRobotics/jumper-design.git
if command -v git-lfs >/dev/null; then
  (cd jumper-design && git lfs pull)
else
  echo "warning: git-lfs missing, jumper-design maps will not load" >&2
fi

cd jumper
[ -x .venv/bin/python ] || "$UV" venv -q --python 3.12 .venv
"$UV" pip install -q --python .venv/bin/python torch torchvision
"$UV" pip install -q --python .venv/bin/python -e ".[dev]"
.venv/bin/python -c "import mujoco, torch, mjlab; print('jumper ok', mujoco.__version__, torch.__version__)"
# ffmpeg: the renderer falls back to the binary imageio-ffmpeg installs into the venv
