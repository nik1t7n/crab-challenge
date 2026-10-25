#!/usr/bin/env bash
# One image per rendered clip with three frames side by side (20%, 50%, 80% of the clip),
# plus a poster frame at 40% for the report page. Lets a person or an agent check a whole
# gallery for broken renders without playing every video.
set -euo pipefail
cd "$(dirname "$0")/.."
# A share of a duration, as a time ffmpeg accepts (bc alone prints ".35", which it refuses).
at() { printf '%.3f' "$(echo "$1*$2" | bc -l)"; }
mkdir -p renders/frames
for mp4 in renders/*/*.mp4; do
  group=$(basename "$(dirname "$mp4")"); name=$(basename "$mp4" .mp4)
  dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$mp4")
  args=(); for f in 0.2 0.5 0.8; do
    args+=(-ss "$(at "$dur" "$f")" -i "$mp4")
  done
  ffmpeg -y -loglevel error "${args[@]}" \
    -filter_complex "[0:v]scale=480:-2[a];[1:v]scale=480:-2[b];[2:v]scale=480:-2[c];[a][b][c]hstack=3" \
    -frames:v 1 "renders/frames/${group}--${name}.jpg"
  ffmpeg -y -loglevel error -ss "$(at "$dur" 0.4)" -i "$mp4" -vf scale=640:-2 \
    -frames:v 1 -q:v 4 "renders/frames/${group}--${name}.poster.jpg"
done
ls renders/frames | wc -l
