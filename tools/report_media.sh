#!/usr/bin/env bash
# Web copies of the gallery for the report page: 960 px wide, H.264, plus a poster frame.
# The full-size renders stay in renders/; these only need to play smoothly in a browser
# and keep the whole page under the artifact's per-publish limit.
set -euo pipefail
cd "$(dirname "$0")/.."
# A share of a duration, as a time ffmpeg accepts (bc alone prints ".35", which it refuses).
at() { printf '%.3f' "$(echo "$1*$2" | bc -l)"; }
mkdir -p report/clips
for mp4 in renders/*/*.mp4; do
  group=$(basename "$(dirname "$mp4")"); name=$(basename "$mp4" .mp4)
  out="report/clips/${group}--${name}"
  w=$(ffprobe -v error -select_streams v -show_entries stream=width -of csv=p=0 "$mp4")
  h=$(ffprobe -v error -select_streams v -show_entries stream=height -of csv=p=0 "$mp4")
  if [ "$w" -gt "$h" ]; then scale=960:-2; else scale=-2:960; fi
  ffmpeg -y -loglevel error -i "$mp4" -vf "scale=$scale" -c:v libx264 -crf 27 -preset slow \
    -pix_fmt yuv420p -movflags +faststart -an "$out.mp4"
  dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$mp4")
  ffmpeg -y -loglevel error -ss "$(at "$dur" 0.4)" -i "$mp4" -vf "scale=$scale" \
    -frames:v 1 -q:v 5 "$out.jpg"
done
du -sh report/clips
