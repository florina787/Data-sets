"""Airspace Safety & Drone Visual Analysis Lab — CIVILIAN SAFETY RESEARCH ONLY.

Scope: offline analysis of prerecorded, authorized images or footage, one frame at a time. There is deliberately no tracking across
frames, no trajectory or route estimation, no intent assessment, no targeting and no interception logic of any kind.

Methods (the response always says which one ran):
* ``vision_model`` — a compatible local vision-language model, if one is already installed (e.g. an Ollama model whose name contains
  llava / qwen2.5vl / qwen-vl / moondream / minicpm-v / llama3.2-vision). Nothing is downloaded. Not available on the build machine.
* ``classical_baseline`` — deterministic image processing (sky estimate, dark-object threshold, connected components, shape features).
  This is NOT AI and is labelled as such; it exists so the evaluation pipeline can run without a vision model.

Demonstration data: synthetic frames rendered with Pillow from a fixed seed (sky gradient, clouds, quadcopter silhouettes, birds,
aircraft) with stored ground-truth labels. Uploaded footage is analysed in memory; only its SHA-256, size and the result summary are
persisted, never the pixels.
"""

from __future__ import annotations

import hashlib
import io
import json
import random
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from app.core.config import get_settings

DEMO_SEED = 20261103
W, H = 320, 200
VISION_NAME = ("llava", "qwen2.5vl", "qwen2-vl", "qwen-vl", "qwenvl", "moondream", "minicpm-v", "llama3.2-vision", "bakllava")
MAX_UPLOAD = 20 * 1024 * 1024
MAX_FRAMES = 12


# ------------------------------------------------------------------ capabilities
def capabilities() -> dict[str, Any]:
    from app.llm.gateway import gateway

    st = gateway().status()
    d = st.get("discovery", {})
    model = (d.get("model") or "") or ""
    text_model_vision = any(v in model.lower() for v in VISION_NAME)
    vision = _find_vision_model()
    return {
        "qwen": {"available": st.get("available", False), "model": d.get("model"), "quantization": d.get("quantization"),
                 "runtime": d.get("runtime"), "context_window": get_settings().qwen_n_ctx,
                 "modality": "vision-language" if text_model_vision else ("text-only" if model else "unknown (no model found)"),
                 "reason": d.get("reason")},
        "vision_model": vision,
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "methods_available": (["vision_model"] if vision["found"] else []) + ["classical_baseline"],
        "default_method": "vision_model" if vision["found"] else "classical_baseline",
        "statement": ("A local vision model was found and can be used." if vision["found"] else
                      "No local vision model was found, so no AI visual detection is available. The lab runs a classical, non-AI "
                      "image-processing baseline and labels every result accordingly. Your Qwen text model is still used to explain results "
                      "in words when it is available."),
        "boundaries": ["Civilian safety research on prerecorded, authorized footage only.",
                       "Frames are analysed independently: no tracking, trajectory, route or intent estimation.",
                       "No targeting, interception, pursuit or engagement functions exist in this module.",
                       "Uploaded pixels are not stored; only a hash and the result summary are kept."],
    }


def _find_vision_model() -> dict[str, Any]:
    """Look for an already-installed vision model on loopback Ollama. Never downloads anything."""
    import httpx

    url = get_settings().llm_url.rstrip("/")
    try:
        r = httpx.get(f"{url}/api/tags", timeout=1.5)
        names = [m.get("name", "") for m in r.json().get("models", [])]
    except Exception:  # noqa: BLE001
        return {"found": False, "model": None, "runtime": None, "searched": f"{url}/api/tags (Ollama)"}
    hit = next((n for n in names if any(v in n.lower() for v in VISION_NAME)), None)
    return {"found": bool(hit), "model": hit, "runtime": "ollama" if hit else None, "searched": f"{url}/api/tags (Ollama)"}


