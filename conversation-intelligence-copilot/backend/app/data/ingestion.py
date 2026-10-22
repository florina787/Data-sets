"""Dataset discovery and loading with explicit schema mapping.

The loader never assumes a schema: it inspects the archive, detects the encoding
and delimiter, and maps source columns to the canonical schema through an
explicit alias table. A missing required column is a hard error.
"""

from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

CANONICAL_COLUMNS = ["conversation_id", "turn_index", "timestamp", "speaker_role", "text", "customer_name", "agent_name"]
REQUIRED = {"conversation_id", "turn_index", "speaker_role", "text"}

COLUMN_ALIASES: dict[str, list[str]] = {
    "conversation_id": ["conv_id", "conversation_id", "conversationid", "thread_id", "ticket_id"],
    "turn_index": ["turn_index", "turn", "message_index", "seq", "position"],
    "timestamp": ["timestamp", "created_at", "time", "datetime", "date"],
    "speaker_role": ["role", "speaker", "speaker_role", "author_role", "sender"],
    "text": ["text", "message", "utterance", "content", "body"],
    "customer_name": ["customer_name", "customer", "customer_id"],
    "agent_name": ["agent_name", "agent", "agent_id"],
}


@dataclass
class LoadedDataset:
    frame: pd.DataFrame
    source_file: str
    member: str | None
    sha256: str
    encoding: str
    delimiter: str
    column_mapping: dict[str, str]
    archive_members: list[str] = field(default_factory=list)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _read_bytes(path: Path) -> tuple[bytes, str | None, list[str]]:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            members = zf.namelist()
            # Ignore macOS resource forks and non-CSV members.
            csvs = [m for m in members if m.lower().endswith(".csv") and not m.startswith("__MACOSX") and "/._" not in m and not Path(m).name.startswith("._")]
            if not csvs:
                raise ValueError(f"No CSV file found in archive {path.name}: {members}")
            if len(csvs) > 1:
                raise ValueError(f"Archive contains several CSV files; specify one: {csvs}")
            return zf.read(csvs[0]), csvs[0], members
    return path.read_bytes(), None, [path.name]


def _detect_encoding(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"


def map_columns(columns: list[str]) -> dict[str, str]:
    """Return {canonical: source} for the columns that could be mapped."""
    lowered = {c.strip().lower(): c for c in columns}
    mapping: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lowered:
                mapping[canonical] = lowered[alias]
                break
    missing = REQUIRED - mapping.keys()
    if missing:
        raise ValueError(f"Required columns missing after mapping: {sorted(missing)}. Found: {columns}")
    return mapping


def load_dataset(path: Path) -> LoadedDataset:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found at {path}")
    raw, member, members = _read_bytes(path)
    encoding = _detect_encoding(raw)
    text = raw.decode(encoding)
    delimiter = csv.Sniffer().sniff(text[:20000], delimiters=",;\t|").delimiter
    frame = pd.read_csv(io.StringIO(text), sep=delimiter, dtype=str, keep_default_na=False)
    mapping = map_columns(list(frame.columns))
    out = pd.DataFrame({canonical: frame[source] for canonical, source in mapping.items()})
    for col in CANONICAL_COLUMNS:
        if col not in out:
            out[col] = ""
    out["source_row"] = range(2, len(out) + 2)  # 1-based CSV line number (header is line 1)
    return LoadedDataset(
        frame=out[CANONICAL_COLUMNS + ["source_row"]],
        source_file=path.name,
        member=member,
        sha256=_sha256(path),
        encoding=encoding,
        delimiter=delimiter,
        column_mapping=mapping,
        archive_members=members,
    )
