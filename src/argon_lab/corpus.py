"""Load the frozen corpus: text documents, diagrams, and frozen diagram captions."""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Doc:
    doc_id: str          # e.g. "ADR-024@v1", exactly the file stem
    title: str
    kind: str            # "text" or "diagram"
    text: str            # full text; for diagrams, the frozen caption (may be empty)
    png: bytes | None = None
    status: str = ""
    date: str = ""


def _meta(text: str, field: str) -> str:
    m = re.search(rf"{field}\**\s*[:|]\s*\**\s*([^\n|*]+)", text, re.I)
    return m.group(1).strip() if m else ""


def _title(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return ""


def load(size: str = "small") -> dict[str, Doc]:
    base = ROOT / "corpus" / size
    docs: dict[str, Doc] = {}
    for p in sorted((base / "docs").glob("*.md")):
        t = p.read_text(encoding="utf-8")
        docs[p.stem] = Doc(p.stem, _title(t), "text", t, status=_meta(t, "Status"), date=_meta(t, "Date"))
    cap_dir = base / "captions"
    for p in sorted((base / "diagrams").glob("*.png")):
        cap = cap_dir / f"{p.stem}.txt"
        docs[p.stem] = Doc(p.stem, f"Diagram {p.stem}", "diagram",
                           cap.read_text(encoding="utf-8") if cap.exists() else "", png=p.read_bytes())
    return docs


def png_b64(doc: Doc) -> str:
    return base64.b64encode(doc.png or b"").decode()