# ------------------------------------------------------------------ synthetic demo frames
def _sky(rng: random.Random) -> Image.Image:
    top = (rng.randint(90, 140), rng.randint(150, 190), rng.randint(215, 245))
    bot = (rng.randint(190, 225), rng.randint(210, 235), rng.randint(235, 252))
    a = np.linspace(0, 1, H)[:, None, None]
    arr = (np.array(top)[None, None, :] * (1 - a) + np.array(bot)[None, None, :] * a).repeat(W, axis=1)
    img = Image.fromarray(arr.astype("uint8"), "RGB")
    d = ImageDraw.Draw(img, "RGBA")
    for _ in range(rng.randint(1, 4)):  # clouds
        cx, cy, r = rng.randint(0, W), rng.randint(0, H), rng.randint(18, 45)
        for _ in range(6):
            ox, oy = rng.randint(-r, r), rng.randint(-r // 3, r // 3)
            d.ellipse([cx + ox - r, cy + oy - r // 2, cx + ox + r, cy + oy + r // 2], fill=(255, 255, 255, rng.randint(90, 160)))
    return img.filter(ImageFilter.GaussianBlur(1.2))


def _quad(d: ImageDraw.ImageDraw, x: float, y: float, s: float, col: tuple[int, int, int]) -> None:
    arm = s
    d.line([x - arm, y - arm * 0.6, x + arm, y + arm * 0.6], fill=col, width=max(2, int(s / 5)))
    d.line([x - arm, y + arm * 0.6, x + arm, y - arm * 0.6], fill=col, width=max(2, int(s / 5)))
    d.rectangle([x - s * 0.35, y - s * 0.25, x + s * 0.35, y + s * 0.25], fill=col)
    for px, py in ((x - arm, y - arm * 0.6), (x + arm, y - arm * 0.6), (x - arm, y + arm * 0.6), (x + arm, y + arm * 0.6)):
        d.ellipse([px - s * 0.45, py - s * 0.15, px + s * 0.45, py + s * 0.15], outline=col, width=max(1, int(s / 7)))


def _bird(d: ImageDraw.ImageDraw, x: float, y: float, s: float, col: tuple[int, int, int]) -> None:
    d.line([x - s * 1.6, y - s * 0.5, x, y + s * 0.15, x + s * 1.6, y - s * 0.5], fill=col, width=max(2, int(s / 4)))


def _plane(d: ImageDraw.ImageDraw, x: float, y: float, s: float, col: tuple[int, int, int]) -> None:
    d.rectangle([x - s * 2.6, y - s * 0.22, x + s * 2.6, y + s * 0.22], fill=col)
    d.polygon([(x - s * 0.4, y), (x + s * 0.5, y), (x - s * 0.1, y + s * 1.5)], fill=col)
    d.polygon([(x - s * 0.4, y), (x + s * 0.5, y), (x - s * 0.1, y - s * 1.5)], fill=col)


def render_frame(rng: random.Random, kind: str) -> tuple[Image.Image, dict[str, Any]]:
    img = _sky(rng)
    d = ImageDraw.Draw(img)
    col = (rng.randint(20, 60),) * 3
    x, y, s = rng.uniform(50, W - 50), rng.uniform(40, H - 40), rng.uniform(6, 13)
    if kind == "drone":
        _quad(d, x, y, s, col)
    elif kind == "bird":
        _bird(d, x, y, s, col)
    elif kind == "aircraft":
        _plane(d, x, y, s * 1.2, col)
    elif kind == "drone_far":
        _quad(d, x, y, 3.5, col)
    box = None if kind == "empty" else [round(x - s * 2, 1), round(y - s * 1.5, 1), round(x + s * 2, 1), round(y + s * 1.5, 1)]
    return img, {"label": "drone" if kind.startswith("drone") else "no_drone", "object": kind, "box": box}


def demo_set() -> list[dict[str, Any]]:
    """40 labelled still frames + 3 short clips (frame sequences). Deterministic; cached on disk in the data folder."""
    out_dir = get_settings().data_dir / "visual_demo"
    index = out_dir / "index.json"
    if index.exists():
        return json.loads(index.read_text())
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(DEMO_SEED)
    kinds = ["drone"] * 14 + ["drone_far"] * 4 + ["bird"] * 8 + ["aircraft"] * 6 + ["empty"] * 8
    rng.shuffle(kinds)
    items = []
    for i, k in enumerate(kinds):
        img, gt = render_frame(rng, k)
        name = f"frame_{i:02d}.png"
        img.save(out_dir / name)
        items.append({"id": f"IMG-{i:02d}", "file": name, "kind": "image", **gt})
    for c, seq in enumerate((["empty", "empty", "drone", "drone", "drone", "empty"], ["bird", "bird", "bird", "empty", "bird", "bird"],
                             ["aircraft", "drone", "drone_far", "empty", "drone", "aircraft"])):
        frames = []
        for j, k in enumerate(seq):
            img, gt = render_frame(rng, k)
            name = f"clip{c}_f{j}.png"
            img.save(out_dir / name)
            frames.append({"file": name, **gt})
        items.append({"id": f"CLIP-{c}", "kind": "clip", "frames": frames, "label": "drone" if any(f["label"] == "drone" for f in frames) else "no_drone",
                      "note": "synthetic prerecorded sequence (frames analysed independently)"})
    index.write_text(json.dumps(items, indent=1))
    return items


def demo_image(name: str) -> bytes:
    p = get_settings().data_dir / "visual_demo" / Path(name).name
    if not p.exists() or p.suffix != ".png":
        raise FileNotFoundError(name)
    return p.read_bytes()


# ------------------------------------------------------------------ classical baseline (NOT AI)
def classical(img: Image.Image) -> dict[str, Any]:
    g = np.asarray(img.convert("L").resize((W, H)), dtype=float)
    sky = np.median(g, axis=1, keepdims=True)  # per-row sky level handles the vertical gradient
    mask = (sky - g) > 55
    if mask.sum() == 0:
        return {"drone_like": False, "score": 0.0, "candidates": [], "reason": "No dark object against the sky."}
    lab, n = _components(mask)
    cands = []
    for k in range(1, n + 1):
        ys, xs = np.nonzero(lab == k)
        if len(xs) < 6:
            continue
        w, h = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
        fill = len(xs) / (w * h)
        aspect = w / h
        # quadcopter silhouettes: compact (aspect 1.1-3), sparse fill (arms + rotors), several internal holes; birds: thin chevrons
        # (aspect > 2.6, very low fill); aircraft: long fuselage (aspect > 3) with high horizontal fill.
        rows = (lab[ys.min():ys.max() + 1, xs.min():xs.max() + 1] == k)
        holes = _holes(rows)
        s = 0.0
        s += 0.35 if 1.0 <= aspect <= 3.0 else 0.0
        s += 0.25 if 0.18 <= fill <= 0.6 else 0.0
        s += 0.3 if holes >= 1 else 0.0
        s += 0.1 if 8 <= max(w, h) <= 70 else 0.0
        cands.append({"box": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())], "area": int(len(xs)), "aspect": round(float(aspect), 2),
                      "fill": round(float(fill), 2), "holes": holes, "score": round(s, 2)})
    cands.sort(key=lambda c: -c["score"])
    best = cands[0]["score"] if cands else 0.0
    return {"drone_like": best >= 0.6, "score": best, "uncertain": 0.45 <= best < 0.7, "candidates": cands[:3],
            "reason": (f"Best candidate: aspect {cands[0]['aspect']}, fill {cands[0]['fill']}, {cands[0]['holes']} enclosed gaps -> score {best} "
                       f"(threshold 0.6).") if cands else "Only specks below the size floor."}


def _components(mask: np.ndarray) -> tuple[np.ndarray, int]:
    lab = np.zeros(mask.shape, dtype=int)
    n = 0
    hgt, wid = mask.shape
    for y0 in range(hgt):
        for x0 in range(wid):
            if mask[y0, x0] and not lab[y0, x0]:
                n += 1
                stack = [(y0, x0)]
                lab[y0, x0] = n
                while stack:
                    y, x = stack.pop()
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            yy, xx = y + dy, x + dx
                            if 0 <= yy < hgt and 0 <= xx < wid and mask[yy, xx] and not lab[yy, xx]:
                                lab[yy, xx] = n
                                stack.append((yy, xx))
    return lab, n


def _holes(obj: np.ndarray) -> int:
    """Background regions inside the bounding box that do not touch its border (enclosed gaps)."""
    bg = ~obj
    lab, n = _components(bg)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
    return sum(1 for k in range(1, n + 1) if k not in border and (lab == k).sum() >= 2)


# ------------------------------------------------------------------ evaluation and analysis
def _metrics(rows: list[tuple[str, bool, float]]) -> dict[str, Any]:
    tp = sum(1 for gt, p, _ in rows if gt == "drone" and p)
    fp = sum(1 for gt, p, _ in rows if gt != "drone" and p)
    fn = sum(1 for gt, p, _ in rows if gt == "drone" and not p)
    tn = sum(1 for gt, p, _ in rows if gt != "drone" and not p)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": round(prec, 4), "recall": round(rec, 4),
            "f1": round(2 * prec * rec / (prec + rec), 4) if prec + rec else 0.0, "n": len(rows),
            "false_positive_rate": round(fp / (fp + tn), 4) if fp + tn else 0.0, "false_negative_rate": round(fn / (fn + tp), 4) if fn + tp else 0.0}


