#!/usr/bin/env bash
# Assembles the frames captured by capture-readme-media.mjs into docs/readme/demo.gif.
# Usage: e2e/readme-demo-gif.sh [mediaDir]   (default ../docs/readme)
set -euo pipefail
dir="${1:-../docs/readme}"
fps="$(cat "$dir/.frames/fps.txt")"
ffmpeg -y -loglevel error -framerate "$fps" -i "$dir/.frames/%05d.png" \
  -vf "fps=8,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle" \
  -loop 0 "$dir/demo.gif"
ls -lh "$dir/demo.gif"
