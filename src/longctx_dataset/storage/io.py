"""Deterministic, provenance-preserving IO.

Everything is written with sorted keys and ``ensure_ascii=False`` so two runs with the
same seed produce byte-identical files, which is what makes the manifest hashes a
meaningful reproducibility check.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def _dump(obj: Any) -> str:
    if isinstance(obj, BaseModel):
        obj = obj.model_dump(mode="json")
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def write_jsonl(path: Path, rows: Iterable[Any]) -> int:
    """Write rows as JSONL. Returns the row count."""
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(_dump(row))
            fh.write("\n")
            n += 1
    return n


def iter_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    """Stream a JSONL file. Used for instances, which can be very large."""
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: malformed JSONL row: {exc}") from exc


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    return list(iter_jsonl(path))


def read_models(path: Path, model: Type[T]) -> List[T]:
    return [model.model_validate(row) for row in iter_jsonl(path)]


def iter_models(path: Path, model: Type[T]) -> Iterator[T]:
    for row in iter_jsonl(path):
        yield model.model_validate(row)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, BaseModel):
        obj = obj.model_dump(mode="json")
    path.write_text(
        json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


VOLATILE_FIELDS = ("generated_at", "retrieved_at")
"""Wall-clock fields that legitimately differ between runs of identical inputs."""


def _strip_volatile(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_volatile(v) for k, v in obj.items() if k not in VOLATILE_FIELDS}
    if isinstance(obj, list):
        return [_strip_volatile(v) for v in obj]
    return obj


def sha256_jsonl_content(path: Path) -> Optional[str]:
    """Hash a JSONL file's *content*, ignoring wall-clock timestamps.

    File hashes alone cannot verify reproducibility, because every run stamps a fresh
    ``generated_at``. This hash covers everything a rerun with the same seed, config and
    raw cache must reproduce exactly -- questions, gold answers, contexts, ordering --
    and nothing that is expected to change.
    """
    if not path.exists():
        return None
    h = hashlib.sha256()
    for row in iter_jsonl(path):
        h.update(json.dumps(_strip_volatile(row), sort_keys=True, ensure_ascii=False).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def write_parquet(path: Path, rows: List[Dict[str, Any]], drop_columns: Optional[List[str]] = None) -> bool:
    """Optional Parquet mirror. Returns False when pyarrow/pandas are unavailable."""
    try:
        import pandas as pd  # noqa: PLC0415
    except ImportError:
        return False
    if not rows:
        return False
    df = pd.DataFrame(rows)
    for col in drop_columns or []:
        if col in df.columns:
            df = df.drop(columns=[col])

    # `gold_answer_normalized` is deliberately a union (float for numeric answers, the
    # string INSUFFICIENT_EVIDENCE for unanswerable ones). Parquet needs one type per
    # column, so the union is stored as text and a parallel numeric column is added for
    # convenient analysis. JSONL remains the authoritative, lossless format.
    if "gold_answer_normalized" in df.columns:
        df["gold_answer_numeric"] = df["gold_answer_normalized"].apply(
            lambda v: float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
        )

    # Nested dict/list columns are not Parquet-native; store them as JSON strings.
    for col in df.columns:
        if df[col].apply(lambda v: isinstance(v, (dict, list))).any():
            df[col] = df[col].apply(lambda v: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v)
        else:
            # Any remaining column holding more than one scalar type is a union too.
            kinds = {type(v).__name__ for v in df[col] if v is not None}
            if len(kinds) > 1:
                df[col] = df[col].apply(lambda v: None if v is None else str(v))
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_parquet(path, index=False)
    except (ImportError, ValueError, OSError):
        return False
    return True
