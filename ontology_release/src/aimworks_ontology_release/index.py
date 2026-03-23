from __future__ import annotations

from pathlib import Path
from typing import Any

from .sources import builtin_source_terms, load_sources


def build_source_index(config_dir: str | Path | None = None) -> list[dict[str, Any]]:
    sources = load_sources(config_dir)
    enabled = {source.identifier for source in sources if source.enabled}
    terms = [term for term in builtin_source_terms() if term["source"] in enabled or term["source"] == "foaf"]
    return terms
