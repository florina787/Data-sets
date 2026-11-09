#!/usr/bin/env bash
# Builds the static VEENA.AI website into ./_site (or $1).
#   REF: the git branch or tag the repository links should point at (default: main).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
out="${1:-$here/_site}"
ref="${REF:-main}"
rm -rf "$out" && mkdir -p "$out/images"
cp "$here"/index.html "$here"/privacy.html "$here"/site.css "$here"/downloads.js "$out/"
cp "$here"/../apps/desktop/assets/icon-64.png "$out/images/"
for img in agents agents-answer agents-graphs citations meeting screen interview; do
  cp "$here/../docs/images/$img.png" "$out/images/"
done
# Never publish the owner's private photo, even by accident.
if find "$out" -iname '*founder*' | grep -q .; then echo "refusing: private photo in site output" >&2; exit 1; fi
sed -i.bak "s#__REF__#${ref}#g" "$out"/*.html && rm -f "$out"/*.bak
# Every local link and image must exist.
python3 - "$out" <<'PY'
import re, sys, pathlib
out = pathlib.Path(sys.argv[1]); missing = []
for page in out.glob("*.html"):
    for ref in re.findall(r'(?:src|href)="([^"#:]+)"', page.read_text()):
        if not (out / ref).exists():
            missing.append(f"{page.name}: {ref}")
if missing:
    sys.exit("missing local files:\n" + "\n".join(missing))
print(f"site built: {sum(1 for _ in out.rglob('*') if _.is_file())} files, {sum(f.stat().st_size for f in out.rglob('*') if f.is_file())/1e6:.1f} MB")
PY