def evaluate() -> dict[str, Any]:
    items = demo_set()
    rows, per, by_obj = [], [], {}
    for it in items:
        frames = [it] if it["kind"] == "image" else it["frames"]
        for f in frames:
            r = classical(Image.open(io.BytesIO(demo_image(f["file"]))))
            rows.append((f["label"], r["drone_like"], r["score"]))
            by_obj.setdefault(f["object"], []).append(r["drone_like"])
            per.append({"item": it["id"], "file": f["file"], "object": f["object"], "label": f["label"], "predicted": "drone" if r["drone_like"] else "no_drone",
                        "score": r["score"], "uncertain": r.get("uncertain", False), "correct": (f["label"] == "drone") == r["drone_like"]})
    return {"method": "classical_baseline", "is_ai": False, "dataset": f"synthetic labelled frames (seed {DEMO_SEED})", **_metrics(rows),
            "by_object": {k: {"n": len(v), "flagged_drone_like": sum(v)} for k, v in by_obj.items()},
            "uncertain": [p for p in per if p["uncertain"]], "errors": [p for p in per if not p["correct"]], "frames": per}


def frames_from_upload(data: bytes, filename: str) -> list[Image.Image]:
    if len(data) > MAX_UPLOAD:
        raise ValueError("File larger than 20 MB.")
    ext = Path(filename).suffix.lower()
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
        return [Image.open(io.BytesIO(data)).convert("RGB")]
    if ext == ".gif":
        im = Image.open(io.BytesIO(data))
        n = getattr(im, "n_frames", 1)
        idx = sorted({int(i * n / min(n, MAX_FRAMES)) for i in range(min(n, MAX_FRAMES))})
        out = []
        for i in idx:
            im.seek(i)
            out.append(im.convert("RGB"))
        return out
    if ext in (".mp4", ".mov", ".webm", ".avi", ".mkv"):
        if not shutil.which("ffmpeg"):
            raise ValueError("Video frame sampling needs ffmpeg, which is not installed. Upload images or an animated GIF instead.")
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / f"in{ext}"
            src.write_bytes(data)
            subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(src), "-vf", "fps=1,scale=320:-2", "-frames:v", str(MAX_FRAMES),  # noqa: S603,S607
                            str(Path(td) / "f_%03d.png")], check=True, timeout=60)
            return [Image.open(p).convert("RGB") for p in sorted(Path(td).glob("f_*.png"))]
    raise ValueError("Unsupported file type. Use PNG, JPEG, WebP, GIF, MP4, MOV, WEBM.")


