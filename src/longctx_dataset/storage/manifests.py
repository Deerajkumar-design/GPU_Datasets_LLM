"""Dataset manifests: the reproducibility receipt for a generation run."""

from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .. import GENERATOR_VERSION, SCHEMA_VERSION
from .io import sha256_file, write_json


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class FileEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    bytes: int
    sha256: str
    rows: Optional[int] = None


class SourceRetrieval(BaseModel):
    """One adapter's fetch summary, so a run can be traced back to live API state."""

    model_config = ConfigDict(extra="forbid")

    domain: str
    source: str
    api_base: str
    api_version: Optional[str] = None
    retrieved_at: str
    n_requests: int = 0
    n_raw_payloads: int = 0
    n_raw_records: int = 0
    n_normalized_records: int = 0
    identifiers: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    blocked: bool = False
    blocker_reason: Optional[str] = None


class DatasetManifest(BaseModel):
    """Hashes + environment + config identity for one pipeline run."""

    model_config = ConfigDict(extra="forbid")

    manifest_version: str = "1.0.0"
    dataset_name: str
    generated_at: str = Field(default_factory=utc_now)

    generator_version: str = GENERATOR_VERSION
    schema_version: str = SCHEMA_VERSION
    config_path: Optional[str] = None
    config_hash: str
    seed: int
    git_commit: Optional[str] = None

    tokenizer_id: str
    tokenizer_version: Optional[str] = None

    python_version: str = Field(default_factory=lambda: sys.version.split()[0])
    platform: str = Field(default_factory=platform.platform)

    counts: Dict[str, int] = Field(default_factory=dict)
    files: List[FileEntry] = Field(default_factory=list)
    source_retrievals: List[SourceRetrieval] = Field(default_factory=list)
    stage_timings_seconds: Dict[str, float] = Field(default_factory=dict)
    extra: Dict[str, Any] = Field(default_factory=dict)

    def add_file(self, path: Path, rows: Optional[int] = None, root: Optional[Path] = None) -> None:
        if not path.exists():
            return
        rel = str(path.relative_to(root)) if root and root in path.parents else str(path)
        self.files.append(
            FileEntry(path=rel, bytes=path.stat().st_size, sha256=sha256_file(path), rows=rows)
        )

    def save(self, path: Path) -> None:
        write_json(path, self)
