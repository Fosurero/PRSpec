#!/usr/bin/env bash
# Screen recorder for the live demo: a virtual X display (Xvfb) captured in real
# time by ffmpeg x11grab while xterm runs session.sh and Chrome shows the
# generated reports and the public GitHub pages of the pilot PR and run.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export DISPLAY=:99 LANG=C.UTF-8 LC_ALL=C.UTF-8
VIDEO="$WORK/evidence/prspec-besu-live-demo.mp4"
mkdir -p "$WORK/evidence"; : > "$WORK/evidence/terminal-transcript.txt"
Xvfb :99 -screen 0 1920x1080x24 -dpi 96 -br -nolisten tcp > /dev/null 2>&1 &
XVFB=$!
for _ in $(seq 50); do xdpyinfo > /dev/null 2>&1 && break; sleep 0.2; done
ffmpeg -nostdin -loglevel error -y -f x11grab -draw_mouse 0 -framerate 15 \
  -video_size 1920x1080 -i :99 -c:v libx264 -preset veryfast -crf 24 \
  -pix_fmt yuv420p -movflags +faststart "$VIDEO" &
FFMPEG=$!
sleep 1
xterm -u8 -geometry 180x50+0+0 -fa 'DejaVu Sans Mono' -fs 13 -b 12 \
  -bg '#0d1117' -fg '#e6edf3' -xrm 'XTerm*termName: xterm-256color' \
  -xrm 'XTerm*borderWidth: 0' -T 'PRSpec live demo' -e bash "$HERE/session.sh"

CHROME="$(command -v google-chrome || command -v chromium-browser || command -v chromium)"
page() {  # url, seconds to hold, mouse-wheel scroll steps
  local profile pid
  profile="$(mktemp -d)"
  "$CHROME" --user-data-dir="$profile" --no-first-run --no-default-browser-check \
    --disable-features=Translate,MediaRouter --hide-crash-restore-bubble \
    --password-store=basic --kiosk --window-position=0,0 --window-size=1920,1080 \
    "$1" > /dev/null 2>&1 &
  pid=$!
  sleep 7
  xdotool mousemove 960 540 > /dev/null 2>&1
  for _ in $(seq "${3:-0}"); do xdotool click 5 click 5 click 5 > /dev/null 2>&1; sleep 1.3; done
  sleep "$2"
  kill "$pid" 2> /dev/null; wait "$pid" 2> /dev/null
}
for side in before after; do
  report=$(ls "$WORK/out/$side/output/"prspec_eip4844_besu*.html 2> /dev/null | head -1)
  if [ -n "$report" ]; then page "file://$report" 3 6; fi
done
if [ -n "${PR_URL:-}" ]; then page "$PR_URL" 3 3; fi
if [ -n "${PILOT_RUN_URL:-}" ]; then page "$PILOT_RUN_URL" 3 6; fi
kill -INT "$FFMPEG"; wait "$FFMPEG"
kill "$XVFB" 2> /dev/null
ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$VIDEO"
