#!/usr/bin/env bash
# Builds the static VEENA.AI website into ./_site (or $1).
#   REF: the git branch or tag the repository links should point at (default: main).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
out="${1:-$here/_site}"
ref="${REF:-main}"
rm -rf "$out" && mkdir -p "$out/images"
# Nothing switched on unverified (feedback form, community link, analytics), and no secrets.
python3 "$here/tools/check_config.py" "$here/config.js"
cp "$here"/index.html "$here"/features.html "$here"/feedback.html "$here"/privacy.html \
   "$here"/site.css "$here"/site.js "$here"/config.js "$out/"
cp -R "$here/fonts" "$out/fonts"
cp "$here"/../apps/desktop/assets/icon-64.png "$out/images/"
# Demo media (recorded from the real app by apps/desktop/scripts/record-demos.mjs).
if [ -d "$here/media" ]; then cp -R "$here/media" "$out/media"; fi
# Media budget: keep pages fast on ordinary connections.
python3 - "$out" <<'PY'
import pathlib, sys
media = pathlib.Path(sys.argv[1]) / "media"
files = list(media.glob("*")) if media.exists() else []
limits = {".gif": 6e6, ".mp4": 6e6, ".webm": 6e6, ".jpg": 400e3}
over = [f"{f.name} {f.stat().st_size/1e6:.1f} MB" for f in files if f.stat().st_size > limits.get(f.suffix, 1e6)]
total = sum(f.stat().st_size for f in files)
if over or total > 60e6:
    sys.exit("media over budget: " + ", ".join(over) + f" (total {total/1e6:.1f} MB, limit 60 MB)")
PY
# Never publish the owner's private photo, even by accident.
if find "$out" -iname '*founder*' | grep -q .; then echo "refusing: private photo in site output" >&2; exit 1; fi
sed -i.bak "s#__REF__#${ref}#g" "$out"/*.html && rm -f "$out"/*.bak
# Every local link and image must exist.
python3 - "$out" <<'PY'
import re, sys, pathlib
out = pathlib.Path(sys.argv[1]); missing = []
for page in out.glob("*.html"):
    for ref in re.findall(r'(?:src|href|srcset|poster|data-video)="([^"#:]+)"', page.read_text()):
        if ref not in ("./",) and not (out / ref.split("?")[0]).exists():
            missing.append(f"{page.name}: {ref}")
if missing:
    sys.exit("missing local files:\n" + "\n".join(missing))
print(f"site built: {sum(1 for _ in out.rglob('*') if _.is_file())} files, {sum(f.stat().st_size for f in out.rglob('*') if f.is_file())/1e6:.1f} MB")
PY
