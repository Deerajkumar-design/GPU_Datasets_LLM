"""Typed configuration loading, with a stable hash for reproducibility.

The config hash is computed over the *semantic* config (the parsed, normalized model
dump), not the YAML bytes, so reformatting a comment does not invalidate a dataset.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .schemas import Domain, QuestionType

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def _expand_env(obj: Any) -> Any:
    """Recursively expand ``${VAR}`` / ``${VAR:-default}`` inside string values."""
    if isinstance(obj, str):
        def repl(m: re.Match) -> str:
            return os.environ.get(m.group(1), m.group(2) if m.group(2) is not None else "")
        return _ENV_PATTERN.sub(repl, obj)
    if isinstance(obj, dict):
        return {k: _expand_env(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_env(v) for v in obj]
    return obj


class TokenizerConfig(BaseModel):
    """The tokenizer is an experimental parameter, never a hard-coded constant.

    ``id`` uses a ``backend:name`` scheme so a different backend can be swapped in
    once the model under test is chosen, without touching generation code.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field("tiktoken:cl100k_base", description="'tiktoken:<enc>', 'hf:<model>', or 'whitespace:v1'.")
    fallback_id: Optional[str] = Field(
        "whitespace:v1",
        description="Used only if the primary backend is unavailable offline. Recorded in outputs.",
    )
    allow_fallback: bool = False


class ContextConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lengths: List[int] = Field(default_factory=lambda: [4096, 8192, 16384, 32768, 65536, 131072])
    target_position: float = 0.50
    position_tolerance: float = 0.05
    min_fill_ratio: float = Field(
        0.95,
        description="A variant is only emitted if actual tokens >= min_fill_ratio * nominal. "
        "Below that it is recorded as UNAVAILABLE rather than padded.",
    )
    record_open_template: str = '<RECORD id="{record_id}" source="{source}">'
    record_close: str = "</RECORD>"
    record_separator: str = "\n"

    @field_validator("lengths")
    @classmethod
    def _sorted_unique(cls, v: List[int]) -> List[int]:
        if sorted(set(v)) != v:
            raise ValueError("context.lengths must be strictly increasing and unique (nesting depends on it)")
        return v

    @model_validator(mode="after")
    def _bounds(self) -> "ContextConfig":
        if not 0.0 < self.target_position < 1.0:
            raise ValueError("context.target_position must be in (0, 1)")
        if not 0.0 < self.min_fill_ratio <= 1.0:
            raise ValueError("context.min_fill_ratio must be in (0, 1]")
        return self


class DomainConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = True
    n_families: int = 0
    question_type_mix: Dict[QuestionType, float] = Field(default_factory=dict)
    question_type_counts: Dict[QuestionType, int] = Field(
        default_factory=dict,
        description="Explicit per-type family counts. Overrides question_type_mix when "
        "set. Needed when a fractional target is not reachable by rounding within one "
        "domain -- 30% of 25 is 7.5 -- but the totals across domains must still land "
        "exactly on the design.",
    )
    params: Dict[str, Any] = Field(default_factory=dict)


class HTTPConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeout_seconds: float = 30.0
    max_retries: int = 4
    backoff_seconds: float = 1.5
    sec_user_agent: Optional[str] = None
    sec_rate_limit_per_second: float = 8.0
    openfda_api_key: Optional[str] = None
    # Optional: upgrades the FRED adapter from the keyless CSV endpoints to the
    # JSON API, which supplies authoritative series metadata.
    fred_api_key: Optional[str] = None
    default_rate_limit_per_second: float = 5.0
    cache_enabled: bool = True


class ValidationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fail_on: List[str] = Field(
        default_factory=lambda: ["CRITICAL"],
        description="Severities that make `validate` exit nonzero.",
    )
    numeric_recompute_rel_tolerance: float = 1e-9
    require_all_question_types: bool = True
    max_leakage_value_rel_tolerance: float = Field(
        1e-6,
        description="A distractor whose value matches the withheld answer within this "
        "relative tolerance counts as leakage.",
    )


class PipelineConfig(BaseModel):
    """Root config object."""

    model_config = ConfigDict(extra="forbid")

    name: str = "pilot"
    seed: int = 20240817
    data_root: Path = Path("data")
    output_subdir: str = "pilot"
    schema_version: str = "1.0.0"
    write_parquet: bool = False

    tokenizer: TokenizerConfig = Field(default_factory=TokenizerConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    http: HTTPConfig = Field(default_factory=HTTPConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)

    domains: Dict[Domain, DomainConfig] = Field(default_factory=dict)

    # Populated at load time; excluded from the hash to avoid self-reference.
    config_path: Optional[Path] = None
    config_hash: str = ""

    # ---- derived paths -------------------------------------------------------------

    @property
    def raw_dir(self) -> Path:
        return self.data_root / "raw"

    @property
    def normalized_dir(self) -> Path:
        return self.data_root / "normalized"

    @property
    def out_dir(self) -> Path:
        return self.data_root / self.output_subdir

    @property
    def manifest_dir(self) -> Path:
        return self.data_root / "manifests"

    @property
    def report_dir(self) -> Path:
        return self.data_root / "reports"

    def enabled_domains(self) -> List[Domain]:
        return [d for d, c in self.domains.items() if c.enabled]

    def ensure_dirs(self) -> None:
        for p in (self.raw_dir, self.normalized_dir, self.out_dir, self.manifest_dir, self.report_dir):
            p.mkdir(parents=True, exist_ok=True)

    def compute_hash(self) -> str:
        payload = self.model_dump(mode="json", exclude={"config_path", "config_hash", "data_root"})
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def load_config(path: str | Path) -> PipelineConfig:
    """Load YAML, expand env vars, validate, and stamp the config hash."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"config not found: {path}")
    raw = yaml.safe_load(path.read_text()) or {}
    raw = _expand_env(raw)

    cfg = PipelineConfig.model_validate(raw)
    cfg.config_path = path

    # Environment always wins over YAML for secrets/contact info.
    env_ua = os.environ.get("SEC_USER_AGENT")
    if env_ua:
        cfg.http.sec_user_agent = env_ua
    if not cfg.http.sec_user_agent:
        cfg.http.sec_user_agent = None
    env_key = os.environ.get("OPENFDA_API_KEY")
    if env_key:
        cfg.http.openfda_api_key = env_key
    if not cfg.http.openfda_api_key:
        cfg.http.openfda_api_key = None
    env_fred = os.environ.get("FRED_API_KEY")
    if env_fred:
        cfg.http.fred_api_key = env_fred
    if not cfg.http.fred_api_key:
        cfg.http.fred_api_key = None

    cfg.config_hash = cfg.compute_hash()
    return cfg


def git_commit(repo_root: Optional[Path] = None) -> Optional[str]:
    """Best-effort current commit SHA; ``None`` outside a git repo."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root) if repo_root else None,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None
