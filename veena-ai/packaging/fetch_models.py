"""Downloads the models that are bundled inside the installer.

    python packaging/fetch_models.py   ->  packaging/models/all-MiniLM-L6-v2/

Bundled so that document search works on first use without any download
(a first-use download hung on a Windows CI runner). Apache-2.0 licensed.
"""

from __future__ import annotations

from pathlib import Path

from huggingface_hub import snapshot_download

OUT = Path(__file__).parent / "models" / "all-MiniLM-L6-v2"
# Pinned revision of sentence-transformers/all-MiniLM-L6-v2 (as resolved by the app today).
REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
FILES = [
    "modules.json",
    "config.json",
    "config_sentence_transformers.json",
    "sentence_bert_config.json",
    "model.safetensors",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "vocab.txt",
    "1_Pooling/config.json",
]

if __name__ == "__main__":
    snapshot_download("sentence-transformers/all-MiniLM-L6-v2", revision=REVISION, allow_patterns=FILES, local_dir=OUT)
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file()) / 1e6
    print(f"bundled embedding model at {OUT} ({size:.0f} MB)")
