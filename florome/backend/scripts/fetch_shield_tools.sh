#!/usr/bin/env bash
# Download the external analysers Florome Shield runs as separate processes. Versions are pinned.
set -euo pipefail
DEST="$(cd "$(dirname "$0")/.." && pwd)/.tools/bin"
mkdir -p "$DEST"
curl -fsSL -o "$DEST/opengrep" https://github.com/opengrep/opengrep/releases/download/v1.33.1/opengrep_manylinux_x86
curl -fsSL https://github.com/aquasecurity/trivy/releases/download/v0.76.2/trivy_0.76.2_Linux-64bit.tar.gz | tar xz -C "$DEST" trivy
curl -fsSL -o "$DEST/opa" https://github.com/open-policy-agent/opa/releases/download/v1.22.4/opa_linux_amd64_static
chmod +x "$DEST"/opengrep "$DEST"/opa "$DEST"/trivy
"$DEST/opengrep" --version && "$DEST/trivy" --version | head -1 && "$DEST/opa" version | head -1
