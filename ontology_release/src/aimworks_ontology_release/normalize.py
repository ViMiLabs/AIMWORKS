from __future__ import annotations

import re
from datetime import datetime, timezone


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _identifier_words(text: str) -> str:
    value = text.replace("_", " ").replace("-", " ")
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    value = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", value)
    return normalize_text(value)


def humanize_identifier(identifier: str) -> str:
    value = _identifier_words(identifier)
    if not value:
        return value
    parts = value.split(" ")
    acronyms = {"PEMFC", "QUDT", "EMMO", "ECHO", "IRI", "OWL", "RDF", "SKOS"}
    return " ".join(part if part.upper() in acronyms else part.capitalize() for part in parts)


def normalize_label(label: str) -> str:
    return _identifier_words(label).lower()


def token_set(label: str) -> set[str]:
    return {token for token in re.split(r"[^A-Za-z0-9]+", normalize_label(label)) if token}


def coerce_version(version: str | None = None) -> str:
    if version:
        return version
    now = datetime.now(timezone.utc)
    return f"{now.year}.{now.month}.0"
