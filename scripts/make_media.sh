#!/bin/sh
# Render every visual and media file from the committed data (offline, no store requests).
#
#   scripts/make_media.sh            # uses data/, writes assets/ and media/
#
# Needs: uv, Node with Playwright (Chromium), ffmpeg with libx264.
set -eu
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

uv run python -m crossprice.visuals --data data --retailers config/retailers.yml --out assets
uv run python -m crossprice.readme
uv run python -m crossprice.site --data data --retailers config/retailers.yml --out "$work/site"
node scripts/render_media.cjs dashboard "$work/site" assets/dashboard.png 1280
node scripts/render_media.cjs dashboard "$work/site" assets/dashboard-phone.png 390
stores="$(grep -c '^- id:' config/retailers.yml)"
products="$(tail -n 1 data/runs.jsonl | python3 -c 'import json,sys; print(f"{json.load(sys.stdin)[\"comparison\"][\"products_matched\"]:,}")')"
node scripts/render_media.cjs social src/crossprice/site_assets/fonts "$stores" "$products" assets/social-preview.png
uv run python -c "
from pathlib import Path
from crossprice.visuals import collect, hero_square
Path('$work/hero-square.svg').write_text(hero_square(collect(Path('data'), Path('config/retailers.yml'))).render())
"
node scripts/render_media.cjs frames "$work/hero-square.svg" "$work/frames"
mkdir -p media
ffmpeg -loglevel error -y -framerate 30 -i "$work/frames/f%04d.png" \
  -c:v libx264 -pix_fmt yuv420p -crf 20 -preset slow -movflags +faststart media/linkedin-hero.mp4
ls -la assets/*.svg assets/*.png media/linkedin-hero.mp4
