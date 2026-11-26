# Reels-creative-#!/usr/bin/env bash
# Build a reel from a source video and an edit plan.
#   tools/build.sh SRC.mp4 projects/dentist-reel/edit_plan.json output/dentist_reel_final.mp4
set -euo pipefail
SRC=$1
PLAN=$2
OUT=$3
BUILD=build/$(basename "$(dirname "$PLAN")")
mkdir -p "$BUILD" "$(dirname "$OUT")"

DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$SRC")

python3 tools/sfx_synth.py sfx
python3 tools/music_synth.py "$PLAN" "$BUILD/music.wav" "$DUR"
python3 tools/render_video.py "$SRC" "$PLAN" "$BUILD/video_only.mp4"
python3 tools/mix_audio.py "$SRC" "$PLAN" "$BUILD/music.wav" sfx "$BUILD/mix.wav"

ffmpeg -v error -y -i "$BUILD/video_only.mp4" -i "$BUILD/mix.wav" -map 0:v -map 1:a \
  -c:v copy -c:a aac -b:a 256k -ar 48000 -shortest -movflags +faststart "$OUT"
echo "done -> $OUT"