def analyze_frames(frames: list[Image.Image], method: str | None = None) -> dict[str, Any]:
    caps_vision = _find_vision_model()
    use = method or ("vision_model" if caps_vision["found"] else "classical_baseline")
    if use == "vision_model" and not caps_vision["found"]:
        raise ValueError("No local vision model is installed; the vision_model method is unavailable.")
    results = []
    for i, f in enumerate(frames[:MAX_FRAMES]):
        if use == "vision_model":
            r = _vision(f, caps_vision["model"])
        else:
            r = classical(f)
        thumb = io.BytesIO()
        f.copy().resize((W, int(W * f.height / max(f.width, 1)))).save(thumb, "PNG")
        results.append({"frame": i, **r, "thumbnail_png_b64": __import__("base64").b64encode(thumb.getvalue()).decode()})
    flagged = sum(1 for r in results if r.get("drone_like"))
    return {"method": use, "is_ai": use == "vision_model", "frames": results, "frames_flagged": flagged, "frames_total": len(results),
            "summary": (f"{flagged} of {len(results)} frame(s) contain a drone-like object according to the "
                        f"{'local vision model' if use == 'vision_model' else 'classical image-processing baseline (not AI)'}."),
            "limitations": ["Frames are judged independently; no tracking or trajectory is computed.",
                            "Classical baseline: silhouettes against open sky only; clutter, low contrast and small objects reduce reliability."
                            if use == "classical_baseline" else "Vision-model output is a model judgement and can be wrong; verify visually."]}


