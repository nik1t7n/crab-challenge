#!/bin/sh
# Render a film's baked shots in Blender, one after another (the GPU is the limit;
# two at once only share it).
#   FILM=rocky tools/film/blender/render_all.sh [shot ...]     (default: every baked shot)
cd "$(dirname "$0")/../../.." || exit 1
BLENDER=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
FILM=${FILM:-bedroom}
if [ -n "$*" ]; then
  SHOTS="$*"
else
  SHOTS=$(cd "renders/${FILM}_blend/bake" && ls *.json | grep -v '^room.json$' | sed 's/\.json$//')
fi
for s in $SHOTS; do
  start=$(date +%s)
  nice -n 10 "$BLENDER" -b -P tools/film/blender/shot.py -- "$s" --film "$FILM" 2>&1 | grep -iE "error|traceback|\[blend\]"
  echo "[render_all] $s $(( $(date +%s) - start )) s"
done
