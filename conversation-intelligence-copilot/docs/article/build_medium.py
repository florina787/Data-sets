"""Build docs/article/medium-article.html from medium-article.src.html by embedding every IMG:<path> image as a data URI,
so the page displays anywhere (and images copy along when pasted into Medium's editor).
Run from the project root: python docs/article/build_medium.py
"""

import base64
import mimetypes
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "docs" / "article" / "medium-article.src.html"
OUT = ROOT / "docs" / "article" / "medium-article.html"


def embed(match: re.Match) -> str:
    path = ROOT / match.group(1)
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f'src="data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"'


html = re.sub(r'src="IMG:([^"]+)"', embed, SRC.read_text())
OUT.write_text(html)
print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")