def _vision(img: Image.Image, model: str) -> dict[str, Any]:  # pragma: no cover - needs a locally installed vision model
    import base64

    import httpx

    buf = io.BytesIO()
    img.save(buf, "PNG")
    prompt = ("Civilian airspace-safety review of a single still frame. Does it contain a drone (small unmanned aircraft)? Answer JSON "
              '{"drone_like": true|false, "confidence": "low|medium|high", "visible_characteristics": "..."}. Describe only what is visible.')
    r = httpx.post(f"{get_settings().llm_url.rstrip('/')}/api/generate", json={"model": model, "prompt": prompt, "images": [base64.b64encode(buf.getvalue()).decode()],
                                                                            "stream": False, "format": "json", "options": {"temperature": 0}}, timeout=90)
    try:
        out = json.loads(r.json().get("response", "{}"))
    except json.JSONDecodeError:
        out = {}
    return {"drone_like": bool(out.get("drone_like")), "score": {"low": 0.4, "medium": 0.65, "high": 0.9}.get(str(out.get("confidence")), 0.5),
            "uncertain": str(out.get("confidence")) == "low", "reason": str(out.get("visible_characteristics", ""))[:400], "candidates": []}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def report_markdown(result: dict[str, Any], source: str) -> str:
    lines = [f"# Visual analysis report — {source}", "", "> Civilian safety research. Prerecorded footage. Frames analysed independently.", "",
             f"**Method:** {result['method']} ({'AI model' if result['is_ai'] else 'classical image processing, not AI'})", "",
             f"**Result:** {result['summary']}", "", "| Frame | Drone-like | Score | Uncertain | Evidence |", "|---|---|---|---|---|"]
    for f in result["frames"]:
        lines.append(f"| {f['frame']} | {'yes' if f.get('drone_like') else 'no'} | {f.get('score')} | {'yes' if f.get('uncertain') else 'no'} | {f.get('reason', '')} |")
    lines += ["", "## Limitations", ""] + [f"* {x}" for x in result["limitations"]]
    return "\n".join(lines)

