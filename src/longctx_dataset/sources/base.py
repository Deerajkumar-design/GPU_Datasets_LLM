"""Source-adapter contract and the shared HTTP layer.

Design rules enforced here:

* A source failure is never silently swallowed. An adapter either returns real records
  or raises :class:`SourceBlocked`, which the pipeline records as an explicit blocker.
* Every raw payload is cached to disk with the request URL and retrieval timestamp, so
  a generated dataset stays reproducible even when the live API moves on.
* Rate limits are honoured per-host (SEC in particular publishes a hard limit).
"""

from __future__ import annotations

import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

import requests

from ..config import PipelineConfig
from ..schemas import Domain, NormalizedRecord, RawReference


class SourceBlocked(RuntimeError):
    """Raised when a primary source cannot be used honestly.

    Examples: a missing SEC User-Agent contact, a persistent 403, an API version that
    no longer exists. The caller records the blocker; it never substitutes other data.
    """

    def __init__(self, domain: str, reason: str, remedy: Optional[str] = None):
        self.domain = domain
        self.reason = reason
        self.remedy = remedy
        super().__init__(f"[{domain}] {reason}" + (f" Remedy: {remedy}" if remedy else ""))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass
class RetrievalResult:
    """What one adapter produced during a fetch, plus everything needed to audit it."""

    domain: Domain
    source: str
    api_base: str
    api_version: Optional[str] = None
    retrieved_at: str = field(default_factory=utc_now)
    raw_paths: List[Path] = field(default_factory=list)
    identifiers: List[str] = field(default_factory=list)
    n_requests: int = 0
    n_raw_records: int = 0
    errors: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    blocked: bool = False
    blocker_reason: Optional[str] = None


class _RateLimiter:
    """Simple monotonic-clock spacing limiter (one per host)."""

    def __init__(self, per_second: float):
        self.min_interval = 1.0 / per_second if per_second > 0 else 0.0
        self._last = 0.0

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        now = time.monotonic()
        delta = now - self._last
        if delta < self.min_interval:
            time.sleep(self.min_interval - delta)
        self._last = time.monotonic()


class HTTPClient:
    """Rate-limited, retrying, caching JSON client.

    Cached payloads live under ``data/raw/<subdir>/`` keyed by a hash of the full URL,
    so re-running ``fetch`` is idempotent and offline-friendly.
    """

    def __init__(
        self,
        cfg: PipelineConfig,
        raw_subdir: str,
        headers: Optional[Dict[str, str]] = None,
        rate_limit_per_second: Optional[float] = None,
        timeout_seconds: Optional[float] = None,
    ):
        self.cfg = cfg
        self.timeout = timeout_seconds or cfg.http.timeout_seconds
        self.raw_dir = cfg.raw_dir / raw_subdir
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(headers or {})
        self.limiter = _RateLimiter(rate_limit_per_second or cfg.http.default_rate_limit_per_second)
        self.n_requests = 0
        self.request_log: List[Dict[str, Any]] = []

    def _cache_path(self, url: str, params: Optional[Dict[str, Any]]) -> Path:
        key = url + "?" + json.dumps(params or {}, sort_keys=True)
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
        return self.raw_dir / f"{digest}.json"

    def get_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        use_cache: Optional[bool] = None,
        allow_404: bool = False,
    ) -> tuple[Optional[Any], Path]:
        """GET a JSON endpoint. Returns ``(payload_or_None, cache_path)``.

        ``None`` is returned only for an allowed 404 -- every other failure raises,
        because a quietly empty result would corrupt the dataset without a trace.
        """
        cache = self._cache_path(url, params)
        use_cache = self.cfg.http.cache_enabled if use_cache is None else use_cache

        if use_cache and cache.exists():
            envelope = json.loads(cache.read_text(encoding="utf-8"))
            return envelope.get("payload"), cache

        last_exc: Optional[Exception] = None
        for attempt in range(self.cfg.http.max_retries):
            self.limiter.wait()
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                self.n_requests += 1
                if resp.status_code == 404 and allow_404:
                    self.request_log.append({"url": resp.url, "status": 404, "at": utc_now()})
                    return None, cache
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"HTTP {resp.status_code} from {resp.url}")
                resp.raise_for_status()
                payload = resp.json()
                envelope = {
                    "request_url": resp.url,
                    "status": resp.status_code,
                    "retrieved_at": utc_now(),
                    "payload": payload,
                }
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(
                    json.dumps(envelope, sort_keys=False, ensure_ascii=False), encoding="utf-8"
                )
                self.request_log.append({"url": resp.url, "status": resp.status_code, "at": utc_now()})
                return payload, cache
            except (requests.RequestException, ValueError) as exc:
                last_exc = exc
                if attempt < self.cfg.http.max_retries - 1:
                    time.sleep(self.cfg.http.backoff_seconds * (2**attempt))
        raise SourceBlocked(
            self.raw_dir.name,
            f"GET {url} failed after {self.cfg.http.max_retries} attempts: {last_exc}",
        )

    # Raw payloads can be tens of megabytes; normalization asks for the request URL once
    # per record, so the lookup is memoized per path rather than re-parsing the file.
    _URL_CACHE: Dict[str, Optional[str]] = {}

    @classmethod
    def cached_request_url(cls, cache_path: Path) -> Optional[str]:
        key = str(cache_path)
        if key in cls._URL_CACHE:
            return cls._URL_CACHE[key]
        url: Optional[str] = None
        if cache_path.exists():
            try:
                url = json.loads(cache_path.read_text(encoding="utf-8")).get("request_url")
            except (json.JSONDecodeError, OSError):
                url = None
        cls._URL_CACHE[key] = url
        return url


