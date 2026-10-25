#!/bin/sh
# Render every baked bedroom shot in Blender, one after another (the GPU is the
# limit; two at once only share it). Usage: tools/film/blender/render_all.sh [shot ...]
cd "$(dirname "$0")/../../.." || exit 1
BLENDER=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
SHOTS=${*:-"wide popout near_miss convoy sweep macro bulldozer last_in door mom_pov guilty title"}
for s in $SHOTS; do
  start=$(date +%s)
  nice -n 10 "$BLENDER" -b -P tools/film/blender/shot.py -- "$s" 2>&1 | grep -iE "error|traceback|\[blend\]"
  echo "[render_all] $s $(( $(date +%s) - start )) s"
done
