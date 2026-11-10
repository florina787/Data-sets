"""Privacy check for the website demo clips: no frame may show the app's Home screen.

    python site/tools/check_media_privacy.py site/media

The Home screen can show a private local photo (apps/desktop/public/founder.png, never
committed). This reads two frames per second of every clip with Tesseract OCR and fails
if the Home screen's headline appears. Needs ffmpeg and tesseract.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

MARKERS = ("nail every conversation", "own every meeting")


def main() -> int:
    media = Path(sys.argv[1])
    clips = sorted(media.glob("*.mp4")) + sorted(media.glob("*.gif"))
    bad = []
    for clip in clips:
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["ffmpeg", "-v", "error", "-i", str(clip), "-vf", "fps=2,scale=1280:-1", f"{tmp}/f%04d.png"], check=True)
            frames = sorted(Path(tmp).glob("*.png"))
            for f in frames:
                text = subprocess.run(["tesseract", str(f), "-", "--psm", "11"], capture_output=True, text=True).stdout.lower()
                if any(m in text for m in MARKERS):
                    bad.append(f"{clip.name} at {(int(f.stem[1:]) - 1) / 2:.1f}s")
                    break
        print(f"{clip.name}: {len(frames)} frames checked")
    if bad:
        print("FAIL: Home screen (may show a private photo) in: " + ", ".join(bad))
        return 1
    print(f"privacy OK: {len(clips)} clips, no Home screen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