class SourceAdapter(ABC):
    """Contract every primary-source adapter implements.

    The split between :meth:`fetch` and :meth:`normalize` is what keeps the raw layer
    intact: ``fetch`` only ever writes verbatim API payloads, and ``normalize`` is a
    pure function of those payloads, so normalization can be re-run offline.
    """

    domain: Domain
    source_name: str
    api_base: str
    api_version: Optional[str] = None
    license_note: Optional[str] = None

    def __init__(self, cfg: PipelineConfig):
        self.cfg = cfg
        self.domain_cfg = cfg.domains.get(self.domain)
        self.params: Dict[str, Any] = dict(self.domain_cfg.params) if self.domain_cfg else {}

    # ---- lifecycle -----------------------------------------------------------------

    def check_availability(self) -> Optional[str]:
        """Return a blocker reason if this adapter must not run, else ``None``."""
        return None

    @abstractmethod
    def fetch(self) -> RetrievalResult:
        """Retrieve raw payloads from the primary source and cache them to ``data/raw``."""

    @abstractmethod
    def normalize(self) -> List[NormalizedRecord]:
        """Convert cached raw payloads into the common record envelope. Pure + offline."""

    # ---- helpers -------------------------------------------------------------------

    @property
    def raw_subdir(self) -> str:
        return self.domain.value.lower()

    def raw_dir(self) -> Path:
        d = self.cfg.raw_dir / self.raw_subdir
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _raw_reference(self, cache_path: Path, pointer: str, retrieved_at: Optional[str] = None) -> RawReference:
        return RawReference(
            source_url=HTTPClient.cached_request_url(cache_path),
            raw_file=str(cache_path),
            raw_pointer=pointer,
            retrieved_at=retrieved_at or utc_now(),
        )

    def iter_raw_payloads(self):
        """Yield ``(envelope, path)`` for every cached payload belonging to this adapter."""
        for path in sorted(self.raw_dir().glob("*.json")):
            try:
                yield json.loads(path.read_text(encoding="utf-8")), path
            except (json.JSONDecodeError, OSError) as exc:
                raise ValueError(f"corrupt raw payload {path}: {exc}") from exc


# --------------------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------------------

_REGISTRY: Dict[Domain, Type[SourceAdapter]] = {}


def register_adapter(cls: Type[SourceAdapter]) -> Type[SourceAdapter]:
    """Class decorator that makes an adapter discoverable by domain."""
    _REGISTRY[cls.domain] = cls
    return cls


def get_adapter(domain: Domain, cfg: PipelineConfig) -> SourceAdapter:
    if domain not in _REGISTRY:
        raise KeyError(
            f"no adapter registered for domain {domain}; registered: {sorted(d.value for d in _REGISTRY)}"
        )
    return _REGISTRY[domain](cfg)


def available_adapters() -> List[Domain]:
    return sorted(_REGISTRY, key=lambda d: d.value)
